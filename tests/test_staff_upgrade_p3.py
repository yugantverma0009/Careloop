"""
tests/test_staff_upgrade_p3.py

Tests for Care Team Portal Phase 3 (Features D-07 Task Queue and D-08 Clinical Summaries).
Covers:
- D-07 Task Queue listing, identity badges, priority labels, overdue computation
- D-07 Filters (scope, priority, status, overdue)
- D-07 Task lifecycle actions: claim, assign, snooze, complete with outcome codes & audit
- D-08 Deterministic fact sheet (anonymized, no patient names sent)
- D-08 Mandatory guard against 11 banned judgment words and hallucinated numbers
- D-08 SBAR Draft generation & storage
- D-08 Doctor approval & edit in place (Nurse gets 403 Forbidden)
- D-08 Doctor rejection with mandatory clinical reason (Nurse gets 403 Forbidden)
"""

import pytest
import json
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import get_conn
from backend.app.auth import make_token
from backend.app.clinical_summaries import (
    build_deterministic_fact_sheet,
    run_summary_guard,
    generate_fallback_summary,
    BANNED_WORDS,
)

client = TestClient(app)

# Test Tokens
doctor_token = make_token({
    "account_id": 3,
    "email": "ananya.demo@example.test",
    "account_role": "Doctor",
    "patient_id": None,
    "caregiver_id": None,
    "staff_id": 1,
})
nurse_token = make_token({
    "account_id": 4,
    "email": "priya.demo@example.test",
    "account_role": "Nurse",
    "patient_id": None,
    "caregiver_id": None,
    "staff_id": 3,
})
doc_headers = {"Authorization": f"Bearer {doctor_token}"}
nurse_headers = {"Authorization": f"Bearer {nurse_token}"}


def test_d07_task_queue_listing():
    """D-07: Queue returns tasks with patient identity, human priority, and overdue state."""
    resp = client.get("/staff/tasks?scope=all&status=all", headers=nurse_headers)
    assert resp.status_code == 200
    tasks = resp.json()
    assert len(tasks) > 0

    first = tasks[0]
    assert "followup_id" in first
    assert "patient_id" in first
    assert "patient_code" in first
    assert first["patient_code"].startswith("CL-")
    assert "patient_name" in first
    assert "age_years" in first
    assert "priority" in first
    assert first["priority_label"] in ["Urgent", "Review soon", "Routine"]
    assert "status" in first
    assert "is_overdue" in first
    assert "overdue_label" in first


def test_d07_task_filters():
    """D-07: Test queue filtering by priority, scope, and status."""
    # Priority filter
    resp = client.get("/staff/tasks?scope=all&priority=Urgent_Review", headers=doc_headers)
    assert resp.status_code == 200
    for t in resp.json():
        assert t["priority"] == "Urgent_Review"
        assert t["priority_label"] == "Urgent"

    # Pending status filter
    resp = client.get("/staff/tasks?scope=all&status=pending", headers=doc_headers)
    assert resp.status_code == 200
    for t in resp.json():
        assert t["status"] != "Resolved"

    # Mine filter for doctor (staff_id=1)
    resp = client.get("/staff/tasks?scope=mine", headers=doc_headers)
    assert resp.status_code == 200
    for t in resp.json():
        assert t["assigned_staff_id"] == 1

    # Query param tolerance test (prevents 422 on undefined or team scope)
    resp_tol = client.get("/staff/tasks?scope=team&status=pending&priority=all&search=&overdue=undefined", headers=doc_headers)
    assert resp_tol.status_code == 200
    assert len(resp_tol.json()) > 0


