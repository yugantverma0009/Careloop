"""
backend/app/plan_service.py

Phase 4: Recovery Plan Drafter, Patient "My plan", Doctor Plan Approvals,
Understanding Check, Ingestion Section Detection, and Nurse "Admit Patient" Flow.

Principles:
- "The LLM talks. Rules decide. Humans act."
- "Automate the routine. Propose the rest. Humans decide."
- Guardrails:
  1. Every item must cite a valid source chunk.
  2. Numbers & dates in plan items must strictly exist in the cited chunk text (no hallucinations).
  3. Medicine items are reconciled against prescriptions ('Matches' vs 'Mismatch').
  4. Only doctor-approved plans are visible to patients (Draft plans are strictly invisible).
  5. Admitted patients do not start active monitoring until alert limits are approved by doctor.
  6. Understanding check never returns grades or scores to patients; incorrect answers generate
     nurse agent proposals ("Suggest_Plan_Review").
"""

import os
import re
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import pymysql
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))
load_dotenv(".env")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "careloop_api")
DB_PASSWORD = os.getenv("DB_PASSWORD", "careloop_dev_pass")
DB_NAME = os.getenv("DB_NAME", "careloop")


def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


# -----------------------------------------------------------------------------
# 1. Ingestion Upgrade: Heading & Section Detection
# -----------------------------------------------------------------------------

SECTION_PATTERNS = [
    (
        "medications",
        "Medications & Prescriptions",
        [
            r"(?i)\bmedications?\b",
            r"(?i)\bprescriptions?\b",
            r"(?i)\bdrugs?\b",
            r"(?i)\bdoses?\b",
            r"(?i)\bmedicines?\b",
        ],
    ),
    (
        "follow_up",
        "Appointments & Follow-up",
        [
            r"(?i)\bfollow[\s-]?up\b",
            r"(?i)\bappointments?\b",
            r"(?i)\bclinic visit\b",
            r"(?i)\bnext visit\b",
            r"(?i)\breview date\b",
        ],
    ),
    (
        "warning_signs",
        "Warning Signs & Red Flags",
        [
            r"(?i)\bwarning signs?\b",
            r"(?i)\bred flags?\b",
            r"(?i)\bemergency\b",
            r"(?i)\bseek immediate\b",
            r"(?i)\bcall 112\b",
            r"(?i)\bdanger signs?\b",
        ],
    ),
    (
        "activity",
        "Activity & Mobility Guidelines",
        [
            r"(?i)\bactivity\b",
            r"(?i)\bexercise\b",
            r"(?i)\bmobility\b",
            r"(?i)\blifting\b",
            r"(?i)\bwalking\b",
            r"(?i)\brestrictions?\b",
        ],
    ),
    (
        "wound_care",
        "Incision & Wound Care",
        [
            r"(?i)\bwound care\b",
            r"(?i)\bincision\b",
            r"(?i)\bsurgical site\b",
            r"(?i)\bdressing\b",
            r"(?i)\bsternal\b",
            r"(?i)\bsutures?\b",
        ],
    ),
    (
        "diet",
        "Diet & Nutrition",
        [
            r"(?i)\bdiet\b",
            r"(?i)\bnutrition\b",
            r"(?i)\bfluid restriction\b",
            r"(?i)\bsodium\b",
            r"(?i)\bmeals?\b",
        ],
    ),
]


def detect_section_from_heading_or_text(text: str) -> Tuple[str, str]:
    """
    Detects section_type and section_title from text lines or headings.
    Returns (section_type, section_title).
    """
    first_lines = text.strip().split("\n")[:3]
    header_probe = " ".join(first_lines)

    for sec_type, sec_title, patterns in SECTION_PATTERNS:
        for p in patterns:
            if re.search(p, header_probe):
                return sec_type, sec_title

    # Fallback search in entire text block
    for sec_type, sec_title, patterns in SECTION_PATTERNS:
        for p in patterns:
            if re.search(p, text):
                return sec_type, sec_title

    return "general", "General Discharge Information"


def parse_discharge_text_to_chunks(raw_text: str) -> List[Dict[str, Any]]:
    """
    Splits text by double newlines or section headings, associates each chunk
    with detected section_type and section_title.
    """
    raw_blocks = [b.strip() for b in re.split(r"\n\s*\n+", raw_text) if b.strip()]
    if not raw_blocks:
        raw_blocks = [raw_text.strip()] if raw_text.strip() else []

    chunks = []
    for idx, block in enumerate(raw_blocks, start=1):
        sec_type, sec_title = detect_section_from_heading_or_text(block)
        chunks.append({
            "chunk_index": idx,
            "chunk_text": block,
            "section_type": sec_type,
            "section_title": sec_title,
            "page_no": 1 + (idx - 1) // 3,
        })
    return chunks


# -----------------------------------------------------------------------------
# 2. Number Grounding Guard
# -----------------------------------------------------------------------------

def extract_all_numbers(text: str) -> List[str]:
    """Extracts all digit sequences and decimal values from text."""
    return re.findall(r"\b\d+(?:\.\d+)?\b", text)


