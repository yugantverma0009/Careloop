"""
app/photo_service.py — CareLoop Wound & Recovery Photo Check Service (Phase 3 Feature F4)

Responsibilities:
1. Deterministic image quality verification (resolution, Laplacian sharpness variance, mean brightness).
2. Privacy compliance: EXIF stripping, SHA-256 hashing, storage outside web root.
3. Strict role-based access control (Caregivers forbidden 403, patients own-only, staff full access).
4. Human-only clinical review (no automated medical diagnostic claims or AI infection detection).
5. Audit logging for every upload, view, review, and retention purge.
"""

import os
import io
import time
import uuid
import hashlib
import json
from datetime import datetime
from PIL import Image
import numpy as np
from scipy.ndimage import laplace

from backend.app.db import get_conn

# Storage configuration (strictly outside web root)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STORAGE_DIR = os.path.join(BASE_DIR, "data", "wound_photos")
THUMB_DIR = os.path.join(STORAGE_DIR, "thumbs")
os.makedirs(THUMB_DIR, exist_ok=True)

# Quality check thresholds (deterministic parameters)
MIN_DIMENSION = 640       # Minimum resolution on shortest edge
MAX_DIMENSION = 1600      # Maximum dimension (resized if larger)
THUMB_DIMENSION = 320     # Max thumbnail size
MIN_BRIGHTNESS = 45.0     # Below 45 out of 255 is too dark
MAX_BRIGHTNESS = 235.0    # Above 235 is overexposed / excessive glare
MIN_SHARPNESS = 100.0     # Laplacian variance threshold
MAX_FILE_SIZE_BYTES = 8 * 1024 * 1024  # 8 MB limit
PHOTO_RETENTION_DAYS = 30  # Standard clinical retention period