def test_d07_task_claim_assign_snooze():
    """D-07: Claim, assign, and snooze task workflow."""
    # Get a pending task
    resp = client.get("/staff/tasks?scope=all&status=pending", headers=doc_headers)
    assert resp.status_code == 200
    tasks = resp.json()
    task_id = tasks[0]["followup_id"]

    # 1. Claim task
    c_resp = client.post(f"/staff/tasks/{task_id}/claim", headers=doc_headers)
    assert c_resp.status_code == 200
    assert c_resp.json()["assigned_staff_id"] == 1

    # 2. Assign task to nurse 3
    a_resp = client.post(
        f"/staff/tasks/{task_id}/assign",
        json={"target_staff_id": 3, "note": "Please check on patient this afternoon"},
        headers=doc_headers,
    )
    assert a_resp.status_code == 200
    assert a_resp.json()["assigned_staff_id"] == 3

    # 3. Snooze task
    s_resp = client.post(
        f"/staff/tasks/{task_id}/snooze",
        json={"hours": 4, "reason": "Patient resting post-medication"},
        headers=nurse_headers,
    )
    assert s_resp.status_code == 200
    assert s_resp.json()["status"] == "snoozed"

    # Validation: Snooze requires valid reason
    bad_snooze = client.post(
        f"/staff/tasks/{task_id}/snooze",
        json={"hours": 4, "reason": "  "},
        headers=nurse_headers,
    )
    assert bad_snooze.status_code == 400


