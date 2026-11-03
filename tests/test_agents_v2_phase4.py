"""
tests/test_agents_v2_phase4.py — CareLoop Agents v2 Phase 4 Test Suite
Validates:
1. Case state machine transitions, SLA timers with a fake clock, and transition history logging.
2. Prevention of skipped states and strict prohibition of agent actions on Closed cases.
3. Explainable queue ordering matching the exact fixed-weight factor table (no ML).
4. Routine drafts diff view, nurse edit preservation, and strict batch approval threshold (>= 95%).
"""

import json
from datetime import datetime, timedelta
import pytest

from backend.app.db import get_conn
from backend.app.agents.config import (
    CASE_SLA_SECONDS,
    CASE_QUEUE_WEIGHTS,
    AGENTS_V2_BATCH_APPROVAL_THRESHOLD,
    BATCH_APPROVED_DRAFT_TYPES
)
from backend.app.agents.case_workflow_service import (
    CaseWorkflowService,
    ExplainableQueueService,
    RoutineDraftReviewService
)


@pytest.fixture
def setup_test_case():
    """Seeds a dedicated test case for workflow state machine validation."""
    test_case_id = "case-eval-p4-state-001"
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM case_workflow_transitions WHERE case_id = %s;", (test_case_id,))
        cur.execute("DELETE FROM case_workflows WHERE case_id = %s;", (test_case_id,))
        cur.execute("DELETE FROM cases WHERE case_id = %s;", (test_case_id,))
        cur.execute("""
            INSERT INTO cases (case_id, patient_id, primary_flag_id, status, merged_count, created_at, updated_at)
            VALUES (%s, 1, 1, 'Open', 1, NOW(), NOW());
        """, (test_case_id,))
        conn.commit()

    yield test_case_id

    # Cleanup
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM case_workflow_transitions WHERE case_id = %s;", (test_case_id,))
        cur.execute("DELETE FROM case_workflows WHERE case_id = %s;", (test_case_id,))
        cur.execute("DELETE FROM cases WHERE case_id = %s;", (test_case_id,))
        conn.commit()


