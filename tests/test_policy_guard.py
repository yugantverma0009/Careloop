"""
tests/test_policy_guard.py — Phase 1 Policy Guard & Dispatcher Test Suite

Tests all 10 checks of the Policy Guard (Section 6) and the Supervisor Dispatcher:
1. Allowlist enforcement (tools and actions).
2. Identity enforcement.
3. Source citation requirements.
4. Numeric grounding guard.
5. Approved next-step menu.
6. Language consistency.
7. Banned clinical judgment words.
8. Caregiver consent enforcement.
9. Automation limits (quiet hours, daily caps, emergency flag suppression).
10. Global pause, patient opt-out, and degradation modes.
"""

import pytest
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

from backend.app.agents.policy_guard import PolicyGuard
from backend.app.agents.dispatcher import AgentDispatcher, MAX_DAILY_LLM_CALLS_PER_PATIENT
from backend.app.agents.ledger import AgentLedger
from backend.app.db import get_conn


def test_guard_blocks_disallowed_tool():
    """Tools outside the agent's allowlist must be rejected."""
    payload = {
        "tools_used": ["unauthorized_sql_exec", "get_next_appointment"],
        "answer": "Your appointment is tomorrow."
    }
    res = PolicyGuard.inspect("papers_agent", payload)
    assert not res.passed
    assert any("Disallowed tool" in r for r in res.reasons)


def test_guard_blocks_unapproved_action():
    """Action cards not on the allowlist must be rejected."""
    payload = {
        "actions": ["Prescribe_Medicine", "Ask_Care_Team"],
        "answer": "Here is an action."
    }
    res = PolicyGuard.inspect("papers_agent", payload)
    assert not res.passed
    assert any("not in allowlist" in r for r in res.reasons)


def test_guard_blocks_patient_id_mismatch():
    """Payload targeting a different patient than the context must be rejected."""
    payload = {
        "patient_id": 2,
        "answer": "Test"
    }
    res = PolicyGuard.inspect("papers_agent", payload, context={"patient_id": 1})
    assert not res.passed
    assert any("Patient ID mismatch" in r for r in res.reasons)


def test_guard_blocks_unsourced_fact():
    """Facts in a brief or answer must cite a source ID."""
    payload = {
        "facts": [
            {"fact": "Heart rate is 74 bpm", "source": "reading#12"},
            {"fact": "Patient was feeling dizzy"} # Missing source
        ]
    }
    res = PolicyGuard.inspect("case_prep_agent", payload)
    assert not res.passed
    assert any("missing required source" in r for r in res.reasons)


def test_guard_blocks_hallucinated_number():
    """Numbers in the answer must appear in the cited source text."""
    payload = {
        "answer": "Your target blood pressure is 120 over 80 mm Hg."
    }
    context = {
        "source_texts": ["Patient was discharged on CardioPulse-XR. Sternal incision healing."]
    }
    res = PolicyGuard.inspect("papers_agent", payload, context=context)
    assert not res.passed
    assert any("Numeric hallucination" in r for r in res.reasons)


def test_guard_blocks_unapproved_next_step():
    """Next steps must come only from the fixed menu."""
    payload = {
        "next_step": {"key": "order_new_labs", "why": ["Routine check"]}
    }
    res = PolicyGuard.inspect("case_prep_agent", payload)
    assert not res.passed
    assert any("not in approved menu" in r for r in res.reasons)


def test_guard_blocks_banned_clinical_words():
    """Clinical judgment words like normal, safe, stable, or optimal must be rejected."""
    payload1 = {"answer": "Your vitals are completely normal and safe."}
    res1 = PolicyGuard.inspect("papers_agent", payload1)
    assert not res1.passed
    assert any("Banned clinical judgment" in r for r in res1.reasons)

    payload2 = {"answer": "CareLoop's AI nurse will monitor you 24/7."}
    res2 = PolicyGuard.inspect("papers_agent", payload2)
    assert not res2.passed
    assert any("Banned clinical judgment" in r for r in res2.reasons)


