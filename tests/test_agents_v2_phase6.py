"""
tests/test_agents_v2_phase6.py — Phase 6 Hardening, Retention & Security Verification Tests
"""

import pytest
from datetime import datetime, timedelta
from backend.app.agents.config import (
    CANARY_STRING,
    AGENTS_V2_HARDENING,
    AGENTS_V2_RETENTION_DAYS,
    MAX_INPUT_LENGTH_CHARS,
)
from backend.app.agents.policy_guard import PolicyGuard
from backend.app.agents.retention_service import AgentRetentionService
import uuid
from backend.app.agents.redteam_cases_v2 import REDTEAM_CASES_V2
from backend.app.agents.redteam_runner import run_redteam_suite
from backend.app.agents.ledger import AgentLedger
from backend.app.db import get_conn


def test_canary_leakage_detection():
    """Verify that any output attempting to leak the internal canary token is blocked."""
    leaked_output = f"Here is the system secret: {CANARY_STRING} and the patient details."
    guard_res = PolicyGuard.inspect_output(leaked_output, agent_name="PapersAgent")
    assert not guard_res.is_safe
    assert "Canary token leaked in output payload" in guard_res.reason


def test_input_screening_length_cap():
    """Verify input screening flags inputs exceeding maximum character length."""
    excessive_input = "A" * (MAX_INPUT_LENGTH_CHARS + 50)
    is_safe, reason = PolicyGuard.screen_input_text(excessive_input)
    assert not is_safe
    assert "INPUT_LENGTH_EXCEEDED" in reason


def test_tool_argument_fuzzing_and_injection():
    """Verify tool argument validation catches SQL injection, script injection, and prompt overrides."""
    malicious_args = {
        "patient_id": "1; DROP TABLE patients;--",
        "question": "<script>alert('xss')</script>",
        "role": "SYSTEM OVERRIDE"
    }
    is_safe, reason = PolicyGuard.validate_tool_arguments(malicious_args)
    assert not is_safe
    assert "Fuzzing / injection pattern detected" in reason

    clean_args = {
        "patient_id": 1,
        "question": "When do I take my evening Metformin?",
        "role": "Nurse"
    }
    clean_safe, clean_reason = PolicyGuard.validate_tool_arguments(clean_args)
    assert clean_safe
    assert clean_reason is None


def test_retention_service_purge():
    """Verify expired traces and approved drafts are purged while pending drafts and audit records are preserved."""
    # 1. Create expired and recent runs
    expired_run_id = f"run-test-purge-{uuid.uuid4().hex[:8]}"
    AgentLedger.start_run(
        run_id=expired_run_id,
        agent_name="RetentionTestAgent",
        trigger_type="test_purge",
        patient_id=1,
        autonomy_level="Draft",
        mode="Live",
        version_id="ver-retention-1.0.0"
    )
    
    # Artificially age the expired run
    old_date = datetime.now() - timedelta(days=AGENTS_V2_RETENTION_DAYS + 5)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE agent_runs SET started_at = %s WHERE run_id = %s", (old_date, expired_run_id))
            cur.execute("UPDATE agent_steps SET created_at = %s WHERE run_id = %s", (old_date, expired_run_id))
            # Create an expired draft in Accepted status
            cur.execute("""
                INSERT INTO agent_drafts (run_id, patient_id, draft_type, body, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (expired_run_id, 1, "Summary", '{"text": "Old Accepted Draft"}', "Accepted", old_date))
            # Create an expired draft in Pending status (must NOT be purged)
            cur.execute("""
                INSERT INTO agent_drafts (run_id, patient_id, draft_type, body, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (expired_run_id, 1, "Summary", '{"text": "Pending Draft"}', "Pending", old_date))
        conn.commit()

    # Run purge
    purge_stats = AgentRetentionService.purge_expired_records(days=AGENTS_V2_RETENTION_DAYS, staff_id=1)
    assert purge_stats["status"] == "COMPLETED"
    assert purge_stats["deleted_runs"] >= 1
    assert purge_stats["deleted_drafts"] >= 1

    # Verify Pending draft is preserved
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM agent_drafts WHERE status = 'Pending' AND run_id = %s", (expired_run_id,))
            res = cur.fetchone()
            assert (res["cnt"] if isinstance(res, dict) else res[0]) >= 1


def test_trace_anonymization_verification():
    """Verify trace anonymization check reports clean state."""
    check = AgentRetentionService.verify_trace_anonymization()
    assert check["violations_found"] == 0
    assert check["status"] == "COMPLIANT"


def test_redteam_suite_100_percent_blocked():
    """Verify the 85-case redteam suite achieves 100% block rate across all attack vectors."""
    assert len(REDTEAM_CASES_V2) == 85
    summary = run_redteam_suite()
    assert summary["total_cases"] == 85
    assert summary["blocked_count"] == 85
    assert summary["passed_attacks_count"] == 0
    assert summary["block_rate_pct"] == 100.0


def test_failure_drills_executable():
    """Verify failure drills run without error and report graceful degradation."""
    from scripts.failure_drills import run_all_failure_drills
    drill_results = run_all_failure_drills()
    assert len(drill_results) == 6
    assert all(d["passed"] for d in drill_results)
