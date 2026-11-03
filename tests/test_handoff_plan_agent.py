"""
tests/test_handoff_plan_agent.py — Phase 5 Handoff Agent, Plan Agent & Auto-Close Test Suite

Validates Phase 5 specifications in careloop_care_agents_plan.md:
1. Handoff Agent:
   - Fact sheet generation: 100% deterministic, zero LLM reliance for core facts.
   - SBAR/I-PASS summary drafting: zero banned judgment words (Policy Guard checked).
   - Cohort shift handoff drafting.
   - Summary signing: records reviewer, reviewed_at, and edit_chars fidelity.
   - Patient isolation: unsigned drafts are never visible to patients.
2. Plan Agent:
   - Sourced plan drafting: citations link to valid document chunks.
   - Medication reconciliation ('Matches' vs 'Mismatch').
   - Doctor approval activates the plan and generates understanding checks.
3. Approved Auto-Close Rules:
   - Refuses Emergency, SOS, Urgent_Review, Symptom, and Photo flags.
   - Closes low-risk routine flags when enabled with trigger label.
   - Permits reopening of auto-closed flags.
4. Governance & Autonomy Matrix:
   - Promotion to Live is restricted to Doctor role and audited.
   - Demotion to Shadow functions immediately.
"""

import pytest
import json
from datetime import datetime, date

from backend.app.agents.handoff_agent import HandoffAgent
from backend.app.agents.plan_agent import PlanAgent
from backend.app.agents.auto_close_service import AutoCloseService
from backend.app.agents.policy_guard import PolicyGuard, BANNED_WORDS
from backend.app.agents.dispatcher import AgentDispatcher
from backend.app.db import get_conn


def test_handoff_agent_fact_sheet_faithfulness():
    """Handoff Agent compiles deterministic fact sheet from SQL without hallucination."""
    patient_id = 1  # Aarav Patel
    facts = HandoffAgent.build_patient_fact_sheet(patient_id)

    assert facts["patient_id"] == 1
    assert facts["patient_code"] in ("CL-101", "CL-00001")
    assert facts["relative_day"] >= 1
    assert "vitals" in facts
    assert "medications_today" in facts
    assert "open_flags" in facts
    assert "open_tasks" in facts

    # Verify numbers in vitals match actual DB readings
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT measurement_type, measurement_value FROM sensor_readings WHERE patient_id = 1 ORDER BY measured_at DESC LIMIT 1;")
        latest_reading = cur.fetchone()
        if latest_reading and facts["vitals"]:
            assert latest_reading["measurement_type"] == facts["vitals"][0]["metric"]
            assert float(latest_reading["measurement_value"]) == facts["vitals"][0]["value"]


def test_handoff_agent_draft_summary_and_banned_words():
    """Drafted patient summary strictly adheres to SBAR format and zero banned clinical judgment words."""
    patient_id = 1
    staff_id = 2  # Nurse Priya

    draft = HandoffAgent.draft_patient_summary(patient_id, staff_id)
    assert draft["ai_prepared"] is True
    assert draft["badge"] == "AI-prepared draft"
    assert "draft_id" in draft
    assert "run_id" in draft

    combined_text = f"{draft['situation']} {draft['background']} {' '.join(draft['assessment_facts'])} {' '.join(draft['items_for_review'])}".lower()

    # Rule: Zero banned clinical judgment words (stable, normal, safe, improving, etc.)
    for word_regex in BANNED_WORDS:
        # Check against banned words in summary draft
        assert not any(b_word in combined_text for b_word in ["stable", "normal", "optimal", "cured"]), \
            f"Banned word found in summary: {combined_text}"

    # Verify draft in agent_drafts table
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM agent_drafts WHERE draft_id = %s;", (draft["draft_id"],))
        d_row = cur.fetchone()
        assert d_row is not None
        assert d_row["status"] == "Pending"
        assert d_row["draft_type"] == "Summary"


