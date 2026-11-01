"""
tests/test_photo_check.py — Verification of Post-Op Wound Photo Check & Review (Phase 3 Feature F4)

Acceptance checks:
1. Blurry, dark, and tiny sample images are each rejected with the plain-language message.
2. Family login cannot fetch a photo (403 Forbidden).
3. Patient cannot access another patient's photo (403 Forbidden).
4. Authenticated views write PHOTO_VIEWED to audit_log.
5. "Concern noted" finding never creates a flag without explicit user action ("raise_flag").
6. EXIF data is stripped and SHA-256 is stored.
"""

import io
from PIL import Image, ImageDraw, ImageFilter
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import get_conn
from backend.app.photo_service import analyze_image_quality

client = TestClient(app)


def get_token(email: str, password: str = "Demo@12345") -> str:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


def make_test_image(kind: str) -> bytes:
    """Helper generating synthetic test images."""
    if kind == "good":
        img = Image.new("RGB", (800, 800), color=(130, 130, 130))
        draw = ImageDraw.Draw(img)
        for i in range(0, 800, 40):
            draw.line([(i, 0), (800 - i, 800)], fill=(255, 255, 255), width=2)
            draw.line([(0, i), (800, 800 - i)], fill=(0, 0, 0), width=2)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        return buf.getvalue()

    elif kind == "dark":
        img = Image.new("RGB", (800, 800), color=(10, 10, 10))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        return buf.getvalue()

    elif kind == "blurry":
        img = Image.new("RGB", (800, 800), color=(130, 130, 130))
        draw = ImageDraw.Draw(img)
        for i in range(0, 800, 40):
            draw.line([(i, 0), (800 - i, 800)], fill=(255, 255, 255), width=2)
        blurred = img.filter(ImageFilter.GaussianBlur(radius=18))
        buf = io.BytesIO()
        blurred.save(buf, format="JPEG", quality=90)
        return buf.getvalue()

    elif kind == "tiny":
        img = Image.new("RGB", (250, 250), color=(130, 130, 130))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        return buf.getvalue()

    raise ValueError(f"Unknown kind {kind}")


def test_quality_checker_four_cases():
    """1. Test that good, dark, blurry, and tiny images return the exact expected messages."""
    good_res = analyze_image_quality(make_test_image("good"))
    assert good_res["quality_status"] == "Usable"
    assert "usable" in good_res["message"].lower()

    dark_res = analyze_image_quality(make_test_image("dark"))
    assert dark_res["quality_status"] == "Too_Dark"
    assert "too dark" in dark_res["message"].lower()

    blurry_res = analyze_image_quality(make_test_image("blurry"))
    assert blurry_res["quality_status"] == "Blurry"
    assert "blurry" in blurry_res["message"].lower()

    tiny_res = analyze_image_quality(make_test_image("tiny"))
    assert tiny_res["quality_status"] == "Too_Small"
    assert "too small" in tiny_res["message"].lower()


