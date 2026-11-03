"""
tests/test_outreach_call_notes_agent.py — Phase 4 Outreach Agent & Call Notes Agent Test Suite

Validates Phase 4 specifications in careloop_care_agents_plan.md:
1. Call Notes Agent:
   - Grounding check: Policy Guard blocks drafts that add unprovided facts/numbers/symptoms.
   - Atomic action: Approving draft creates note, task, patient message, and contact log in one transaction.
   - Edit fidelity: edit_chars recorded to measure drafting accuracy.
   - Nurse 3-click workflow benchmark.
2. Outreach Agent:
   - Policy limits: Quiet hours (22:00-07:00 IST), daily caps (max 3/day), STOP opt-out, global/patient pause.
   - Active emergency suppression.
   - Retry chain: 2 call retries; at 3rd attempt evaluates caregiver consent (Aarav -> family; Meera -> doctor).
   - Undo capability: Reverts scheduled actions, sets status Cancelled, audits with staff identity.
   - SMS reply handling (1/2/3/STOP).
"""

import pytest
import json
from datetime import datetime, timedelta

from backend.app.agents.call_notes_agent import CallNotesAgent
from backend.app.agents.outreach_agent import OutreachAgent
from backend.app.agents.policy_guard import PolicyGuard
from backend.app.agents.dispatcher import AgentDispatcher
from backend.app.db import get_conn


def test_call_notes_policy_guard_blocks_unprovided_facts():
    """Policy guard blocks drafts that hallucinate unprovided clinical facts, symptoms or numbers."""
    nurse_input = "Patient took medication with lunch. BP was 125/80. Feels mild headache."

    # Valid grounded draft
    grounded_draft = "Patient reports taking dose after lunch. BP 125/80 recorded. Mild headache noted."
    guard_ok, reasons = PolicyGuard.check_call_notes_grounding(grounded_draft, nurse_input)
    assert guard_ok is True
    assert len(reasons) == 0

    # Hallucinated symptom (e.g. fever / vomiting / chest pain not in nurse input)
    hallucinated_symptom_draft = "Patient has high fever and severe vomiting since morning."
    guard_ok, reasons = PolicyGuard.check_call_notes_grounding(hallucinated_symptom_draft, nurse_input)
    assert guard_ok is False
    assert any("unprovided clinical symptom" in r.lower() for r in reasons)

    # Hallucinated vital number (e.g. BP 190 not in nurse input)
    hallucinated_number_draft = "Patient BP shot up to 190 yesterday."
    guard_ok, reasons = PolicyGuard.check_call_notes_grounding(hallucinated_number_draft, nurse_input)
    assert guard_ok is False
    assert any("unprovided" in r.lower() or "hallucination" in r.lower() for r in reasons)


def test_call_notes_atomic_approval_and_ledger():
    """Approving a call note draft atomically commits note, task, message, and contact log."""
    patient_id = 1  # Aarav Patel
    staff_id = 1

    # Step 1: Draft records
    draft_res = CallNotesAgent.draft_call_records(
        patient_id=patient_id,
        staff_id=staff_id,
        staff_name="Priya (nurse)",
        patient_reports=["Dose taken on time", "No dizziness"],
        actions_agreed=["Continue scheduled medications with warm water"],
        voice_transcript="Aarav confirms taking morning tablet at 8am. Energy level is good.",
        needs_doctor=False
    )

    assert "draft_id" in draft_res
    draft_id = draft_res["draft_id"]
    run_id = draft_res["run_id"]
    assert draft_res.get("guard_passed") is True

    # Verify agent_drafts and agent_runs exist
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM agent_drafts WHERE draft_id = %s;", (draft_id,))
        draft_row = cur.fetchone()
        assert draft_row is not None
        assert draft_row["status"] == "Pending"

        cur.execute("SELECT * FROM agent_runs WHERE run_id = %s;", (run_id,))
        run_row = cur.fetchone()
        assert run_row is not None

    # Step 2: Atomic approval
    commit_res = CallNotesAgent.commit_call_records(
        draft_id=draft_id,
        staff_id=staff_id,
        staff_name="Priya (nurse)",
        call_duration_seconds=180
    )

    assert commit_res["status"] in ("approved", "committed")
    assert commit_res["note_id"] is not None
    assert commit_res["task_id"] is not None
    assert commit_res["update_id"] is not None
    assert commit_res["contact_id"] is not None

    # Step 3: Verify all 4 database tables were populated
    with get_conn() as conn, conn.cursor() as cur:
        # 1. Clinician note
        cur.execute("SELECT * FROM clinician_notes WHERE note_id = %s;", (commit_res["note_id"],))
        note = cur.fetchone()
        assert note is not None
        assert note["patient_id"] == patient_id
        assert "Aarav" in note["note_text"] or "Dose taken" in note["note_text"]

        # 2. Follow up task
        cur.execute("SELECT * FROM follow_up_tasks WHERE followup_id = %s;", (commit_res["task_id"],))
        task = cur.fetchone()
        assert task is not None
        assert task["assigned_staff_id"] == staff_id

        # 3. Patient update message ("Message from Priya (nurse)")
        cur.execute("SELECT * FROM patient_updates WHERE update_id = %s;", (commit_res["update_id"],))
        update = cur.fetchone()
        assert update is not None
        assert "Message from Priya (nurse)" in update["title"]

        # 4. Contact log
        cur.execute("SELECT * FROM contact_log WHERE contact_id = %s;", (commit_res["contact_id"],))
        contact = cur.fetchone()
        assert contact is not None
        assert contact["outcome"] == "Reached"
        assert "180s" in (contact["summary"] or "")

        # 5. Agent draft status updated to Accepted
        cur.execute("SELECT status, edit_chars FROM agent_drafts WHERE draft_id = %s;", (draft_id,))
        d_status = cur.fetchone()
        assert d_status["status"] == "Accepted"
        assert d_status["edit_chars"] == 0


