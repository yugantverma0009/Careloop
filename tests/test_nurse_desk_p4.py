"""
CareLoop Phase 4 Automated Test Suite: Nurse Desk ("My call list")
Verifies:
1. Nurse call list aggregation: 4 KPI cards, prioritized call queue, target timers, quiet patients.
2. Clinical governance: immediate/urgent flags show 'needs doctor to resolve'.
3. 'Ask doctor' escalation flow: records event and reflects nurse name & time on Doctor Desk.
4. Call logging: phone/SMS logging to contact_log and audit_log.
5. Task completion: outcome codes and resolution.
6. Nurse limit proposal: submits to doctor approvals queue.
7. Nurse permissions: forbidden from audit, summary approval, fhir export, and doctor decisions.
8. Shift handoff: exactly 5 unique patients, concise cards, and contingency note updates.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app, get_conn
from backend.app.auth import make_token, verify_login
from scripts.seed_demo import main as run_seed


@pytest.fixture(autouse=True)
def reset_database():
    """Seed only with explicit disposable database opt-in."""
    import os
    if os.getenv("CARELOOP_ALLOW_DEMO_RESET", "").lower() != "true":
        pytest.skip("Set CARELOOP_ALLOW_DEMO_RESET=true to run DB integration tests against a disposable demo database.")
    run_seed()


@pytest.fixture
def nurse_token():
    acct = verify_login("priya.demo@example.test", "Demo@12345")
    assert acct is not None
    return make_token(acct)


@pytest.fixture
def doctor_token():
    acct = verify_login("ananya.demo@example.test", "Demo@12345")
    assert acct is not None
    return make_token(acct)


def test_nurse_call_list_endpoint(nurse_token):
    """Verify Nurse Call List returns 4 KPI cards, prioritized queue, and quiet patients."""
    client = TestClient(app)
    res = client.get("/staff/nurse/call-list", headers={"Authorization": f"Bearer {nurse_token}"})
    assert res.status_code == 200
    data = res.json()

    # 1. KPI Cards
    cards = data["cards"]
    assert cards["active_patients"] == 5
    assert cards["calls_to_make"] >= 3
    assert cards["visits_today"] >= 1
    assert cards["pending_limit_requests"] == 0

    # 2. Prioritized Call Items
    items = data["call_items"]
    assert len(items) == 3

    # Rajesh Verma (Patient #3) must be Immediate
    rajesh_item = next(i for i in items if i["patient_id"] == 3)
    assert rajesh_item["tier"] == "Immediate"
    assert rajesh_item["needs_doctor_to_resolve"] is True
    assert rajesh_item["can_nurse_resolve"] is False
    assert "shortness of breath" in rajesh_item["reason"] or "emergency" in rajesh_item["reason"].lower()
    assert rajesh_item["target_mins"] == 15
    assert "Target: seen within 15 min" in rajesh_item["target_display"]

    # Meera Sharma (Patient #2) & Sunita Rao (Patient #5) are Review Soon
    meera_item = next(i for i in items if i["patient_id"] == 2)
    assert meera_item["tier"] == "Review soon"
    assert meera_item["needs_doctor_to_resolve"] is False
    assert meera_item["can_nurse_resolve"] is True

    sunita_item = next(i for i in items if i["patient_id"] == 5)
    assert sunita_item["tier"] == "Review soon"
    assert sunita_item["needs_doctor_to_resolve"] is False
    assert sunita_item["can_nurse_resolve"] is True

    # 3. Tasks Due Today
    tasks = data["tasks_due_today"]
    assert len(tasks) >= 1
    assert any("dose" in t["reason"].lower() or "blood-pressure" in t["reason"].lower() for t in tasks)

    # 4. Quiet Patients On Track
    quiet = data["on_track_patients"]
    quiet_ids = [q["patient_id"] for q in quiet]
    assert 1 in quiet_ids  # Aarav Patel
    assert 4 in quiet_ids  # Kabir Mehta


def test_nurse_ask_doctor_escalation_flow(nurse_token, doctor_token):
    """
    Verify nurse 'Ask doctor' flow:
    1. Nurse escalates Rajesh's flag (#3) with a note.
    2. Flag event is recorded with Nurse Priya's identity.
    3. Doctor desk immediately reflects the nurse escalation with name and timestamp.
    """
    client = TestClient(app)

    # 1. Nurse clicks 'Ask doctor'
    esc_note = "Nurse Priya: Patient reporting increased breathing difficulty; requesting physician review."
    esc_res = client.post(
        "/staff/flags/3/escalate-doctor",
        headers={"Authorization": f"Bearer {nurse_token}"},
        json={"note": esc_note},
    )
    assert esc_res.status_code == 200
    assert esc_res.json()["status"] == "escalated_to_doctor"

    # 2. Verify database records
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT event_type, staff_id, note FROM flag_events WHERE flag_id = 3 AND event_type = 'Escalated' ORDER BY flag_event_id DESC LIMIT 1"
        )
        ev = cur.fetchone()
        assert ev is not None
        assert ev["staff_id"] == 2  # Priya Nair
        assert "Nurse Priya" in ev["note"]

    # 3. Doctor checks decisions desk
    doc_res = client.get("/staff/doctor/decisions", headers={"Authorization": f"Bearer {doctor_token}"})
    assert doc_res.status_code == 200
    doc_data = doc_res.json()

    rajesh_decision = next(i for i in doc_data["items"] if i.get("flag_id") == 3)
    assert rajesh_decision["escalated_by"] == "Priya Nair"
    assert rajesh_decision["escalated_at"] is not None
    assert "Priya Nair" in rajesh_decision["escalated_kicker"]
    assert "Nurse Priya" in rajesh_decision["escalated_kicker"]


def test_nurse_contact_call_logging(nurse_token):
    """Verify Nurse can log a telephone call with channel, outcome, and summary."""
    client = TestClient(app)

    call_payload = {
        "patient_id": 5,
        "flag_id": 2,
        "channel": "Phone",
        "outcome": "Reached",
        "summary": "Spoke with Sunita Rao regarding missed doses; advised on medication timing protocol.",
    }

    res = client.post(
        "/staff/contacts/log",
        headers={"Authorization": f"Bearer {nurse_token}"},
        json=call_payload,
    )
    assert res.status_code == 200
    assert res.json()["status"] == "logged"
    contact_id = res.json()["contact_id"]

    # Verify audit log and contacts history
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT action, entity_id FROM audit_log WHERE entity_type = 'contact_log' AND entity_id = %s", (contact_id,))
        audit = cur.fetchone()
        assert audit is not None
        assert audit["action"] == "CONTACT_LOGGED"

    hist_res = client.get("/staff/patients/5/contacts", headers={"Authorization": f"Bearer {nurse_token}"})
    assert hist_res.status_code == 200
    contacts = hist_res.json()
    assert any(c["contact_id"] == contact_id and c["outcome"] == "Reached" for c in contacts)


def test_nurse_complete_task_with_outcome_codes(nurse_token):
    """Verify Nurse can complete a task using standard outcome codes."""
    client = TestClient(app)

    # 1. Invalid outcome code rejected
    bad_res = client.post(
        "/staff/tasks/1/complete",
        headers={"Authorization": f"Bearer {nurse_token}"},
        json={"outcome_code": "INVALID_CODE", "outcome_notes": "Test notes"},
    )
    assert bad_res.status_code == 400

    # 2. Valid completion
    good_res = client.post(
        "/staff/tasks/1/complete",
        headers={"Authorization": f"Bearer {nurse_token}"},
        json={
            "outcome_code": "Reached_And_Advised",
            "outcome_notes": "Followed up with patient regarding dose question; verified discharge instructions.",
        },
    )
    assert good_res.status_code == 200
    assert good_res.json()["status"] == "completed"

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT status, outcome_code, outcome_notes FROM follow_up_tasks WHERE followup_id = 1")
        t = cur.fetchone()
        assert t["status"] == "Resolved"
        assert t["outcome_code"] == "Reached_And_Advised"


def test_nurse_propose_limit_appears_in_doctor_approvals(nurse_token, doctor_token):
    """Verify Nurse proposing a limit appears in Doctor Approvals and increments proposal count."""
    client = TestClient(app)

    # Nurse proposes rule limit
    prop_res = client.post(
        "/staff/rules/propose-limit",
        headers={"Authorization": f"Bearer {nurse_token}"},
        json={
            "rule_id": 1,
            "threshold_value": 55.0,
            "change_reason": "Patient post-op resting pulse stable around 55 bpm without symptoms.",
        },
    )
    assert prop_res.status_code == 200
    assert prop_res.json()["status"] == "proposed"

    # Doctor views proposals
    doc_props = client.get("/staff/rules/proposals", headers={"Authorization": f"Bearer {doctor_token}"})
    assert doc_props.status_code == 200
    props = doc_props.json()
    assert len(props) >= 1
    target_prop = next(p for p in props if p["rule_id"] == 1)
    assert target_prop["proposed_by_name"] == "Priya Nair"
    assert float(target_prop["new_values"]["threshold_value"]) == 55.0

    # Doctor desk KPI reflects proposal
    dec_res = client.get("/staff/doctor/decisions", headers={"Authorization": f"Bearer {doctor_token}"})
    assert dec_res.status_code == 200
    assert dec_res.json()["cards"]["limit_change_requests"] >= 1


def test_nurse_forbidden_from_doctor_operations(nurse_token):
    """Verify Nurse is strictly forbidden from physician-only endpoints (403 Forbidden)."""
    client = TestClient(app)

    # 1. Audit Log Viewer
    r1 = client.get("/staff/audit-log", headers={"Authorization": f"Bearer {nurse_token}"})
    assert r1.status_code == 403

    # 2. FHIR Export
    r2 = client.get("/staff/patients/1/fhir", headers={"Authorization": f"Bearer {nurse_token}"})
    assert r2.status_code == 403

    # 3. Summary Approval
    r3 = client.post(
        "/staff/summaries/1/approve",
        headers={"Authorization": f"Bearer {nurse_token}"},
        json={"edited_text": "Nurse approving summary"},
    )
    assert r3.status_code == 403

    # 4. Doctor Decision Desk Endpoint
    r4 = client.get("/staff/doctor/decisions", headers={"Authorization": f"Bearer {nurse_token}"})
    assert r4.status_code == 403


def test_shift_handoff_concise_5_lines_per_patient(nurse_token, doctor_token):
    """Verify Shift Handoff contains exactly 5 unique patients and supports contingency updates."""
    client = TestClient(app)

    # 1. Handoff patient count & unique identities
    res = client.get("/staff/handoff", headers={"Authorization": f"Bearer {nurse_token}"})
    assert res.status_code == 200
    data = res.json()
    patients = data["patients"]
    assert len(patients) == 5

    pids = [p["patient_id"] for p in patients]
    assert len(set(pids)) == 5  # No duplicate cards

    # Rajesh is Immediate
    rajesh = next(p for p in patients if p["patient_id"] == 3)
    assert rajesh["illness_tier"] == "Immediate"

    # 2. Nurse updates contingency note
    new_note = "If SpO2 drops below 92% or chest tightness recurs, call attending doctor immediately."
    c_res = client.post(
        "/staff/handoff/3/contingency",
        headers={"Authorization": f"Bearer {nurse_token}"},
        json={"contingency_note": new_note},
    )
    assert c_res.status_code == 200

    # 3. Doctor marks handoff received
    rec_res = client.post("/staff/handoff/3/receive", headers={"Authorization": f"Bearer {doctor_token}"})
    assert rec_res.status_code == 200
    assert rec_res.json()["status"] == "received"
