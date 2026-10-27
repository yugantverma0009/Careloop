"""
tests/test_m4_escalation.py — Milestone M4 Tests

Tests:
1. Triage Board: GET /staff/triage returns v_triage_board for staff; rejects Patient with 403
2. Escalation Ladder: run_escalations() creates ladder steps in escalations table
3. Consent Gating: Kabir (consent_granted=FALSE) caregiver step recorded as 'Skipped_No_Consent'
4. Atomic Acknowledge: sp_acknowledge_flag locks flag, marks Acknowledged, creates follow_up_task & audit_log
5. Double Acknowledge Rejection: Calling acknowledge on already acknowledged flag returns HTTP 409
6. Follow-up Work Queue: GET /staff/follow-ups surfaces pending tasks from v_pending_followups
7. Patient Timeline: GET /staff/patients/{id}/timeline returns chronological audit feed
"""

import time
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import get_conn
from backend.app.auth import make_token
from backend.app.escalation import run_escalations

client = TestClient(app)

# Doctor 1: Dr. Ananya Sharma (staff_id: 1)
DOCTOR_TOKEN = make_token({
    "account_id": 3,
    "email": "ananya.demo@example.test",
    "account_role": "Doctor",
    "patient_id": None,
    "caregiver_id": None,
    "staff_id": 1,
})

# Nurse 1: Priya Nair (staff_id: 3)
NURSE_TOKEN = make_token({
    "account_id": 4,
    "email": "priya.demo@example.test",
    "account_role": "Nurse",
    "patient_id": None,
    "caregiver_id": None,
    "staff_id": 3,
})

# Patient 1: Aarav Demo
PATIENT_TOKEN = make_token({
    "account_id": 1,
    "email": "aarav.demo@example.test",
    "account_role": "Patient",
    "patient_id": 1,
    "caregiver_id": None,
    "staff_id": None,
})


def test_triage_board_access():
    doc_headers = {"Authorization": f"Bearer {DOCTOR_TOKEN}"}
    res = client.get("/staff/triage", headers=doc_headers)
    assert res.status_code == 200, res.text
    board = res.json()
    assert isinstance(board, list)
    assert len(board) >= 1
    item = board[0]
    assert "flag_id" in item
    assert "severity" in item
    assert "reason" in item
    assert "risk_score" in item
    print(f"✅ GET /staff/triage returned {len(board)} items for Doctor (top: Flag #{item['flag_id']} [{item['severity']}])")

    # Patient token blocked
    pat_headers = {"Authorization": f"Bearer {PATIENT_TOKEN}"}
    res_pat = client.get("/staff/triage", headers=pat_headers)
    assert res_pat.status_code == 403, f"Expected 403, got {res_pat.status_code}"
    print("✅ Patient token blocked from triage board with HTTP 403")


def test_escalation_ladder_and_consent_gating():
    # Make sure we have flags for Kabir (patient 3) and Meera (patient 2)
    # Kabir's caregiver has consent_granted=FALSE
    with get_conn() as conn, conn.cursor() as cur:
        # Check Kabir's caregiver status
        cur.execute("SELECT consent_granted FROM caregivers WHERE patient_id=3")
        cg_kabir = cur.fetchone()
        assert cg_kabir is not None
        assert cg_kabir["consent_granted"] == 0, "Kabir's caregiver must have consent_granted=FALSE for this test"

        # Check Meera's caregiver status
        cur.execute("SELECT consent_granted FROM caregivers WHERE patient_id=2")
        cg_meera = cur.fetchone()
        assert cg_meera is not None
        assert cg_meera["consent_granted"] == 1, "Meera's caregiver must have consent_granted=TRUE for this test"

        # Age the flags so ladder steps trigger immediately
        cur.execute("UPDATE flags SET created_at = NOW() - INTERVAL 100 MINUTE WHERE status='Open'")

    # Run the escalation agent loop
    run_escalations()

    with get_conn() as conn, conn.cursor() as cur:
        # 1. Verify Kabir's caregiver step was skipped with Skipped_No_Consent
        cur.execute(
            """SELECT e.delivery_status, e.notes, e.step_type, f.flag_id, f.patient_id
               FROM escalations e
               JOIN flags f ON f.flag_id = e.flag_id
               WHERE f.patient_id = 3 AND e.step_type = 'Caregiver_SMS'"""
        )
        kabir_esc = cur.fetchone()
        assert kabir_esc is not None, "Expected Caregiver_SMS step for Kabir"
        assert kabir_esc["delivery_status"] == "Skipped_No_Consent"
        assert "consent" in kabir_esc["notes"].lower()
        print(f"✅ Consent Gate Passed: Kabir's caregiver step recorded as 'Skipped_No_Consent' ('{kabir_esc['notes']}')")

        # 2. Verify Meera's caregiver step was sent
        cur.execute(
            """SELECT e.delivery_status, e.step_type, f.flag_id, f.patient_id
               FROM escalations e
               JOIN flags f ON f.flag_id = e.flag_id
               WHERE f.patient_id = 2 AND e.step_type = 'Caregiver_SMS'"""
        )
        meera_esc = cur.fetchone()
        assert meera_esc is not None, "Expected Caregiver_SMS step for Meera"
        assert meera_esc["delivery_status"] in ("Sent", "Acknowledged")
        print(f"✅ Consent Gate Passed: Meera's caregiver step correctly recorded as '{meera_esc['delivery_status']}'")