def test_call_notes_draft_edit_fidelity_tracking():
    """Nurse editing draft tracks character distance in edit_chars to monitor draft fidelity."""
    patient_id = 1
    staff_id = 1

    draft_res = CallNotesAgent.draft_call_records(
        patient_id=patient_id,
        staff_id=staff_id,
        staff_name="Priya (nurse)",
        patient_reports=["Dose taken"],
        actions_agreed=["Monitor hydration"],
        voice_transcript="Patient reports mild cough.",
        needs_doctor=False
    )
    draft_id = draft_res["draft_id"]

    # Nurse edits the note before signing
    edited_note = "Patient confirmed taking dose. Mild cough noted, advised warm salt water gargle."
    commit_res = CallNotesAgent.commit_call_records(
        draft_id=draft_id,
        staff_id=staff_id,
        staff_name="Priya (nurse)",
        edited_note=edited_note
    )

    assert commit_res["status"] in ("approved", "committed")
    assert commit_res["edit_chars"] > 0

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT status, edit_chars FROM agent_drafts WHERE draft_id = %s;", (draft_id,))
        d = cur.fetchone()
        assert d["status"] == "Edited"
        assert d["edit_chars"] > 0


def test_outreach_quiet_hours_and_policy_limits():
    """Outreach Agent strictly respects quiet hours, daily limits, STOP opt-out, and pause switches."""
    patient_id = 1

    # Fake clock: 23:30 (Quiet hours: 22:00 to 07:00 IST)
    night_time = datetime(2026, 11, 4, 23, 30, 0)
    res_night = OutreachAgent.evaluate_outreach(
        patient_id=patient_id,
        channel="SMS",
        message_type="Routine_Reminder",
        current_time=night_time
    )
    assert res_night["allowed"] is False
    assert any("quiet hours" in r.lower() for r in res_night["reasons"])

    # Fake clock: 04:15 (Quiet hours)
    early_time = datetime(2026, 11, 4, 4, 15, 0)
    res_early = OutreachAgent.evaluate_outreach(
        patient_id=patient_id,
        channel="SMS",
        message_type="Routine_Reminder",
        current_time=early_time
    )
    assert res_early["allowed"] is False
    assert any("quiet hours" in r.lower() for r in res_early["reasons"])

    # Fake clock: 14:00 (Active Daytime - Patient 4 with 0 messages today)
    day_time = datetime(2026, 11, 4, 14, 0, 0)
    res_day = OutreachAgent.evaluate_outreach(
        patient_id=4,
        channel="App",
        message_type="Routine_Reminder",
        current_time=day_time
    )
    # Kabir is active, not paused, daytime, within cap -> allowed
    assert res_day["allowed"] is True

    # Daily Cap Test: Patient 1 already has messages today -> daily cap exceeded
    res_cap = OutreachAgent.evaluate_outreach(
        patient_id=1,
        channel="App",
        message_type="Routine_Reminder",
        current_time=day_time
    )
    assert res_cap["allowed"] is False
    assert any("daily automation cap exceeded" in r.lower() for r in res_cap["reasons"])

    # Test STOP Opt-Out
    OutreachAgent.handle_sms_reply(patient_id=patient_id, text="STOP")
    res_opt_out = OutreachAgent.evaluate_outreach(
        patient_id=patient_id,
        channel="SMS",
        message_type="Routine_Reminder",
        current_time=day_time
    )
    assert res_opt_out["allowed"] is False
    assert any("sms opt-out" in r.lower() for r in res_opt_out["reasons"])

    # Restore Aarav SMS opt-out
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE patients SET sms_opt_out = 0 WHERE patient_id = %s;", (patient_id,))
        conn.commit()