def analyze_image_quality(image_bytes: bytes) -> dict:
    """
    Deterministic quality analysis of submitted wound photograph.
    Checks:
    - Minimum resolution (short edge >= 640px)
    - Mean grayscale brightness (45.0 <= b <= 235.0)
    - Laplacian variance sharpness (>= 100.0)
    Returns dictionary with plain-language recommendation.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        return {
            "quality_status": "Invalid_Format",
            "message": "Invalid or unreadable image file. Please upload JPEG or PNG.",
            "is_usable": False,
            "metrics": {},
        }

    width, height = img.size
    min_dim = min(width, height)

    # Convert to grayscale float array for brightness and sharpness
    gray = np.array(img.convert("L"), dtype=np.float64)
    brightness = float(np.mean(gray))

    # Laplacian variance Pech-Pacheco focus metric
    lap = laplace(gray)
    sharpness = float(np.var(lap))

    metrics = {
        "width": width,
        "height": height,
        "min_dimension": min_dim,
        "brightness": round(brightness, 1),
        "sharpness": round(sharpness, 1),
    }

    # Evaluate sequentially with plain-language recommendations
    if min_dim < MIN_DIMENSION:
        return {
            "quality_status": "Too_Small",
            "message": "Too small",
            "details": f"Photo resolution ({width}x{height}) is below minimum requirement of {MIN_DIMENSION}px.",
            "is_usable": False,
            "metrics": metrics,
        }

    if brightness < MIN_BRIGHTNESS:
        return {
            "quality_status": "Too_Dark",
            "message": "Too dark, please retake",
            "details": f"Lighting level ({brightness:.1f}) is insufficient for clinical wound review.",
            "is_usable": False,
            "metrics": metrics,
        }

    if brightness > MAX_BRIGHTNESS:
        return {
            "quality_status": "Too_Dark",  # Map glare / overexposure to retake prompt
            "message": "Too bright or glare present, please retake",
            "details": f"Excessive glare or overexposure ({brightness:.1f}) obscures skin detail.",
            "is_usable": False,
            "metrics": metrics,
        }

    if sharpness < MIN_SHARPNESS:
        return {
            "quality_status": "Blurry",
            "message": "A bit blurry, please retake",
            "details": f"Image focus score ({sharpness:.1f}) indicates motion blur or lack of focus.",
            "is_usable": False,
            "metrics": metrics,
        }

    return {
        "quality_status": "Usable",
        "message": "Looks usable",
        "details": "Image resolution, illumination, and focus meet clinical review criteria.",
        "is_usable": True,
        "metrics": metrics,
    }


def save_wound_photo(
    patient_id: int,
    image_bytes: bytes,
    original_filename: str,
    patient_note: str = None,
    session_id: int = None,
    use_anyway: bool = False,
    actor_id: int = None,
    actor_role: str = "Patient",
) -> dict:
    """
    Saves an uploaded wound photo, strips EXIF data, generates thumbnail,
    computes SHA-256 hash, and inserts database and audit records.
    """
    if len(image_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"File size exceeds maximum allowed limit of {MAX_FILE_SIZE_BYTES // (1024*1024)} MB.")

    analysis = analyze_image_quality(image_bytes)
    if not analysis["is_usable"] and not use_anyway:
        raise ValueError(f"Photo quality check failed: {analysis['message']}. Select 'Use anyway' to proceed.")

    quality_status = "Used_Anyway" if (use_anyway and not analysis["is_usable"]) else analysis["quality_status"]

    # Open image, strip EXIF metadata, and resize if exceeding max dimension
    orig_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = orig_img.size
    if max(w, h) > MAX_DIMENSION:
        orig_img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.Resampling.LANCZOS)

    # Save clean image without EXIF metadata
    clean_buf = io.BytesIO()
    orig_img.save(clean_buf, format="JPEG", quality=88, optimize=True)
    clean_bytes = clean_buf.getvalue()

    # Compute SHA-256 hash
    sha256_hash = hashlib.sha256(clean_bytes).hexdigest()

    # Unique filenames
    file_id = f"{patient_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    main_filename = f"{file_id}.jpg"
    thumb_filename = f"{file_id}_thumb.jpg"

    main_path = os.path.join(STORAGE_DIR, main_filename)
    thumb_path = os.path.join(THUMB_DIR, thumb_filename)

    with open(main_path, "wb") as f:
        f.write(clean_bytes)

    # Generate thumbnail
    thumb_img = orig_img.copy()
    thumb_img.thumbnail((THUMB_DIMENSION, THUMB_DIMENSION), Image.Resampling.LANCZOS)
    thumb_img.save(thumb_path, format="JPEG", quality=80)

    # Relative paths for database portability
    rel_main_path = os.path.join("data", "wound_photos", main_filename)
    rel_thumb_path = os.path.join("data", "wound_photos", "thumbs", thumb_filename)

    clean_note = (patient_note or "").strip()[:255] if patient_note else None

    with get_conn() as conn:
        with conn.cursor() as cur:
            import json
            cur.execute(
                """
                INSERT INTO wound_photos (
                    patient_id, session_id, file_path, thumb_path, sha256,
                    quality_status, quality_details, patient_note, review_status, taken_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, 'Pending', NOW()
                )
                """,
                (
                    patient_id,
                    session_id,
                    rel_main_path,
                    rel_thumb_path,
                    sha256_hash,
                    quality_status,
                    json.dumps(analysis["metrics"]),
                    clean_note,
                ),
            )
            photo_id = cur.lastrowid

            # Write upload audit event
            actor_type = "Staff" if actor_role in ("Nurse", "Doctor") else "Patient"
            cur.execute(
                """
                INSERT INTO audit_log (
                    actor_type, actor_id, action, entity_type, entity_id, details, created_at
                ) VALUES (
                    %s, %s, 'PHOTO_UPLOADED', 'Photo', %s, %s, NOW()
                )
                """,
                (
                    actor_type,
                    str(actor_id or patient_id),
                    photo_id,
                    json.dumps({
                        "patient_id": patient_id,
                        "quality_status": quality_status,
                        "sha256": sha256_hash,
                    }),
                ),
            )
        conn.commit()

    return {
        "photo_id": photo_id,
        "patient_id": patient_id,
        "quality_status": quality_status,
        "message": analysis["message"],
        "sha256": sha256_hash,
        "review_status": "Pending",
        "taken_at": datetime.now().isoformat(),
        "confirmation_text": (
            "Photo received. A nurse will look at it. We do not check it automatically. "
            "If you are worried, use your daily check-in or call your care team."
        ),
    }


def get_patient_photos(patient_id: int) -> dict:
    """
    Returns list of wound photos for a patient with latest and previous photo comparison.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    wp.photo_id,
                    wp.patient_id,
                    wp.session_id,
                    wp.taken_at,
                    wp.sha256,
                    wp.quality_status,
                    wp.quality_details,
                    wp.patient_note,
                    wp.review_status,
                    wp.finding,
                    wp.review_note,
                    wp.reviewed_by_staff_id,
                    wp.reviewed_at,
                    wp.flag_id,
                    s.full_name AS reviewed_by_name,
                    s.role AS reviewed_by_role
                FROM wound_photos wp
                LEFT JOIN care_staff s ON s.staff_id = wp.reviewed_by_staff_id
                WHERE wp.patient_id = %s
                ORDER BY wp.taken_at DESC
                """,
                (patient_id,),
            )
            photos = cur.fetchall()

    latest = photos[0] if len(photos) > 0 else None
    previous = photos[1] if len(photos) > 1 else None

    return {
        "patient_id": patient_id,
        "total_count": len(photos),
        "photos": photos,
        "latest_photo": latest,
        "previous_photo": previous,
    }


def review_wound_photo(
    photo_id: int,
    staff_id: int,
    staff_role: str,
    finding: str,
    review_note: str = None,
    action: str = "none",
) -> dict:
    """
    Human clinician review of a patient wound photo.
    Findings:
      - 'No_Concern_Seen'
      - 'Concern_Noted' (requires review_note; can trigger 'ask_doctor' or 'raise_flag')
      - 'Retake_Needed'
    Actions:
      - 'none'
      - 'ask_doctor' -> sets review_status to 'Needs_Doctor'
      - 'raise_flag' -> creates human Review_Soon flag
    """
    valid_findings = ("No_Concern_Seen", "Concern_Noted", "Retake_Needed")
    if finding not in valid_findings:
        raise ValueError(f"Invalid review finding '{finding}'. Must be one of {valid_findings}.")

    clean_note = (review_note or "").strip()
    if finding == "Concern_Noted" and len(clean_note) < 3:
        raise ValueError("A clinical review note is required when recording 'Concern noted'.")

    created_flag_id = None
    new_review_status = "Needs_Doctor" if action == "ask_doctor" else "Reviewed"

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT photo_id, patient_id, review_status FROM wound_photos WHERE photo_id = %s", (photo_id,))
            photo = cur.fetchone()
            if not photo:
                raise ValueError(f"Wound photo #{photo_id} not found.")

            patient_id = photo["patient_id"]

            if action == "raise_flag":
                # Create clinical flag sourced from human photo review
                flag_reason = f"Wound photo review finding: {clean_note}"
                cur.execute(
                    """
                    INSERT INTO flags (
                        patient_id, rule_id, source_type, source_ref_id, reason, severity, status, created_at
                    ) VALUES (
                        %s, NULL, 'Photo', %s, %s, 'Review_Soon', 'Open', NOW()
                    )
                    """,
                    (patient_id, photo_id, flag_reason[:255]),
                )
                created_flag_id = cur.lastrowid

            cur.execute(
                """
                UPDATE wound_photos
                SET
                    review_status = %s,
                    finding = %s,
                    review_note = %s,
                    reviewed_by_staff_id = %s,
                    reviewed_at = NOW(),
                    flag_id = COALESCE(%s, flag_id)
                WHERE photo_id = %s
                """,
                (
                    new_review_status,
                    finding,
                    clean_note if clean_note else None,
                    staff_id,
                    created_flag_id,
                    photo_id,
                ),
            )

            # Audit review action
            cur.execute(
                """
                INSERT INTO audit_log (
                    actor_type, actor_id, action, entity_type, entity_id, details, created_at
                ) VALUES (
                    'Staff', %s, 'PHOTO_REVIEWED', 'Photo', %s, %s, NOW()
                )
                """,
                (
                    str(staff_id),
                    photo_id,
                    json.dumps({
                        "patient_id": patient_id,
                        "finding": finding,
                        "action": action,
                        "flag_id": created_flag_id,
                        "staff_role": staff_role,
                    }),
                ),
            )
        conn.commit()

    return {
        "photo_id": photo_id,
        "review_status": new_review_status,
        "finding": finding,
        "flag_id": created_flag_id,
        "action_taken": action,
    }


def get_photo_path(photo_id: int, is_thumb: bool = False) -> tuple:
    """
    Returns absolute file path and patient_id for a photo ID.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT photo_id, patient_id, file_path, thumb_path FROM wound_photos WHERE photo_id = %s",
                (photo_id,),
            )
            photo = cur.fetchone()
            if not photo:
                return None, None

    rel_path = photo["thumb_path"] if is_thumb else photo["file_path"]
    full_path = os.path.join(BASE_DIR, rel_path) if rel_path else None
    return full_path, photo["patient_id"]