def test_phase4_case_state_machine_and_fake_clock_sla(setup_test_case):
    """Verify transitions and SLA timers with a fake clock: Raised -> Briefed -> Contacting -> Waiting_For_Doctor -> Decided -> Closed."""
    case_id = setup_test_case
    base_time = datetime(2026, 11, 4, 10, 0, 0)

    # 1. Initialize case workflow at 10:00:00
    st = CaseWorkflowService.initialize_case_workflow(case_id, fake_clock=base_time)
    assert st["state"] == "Raised"
    assert st["sla_seconds"] == CASE_SLA_SECONDS["Raised"]  # 900s = 15m
    assert st["is_overdue"] is False

    # 2. Advance clock by 10m (600s): Under SLA limit
    clock_10m = base_time + timedelta(minutes=10)
    st_10m = CaseWorkflowService.get_case_state(case_id, fake_clock=clock_10m)
    assert st_10m["elapsed_seconds"] == 600
    assert st_10m["remaining_seconds"] == 300
    assert st_10m["is_overdue"] is False

    # 3. Advance clock by 16m (960s): Overdue!
    clock_16m = base_time + timedelta(minutes=16)
    st_16m = CaseWorkflowService.get_case_state(case_id, fake_clock=clock_16m)
    assert st_16m["elapsed_seconds"] == 960
    assert st_16m["remaining_seconds"] == 0
    assert st_16m["is_overdue"] is True

    # 4. Valid transition: Raised -> Briefed
    t_briefed = CaseWorkflowService.transition_case(
        case_id=case_id,
        to_state="Briefed",
        actor_type="Agent",
        reason="Synthesized 5-part Case Prep brief",
        fake_clock=clock_16m
    )
    assert t_briefed["state"] == "Briefed"
    assert t_briefed["sla_seconds"] == CASE_SLA_SECONDS["Briefed"]  # 1800s = 30m
    assert t_briefed["is_overdue"] is False

    # 5. Valid transition: Briefed -> Contacting
    clock_briefed = clock_16m + timedelta(minutes=5)
    t_contact = CaseWorkflowService.transition_case(
        case_id=case_id,
        to_state="Contacting",
        actor_type="Staff",
        actor_id=2,
        reason="Nurse initiating contact call",
        fake_clock=clock_briefed
    )
    assert t_contact["state"] == "Contacting"

    # 6. Valid transition: Contacting -> Waiting_For_Doctor
    clock_waiting = clock_briefed + timedelta(minutes=10)
    t_wait = CaseWorkflowService.transition_case(
        case_id=case_id,
        to_state="Waiting_For_Doctor",
        actor_type="Staff",
        actor_id=2,
        reason="Escalated to attending physician",
        fake_clock=clock_waiting
    )
    assert t_wait["state"] == "Waiting_For_Doctor"

    # 7. Valid transition: Waiting_For_Doctor -> Decided
    clock_decided = clock_waiting + timedelta(minutes=15)
    t_decide = CaseWorkflowService.transition_case(
        case_id=case_id,
        to_state="Decided",
        actor_type="Staff",
        actor_id=1,
        reason="Doctor decided follow-up clinical protocol",
        fake_clock=clock_decided
    )
    assert t_decide["state"] == "Decided"

    # 8. Valid transition: Decided -> Closed
    clock_closed = clock_decided + timedelta(minutes=5)
    t_close = CaseWorkflowService.transition_case(
        case_id=case_id,
        to_state="Closed",
        actor_type="Staff",
        actor_id=1,
        reason="Patient stable, flag resolved",
        fake_clock=clock_closed
    )
    assert t_close["state"] == "Closed"
    assert t_close["transitions_count"] == 5

    print("  ✓ State machine lifecycle and SLA fake-clock calculations validated across 5 transitions.")


def test_phase4_state_machine_strict_no_skip_and_closed_prohibition(setup_test_case):
    """Verify state skipping is rejected and agents/staff cannot act on Closed cases without reopening."""
    case_id = setup_test_case
    base_time = datetime(2026, 11, 4, 11, 0, 0)
    CaseWorkflowService.initialize_case_workflow(case_id, fake_clock=base_time)

    # Attempt to skip from Raised directly to Closed
    with pytest.raises(ValueError) as exc:
        CaseWorkflowService.transition_case(case_id, "Closed", actor_type="Staff")
    assert "State Machine Violation" in str(exc.value)

    # Attempt to skip from Raised directly to Decided
    with pytest.raises(ValueError) as exc2:
        CaseWorkflowService.transition_case(case_id, "Decided", actor_type="Staff")
    assert "State Machine Violation" in str(exc2.value)

    # Transition cleanly to Closed via allowed path
    CaseWorkflowService.transition_case(case_id, "Briefed", actor_type="Agent")
    CaseWorkflowService.transition_case(case_id, "Decided", actor_type="Staff", actor_id=1)
    CaseWorkflowService.transition_case(case_id, "Closed", actor_type="Staff", actor_id=1)

    # Once Closed: Agent step attachment MUST fail
    with pytest.raises(ValueError) as exc_agent:
        CaseWorkflowService.attach_agent_step(
            case_id=case_id,
            run_id="run-closed-prohibited-001",
            step_name="OutreachAttempt",
            details={"attempt": 1}
        )
    assert "Agent cannot act or attach steps to Closed case" in str(exc_agent.value)

    # Once Closed: Direct transition to any state except Reopened MUST fail
    with pytest.raises(ValueError) as exc_staff:
        CaseWorkflowService.transition_case(case_id, "Decided", actor_type="Staff")
    assert "Cannot act on a Closed case without reopening" in str(exc_staff.value)

    # Transition Closed -> Reopened
    t_reopen = CaseWorkflowService.transition_case(
        case_id=case_id,
        to_state="Reopened",
        actor_type="Staff",
        actor_id=1,
        reason="New symptom exacerbation reported"
    )
    assert t_reopen["state"] == "Reopened"

    # Now agent step attachment succeeds
    step_res = CaseWorkflowService.attach_agent_step(
        case_id=case_id,
        run_id="run-reopened-allowed-001",
        step_name="ReopenedCasePrep",
        details={"status": "resumed"}
    )
    assert step_res["status"] == "attached"

    print("  ✓ State skipping forbidden and Closed case safety boundaries strictly enforced.")


