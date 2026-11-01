"""
backend/app/sms_service.py — CareLoop Outbound & Inbound Two-Way SMS Engine (Feature F3)

Core Principles:
- Single outbound funnel for all SMS; always logs to `sms_messages`.
- Respects `can_send()` automation policy, `SMS_ENABLED`, quiet hours, and patient STOP opt-outs.
- Deterministic inbound parsing without non-deterministic LLM hallucination:
    1 or TAKEN -> confirms next pending dose
    2 or SKIP  -> marks next pending dose skipped
    3 or HELP  -> creates an urgent call request on nurse list & replies with safety text + 112
    STOP       -> opts out patient from SMS
    Emergency  -> raises urgent Emergency flag and triggers nurse/doctor escalation
"""

import os
import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from backend.app.db import get_conn
from backend.app.automation_policy import can_send

SMS_ENABLED = os.getenv("SMS_ENABLED", "false").lower() == "true"
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "+15005550006")


def send_sms(
    to_phone: str,
    body: str,
    patient_id: Optional[int] = None,
    caregiver_id: Optional[int] = None,
    template_key: Optional[str] = None,
    related_type: Optional[str] = None,
    related_id: Optional[int] = None,
    is_automated: bool = True,
    reason: Optional[str] = None
) -> Dict[str, Any]:
    """
    Unified outbound SMS dispatcher.
    Always records row to sms_messages with status ('Logged', 'Sent', or 'Failed').
    """
    clean_phone = re.sub(r"[^\d+]", "", to_phone)

    # 1. Automation policy gate if automated
    if is_automated and patient_id:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT p.patient_id, p.rounds_paused_until, p.sms_opt_out,
                          (SELECT COUNT(*) FROM flags WHERE patient_id = p.patient_id AND severity = 'Urgent_Review' AND status = 'Open') AS open_emergency_flags
                   FROM patients p WHERE p.patient_id = %s""",
                (patient_id,)
            )
            pat = cur.fetchone()
            if pat:
                policy_pat = {
                    "patient_id": pat["patient_id"],
                    "rounds_paused_until": pat["rounds_paused_until"],
                    "sms_opt_out": bool(pat["sms_opt_out"]),
                }
                action_spec = {
                    "channel": "SMS",
                    "reason": reason or "Scheduled SMS notification",
                    "action_type": template_key or "General_SMS",
                    "attempts": 0,
                    "max_attempts": 3,
                }
                has_emergency = pat["open_emergency_flags"] > 0
                allowed, block_reason = can_send(
                    policy_pat,
                    action_spec,
                    daily_message_count=0,
                    has_open_emergency_flag=has_emergency
                )
                if not allowed:
                    # Log blocked attempt
                    with get_conn() as conn2, conn2.cursor() as cur2:
                        cur2.execute(
                            """INSERT INTO sms_messages
                               (direction, patient_id, caregiver_id, phone, body, template_key, related_type, related_id, status, created_at)
                               VALUES ('Outbound', %s, %s, %s, %s, %s, %s, %s, 'Failed', NOW())""",
                            (patient_id, caregiver_id, clean_phone, f"[BLOCKED: {block_reason}] {body}", template_key, related_type, related_id)
                        )
                        conn2.commit()
                    return {"status": "blocked", "reason": block_reason}

    # 2. Dispatch via Twilio if enabled, otherwise Log
    delivery_status = "Logged"
    if SMS_ENABLED and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        try:
            from twilio.rest import Client
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            client.messages.create(body=body, from_=TWILIO_FROM_NUMBER, to=clean_phone)
            delivery_status = "Sent"
        except Exception as e:
            delivery_status = "Failed"

    # 3. Insert record in sms_messages
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO sms_messages
               (direction, patient_id, caregiver_id, phone, body, template_key, related_type, related_id, status, created_at)
               VALUES ('Outbound', %s, %s, %s, %s, %s, %s, %s, %s, NOW())""",
            (patient_id, caregiver_id, clean_phone, body, template_key, related_type, related_id, delivery_status)
        )
        sms_id = cur.lastrowid
        conn.commit()

    return {"status": delivery_status, "sms_id": sms_id, "phone": clean_phone}


