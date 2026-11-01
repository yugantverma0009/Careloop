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
    patient_id: int,
    question_id: int,
    answer_value: str,
    raw_input: Optional[str] = None
) -> Dict[str, Any]:
    """
    Record an answer for the current question in a session.
    If the question is an emergency trigger and the answer is positive:
    - Immediately creates an emergency symptom report and triggers urgent escalation.
    - Halts subsequent routine questions.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT session_id, patient_id, template_id, status, current_step
               FROM checkin_sessions
               WHERE session_id = %s AND patient_id = %s""",
            (session_id, patient_id)
        )
        session = cur.fetchone()
        if not session:
            raise ValueError("Check-in session not found.")
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

        # Save or update answer
        cur.execute(
            """INSERT INTO checkin_answers (session_id, question_id, answer_value, raw_input, created_at)
               VALUES (%s, %s, %s, %s, NOW())""",
            (session_id, question_id, str(answer_value), raw_input)
        )

        # ── EMERGENCY TRIGGER CHECK ──────────────────────────────────────────
        is_emergency = False
        val_clean = str(answer_value).strip().lower()
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
                "completed": True,
                "session_id": session_id,
                "report_id": report_id,
                "flag_id": flag_id,
                "guidance_en": "Immediate Safety Alert: A triage nurse has been alerted right now. Please sit down, rest, and keep your phone near. If you feel severe chest tightness or difficulty breathing, call 112 immediately.",
                "guidance_hi": "आपातकालीन सुरक्षा सूचना: आपकी देखभाल टीम को तुरंत सूचित कर दिया गया है। कृपया आराम से बैठें। यदि सीने में तेज दबाव या सांस लेने में गंभीर तकलीफ हो, तो तुरंत 112 पर कॉल करें।"
            }

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
            for ans in all_answers:
                k = ans["question_key"]
                v = ans["answer_value"]
                if "pain" in k:
                    try:
                        pain_score = int(v)
                    except ValueError:
                        pass
                notes_parts.append(f"{k}: {v}")

            symptom_summary = "Check-in Guide summary: " + " | ".join(notes_parts)

            # Insert normal symptom report so existing stored procedure sp_evaluate_symptom_report runs
            cur.execute(
                """INSERT INTO symptom_reports
                   (patient_id, symptom_text, pain_level, reported_at, input_method, language, emergency_keyword_hit, review_status)
                   VALUES (%s, %s, %s, NOW(), 'Text', 'en', 0, 'Pending')""",
                (patient_id, symptom_summary, pain_score)
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

            return {
                "status": "completed",
                "emergency": False,
                "completed": True,
                "session_id": session_id,
                "report_id": report_id,
                "pain_level": pain_score,
                "message": "Daily check-in completed and saved to your chart."
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
                "total_steps": total_questions
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