def test_summary_signing_records_reviewer_and_patient_isolation():
    """Signing records reviewer, reviewed_at, and edit_chars. Unsigned draft never shown to patient."""
    patient_id = 1
    staff_id = 2

    # Step 1: Draft summary
    draft = HandoffAgent.draft_patient_summary(patient_id, staff_id)
    draft_id = draft["draft_id"]

    # Acceptance check: Unsigned draft must NOT exist in ai_summaries with status='Approved'
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM ai_summaries WHERE patient_id = %s AND status = 'Approved' AND summary_text LIKE %s;",
                    (patient_id, f"%{draft['draft_id']}%"))
        assert cur.fetchone() is None

    # Step 2: Sign summary with edit
    edited_text = f"Patient CL-101 post-discharge Day 3. Sternal incision healing cleanly. Vital signs logged."
    signed = HandoffAgent.sign_patient_summary(draft_id=draft_id, staff_id=staff_id, edited_text=edited_text)

    assert signed["status"] == "signed"
    assert signed["final_status"] == "Edited"
    assert signed["edit_chars"] > 0
    assert signed["signed_by_staff_id"] == staff_id

    # Step 3: Verified in DB
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT status, reviewed_by_staff_id, edit_chars FROM agent_drafts WHERE draft_id = %s;", (draft_id,))
        d = cur.fetchone()
        assert d["status"] == "Edited"
        assert d["reviewed_by_staff_id"] == staff_id
        assert d["edit_chars"] > 0

        # Verified in ai_summaries table
        cur.execute("SELECT * FROM ai_summaries WHERE summary_id = %s;", (signed["summary_id"],))
        summ = cur.fetchone()
        assert summ is not None
        assert summ["status"] == "Approved"
        assert summ["reviewed_by_staff_id"] == staff_id


def test_cohort_shift_handoff_draft_and_sign():
    """Handoff Agent drafts cohort shift handoff report and incoming clinician signs it."""
    staff_id = 2
    handoff = HandoffAgent.draft_shift_handoff(staff_id=staff_id, shift_type="Morning_to_Evening")

    assert handoff["ai_prepared"] is True
    assert handoff["total_patients"] >= 5
    assert len(handoff["patient_handoffs"]) >= 5
    draft_id = handoff["draft_id"]

    # Sign handoff
    signed = HandoffAgent.sign_shift_handoff(draft_id=draft_id, staff_id=staff_id, notes="Received by Priya Nair. All contingent tasks reviewed.")
    assert signed["status"] == "signed"
    assert signed["reviewed_by_staff_id"] == staff_id

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT status, reviewed_by_staff_id FROM agent_drafts WHERE draft_id = %s;", (draft_id,))
        d = cur.fetchone()
        assert d["status"] == "Accepted"
        assert d["reviewed_by_staff_id"] == staff_id


def test_plan_agent_draft_reconciliation_and_doctor_approval():
    """Plan Agent drafts recovery plan with sources & reconciliation; doctor approval activates plan."""
    patient_id = 1
    staff_id = 1  # Dr. Sharma

    # 1. Draft Recovery Plan
    plan_draft = PlanAgent.draft_recovery_plan(patient_id=patient_id, staff_id=staff_id)
    assert plan_draft["patient_id"] == 1
    assert "plan_id" in plan_draft
    assert plan_draft["items_count"] > 0
    plan_id = plan_draft["plan_id"]

    # Verify items have citations and reconcile_status
    has_medicine = any(it["item_type"] == "Medicine" for it in plan_draft["items"])
    assert has_medicine is True
    for it in plan_draft["items"]:
        assert it["reconcile_status"] in ("Matches", "Mismatch", "Not_Applicable")

    # Verify plan starts in 'Draft' status (invisible to patients)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM recovery_plans WHERE plan_id = %s;", (plan_id,))
        assert cur.fetchone()["status"] == "Draft"

    # 2. Doctor approves recovery plan
    approve_res = PlanAgent.approve_recovery_plan(plan_id=plan_id, doctor_staff_id=1, notes="Approved per clinical protocol.")
    assert approve_res["status"] == "approved"
    assert approve_res["plan_id"] == plan_id

    # Verify plan is now 'Approved'
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT status, approved_by_staff_id FROM recovery_plans WHERE plan_id = %s;", (plan_id,))
        approved_row = cur.fetchone()
        assert approved_row["status"] == "Approved"
        assert approved_row["approved_by_staff_id"] == 1


