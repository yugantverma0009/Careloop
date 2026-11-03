"""
backend/app/agents/dispatcher.py — CareLoop Agent Dispatcher & Supervisor

The central supervisor coordinating agent execution without any LLM dependencies:
- Enforces Global Pause Switch (Doctor control).
- Enforces Per-Patient Pause (Clinician control).
- Enforces Patient AI Help Opt-Out (Patient control: ai_help_enabled).
- Enforces Daily Token/Call Budgets.
- Resolves Autonomy Level (Suggest, Draft, Auto, Never) and Mode (Shadow vs Live).
- Dispatches events to appropriate agents and logs executions via AgentLedger.
"""

import json
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

from backend.app.db import get_conn
from backend.app.agents.ledger import AgentLedger
from backend.app.agents.policy_guard import PolicyGuard, PolicyGuardResult

import os
logger = logging.getLogger(__name__)

# Daily budget: max LLM calls per patient per day (configurable for evaluation)
MAX_DAILY_LLM_CALLS_PER_PATIENT = int(os.getenv("MAX_DAILY_LLM_CALLS", "500"))


class DispatcherDecision:
    def __init__(
        self,
        allowed: bool,
        reason: Optional[str] = None,
        autonomy_level: str = "Suggest",
        mode: str = "Shadow",
        degraded: bool = False
    ):
        self.allowed = allowed
        self.reason = reason
        self.autonomy_level = autonomy_level
        self.mode = mode
        self.degraded = degraded

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "autonomy_level": self.autonomy_level,
            "mode": self.mode,
            "degraded": self.degraded
        }


class AgentDispatcher:
    @staticmethod
    def is_global_paused() -> bool:
        """Returns True if the doctor has engaged the global pause switch."""
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT state_val FROM agent_system_state WHERE state_key = 'pause_all_agents';")
                row = cur.fetchone()
                if row and str(row.get("state_val", "")).lower() in ("true", "1", "yes", "paused"):
                    return True
        return False

    @staticmethod
    def set_global_pause(paused: bool, staff_id: int) -> bool:
        """Toggles the global pause switch (Doctor only)."""
        val_str = "true" if paused else "false"
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO agent_system_state (state_key, state_val, updated_by_staff_id, updated_at)
                    VALUES ('pause_all_agents', %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE state_val = VALUES(state_val), updated_by_staff_id = VALUES(updated_by_staff_id);
                """, (val_str, staff_id))
            conn.commit()
        logger.info(f"Global agent pause set to {val_str} by staff #{staff_id}")
        return paused

    @staticmethod
    def get_autonomy(action_type: str) -> Tuple[str, str]:
        """Returns (level, mode) for a given action type from agent_autonomy."""
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT level, mode FROM agent_autonomy WHERE action_type = %s;
                """, (action_type,))
                row = cur.fetchone()
                if row:
                    return row["level"], row["mode"]
        # Safe default
        return "Suggest", "Shadow"

    @staticmethod
    def set_autonomy(action_type: str, level: str, mode: str, staff_id: int) -> None:
        """Updates autonomy level and mode for an action type (Doctor only)."""
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO agent_autonomy (action_type, level, mode, set_by_staff_id, set_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE level = VALUES(level), mode = VALUES(mode), set_by_staff_id = VALUES(set_by_staff_id);
                """, (action_type, level, mode, staff_id))
            conn.commit()

    @staticmethod
    def check_intake(
        action_type: str,
        patient_id: Optional[int] = None
    ) -> DispatcherDecision:
        """
        Evaluates whether an agent action is permitted under current policies:
        1. Global pause switch.
        2. Patient AI help opt-out (ai_help_enabled).
        3. Per-patient pause (rounds_paused_until).
        4. Autonomy lookup.
        5. Daily budget.
        """
        # 1. Global Pause
        if AgentDispatcher.is_global_paused():
            return DispatcherDecision(
                allowed=False,
                reason="All agents globally paused by clinician switch",
                degraded=True
            )

        if patient_id is not None:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT ai_help_enabled, rounds_paused_until, preferred_language
                        FROM patients
                        WHERE patient_id = %s;
                    """, (patient_id,))
                    p = cur.fetchone()
                    if p:
                        # 2. Patient Opt-Out
                        if p.get("ai_help_enabled") == 0:
                            return DispatcherDecision(
                                allowed=False,
                                reason="Patient has opted out of automated AI help (human-only mode active)",
                                degraded=True
                            )
                        # 3. Patient Specific Pause
                        paused_until = p.get("rounds_paused_until")
                        if paused_until and paused_until > datetime.now():
                            return DispatcherDecision(
                                allowed=False,
                                reason=f"Automated workflows paused for this patient until {paused_until}",
                                degraded=True
                            )

                    # 4. Daily budget check
                    cur.execute("""
                        SELECT COALESCE(SUM(llm_calls), 0) as total_calls
                        FROM agent_runs
                        WHERE patient_id = %s AND started_at >= CURDATE();
                    """, (patient_id,))
                    calls_row = cur.fetchone()
                    total_calls = calls_row["total_calls"] if calls_row else 0
                    if total_calls >= MAX_DAILY_LLM_CALLS_PER_PATIENT:
                        return DispatcherDecision(
                            allowed=False,
                            reason=f"Patient daily LLM budget reached ({total_calls}/{MAX_DAILY_LLM_CALLS_PER_PATIENT})",
                            degraded=True
                        )

        # 5. Autonomy Level & Mode
        level, mode = AgentDispatcher.get_autonomy(action_type)
        if level == "Never":
            return DispatcherDecision(
                allowed=False,
                reason=f"Action '{action_type}' is prohibited by safety policy (autonomy level Never)",
                autonomy_level=level,
                mode=mode
            )

        return DispatcherDecision(
            allowed=True,
            reason=None,
            autonomy_level=level,
            mode=mode,
            degraded=False
        )

    @staticmethod
    def record_shadow_decision(
        run_id: str,
        action_type: str,
        agent_decision: Dict[str, Any],
        human_decision: Optional[Dict[str, Any]] = None,
        agreed: Optional[bool] = None
    ) -> int:
        """Records a shadow decision comparing agent recommendation vs actual human action."""
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO shadow_decisions (
                        run_id, action_type, agent_decision, human_decision, agreed, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, NOW()
                    );
                """, (
                    run_id, action_type,
                    json.dumps(agent_decision),
                    json.dumps(human_decision) if human_decision else None,
                    agreed
                ))
                shadow_id = cur.lastrowid
            conn.commit()
            return shadow_id