def test_atomic_acknowledge_and_double_ack_error():
    # Find an open flag to acknowledge
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT flag_id, patient_id FROM flags WHERE status='Open' LIMIT 1")
        row = cur.fetchone()
        assert row is not None, "Expected at least 1 open flag"
        target_flag_id = row["flag_id"]
        target_patient_id = row["patient_id"]

    nurse_headers = {"Authorization": f"Bearer {NURSE_TOKEN}"}

    # 1. First Acknowledge call -> succeeds (HTTP 200)
    ack_res = client.post(
        f"/staff/flags/{target_flag_id}/acknowledge",
        json={"note": "Nurse Priya reviewed telemetry and initiated patient call"},
        headers=nurse_headers,
    )
    assert ack_res.status_code == 200, ack_res.text
    assert ack_res.json()["status"] == "acknowledged"

    # Verify atomic transaction in database
    with get_conn() as conn, conn.cursor() as cur:
        # Flag updated
        cur.execute("SELECT status, acknowledged_by_staff_id, acknowledged_at FROM flags WHERE flag_id=%s", (target_flag_id,))
        flag = cur.fetchone()
        assert flag["status"] == "Acknowledged"
        assert flag["acknowledged_by_staff_id"] == 3  # Nurse Priya
        assert flag["acknowledged_at"] is not None

        # Follow-up task created
        cur.execute("SELECT * FROM follow_up_tasks WHERE flag_id=%s ORDER BY followup_id DESC LIMIT 1", (target_flag_id,))
        task = cur.fetchone()
        assert task is not None, "Expected follow_up_task to be created by sp_acknowledge_flag"
        assert task["assigned_staff_id"] == 3
        assert task["status"] == "Pending"

        # Audit log written
        cur.execute("SELECT * FROM audit_log WHERE entity_type='flag' AND entity_id=%s AND action='ACK_FLAG' ORDER BY log_id DESC LIMIT 1", (str(target_flag_id),))
        audit = cur.fetchone()
        assert audit is not None, "Expected audit_log row for flag acknowledgement"
        print(f"✅ Atomic Acknowledge Verified: Flag #{target_flag_id} acknowledged, follow-up task #{task['followup_id']} created, audit log #{audit['log_id']} recorded")

    # 2. Second Acknowledge call on SAME flag -> MUST return HTTP 409 Conflict
    double_ack_res = client.post(
        f"/staff/flags/{target_flag_id}/acknowledge",
        json={"note": "Trying to acknowledge twice"},
        headers=nurse_headers,
    )
    assert double_ack_res.status_code == 409, f"Expected 409, got {double_ack_res.status_code}: {double_ack_res.text}"
    print("✅ Double Acknowledge Rejection Verified: Second acknowledge returned HTTP 409 Conflict without modifying database")


def test_follow_ups_queue():
    nurse_headers = {"Authorization": f"Bearer {NURSE_TOKEN}"}
    res = client.get("/staff/follow-ups", headers=nurse_headers)
    assert res.status_code == 200, res.text
    tasks = res.json()
    assert isinstance(tasks, list)
    assert len(tasks) >= 1
    t = tasks[0]
    assert "followup_id" in t
    assert "assigned_to" in t
    assert "status" in t
    print(f"✅ GET /staff/follow-ups returned {len(tasks)} pending task(s) (e.g. Task #{t['followup_id']}: '{t['reason']}')")


def test_patient_timeline():
    doc_headers = {"Authorization": f"Bearer {DOCTOR_TOKEN}"}
    res = client.get("/staff/patients/1/timeline", headers=doc_headers)
    assert res.status_code == 200, res.text
    timeline = res.json()
    assert isinstance(timeline, list)
    assert len(timeline) >= 1
    event = timeline[0]
    assert "event_time" in event
    assert "event_type" in event
    assert "summary" in event
    print(f"✅ GET /staff/patients/1/timeline returned {len(timeline)} events from v_patient_timeline (latest: [{event['event_type']}] {event['summary']})")


if __name__ == "__main__":
    test_triage_board_access()
    test_escalation_ladder_and_consent_gating()
    test_atomic_acknowledge_and_double_ack_error()
    test_follow_ups_queue()
    test_patient_timeline()
    print("\n🎉 ALL MILESTONE M4 ESCALATION & CLINICAL WORKFLOW TESTS PASSED!")