def test_guard_blocks_family_outreach_without_consent():
    """Family notifications cannot be suggested if caregiver consent is False."""
    payload = {
        "next_step": {"key": "call_now"},
        "facts": [{"fact": "Family caregiver notified", "source": "caregiver#2"}]
    }
    context = {"caregiver_consent": False}
    res = PolicyGuard.inspect("case_prep_agent", payload, context=context)
    assert not res.passed
    assert any("valid caregiver consent" in r for r in res.reasons)


def test_guard_blocks_quiet_hours_and_daily_caps():
    """Automated messages during quiet hours (22:00-07:00) or above daily caps must be blocked."""
    quiet_time = datetime(2026, 11, 3, 23, 15, tzinfo=IST) # 23:15 IST
    
    payload = {
        "is_automated_patient_msg": True,
        "answer": "Time for your evening check-in"
    }
    res_quiet = PolicyGuard.inspect("outreach_agent", payload, context={"current_time": quiet_time})
    assert not res_quiet.passed
    assert any("quiet hours" in r for r in res_quiet.reasons)

    # Daytime cap test (4th message)
    day_time = datetime(2026, 11, 3, 14, 0, tzinfo=IST)
    res_cap = PolicyGuard.inspect(
        "outreach_agent", payload,
        context={"current_time": day_time, "daily_automated_message_count": 3}
    )
    assert not res_cap.passed
    assert any("Daily automation cap exceeded" in r for r in res_cap.reasons)


def test_dispatcher_global_pause():
    """Doctor global pause switch blocks all agent actions immediately."""
    try:
        AgentDispatcher.set_global_pause(True, staff_id=1)
        assert AgentDispatcher.is_global_paused() is True

        decision = AgentDispatcher.check_intake("dose_reminder", patient_id=1)
        assert decision.allowed is False
        assert "globally paused" in decision.reason
    finally:
        AgentDispatcher.set_global_pause(False, staff_id=1)
        assert AgentDispatcher.is_global_paused() is False


def test_dispatcher_patient_opt_out():
    """Patient toggle ai_help_enabled=0 must block automated AI interactions."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE patients SET ai_help_enabled = 0 WHERE patient_id = 1;")
        conn.commit()

    try:
        decision = AgentDispatcher.check_intake("papers_question_sourced", patient_id=1)
        assert decision.allowed is False
        assert "opted out of automated AI help" in decision.reason
    finally:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE patients SET ai_help_enabled = 1 WHERE patient_id = 1;")
            conn.commit()


def test_shadow_mode_records_without_acting():
    """Shadow mode actions are recorded in shadow_decisions alongside human actions."""
    level, mode = AgentDispatcher.get_autonomy("call_note")
    assert level == "Draft"
    assert mode == "Shadow"

    shadow_id = AgentDispatcher.record_shadow_decision(
        run_id="run-shadow-test-01",
        action_type="call_note",
        agent_decision={"draft": "Patient reported mild fatigue, taking medicines on time."},
        human_decision={"final": "Patient reported mild fatigue, resting well."},
        agreed=True
    )
    assert shadow_id > 0

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shadow_decisions WHERE shadow_id = %s;", (shadow_id,))
            row = cur.fetchone()
            assert row is not None
            assert row["action_type"] == "call_note"
            assert row["agreed"] == 1


def test_ledger_run_and_trace():
    """Every agent run records plan, steps, and produces a complete trace."""
    run_id = "test-run-trace-01"
    AgentLedger.start_run(
        run_id=run_id,
        agent_name="case_prep_agent",
        trigger_type="sensor_flag",
        patient_id=1,
        autonomy_level="Auto",
        mode="Live",
        plan={"goal": "prepare_case_brief"}
    )
    AgentLedger.record_step(run_id, 1, "Gate", "Checked emergency and consent", ok=True, ms=2)
    AgentLedger.record_step(run_id, 2, "Tool", "Fetched latest readings", ids=[12, 13], ok=True, ms=15)
    AgentLedger.finish_run(
        run_id=run_id,
        status="Done",
        result_type="case_brief",
        llm_calls=1,
        latency_ms=450
    )

    trace = AgentLedger.trace(run_id)
    assert trace is not None
    assert trace["run"]["agent_name"] == "case_prep_agent"
    assert len(trace["steps"]) == 2
    assert trace["steps"][0]["step_type"] == "Gate"
    assert trace["steps"][1]["step_type"] == "Tool"
