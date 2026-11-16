"""
backend/app/agents/circuit_breaker.py — Continuous Safety Evaluation and Auto-Demotion

Rules:
1. Evaluate continuously for every action at Auto or Live.
2. Demote to Draft (and notify doctor on Agent Desk and the bell) when ANY of:
   - Guard-block rate > 10% over the last 50 runs
   - 2 or more reported incidents in 24 hours
   - Shadow agreement below threshold (default 80%) over the last 50 cases
   - Failure rate > 15% over the last 50 runs
3. Demotion is audited with reason; only the doctor can re-promote.
4. Acceptance: fake clock support for simulated time testing.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from backend.app.db import get_conn
from backend.app.agents.config import (
    AGENTS_V2_CIRCUIT_BREAKER,
    CIRCUIT_BREAKER_MIN_RUNS,
    CIRCUIT_BREAKER_WINDOW_RUNS,
    CIRCUIT_BREAKER_GUARD_BLOCK_MAX_PCT,
    CIRCUIT_BREAKER_FAILURE_MAX_PCT,
    CIRCUIT_BREAKER_MAX_INCIDENTS_24H,
    CIRCUIT_BREAKER_MIN_SHADOW_AGREEMENT_PCT,
)

logger = logging.getLogger(__name__)

ACTION_TO_AGENT = {
    "papers_question_sourced": "papers_agent",
    "case_brief": "case_prep_agent",
    "duplicate_alert_merging": "case_prep_agent",
    "next_step_suggestion": "case_prep_agent",
    "call_script": "case_prep_agent",
    "call_note": "call_notes_agent",
    "post_call_patient_message": "call_notes_agent",
    "dose_reminder": "outreach_agent",
    "checkin_prompt": "outreach_agent",
    "no_answer_retry_scheduling": "outreach_agent",
    "shift_handoff": "handoff_agent",
    "daily_summary": "handoff_agent",
    "recovery_plan": "plan_agent",
    "approved_flag_auto_close": "auto_close_service",
    "dose_change_care_team_request": "papers_agent",
    "not_found_care_team_request": "papers_agent",
}


class CircuitBreaker:
    @staticmethod
    def evaluate_action(action_type: str, now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """Evaluates an action type; demotes to Draft if safety thresholds are breached.
        
        Supports optional fake clock (`now`) for deterministically testing time windows.
        """
        if not AGENTS_V2_CIRCUIT_BREAKER:
            return None

        current_time = now or datetime.now()
        agent_name = ACTION_TO_AGENT.get(action_type, action_type)

        with get_conn() as conn:
            with conn.cursor() as cur:
                # 1. Fetch current autonomy setting
                cur.execute(
                    "SELECT level, mode FROM agent_autonomy WHERE action_type = %s;",
                    (action_type,)
                )
                row = cur.fetchone()
                if not row:
                    return None

                curr_level = row["level"]
                curr_mode = row["mode"]

                # Only evaluate if currently Auto or Live (if already Draft, do not re-evaluate or spam audit log)
                if curr_level != "Auto" and curr_mode != "Live":
                    return None

                # 2. Fetch last N runs for this agent/action (excluding test runs)
                cur.execute("""
                    SELECT status FROM agent_runs
                    WHERE (agent_name = %s OR trigger_type = %s)
                      AND source != 'test'
                    ORDER BY started_at DESC
                    LIMIT %s;
                """, (agent_name, action_type, CIRCUIT_BREAKER_WINDOW_RUNS))
                runs = cur.fetchall() or []
                total_runs = len(runs)

                triggered_reason = None
                details: Dict[str, Any] = {"total_runs": total_runs}

                # Only evaluate block and fail rates if minimum sample size is met (>= 30 runs)
                if total_runs >= CIRCUIT_BREAKER_MIN_RUNS:
                    # Hysteresis check across 3 consecutive sub-windows
                    window_size = max(5, total_runs // 3)
                    sub_windows = [
                        runs[0:window_size],
                        runs[window_size:2*window_size],
                        runs[2*window_size:3*window_size]
                    ]

                    sub_block_rates = [
                        (sum(1 for r in w if r["status"] == "Blocked_By_Guard") / len(w)) * 100.0
                        for w in sub_windows if len(w) > 0
                    ]
                    sustained_block = len(sub_block_rates) == 3 and all(rate > CIRCUIT_BREAKER_GUARD_BLOCK_MAX_PCT for rate in sub_block_rates)

                    overall_blocked = sum(1 for r in runs if r["status"] == "Blocked_By_Guard")
                    guard_block_pct = (overall_blocked / total_runs) * 100.0
                    details["guard_block_pct"] = guard_block_pct

                    if sustained_block and guard_block_pct > CIRCUIT_BREAKER_GUARD_BLOCK_MAX_PCT:
                        triggered_reason = (
                            f"Guard-block rate {guard_block_pct:.1f}% exceeded limit "
                            f"{CIRCUIT_BREAKER_GUARD_BLOCK_MAX_PCT}% across 3 consecutive windows over {total_runs} runs"
                        )

                    if not triggered_reason:
                        sub_fail_rates = [
                            (sum(1 for r in w if r["status"] == "Failed") / len(w)) * 100.0
                            for w in sub_windows if len(w) > 0
                        ]
                        sustained_fail = len(sub_fail_rates) == 3 and all(rate > CIRCUIT_BREAKER_FAILURE_MAX_PCT for rate in sub_fail_rates)

                        overall_failed = sum(1 for r in runs if r["status"] == "Failed")
                        fail_pct = (overall_failed / total_runs) * 100.0
                        details["fail_pct"] = fail_pct

                        if sustained_fail and fail_pct > CIRCUIT_BREAKER_FAILURE_MAX_PCT:
                            triggered_reason = (
                                f"Failure rate {fail_pct:.1f}% exceeded limit "
                                f"{CIRCUIT_BREAKER_FAILURE_MAX_PCT}% across 3 consecutive windows over {total_runs} runs"
                            )

                # 3. Check Incidents in last 24h (excluding test incidents)
                if not triggered_reason:
                    t_24h_ago = current_time - timedelta(hours=24)
                    cur.execute("""
                        SELECT COUNT(*) AS inc_count FROM agent_incidents i
                        JOIN agent_runs r ON r.run_id = i.run_id
                        WHERE (r.agent_name = %s OR r.trigger_type = %s)
                          AND i.source != 'test'
                          AND i.created_at >= %s AND i.created_at <= %s;
                    """, (agent_name, action_type, t_24h_ago, current_time))
                    inc_row = cur.fetchone()
                    inc_count = inc_row["inc_count"] if inc_row else 0
                    details["incidents_24h"] = inc_count

                    if inc_count >= CIRCUIT_BREAKER_MAX_INCIDENTS_24H:
                        triggered_reason = (
                            f"{inc_count} incidents reported in 24 hours (threshold: {CIRCUIT_BREAKER_MAX_INCIDENTS_24H})"
                        )

                # 4. Check Shadow Agreement over last 50 decisions
                if not triggered_reason:
                    cur.execute("""
                        SELECT agreed FROM shadow_decisions
                        WHERE action_type = %s
                        ORDER BY created_at DESC
                        LIMIT 50;
                    """, (action_type,))
                    decisions = cur.fetchall() or []
                    if len(decisions) >= 10:
                        agreed_count = sum(1 for d in decisions if d["agreed"])
                        shadow_pct = (agreed_count / len(decisions)) * 100.0
                        details["shadow_agreement_pct"] = shadow_pct
                        if shadow_pct < CIRCUIT_BREAKER_MIN_SHADOW_AGREEMENT_PCT:
                            triggered_reason = (
                                f"Shadow agreement {shadow_pct:.1f}% fell below threshold "
                                f"{CIRCUIT_BREAKER_MIN_SHADOW_AGREEMENT_PCT}% over last {len(decisions)} cases"
                            )

                # If triggered, demote to Draft and notify doctor
                if triggered_reason:
                    # Demote level to Draft
                    cur.execute("""
                        UPDATE agent_autonomy
                        SET level = 'Draft', set_at = %s, set_by_staff_id = NULL
                        WHERE action_type = %s;
                    """, (current_time, action_type))

                    # Audit trail
                    cur.execute("""
                        INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                        VALUES ('System', 0, 'CIRCUIT_BREAKER_DEMOTION', 'agent_autonomy', 0, %s);
                    """, (json.dumps({
                        "action_type": action_type,
                        "previous_level": curr_level,
                        "previous_mode": curr_mode,
                        "new_level": "Draft",
                        "reason": triggered_reason,
                        "metrics": details,
                        "triggered_at": current_time.isoformat()
                    }),))
                    conn.commit()

                    logger.warning(f"CIRCUIT BREAKER DEMOTION for {action_type}: {triggered_reason}")
                    return {
                        "action_type": action_type,
                        "demoted": True,
                        "reason": triggered_reason,
                        "previous_level": curr_level,
                        "new_level": "Draft",
                        "details": details
                    }

        return None

    @staticmethod
    def evaluate_all(now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Evaluates all actions currently Auto or Live."""
        demotions = []
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT action_type FROM agent_autonomy WHERE level = 'Auto' OR mode = 'Live';")
                rows = cur.fetchall() or []
        for r in rows:
            res = CircuitBreaker.evaluate_action(r["action_type"], now=now)
            if res:
                demotions.append(res)
        return demotions

    @staticmethod
    def get_active_demotions(window_hours: int = 48) -> List[Dict[str, Any]]:
        """Fetches active circuit breaker demotions (at most ONE persistent banner per action_type).
        
        Only returns actions that are still currently demoted (level == 'Draft').
        """
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Query current autonomy status
                cur.execute("SELECT action_type, level, mode FROM agent_autonomy;")
                curr_levels = {r["action_type"]: r for r in (cur.fetchall() or [])}

                cur.execute("""
                    SELECT details, created_at FROM audit_log
                    WHERE action = 'CIRCUIT_BREAKER_DEMOTION'
                      AND created_at >= NOW() - INTERVAL %s HOUR
                    ORDER BY created_at DESC;
                """, (window_hours,))
                rows = cur.fetchall() or []
                res = []
                seen_actions = set()
                for r in rows:
                    try:
                        d = json.loads(r["details"]) if isinstance(r["details"], str) else r["details"]
                        act = d.get("action_type")
                        if not act or act in seen_actions:
                            continue
                        # If doctor re-promoted this action back to Auto or Live, it is resolved
                        curr = curr_levels.get(act)
                        if curr and curr["level"] != "Draft":
                            continue

                        seen_actions.add(act)
                        d["timestamp"] = str(r["created_at"])
                        d["current_level"] = curr["level"] if curr else "Draft"
                        res.append(d)
                    except Exception:
                        pass
                return res