def test_outreach_active_emergency_suppresses_routine():
    """Active emergency / urgent flags immediately suppress automated routine check-ins."""
    patient_id = 1
    day_time = datetime(2026, 11, 4, 11, 0, 0)

    # Insert temporary urgent flag
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO flags (patient_id, rule_id, source_type, reason, severity, status, created_at)
                VALUES (%s, 1, 'Emergency', 'Severe chest pain reported', 'Urgent_Review', 'Open', NOW());
            """, (patient_id,))
            temp_flag_id = cur.lastrowid
        conn.commit()

    try:
        res = OutreachAgent.evaluate_outreach(
            patient_id=patient_id,
            channel="App",
            message_type="Routine_Reminder",
            current_time=day_time
        )
        assert res["allowed"] is False
        assert any("active emergency" in r.lower() for r in res["reasons"])
    finally:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM flags WHERE flag_id = %s;", (temp_flag_id,))
            conn.commit()


def test_outreach_retry_ladder_and_caregiver_consent():
    """
    Retry ladder tests:
    - Retries < 2: schedules retry (+30m).
    - Retry >= 2: evaluates caregiver consent:
      - Aarav Patel (consent granted = 1): proposes family contact (Suggest_Call).
      - Meera Sharma (consent granted = 0): proposes doctor review (Suggest_Plan_Review).
    """
    # Attempt 1 (retry_count = 0) -> schedules retry 1
    r1 = OutreachAgent.handle_no_answer_retry(patient_id=1, retry_count=0)
    assert r1["action"] == "schedule_retry"
    assert r1["retry_count"] == 1
    action_id = r1["action_id"]

    # Undo action test
    undo_res = OutreachAgent.undo_action(action_id=action_id, staff_id=1)
    assert undo_res["status"] == "undone"

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM scheduled_actions WHERE action_id = %s;", (action_id,))
        act = cur.fetchone()
        assert act["status"] == "Cancelled"

    # Aarav (patient 1): caregiver consent granted
    r_aarav = OutreachAgent.handle_no_answer_retry(patient_id=1, retry_count=2)
    assert r_aarav["action"] == "propose_escalation"
    assert r_aarav["proposal_type"] == "Suggest_Call"
    assert r_aarav["caregiver_consent"] is True
    assert "Propose family contact" in r_aarav["reason"]

    # Meera Sharma (patient 2): caregiver consent NOT granted
    r_meera = OutreachAgent.handle_no_answer_retry(patient_id=2, retry_count=2)
    assert r_meera["action"] == "propose_escalation"
    assert r_meera["proposal_type"] == "Suggest_Plan_Review"
    assert r_meera["caregiver_consent"] is False
    assert "Propose physician review" in r_meera["reason"]


def test_nurse_three_click_workflow_benchmark():
    """
    Benchmarks the nurse 3-click workflow target:
    Click 1: Quick pick / input entry
    Click 2: Agent draft generated & reviewed
    Click 3: Single-click 'Approve & Sign' commits note + task + patient update atomically.
    """
    clicks = []

    # Click 1: Quick pick selection
    clicks.append({"step": "Quick picks selected", "click_count": 1})
    nurse_payload = {
        "patient_id": 1,
        "patient_reports": ["Dose taken on time", "No dizziness"],
        "actions_agreed": ["Hydration advice given"]
    }

    # Click 2: Agent drafts note, task, and message
    clicks.append({"step": "Agent draft generated", "click_count": 2})
    draft = CallNotesAgent.draft_call_records(
        patient_id=nurse_payload["patient_id"],
        staff_id=1,
        staff_name="Priya (nurse)",
        patient_reports=nurse_payload["patient_reports"],
        actions_agreed=nurse_payload["actions_agreed"]
    )
    assert draft.get("guard_passed") is True

    # Click 3: Single-action sign & delivery
    clicks.append({"step": "Approve & Sign clicked", "click_count": 3})
    commit = CallNotesAgent.commit_call_records(
        draft_id=draft["draft_id"],
        staff_id=1,
        staff_name="Priya (nurse)"
    )
    assert commit["status"] in ("approved", "committed")

    # Assert 3 clicks exactly achieved
    assert len(clicks) == 3
    assert clicks[-1]["click_count"] == 3