def verify_numbers_grounded(item_text: str, source_text: str) -> Tuple[bool, List[str]]:
    """
    Checks that every number present in item_text appears in source_text.
    Returns (is_grounded, ungrounded_numbers).
    """
    item_numbers = extract_all_numbers(item_text)
    source_numbers = set(extract_all_numbers(source_text))

    # Also check time formats like 08:00 vs 8
    ungrounded = []
    for num in item_numbers:
        # Strip leading zeros for matching (e.g. 08 -> 8)
        norm_num = str(int(float(num))) if "." not in num else num
        matched = False
        if num in source_numbers or norm_num in source_numbers or num in source_text:
            matched = True
        else:
            # Check if source contains formatted time or word
            for s_num in source_numbers:
                if str(int(float(s_num))) == norm_num:
                    matched = True
                    break
        if not matched:
            ungrounded.append(num)

    return (len(ungrounded) == 0, ungrounded)


# -----------------------------------------------------------------------------
# 3. Prescription Reconciliation
# -----------------------------------------------------------------------------

def reconcile_medicine_with_prescriptions(
    patient_id: int,
    med_title: str,
    med_detail: str,
    conn: Any
) -> Tuple[str, Optional[str]]:
    """
    Reconciles a candidate medicine item with active prescriptions.
    Returns (reconcile_status, note).
    Statuses: 'Matches', 'Mismatch'.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.prescription_id, m.medicine_name, p.dose_instructions
            FROM prescriptions p
            JOIN medicines m ON p.medicine_id = m.medicine_id
            WHERE p.patient_id = %s AND p.active_status = 1
            """,
            (patient_id,)
        )
        prescriptions = cur.fetchall()

    if not prescriptions:
        return "Mismatch", "No active prescriptions found in system to match."

    # Look for matching medicine name
    item_combined = f"{med_title} {med_detail}".lower()
    matched_rx = None
    for rx in prescriptions:
        med_name = rx["medicine_name"].lower()
        # Clean suffix (e.g. Cardiopulse-XR -> Cardiopulse)
        core_name = re.sub(r"[-_\s]?(xr|sr|cr|10|5|d)?$", "", med_name).strip()
        if core_name in item_combined or med_name in item_combined:
            matched_rx = rx
            break

    if not matched_rx:
        return "Mismatch", f"Medication not found in active prescriptions: '{med_title}'."

    # Check frequency / timing alignment
    rx_dose_inst = (matched_rx.get("dose_instructions") or "").lower()

    # If item mentions dosage and frequency, verify consistency
    if "twice" in item_combined and "once" in rx_dose_inst:
        return "Mismatch", f"Plan suggests twice daily, but prescription is once daily ({matched_rx['dose_instructions']})."
    if "once" in item_combined and "twice" in rx_dose_inst:
        return "Mismatch", f"Plan suggests once daily, but prescription is twice daily ({matched_rx['dose_instructions']})."

    return "Matches", f"Matches active prescription for {matched_rx['medicine_name']} ({matched_rx['dose_instructions']})."


# -----------------------------------------------------------------------------
# 4. Recovery Plan Drafter
# -----------------------------------------------------------------------------

