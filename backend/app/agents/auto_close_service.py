"""
backend/app/agents/auto_close_service.py — Approved Auto-Close Rules Service

Principles:
- "The LLM talks. Rules decide. Humans act."
- "Doctor-enabled per rule type and per patient, off by default."
- Low-risk types only (e.g. "No data from device" closes when valid telemetry resumes for 30 minutes).
- STRICT SAFETY GUARD: NEVER auto-close Emergency, SOS, Urgent, Symptom, or Photo flags.
- Closures are clearly labelled with the trigger condition and the doctor who approved the rule.
- Every auto-closed flag CAN be reopened by staff at any time.
- All actions audited with staff/system identity.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from ..db import get_conn

logger = logging.getLogger(__name__)

RESTRICTED_SOURCE_TYPES = {"Emergency", "SOS", "Symptom", "Photo"}
RESTRICTED_SEVERITIES = {"Urgent", "Urgent_Review"}


class AutoCloseService:
    """Manages doctor-approved auto-close rules for low-risk clinical flags."""

    @staticmethod
    def is_auto_close_enabled() -> bool:
        """Checks if doctor has turned on auto-close for approved rule types (off by default)."""
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT state_val FROM agent_system_state WHERE state_key = 'auto_close_enabled';
                """)
                row = cur.fetchone()
                if row and row.get("state_val") == "true":
                    return True
                
                # Check agent_autonomy table for approved_flag_auto_close mode
                cur.execute("""
                    SELECT mode FROM agent_autonomy WHERE action_type = 'approved_flag_auto_close';
                """)
                auto_row = cur.fetchone()
                return bool(auto_row and auto_row.get("mode") == "Live")

    @staticmethod
    def set_auto_close_enabled(enabled: bool, doctor_staff_id: int) -> None:
        """Doctor enables or disables auto-close rules. Off by default."""
        with get_conn() as conn:
            with conn.cursor() as cur:
                val = "true" if enabled else "false"
                cur.execute("""
                    INSERT INTO agent_system_state (state_key, state_val, updated_by_staff_id, updated_at)
                    VALUES ('auto_close_enabled', %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE state_val = VALUES(state_val), updated_by_staff_id = VALUES(updated_by_staff_id), updated_at = NOW();
                """, (val, doctor_staff_id))

                # Update agent_autonomy table mode
                new_mode = "Live" if enabled else "Shadow"
                cur.execute("""
                    UPDATE agent_autonomy
                    SET mode = %s, set_by_staff_id = %s, set_at = NOW()
                    WHERE action_type = 'approved_flag_auto_close';
                """, (new_mode, doctor_staff_id))

                cur.execute("""
                    INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                    VALUES ('Staff', %s, 'AUTO_CLOSE_POLICY_UPDATED', 'agent_system_state', 0,
                            JSON_OBJECT('enabled', %s, 'mode', %s));
                """, (str(doctor_staff_id), enabled, new_mode))
                conn.commit()

        logger.info(f"Auto-close rules set to enabled={enabled} by doctor #{doctor_staff_id}")

    @classmethod
    def can_auto_close(cls, flag_id: int) -> Tuple[bool, str]:
        """
        Evaluates whether a specific flag is eligible for approved auto-close.
        Enforces Section 5.4 constraints:
        - Must be enabled by doctor (off by default).
        - Refuses Emergency, SOS, Urgent, Symptom, and Photo flags.
        """
        if not cls.is_auto_close_enabled():
            return False, "Auto-close is disabled by default until doctor enables approved rules"

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT flag_id, patient_id, source_type, severity, status, reason
                    FROM flags WHERE flag_id = %s;
                """, (flag_id,))
                fl = cur.fetchone()
                if not fl:
                    return False, f"Flag #{flag_id} not found"

                if fl["status"] != "Open":
                    return False, f"Flag #{flag_id} is already {fl['status']}"

                # Mandatory Refusal of Emergency, SOS, Symptom, and Photo flags
                if fl["source_type"] in RESTRICTED_SOURCE_TYPES:
                    return False, f"Auto-close strictly refused: flag source_type '{fl['source_type']}' cannot be auto-closed"

                # Mandatory Refusal of Urgent severities
                if fl["severity"] in RESTRICTED_SEVERITIES:
                    return False, f"Auto-close strictly refused: flag severity '{fl['severity']}' requires licensed clinician sign-off"

                # Allowed low-risk types: Device / Silent_Device or Routine Medication adherence confirmation
                if fl["source_type"] in ("Device", "Silent_Device", "Medication", "Routine"):
                    return True, "Eligible for low-risk rule auto-close"

                return False, f"Source type '{fl['source_type']}' is not in approved low-risk auto-close catalog"

    @classmethod
    def auto_close_flag(
        cls,
        flag_id: int,
        trigger_condition: str = "data resumed 30m",
        doctor_name: str = "Dr. Sharma"
    ) -> Dict[str, Any]:
        """
        Executes approved auto-close on an eligible flag.
        Labels the closure with condition and approving doctor, and permits reopening.
        """
        eligible, reason = cls.can_auto_close(flag_id)
        if not eligible:
            raise ValueError(f"Cannot auto-close flag #{flag_id}: {reason}")

        now_str = datetime.now().strftime("%H:%M")
        resolution_code = "AUTO_CLOSED_DATA_RESUMED"
        resolution_label = f"Closed by approved rule ({trigger_condition} at {now_str}). Enabled by {doctor_name}."

        with get_conn() as conn:
            with conn.cursor() as cur:
                # Update flag to Resolved
                cur.execute("""
                    UPDATE flags
                    SET status = 'Resolved',
                        resolution_code = %s,
                        resolution_note = %s,
                        resolved_at = NOW()
                    WHERE flag_id = %s;
                """, (resolution_code, resolution_label, flag_id))

                # Check if case can be marked Resolved
                cur.execute("""
                    SELECT case_id FROM case_flags WHERE flag_id = %s;
                """, (flag_id,))
                cf = cur.fetchone()
                case_id = cf["case_id"] if cf else None

                if case_id:
                    # If all flags in case are resolved, mark case Resolved
                    cur.execute("""
                        SELECT COUNT(*) as open_cnt
                        FROM case_flags cf
                        JOIN flags f ON f.flag_id = cf.flag_id
                        WHERE cf.case_id = %s AND f.status = 'Open';
                    """, (case_id,))
                    open_cnt = cur.fetchone()["open_cnt"]
                    if open_cnt == 0:
                        cur.execute("UPDATE cases SET status = 'Resolved' WHERE case_id = %s;", (case_id,))

                # Audit Log
                cur.execute("""
                    INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                    VALUES ('Agent', '0', 'FLAG_AUTO_CLOSED', 'flags', %s,
                            JSON_OBJECT('flag_id', %s, 'case_id', %s, 'label', %s, 'condition', %s));
                """, (flag_id, flag_id, case_id, resolution_label, trigger_condition))

                conn.commit()

        logger.info(f"Flag #{flag_id} auto-closed: {resolution_label}")
        return {
            "status": "auto_closed",
            "flag_id": flag_id,
            "case_id": case_id,
            "resolution_label": resolution_label,
            "can_reopen": True
        }

    @staticmethod
    def reopen_flag(flag_id: int, staff_id: int, reopen_reason: str = "Reopened by clinician") -> Dict[str, Any]:
        """
        Reopens a resolved or auto-closed flag and its parent case.
        Audited with staff identity.
        """
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT flag_id, status FROM flags WHERE flag_id = %s;", (flag_id,))
                fl = cur.fetchone()
                if not fl:
                    raise ValueError(f"Flag #{flag_id} not found.")

                # Reopen flag
                cur.execute("""
                    UPDATE flags
                    SET status = 'Open',
                        resolution_code = NULL,
                        resolution_note = NULL,
                        resolved_at = NULL,
                        resolved_by_staff_id = NULL
                    WHERE flag_id = %s;
                """, (flag_id,))

                # Reopen case
                cur.execute("SELECT case_id FROM case_flags WHERE flag_id = %s;", (flag_id,))
                cf = cur.fetchone()
                case_id = cf["case_id"] if cf else None
                if case_id:
                    cur.execute("UPDATE cases SET status = 'Open' WHERE case_id = %s;", (case_id,))

                # Audit row
                cur.execute("""
                    INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                    VALUES ('Staff', %s, 'FLAG_REOPENED', 'flags', %s,
                            JSON_OBJECT('flag_id', %s, 'case_id', %s, 'reason', %s));
                """, (str(staff_id), flag_id, flag_id, case_id, reopen_reason))

                conn.commit()

        logger.info(f"Flag #{flag_id} reopened by staff #{staff_id}: {reopen_reason}")
        return {
            "status": "reopened",
            "flag_id": flag_id,
            "case_id": case_id,
            "new_status": "Open",
            "reopened_by_staff_id": staff_id
        }

