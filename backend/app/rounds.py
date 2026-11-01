"""
backend/app/rounds.py — CareLoop Rounds Engine & Visible Scheduler

Implements Feature F1 (Rounds):
- "Automate the routine. Propose the rest. Humans decide."
- Idempotent executor with dedupe_key uniqueness.
- Governed strictly by automation_policy.can_send(patient, action).
- Transparent 24-hour lookahead and 24-hour history grouped by patient.
- Patient pause with explicit clinical reason and end time.
- Proposals queue (Suggested by Rounds) requiring clinician Accept/Dismiss.
- Every automated dispatch logs an immutable audit row with an explicit reason.
"""

import os
import json
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple

from .db import get_conn
from .automation_policy import can_send
from .escalation import send_sms

logger = logging.getLogger(__name__)


def generate_routine_scheduled_actions(target_date: Optional[date] = None) -> int:
    """
    Populates scheduled_actions for the given date (default today).
    Idempotent via unique dedupe_key (INSERT IGNORE).
    Returns count of new rows inserted.
    """
    t_date = target_date or datetime.now().date()
    inserted_count = 0

    with get_conn() as conn, conn.cursor() as cur:
        # 1. Dose reminders for unconfirmed doses today
        # - 10 min before scheduled dose
        # - 30 min after scheduled dose (if unconfirmed)
        cur.execute(
            """SELECT ml.medication_log_id, ml.prescription_id, pr.patient_id,
                      m.medicine_name, ml.scheduled_for, p.phone, p.preferred_language,
                      p.consent_status, p.rounds_paused_until, p.sms_opt_out
               FROM medication_logs ml
               JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
               JOIN medicines m ON m.medicine_id = pr.medicine_id
               JOIN patients p ON p.patient_id = pr.patient_id
               WHERE DATE(ml.scheduled_for) = %s
                 AND ml.status = 'Unconfirmed'""",
            (t_date,),
        )
        dose_rows = cur.fetchall() or []

        for r in dose_rows:
            log_id = r["medication_log_id"]
            pid = r["patient_id"]
            m_name = r["medicine_name"]
            sched_dt = r["scheduled_for"]
            if isinstance(sched_dt, str):
                sched_dt = datetime.fromisoformat(sched_dt)

            sched_time_str = sched_dt.strftime("%H:%M")

            # A. Pre-dose reminder (10 min before)
            pre_run = sched_dt - timedelta(minutes=10)
            pre_key = f"reminder:{log_id}:pre:{sched_dt.strftime('%Y%m%d%H%M')}"
            pre_reason = f"Dose reminder: {m_name} scheduled for {sched_time_str}"
            pre_payload = json.dumps({
                "medication_log_id": log_id,
                "medicine_name": m_name,
                "scheduled_for": str(sched_dt),
                "reminder_type": "pre_dose",
            })

            cur.execute(
                """INSERT IGNORE INTO scheduled_actions
                   (patient_id, action_type, channel, run_at, status, reason, payload, dedupe_key)
                   VALUES (%s, 'Dose_Reminder', 'SMS', %s, 'Scheduled', %s, %s, %s)""",
                (pid, pre_run, pre_reason, pre_payload, pre_key),
            )
            if cur.rowcount > 0:
                inserted_count += 1

            # B. Post-dose follow-up reminder (30 min after)
            post_run = sched_dt + timedelta(minutes=30)
            post_key = f"reminder:{log_id}:post:{sched_dt.strftime('%Y%m%d%H%M')}"
            post_reason = f"Follow-up reminder: {m_name} was due at {sched_time_str} and is unconfirmed"
            post_payload = json.dumps({
                "medication_log_id": log_id,
                "medicine_name": m_name,
                "scheduled_for": str(sched_dt),
                "reminder_type": "post_dose",
            })

            cur.execute(
                """INSERT IGNORE INTO scheduled_actions
                   (patient_id, action_type, channel, run_at, status, reason, payload, dedupe_key)
                   VALUES (%s, 'Dose_Reminder', 'SMS', %s, 'Scheduled', %s, %s, %s)""",
                (pid, post_run, post_reason, post_payload, post_key),
            )
            if cur.rowcount > 0:
                inserted_count += 1

        # 2. Daily morning check-in prompt for all active patients (09:30 AM)
        cur.execute("SELECT patient_id, full_name FROM patients WHERE consent_status = 'Granted'")
        patients = cur.fetchall() or []

        prompt_time = datetime.combine(t_date, datetime.min.time()) + timedelta(hours=9, minutes=30)
        for p in patients:
            pid = p["patient_id"]
            chk_key = f"checkin_prompt:{pid}:{t_date.isoformat()}"
            chk_reason = "Scheduled daily post-discharge recovery check-in prompt"
            chk_payload = json.dumps({"patient_id": pid, "prompt_date": str(t_date)})

            cur.execute(
                """INSERT IGNORE INTO scheduled_actions
                   (patient_id, action_type, channel, run_at, status, reason, payload, dedupe_key)
                   VALUES (%s, 'Checkin_Prompt', 'App', %s, 'Scheduled', %s, %s, %s)""",
                (pid, prompt_time, chk_reason, chk_payload, chk_key),
            )
            if cur.rowcount > 0:
                inserted_count += 1

        conn.commit()

    return inserted_count