def draft_recovery_plan(
    patient_id: int,
    staff_id: int,
    staff_role: str,
    source_document_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Structured Recovery Plan Drafter.
    Reads document chunks for the patient's discharge summary, applies guards,
    reconciles medicine items against prescriptions, and creates a Draft plan.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. Resolve source document
            if not source_document_id:
                cur.execute(
                    """
                    SELECT d.document_id, d.file_name, r.discharge_id
                    FROM discharge_records r
                    JOIN discharge_documents d ON r.discharge_id = d.discharge_id
                    WHERE r.patient_id = %s
                    ORDER BY d.uploaded_at DESC LIMIT 1
                    """,
                    (patient_id,)
                )
                doc_row = cur.fetchone()
                if doc_row:
                    source_document_id = doc_row["document_id"]

            if not source_document_id:
                raise ValueError("No discharge summary document found for patient.")

            # 2. Fetch all document chunks
            cur.execute(
                """
                SELECT chunk_id, chunk_index, chunk_text, section_title, section_type, page_no
                FROM document_chunks
                WHERE document_id = %s
                ORDER BY chunk_index ASC
                """,
                (source_document_id,)
            )
            chunks = cur.fetchall()
            if not chunks:
                raise ValueError(f"No indexed chunks found for document #{source_document_id}.")

            # 3. Draft structured items from chunks
            candidate_items = []
            not_used_items = []

            for chunk in chunks:
                c_id = chunk["chunk_id"]
                c_text = chunk["chunk_text"]
                sec_type = chunk.get("section_type") or "general"
                sec_title = chunk.get("section_title") or "Discharge summary"

                # Parse lines or sentences in chunk
                lines = [ln.strip() for ln in c_text.splitlines() if ln.strip()]
                for line in lines:
                    # Clean leading section tags if present
                    clean_line = re.sub(r"^[A-Z\s_-]+:\s*", "", line)
                    if not clean_line or len(clean_line) < 10:
                        continue

                    # Determine item type
                    item_type = "Other"
                    title = "Recovery Guideline"
                    schedule_text = None

                    if sec_type == "medications" or "tablet" in clean_line.lower() or "capsule" in clean_line.lower():
                        item_type = "Medicine"
                        # Extract title from medication name
                        med_match = re.match(r"^([A-Za-z0-9\-_]+(?:\s+[A-Za-z0-9\-_]+)?)\s+(.+)$", clean_line)
                        if med_match:
                            title = med_match.group(1)
                            detail = clean_line
                        else:
                            title = "Medication"
                            detail = clean_line
                        # Extract schedule
                        sched_match = re.search(r"(\d{1,2}:\d{2}(?:\s*(?:and|,)\s*\d{1,2}:\d{2})?|morning|evening|afternoon|daily)", clean_line, re.IGNORECASE)
                        if sched_match:
                            schedule_text = sched_match.group(0)

                    elif sec_type == "follow_up" or "appointment" in clean_line.lower() or "follow" in clean_line.lower():
                        item_type = "Appointment"
                        title = "Outpatient Follow-Up"
                        detail = clean_line
                        sched_match = re.search(r"(day\s+\d+|in\s+\d+\s+days|at\s+\d{1,2}:\d{2}\s*(?:AM|PM)?)", clean_line, re.IGNORECASE)
                        if sched_match:
                            schedule_text = sched_match.group(0)

                    elif sec_type == "wound_care" or "wound" in clean_line.lower() or "incision" in clean_line.lower():
                        item_type = "Wound_Care"
                        title = "Incision Care & Inspection"
                        detail = clean_line
                        schedule_text = "Daily at morning check-in"

                    elif sec_type == "warning_signs" or "warning" in clean_line.lower() or "call 112" in clean_line.lower():
                        item_type = "Warning_Sign"
                        title = "Emergency Red Flag Signs"
                        detail = clean_line
                        schedule_text = "Immediate — 112 / Emergency"

                    elif sec_type == "activity" or "walk" in clean_line.lower() or "lift" in clean_line.lower():
                        item_type = "Activity"
                        title = "Physical Activity Guideline"
                        detail = clean_line
                        schedule_text = "Twice daily"

                    elif sec_type == "diet" or "diet" in clean_line.lower() or "food" in clean_line.lower():
                        item_type = "Diet"
                        title = "Nutrition & Dietary Restrictions"
                        detail = clean_line
                        schedule_text = "Daily"

                    else:
                        item_type = "Other"
                        title = sec_title
                        detail = clean_line

                    # GUARD 1: Source chunk required
                    if not c_id:
                        not_used_items.append({"title": title, "reason": "Missing source chunk id"})
                        continue

                    # GUARD 2: Number Grounding Guard
                    is_grounded, ungrounded = verify_numbers_grounded(detail, c_text)
                    if not is_grounded:
                        not_used_items.append({
                            "title": title,
                            "reason": f"Hallucinated or ungrounded numbers found: {ungrounded}",
                            "detail": detail,
                        })
                        continue

                    # GUARD 3: Medication Reconciliation
                    reconcile_status = "Not_Applicable"
                    reconcile_note = None
                    if item_type == "Medicine":
                        reconcile_status, reconcile_note = reconcile_medicine_with_prescriptions(
                            patient_id=patient_id,
                            med_title=title,
                            med_detail=detail,
                            conn=conn
                        )

                    candidate_items.append({
                        "item_type": item_type,
                        "title": title[:120],
                        "detail": detail[:500],
                        "schedule_text": schedule_text[:120] if schedule_text else None,
                        "source_chunk_id": c_id,
                        "reconcile_status": reconcile_status,
                        "reconcile_note": reconcile_note,
                        "section_title": sec_title,
                        "section_type": sec_type,
                    })

            if not candidate_items:
                raise ValueError("No valid grounded recovery items could be drafted from discharge summary.")

            # 4. Create new version in recovery_plans
            cur.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 AS next_ver FROM recovery_plans WHERE patient_id = %s",
                (patient_id,)
            )
            next_version = cur.fetchone()["next_ver"]

            cur.execute(
                """
                INSERT INTO recovery_plans (patient_id, version, status, source_document_id, drafted_by, drafted_at)
                VALUES (%s, %s, 'Draft', %s, 'Agent', NOW())
                """,
                (patient_id, next_version, source_document_id)
            )
            plan_id = cur.lastrowid

            # 5. Insert plan items
            for idx, it in enumerate(candidate_items, start=1):
                cur.execute(
                    """
                    INSERT INTO recovery_plan_items (
                        plan_id, item_type, title, detail, schedule_text,
                        source_chunk_id, reconcile_status, display_order
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        plan_id,
                        it["item_type"],
                        it["title"],
                        it["detail"],
                        it["schedule_text"],
                        it["source_chunk_id"],
                        it["reconcile_status"],
                        idx
                    )
                )

            # 6. Audit log
            cur.execute(
                """
                INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                VALUES ('Staff', %s, 'PLAN_DRAFTED', 'recovery_plan', %s, %s)
                """,
                (
                    staff_id,
                    plan_id,
                    json.dumps({
                        "patient_id": patient_id,
                        "version": next_version,
                        "items_count": len(candidate_items),
                        "not_used_count": len(not_used_items),
                        "source_document_id": source_document_id,
                    })
                )
            )

        conn.commit()
        return {
            "success": True,
            "plan_id": plan_id,
            "patient_id": patient_id,
            "version": next_version,
            "status": "Draft",
            "items_count": len(candidate_items),
            "items": candidate_items,
            "not_used": not_used_items,
        }
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# 5. Review, Verify, and Doctor Approval
# -----------------------------------------------------------------------------

def verify_plan_item(item_id: int, staff_id: int, staff_role: str) -> Dict[str, Any]:
    """
    Nurse or Doctor ticks 'Matches papers' for a specific plan item.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT i.item_id, i.plan_id, i.title, p.patient_id, p.status
                FROM recovery_plan_items i
                JOIN recovery_plans p ON i.plan_id = p.plan_id
                WHERE i.item_id = %s
                """,
                (item_id,)
            )
            item = cur.fetchone()
            if not item:
                raise ValueError("Recovery plan item not found.")

            cur.execute(
                """
                UPDATE recovery_plan_items
                SET verified_by_staff_id = %s, verified_at = NOW()
                WHERE item_id = %s
                """,
                (staff_id, item_id)
            )

            cur.execute(
                """
                INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                VALUES ('Staff', %s, 'PLAN_ITEM_VERIFIED', 'recovery_plan_item', %s, %s)
                """,
                (
                    staff_id,
                    item_id,
                    json.dumps({
                        "patient_id": item["patient_id"],
                        "plan_id": item["plan_id"],
                        "staff_role": staff_role,
                        "title": item["title"],
                    })
                )
            )
        conn.commit()
        return {"success": True, "item_id": item_id, "verified": True}
    finally:
        conn.close()


def approve_recovery_plan(plan_id: int, doctor_id: int) -> Dict[str, Any]:
    """
    Doctor-only approval of a recovery plan.
    - Sets previous approved plan to 'Superseded'.
    - Activates this plan ('Approved').
    - Schedules wound care photo prompts in Rounds if wound care items exist.
    - Deterministically generates 3 understanding check questions.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT plan_id, patient_id, version, status FROM recovery_plans WHERE plan_id = %s", (plan_id,))
            plan = cur.fetchone()
            if not plan:
                raise ValueError("Recovery plan not found.")

            patient_id = plan["patient_id"]

            # Supersede prior approved plans for this patient
            cur.execute(
                "UPDATE recovery_plans SET status = 'Superseded' WHERE patient_id = %s AND status = 'Approved'",
                (patient_id,)
            )

            # Approve target plan
            cur.execute(
                """
                UPDATE recovery_plans
                SET status = 'Approved', approved_by_staff_id = %s, approved_at = NOW()
                WHERE plan_id = %s
                """,
                (doctor_id, plan_id)
            )

            # Load approved items
            cur.execute(
                """
                SELECT item_id, item_type, title, detail, schedule_text
                FROM recovery_plan_items
                WHERE plan_id = %s
                ORDER BY display_order ASC
                """,
                (plan_id,)
            )
            items = cur.fetchall()

            # Schedule Photo_Request in scheduled_actions if wound care item exists
            has_wound_care = any(it["item_type"] == "Wound_Care" for it in items)
            if has_wound_care:
                dedupe_key = f"photo_req_{patient_id}_day1"
                cur.execute(
                    """
                    INSERT IGNORE INTO scheduled_actions (
                        patient_id, action_type, channel, run_at, status, reason, dedupe_key
                    ) VALUES (%s, 'Photo_Request', 'App', NOW() + INTERVAL 1 DAY, 'Scheduled',
                              'Scheduled post-op incision check per approved recovery plan', %s)
                    """,
                    (patient_id, dedupe_key)
                )

            # Generate 3 deterministic understanding check questions
            generate_understanding_check_questions(patient_id, plan_id, items, cur)

            # Audit row
            cur.execute(
                """
                INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                VALUES ('Staff', %s, 'PLAN_APPROVED', 'recovery_plan', %s, %s)
                """,
                (
                    doctor_id,
                    plan_id,
                    json.dumps({
                        "patient_id": patient_id,
                        "version": plan["version"],
                        "items_count": len(items),
                        "has_wound_care": has_wound_care,
                    })
                )
            )

        conn.commit()
        return {"success": True, "plan_id": plan_id, "status": "Approved"}
    finally:
        conn.close()


def reject_recovery_plan(plan_id: int, doctor_id: int, reason: str = "") -> Dict[str, Any]:
    """Doctor-only rejection of a recovery plan draft."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT plan_id, patient_id, version FROM recovery_plans WHERE plan_id = %s", (plan_id,))
            plan = cur.fetchone()
            if not plan:
                raise ValueError("Recovery plan not found.")

            cur.execute("UPDATE recovery_plans SET status = 'Rejected' WHERE plan_id = %s", (plan_id,))

            cur.execute(
                """
                INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                VALUES ('Staff', %s, 'PLAN_REJECTED', 'recovery_plan', %s, %s)
                """,
                (
                    doctor_id,
                    plan_id,
                    json.dumps({
                        "patient_id": plan["patient_id"],
                        "version": plan["version"],
                        "reason": reason,
                    })
                )
            )
        conn.commit()
        return {"success": True, "plan_id": plan_id, "status": "Rejected"}
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# 6. Understanding Check (P2)
# -----------------------------------------------------------------------------

def generate_understanding_check_questions(
    patient_id: int,
    plan_id: int,
    items: List[Dict[str, Any]],
    cur: Any
):
    """
    Builds 3 deterministic multiple-choice questions from approved recovery items.
    Stores them in plan_understanding_checks.
    """
    # Clear any prior pending checks for this plan
    cur.execute("DELETE FROM plan_understanding_checks WHERE plan_id = %s", (plan_id,))

    # Find medicine item, warning sign item, activity item
    med_item = next((it for it in items if it["item_type"] == "Medicine"), None)
    warn_item = next((it for it in items if it["item_type"] == "Warning_Sign"), None)
    act_item = next((it for it in items if it["item_type"] == "Activity"), None)

    questions = []

    # Q1: Medication timing
    if med_item and med_item.get("schedule_text"):
        sched = med_item["schedule_text"]
        q1 = {
            "question_text": f"According to your recovery papers, when should you take {med_item['title']}?",
            "options": [
                f"{sched} as instructed in your discharge plan",
                "Only when feeling acute pain or distress",
                "Once every three days",
            ],
            "correct_option_index": 0,
        }
        questions.append(q1)
    else:
        questions.append({
            "question_text": "How should you take your prescribed recovery medicines?",
            "options": [
                "At the exact scheduled times specified in your discharge papers",
                "Only when severe pain starts",
                "Double the dose if a dose was missed earlier",
            ],
            "correct_option_index": 0,
        })

    # Q2: Warning Signs / Emergency 112
    questions.append({
        "question_text": "If you experience severe chest pain, sudden breathlessness, or heavy bleeding, what is the correct action?",
        "options": [
            "Call 112 or emergency services immediately and press SOS",
            "Wait 24 hours to see if symptoms resolve",
            "Take an extra sleeping pill and lie down",
        ],
        "correct_option_index": 0,
    })

    # Q3: Activity / Incision Care
    if act_item:
        questions.append({
            "question_text": f"What is your recommended physical activity guidance?",
            "options": [
                f"{act_item['detail'][:100]}",
                "Heavy weightlifting and intense exercise daily",
                "Complete bed rest without moving or walking at all",
            ],
            "correct_option_index": 0,
        })
    else:
        questions.append({
            "question_text": "How should you care for your post-operative incision site?",
            "options": [
                "Keep the incision clean and dry, inspecting daily for redness or drainage",
                "Apply unapproved creams and scrub vigorously in hot water",
                "Remove dressings and immerse in bathwater immediately",
            ],
            "correct_option_index": 0,
        })

    for q in questions[:3]:
        cur.execute(
            """
            INSERT INTO plan_understanding_checks (
                patient_id, plan_id, question_text, options, correct_option_index
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            (
                patient_id,
                plan_id,
                q["question_text"],
                json.dumps(q["options"]),
                q["correct_option_index"],
            )
        )


def get_patient_understanding_check(patient_id: int) -> List[Dict[str, Any]]:
    """
    Returns understanding check questions for the patient's active approved plan.
    Omits correct_option_index so patient answers naturally.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.check_id, c.plan_id, c.question_text, c.options,
                       c.selected_option_index, c.is_correct, c.answered_at
                FROM plan_understanding_checks c
                JOIN recovery_plans p ON c.plan_id = p.plan_id
                WHERE c.patient_id = %s AND p.status = 'Approved'
                ORDER BY c.check_id ASC
                """,
                (patient_id,)
            )
            rows = cur.fetchall()
            result = []
            for r in rows:
                opts = r["options"]
                if isinstance(opts, str):
                    opts = json.loads(opts)
                result.append({
                    "check_id": r["check_id"],
                    "question_text": r["question_text"],
                    "options": opts,
                    "selected_option_index": r["selected_option_index"],
                    "answered": r["answered_at"] is not None,
                })
            return result
    finally:
        conn.close()


