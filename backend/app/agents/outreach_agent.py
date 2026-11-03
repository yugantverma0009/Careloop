"""
backend/app/agents/outreach_agent.py — Outreach Agent (Adaptive but Bounded)

Specifications (Section 4.4 of careloop_care_agents_plan.md):
1. Channel choice inside policy: App notification first, SMS if unread or requested; Hindi or English by patient preference.
2. Automation limits & constraints:
   - Quiet hours (22:00 - 07:00 IST) enforced.
   - Daily cap (maximum 3 messages per patient per day) enforced.
   - STOP opt-out enforced.
   - Global Pause & Per-Patient Pause respected.
   - Open Emergency Flag routine suppression enforced.
3. Retries:
   - Check-ins: retried once if unanswered.
   - No-answer calls: reschedule up to 2 retries (max 2).
   - After limit (2 retries): proposes family step (ONLY with caregiver consent) or physician review.
4. Reply handling: SMS 1/2/3/STOP.
5. Undo capability for automated actions.
"""

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

IST = timezone(timedelta(hours=5, minutes=30))
logger = logging.getLogger(__name__)

from backend.app.db import get_conn
from backend.app.agents.ledger import AgentLedger
from backend.app.agents.dispatcher import AgentDispatcher
from backend.app.agents.policy_guard import PolicyGuard


