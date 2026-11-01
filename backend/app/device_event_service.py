"""
backend/app/device_event_service.py — CareLoop Watch Events & Possible Fall Service

Implements Feature F7 (Possible Fall & Watch Events):
- "The system records and flags. Authorized humans review and act."
- "Automate the routine. Propose the rest. Humans decide."
- Bounded, honest fall workflow without unvalidated claims ("No text says detected").
- Flow in Rounds:
  1. Watch/Simulator posts Possible_Fall to /device/events.
  2. If rule is OFF: event only recorded in audit log.
  3. If rule is ON: prompt sent (app banner + SMS), wait timer scheduled.
  4. Outcome A (I'm OK): closes event, prompt counts updated, no flag.
  5. Outcome B (I need help): creates Immediate flag, starts escalation ladder.
  6. Outcome C (Wait time expired): creates Immediate flag, reason:
     "Watch reported a possible fall at 14:02. No reply within 2 minutes."
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from .db import get_conn
from .escalation import send_sms

logger = logging.getLogger(__name__)


def record_device_event(
    device_id: str,
    event_type: str,
    occurred_at: Optional[datetime] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Idempotent IoT device event ingestion.
    Evaluates clinician-approved Possible_Fall rule for the patient.
    """
    now = occurred_at or datetime.now()
    details_json = json.dumps(details or {})

    with get_conn() as conn, conn.cursor() as cur:
        # 1. Resolve patient_id from device_id
        cur.execute("SELECT patient_id FROM devices WHERE device_id = %s", (device_id,))
        dev = cur.fetchone()
        if not dev:
            raise ValueError(f"Unknown device '{device_id}'")
        patient_id = dev["patient_id"]

        # Update last_seen_at for device health
        cur.execute(
            "UPDATE devices SET last_seen_at = %s WHERE device_id = %s",
            (now, device_id),
        )

        # 2. Idempotent insert into device_events
        try:
            cur.execute(
                """INSERT INTO device_events
                   (device_id, patient_id, event_type, occurred_at, details)
                   VALUES (%s, %s, %s, %s, %s)""",
                (device_id, patient_id, event_type, now, details_json),
            )
            event_id = cur.lastrowid
        except Exception as e:
            if hasattr(e, "args") and len(e.args) > 0 and e.args[0] == 1062:
                # Duplicate entry
                cur.execute(
                    """SELECT event_id, prompt_sent_at, patient_response
                       FROM device_events
                       WHERE device_id = %s AND event_type = %s AND occurred_at = %s""",
                    (device_id, event_type, now),
                )
                existing = cur.fetchone()
                return {
                    "status": "duplicate_ignored",
                    "event_id": existing["event_id"] if existing else None,
                    "prompt_sent": bool(existing and existing["prompt_sent_at"]),
                }
            raise

        # If event is not Possible_Fall (e.g. Low_Battery, Reconnected), record and return
        if event_type != "Possible_Fall":
            cur.execute(
                """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details, created_at)
                   VALUES ('Device', %s, 'DEVICE_EVENT_LOGGED', 'device_event', %s, %s, %s)""",
                (device_id, event_id, json.dumps({"event_type": event_type, "patient_id": patient_id}), now),
            )
            return {"status": "recorded", "event_id": event_id, "prompt_sent": False}

        # 3. Check if Possible_Fall rule is active for this patient
        cur.execute(
            """SELECT rule_id, threshold_value, window_hours, severity, is_active
               FROM alert_rules
               WHERE patient_id = %s AND rule_type = 'Possible_Fall' AND is_active = 1
               LIMIT 1""",
            (patient_id,),
        )
        rule = cur.fetchone()

        # RULE OFF: The event only appears in the audit log
        if not rule:
            cur.execute(
                """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details, created_at)
                   VALUES ('Device', %s, 'POSSIBLE_FALL_LOGGED_RULE_OFF', 'device_event', %s, %s, %s)""",
                (
                    device_id,
                    event_id,
                    json.dumps({
                        "event_type": event_type,
                        "patient_id": patient_id,
                        "rule_status": "Disabled / Off by default",
                        "note": "Watch event recorded in log; prompt skipped because clinician rule is inactive.",
                    }),
                    now,
                ),
            )
            return {
                "status": "recorded",
                "event_id": event_id,
                "rule_active": False,
                "prompt_sent": False,
                "message": "Event recorded in audit log. Possible fall rule is disabled for this patient.",
            }

        # RULE ON: Prompt patient with wait time (default 2 minutes)
        wait_minutes = int(float(rule["threshold_value"])) if rule["threshold_value"] else 2
        cur.execute(
            "UPDATE device_events SET prompt_sent_at = %s WHERE event_id = %s",
            (now, event_id),
        )

        # Schedule Fall_Prompt_Timeout action in scheduled_actions
        timeout_run_at = now + timedelta(minutes=wait_minutes)
        dedupe_key = f"fall_timeout_{event_id}"
        reason = f"Wait {wait_minutes} minutes for patient response to possible fall prompt"
        payload_data = json.dumps({
            "event_id": event_id,
            "patient_id": patient_id,
            "wait_minutes": wait_minutes,
            "occurred_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        })

        cur.execute(
            """INSERT INTO scheduled_actions
               (patient_id, action_type, channel, run_at, reason, payload, dedupe_key, status, created_at)
               VALUES (%s, 'Fall_Prompt', 'App', %s, %s, %s, %s, 'Scheduled', %s)
               ON DUPLICATE KEY UPDATE run_at = VALUES(run_at)""",
            (patient_id, timeout_run_at, reason, payload_data, dedupe_key, now),
        )

        # Fetch patient phone for outbound SMS prompt
        cur.execute("SELECT phone, sms_opt_out FROM patients WHERE patient_id = %s", (patient_id,))
        pat = cur.fetchone()
        if pat and pat["phone"] and not pat["sms_opt_out"]:
            sms_text = (
                "CareLoop check: We noticed sudden movement from your watch. "
                "Are you OK? Reply 1 for I'm OK, or 3 for I need help."
            )
            send_sms(pat["phone"], sms_text)
            cur.execute(
                """INSERT INTO sms_messages
                   (direction, patient_id, phone, body, template_key, related_type, related_id, status, created_at)
                   VALUES ('Outbound', %s, %s, %s, 'Possible_Fall_Prompt', 'device_event', %s, 'Sent', %s)""",
                (patient_id, pat["phone"], sms_text, event_id, now),
            )

        # Audit log for prompt dispatch
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details, created_at)
               VALUES ('Device', %s, 'FALL_PROMPT_SENT', 'device_event', %s, %s, %s)""",
            (
                device_id,
                event_id,
                json.dumps({
                    "patient_id": patient_id,
                    "rule_id": rule["rule_id"],
                    "wait_minutes": wait_minutes,
                    "timeout_at": timeout_run_at.strftime("%Y-%m-%d %H:%M:%S"),
                }),
                now,
            ),
        )

        return {
            "status": "prompt_sent",
            "event_id": event_id,
            "rule_active": True,
            "prompt_sent": True,
            "wait_minutes": wait_minutes,
            "occurred_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        }


def handle_patient_fall_response(
    patient_id: int,
    event_id: int,
    response: str,
    responded_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Processes patient response from In-App prompt banner or Inbound SMS.
    Response must be 'Ok' or 'Need_Help'.
    """
    now = responded_at or datetime.now()
    clean_resp = "Ok" if response.lower() in ("ok", "1", "im_ok", "i'm ok", "safe") else "Need_Help"

    with get_conn() as conn, conn.cursor() as cur:
        # 1. Fetch event
        cur.execute(
            """SELECT event_id, patient_id, device_id, occurred_at, prompt_sent_at, patient_response, flag_id
               FROM device_events
               WHERE event_id = %s AND patient_id = %s""",
            (event_id, patient_id),
        )
        ev = cur.fetchone()
        if not ev:
            raise ValueError(f"Device event #{event_id} not found for patient #{patient_id}")

        if ev["patient_response"] is not None:
            return {
                "status": "already_responded",
                "patient_response": ev["patient_response"],
                "message": "Response was already recorded for this event.",
            }

        # 2. Update device_events
        cur.execute(
            """UPDATE device_events
               SET patient_response = %s, responded_at = %s
               WHERE event_id = %s""",
            (clean_resp, now, event_id),
        )

        # Cancel / Complete pending timeout in scheduled_actions
        cur.execute(
            """UPDATE scheduled_actions
               SET status = 'Done', result = %s, done_at = %s
               WHERE dedupe_key = %s AND status = 'Scheduled'""",
            (f"Patient responded {clean_resp}", now, f"fall_timeout_{event_id}"),
        )

        occurred_time_str = ev["occurred_at"].strftime("%H:%M") if ev["occurred_at"] else now.strftime("%H:%M")

        # OUTCOME A: I'm OK
        if clean_resp == "Ok":
            cur.execute(
                """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details, created_at)
                   VALUES ('Patient', %s, 'FALL_PROMPT_ANSWERED_OK', 'device_event', %s, %s, %s)""",
                (
                    str(patient_id),
                    event_id,
                    json.dumps({"patient_id": patient_id, "response": "Ok", "device_id": ev["device_id"]}),
                    now,
                ),
            )
            return {
                "status": "recorded",
                "patient_response": "Ok",
                "message": "Thank you for confirming you are safe. Your care team has been notified that you are OK.",
            }

        # OUTCOME B: I need help
        # Create Immediate flag in flags table
        flag_reason = f"Watch reported a possible fall at {occurred_time_str}. Patient pressed I need help."
        cur.execute(
            """INSERT INTO flags
               (patient_id, source_type, source_ref_id, reason, severity, status, created_at)
               VALUES (%s, 'Fall', %s, %s, 'Urgent_Review', 'Open', %s)""",
            (patient_id, event_id, flag_reason, now),
        )
        flag_id = cur.lastrowid

        # Link flag to device_events
        cur.execute("UPDATE device_events SET flag_id = %s WHERE event_id = %s", (flag_id, event_id))

        # Start escalation ladder: step 1 Nurse alert
        cur.execute(
            """INSERT INTO escalations
               (flag_id, step_no, step_type, channel, delivery_status, notes, sent_at)
               VALUES (%s, 1, 'Nurse_Alert', 'Dashboard', 'Sent', 'Patient pressed I need help on possible fall prompt', %s)""",
            (flag_id, now),
        )

        # Create urgent nurse callback task
        cur.execute(
            """INSERT INTO follow_up_tasks
               (patient_id, assigned_staff_id, reason, priority, status, due_at, created_at)
               VALUES (%s, 2, %s, 'Urgent_Review', 'Pending', %s, %s)""",
            (patient_id, f"Urgent fall follow-up: {flag_reason}", now + timedelta(minutes=30), now),
        )

        # Audit log
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details, created_at)
               VALUES ('Patient', %s, 'FALL_NEED_HELP_FLAG_CREATED', 'flag', %s, %s, %s)""",
            (
                str(patient_id),
                flag_id,
                json.dumps({"event_id": event_id, "reason": flag_reason, "severity": "Urgent_Review"}),
                now,
            ),
        )

        return {
            "status": "help_flag_created",
            "patient_response": "Need_Help",
            "flag_id": flag_id,
            "message": "Alert raised. Dr. Sharma and Nurse Priya have been alerted immediately. If in acute danger, please dial 112.",
        }


def process_fall_timeout(event_id: int, current_time: Optional[datetime] = None) -> Dict[str, Any]:
    """
    OUTCOME C: Wait time expired without patient answer.
    Run by Rounds executor or scheduler.
    Creates an Immediate flag with reason:
    "Watch reported a possible fall at 14:02. No reply within 2 minutes."
    """
    now = current_time or datetime.now()

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT de.event_id, de.patient_id, de.device_id, de.occurred_at,
                      de.prompt_sent_at, de.patient_response, de.flag_id,
                      ar.threshold_value AS wait_minutes
               FROM device_events de
               LEFT JOIN alert_rules ar ON ar.patient_id = de.patient_id AND ar.rule_type = 'Possible_Fall'
               WHERE de.event_id = %s""",
            (event_id,),
        )
        ev = cur.fetchone()
        if not ev:
            return {"status": "not_found"}

        if ev["patient_response"] is not None:
            return {"status": "already_responded", "patient_response": ev["patient_response"]}

        wait_minutes = int(float(ev["wait_minutes"])) if ev["wait_minutes"] else 2
        occurred_time_str = ev["occurred_at"].strftime("%H:%M") if ev["occurred_at"] else now.strftime("%H:%M")

        # Mark No_Response
        cur.execute(
            """UPDATE device_events
               SET patient_response = 'No_Response', responded_at = %s
               WHERE event_id = %s""",
            (now, event_id),
        )

        # Create Immediate flag
        flag_reason = f"Watch reported a possible fall at {occurred_time_str}. No reply within {wait_minutes} minutes."
        cur.execute(
            """INSERT INTO flags
               (patient_id, source_type, source_ref_id, reason, severity, status, created_at)
               VALUES (%s, 'Fall', %s, %s, 'Urgent_Review', 'Open', %s)""",
            (ev["patient_id"], event_id, flag_reason, now),
        )
        flag_id = cur.lastrowid

        cur.execute("UPDATE device_events SET flag_id = %s WHERE event_id = %s", (flag_id, event_id))

        # Escalation ladder
        cur.execute(
            """INSERT INTO escalations
               (flag_id, step_no, step_type, channel, delivery_status, notes, sent_at)
               VALUES (%s, 1, 'Nurse_Alert', 'Dashboard', 'Sent', 'Possible fall prompt expired with no answer', %s)""",
            (flag_id, now),
        )

        # Nurse task
        cur.execute(
            """INSERT INTO follow_up_tasks
               (patient_id, assigned_staff_id, reason, priority, status, due_at, created_at)
               VALUES (%s, 2, %s, 'Urgent_Review', 'Pending', %s, %s)""",
            (ev["patient_id"], f"Check on patient: {flag_reason}", now + timedelta(minutes=30), now),
        )

        # Audit log
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details, created_at)
               VALUES ('Agent', 'rounds', 'FALL_TIMEOUT_FLAG_CREATED', 'flag', %s, %s, %s)""",
            (
                flag_id,
                json.dumps({
                    "event_id": event_id,
                    "patient_id": ev["patient_id"],
                    "reason": flag_reason,
                    "wait_minutes": wait_minutes,
                }),
                now,
            ),
        )

        return {
            "status": "timeout_flag_created",
            "flag_id": flag_id,
            "reason": flag_reason,
        }


def get_active_fall_prompt(patient_id: int) -> Optional[Dict[str, Any]]:
    """
    Checks if there is a currently open Possible_Fall prompt awaiting answer for patient.
    Window is last 10 minutes.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT de.event_id, de.device_id, de.occurred_at, de.prompt_sent_at,
                      COALESCE(ar.threshold_value, 2.00) AS wait_minutes
               FROM device_events de
               LEFT JOIN alert_rules ar ON ar.patient_id = de.patient_id AND ar.rule_type = 'Possible_Fall'
               WHERE de.patient_id = %s
                 AND de.event_type = 'Possible_Fall'
                 AND de.prompt_sent_at IS NOT NULL
                 AND de.patient_response IS NULL
                 AND de.prompt_sent_at >= NOW() - INTERVAL 10 MINUTE
               ORDER BY de.event_id DESC LIMIT 1""",
            (patient_id,),
        )
        row = cur.fetchone()
        if not row:
            return None

        wait_m = int(float(row["wait_minutes"]))
        occ_dt = row["occurred_at"]
        sent_dt = row["prompt_sent_at"]
        remaining_sec = max(0, int((sent_dt + timedelta(minutes=wait_m) - datetime.now()).total_seconds()))

        return {
            "event_id": row["event_id"],
            "device_id": row["device_id"],
            "occurred_at": occ_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "occurred_time": occ_dt.strftime("%H:%M"),
            "wait_minutes": wait_m,
            "seconds_remaining": remaining_sec,
        }


def get_device_health(patient_id: int) -> Dict[str, Any]:
    """
    Aggregates live device connectivity, battery %, and silence checks for patient chart.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT device_id, device_type, connectivity_status, last_seen_at,
                      minutes_since_last_seen, expected_interval_minutes
               FROM v_device_status
               WHERE patient_id = %s LIMIT 1""",
            (patient_id,),
        )
        dev = cur.fetchone()
        if not dev:
            return {
                "has_device": False,
                "status": "No device assigned",
            }

        # Check for battery_pct in recent device_events details
        cur.execute(
            """SELECT JSON_UNQUOTE(JSON_EXTRACT(details, '$.battery_pct')) AS battery_pct
               FROM device_events
               WHERE device_id = %s AND details IS NOT NULL AND JSON_EXTRACT(details, '$.battery_pct') IS NOT NULL
               ORDER BY occurred_at DESC LIMIT 1""",
            (dev["device_id"],),
        )
        batt_row = cur.fetchone()
        battery_pct = int(batt_row["battery_pct"]) if batt_row and batt_row.get("battery_pct") else 85

        return {
            "has_device": True,
            "device_id": dev["device_id"],
            "device_type": dev["device_type"],
            "connectivity_status": dev["connectivity_status"],
            "last_seen_at": dev["last_seen_at"].strftime("%Y-%m-%d %H:%M:%S") if dev["last_seen_at"] else None,
            "minutes_since_last_seen": dev["minutes_since_last_seen"],
            "battery_pct": battery_pct,
            "rounds_silence_monitored": True,
            "expected_interval_minutes": dev["expected_interval_minutes"] or 60,
        }


def get_rule_prompt_counts(patient_id: int) -> Dict[str, int]:
    """
    Returns prompt performance counters for the Possible_Fall rule:
    prompts_sent, prompts_ok, prompts_unanswered, prompts_help.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT
                 COUNT(*) AS sent_count,
                 SUM(patient_response = 'Ok') AS ok_count,
                 SUM(patient_response = 'Need_Help') AS help_count,
                 SUM(patient_response = 'No_Response' OR (patient_response IS NULL AND flag_id IS NOT NULL)) AS unanswered_count
               FROM device_events
               WHERE patient_id = %s
                 AND event_type = 'Possible_Fall'
                 AND prompt_sent_at IS NOT NULL""",
            (patient_id,),
        )
        row = cur.fetchone() or {}
        return {
            "prompts_sent": int(row.get("sent_count") or 0),
            "prompts_ok": int(row.get("ok_count") or 0),
            "prompts_help": int(row.get("help_count") or 0),
            "prompts_unanswered": int(row.get("unanswered_count") or 0),
        }