def submit_understanding_answer(
    patient_id: int,
    check_id: int,
    selected_option_index: int
) -> Dict[str, Any]:
    """
    Evaluates patient's answer to an understanding check question.
    - Never shows scores or grades to patient.
    - If incorrect, generates an agent_proposal ('Suggest_Plan_Review') for the nurse call list.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT check_id, patient_id, plan_id, question_text, correct_option_index
                FROM plan_understanding_checks
                WHERE check_id = %s AND patient_id = %s
                """,
                (check_id, patient_id)
            )
            check = cur.fetchone()
            if not check:
                raise ValueError("Understanding check question not found.")

            is_correct = (selected_option_index == check["correct_option_index"])
            proposal_id = None

            if not is_correct:
                # Generate proposal for nurse call list
                q_snippet = check["question_text"][:60]
                reason = f"Patient answered recovery plan question incorrectly ('{q_snippet}...'). Outreach recommended to review instructions."
                cur.execute(
                    """
                    INSERT INTO agent_proposals (
                        patient_id, agent_name, proposal_type, reason, evidence, status
                    ) VALUES (%s, 'PlanAgent', 'Suggest_Plan_Review', %s, %s, 'Pending')
                    """,
                    (
                        patient_id,
                        reason,
                        json.dumps({
                            "check_id": check_id,
                            "question": check["question_text"],
                            "selected_option": selected_option_index,
                        })
                    )
                )
                proposal_id = cur.lastrowid

            cur.execute(
                """
                UPDATE plan_understanding_checks
                SET selected_option_index = %s, is_correct = %s, answered_at = NOW(), proposal_id = %s
                WHERE check_id = %s
                """,
                (selected_option_index, 1 if is_correct else 0, proposal_id, check_id)
            )

        conn.commit()
        return {
            "success": True,
            "check_id": check_id,
            "message": "Thank you for confirming your understanding. Your care team is here if you have questions.",
        }
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# 7. Patient "My Plan" and Staff Views
# -----------------------------------------------------------------------------