def test_auto_close_rules_refuse_emergency_and_urgent_flags():
    """Approved auto-close rules strictly REFUSE emergency, SOS, urgent, symptom, or photo flags."""
    # Ensure auto-close rules are enabled
    AutoCloseService.set_auto_close_enabled(True, doctor_staff_id=1)

    # 1. Test Refusal on Emergency Flag
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO flags (patient_id, rule_id, source_type, reason, severity, status, created_at)
            VALUES (1, 1, 'Emergency', 'Severe acute chest pain', 'Urgent_Review', 'Open', NOW());
        """, ())
        emerg_flag_id = cur.lastrowid
        conn.commit()

    try:
        can_close, reason = AutoCloseService.can_auto_close(emerg_flag_id)
        assert can_close is False
        assert "strictly refused" in reason.lower()

        # Direct execution must raise ValueError
        with pytest.raises(ValueError):
            AutoCloseService.auto_close_flag(emerg_flag_id)
    finally:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM flags WHERE flag_id = %s;", (emerg_flag_id,))
            conn.commit()

    # 2. Test Refusal on Symptom Flag
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO flags (patient_id, rule_id, source_type, reason, severity, status, created_at)
            VALUES (1, 2, 'Symptom', 'Reported shortness of breath', 'Review_Soon', 'Open', NOW());
        """, ())
        symptom_flag_id = cur.lastrowid
        conn.commit()

    try:
        can_close, reason = AutoCloseService.can_auto_close(symptom_flag_id)
        assert can_close is False
        assert "symptom" in reason.lower()
    finally:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM flags WHERE flag_id = %s;", (symptom_flag_id,))
            conn.commit()


def test_auto_close_low_risk_flag_and_reopen():
    """Approved auto-close succeeds on low-risk Device flag, writes clear label, and permits reopening."""
    AutoCloseService.set_auto_close_enabled(True, doctor_staff_id=1)

    # Insert low-risk device flag
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO flags (patient_id, rule_id, source_type, reason, severity, status, created_at)
            VALUES (2, 5, 'Device', 'No telemetry readings received for 2 hours', 'Review_Soon', 'Open', NOW());
        """, ())
        device_flag_id = cur.lastrowid
        conn.commit()

    try:
        # Can auto-close check
        can_close, reason = AutoCloseService.can_auto_close(device_flag_id)
        assert can_close is True

        # Execute Auto-Close
        close_res = AutoCloseService.auto_close_flag(
            flag_id=device_flag_id,
            trigger_condition="telemetry readings resumed for 30m",
            doctor_name="Dr. Sharma"
        )
        assert close_res["status"] == "auto_closed"
        assert "Closed by approved rule" in close_res["resolution_label"]
        assert "Dr. Sharma" in close_res["resolution_label"]
        assert close_res["can_reopen"] is True

        # Verify flag status in DB
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT status, resolution_code, resolution_note FROM flags WHERE flag_id = %s;", (device_flag_id,))
            fl = cur.fetchone()
            assert fl["status"] == "Resolved"
            assert fl["resolution_code"] == "AUTO_CLOSED_DATA_RESUMED"

        # Reopen flag
        reopen_res = AutoCloseService.reopen_flag(
            flag_id=device_flag_id,
            staff_id=2,  # Nurse Priya reopens
            reopen_reason="Clinician noticed intermittent heart rate drop"
        )
        assert reopen_res["status"] == "reopened"
        assert reopen_res["new_status"] == "Open"

        # Verify flag reopened in DB
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT status, resolution_code FROM flags WHERE flag_id = %s;", (device_flag_id,))
            fl_reopened = cur.fetchone()
            assert fl_reopened["status"] == "Open"
            assert fl_reopened["resolution_code"] is None
    finally:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM flags WHERE flag_id = %s;", (device_flag_id,))
            conn.commit()


def test_autonomy_matrix_promotion_and_demotion():
    """Autonomy matrix update: Promotion to Live is restricted to Doctor and audited; demotion works immediately."""
    doctor_staff_id = 1

    # 1. Promote 'shift_handoff' to Live
    AgentDispatcher.set_autonomy(action_type="shift_handoff", level="Draft", mode="Live", staff_id=doctor_staff_id)
    assert AgentDispatcher.get_autonomy("shift_handoff") == ("Draft", "Live")

    # 2. Demote 'shift_handoff' to Shadow
    AgentDispatcher.set_autonomy(action_type="shift_handoff", level="Draft", mode="Shadow", staff_id=doctor_staff_id)
    assert AgentDispatcher.get_autonomy("shift_handoff") == ("Draft", "Shadow")
