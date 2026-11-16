"""
backend/app/escalation.py — CareLoop Escalation Ladder & Clinical Notification Agent

Features:
- Deterministic escalation ladders based on flag severity (Urgent_Review vs Review_Soon).
- Consent-gated caregiver notifications: Caregiver_SMS is skipped with status
  'Skipped_No_Consent' if no consented caregiver exists for the patient.
- SMS delivery via Twilio, with safe fallback when SMS_ENABLED is false (demo mode).
- SMS messages are strictly privacy-conscious and contain NO diagnosis details.
- Every escalation step writes an immutable audit_log row.
"""

import os
from datetime import datetime
from .db import get_conn

# Ladders: (step_no, step_type, channel, offset_minutes)
LADDER_REVIEW_SOON = [
    (1, "Patient_Prompt", "App", 0),
    (2, "Caregiver_SMS", "SMS", 20),
    (3, "Nurse_Alert", "Dashboard", 40),
    (4, "Doctor_Alert", "Dashboard", 90),
]

LADDER_URGENT = [
    (1, "Patient_Prompt", "App", 0),
    (2, "Nurse_Alert", "Dashboard", 0),
    (3, "Doctor_Alert", "Dashboard", 0),
    (4, "Caregiver_SMS", "SMS", 10),
]


def send_sms(to: str, body: str) -> str:
    """
    Sends SMS via Twilio if SMS_ENABLED=true.
    In demo mode, logs the dispatch and returns 'Sent'.
    Failures return 'Failed' without stopping the escalation ladder.
    """
    if not to:
        return "Failed"

    if os.getenv("SMS_ENABLED", "false").lower() != "true":
        print(f"[Escalation/SMS-Demo] 📱 Would send SMS to {to}: '{body}'")
        return "Sent"

    try:
        from twilio.rest import Client
        sid = os.getenv("TWILIO_ACCOUNT_SID")
        token = os.getenv("TWILIO_AUTH_TOKEN")
        from_num = os.getenv("TWILIO_FROM_NUMBER")
        if not (sid and token and from_num):
            print("[Escalation/SMS] ⚠️ Twilio credentials missing in .env")
            return "Failed"

        client = Client(sid, token)
        msg = client.messages.create(to=to, from_=from_num, body=body)
        print(f"[Escalation/SMS] ✅ SMS dispatched to {to} (SID: {msg.sid})")
        return "Sent"
    except Exception as e:
        print(f"[Escalation/SMS] ❌ SMS delivery error to {to}: {e}")
        return "Failed"


def run_escalations():
    """
    Core escalation loop called by the scheduler.
    Finds all Open flags and walks through the appropriate ladder steps.
    """
    now = datetime.now()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT flag_id, patient_id, severity, created_at FROM flags WHERE status = 'Open'")
        open_flags = cur.fetchall()

        for f in open_flags:
            ladder = LADDER_URGENT if f["severity"] == "Urgent_Review" else LADDER_REVIEW_SOON
            minutes_open = (now - f["created_at"]).total_seconds() / 60.0

            for step_no, step_type, channel, offset in ladder:
                if minutes_open < offset:
                    continue  # Timeout window has not passed yet

                # Check if this step was already recorded
                cur.execute(
                    "SELECT 1 FROM escalations WHERE flag_id = %s AND step_no = %s",
                    (f["flag_id"], step_no),
                )
                if cur.fetchone():
                    continue

                status = "Sent"
                note = None

                # ── CONSENT GATE: Check caregiver consent before sending SMS ──
                if step_type == "Caregiver_SMS":
                    cur.execute(
                        """SELECT caregiver_id, phone, full_name, consent_granted
                           FROM caregivers
                           WHERE patient_id = %s AND consent_granted = TRUE
                           ORDER BY is_primary DESC, caregiver_id ASC LIMIT 1""",
                        (f["patient_id"],),
                    )
                    cg = cur.fetchone()

                    if not cg:
                        status = "Skipped_No_Consent"
                        note = "Caregiver step skipped: No caregiver with recorded consent"
                        print(f"[Escalation] 🔒 Patient #{f['patient_id']} - Caregiver step skipped: Skipped_No_Consent")
                    else:
                        sms_body = "CareLoop: The care team is checking on a recent health update for the patient. Please contact them when convenient."
                        status = send_sms(cg["phone"], sms_body)
                        note = f"Notified caregiver {cg['full_name']}"

                # Insert escalation record
                cur.execute(
                    """INSERT IGNORE INTO escalations
                       (flag_id, step_no, step_type, channel, delivery_status, notes)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (f["flag_id"], step_no, step_type, channel, status, note),
                )

                # Write immutable audit log
                cur.execute(
                    """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                       VALUES ('Agent', 'escalation_agent', 'ESCALATION_STEP', 'flag', %s,
                               JSON_OBJECT('step', %s, 'channel', %s, 'status', %s, 'patient_id', %s))""",
                    (str(f["flag_id"]), step_type, channel, status, f["patient_id"]),
                )
                print(f"[Escalation] ⚡ Flag #{f['flag_id']} -> Step {step_no} ({step_type}) status={status}")