def handle_inbound_sms(from_phone: str, body_text: str) -> Dict[str, Any]:
    """
    Deterministic Inbound SMS Parser.
    Maps phone number to patient or caregiver, interprets commands, and takes deterministic action.
    """
    clean_phone = re.sub(r"[^\d+]", "", from_phone)
    raw_digits = re.sub(r"[^\d]", "", from_phone)
    last10 = raw_digits[-10:] if len(raw_digits) >= 10 else raw_digits
    raw_body = body_text.strip()
    cmd = raw_body.upper()

    # 1. Look up patient or caregiver
    with get_conn() as conn, conn.cursor() as cur:
        # Match patient phone normalized
        cur.execute(
            """SELECT patient_id, full_name, phone, sms_opt_out FROM patients
               WHERE REPLACE(REPLACE(phone, '-', ''), ' ', '') LIKE %s LIMIT 1""",
            (f"%{last10}",)
        )
        patient = cur.fetchone()
        caregiver = None
        if not patient:
            cur.execute(
                """SELECT c.caregiver_id, c.patient_id, c.full_name, c.phone, p.full_name AS patient_name
                   FROM caregivers c
                   JOIN patients p ON c.patient_id = p.patient_id
                   WHERE REPLACE(REPLACE(c.phone, '-', ''), ' ', '') LIKE %s LIMIT 1""",
                (f"%{last10}",)
            )
            caregiver = cur.fetchone()

        if not patient and not caregiver:
            # Unknown phone number: log and ignore
            cur.execute(
                """INSERT INTO sms_messages
                   (direction, phone, body, status, created_at)
                   VALUES ('Inbound', %s, %s, 'Received', NOW())""",
                (clean_phone, raw_body)
            )
            conn.commit()
            return {"action": "ignored_unknown_number", "reply": None}

        pat_id = patient["patient_id"] if patient else caregiver["patient_id"]
        cg_id = caregiver["caregiver_id"] if caregiver else None

        # Record incoming message
        cur.execute(
            """INSERT INTO sms_messages
               (direction, patient_id, caregiver_id, phone, body, status, created_at)
               VALUES ('Inbound', %s, %s, %s, %s, 'Received', NOW())""",
            (pat_id, cg_id, clean_phone, raw_body)
        )
        conn.commit()

    # 2. EMERGENCY KEYWORDS
    emergency_patterns = ["CHEST PAIN", "BREATHING", "BLEED", "SEENE MEIN DARD", "SANS", "UNCONSCIOUS", "EMERGENCY"]
    if any(pat in cmd for pat in emergency_patterns):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO symptom_reports
                   (patient_id, symptom_text, pain_level, reported_at, input_method, language, emergency_keyword_hit, review_status)
                   VALUES (%s, %s, %s, NOW(), 'Text', 'en', 1, 'Pending')""",
                (pat_id, f"[SMS Emergency Keyword Match] Inbound text: {raw_body}", 0)
            )
            report_id = cur.lastrowid
            cur.execute(
                """INSERT INTO flags (patient_id, source_type, source_ref_id, reason, severity, status, created_at)
                   VALUES (%s, 'Emergency', %s, %s, 'Urgent_Review', 'Open', NOW())""",
                (pat_id, report_id, f"Inbound SMS Emergency Keyword: '{raw_body}'")
            )
            flag_id = cur.lastrowid
            cur.execute(
                """INSERT INTO escalations (flag_id, step_no, step_type, channel, delivery_status, notes, sent_at)
                   VALUES (%s, 1, 'Nurse_Alert', 'Dashboard', 'Sent', 'Inbound SMS emergency keyword matched acute symptom', NOW())""",
                (flag_id,)
            )
            cur.execute(
                """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                   VALUES ('Patient', %s, 'SMS_EMERGENCY_TRIGGER', 'flag', %s, JSON_OBJECT('body', %s))""",
                (str(pat_id), flag_id, raw_body)
            )
            conn.commit()

        reply_text = (
            "EMERGENCY ALERT: Your care team has been alerted immediately. "
            "Please sit down, rest, and stay calm. If you feel severe chest tightness or difficulty breathing, immediately dial 112."
        )
        send_sms(clean_phone, reply_text, patient_id=pat_id, caregiver_id=cg_id, is_automated=False)
        return {"action": "emergency_flag_created", "flag_id": flag_id, "reply": reply_text}

    # 3. OPT-OUT (STOP / UNSUBSCRIBE)
    if cmd in ["STOP", "UNSUBSCRIBE", "CANCEL", "ROKO"]:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("UPDATE patients SET sms_opt_out = TRUE WHERE patient_id = %s", (pat_id,))
            cur.execute(
                """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                   VALUES ('Patient', %s, 'SMS_OPT_OUT', 'patient', %s, JSON_OBJECT('phone', %s))""",
                (str(pat_id), pat_id, clean_phone)
            )
            conn.commit()
        reply_text = "You have unsubscribed from CareLoop SMS notifications. Reply START to resume messages at any time."
        send_sms(clean_phone, reply_text, patient_id=pat_id, caregiver_id=cg_id, is_automated=False)
        return {"action": "opt_out", "reply": reply_text}

    # 4. OPT-IN (START / RESUME)
    if cmd in ["START", "SUBSCRIBE", "RESUME", "SHURU"]:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("UPDATE patients SET sms_opt_out = FALSE WHERE patient_id = %s", (pat_id,))
            conn.commit()
        reply_text = "CareLoop SMS notifications have been resumed. We are here to support your recovery."
        send_sms(clean_phone, reply_text, patient_id=pat_id, caregiver_id=cg_id, is_automated=False)
        return {"action": "opt_in", "reply": reply_text}

    # 5. COMMAND 1 or TAKEN (Confirm dose)
    if cmd in ["1", "TAKEN", "HAAN", "YES"]:
        with get_conn() as conn, conn.cursor() as cur:
            # Find earliest unconfirmed dose today
            cur.execute(
                """SELECT ml.medication_log_id, ml.prescription_id, ml.scheduled_for, m.medicine_name
                   FROM medication_logs ml
                   JOIN prescriptions p ON ml.prescription_id = p.prescription_id
                   JOIN medicines m ON p.medicine_id = m.medicine_id
                   WHERE p.patient_id = %s AND ml.status = 'Unconfirmed'
                     AND DATE(ml.scheduled_for) = CURDATE()
                   ORDER BY ml.scheduled_for ASC LIMIT 1""",
                (pat_id,)
            )
            pending_dose = cur.fetchone()
            if pending_dose:
                cur.execute(
                    """UPDATE medication_logs
                       SET status = 'Taken_Confirmed', recorded_at = NOW(), recorded_by = 'Patient',
                           patient_note = 'Confirmed via inbound SMS'
                       WHERE medication_log_id = %s""",
                    (pending_dose["medication_log_id"],)
                )
                cur.execute(
                    """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                       VALUES ('Patient', %s, 'SMS_DOSE_CONFIRMED', 'medication_log', %s,
                               JSON_OBJECT('medicine', %s, 'scheduled', %s))""",
                    (str(pat_id), pending_dose["medication_log_id"], pending_dose["medicine_name"], str(pending_dose["scheduled_for"]))
                )
                conn.commit()
                sched_time = pending_dose["scheduled_for"].strftime("%I:%M %p")
                reply_text = f"Confirmed: Your dose of {pending_dose['medicine_name']} ({sched_time}) has been marked taken. Thank you."
            else:
                reply_text = "All scheduled doses for today have already been confirmed. Thank you."
        send_sms(clean_phone, reply_text, patient_id=pat_id, caregiver_id=cg_id, is_automated=False)
        return {"action": "dose_confirmed", "reply": reply_text}

    # 6. COMMAND 2 or SKIP (Skip dose)
    if cmd in ["2", "SKIP", "NAHI", "NO"]:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT ml.medication_log_id, ml.prescription_id, ml.scheduled_for, m.medicine_name
                   FROM medication_logs ml
                   JOIN prescriptions p ON ml.prescription_id = p.prescription_id
                   JOIN medicines m ON p.medicine_id = m.medicine_id
                   WHERE p.patient_id = %s AND ml.status = 'Unconfirmed'
                     AND DATE(ml.scheduled_for) = CURDATE()
                   ORDER BY ml.scheduled_for ASC LIMIT 1""",
                (pat_id,)
            )
            pending_dose = cur.fetchone()
            if pending_dose:
                cur.execute(
                    """UPDATE medication_logs
                       SET status = 'Skipped', recorded_at = NOW(), recorded_by = 'Patient',
                           patient_note = 'Skipped via inbound SMS'
                       WHERE medication_log_id = %s""",
                    (pending_dose["medication_log_id"],)
                )
                cur.execute(
                    """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                       VALUES ('Patient', %s, 'SMS_DOSE_SKIPPED', 'medication_log', %s,
                               JSON_OBJECT('medicine', %s, 'scheduled', %s))""",
                    (str(pat_id), pending_dose["medication_log_id"], pending_dose["medicine_name"], str(pending_dose["scheduled_for"]))
                )
                conn.commit()
                sched_time = pending_dose["scheduled_for"].strftime("%I:%M %p")
                reply_text = f"Recorded: Dose of {pending_dose['medicine_name']} ({sched_time}) marked skipped. Please contact your care team if experiencing side effects."
            else:
                reply_text = "No pending dose to skip for today."
        send_sms(clean_phone, reply_text, patient_id=pat_id, caregiver_id=cg_id, is_automated=False)
        return {"action": "dose_skipped", "reply": reply_text}

    # 7. COMMAND 3 or HELP (Nurse Callback Request)
    if cmd in ["3", "HELP", "MADAD", "CALL"]:
        with get_conn() as conn, conn.cursor() as cur:
            # Create urgent follow-up task on nurse call queue
            cur.execute(
                """INSERT INTO follow_up_tasks
                   (patient_id, assigned_staff_id, reason, priority, status, due_at, created_at)
                   VALUES (%s, 2, 'Urgent SMS HELP callback request: Patient requested triage call via SMS',
                           'Urgent_Review', 'Pending', NOW() + INTERVAL 30 MINUTE, NOW())""",
                (pat_id,)
            )
            task_id = cur.lastrowid
            cur.execute(
                """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                   VALUES ('Patient', %s, 'SMS_HELP_CALLBACK_REQUESTED', 'follow_up_task', %s,
                           JSON_OBJECT('phone', %s, 'priority', 'Urgent_Review'))""",
                (str(pat_id), task_id, clean_phone)
            )
            conn.commit()
        reply_text = (
            "Your care team has received your request. A triage nurse will call you shortly. "
            "If this is an immediate medical emergency, please dial 112."
        )
        send_sms(clean_phone, reply_text, patient_id=pat_id, caregiver_id=cg_id, is_automated=False)
        return {"action": "help_callback_created", "task_id": task_id, "reply": reply_text}

    # 8. DEFAULT FALLBACK
    reply_text = (
        "CareLoop: Reply 1 for TAKEN, 2 for SKIP, 3 for NURSE HELP. In an emergency, dial 112."
    )
    send_sms(clean_phone, reply_text, patient_id=pat_id, caregiver_id=cg_id, is_automated=False)
    return {"action": "help_options_sent", "reply": reply_text}


def get_patient_sms_messages(patient_id: int) -> list:
    """Retrieve SMS message history for a patient chart."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT sms_id, direction, phone, body, template_key, status, created_at
               FROM sms_messages
               WHERE patient_id = %s
               ORDER BY created_at DESC
               LIMIT 50""",
            (patient_id,)
        )
        return cur.fetchall()