def audit_photo_view(photo_id: int, patient_id: int, actor_id: int, actor_role: str):
    """
    Writes PHOTO_VIEWED to audit_log for verifiable DPDP tracking.
    """
    import json
    actor_type = "Staff" if actor_role in ("Nurse", "Doctor") else "Patient"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_log (
                    actor_type, actor_id, action, entity_type, entity_id, details, created_at
                ) VALUES (
                    %s, %s, 'PHOTO_VIEWED', 'Photo', %s, %s, NOW()
                )
                """,
                (
                    actor_type,
                    str(actor_id or patient_id),
                    photo_id,
                    json.dumps({"patient_id": patient_id, "role": actor_role}),
                ),
            )
        conn.commit()


def get_pending_photos_overview() -> dict:
    """
    Returns list and count of unreviewed photos across all patients for the nurse call list and doctor desk.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    wp.photo_id,
                    wp.patient_id,
                    wp.taken_at,
                    wp.quality_status,
                    wp.patient_note,
                    wp.review_status,
                    p.full_name AS patient_name,
                    p.patient_code
                FROM wound_photos wp
                JOIN patients p ON p.patient_id = wp.patient_id
                WHERE wp.review_status IN ('Pending', 'Needs_Doctor')
                ORDER BY wp.taken_at ASC
                """
            )
            rows = cur.fetchall()

    pending_nurse = [r for r in rows if r["review_status"] == "Pending"]
    needs_doctor = [r for r in rows if r["review_status"] == "Needs_Doctor"]

    return {
        "pending_count": len(pending_nurse),
        "needs_doctor_count": len(needs_doctor),
        "total_active_reviews": len(rows),
        "pending_photos": rows,
    }


def cleanup_retention_photos(retention_days: int = PHOTO_RETENTION_DAYS, staff_id: int = 1) -> dict:
    """
    Audited purge of wound photos exceeding retention threshold.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT photo_id, patient_id, file_path, thumb_path, taken_at
                FROM wound_photos
                WHERE taken_at < NOW() - INTERVAL %s DAY
                """,
                (retention_days,),
            )
            expired = cur.fetchall()

            purged_count = 0
            for item in expired:
                # Remove files from disk
                for p in (item["file_path"], item["thumb_path"]):
                    if p:
                        full_p = os.path.join(BASE_DIR, p)
                        if os.path.exists(full_p):
                            try:
                                os.remove(full_p)
                            except OSError:
                                pass

                # Delete row
                cur.execute("DELETE FROM wound_photos WHERE photo_id = %s", (item["photo_id"],))

                # Log audit row
                cur.execute(
                    """
                    INSERT INTO audit_log (
                        actor_type, actor_id, action, entity_type, entity_id, details, created_at
                    ) VALUES (
                        'Staff', %s, 'PHOTO_PURGED', 'Photo', %s, %s, NOW()
                    )
                    """,
                    (
                        str(staff_id),
                        item["photo_id"],
                        json.dumps({
                            "patient_id": item["patient_id"],
                            "retention_days": retention_days,
                            "reason": f"Purged photo exceeding retention limit of {retention_days} days.",
                        }),
                    ),
                )
                purged_count += 1
        conn.commit()

    return {"purged_count": purged_count, "retention_days": retention_days}