def test_phase4_explainable_queue_order_factor_table():
    """Verify explainable score calculation matches the exact fixed-weight factor table (zero ML)."""
    # Profile 1: Critical Emergency (Immediate + Overdue >120m + SOS)
    p1 = {
        "tier": "Immediate",        # +100
        "minutes_overdue": 140,     # +40
        "no_answers_count": 0,
        "device_silent_hours": 0,
        "consent_missing": False,
        "has_sos": True,            # +150
        "photo_pending": False
    }
    score1, f1 = ExplainableQueueService.compute_explainable_score(p1)
    assert score1 == 290
    assert len(f1) == 3

    # Profile 2: Urgent Review (Urgent + Overdue 35m + 2 No-Answers)
    p2 = {
        "tier": "Urgent",           # +50
        "minutes_overdue": 35,      # +15 (30-60m bucket)
        "no_answers_count": 2,      # 2 * 15 = +30
        "device_silent_hours": 0,
        "consent_missing": False,
        "has_sos": False,
        "photo_pending": False
    }
    score2, f2 = ExplainableQueueService.compute_explainable_score(p2)
    assert score2 == 95
    assert len(f2) == 3

    # Profile 3: Moderate (Review Soon + Device Silent 26h + Photo Pending)
    p3 = {
        "tier": "Review_Soon",      # +20
        "minutes_overdue": 10,      # <15m = +0
        "no_answers_count": 0,
        "device_silent_hours": 26,  # >24h = +30
        "consent_missing": False,
        "has_sos": False,
        "photo_pending": True       # +25
    }
    score3, f3 = ExplainableQueueService.compute_explainable_score(p3)
    assert score3 == 75
    assert len(f3) == 3

    # Profile 4: Routine with Consent Missing Penalty
    p4 = {
        "tier": "Routine",          # +0
        "minutes_overdue": 0,
        "no_answers_count": 0,
        "device_silent_hours": 0,
        "consent_missing": True,    # -20
        "has_sos": False,
        "photo_pending": False
    }
    score4, f4 = ExplainableQueueService.compute_explainable_score(p4)
    assert score4 == -20
    assert len(f4) == 1
    assert "consent missing" in f4[0]["factor"].lower()

    # Queue ordering test: Score 1 > Score 2 > Score 3 > Score 4
    queue = [p4, p2, p1, p3]
    queue.sort(key=lambda p: ExplainableQueueService.compute_explainable_score(p)[0], reverse=True)
    assert queue[0] == p1
    assert queue[1] == p2
    assert queue[2] == p3
    assert queue[3] == p4

    print("  ✓ Explainable queue order factors match fixed weights: P1(290) > P2(95) > P3(75) > P4(-20).")


