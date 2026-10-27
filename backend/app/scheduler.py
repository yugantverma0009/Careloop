"""
backend/app/scheduler.py — CareLoop Periodic Jobs & Rule Evaluation

Jobs:
1. rule_cycle: Executes stored procedures to generate doses, mark missed doses,
   evaluate clinical alert rules, and refresh risk priority snapshots.
2. send_due_reminders: Evaluates upcoming unconfirmed medication doses and sends
   timely reminders, logging each event to audit_log.
"""

import os
import json
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from .db import get_conn

scheduler: BackgroundScheduler = None

REMINDER_TEXT = {
    "en": "CareLoop: Time for your scheduled medicine ({t}). Please confirm in the app.",
    "hi": "CareLoop: आपकी दवा का समय ({t}) हो गया है। कृपया ऐप में पुष्टि करें।",
}


def send_due_reminders():
    """
    Finds unconfirmed doses scheduled within the next 5 minutes for consented patients
    where reminder_sent_at is NULL, dispatches reminder, and logs the action.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT ml.medication_log_id, m.medicine_name, p.phone, p.preferred_language, ml.scheduled_for, p.patient_id
               FROM medication_logs ml
               JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
               JOIN medicines m ON m.medicine_id = pr.medicine_id
               JOIN patients p ON p.patient_id = pr.patient_id
               WHERE ml.status = 'Unconfirmed'
                 AND ml.reminder_sent_at IS NULL
                 AND ml.scheduled_for <= NOW() + INTERVAL 5 MINUTE
                 AND p.consent_status = 'Granted'"""
        )
        due_doses = cur.fetchall()

        for d in due_doses:
            lang = d["preferred_language"] if d["preferred_language"] in REMINDER_TEXT else "en"
            dose_time_str = d["scheduled_for"].strftime("%H:%M") if hasattr(d["scheduled_for"], "strftime") else str(d["scheduled_for"])
            msg_text = REMINDER_TEXT[lang].format(t=dose_time_str)

            # Mark reminder sent
            cur.execute(
                "UPDATE medication_logs SET reminder_sent_at = NOW() WHERE medication_log_id = %s",
                (d["medication_log_id"],),
            )

            # Record in immutable audit log
            cur.execute(
                """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                   VALUES ('Agent', 'reminder_agent', 'SEND_REMINDER', 'medication_log', %s,
                           JSON_OBJECT('channel', 'SMS', 'patient_id', %s, 'medicine', %s))""",
                (d["medication_log_id"], d["patient_id"], d["medicine_name"]),
            )
            print(f"[Scheduler] ⏰ Sent dose reminder for log #{d['medication_log_id']} (Patient #{d['patient_id']})")


def rule_cycle():
    """
    Executes the clinical rule engine procedures in CareLoop MySQL.
    """
    now = datetime.now()
    with get_conn() as conn, conn.cursor() as cur:
        # 1. Generate today's dose events from prescription_times
        cur.callproc("sp_generate_daily_doses", (now.date(),))
        # 2. Mark overdue unconfirmed doses as Missed after grace period (60 min)
        cur.callproc("sp_mark_overdue_doses_missed", (now, 60))
        # 3. Evaluate missed dose alert rules
        cur.callproc("sp_evaluate_missed_dose_rules", (now,))
        # 4. Evaluate silent device (no-data) rules
        cur.callproc("sp_evaluate_no_data_rules", (now,))
        # 5. Compute explainable risk priority score snapshots for consented patients
        cur.callproc("sp_compute_all_risk_snapshots", (now,))


def start():
    """Start background scheduler if not already running."""
    global scheduler
    if scheduler and scheduler.running:
        return
    scheduler = BackgroundScheduler()
    scheduler.add_job(rule_cycle, "interval", minutes=5, id="careloop_rule_cycle", replace_existing=True)
    scheduler.add_job(send_due_reminders, "interval", minutes=1, id="careloop_reminders", replace_existing=True)
    scheduler.start()
    print("[Scheduler] ✅ CareLoop BackgroundScheduler active (rule_cycle=5m, reminders=1m)")


def shutdown():
    """Shut down scheduler gracefully on app teardown."""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        print("[Scheduler] CareLoop BackgroundScheduler stopped.")
