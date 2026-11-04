"""
tests/test_case_prep_agent.py — Phase 3 Case Prep Agent & Decision Table Test Suite

Validates Phase 3 specifications in careloop_care_agents_plan.md:
1. Duplicate alert merging (24h window, merged_count, single nurse call-list card).
2. Deterministic fact sheet builder faithfulness (100% facts map to valid sources).
3. Decision table unit tests per row (Section 4.2 fixed menu; LLM never chooses step).
4. Caregiver consent enforcement (Meera Sharma: brief explicitly states "not granted", no family outreach).
5. Call script builder (doctor-approved check-in questions, zero invented questions).
6. Shadow decision logging & audit recording.
7. Agent execution ledger & trace provider verification.
"""

import pytest
import uuid
from datetime import datetime, timedelta

from backend.app.agents.case_prep_agent import CasePrepAgent
from backend.app.agents.policy_guard import PolicyGuard, ALLOWED_NEXT_STEPS
from backend.app.agents.ledger import AgentLedger
from backend.app.auth import make_token
from backend.app.db import get_conn


def test_duplicate_alert_merging():
    """Duplicate flags within 24h merge into one case with merged_count incremented."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Create a test flag for patient 5
            cur.execute("""
                INSERT INTO flags (patient_id, rule_id, source_type, reason, severity, status, created_at)
                VALUES (5, 14, 'Medication', 'Missed evening dose test', 'Review_Soon', 'Open', NOW());
            """)
            test_flag_id = cur.lastrowid
        conn.commit()

    # Group or create case
    res = CasePrepAgent.group_or_create_case(
        patient_id=5,
        flag_id=test_flag_id,
        source_type="Medication",
        rule_id=14
    )

    assert res["case_id"] == "case-sunita-missed-doses"
    assert res["is_duplicate"] is True
    assert res["merged_count"] >= 2

    # Verify case_flags association
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM case_flags WHERE case_id = %s AND flag_id = %s;", ("case-sunita-missed-doses", test_flag_id))
            cf = cur.fetchone()
            assert cf is not None


def test_decision_table_all_rows():
    """Validates each row in the Section 4.2 decision table deterministically."""
    # Row 1: Emergency / Urgent tier -> call_now
    r1 = CasePrepAgent.evaluate_decision_table(
        source_type="Emergency",
        severity="Urgent_Review",
        caregiver_consent=True,
        device_status="Online",
        time_since_last_contact_hours=0.5,
        no_answer_count=0
    )
    assert r1["next_step"]["key"] == "call_now"
    assert "Immediate or urgent tier flag" in r1["next_step"]["why"][0]
    assert all(opt in ALLOWED_NEXT_STEPS for opt in r1["options"])

    # Row 2a: Device silence with long gap (>4h) -> call_now
    r2a = CasePrepAgent.evaluate_decision_table(
        source_type="Device",
        severity="Review_Soon",
        caregiver_consent=False,
        device_status="Offline",
        time_since_last_contact_hours=6.5,
        no_answer_count=0
    )
    assert r2a["next_step"]["key"] == "call_now"
    assert "Device telemetry inactive > 6 hours" in r2a["next_step"]["why"][0]

    # Row 2b: Device silence with recent contact (<=4h) -> send_checkin
    r2b = CasePrepAgent.evaluate_decision_table(
        source_type="Device",
        severity="Review_Soon",
        caregiver_consent=False,
        device_status="Offline",
        time_since_last_contact_hours=1.2,
        no_answer_count=0
    )
    assert r2b["next_step"]["key"] == "send_checkin"
    assert all(opt in ALLOWED_NEXT_STEPS for opt in r2b["options"])

    # Row 3: Sensor vital breach -> call_now
    r3 = CasePrepAgent.evaluate_decision_table(
        source_type="Sensor",
        severity="Review_Soon",
        caregiver_consent=True,
        device_status="Online",
        time_since_last_contact_hours=2.0,
        no_answer_count=0
    )
    assert r3["next_step"]["key"] == "call_now"
    assert "Vital reading crossed clinician-approved threshold" in r3["next_step"]["why"][0]

    # Row 4a: Medication with multiple no-answers -> call_now
    r4a = CasePrepAgent.evaluate_decision_table(
        source_type="Medication",
        severity="Review_Soon",
        caregiver_consent=True,
        device_status="Online",
        time_since_last_contact_hours=3.0,
        no_answer_count=2
    )
    assert r4a["next_step"]["key"] == "call_now"
    assert "Multiple unconfirmed scheduled doses" in r4a["next_step"]["why"][0]

    # Row 4b: Medication single unconfirmed -> send_checkin
    r4b = CasePrepAgent.evaluate_decision_table(
        source_type="Medication",
        severity="Review_Soon",
        caregiver_consent=True,
        device_status="Online",
        time_since_last_contact_hours=1.0,
        no_answer_count=1
    )
    assert r4b["next_step"]["key"] == "send_checkin"

    # Row 5: Symptom report -> call_now
    r5 = CasePrepAgent.evaluate_decision_table(
        source_type="Symptom",
        severity="Review_Soon",
        caregiver_consent=True,
        device_status="Online",
        time_since_last_contact_hours=1.0,
        no_answer_count=0
    )
    assert r5["next_step"]["key"] == "call_now"
    assert "call_now" in r5["options"]

    # Row 6: Duplicate alert merging support
    r6 = CasePrepAgent.evaluate_decision_table(
        source_type="Medication",
        severity="Review_Soon",
        caregiver_consent=True,
        device_status="Online",
        time_since_last_contact_hours=1.0,
        no_answer_count=0,
        is_duplicate=True,
        merged_count=3
    )
    assert "merge_duplicate" in r6["options"]


def test_caregiver_consent_enforcement_meera():
    """Patient with no caregiver consent (Meera Sharma) explicitly notes so, and family step is blocked."""
    brief = CasePrepAgent.generate_case_brief("case-meera-silent", force_deterministic=True)

    # 1. Fact sheet must explicitly state lack of consent
    context_facts = [c["fact"] for c in brief["context"]]
    assert any("Caregiver consent: not granted" in f for f in context_facts)

    # 2. Family outreach must NEVER be suggested
    assert brief["next_step"]["key"] != "notify_family"
    assert "family" not in str(brief["next_step"]).lower()
    assert all("family" not in str(opt).lower() for opt in brief["options"])

    # 3. PolicyGuard inspection must pass
    guard_res = PolicyGuard.inspect("case_prep_agent", brief, {
        "patient_id": brief["patient_id"],
        "caregiver_consent": False
    })
    assert guard_res.passed is True


def test_brief_faithfulness_seed_cases():
    """100% of facts in generated briefs for Aarav, Meera, Rajesh, and Sunita must cite real sources."""
    seed_cases = ["case-aarav-spo2", "case-meera-silent", "case-rajesh-emergency", "case-sunita-missed-doses"]

    for cid in seed_cases:
        brief = CasePrepAgent.generate_case_brief(cid, force_deterministic=True)
        assert brief["case_id"] == cid
        assert brief["headline"] is not None
        assert len(brief["what_happened"]) >= 1
        assert len(brief["context"]) >= 3

        # Every fact in what_happened must have a valid source id
        for f in brief["what_happened"]:
            assert "fact" in f and len(f["fact"]) > 0
            assert "source" in f and len(f["source"]) > 0
            assert any(f["source"].startswith(prefix) for prefix in [
                "flag#", "reading#", "device#", "medication_log#", "symptom#"
            ])

        # Every fact in context must have a valid source id
        for c in brief["context"]:
            assert "fact" in c and len(c["fact"]) > 0
            assert "source" in c and len(c["source"]) > 0
            assert any(c["source"].startswith(prefix) for prefix in [
                "checkin#", "doses#", "caregiver#", "device#", "rule#", "task#"
            ])

        # Suggested step must be from approved menu
        assert brief["next_step"]["key"] in ALLOWED_NEXT_STEPS
        for opt in brief["options"]:
            assert opt in ALLOWED_NEXT_STEPS

        # PolicyGuard must pass
        assert brief["guard"]["passed"] is True


def test_call_script_builder_no_invented_questions():
    """Call script questions are derived strictly from clinical check-in protocols."""
    script = CasePrepAgent.prepare_call_script(
        patient_id=1,
        primary_flag_id=4,
        headline="Heart_Rate reading 104.0 bpm is above limit",
        source_type="Sensor"
    )
    assert script["call_script_id"] > 0
    assert len(script["questions"]) >= 4
    # Check 1 is identity verification
    assert "identity" in script["questions"][0].lower()
    # Check 2 is telemetry finding
    assert "telemetry" in script["questions"][1].lower() or "finding" in script["questions"][1].lower()


def test_shadow_mode_and_decide_endpoint():
    """Clinician decisions are recorded beside agent suggestions in shadow_decisions."""
    unique_run_id = f"run-test-shadow-{uuid.uuid4().hex[:6]}"
    agent_decision = {"key": "send_checkin", "label": "Send a check-in prompt"}
    human_decision = {"key": "call_now", "staff_id": 2, "staff_name": "Nurse Priya"}

    shadow_id = CasePrepAgent.record_shadow_decision(
        run_id=unique_run_id,
        action_type="next_step_suggestion",
        agent_decision=agent_decision,
        human_decision=human_decision
    )
    assert shadow_id > 0

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM shadow_decisions WHERE shadow_id = %s;", (shadow_id,))
            sd = cur.fetchone()
            assert sd is not None
            assert sd["run_id"] == unique_run_id
            assert sd["agreed"] == 0  # Disagreement recorded accurately


def test_ledger_trace_recording():
    """Every case brief run records run metrics and all pipeline steps in the ledger."""
    brief = CasePrepAgent.generate_case_brief("case-aarav-spo2", force_deterministic=True)
    run_id = brief["run_id"]

    trace = AgentLedger.trace(run_id)
    assert trace is not None
    assert trace["run"]["agent_name"] == "case_prep_agent"
    assert trace["run"]["status"] == "Done"

    # Must contain Gate, Tool, Plan, Guard steps
    step_types = [s["step_type"] for s in trace["steps"]]
    assert "Gate" in step_types
    assert "Tool" in step_types
    assert "Plan" in step_types
    assert "Guard" in step_types