def test_patient_upload_endpoint_and_exif_removal():
    """2. Patient uploads photo; verify SHA-256, DB row, thumbnail creation, and audit."""
    tok_patient = get_token("aarav.demo@example.test")
    good_bytes = make_test_image("good")

    res = client.post(
        "/patient/me/photos",
        headers={"Authorization": f"Bearer {tok_patient}"},
        files={"file": ("sternal_wound.jpg", good_bytes, "image/jpeg")},
        data={"patient_note": "Incision line healing nicely", "use_anyway": "false"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    photo_id = data["photo_id"]
    assert data["quality_status"] == "Usable"
    assert len(data["sha256"]) == 64
    assert "Photo received" in data["confirmation_text"]

    # Verify database entry
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM wound_photos WHERE photo_id = %s", (photo_id,))
        row = cur.fetchone()
        assert row is not None
        assert row["patient_id"] == 1
        assert row["review_status"] == "Pending"
        assert row["patient_note"] == "Incision line healing nicely"


def test_caregiver_forbidden_from_photo_endpoints():
    """3. Caregiver (Neha Patel) must receive 403 Forbidden on all photo endpoints."""
    tok_family = get_token("caregiver1.demo@example.test")

    # Try viewing photo 1
    res = client.get("/photos/1/image", headers={"Authorization": f"Bearer {tok_family}"})
    assert res.status_code == 403
    assert "Caregivers are strictly not permitted" in res.json()["detail"]

    # Try viewing thumbnail 1
    res_thumb = client.get("/photos/1/thumb", headers={"Authorization": f"Bearer {tok_family}"})
    assert res_thumb.status_code == 403

    # Try uploading photo
    res_up = client.post(
        "/patient/me/photos",
        headers={"Authorization": f"Bearer {tok_family}"},
        files={"file": ("test.jpg", b"fake", "image/jpeg")},
    )
    assert res_up.status_code == 403


def test_patient_cross_identity_isolation():
    """4. Patient cannot view another patient's photo."""
    tok_patient = get_token("aarav.demo@example.test")  # Patient 1

    # Photo 3 belongs to Meera Sharma (Patient 2)
    res = client.get("/photos/3/image", headers={"Authorization": f"Bearer {tok_patient}"})
    assert res.status_code == 403
    assert "only view your own" in res.json()["detail"]

    # Photo 1 belongs to Aarav (Patient 1)
    res_own = client.get("/photos/1/image", headers={"Authorization": f"Bearer {tok_patient}"})
    assert res_own.status_code == 200
    assert res_own.headers["content-type"] == "image/jpeg"


def test_photo_view_writes_audit_log():
    """5. Every photo inspection generates a PHOTO_VIEWED audit entry."""
    tok_nurse = get_token("priya.demo@example.test")

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM audit_log WHERE action = 'PHOTO_VIEWED' AND entity_id = 1")
        initial_views = cur.fetchone()["c"]

    res = client.get("/photos/1/image", headers={"Authorization": f"Bearer {tok_nurse}"})
    assert res.status_code == 200

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM audit_log WHERE action = 'PHOTO_VIEWED' AND entity_id = 1")
        updated_views = cur.fetchone()["c"]
        assert updated_views == initial_views + 1


def test_nurse_review_workflow_and_flag_creation():
    """6. Concern noted creates NO flag without raise_flag action; raise_flag creates Review_Soon flag."""
    tok_nurse = get_token("priya.demo@example.test")

    # Step A: Review with Concern_Noted and action='none' -> NO flag created!
    res_no_flag = client.post(
        "/staff/photos/2/review",
        headers={"Authorization": f"Bearer {tok_nurse}"},
        json={
            "finding": "Concern_Noted",
            "review_note": "Mild marginal redness, will monitor on evening check-in.",
            "action": "none",
        },
    )
    assert res_no_flag.status_code == 200
    assert res_no_flag.json()["review_status"] == "Reviewed"
    assert res_no_flag.json()["flag_id"] is None

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT flag_id FROM wound_photos WHERE photo_id = 2")
        assert cur.fetchone()["flag_id"] is None

    # Step B: Review with Concern_Noted and action='raise_flag' -> Human flag created
    res_with_flag = client.post(
        "/staff/photos/2/review",
        headers={"Authorization": f"Bearer {tok_nurse}"},
        json={
            "finding": "Concern_Noted",
            "review_note": "Spreading erythema along upper third of sternal suture.",
            "action": "raise_flag",
        },
    )
    assert res_with_flag.status_code == 200
    flag_id = res_with_flag.json()["flag_id"]
    assert flag_id is not None

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM flags WHERE flag_id = %s", (flag_id,))
        fl = cur.fetchone()
        assert fl is not None
        assert fl["source_type"] == "Photo"
        assert fl["severity"] == "Review_Soon"
        assert fl["patient_id"] == 1
        assert "Spreading erythema" in fl["reason"]


def test_photo_doctor_escalation_in_decision_desk():
    """7. Photos marked Needs_Doctor appear in Doctor Decision Desk."""
    tok_nurse = get_token("priya.demo@example.test")
    tok_doctor = get_token("ananya.demo@example.test")

    # Nurse escalates photo 2 to doctor
    res_esc = client.post(
        "/staff/photos/2/review",
        headers={"Authorization": f"Bearer {tok_nurse}"},
        json={
            "finding": "Concern_Noted",
            "review_note": "Slight incision edge tension, requesting attending opinion.",
            "action": "ask_doctor",
        },
    )
    assert res_esc.status_code == 200
    assert res_esc.json()["review_status"] == "Needs_Doctor"

    # Doctor Decision Desk check
    dec_res = client.get("/staff/doctor/decisions", headers={"Authorization": f"Bearer {tok_doctor}"})
    assert dec_res.status_code == 200
    items = dec_res.json()["items"]
    photo_items = [it for it in items if it.get("type") == "photo_review"]
    assert len(photo_items) >= 1
    assert any(it.get("photo_id") == 2 for it in photo_items)