def test_d07_task_complete_with_outcomes_and_audit():
    """D-07: Completing task requires valid outcome code and records audit trail."""
    # Find or create a pending task
    resp = client.get("/staff/tasks?scope=all&status=pending", headers=doc_headers)
    task_id = resp.json()[-1]["followup_id"]

    # Invalid outcome code rejected
    bad_resp = client.post(
        f"/staff/tasks/{task_id}/complete",
        json={"outcome_code": "DidNothing", "outcome_notes": "test"},
        headers=nurse_headers,
    )
    assert bad_resp.status_code == 400

    # Valid outcome code succeeds
    good_resp = client.post(
        f"/staff/tasks/{task_id}/complete",
        json={
            "outcome_code": "Reached_And_Advised",
            "outcome_notes": "Patient advised on morning insulin timing and confirmed symptom resolution.",
        },
        headers=nurse_headers,
    )
    assert good_resp.status_code == 200
    assert good_resp.json()["status"] == "completed"

    # Verify audit trail
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT action, entity_type, entity_id, details
               FROM audit_log
               WHERE entity_type = 'task' AND entity_id = %s
               ORDER BY log_id DESC LIMIT 1""",
            (task_id,),
        )
        row = cur.fetchone()
        assert row is not None
        assert row["action"] == "COMPLETE_TASK"
        details = json.loads(row["details"]) if isinstance(row["details"], str) else row["details"]
        assert details["outcome_code"] == "Reached_And_Advised"


def test_d08_deterministic_fact_sheet_anonymization():
    """D-08: Fact sheet strictly anonymizes patient to 'the patient' and never leaks names."""
    with get_conn() as conn:
        fact_sheet = build_deterministic_fact_sheet(conn, 1, "2026-10-29")
        assert "patient_code" in fact_sheet
        assert fact_sheet["patient_code"] == "CL-00001"
        assert "condition" in fact_sheet
        assert "total_medications_scheduled" in fact_sheet
        assert "latest_readings" in fact_sheet
        # Full name must NOT appear as a key in the fact sheet
        assert "full_name" not in fact_sheet
        assert "patient_name" not in fact_sheet


def test_d08_summary_guard_safety():
    """D-08: Mandatory guard flags banned judgment words and hallucinated numbers."""
    fact_sheet = {
        "day_number": 3,
        "condition": "Post-CABG",
        "open_flag_reasons": ["High systolic blood pressure"],
        "open_task_texts": ["Review beta-blocker adherence"],
        "total_doses_taken": 2,
    }

    # 1. Banned word violation
    for word in BANNED_WORDS:
        draft = {
            "situation": f"The patient is {word}.",
            "background": "Post-CABG recovery.",
            "assessment_facts": ["2 doses taken."],
            "items_for_review": ["High systolic blood pressure"],
        }
        passed, reason = run_summary_guard(draft, fact_sheet)
        assert passed is False
        assert f"banned_word_{word}" == reason or reason.startswith("banned_word")

    # 2. Hallucinated number violation (e.g. 999 not in fact sheet)
    hallucinated_draft = {
        "situation": "The patient is on post-discharge day 3.",
        "background": "Post-CABG recovery.",
        "assessment_facts": ["Heart rate was 999 bpm."],
        "items_for_review": ["High systolic blood pressure"],
    }
    passed, reason = run_summary_guard(hallucinated_draft, fact_sheet)
    assert passed is False
    assert "numbers_not_in_facts" in reason

    # 3. Clean fallback generation
    fallback = generate_fallback_summary(fact_sheet)
    assert "situation" in fallback
    assert "background" in fallback
    assert "assessment_facts" in fallback
    assert "items_for_review" in fallback
    clean_text = " ".join([fallback["situation"], fallback["background"], *fallback["assessment_facts"]]).lower()
    for w in BANNED_WORDS:
        assert w not in clean_text


def test_d08_summary_generation_endpoint():
    """D-08: POST /staff/summaries/generate creates structured draft with snapshot."""
    resp = client.post(
        "/staff/summaries/generate",
        json={"patient_id": 1, "target_date": "2026-10-29"},
        headers=doc_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "summary_id" in data
    assert data["status"] == "Draft"
    assert data["status_label"] == "AI draft, not reviewed"
    assert "parsed_sbar" in data
    assert "source_snapshot" in data
    assert "situation" in data["parsed_sbar"]
    assert "assessment_facts" in data["parsed_sbar"]


def test_d08_doctor_approves_summary():
    """D-08: Doctor can approve clinical summary with optional edit text."""
    # Generate a draft
    g_resp = client.post(
        "/staff/summaries/generate",
        json={"patient_id": 2, "target_date": "2026-10-29"},
        headers=doc_headers,
    )
    assert g_resp.status_code == 200
    summary_id = g_resp.json()["summary_id"]

    # Approve as Doctor
    a_resp = client.post(
        f"/staff/summaries/{summary_id}/approve",
        json={"edited_text": "Clinician verified. Patient progressing per pathway guidelines."},
        headers=doc_headers,
    )
    assert a_resp.status_code == 200
    assert a_resp.json()["status"] == "Approved"

    # Verify status in listing
    l_resp = client.get(f"/staff/summaries?patient_id=2", headers=doc_headers)
    assert l_resp.status_code == 200
    sums = [s for s in l_resp.json() if s["summary_id"] == summary_id]
    assert len(sums) == 1
    assert sums[0]["status"] == "Approved"
    assert "Approved by Dr." in sums[0]["status_label"]


def test_d08_nurse_cannot_approve_or_reject_summary():
    """D-08 & D-12: Nurse receives 403 Forbidden when attempting to approve or reject."""
    # Generate draft
    g_resp = client.post(
        "/staff/summaries/generate",
        json={"patient_id": 3, "target_date": "2026-10-29"},
        headers=nurse_headers,
    )
    assert g_resp.status_code == 200
    summary_id = g_resp.json()["summary_id"]

    # Nurse approval attempt -> 403
    appr_resp = client.post(
        f"/staff/summaries/{summary_id}/approve",
        json={"edited_text": "Nurse note"},
        headers=nurse_headers,
    )
    assert appr_resp.status_code == 403

    # Nurse rejection attempt -> 403
    rej_resp = client.post(
        f"/staff/summaries/{summary_id}/reject",
        json={"reason": "Incorrect facts"},
        headers=nurse_headers,
    )
    assert rej_resp.status_code == 403


def test_d08_doctor_rejects_summary_with_reason():
    """D-08: Doctor can reject clinical summary with required reason."""
    # Generate draft
    g_resp = client.post(
        "/staff/summaries/generate",
        json={"patient_id": 4, "target_date": "2026-10-29"},
        headers=doc_headers,
    )
    assert g_resp.status_code == 200
    summary_id = g_resp.json()["summary_id"]

    # Missing/empty reason -> 400
    bad_rej = client.post(
        f"/staff/summaries/{summary_id}/reject",
        json={"reason": " "},
        headers=doc_headers,
    )
    assert bad_rej.status_code == 400

    # Valid rejection
    good_rej = client.post(
        f"/staff/summaries/{summary_id}/reject",
        json={"reason": "Incomplete medication confirmation for evening dose."},
        headers=doc_headers,
    )
    assert good_rej.status_code == 200
    assert good_rej.json()["status"] == "Rejected"