def test_phase4_routine_drafts_diff_and_batch_approval_threshold():
    """Verify unified diff view and batch approval safety gate (impossible below 95% threshold)."""
    # 1. Diff view test
    orig = "Hello Aarav, your morning aspirin dose is due."
    edited = "Hello Aarav, please take your 75mg aspirin with water right away."
    diff_res = RoutineDraftReviewService.compute_text_diff(orig, edited)

    assert diff_res["has_changes"] is True
    assert diff_res["edit_chars"] > 0
    assert "+++ Human Clinician Edit" in diff_res["diff_unified"]

    # 2. Batch approval below threshold test (simulate draft type below 95%)
    # Handoff agreement rate or unapproved draft type
    with pytest.raises(ValueError) as exc:
        # Handoff is NOT in BATCH_APPROVED_DRAFT_TYPES
        RoutineDraftReviewService.batch_approve_drafts_of_type(
            draft_type="Handoff",
            staff_id=1,
            staff_account_id=1
        )
    assert "Batch approval impossible" in str(exc.value)

    # 3. Seed test draft for Patient_Message in 'Pending' status
    test_run_id = "run-test-batch-001"
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO agent_drafts (run_id, patient_id, draft_type, body, sources, status, created_at)
            VALUES (%s, 1, 'Patient_Message', %s, %s, 'Pending', NOW());
        """, (
            test_run_id,
            json.dumps({"message": "Routine checkin reminder for Aarav"}),
            json.dumps(["test_source"])
        ))
        test_draft_id = cur.lastrowid
        conn.commit()

    try:
        # Batch approval of Patient_Message (in BATCH_APPROVED_DRAFT_TYPES with agreement >= 95%)
        batch_res = RoutineDraftReviewService.batch_approve_drafts_of_type(
            draft_type="Patient_Message",
            staff_id=1,
            staff_account_id=1
        )
        assert batch_res["status"] == "ok"
        assert batch_res["audited_item_by_item"] is True
        assert test_draft_id in batch_res["approved_ids"]

        # Verify draft was transitioned to 'Accepted'
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT status, reviewed_by_staff_id FROM agent_drafts WHERE draft_id = %s;", (test_draft_id,))
            d_row = cur.fetchone()
            assert d_row["status"] == "Accepted"
            assert d_row["reviewed_by_staff_id"] == 1

        print("  ✓ Batch approval safety gate enforced: rejected for unapproved/low-agreement, approved with item audit.")
    finally:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM agent_drafts WHERE draft_id = %s;", (test_draft_id,))
            conn.commit()


def test_phase4_nurse_draft_edit_stores_diff_and_exemplar():
    """Verify nurse's edit preserves the unified diff and original draft text for Phase 5 exemplars."""
    test_draft_id = None
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO agent_drafts (run_id, patient_id, draft_type, body, sources, status, created_at)
            VALUES ('run-test-edit-001', 1, 'Call_Note', %s, %s, 'Pending', NOW());
        """, (
            json.dumps({"note": "Patient reports minor discomfort post-walk"}),
            json.dumps(["test_eval"])
        ))
        test_draft_id = cur.lastrowid
        conn.commit()

    try:
        # Nurse Priya (staff_id=2) edits the draft
        edited_payload = {
            "note": "Patient reports mild 2/10 sternal pain during 15-min morning walk. Relieved with rest. Advised to stay within limits."
        }
        res = RoutineDraftReviewService.record_draft_edit(
            draft_id=test_draft_id,
            edited_body=edited_payload,
            staff_id=2,
            staff_account_id=2
        )
        assert res["status"] == "ok"
        assert res["new_status"] == "Edited"
        assert res["edit_chars"] > 0
        assert "sternal pain" in res["diff_summary"]

        # Inspect database record
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT body, status, edit_chars FROM agent_drafts WHERE draft_id = %s;", (test_draft_id,))
            row = cur.fetchone()
            assert row["status"] == "Edited"
            saved_body = row["body"]
            if isinstance(saved_body, str):
                saved_body = json.loads(saved_body)

            assert "_exemplar_metadata" in saved_body
            meta = saved_body["_exemplar_metadata"]
            assert meta["edited_by_staff_id"] == 2
            assert "diff_unified" in meta
            assert "minor discomfort" in meta["original_text"]
            assert "mild 2/10 sternal pain" in meta["edited_text"]

        print("  ✓ Nurse edit stored with complete diff metadata and original baseline for Phase 5 exemplar retrieval.")
    finally:
        if test_draft_id:
            with get_conn() as conn, conn.cursor() as cur:
                cur.execute("DELETE FROM agent_drafts WHERE draft_id = %s;", (test_draft_id,))
                conn.commit()
