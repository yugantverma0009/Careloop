"""
backend/app/agents/ledger.py — Agent Execution Ledger & Trace Provider

Records every agent run, step, and draft in immutable append-only fashion.
Provides complete execution trace: plan, steps, sources, latency, token costs, and Policy Guard results.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from backend.app.db import get_conn

logger = logging.getLogger(__name__)


class AgentLedger:
    @staticmethod
    def start_run(
        run_id: str,
        agent_name: str,
        trigger_type: str,
        trigger_ref: Optional[str] = None,
        patient_id: Optional[int] = None,
        case_id: Optional[str] = None,
        autonomy_level: str = "Suggest",
        mode: str = "Shadow",
        plan: Optional[Dict[str, Any]] = None
    ) -> None:
        """Records the initialization of an agent run."""
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO agent_runs (
                        run_id, agent_name, trigger_type, trigger_ref, patient_id, case_id,
                        started_at, status, autonomy_level, mode, plan, llm_calls, latency_ms
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, NOW(), 'Done', %s, %s, %s, 0, 0
                    ) ON DUPLICATE KEY UPDATE
                        agent_name = VALUES(agent_name),
                        plan = VALUES(plan);
                """, (
                    run_id, agent_name, trigger_type, trigger_ref, patient_id, case_id,
                    autonomy_level, mode, json.dumps(plan) if plan else None
                ))
            conn.commit()

    @staticmethod
    def record_step(
        run_id: str,
        seq: int,
        step_type: str,
        summary: str,
        ids: Optional[List[Any]] = None,
        ok: bool = True,
        ms: int = 0
    ) -> None:
        """Records an individual execution step within an agent run."""
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO agent_steps (
                        run_id, seq, step_type, summary, ids, ok, ms, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, NOW()
                    );
                """, (
                    run_id, seq, step_type, summary[:255],
                    json.dumps(ids) if ids else None,
                    1 if ok else 0, ms
                ))
            conn.commit()

    @staticmethod
    def finish_run(
        run_id: str,
        status: str = "Done",
        result_type: Optional[str] = None,
        llm_calls: int = 0,
        tokens_in: int = 0,
        tokens_out: int = 0,
        latency_ms: int = 0,
        guard_reasons: Optional[List[str]] = None
    ) -> None:
        """Marks run completion with execution metrics and Policy Guard status."""
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE agent_runs
                    SET finished_at = NOW(),
                        status = %s,
                        result_type = %s,
                        llm_calls = %s,
                        tokens_in = %s,
                        tokens_out = %s,
                        latency_ms = %s,
                        guard_reasons = %s
                    WHERE run_id = %s;
                """, (
                    status, result_type, llm_calls, tokens_in, tokens_out,
                    latency_ms, json.dumps(guard_reasons) if guard_reasons else None,
                    run_id
                ))
            conn.commit()

    @staticmethod
    def save_draft(
        run_id: Optional[str],
        patient_id: int,
        draft_type: str,
        body: Dict[str, Any],
        sources: Optional[List[Any]] = None,
        status: str = "Pending"
    ) -> int:
        """Stores a drafted clinical item for human review."""
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO agent_drafts (
                        run_id, patient_id, draft_type, body, sources, status, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, NOW()
                    );
                """, (
                    run_id, patient_id, draft_type,
                    json.dumps(body), json.dumps(sources) if sources else None,
                    status
                ))
                draft_id = cur.lastrowid
            conn.commit()
            return draft_id

    @staticmethod
    def trace(run_id: str) -> Optional[Dict[str, Any]]:
        """Returns the full execution trace for an agent run."""
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT r.*, p.patient_code, p.full_name as patient_name
                    FROM agent_runs r
                    LEFT JOIN patients p ON p.patient_id = r.patient_id
                    WHERE r.run_id = %s;
                """, (run_id,))
                run_row = cur.fetchone()
                if not run_row:
                    return None

                cur.execute("""
                    SELECT step_id, seq, step_type, summary, ids, ok, ms, created_at
                    FROM agent_steps
                    WHERE run_id = %s
                    ORDER BY seq ASC;
                """, (run_id,))
                steps = cur.fetchall()

                # Parse JSON fields
                if isinstance(run_row.get("plan"), str):
                    try:
                        run_row["plan"] = json.loads(run_row["plan"])
                    except Exception:
                        pass
                if isinstance(run_row.get("guard_reasons"), str):
                    try:
                        run_row["guard_reasons"] = json.loads(run_row["guard_reasons"])
                    except Exception:
                        pass

                for s in steps:
                    if isinstance(s.get("ids"), str):
                        try:
                            s["ids"] = json.loads(s["ids"])
                        except Exception:
                            pass

                return {
                    "run": run_row,
                    "steps": steps
                }
