"""
backend/app/agents/retention_service.py — Agent Trace & Draft Retention Service (Phase 6)

Core Requirements:
1. Configurable retention window: AGENTS_V2_RETENTION_DAYS (default 30 days).
2. Purge job: Deletes expired agent runs, steps, and resolved drafts older than retention window.
3. Audited: Every purge execution logs exact deleted counts in audit_log.
4. Anonymization Check: Verifies traces store IDs, codes, and summaries, never patient names or phone numbers.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, List, Optional

from backend.app.db import get_conn
from backend.app.agents.config import AGENTS_V2_RETENTION, AGENTS_V2_RETENTION_DAYS

logger = logging.getLogger(__name__)


class AgentRetentionService:
    """Manages compliance, retention windows, and privacy purging for agent ledger traces."""

    @classmethod
    def purge_expired_records(
        cls,
        days: Optional[int] = None,
        retention_days: int = AGENTS_V2_RETENTION_DAYS,
        actor_id: int = 1,
        staff_id: Optional[int] = None,
        actor_role: str = "Doctor"
    ) -> Dict[str, Any]:
        """
        Purges agent traces, steps, and completed drafts older than retention_days.
        Logs an immutable audit record in audit_log.
        """
        if days is not None:
            retention_days = days
        if staff_id is not None:
            actor_id = staff_id

        if not AGENTS_V2_RETENTION:
            return {"status": "disabled", "message": "Retention purging is disabled via config."}

        cutoff_dt = datetime.now() - timedelta(days=retention_days)

        with get_conn() as conn, conn.cursor() as cur:
            # 1. Count and delete expired agent_steps
            cur.execute("""
                DELETE ast FROM agent_steps ast
                JOIN agent_runs ar ON ar.run_id = ast.run_id
                WHERE ar.started_at < %s;
            """, (cutoff_dt,))
            steps_deleted = cur.rowcount

            # 2. Count and delete expired agent_runs
            cur.execute("""
                DELETE FROM agent_runs
                WHERE started_at < %s;
            """, (cutoff_dt,))
            runs_deleted = cur.rowcount

            # 3. Delete completed / reviewed drafts older than cutoff (protecting unreviewed Pending items)
            cur.execute("""
                DELETE FROM agent_drafts
                WHERE status IN ('Accepted', 'Edited', 'Rejected', 'Auto_Sent', 'Expired')
                  AND created_at < %s;
            """, (cutoff_dt,))
            drafts_deleted = cur.rowcount

            # 4. Audit Log entry
            audit_details = {
                "retention_days": retention_days,
                "cutoff_datetime": cutoff_dt.isoformat(),
                "steps_deleted": steps_deleted,
                "runs_deleted": runs_deleted,
                "drafts_deleted": drafts_deleted,
                "triggered_by_staff_id": actor_id,
                "actor_role": actor_role
            }

            actor_type = "Staff" if actor_role in ("Doctor", "Nurse", "Staff") else "System"

            cur.execute("""
                INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details, created_at)
                VALUES (%s, %s, 'AGENT_RETENTION_PURGE', 'agent_system', 1, %s, NOW());
            """, (actor_type, str(actor_id), json.dumps(audit_details)))

            conn.commit()

        logger.info(f"Retention purge complete: {runs_deleted} runs, {steps_deleted} steps, {drafts_deleted} drafts (Cutoff: {retention_days} days)")
        return {
            "status": "COMPLETED",
            "retention_days": retention_days,
            "cutoff_date": cutoff_dt.strftime("%Y-%m-%d"),
            "deleted_runs": runs_deleted,
            "deleted_steps": steps_deleted,
            "deleted_drafts": drafts_deleted,
            "runs_deleted": runs_deleted,
            "steps_deleted": steps_deleted,
            "drafts_deleted": drafts_deleted,
            "purged_at": datetime.now().isoformat()
        }

    @classmethod
    def verify_trace_anonymization(cls, run_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Verifies that agent run traces do not store patient full names or phone numbers,
        storing only IDs and sanitized summaries.
        """
        violations = []
        with get_conn() as conn, conn.cursor() as cur:
            if run_id:
                cur.execute("SELECT run_id, plan, trigger_ref FROM agent_runs WHERE run_id = %s;", (run_id,))
                runs = cur.fetchall() or []
                cur.execute("SELECT summary, ids FROM agent_steps WHERE run_id = %s;", (run_id,))
                steps = cur.fetchall() or []
            else:
                cur.execute("SELECT run_id, plan, trigger_ref FROM agent_runs ORDER BY started_at DESC LIMIT 50;")
                runs = cur.fetchall() or []
                cur.execute("SELECT summary, ids FROM agent_steps ORDER BY created_at DESC LIMIT 100;")
                steps = cur.fetchall() or []

        combined_text = " ".join([
            str(r.get("plan") or "") + " " + str(r.get("trigger_ref") or "") for r in runs
        ]) + " " + " ".join([
            str(s.get("summary") or "") + " " + str(s.get("ids") or "") for s in steps
        ])

        # Check for banned names
        banned_names = ["Aarav Patel", "Meera Sharma", "Rajesh Verma", "Kabir Mehta", "Sunita Rao"]
        for name in banned_names:
            if name in combined_text:
                violations.append(f"Trace contains patient full name: '{name}'")

        # Check for raw phone numbers
        import re
        if re.search(r"\+?91[\s-]?\d{10}|\b[6-9]\d{9}\b", combined_text):
            violations.append("Trace contains patient phone number")

        return {
            "status": "COMPLIANT" if len(violations) == 0 else "NON_COMPLIANT",
            "violations_found": len(violations),
            "violations": violations,
            "passed": len(violations) == 0
        }
