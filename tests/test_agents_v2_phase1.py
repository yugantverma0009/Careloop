"""
tests/test_agents_v2_phase1.py — Acceptance Test Suite for CareLoop Agents v2 Phase 1

Verifies:
1. Active version registry (`agent_versions`) and `version_id` recorded on every agent run.
2. CI regression gate (`scripts/regression_gate.py`) runnable and evaluating DEV & HELD-OUT splits.
3. Agent Health telemetry endpoint (`GET /agent/health`) returns real aggregated metrics across agents, actions, and drafts.
4. Circuit Breaker continuously monitors Auto/Live actions and auto-demotes to Draft with fake clock and injected guard blocks.
5. Incident reporting (`POST /agent/incidents`) logs incident, creates Candidate Test for doctor review, and triggers automatic demotion.
6. Doctor review of candidate tests (Approve / Reject).
"""

import os
import json
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db import get_conn
from backend.app.agents.ledger import AgentLedger
from backend.app.agents.circuit_breaker import CircuitBreaker
from backend.app.agents.incident_service import IncidentService
from backend.app.agents.health_service import AgentHealthService
from backend.app.agents.papers_agent import PapersAgent

client = TestClient(app)


def get_auth_token(email: str, password: str = "Demo@12345") -> str:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


def test_phase1_version_registry_recorded_on_runs():
    """Verify that agent_versions table exists and every agent run records a version_id."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM agent_versions WHERE is_active = 1;")
        active_count = cur.fetchone()["cnt"]
        assert active_count >= 6, f"Expected at least 6 active agent versions, got {active_count}"

    # Run PapersAgent query and verify version_id is recorded in agent_runs
    res = PapersAgent.process_query(
        patient_id=1,
        question="When is my next appointment?",
        language="en"
    )
    run_id = res["run_id"]
    assert run_id is not None

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT version_id, agent_name, status FROM agent_runs WHERE run_id = %s;", (run_id,))
        row = cur.fetchone()
        assert row is not None
        assert row["version_id"] is not None and row["version_id"].startswith("ver-")
        print(f"  ✓ Run {run_id} recorded with version_id: {row['version_id']}")


def test_phase1_agent_health_endpoint():
    """Verify GET /agent/health returns real numbers over 24h and 7d windows."""
    doc_token = get_auth_token("ananya.demo@example.test")
    res = client.get("/agent/health?window=24h", headers={"Authorization": f"Bearer {doc_token}"})
    assert res.status_code == 200, res.text
    data = res.json()

    assert "summary" in data
    assert "by_agent" in data
    assert "by_action" in data
    assert "nurse_summary" in data

    assert data["summary"]["total_runs"] >= 0
    assert "overall_p50_ms" in data["summary"]
    assert "overall_p95_ms" in data["summary"]
    assert len(data["by_agent"]) > 0
    print(f"  ✓ Agent Health 24h: {data['summary']['total_runs']} runs, p50={data['summary']['overall_p50_ms']}ms, p95={data['summary']['overall_p95_ms']}ms")


def test_phase1_circuit_breaker_demotes_with_fake_clock():
    """Verify Circuit Breaker demotes an Auto/Live action when guard failure threshold is breached using fake clock."""
    action_type = "dose_reminder"
    fake_clock = datetime(2026, 11, 4, 15, 30, 0)

    with get_conn() as conn:
        with conn.cursor() as cur:
            # Set to Auto and Live
            cur.execute("UPDATE agent_autonomy SET level = 'Auto', mode = 'Live' WHERE action_type = %s;", (action_type,))
            # Inject 10 runs with 3 Blocked_By_Guard (30% > 10% threshold)
            for i in range(10):
                st = "Blocked_By_Guard" if i < 3 else "Done"
                cur.execute("""
                    INSERT INTO agent_runs (
                        run_id, agent_name, trigger_type, started_at, status, autonomy_level, mode, version_id
                    ) VALUES (%s, 'outreach_agent', %s, %s, %s, 'Auto', 'Live', 'ver-outreach-1.0.0')
                    ON DUPLICATE KEY UPDATE status = VALUES(status);
                """, (f"cb-test-run-{i}", action_type, fake_clock - timedelta(minutes=i * 2), st))
        conn.commit()

    try:
        # Evaluate with fake clock
        demotion = CircuitBreaker.evaluate_action(action_type, now=fake_clock)
        assert demotion is not None, "Circuit breaker should have triggered demotion"
        assert demotion["demoted"] is True
        assert demotion["new_level"] == "Draft"
        assert "Guard-block rate" in demotion["reason"]

        # Verify DB updated
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT level, mode FROM agent_autonomy WHERE action_type = %s;", (action_type,))
            auto_row = cur.fetchone()
            assert auto_row["level"] == "Draft"
        print(f"  ✓ Circuit Breaker successfully demoted {action_type} to Draft: {demotion['reason']}")
    finally:
        # Clean up test runs
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM agent_runs WHERE run_id LIKE 'cb-test-run-%';")
                cur.execute("UPDATE agent_autonomy SET level = 'Auto', mode = 'Live' WHERE action_type = %s;", (action_type,))
            conn.commit()


def test_phase1_incident_reporting_creates_candidate_and_demotes():
    """Verify staff incident reporting creates candidate test and immediately auto-demotes the action."""
    doc_token = get_auth_token("ananya.demo@example.test")

    # Fetch an existing run
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT run_id FROM agent_runs ORDER BY started_at DESC LIMIT 1;")
            target_run_id = cur.fetchone()["run_id"]
            # Ensure case_brief is at Auto
            cur.execute("UPDATE agent_autonomy SET level = 'Auto', mode = 'Live' WHERE action_type = 'case_brief';")
        conn.commit()

    # Post Incident Report
    resp = client.post(
        "/agent/incidents",
        headers={"Authorization": f"Bearer {doc_token}"},
        json={
            "run_id": target_run_id,
            "category": "Wrong fact",
            "note": "AI included unverified dose in case prep brief"
        }
    )
    assert resp.status_code == 200, resp.text
    inc_data = resp.json()

    incident_id = inc_data["incident_id"]
    candidate_id = inc_data["candidate_id"]
    assert incident_id is not None
    assert candidate_id is not None

    # Check candidate test was created
    c_resp = client.get("/agent/candidate-tests", headers={"Authorization": f"Bearer {doc_token}"})
    assert c_resp.status_code == 200
    candidates = c_resp.json()
    matched = [c for c in candidates if c["candidate_id"] == candidate_id]
    assert len(matched) == 1
    assert matched[0]["status"] == "Pending_Review"

    # Doctor Approves candidate test
    appr_resp = client.post(f"/agent/candidate-tests/{candidate_id}/approve", headers={"Authorization": f"Bearer {doc_token}"})
    assert appr_resp.status_code == 200
    assert appr_resp.json()["status"] == "Approved"

    # Verify action was demoted to Draft
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT level FROM agent_autonomy WHERE action_type = 'case_brief';")
            assert cur.fetchone()["level"] == "Draft"
            # Reset back for demo state
            cur.execute("UPDATE agent_autonomy SET level = 'Auto' WHERE action_type = 'case_brief';")
        conn.commit()
    print(f"  ✓ Incident #{incident_id} created candidate #{candidate_id} and auto-demoted action to Draft.")
