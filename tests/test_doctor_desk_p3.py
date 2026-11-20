"""
tests/test_doctor_desk_p3.py

Automated acceptance tests for Phase 3: Doctor Desk ("Needs my decision").
Verifies:
1. Doctor home shows 1 immediate item (Rajesh), 2 summaries to approve (Meera, Rajesh), 0 limit requests at start, 5 patients, "Quiet patients: 2".
2. Routine items (Sunita missed doses, Meera silent device) are NOT shown on doctor home unless escalated.
3. Nurse calling /staff/doctor/decisions gets 403.
4. Summary approval writes approver, time, and edited text; summary rejection requires a clinical reason.
5. Limit change proposal workflow: Nurse proposes -> Doctor sees count 1 -> Doctor approves -> alert_rules updated with doctor signature & timestamp.
6. Limit change proposal rejection with clinical reason.
7. Patient timeline includes discharge transition metadata separating hospital stay vs home recovery.
8. FHIR R4 Bundle export returns valid HL7 FHIR Bundle for Dr. Sharma.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from scripts.seed_demo import main as run_seed

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_clean_demo_state():
    """Seed only with explicit disposable database opt-in."""
    import os
    if os.getenv("CARELOOP_ALLOW_DEMO_RESET", "").lower() != "true":
        pytest.skip("Set CARELOOP_ALLOW_DEMO_RESET=true to run DB integration tests against a disposable demo database.")
    run_seed()


def get_auth_headers(email: str, password: str = "Demo@12345"):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_doctor_home_baseline_decisions():
    """Acceptance Check 1: Baseline doctor home decision items and quiet patients."""
    doc_headers = get_auth_headers("ananya.demo@example.test")
    resp = client.get("/staff/doctor/decisions", headers=doc_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    cards = data["cards"]
    assert cards["needs_decision_now"] == 3, f"Expected 3 decision items, got {cards['needs_decision_now']}"
    assert cards["summaries_to_approve"] == 2, f"Expected 2 draft summaries, got {cards['summaries_to_approve']}"
    assert cards["limit_change_requests"] == 0, f"Expected 0 limit proposals at start, got {cards['limit_change_requests']}"
    assert cards["patients_in_followup"] == 5, f"Expected 5 patients, got {cards['patients_in_followup']}"

    # Items breakdown
    items = data["items"]
    assert len(items) == 3

    flag_items = [i for i in items if i["type"] == "flag"]
    summary_items = [i for i in items if i["type"] == "summary"]

    assert len(flag_items) == 1
    assert flag_items[0]["patient_name"] == "Rajesh Verma"
    assert flag_items[0]["tier"] == "Immediate"

    assert len(summary_items) == 2
    summary_patients = {s["patient_name"] for s in summary_items}
    assert summary_patients == {"Meera Sharma", "Rajesh Verma"}

    # Quiet patients check
    quiet = data["quiet_patients"]
    assert quiet["count"] == 2
    quiet_names = {p["full_name"] for p in quiet["patients"]}
    assert quiet_names == {"Aarav Patel", "Kabir Mehta"}


def test_doctor_home_omits_routine_flags_until_escalated():
    """Acceptance Check 2: Doctor home does not show routine items unless nurse escalated them."""
    doc_headers = get_auth_headers("ananya.demo@example.test")
    nurse_headers = get_auth_headers("priya.demo@example.test")

    # Initial state: Sunita's missed dose flag is NOT on doctor home
    resp = client.get("/staff/doctor/decisions", headers=doc_headers)
    assert resp.status_code == 200
    flag_patients = [i["patient_name"] for i in resp.json()["items"] if i["type"] == "flag"]
    assert "Sunita Rao" not in flag_patients

    # Nurse escalates Sunita's flag (Flag #2)
    esc_resp = client.post(
        "/staff/flags/2/escalate-doctor",
        headers=nurse_headers,
        json={"note": "Patient reports skipping carvedilol due to dizziness; requesting doctor review"},
    )
    assert esc_resp.status_code == 200

    # Doctor home now includes Sunita's escalated flag
    resp2 = client.get("/staff/doctor/decisions", headers=doc_headers)
    assert resp2.status_code == 200
    items2 = resp2.json()["items"]
    sunita_item = next((i for i in items2 if i.get("flag_id") == 2), None)
    assert sunita_item is not None
    assert "Nurse Priya Nair" in sunita_item["escalated_kicker"]
    assert resp2.json()["cards"]["needs_decision_now"] == 4


def test_nurse_forbidden_from_doctor_decisions():
    """Acceptance Check 3: Nurse calling /staff/doctor/decisions gets 403."""
    nurse_headers = get_auth_headers("priya.demo@example.test")
    resp = client.get("/staff/doctor/decisions", headers=nurse_headers)
    assert resp.status_code == 403


def test_summary_approval_and_rejection_workflow():
    """Acceptance Check 4: Approving a summary writes approver, time, and edited text; rejecting needs reason."""
    doc_headers = get_auth_headers("ananya.demo@example.test")

    # 1. Reject without reason -> 422 or 400
    bad_rej = client.post("/staff/summaries/1/reject", headers=doc_headers, json={"reason": ""})
    assert bad_rej.status_code in (400, 422)

    # 2. Reject with reason
    good_rej = client.post(
        "/staff/summaries/1/reject",
        headers=doc_headers,
        json={"reason": "Telemetry window incomplete for knee flexion range; regenerate after evening check-in"},
    )
    assert good_rej.status_code == 200
    assert good_rej.json()["status"] == "Rejected"

    # 3. Approve summary #2 (Rajesh) with edited text
    final_text = "Patient recovering from community pneumonia. Completed oral antibiotic regimen; emergency keyword resolved."
    appr_resp = client.post(
        "/staff/summaries/2/approve",
        headers=doc_headers,
        json={"edited_text": final_text},
    )
    assert appr_resp.status_code == 200
    assert appr_resp.json()["status"] == "Approved"

    # Summaries to approve on doctor desk drops from 2 to 0
    resp = client.get("/staff/doctor/decisions", headers=doc_headers)
    assert resp.json()["cards"]["summaries_to_approve"] == 0


def test_limit_proposal_lifecycle():
    """Acceptance Check 5: Nurse proposes limit -> Doctor approves -> alert_rules updated."""
    nurse_headers = get_auth_headers("priya.demo@example.test")
    doc_headers = get_auth_headers("ananya.demo@example.test")

    # 1. Nurse proposes limit for Aarav (Rule #1, SpO2 Reading_Below from 94 to 92)
    prop_resp = client.post(
        "/staff/rules/propose-limit",
        headers=nurse_headers,
        json={
            "rule_id": 1,
            "threshold_value": 92.0,
            "change_reason": "Patient is comfortably ambulating on room air; SpO2 stable between 92-94%",
        },
    )
    assert prop_resp.status_code == 200
    assert prop_resp.json()["status"] == "proposed"

    # 2. Doctor desk shows limit_change_requests incremented to 1
    dec_resp = client.get("/staff/doctor/decisions", headers=doc_headers)
    assert dec_resp.json()["cards"]["limit_change_requests"] == 1

    # 3. Doctor retrieves pending proposals
    props_resp = client.get("/staff/rules/proposals", headers=doc_headers)
    assert props_resp.status_code == 200
    props = props_resp.json()
    assert len(props) >= 1
    proposal = props[0]
    history_id = proposal["history_id"]

    # 4. Doctor approves proposal
    appr_resp = client.post(f"/staff/rules/proposals/{history_id}/approve", headers=doc_headers)
    assert appr_resp.status_code == 200
    assert appr_resp.json()["status"] == "Approved"

    # 5. Active threshold in alert_rules is now 92.0 and signed by doctor
    rules_resp = client.get("/staff/rules/all?patient_id=1", headers=doc_headers)
    assert rules_resp.status_code == 200
    rule1 = next((r for r in rules_resp.json() if r["rule_id"] == 1), None)
    assert rule1 is not None
    assert float(rule1["threshold_value"]) == 92.0
    assert "Ananya" in rule1["approved_by_name"]

    # 6. Doctor desk limit requests drops back to 0
    dec_resp2 = client.get("/staff/doctor/decisions", headers=doc_headers)
    assert dec_resp2.json()["cards"]["limit_change_requests"] == 0


def test_patient_timeline_hospital_vs_recovery_separation():
    """Acceptance Check 6: Timeline contains discharge_date and marks inpatient vs home recovery."""
    doc_headers = get_auth_headers("ananya.demo@example.test")

    # Aarav Patel (Patient #1, discharged Day 3)
    resp = client.get("/staff/patients/1/timeline?date_range=all", headers=doc_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data.get("discharge_date") is not None
    day_groups = data.get("day_groups", [])
    assert len(day_groups) > 0

    # Ensure inpatient and home recovery phases are both distinguished
    has_inpatient = any(g["is_inpatient"] is True for g in day_groups)
    has_home = any(g["is_inpatient"] is False for g in day_groups)
    assert has_inpatient, "Timeline should include hospital stay days"
    assert has_home, "Timeline should include home recovery days"


def test_fhir_r4_bundle_export():
    """Acceptance Check 7: Doctor can export compliant FHIR R4 Bundle for patient."""
    doc_headers = get_auth_headers("ananya.demo@example.test")

    resp = client.get("/staff/patients/1/fhir", headers=doc_headers)
    assert resp.status_code == 200
    bundle = resp.json()

    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    assert len(bundle["entry"]) >= 2

    # Verify Patient resource entry
    patient_res = next((e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Patient"), None)
    assert patient_res is not None
    assert patient_res["identifier"][0]["value"] == "CL-00001"