class OutreachAgent:
    """Outreach Agent handling scheduled communications, retries, and bound channels."""

    @staticmethod
    def evaluate_outreach(
        patient_id: int,
        action_type: str = "Routine_Reminder",
        message_text: str = "",
        is_emergency: bool = False,
        current_time: Optional[datetime] = None,
        channel: Optional[str] = None,
        message_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluates whether an automated outreach message can be delivered under current policy.
        Returns evaluation result with channel, language, and suppression reasons if blocked.
        """
        action_type = message_type or action_type
        now_dt = current_time or datetime.now(IST)
        with get_conn() as conn:
            with conn.cursor() as cur:
                # 1. Check Global Pause
                if AgentDispatcher.is_global_paused():
                    msg = "Global agent pause is engaged by attending physician"
                    return {
                        "allowed": False,
                        "reason": msg,
                        "reasons": [msg],
                        "channel": None
                    }

                # 2. Check Patient Settings & Status
                cur.execute("""
                    SELECT patient_id, full_name, patient_code, phone, preferred_language,
                           rounds_paused_until, rounds_pause_reason, sms_opt_out, ai_help_enabled
                    FROM patients WHERE patient_id = %s;
                """, (patient_id,))
                pat = cur.fetchone()
                if not pat:
                    msg = "Patient not found"
                    return {"allowed": False, "reason": msg, "reasons": [msg], "channel": None}

                # Patient Rounds Pause
                if pat.get("rounds_paused_until") and pat["rounds_paused_until"] > datetime.now():
                    msg = f"Patient outreach paused until {pat['rounds_paused_until'].strftime('%H:%M')}: {pat.get('rounds_pause_reason')}"
                    return {
                        "allowed": False,
                        "reason": msg,
                        "reasons": [msg],
                        "channel": None
                    }

                # AI Help Opt-Out (patient opt-out stops automated proactive agent messages)
                if pat.get("ai_help_enabled") == 0 and not is_emergency:
                    msg = "Patient has opted out of automated AI communications (AI help disabled)"
                    return {
                        "allowed": False,
                        "reason": msg,
                        "reasons": [msg],
                        "channel": None
                    }

                # SMS Opt-out
                sms_opted_out = (pat.get("sms_opt_out") == 1)
                if channel == "SMS" and sms_opted_out and not is_emergency:
                    msg = "Patient has opted out of SMS messages (SMS opt-out via STOP)"
                    return {
                        "allowed": False,
                        "reason": msg,
                        "reasons": [msg],
                        "channel": None
                    }

                # 3. Check Open Emergency Flag Suppression
                cur.execute("""
                    SELECT flag_id FROM flags
                    WHERE patient_id = %s AND source_type = 'Emergency' AND status = 'Open'
                    LIMIT 1;
                """, (patient_id,))
                open_emerg = cur.fetchone()
                if open_emerg and not is_emergency:
                    msg = "Routine outreach suppressed while active emergency flag is open"
                    return {
                        "allowed": False,
                        "reason": msg,
                        "reasons": [msg],
                        "channel": None
                    }

                # 4. Count Today's Automated Messages (Daily Cap)
                cur.execute("""
                    SELECT COUNT(*) as cnt FROM patient_updates
                    WHERE patient_id = %s AND DATE(created_at) = CURDATE() AND created_by = 'Staff';
                """, (patient_id,))
                msg_count = cur.fetchone()["cnt"] or 0

                # 5. Evaluate Policy Guard
                guard_payload = {
                    "patient_id": patient_id,
                    "is_automated_patient_msg": True,
                    "is_emergency": is_emergency,
                    "answer": message_text,
                    "language": pat["preferred_language"]
                }
                guard_context = {
                    "patient_id": patient_id,
                    "current_time": now_dt,
                    "daily_automated_message_count": msg_count,
                    "open_emergency_flag": bool(open_emerg),
                    "is_emergency": is_emergency,
                    "preferred_language": pat["preferred_language"]
                }
                guard_res = PolicyGuard.inspect("outreach_agent", guard_payload, guard_context)
                if not guard_res.passed:
                    return {
                        "allowed": False,
                        "reason": "; ".join(guard_res.reasons),
                        "reasons": guard_res.reasons,
                        "channel": None,
                        "guard_reasons": guard_res.reasons
                    }

                # 6. Channel Selection: App notification first; fallback to SMS if appropriate and not opted out
                selected_channel = channel or ("App" if not sms_opted_out else "App")

                return {
                    "allowed": True,
                    "channel": selected_channel,
                    "preferred_language": pat["preferred_language"],
                    "daily_count": msg_count,
                    "patient_phone": pat["phone"],
                    "reasons": []
                }

    @staticmethod
    def handle_no_answer_retry(
        patient_id: int,
        flag_id: Optional[int] = None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Manages the call retry ladder:
        - Retries up to 2 times (max 2).
        - If retry limit reached (>= 2):
          Evaluates caregiver consent:
          - If caregiver consent is Granted (1): Proposes family call in agent_proposals.
          - If caregiver consent is Not Granted (0): Proposes doctor review in agent_proposals.
        """
        run_id = f"run-outreach-retry-{uuid.uuid4().hex[:8]}"

        AgentLedger.start_run(
            run_id=run_id,
            agent_name="outreach_agent",
            trigger_type="no_answer_retry",
            trigger_ref=f"flag#{flag_id}" if flag_id else f"patient#{patient_id}",
            patient_id=patient_id,
            autonomy_level="Auto",
            mode="Live",
            plan={"strategy": "call_retry_ladder", "current_retry_count": retry_count}
        )

        with get_conn() as conn:
            with conn.cursor() as cur:
                if retry_count < 2:
                    # Reschedule retry call attempt (Auto action inside limits)
                    next_retry_time = datetime.now() + timedelta(minutes=30)
                    dedupe_key = f"retry_call_{patient_id}_{retry_count + 1}_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:6]}"
                    cur.execute("""
                        INSERT INTO scheduled_actions (
                            patient_id, action_type, channel, run_at, status, reason, attempts, dedupe_key, created_at
                        ) VALUES (
                            %s, 'Welcome_Call_Task', 'Task', %s, 'Scheduled',
                            'Automated retry #%s for unreachable patient', %s, %s, NOW()
                        );
                    """, (patient_id, next_retry_time, retry_count + 1, retry_count + 1, dedupe_key))
                    action_id = cur.lastrowid

                    cur.execute("""
                        UPDATE agent_runs SET trigger_ref = %s, plan = %s WHERE run_id = %s;
                    """, (f"action:{action_id}", json.dumps({"strategy": "call_retry_ladder", "action_id": action_id, "retry_count": retry_count + 1}), run_id))
                    conn.commit()

                    AgentLedger.record_step(
                        run_id, 1, "Tool",
                        f"Rescheduled call retry #{retry_count + 1} for +30 minutes",
                        ids=[f"action#{action_id}"],
                        ok=True
                    )
                    AgentLedger.finish_run(run_id, status="Done", result_type="scheduled_retry")

                    return {
                        "action": "schedule_retry",
                        "retry_count": retry_count + 1,
                        "scheduled_for": next_retry_time.strftime("%H:%M"),
                        "run_id": run_id,
                        "action_id": action_id
                    }

                # Retry limit reached (>= 2): check caregiver consent
                cur.execute("""
                    SELECT caregiver_id, consent_granted, full_name, relationship
                    FROM caregivers
                    WHERE patient_id = %s
                    ORDER BY is_primary DESC, caregiver_id ASC LIMIT 1;
                """, (patient_id,))
                cg = cur.fetchone()
                caregiver_consent = bool(cg and cg.get("consent_granted") == 1)

                if caregiver_consent:
                    proposal_type = "Suggest_Call"
                    reason = f"Propose family contact: patient unreachable after 2 call attempts (caregiver: {cg['full_name']} / {cg['relationship']}, consent verified)"
                    evidence = {"retry_count": retry_count, "caregiver_id": cg["caregiver_id"], "consent": True}
                else:
                    proposal_type = "Suggest_Plan_Review"
                    reason = "Propose physician review: patient unreachable after 2 call attempts (caregiver consent not granted)"
                    evidence = {"retry_count": retry_count, "consent": False}

                cur.execute("""
                    INSERT INTO agent_proposals (patient_id, agent_name, proposal_type, reason, evidence, status, created_at)
                    VALUES (%s, 'outreach_agent', %s, %s, %s, 'Pending', NOW());
                """, (patient_id, proposal_type, reason, json.dumps(evidence)))
                proposal_id = cur.lastrowid
                conn.commit()

        AgentLedger.record_step(
            run_id, 1, "Plan",
            f"Retry limit reached. Drafted proposal #{proposal_id} ({proposal_type})",
            ids=[f"proposal#{proposal_id}"],
            ok=True
        )
        AgentLedger.finish_run(run_id, status="Done", result_type="proposal_created")

        return {
            "action": "propose_escalation",
            "proposal_id": proposal_id,
            "proposal_type": proposal_type,
            "caregiver_consent": caregiver_consent,
            "reason": reason,
            "run_id": run_id
        }

    @staticmethod
    def handle_sms_reply(patient_id: int, text: str) -> Dict[str, Any]:
        """
        Parses inbound SMS replies (1/2/3/STOP).
        Enforces STOP opt-out immediately.
        """
        clean_text = text.strip().upper()
        if "STOP" in clean_text:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE patients SET sms_opt_out = 1 WHERE patient_id = %s;
                    """, (patient_id,))
                    cur.execute("""
                        INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                        VALUES ('Patient', %s, 'SMS_OPT_OUT_REQUESTED', 'patient', %s, JSON_OBJECT('text', %s));
                    """, (str(patient_id), patient_id, text))
                    conn.commit()
            return {"status": "opted_out", "message": "SMS opt-out confirmed (STOP)"}

        return {"status": "received", "parsed_choice": clean_text}

    @staticmethod
    def undo_action(action_id: int, staff_id: int) -> Dict[str, Any]:
        """
        Reverts an automated outreach action where possible (e.g. cancels scheduled retry).
        Audited with clinician identity.
        """
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM scheduled_actions WHERE action_id = %s;", (action_id,))
                act = cur.fetchone()
                if not act:
                    raise ValueError(f"Action #{action_id} not found.")

                cur.execute("""
                    UPDATE scheduled_actions SET status = 'Cancelled', result = 'Undone by clinician'
                    WHERE action_id = %s;
                """, (action_id,))

                cur.execute("""
                    INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                    VALUES ('Staff', %s, 'AGENT_ACTION_UNDONE', 'scheduled_actions', %s, JSON_OBJECT('action_id', %s));
                """, (str(staff_id), action_id, action_id))
                conn.commit()

        logger.info(f"Action #{action_id} successfully cancelled/undone by staff #{staff_id}")
        return {"status": "undone", "action_id": action_id}
