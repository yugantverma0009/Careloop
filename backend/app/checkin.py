"""
backend/app/checkin.py — CareLoop Check-in Guide Engine (Feature F2)

Rule: "The LLM talks. Rules decide. Humans act."
- Questions originate strictly from doctor-approved templates (checkin_templates & checkin_questions).
- Guided mode presents one question at a time in English or Hindi.
- Emergency triggers (Question 2: chest pain / severe breathlessness) immediately activate the safety path.
- Completed sessions generate a standard symptom_reports row so existing rules and procedures execute.
- Partial sessions are preserved as 'Abandoned' if not completed.
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import pymysql
from backend.app.db import get_conn
from backend.app.agents.hinglish_normalizer import (
    normalize_pain_answer,
    normalize_yes_no,
    normalize_medication_answer,
    normalize_wound_status,
    extract_barrier_code,
)
from backend.app.agents.phrase_bank_service import PhraseBankService


def get_active_checkin_template() -> Optional[Dict[str, Any]]:
    """Fetch the currently active doctor-approved check-in template with questions."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT template_id, name, version, status, approved_by_staff_id, approved_at, is_active
               FROM checkin_templates
               WHERE status = 'Approved' AND is_active = TRUE
               ORDER BY version DESC LIMIT 1"""
        )
        template = cur.fetchone()
        if not template:
            return None
        template["is_active"] = bool(template["is_active"])

        cur.execute(
            """SELECT question_id, template_id, step_order, question_key, text_en, text_hi,
                      response_type, choices, is_emergency_trigger
               FROM checkin_questions
               WHERE template_id = %s
               ORDER BY step_order ASC""",
            (template["template_id"],)
        )
        questions = cur.fetchall()
        for q in questions:
            q["is_emergency_trigger"] = bool(q.get("is_emergency_trigger"))
            if isinstance(q.get("choices"), str):
                try:
                    q["choices"] = json.loads(q["choices"])
                except Exception:
                    pass
        template["questions"] = questions
        return template


def get_patient_checkin_context(patient_id: int, language: str = "en") -> Dict[str, Any]:
    """
    Day Context Engine (Phase 2 Task 2 & 5.A):
    - Determines if patient has completed today's check-in (prevents duplicate prompts).
    - Retrieves yesterday's check-in facts (e.g., 'Yesterday you reported pain 2').
    - Returns active in-progress session if partially completed.
    - Selects a conversational opening greeting from the doctor-approved phrase bank.
    """
    with get_conn() as conn, conn.cursor() as cur:
        # Check if check-in completed today
        cur.execute(
            """SELECT session_id, completed_at, symptom_report_id
               FROM checkin_sessions
               WHERE patient_id = %s AND status = 'Completed' AND DATE(completed_at) = CURDATE()
               ORDER BY completed_at DESC LIMIT 1""",
            (patient_id,)
        )
        completed_today = cur.fetchone()

        # Check for active in-progress session (started within 2 hours)
        cur.execute(
            """SELECT session_id, template_id, current_step, started_at
               FROM checkin_sessions
               WHERE patient_id = %s AND status = 'In_Progress' AND started_at >= NOW() - INTERVAL 2 HOUR
               ORDER BY started_at DESC LIMIT 1""",
            (patient_id,)
        )
        active_sess = cur.fetchone()

        # Retrieve previous check-in report before today
        cur.execute(
            """SELECT pain_level, DATE(reported_at) as rep_date, symptom_text
               FROM symptom_reports
               WHERE patient_id = %s AND DATE(reported_at) < CURDATE()
               ORDER BY reported_at DESC LIMIT 1""",
            (patient_id,)
        )
        prev_report = cur.fetchone()

    # Yesterday / Previous facts string
    prev_facts = None
    last_pain = None
    if prev_report:
        last_pain = prev_report.get("pain_level")
        p_date = str(prev_report.get("rep_date"))
        if last_pain is not None:
            if language == "hi":
                prev_facts = f"पिछली बार ({p_date}) आपने दर्द स्तर {last_pain}/10 दर्ज किया था।"
            else:
                prev_facts = f"On your previous check-in ({p_date}), you reported pain {last_pain}/10."

    greeting = PhraseBankService.get_rotated_phrase("greeting", language=language, turn_seed=patient_id)

    return {
        "patient_id": patient_id,
        "has_completed_today": bool(completed_today),
        "completed_today": bool(completed_today),
        "completed_at": str(completed_today["completed_at"]) if completed_today else None,
        "active_session": {
            "session_id": active_sess["session_id"],
            "current_step": active_sess["current_step"],
            "template_id": active_sess["template_id"],
        } if active_sess else None,
        "yesterday_facts": prev_facts,
        "yesterday_fact": prev_facts,
        "last_pain": last_pain,
        "greeting_phrase": greeting,
        "greeting": greeting,
    }


def start_checkin_session(patient_id: int, channel: str = "App_Guided") -> Dict[str, Any]:
    """Start a new guided check-in session for a patient using the active approved template."""
    template = get_active_checkin_template()
    if not template:
        raise ValueError("No doctor-approved check-in template is currently active.")

    with get_conn() as conn, conn.cursor() as cur:
        # Check if there is an in-progress session older than 2 hours; mark as Abandoned
        cur.execute(
            """UPDATE checkin_sessions
               SET status = 'Abandoned'
               WHERE patient_id = %s AND status = 'In_Progress' AND started_at < NOW() - INTERVAL 2 HOUR""",
            (patient_id,)
        )

        cur.execute(
            """INSERT INTO checkin_sessions (patient_id, template_id, channel, status, current_step, started_at)
               VALUES (%s, %s, %s, 'In_Progress', 1, NOW())""",
            (patient_id, template["template_id"], channel)
        )
        session_id = cur.lastrowid
        conn.commit()

    return {
        "session_id": session_id,
        "patient_id": patient_id,
        "template_id": template["template_id"],
        "template_name": template["name"],
        "channel": channel,
        "current_step": 1,
        "total_steps": len(template["questions"]),
        "questions": template["questions"],
    }


def record_checkin_answer(
    session_id: int,
    patient_id: Optional[int] = None,
    question_id: int = 1,
    answer_value: Optional[str] = None,
    raw_input: Optional[str] = None,
    language: str = "en",
    raw_answer: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Record an answer for the current question in a session (Phase 2 Task 2 & 5.A).
    - Normalizes Hinglish/Hindi digits and terms.
    - Evaluates branching logic (pain >= 7, some/none meds, wound mild/worried).
    - Emergency trigger immediately creates safety alert and halts routine questions.
    - Attaches conversational phrase bank acknowledgements and factual closing summaries.
    """
    if answer_value is None and raw_answer is not None:
        answer_value = raw_answer
    elif answer_value is None:
        answer_value = ""

    with get_conn() as conn, conn.cursor() as cur:
        if patient_id is not None:
            cur.execute(
                """SELECT session_id, patient_id, template_id, status, current_step
                   FROM checkin_sessions
                   WHERE session_id = %s AND patient_id = %s""",
                (session_id, patient_id)
            )
        else:
            cur.execute(
                """SELECT session_id, patient_id, template_id, status, current_step
                   FROM checkin_sessions
                   WHERE session_id = %s""",
                (session_id,)
            )
        session = cur.fetchone()
        if not session:
            raise ValueError("Check-in session not found.")
        patient_id = session["patient_id"]
        if session["status"] != "In_Progress":
            raise ValueError(f"Session is already {session['status']}.")

        cur.execute(
            """SELECT question_id, template_id, step_order, question_key, text_en, text_hi,
                      response_type, choices, is_emergency_trigger
               FROM checkin_questions
               WHERE question_id = %s AND template_id = %s""",
            (question_id, session["template_id"])
        )
        question = cur.fetchone()
        if not question:
            raise ValueError("Question does not belong to this template.")

        # ── HINGLISH NORMALIZATION ──
        normalized_val = str(answer_value).strip()
        q_key = question["question_key"]
        if "pain" in q_key:
            pn = normalize_pain_answer(normalized_val)
            if pn is not None:
                normalized_val = str(pn)
        elif question["is_emergency_trigger"]:
            yn = normalize_yes_no(normalized_val)
            if yn:
                normalized_val = yn
        elif "medication" in q_key:
            med = normalize_medication_answer(normalized_val)
            if med:
                normalized_val = med
        elif "wound" in q_key:
            wnd = normalize_wound_status(normalized_val)
            if wnd:
                normalized_val = wnd

        # Save or update answer
        cur.execute(
            """INSERT INTO checkin_answers (session_id, question_id, answer_value, raw_input, created_at)
               VALUES (%s, %s, %s, %s, NOW())""",
            (session_id, question_id, normalized_val, raw_input or str(answer_value))
        )

        # ── EMERGENCY TRIGGER CHECK ──────────────────────────────────────────
        is_emergency = False
        val_clean = normalized_val.lower()
        if question["is_emergency_trigger"] and val_clean in ["yes", "haan", "true", "1", "severe"]:
            is_emergency = True

        if is_emergency:
            # 1. Create immediate symptom report with emergency hit
            cur.execute(
                """INSERT INTO symptom_reports
                   (patient_id, symptom_text, pain_level, reported_at, input_method, language, emergency_keyword_hit, review_status)
                   VALUES (%s, %s, %s, NOW(), 'Text', 'en', 1, 'Pending')""",
                (
                    patient_id,
                    f"[Check-in Safety Trigger] Patient answered YES to acute emergency symptoms: {question['text_en']}",
                    0
                )
            )
            report_id = cur.lastrowid

            # 2. Immediately create urgent Emergency flag
            cur.execute(
                """INSERT INTO flags (patient_id, source_type, source_ref_id, reason, severity, status, created_at)
                   VALUES (%s, 'Emergency', %s, %s, 'Urgent_Review', 'Open', NOW())""",
                (
                    patient_id,
                    report_id,
                    f"Immediate emergency safety flag: {question['text_en']} answered YES."
                )
            )
            flag_id = cur.lastrowid

            # 3. Create immediate nurse escalation
            cur.execute(
                """INSERT INTO escalations (flag_id, step_no, step_type, channel, delivery_status, notes, sent_at)
                   VALUES (%s, 1, 'Nurse_Alert', 'Dashboard', 'Sent', 'Check-in Guide detected acute emergency symptom declaration', NOW())""",
                (flag_id,)
            )

            # 4. Mark session completed with report link
            cur.execute(
                """UPDATE checkin_sessions
                   SET status = 'Completed', completed_at = NOW(), symptom_report_id = %s
                   WHERE session_id = %s""",
                (report_id, session_id)
            )

            # Audit log
            cur.execute(
                """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                   VALUES ('Patient', %s, 'EMERGENCY_CHECKIN_TRIGGER', 'flag', %s,
                           JSON_OBJECT('session_id', %s, 'question_id', %s, 'report_id', %s))""",
                (str(patient_id), flag_id, session_id, question_id, report_id)
            )
            conn.commit()

            return {
                "status": "emergency_triggered",
                "emergency": True,
                "halt_flow": True,
                "completed": True,
                "session_id": session_id,
                "report_id": report_id,
                "flag_id": flag_id,
                "guidance": "Immediate Emergency Alert: Call 112 immediately." if language == "en" else "आपातकालीन सुरक्षा सूचना: तुरंत 112 पर कॉल करें।",
                "guidance_en": "Immediate Safety Alert: A triage nurse has been alerted right now. Please sit down, rest, and keep your phone near. If you feel severe chest tightness or difficulty breathing, call 112 immediately.",
                "guidance_hi": "आपातकालीन सुरक्षा सूचना: आपकी देखभाल टीम को तुरंत सूचित कर दिया गया है। कृपया आराम से बैठें। यदि सीने में तेज दबाव या सांस लेने में गंभीर तकलीफ हो, तो तुरंत 112 पर कॉल करें।"
            }

        # ── BRANCHING DETECTION ──
        branch_pain_details = False
        branch_med_barriers = False
        branch_wound_details = False

        if "pain" in q_key:
            try:
                if int(normalized_val) >= 7:
                    branch_pain_details = True
            except (ValueError, TypeError):
                pass
        elif "medication" in q_key and normalized_val in ("some", "none"):
            branch_med_barriers = True
        elif "wound" in q_key and normalized_val in ("mild", "worried"):
            branch_wound_details = True

        ack_phrase = PhraseBankService.get_rotated_phrase(
            "acknowledgement", language=language, turn_seed=question["step_order"]
        )

        # ── ADVANCE STEP OR COMPLETE ─────────────────────────────────────────
        cur.execute(
            "SELECT COUNT(*) AS total_q FROM checkin_questions WHERE template_id = %s",
            (session["template_id"],)
        )
        total_questions = cur.fetchone()["total_q"]
        next_step = question["step_order"] + 1

        if next_step > total_questions:
            # All questions finished -> Complete session and aggregate answers into symptom_reports
            cur.execute(
                """SELECT q.question_key, q.response_type, a.answer_value
                   FROM checkin_answers a
                   JOIN checkin_questions q ON a.question_id = q.question_id
                   WHERE a.session_id = %s
                   ORDER BY q.step_order ASC""",
                (session_id,)
            )
            all_answers = cur.fetchall()

            pain_score = 0
            notes_parts = []
            facts_list = []
            for ans in all_answers:
                k = ans["question_key"]
                v = ans["answer_value"]
                if "pain" in k:
                    try:
                        pain_score = int(v)
                    except ValueError:
                        pass
                    facts_list.append(f"Pain level: {v}/10" if language == "en" else f"दर्द स्तर: {v}/10")
                elif "emergency" in k:
                    facts_list.append("Acute symptoms: None" if language == "en" else "गंभीर लक्षण: कोई नहीं")
                elif "medication" in k:
                    facts_list.append(f"Medications: {v.replace('_', ' ').title()}" if language == "en" else f"दवाएं: {v}")
                elif "wound" in k:
                    facts_list.append(f"Wound site: {v.replace('_', ' ').title()}" if language == "en" else f"घाव स्थिति: {v}")
                elif "notes" in k and v:
                    facts_list.append(f"Note: {v}" if language == "en" else f"नोट: {v}")
                notes_parts.append(f"{k}: {v}")

            symptom_summary = "Check-in Guide summary: " + " | ".join(notes_parts)

            # Insert normal symptom report so existing stored procedure sp_evaluate_symptom_report runs
            cur.execute(
                """INSERT INTO symptom_reports
                   (patient_id, symptom_text, pain_level, reported_at, input_method, language, emergency_keyword_hit, review_status)
                   VALUES (%s, %s, %s, NOW(), 'Text', %s, 0, 'Pending')""",
                (patient_id, symptom_summary, pain_score, language)
            )
            report_id = cur.lastrowid

            # Run evaluation procedure to check pain thresholds
            try:
                cur.callproc("sp_evaluate_symptom_report", (report_id,))
            except Exception:
                pass

            cur.execute(
                """UPDATE checkin_sessions
                   SET status = 'Completed', completed_at = NOW(), symptom_report_id = %s, current_step = %s
                   WHERE session_id = %s""",
                (report_id, total_questions, session_id)
            )

            # Write audit log
            cur.execute(
                """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                   VALUES ('Patient', %s, 'CHECKIN_SESSION_COMPLETED', 'checkin_session', %s,
                           JSON_OBJECT('template_id', %s, 'report_id', %s, 'pain_level', %s))""",
                (str(patient_id), session_id, session["template_id"], report_id, pain_score)
            )
            conn.commit()

            closing_phrase = PhraseBankService.get_rotated_phrase("closing", language=language, turn_seed=patient_id)

            return {
                "status": "completed",
                "emergency": False,
                "completed": True,
                "session_id": session_id,
                "report_id": report_id,
                "pain_level": pain_score,
                "ack_phrase": ack_phrase,
                "closing_phrase": closing_phrase,
                "facts_summary": facts_list,
                "message": "Daily check-in completed and saved to your chart." if language == "en" else "दैनिक चेक-इन सफलतापूर्वक पूरा हुआ और आपके चार्ट में सहेज लिया गया।"
            }
        else:
            cur.execute(
                """UPDATE checkin_sessions SET current_step = %s WHERE session_id = %s""",
                (next_step, session_id)
            )
            conn.commit()
            return {
                "status": "in_progress",
                "emergency": False,
                "completed": False,
                "session_id": session_id,
                "next_step": next_step,
                "total_steps": total_questions,
                "normalized_value": int(normalized_val) if str(normalized_val).isdigit() else normalized_val,
                "ack_phrase": ack_phrase,
                "branching": {
                    "ask_pain_details": branch_pain_details,
                    "ask_med_barriers": branch_med_barriers,
                    "ask_wound_details": branch_wound_details
                }
            }