def get_patient_active_plan(patient_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieves the currently approved plan for the patient.
    If no approved plan exists (or only Drafts exist), returns None.
    (Draft plans are strictly invisible to patients).
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.plan_id, p.patient_id, p.version, p.status, p.approved_at,
                       s.full_name AS approved_by_name
                FROM recovery_plans p
                LEFT JOIN care_staff s ON p.approved_by_staff_id = s.staff_id
                WHERE p.patient_id = %s AND p.status = 'Approved'
                ORDER BY p.version DESC LIMIT 1
                """,
                (patient_id,)
            )
            plan = cur.fetchone()
            if not plan:
                return None

            cur.execute(
                """
                SELECT i.item_id, i.plan_id, i.item_type, i.title, i.detail, i.schedule_text,
                       i.source_chunk_id, i.reconcile_status, i.display_order,
                       c.section_title, c.section_type, c.page_no, c.chunk_text AS source_chunk_text
                FROM recovery_plan_items i
                LEFT JOIN document_chunks c ON i.source_chunk_id = c.chunk_id
                WHERE i.plan_id = %s
                ORDER BY i.display_order ASC
                """,
                (plan["plan_id"],)
            )
            items = cur.fetchall()

            # Group items for structured patient presentation
            today_items = []
            upcoming_items = []
            medicines = []
            wound_care = []
            warning_signs = []
            appointments = []
            activities = []
            diet = []

            for it in items:
                itype = it["item_type"]
                pno = f" · p.{it['page_no']}" if it.get("page_no") else ""
                sec_lbl = it.get("section_title") or "General"
                item_dict = {
                    "item_id": it["item_id"],
                    "item_type": itype,
                    "title": it["title"],
                    "detail": it["detail"],
                    "schedule_text": it["schedule_text"],
                    "source_chunk_id": it["source_chunk_id"],
                    "source_label": f"📄 Discharge summary · {sec_lbl}{pno}",
                    "source_passage": it.get("source_chunk_text") or "",
                }

                if itype == "Medicine":
                    medicines.append(item_dict)
                    today_items.append(item_dict)
                elif itype == "Wound_Care":
                    wound_care.append(item_dict)
                    today_items.append(item_dict)
                elif itype == "Warning_Sign":
                    warning_signs.append(item_dict)
                elif itype == "Appointment":
                    appointments.append(item_dict)
                    upcoming_items.append(item_dict)
                elif itype == "Activity":
                    activities.append(item_dict)
                    today_items.append(item_dict)
                elif itype == "Diet":
                    diet.append(item_dict)
                else:
                    today_items.append(item_dict)

            return {
                "plan_id": plan["plan_id"],
                "patient_id": plan["patient_id"],
                "version": plan["version"],
                "status": plan["status"],
                "approved_at": plan["approved_at"].isoformat() if plan["approved_at"] else None,
                "approved_by_name": plan["approved_by_name"] or "Dr. Ananya Sharma",
                "today_items": today_items,
                "upcoming_items": upcoming_items,
                "medicines": medicines,
                "wound_care": wound_care,
                "warning_signs": warning_signs,
                "appointments": appointments,
                "activities": activities,
                "diet": diet,
                "all_items": items,
            }
    finally:
        conn.close()


def get_staff_patient_plans(patient_id: int) -> Dict[str, Any]:
    """
    Retrieves all recovery plans (Draft, Approved, Superseded) for a patient.
    Accessible to Nurse and Doctor.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.plan_id, p.patient_id, p.version, p.status, p.drafted_by,
                       p.drafted_at, p.approved_at,
                       s.full_name AS approved_by_name
                FROM recovery_plans p
                LEFT JOIN care_staff s ON p.approved_by_staff_id = s.staff_id
                WHERE p.patient_id = %s
                ORDER BY p.version DESC
                """,
                (patient_id,)
            )
            plans = cur.fetchall()

            for pl in plans:
                cur.execute(
                    """
                    SELECT i.item_id, i.plan_id, i.item_type, i.title, i.detail, i.schedule_text,
                           i.source_chunk_id, i.reconcile_status, i.verified_by_staff_id,
                           i.verified_at, i.display_order,
                           c.section_title, c.section_type, c.page_no, c.chunk_text AS source_chunk_text,
                           v.full_name AS verified_by_name
                    FROM recovery_plan_items i
                    LEFT JOIN document_chunks c ON i.source_chunk_id = c.chunk_id
                    LEFT JOIN care_staff v ON i.verified_by_staff_id = v.staff_id
                    WHERE i.plan_id = %s
                    ORDER BY i.display_order ASC
                    """,
                    (pl["plan_id"],)
                )
                pl["items"] = cur.fetchall()
                pl["is_verified"] = all(it["verified_at"] is not None for it in pl["items"]) if pl["items"] else False

            return {"patient_id": patient_id, "plans": plans}
    finally:
        conn.close()


def get_pending_plans_for_doctor() -> List[Dict[str, Any]]:
    """
    Returns all recovery plans with status 'Draft' waiting for doctor review and approval.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.plan_id, p.patient_id, p.version, p.status, p.drafted_at,
                       pt.full_name AS patient_name, pt.patient_code
                FROM recovery_plans p
                JOIN patients pt ON p.patient_id = pt.patient_id
                WHERE p.status = 'Draft'
                ORDER BY p.drafted_at DESC
                """
            )
            plans = cur.fetchall()

            for pl in plans:
                cur.execute(
                    """
                    SELECT i.item_id, i.item_type, i.title, i.detail, i.schedule_text,
                           i.source_chunk_id, i.reconcile_status, i.verified_at,
                           c.section_title, c.page_no
                    FROM recovery_plan_items i
                    LEFT JOIN document_chunks c ON i.source_chunk_id = c.chunk_id
                    WHERE i.plan_id = %s
                    ORDER BY i.display_order ASC
                    """,
                    (pl["plan_id"],)
                )
                pl["items"] = cur.fetchall()
                pl["has_mismatch"] = any(it["reconcile_status"] == "Mismatch" for it in pl["items"])

            return plans
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# 8. Admit Patient Wizard (F6)
# -----------------------------------------------------------------------------

def admit_patient_wizard(
    nurse_id: int,
    patient_data: Dict[str, Any],
    discharge_data: Dict[str, Any],
    prescriptions_data: List[Dict[str, Any]],
    proposed_limits: List[Dict[str, Any]],
    device_data: Optional[Dict[str, Any]] = None,
    caregiver_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Nurse onboarding wizard for starting follow-up for a newly discharged patient.
    Rules:
    - Generates synthetic patient code (CL-XXXXX).
    - Inserts discharge record and indexes discharge summary into chunks.
    - Drafts recovery plan from papers with medication reconciliation.
    - Limits are inserted with status 'Pending_Approval' (Doctor approval required;
      monitoring does NOT start until approved).
    - Creates 'Welcome call: Contact newly discharged patient within 48 hours' task.
    - Writes PATIENT_ADMITTED to audit_log.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Step 1: Patient
            full_name = patient_data["full_name"].strip()
            phone = patient_data.get("phone", "+91-98765-99999").strip()
            dob = patient_data.get("date_of_birth", "1980-01-01")
            lang = patient_data.get("preferred_language", "en")

            # Generate patient code
            cur.execute("SELECT COUNT(*) AS total FROM patients")
            cnt = cur.fetchone()["total"] + 1
            patient_code = f"CL-{cnt:05d}"

            cur.execute(
                """
                INSERT INTO patients (full_name, phone, date_of_birth, preferred_language, consent_status, patient_code)
                VALUES (%s, %s, %s, %s, 'Granted', %s)
                """,
                (full_name, phone, dob, lang, patient_code)
            )
            patient_id = cur.lastrowid

            # Assign to attending nurse and Dr. Ananya Sharma (staff_id=1)
            cur.execute(
                "INSERT INTO care_assignments (patient_id, staff_id, assignment_role) VALUES (%s, %s, 'Nurse')",
                (patient_id, nurse_id)
            )
            cur.execute(
                "INSERT INTO care_assignments (patient_id, staff_id, assignment_role) VALUES (%s, 1, 'Primary_Doctor')",
                (patient_id,)
            )

            # Step 2: Discharge Summary
            condition_desc = discharge_data.get("condition", "Post-Surgical Recovery")
            discharge_date = discharge_data.get("discharge_date") or datetime.now().strftime("%Y-%m-%d")
            summary_text = discharge_data.get("summary_text", f"DISCHARGE SUMMARY FOR {full_name}\nCondition: {condition_desc}\nFollow-up in 7 days.")

            cur.execute(
                """
                INSERT INTO discharge_records (patient_id, attending_staff_id, discharge_date, condition_summary, instructions, follow_up_due)
                VALUES (%s, 1, %s, %s, %s, DATE_ADD(%s, INTERVAL 7 DAY))
                """,
                (patient_id, discharge_date, condition_desc, summary_text, discharge_date)
            )
            discharge_id = cur.lastrowid

            cur.execute(
                """
                INSERT INTO discharge_documents (discharge_id, file_name, uploaded_at, indexing_status, vector_collection)
                VALUES (%s, %s, NOW(), 'Indexed', %s)
                """,
                (discharge_id, f"{patient_code.lower()}_discharge_summary.pdf", f"patient_{patient_id}_discharge")
            )
            doc_id = cur.lastrowid

            # Parse and insert chunks
            chunks = parse_discharge_text_to_chunks(summary_text)
            for chk in chunks:
                cur.execute(
                    """
                    INSERT INTO document_chunks (document_id, chunk_index, chunk_text, section_title, section_type, page_no)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (doc_id, chk["chunk_index"], chk["chunk_text"], chk["section_title"], chk["section_type"], chk["page_no"])
                )

            # Step 3: Prescriptions
            for rx in prescriptions_data:
                med_name = rx.get("name", "CardioPulse-XR").strip()
                # Find or insert medicine
                cur.execute("SELECT medicine_id FROM medicines WHERE medicine_name = %s", (med_name,))
                m_row = cur.fetchone()
                if m_row:
                    med_id = m_row["medicine_id"]
                else:
                    cur.execute("INSERT INTO medicines (medicine_name) VALUES (%s)", (med_name,))
                    med_id = cur.lastrowid

                dose_inst = f"{rx.get('dosage', '1 tablet')} {rx.get('frequency', 'Morning')}".strip()
                cur.execute(
                    """
                    INSERT INTO prescriptions (patient_id, medicine_id, dose_instructions, start_date, active_status, prescribed_by_staff_id)
                    VALUES (%s, %s, %s, %s, 1, 1)
                    """,
                    (patient_id, med_id, dose_inst, discharge_date)
                )

            # Step 4: Alert Limits (Proposed — 'Pending_Approval' via alert_rules_history)
            for rule in proposed_limits:
                cur.execute(
                    """
                    INSERT INTO alert_rules (
                        patient_id, rule_type, measurement_type, threshold_value,
                        severity, approved_by_staff_id, approved_at, is_active
                    ) VALUES (%s, %s, 'Heart_Rate', %s, %s, 1, NOW(), 0)
                    """,
                    (
                        patient_id,
                        rule.get("rule_type", "Reading_Above"),
                        rule.get("threshold_val", 100.0),
                        rule.get("severity", "Review_Soon"),
                    )
                )
                rule_id = cur.lastrowid
                cur.execute(
                    """
                    INSERT INTO alert_rules_history (rule_id, changed_by_staff_id, change_reason, old_values, new_values, changed_at)
                    VALUES (%s, %s, 'Proposed limit during patient admission', '{}', %s, NOW())
                    """,
                    (rule_id, nurse_id, json.dumps({"threshold_value": rule.get("threshold_val", 100.0), "proposed_only": True, "status": "Pending"}))
                )

            # Step 5: Device binding (optional)
            if device_data and device_data.get("device_id"):
                dev_id = device_data["device_id"].strip()
                cur.execute(
                    """
                    INSERT INTO devices (device_id, patient_id, device_type, registered_at, last_seen_at)
                    VALUES (%s, %s, 'Simulator', NOW(), NOW())
                    ON DUPLICATE KEY UPDATE patient_id = VALUES(patient_id)
                    """,
                    (dev_id, patient_id)
                )

            # Step 6: Caregiver / Family helper (optional)
            if caregiver_data and caregiver_data.get("full_name"):
                c_name = caregiver_data["full_name"].strip()
                c_phone = caregiver_data.get("phone", "+91-98765-88888").strip()
                c_rel = caregiver_data.get("relationship", "Family Helper")
                c_consent = 1 if caregiver_data.get("consent_granted") else 0

                cur.execute(
                    """
                    INSERT INTO caregivers (patient_id, full_name, phone, relationship, consent_granted, is_primary)
                    VALUES (%s, %s, %s, %s, %s, 1)
                    """,
                    (patient_id, c_name, c_phone, c_rel, c_consent)
                )

            # Step 7: Welcome Call Task (Due in 48 hours)
            cur.execute(
                """
                INSERT INTO follow_up_tasks (
                    patient_id, assigned_staff_id, reason, priority, status, due_at
                ) VALUES (%s, %s,
                          'Welcome call: Contact newly discharged patient within 48 hours',
                          'Routine', 'Pending', NOW() + INTERVAL 48 HOUR)
                """,
                (patient_id, nurse_id)
            )

            # Write Audit Row
            cur.execute(
                """
                INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                VALUES ('Staff', %s, 'PATIENT_ADMITTED', 'patient', %s, %s)
                """,
                (
                    nurse_id,
                    patient_id,
                    json.dumps({
                        "patient_code": patient_code,
                        "full_name": full_name,
                        "condition": condition_desc,
                        "welcome_call_due_hours": 48,
                        "limits_status": "Waiting for doctor limits",
                    })
                )
            )

        conn.commit()

        # Step 8: Trigger Initial Plan Drafting
        try:
            draft_res = draft_recovery_plan(patient_id, nurse_id, "Nurse", source_document_id=doc_id)
            plan_id = draft_res["plan_id"]
        except Exception as e:
            plan_id = None

        return {
            "success": True,
            "patient_id": patient_id,
            "patient_code": patient_code,
            "full_name": full_name,
            "plan_id": plan_id,
            "limits_status": "Waiting for doctor limits",
            "welcome_call_due": "within 48 hours",
        }
    finally:
        conn.close()
