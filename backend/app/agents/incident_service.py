"""
backend/app/agents/incident_service.py — Incident Reporting, Candidate Test Generation, and Circuit Demotion

Implements:
1. Staff incident submission for any AI-prepared item or assistant answer.
2. Candidate regression test generation for doctor review.
3. Automatic demotion of the corresponding action to Draft (configurable).
4. Doctor candidate test approval/rejection lifecycle.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from backend.app.db import get_conn
from backend.app.agents.config import (
    AGENTS_V2_INCIDENT_REPORTING,
    AGENTS_V2_INCIDENT_AUTO_DEMOTE,
)
from backend.app.agents.circuit_breaker import ACTION_TO_AGENT, CircuitBreaker

logger = logging.getLogger(__name__)

# Reverse map: agent_name to primary action_type
AGENT_TO_PRIMARY_ACTION = {
    "papers_agent": "papers_question_sourced",
    "case_prep_agent": "case_brief",
    "call_notes_agent": "call_note",
    "outreach_agent": "dose_reminder",
    "handoff_agent": "shift_handoff",
    "plan_agent": "recovery_plan",
    "auto_close_service": "approved_flag_auto_close",
}


class IncidentService:
    @staticmethod
    def report_incident(
        run_id: str,
        reported_by_staff_id: int,
        category: str,
        note: str,
    ) -> Dict[str, Any]:
        """Records an AI output incident, creates candidate test, and triggers demotion."""
        if not AGENTS_V2_INCIDENT_REPORTING:
            raise ValueError("Incident reporting feature is currently disabled via AGENTS_V2_INCIDENT_REPORTING.")

        valid_categories = {"Wrong fact", "Unsafe", "Tone", "Other"}
        if category not in valid_categories:
            raise ValueError(f"Category '{category}' invalid. Must be one of {valid_categories}")

        with get_conn() as conn:
            with conn.cursor() as cur:
                # 1. Fetch run details
                cur.execute("""
                    SELECT run_id, agent_name, trigger_type, plan, guard_reasons, version_id
                    FROM agent_runs WHERE run_id = %s;
                """, (run_id,))
                run_row = cur.fetchone()
                if not run_row:
                    raise ValueError(f"Agent run '{run_id}' not found.")

                agent_name = run_row["agent_name"]
                trigger_type = run_row["trigger_type"]

                # Check for duplicate incident on this run_id or identical note/category
                cur.execute("""
                    SELECT incident_id, candidate_test_id FROM agent_incidents
                    WHERE run_id = %s AND category = %s AND note = %s LIMIT 1;
                """, (run_id, category, note))
                existing_inc = cur.fetchone()
                if existing_inc:
                    return {
                        "incident_id": existing_inc["incident_id"],
                        "candidate_id": existing_inc["candidate_test_id"],
                        "run_id": run_id,
                        "category": category,
                        "status": "Open",
                        "auto_demoted_action": None,
                        "duplicate": True
                    }

                # 2. Insert into agent_incidents
                cur.execute("""
                    INSERT INTO agent_incidents (
                        run_id, reported_by_staff_id, category, note, status, created_at
                    ) VALUES (%s, %s, %s, %s, 'Open', NOW());
                """, (run_id, reported_by_staff_id, category, note))
                incident_id = cur.lastrowid

                # 3. Create Candidate Test Case for Doctor Approval
                test_type = f"regression_{category.lower().replace(' ', '_')}"
                input_payload = {
                    "run_id": run_id,
                    "trigger_type": trigger_type,
                    "plan": run_row["plan"],
                    "version_id": run_row["version_id"],
                }
                expected_behavior = (
                    f"Staff-reported defect ({category}): {note}. "
                    "Agent must produce grounded output without unverified facts, unapproved advice, or safety policy violations."
                )

                cur.execute("""
                    INSERT INTO agent_candidate_tests (
                        incident_id, agent_name, test_type, input_payload, expected_behavior, status, created_at
                    ) VALUES (%s, %s, %s, %s, %s, 'Pending_Review', NOW());
                """, (incident_id, agent_name, test_type, json.dumps(input_payload), expected_behavior))
                candidate_id = cur.lastrowid

                # Link candidate_id back to incident
                cur.execute("""
                    UPDATE agent_incidents SET candidate_test_id = %s WHERE incident_id = %s;
                """, (candidate_id, incident_id))

                # 4. Immediate Demotion to Draft (config, default on)
                demoted_action = None
                if AGENTS_V2_INCIDENT_AUTO_DEMOTE:
                    action_type = trigger_type if trigger_type in ACTION_TO_AGENT else AGENT_TO_PRIMARY_ACTION.get(agent_name, "case_brief")
                    cur.execute("""
                        SELECT level, mode FROM agent_autonomy WHERE action_type = %s;
                    """, (action_type,))
                    auto_row = cur.fetchone()
                    if auto_row and auto_row["level"] != "Draft":
                        cur.execute("""
                            UPDATE agent_autonomy SET level = 'Draft' WHERE action_type = %s;
                        """, (action_type,))
                        cur.execute("""
                            INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                            VALUES ('Staff', %s, 'INCIDENT_AUTO_DEMOTION', 'agent_autonomy', 0, %s);
                        """, (reported_by_staff_id, json.dumps({
                            "incident_id": incident_id,
                            "run_id": run_id,
                            "action_type": action_type,
                            "reason": f"Incident reported ({category}): {note}",
                            "previous_level": auto_row["level"]
                        })))
                        demoted_action = action_type

            conn.commit()

        logger.info(f"Reported incident #{incident_id} for run {run_id}, candidate test #{candidate_id} created.")
        return {
            "incident_id": incident_id,
            "candidate_id": candidate_id,
            "run_id": run_id,
            "category": category,
            "status": "Open",
            "auto_demoted_action": demoted_action
        }

    @staticmethod
    def get_candidate_tests(status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists candidate tests requiring doctor review."""
        with get_conn() as conn:
            with conn.cursor() as cur:
                if status:
                    cur.execute("""
                        SELECT c.*, i.category, i.note, i.reported_by_staff_id, s.full_name as reported_by_name
                        FROM agent_candidate_tests c
                        LEFT JOIN agent_incidents i ON i.incident_id = c.incident_id
                        LEFT JOIN care_staff s ON s.staff_id = i.reported_by_staff_id
                        WHERE c.status = %s
                        ORDER BY c.created_at DESC;
                    """, (status,))
                else:
                    cur.execute("""
                        SELECT c.*, i.category, i.note, i.reported_by_staff_id, s.full_name as reported_by_name
                        FROM agent_candidate_tests c
                        LEFT JOIN agent_incidents i ON i.incident_id = c.incident_id
                        LEFT JOIN care_staff s ON s.staff_id = i.reported_by_staff_id
                        ORDER BY c.created_at DESC;
                    """)
                rows = cur.fetchall() or []
                for r in rows:
                    if isinstance(r.get("input_payload"), str):
                        try:
                            r["input_payload"] = json.loads(r["input_payload"])
                        except Exception:
                            pass
                    r["created_at"] = str(r["created_at"])
                    if r.get("reviewed_at"):
                        r["reviewed_at"] = str(r["reviewed_at"])
                return rows

    @staticmethod
    def review_candidate_test(candidate_id: int, reviewer_staff_id: int, approve: bool) -> Dict[str, Any]:
        """Doctor approves or rejects a candidate test case."""
        new_status = "Approved" if approve else "Rejected"
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE agent_candidate_tests
                    SET status = %s, reviewed_by_staff_id = %s, reviewed_at = NOW()
                    WHERE candidate_id = %s;
                """, (new_status, reviewer_staff_id, candidate_id))

                # Update incident status to Reviewed
                cur.execute("""
                    UPDATE agent_incidents
                    SET status = 'Reviewed'
                    WHERE candidate_test_id = %s;
                """, (candidate_id,))
            conn.commit()

        return {"candidate_id": candidate_id, "status": new_status, "reviewed_by": reviewer_staff_id}
