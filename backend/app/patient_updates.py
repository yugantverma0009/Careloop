"""
backend/app/patient_updates.py — Proactive Patient Updates & Automation Limits Engine

Assistant v2 (Phase 4):
Automated messages (reminders, prompts, plan of the day) land in the patient's
Updates inbox. All proactive system updates MUST respect clinical automation limits:
1. Quiet hours (22:00 - 07:00 local time): non-emergency automated messages are suppressed.
2. Max 2 reminders per dose.
3. Max 3 other automated messages per day.
4. No new prompts while an open emergency flag exists on the patient.
5. De-duplication per topic per day.
6. Every created or suppressed update is recorded in the audit log with a clear reason.
"""

import json
import logging
from datetime import datetime, time
from typing import Optional, Dict, Any, Tuple
from .db import get_conn

logger = logging.getLogger(__name__)

QUIET_HOURS_START = 22  # 10:00 PM
QUIET_HOURS_END = 7     # 07:00 AM

MAX_REMINDERS_PER_DOSE = 2
MAX_OTHER_AUTOMATED_PER_DAY = 3


def is_in_quiet_hours(current_time: Optional[datetime] = None) -> bool:
    """Check if the given time (or now) falls in quiet hours (22:00 to 07:00)."""
    now = current_time or datetime.now()
    hour = now.hour
    return hour >= QUIET_HOURS_START or hour < QUIET_HOURS_END


def create_patient_update(
    patient_id: int,
    update_type: str,
    title: str,
    body: str,
    action_type: Optional[str] = None,
    action_payload: Optional[Dict[str, Any]] = None,
    source_action_id: Optional[int] = None,
    created_by: str = "System",
    force: bool = False,
    override_time: Optional[datetime] = None,
) -> Tuple[bool, Optional[int], str]:
    """
    Creates a proactive update for the patient, applying deterministic automation limits.
    Returns: (success: bool, update_id: Optional[int], message_or_reason: str)
    """
    check_time = override_time or datetime.now()

    with get_conn() as conn:
        with conn.cursor() as cur:
            # 1. Quiet Hours Check (Only applies to System, Staff bypasses quiet hours)
            if created_by == "System" and not force:
                if is_in_quiet_hours(check_time):
                    reason = f"Quiet hours active ({QUIET_HOURS_START}:00 - {QUIET_HOURS_END:00}). Automated message held."
                    _log_suppression(cur, patient_id, update_type, title, reason, check_time)
                    conn.commit()
                    return False, None, reason

            # 2. Open Emergency Flag Check (Never distract or confuse a patient experiencing an active emergency)
            cur.execute(
                """SELECT flag_id, reason FROM flags
                   WHERE patient_id = %s AND status = 'Open' AND (severity = 'Urgent_Review' OR source_type = 'Emergency' OR source_type = 'SOS')
                   LIMIT 1""",
                (patient_id,),
            )
            emg_flag = cur.fetchone()
            if emg_flag and not force:
                reason = f"Suppressed because patient has an active Emergency flag (#{emg_flag['flag_id']}: {emg_flag['reason']})."
                _log_suppression(cur, patient_id, update_type, title, reason, check_time)
                conn.commit()
                return False, None, reason

            # 3. De-duplication check: identical update_type and title today
            cur.execute(
                """SELECT update_id FROM patient_updates
                   WHERE patient_id = %s AND update_type = %s AND title = %s
                     AND DATE(created_at) = %s
                   LIMIT 1""",
                (patient_id, update_type, title, check_time.date()),
            )
            if cur.fetchone():
                reason = f"Duplicate update suppressed: '{title}' was already delivered today."
                _log_suppression(cur, patient_id, update_type, title, reason, check_time)
                conn.commit()
                return False, None, reason

            # 4. Limit: Max 2 reminders per dose
            if update_type == "reminder_dose":
                cur.execute(
                    """SELECT COUNT(*) AS cnt FROM patient_updates
                       WHERE patient_id = %s AND update_type = 'reminder_dose'
                         AND title = %s AND DATE(created_at) = %s""",
                    (patient_id, title, check_time.date()),
                )
                dose_rem_count = cur.fetchone()["cnt"]
                if dose_rem_count >= MAX_REMINDERS_PER_DOSE:
                    reason = f"Dose reminder cap reached ({MAX_REMINDERS_PER_DOSE} max per dose per day)."
                    _log_suppression(cur, patient_id, update_type, title, reason, check_time)
                    conn.commit()
                    return False, None, reason

            # 5. Limit: Max 3 other automated messages per day
            if created_by == "System" and update_type != "reminder_dose":
                cur.execute(
                    """SELECT COUNT(*) AS cnt FROM patient_updates
                       WHERE patient_id = %s AND created_by = 'System'
                         AND update_type != 'reminder_dose'
                         AND DATE(created_at) = %s""",
                    (patient_id, check_time.date()),
                )
                other_count = cur.fetchone()["cnt"]
                if other_count >= MAX_OTHER_AUTOMATED_PER_DAY:
                    reason = f"Daily automated message cap reached ({MAX_OTHER_AUTOMATED_PER_DAY} max non-dose messages per day)."
                    _log_suppression(cur, patient_id, update_type, title, reason, check_time)
                    conn.commit()
                    return False, None, reason

            # All limits satisfied -> Insert update
            payload_json = json.dumps(action_payload, ensure_ascii=False) if action_payload else None
            cur.execute(
                """INSERT INTO patient_updates (patient_id, update_type, title, body, action_type, action_payload, source_action_id, created_by, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (patient_id, update_type, title, body, action_type, payload_json, source_action_id, created_by, check_time),
            )
            update_id = cur.lastrowid

            # Write audit log
            cur.execute(
                """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details, created_at)
                   VALUES (%s, %s, 'PATIENT_UPDATE_CREATED', 'patient_update', %s,
                           JSON_OBJECT('update_type', %s, 'title', %s, 'action_type', %s), %s)""",
                (created_by, str(patient_id), update_id, update_type, title, action_type, check_time),
            )
            conn.commit()
            return True, update_id, "Update delivered successfully."


def _log_suppression(cur, patient_id: int, update_type: str, title: str, reason: str, timestamp: datetime):
    """Audits suppressed proactive messages to guarantee complete governance transparency."""
    cur.execute(
        """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details, created_at)
           VALUES ('System', %s, 'PATIENT_UPDATE_SUPPRESSED', 'patient', %s,
                   JSON_OBJECT('update_type', %s, 'title', %s, 'reason', %s), %s)""",
        (str(patient_id), patient_id, update_type, title, reason, timestamp),
    )