def tick_rounds(now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Executes all scheduled actions currently due (run_at <= now and status = 'Scheduled').
    Idempotent and safe: honors can_send policy, updates status, and logs audit rows.
    """
    current_time = now or datetime.now()
    executed_count = 0
    skipped_count = 0
    failed_count = 0

    with get_conn() as conn, conn.cursor() as cur:
        # Fetch actions due for execution
        cur.execute(
            """SELECT sa.action_id, sa.patient_id, sa.action_type, sa.channel,
                      sa.run_at, sa.reason, sa.payload, sa.attempts, sa.dedupe_key,
                      p.full_name, p.phone, p.preferred_language, p.rounds_paused_until,
                      p.rounds_pause_reason, p.sms_opt_out, p.consent_status
               FROM scheduled_actions sa
               JOIN patients p ON p.patient_id = sa.patient_id
               WHERE sa.status = 'Scheduled'
                 AND sa.run_at <= %s
               ORDER BY sa.run_at ASC
               LIMIT 50""",
            (current_time,),
        )
        due_actions = cur.fetchall() or []

        for act in due_actions:
            action_id = act["action_id"]
            pid = act["patient_id"]
            action_type = act["action_type"]
            channel = act["channel"]
            reason = act["reason"]
            attempts = act["attempts"]
            payload = {}
            if act["payload"]:
                try:
                    payload = json.loads(act["payload"]) if isinstance(act["payload"], str) else act["payload"]
                except Exception:
                    payload = {}

            # Check open emergency flag
            cur.execute(
                """SELECT 1 FROM flags
                   WHERE patient_id = %s AND status = 'Open'
                     AND (severity = 'Urgent_Review' OR source_type = 'Emergency')
                   LIMIT 1""",
                (pid,),
            )
            has_emergency = cur.fetchone() is not None

            # Count daily automated non-dose messages sent today
            cur.execute(
                """SELECT COUNT(*) AS cnt FROM scheduled_actions
                   WHERE patient_id = %s AND status = 'Done'
                     AND action_type NOT IN ('Dose_Reminder')
                     AND DATE(done_at) = DATE(%s)""",
                (pid, current_time),
            )
            daily_cnt_row = cur.fetchone()
            daily_cnt = daily_cnt_row["cnt"] if daily_cnt_row else 0

            # Count reminders already sent for this specific dose
            dose_reminder_count = 0
            if action_type == "Dose_Reminder" and "medication_log_id" in payload:
                cur.execute(
                    """SELECT COUNT(*) AS cnt FROM scheduled_actions
                       WHERE patient_id = %s AND action_type = 'Dose_Reminder'
                         AND status = 'Done'
                         AND JSON_UNQUOTE(JSON_EXTRACT(payload, '$.medication_log_id')) = %s""",
                    (pid, str(payload["medication_log_id"])),
                )
                dc_row = cur.fetchone()
                dose_reminder_count = dc_row["cnt"] if dc_row else 0

            patient_dict = {
                "patient_id": pid,
                "full_name": act["full_name"],
                "rounds_paused_until": act["rounds_paused_until"],
                "rounds_pause_reason": act["rounds_pause_reason"],
                "sms_opt_out": bool(act["sms_opt_out"]),
                "consent_status": act["consent_status"],
            }
            action_dict = {
                "action_type": action_type,
                "channel": channel,
                "reason": reason,
                "attempts": attempts,
                "dose_reminder_count": dose_reminder_count,
            }

            allowed, policy_msg = can_send(
                patient_dict,
                action_dict,
                current_time=current_time,
                daily_message_count=daily_cnt,
                has_open_emergency_flag=has_emergency,
            )

            if not allowed:
                # Mark Skipped with policy reason
                cur.execute(
                    """UPDATE scheduled_actions
                       SET status = 'Skipped', result = %s, done_at = %s
                       WHERE action_id = %s""",
                    (policy_msg, current_time, action_id),
                )
                cur.execute(
                    """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details, created_at)
                       VALUES ('Agent', 'rounds', 'ROUNDS_ACTION_SKIPPED', 'scheduled_action', %s, %s, %s)""",
                    (
                        action_id,
                        json.dumps({
                            "action_type": action_type,
                            "patient_id": pid,
                            "skipped_reason": policy_msg,
                            "original_reason": reason,
                        }),
                        current_time,
                    ),
                )
                skipped_count += 1
                continue

            # Execute action
            try:
                if action_type == "Dose_Reminder":
                    med_log_id = payload.get("medication_log_id")
                    m_name = payload.get("medicine_name", "Prescription medication")
                    if med_log_id:
                        cur.execute(
                            "UPDATE medication_logs SET reminder_sent_at = %s WHERE medication_log_id = %s",
                            (current_time, med_log_id),
                        )
                    if channel == "SMS" and act["phone"]:
                        send_sms(act["phone"], f"CareLoop: Reminder to confirm your dose of {m_name}. Open the app to confirm.")

                    cur.execute(
                        """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details, created_at)
                           VALUES ('Agent', 'rounds', 'SEND_REMINDER', 'medication_log', %s, %s, %s)""",
                        (
                            med_log_id or 0,
                            json.dumps({
                                "channel": channel,
                                "patient_id": pid,
                                "medicine": m_name,
                                "reason": reason,
                            }),
                            current_time,
                        ),
                    )

                elif action_type == "Checkin_Prompt":
                    if channel == "SMS" and act["phone"]:
                        send_sms(act["phone"], "CareLoop: Your daily recovery check-in is due. Reply 1 if doing well, or open the app.")
                    cur.execute(
                        """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details, created_at)
                           VALUES ('Agent', 'rounds', 'CHECKIN_PROMPT_SENT', 'patient', %s, %s, %s)""",
                        (
                            pid,
                            json.dumps({"channel": channel, "reason": reason}),
                            current_time,
                        ),
                    )

                elif action_type == "Welcome_Call_Task":
                    cur.execute(
                        """INSERT INTO follow_up_tasks (patient_id, assigned_staff_id, reason, priority, status, due_at, created_at)
                           VALUES (%s, 2, %s, 'Routine', 'Pending', %s, %s)""",
                        (pid, reason, current_time + timedelta(hours=48), current_time),
                    )
                    cur.execute(
                        """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details, created_at)
                           VALUES ('Agent', 'rounds', 'TASK_CREATED', 'follow_up_task', %s, %s, %s)""",
                        (
                            cur.lastrowid,
                            json.dumps({"reason": reason, "patient_id": pid}),
                            current_time,
                        ),
                    )

                elif action_type in ("Fall_Prompt", "Fall_Prompt_Timeout"):
                    # Delegate timeout processing to device_event_service
                    ev_id = payload.get("event_id")
                    if ev_id:
                        from .device_event_service import process_fall_timeout
                        process_fall_timeout(ev_id, current_time=current_time)

                # Mark Done
                cur.execute(
                    """UPDATE scheduled_actions
                       SET status = 'Done', done_at = %s, result = 'Completed successfully'
                       WHERE action_id = %s""",
                    (current_time, action_id),
                )
                executed_count += 1

            except Exception as e:
                logger.error(f"[Rounds] Error executing action #{action_id}: {e}")
                new_attempts = attempts + 1
                if new_attempts >= 3:
                    cur.execute(
                        """UPDATE scheduled_actions
                           SET status = 'Failed', attempts = %s, result = %s, done_at = %s
                           WHERE action_id = %s""",
                        (new_attempts, str(e), current_time, action_id),
                    )
                    failed_count += 1
                else:
                    cur.execute(
                        """UPDATE scheduled_actions
                           SET attempts = %s, run_at = %s
                           WHERE action_id = %s""",
                        (new_attempts, current_time + timedelta(minutes=5), action_id),
                    )

        conn.commit()

    return {
        "executed": executed_count,
        "skipped": skipped_count,
        "failed": failed_count,
        "timestamp": current_time.isoformat(),
    }


def get_rounds_overview() -> Dict[str, Any]:
    """
    Returns complete Rounds dashboard dataset:
    - upcoming (next 24 hours, grouped by patient)
    - history (last 24 hours: Done, Skipped, Failed)
    - active escalation timers (keeps escalation visible!)
    - summary counters
    - paused patients list
    """
    now = datetime.now()
    next_24h = now + timedelta(hours=24)
    last_24h = now - timedelta(hours=24)

    with get_conn() as conn, conn.cursor() as cur:
        # 1. Upcoming actions (next 24 hours)
        cur.execute(
            """SELECT sa.action_id, sa.patient_id, sa.action_type, sa.channel,
                      sa.run_at, sa.status, sa.reason, sa.dedupe_key,
                      p.full_name AS patient_name, p.patient_code,
                      p.rounds_paused_until, p.rounds_pause_reason
               FROM scheduled_actions sa
               JOIN patients p ON p.patient_id = sa.patient_id
               WHERE sa.run_at BETWEEN %s AND %s
                 AND sa.status = 'Scheduled'
               ORDER BY sa.run_at ASC""",
            (now, next_24h),
        )
        upcoming_rows = cur.fetchall() or []

        # 2. History actions (last 24 hours)
        cur.execute(
            """SELECT sa.action_id, sa.patient_id, sa.action_type, sa.channel,
                      sa.run_at, sa.done_at, sa.status, sa.reason, sa.result,
                      p.full_name AS patient_name, p.patient_code
               FROM scheduled_actions sa
               JOIN patients p ON p.patient_id = sa.patient_id
               WHERE (sa.done_at >= %s OR (sa.run_at >= %s AND sa.status IN ('Done', 'Skipped', 'Failed')))
               ORDER BY COALESCE(sa.done_at, sa.run_at) DESC
               LIMIT 100""",
            (last_24h, last_24h),
        )
        history_rows = cur.fetchall() or []

        # 3. Active Escalation Timers for Open Flags (keeps escalation visible!)
        cur.execute(
            """SELECT f.flag_id, f.patient_id, f.reason, f.severity, f.created_at,
                      p.full_name AS patient_name, p.patient_code,
                      TIMESTAMPDIFF(MINUTE, f.created_at, NOW()) AS age_minutes
               FROM flags f
               JOIN patients p ON p.patient_id = f.patient_id
               WHERE f.status IN ('Open', 'Acknowledged')
               ORDER BY f.created_at DESC""",
        )
        active_flags = cur.fetchall() or []
        escalation_timers = []
        for fl in active_flags:
            age = fl["age_minutes"]
            is_urgent = fl["severity"] == "Urgent_Review"
            # Target timers based on ladder
            target_mins = 15 if is_urgent else 120
            remaining = max(0, target_mins - age)
            escalation_timers.append({
                "flag_id": fl["flag_id"],
                "patient_id": fl["patient_id"],
                "patient_name": fl["patient_name"],
                "patient_code": fl["patient_code"],
                "reason": fl["reason"],
                "severity": fl["severity"],
                "age_minutes": age,
                "target_minutes": target_mins,
                "remaining_minutes": remaining,
                "is_overdue": age > target_mins,
            })

        # 4. Paused patients
        cur.execute(
            """SELECT patient_id, full_name, patient_code, rounds_paused_until, rounds_pause_reason
               FROM patients
               WHERE rounds_paused_until > NOW()"""
        )
        paused_patients = cur.fetchall() or []

        # 5. Counters
        cur.execute(
            """SELECT
                 SUM(CASE WHEN status = 'Scheduled' AND run_at BETWEEN NOW() AND NOW() + INTERVAL 24 HOUR THEN 1 ELSE 0 END) AS upcoming_count,
                 SUM(CASE WHEN status = 'Done' AND (done_at >= NOW() - INTERVAL 24 HOUR OR run_at >= NOW() - INTERVAL 24 HOUR) THEN 1 ELSE 0 END) AS done_count,
                 SUM(CASE WHEN status = 'Skipped' AND (done_at >= NOW() - INTERVAL 24 HOUR OR run_at >= NOW() - INTERVAL 24 HOUR) THEN 1 ELSE 0 END) AS skipped_count,
                 SUM(CASE WHEN status = 'Failed' AND (done_at >= NOW() - INTERVAL 24 HOUR OR run_at >= NOW() - INTERVAL 24 HOUR) THEN 1 ELSE 0 END) AS failed_count
               FROM scheduled_actions"""
        )
        c_row = cur.fetchone() or {}

    # Format dates
    def fmt_item(item):
        d = dict(item)
        if d.get("run_at") and hasattr(d["run_at"], "strftime"):
            d["run_at_str"] = d["run_at"].strftime("%H:%M")
            d["run_at_date"] = d["run_at"].strftime("%d %b")
            d["run_at_iso"] = d["run_at"].isoformat()
        if d.get("done_at") and hasattr(d["done_at"], "strftime"):
            d["done_at_str"] = d["done_at"].strftime("%H:%M")
            d["done_at_date"] = d["done_at"].strftime("%d %b")
            d["done_at_iso"] = d["done_at"].isoformat()
        if d.get("rounds_paused_until") and hasattr(d["rounds_paused_until"], "strftime"):
            d["rounds_paused_until_str"] = d["rounds_paused_until"].strftime("%H:%M (%d %b)")
        return d

    formatted_upcoming = [fmt_item(r) for r in upcoming_rows]
    formatted_history = [fmt_item(r) for r in history_rows]

    # Group upcoming by patient
    upcoming_by_patient = {}
    for item in formatted_upcoming:
        pid = item["patient_id"]
        if pid not in upcoming_by_patient:
            upcoming_by_patient[pid] = {
                "patient_id": pid,
                "patient_name": item["patient_name"],
                "patient_code": item["patient_code"],
                "is_paused": bool(item.get("rounds_paused_until")),
                "pause_reason": item.get("rounds_pause_reason"),
                "paused_until": item.get("rounds_paused_until_str"),
                "actions": [],
            }
        upcoming_by_patient[pid]["actions"].append(item)

    return {
        "counters": {
            "upcoming": int(c_row.get("upcoming_count") or len(formatted_upcoming)),
            "done_24h": int(c_row.get("done_count") or 0),
            "skipped_24h": int(c_row.get("skipped_count") or 0),
            "failed_24h": int(c_row.get("failed_count") or 0),
            "paused_patients": len(paused_patients),
        },
        "upcoming_by_patient": list(upcoming_by_patient.values()),
        "upcoming_list": formatted_upcoming,
        "history_list": formatted_history,
        "escalation_timers": escalation_timers,
        "paused_patients": paused_patients,
        "timestamp": now.isoformat(),
    }


def pause_patient_rounds(patient_id: int, staff_id: int, staff_role: str, hours: int, reason: str) -> Dict[str, Any]:
    """Pauses scheduled rounds for a specific patient."""
    now = datetime.now()
    paused_until = now + timedelta(hours=hours)
    clean_reason = (reason or "Clinician temporary hold").strip()

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE patients
               SET rounds_paused_until = %s, rounds_pause_reason = %s
               WHERE patient_id = %s""",
            (paused_until, clean_reason, patient_id),
        )
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details, created_at)
               VALUES ('Staff', %s, 'ROUNDS_PAUSED', 'patient', %s, %s, %s)""",
            (
                str(staff_id),
                patient_id,
                json.dumps({
                    "staff_role": staff_role,
                    "paused_hours": hours,
                    "paused_until": str(paused_until),
                    "reason": clean_reason,
                }),
                now,
            ),
        )
        conn.commit()

    return {
        "status": "paused",
        "patient_id": patient_id,
        "paused_until": paused_until.strftime("%H:%M (%d %b)"),
        "reason": clean_reason,
    }


def resume_patient_rounds(patient_id: int, staff_id: int, staff_role: str) -> Dict[str, Any]:
    """Resumes scheduled rounds for a patient immediately."""
    now = datetime.now()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE patients
               SET rounds_paused_until = NULL, rounds_pause_reason = NULL
               WHERE patient_id = %s""",
            (patient_id,),
        )
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details, created_at)
               VALUES ('Staff', %s, 'ROUNDS_RESUMED', 'patient', %s, %s, %s)""",
            (
                str(staff_id),
                patient_id,
                json.dumps({"staff_role": staff_role}),
                now,
            ),
        )
        conn.commit()

    return {"status": "resumed", "patient_id": patient_id}


def get_patient_agent_activity(patient_id: int, limit: int = 40) -> List[Dict[str, Any]]:
    """Returns chronologically ordered activity feed of automation actions for a patient chart."""
    with get_conn() as conn, conn.cursor() as cur:
        # Combine scheduled_actions and agent audit events
        cur.execute(
            """SELECT sa.action_id, sa.action_type, sa.channel, sa.run_at, sa.done_at,
                      sa.status, sa.reason, sa.result
               FROM scheduled_actions sa
               WHERE sa.patient_id = %s
               ORDER BY COALESCE(sa.done_at, sa.run_at) DESC
               LIMIT %s""",
            (patient_id, limit),
        )
        actions = cur.fetchall() or []

    results = []
    for a in actions:
        t = a.get("done_at") or a.get("run_at")
        time_str = t.strftime("%H:%M") if hasattr(t, "strftime") else ""
        date_str = t.strftime("%d %b") if hasattr(t, "strftime") else ""

        results.append({
            "id": f"act-{a['action_id']}",
            "type": a["action_type"],
            "channel": a["channel"],
            "status": a["status"],
            "time_str": time_str,
            "date_str": date_str,
            "timestamp": t.isoformat() if hasattr(t, "isoformat") else str(t),
            "reason": a["reason"],
            "result": a.get("result") or a["status"],
        })

    return results


def get_agent_proposals(status: str = "Pending") -> List[Dict[str, Any]]:
    """Returns proposals generated by Rounds for nurse review."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT ap.proposal_id, ap.patient_id, ap.agent_name, ap.proposal_type,
                      ap.reason, ap.evidence, ap.status, ap.created_at,
                      p.full_name AS patient_name, p.patient_code,
                      TIMESTAMPDIFF(HOUR, ap.created_at, NOW()) AS age_hours
               FROM agent_proposals ap
               JOIN patients p ON p.patient_id = ap.patient_id
               WHERE ap.status = %s
               ORDER BY ap.created_at DESC""",
            (status,),
        )
        rows = cur.fetchall() or []

    proposals = []
    for r in rows:
        evidence = {}
        if r.get("evidence"):
            try:
                evidence = json.loads(r["evidence"]) if isinstance(r["evidence"], str) else r["evidence"]
            except Exception:
                evidence = {}

        proposals.append({
            "proposal_id": r["proposal_id"],
            "patient_id": r["patient_id"],
            "patient_name": r["patient_name"],
            "patient_code": r["patient_code"],
            "agent_name": r["agent_name"],
            "proposal_type": r["proposal_type"],
            "title": f"Suggested: {r['reason']}",
            "reason": r["reason"],
            "evidence": evidence,
            "status": r["status"],
            "created_at": r["created_at"].strftime("%d %b, %H:%M") if hasattr(r["created_at"], "strftime") else str(r["created_at"]),
        })

    return proposals


def accept_proposal(proposal_id: int, staff_id: int, staff_role: str) -> Dict[str, Any]:
    """Nurse accepts a proposal; automatically converts it into a clinical task."""
    now = datetime.now()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT proposal_id, patient_id, proposal_type, reason FROM agent_proposals WHERE proposal_id = %s",
            (proposal_id,),
        )
        prop = cur.fetchone()
        if not prop:
            raise ValueError("Proposal not found")

        # Create corresponding task in follow_up_tasks
        task_reason = f"Nurse accepted Rounds suggestion: {prop['reason']}"
        cur.execute(
            """INSERT INTO follow_up_tasks (patient_id, assigned_staff_id, reason, priority, status, due_at, created_at)
               VALUES (%s, %s, %s, 'Review_Soon', 'Pending', %s, %s)""",
            (prop["patient_id"], staff_id, task_reason, now + timedelta(hours=4), now),
        )
        task_id = cur.lastrowid

        # Mark proposal accepted
        cur.execute(
            """UPDATE agent_proposals
               SET status = 'Accepted', decided_by_staff_id = %s, decided_at = %s
               WHERE proposal_id = %s""",
            (staff_id, now, proposal_id),
        )

        # Audit log
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details, created_at)
               VALUES ('Staff', %s, 'PROPOSAL_ACCEPTED', 'agent_proposal', %s, %s, %s)""",
            (
                str(staff_id),
                proposal_id,
                json.dumps({"task_id": task_id, "staff_role": staff_role, "reason": prop["reason"]}),
                now,
            ),
        )
        conn.commit()

    return {"status": "accepted", "proposal_id": proposal_id, "task_id": task_id}


def dismiss_proposal(proposal_id: int, staff_id: int, staff_role: str, dismiss_reason: str) -> Dict[str, Any]:
    """Nurse dismisses a proposal with a required reason."""
    now = datetime.now()
    clean_reason = (dismiss_reason or "").strip()
    if not clean_reason:
        raise ValueError("A dismissal reason is required.")

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE agent_proposals
               SET status = 'Dismissed', decided_by_staff_id = %s, decided_at = %s, dismiss_reason = %s
               WHERE proposal_id = %s""",
            (staff_id, now, clean_reason, proposal_id),
        )
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details, created_at)
               VALUES ('Staff', %s, 'PROPOSAL_DISMISSED', 'agent_proposal', %s, %s, %s)""",
            (
                str(staff_id),
                proposal_id,
                json.dumps({"staff_role": staff_role, "dismiss_reason": clean_reason}),
                now,
            ),
        )
        conn.commit()

    return {"status": "dismissed", "proposal_id": proposal_id, "reason": clean_reason}