def get_doctor_templates_overview() -> List[Dict[str, Any]]:
    """List all check-in templates for Doctor Approvals."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT t.template_id, t.name, t.version, t.status, t.is_active,
                      t.approved_at, t.created_at,
                      s.full_name AS approved_by_name,
                      COUNT(q.question_id) AS question_count
               FROM checkin_templates t
               LEFT JOIN care_staff s ON t.approved_by_staff_id = s.staff_id
               LEFT JOIN checkin_questions q ON t.template_id = q.template_id
               GROUP BY t.template_id, t.name, t.version, t.status, t.is_active,
                        t.approved_at, t.created_at, s.full_name
               ORDER BY t.version DESC, t.template_id ASC"""
        )
        rows = cur.fetchall()
        for r in rows:
            r["is_active"] = bool(r.get("is_active"))
        return rows


def approve_template(template_id: int, doctor_id: int) -> Dict[str, Any]:
    """Doctor approves a check-in template and makes it active."""
    with get_conn() as conn, conn.cursor() as cur:
        # Check template exists
        cur.execute("SELECT template_id, name, status FROM checkin_templates WHERE template_id = %s", (template_id,))
        t = cur.fetchone()
        if not t:
            raise ValueError("Template not found")

        # Deactivate all others
        cur.execute("UPDATE checkin_templates SET is_active = FALSE")
        # Approve and activate this one
        cur.execute(
            """UPDATE checkin_templates
               SET status = 'Approved', approved_by_staff_id = %s, approved_at = NOW(), is_active = TRUE
               WHERE template_id = %s""",
            (doctor_id, template_id)
        )
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Staff', %s, 'APPROVE_CHECKIN_TEMPLATE', 'checkin_template', %s,
                       JSON_OBJECT('doctor_id', %s, 'template_name', %s))""",
            (str(doctor_id), template_id, doctor_id, t["name"])
        )
        conn.commit()
    return {"status": "approved", "template_id": template_id, "is_active": True}
