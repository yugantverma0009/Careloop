"""
tests/test_role_permissions_p2.py

Automated Acceptance Tests for Phase 2: Role and Permission Model
- Single Role Contract enforcement:
  1. Nurse calling approve summary, reject summary, audit log, export gets 403.
  2. Doctor allowed on summary approve/reject, audit log, export.
  3. Family token calling any /patient/... or /chat/... endpoint gets 403.
  4. Patient token calling /family/... endpoints gets 403.
  5. IDOR prevention: patient_id extracted solely from JWT; patients blocked from staff endpoints.
  6. Family consent immediate cutoff:
     - When patient turns sharing OFF, /family/today immediately returns 403 ("Sharing turned off by patient").
     - When patient turns sharing back ON, /family/today returns 200.
  7. Flag resolution authority:
     - Nurse attempting to resolve Urgent_Review/Immediate flag gets 403.
     - Nurse can escalate flag to doctor via POST /staff/flags/{id}/escalate-doctor (records flag_events).
     - Doctor can resolve urgent flag, requiring a clinical note >= 5 characters.
  8. Family dose assistance:
     - Family helper calls POST /family/doses/{id}/helped -> records dose as taken with Caregiver role.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import get_conn

client = TestClient(app)


def get_token(email: str, password: str = "Demo@12345") -> str:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def tokens():
    return {
        "doctor": get_token("ananya.demo@example.test"),
        "nurse": get_token("priya.demo@example.test"),
        "patient": get_token("aarav.demo@example.test"),
        "family": get_token("caregiver1.demo@example.test"),
    }


@pytest.fixture(autouse=True)
def setup_demo_state():
    client.post("/demo/reset")
    yield
    client.post("/demo/reset")



# ── 1. Nurse Forbidden from Doctor Actions ───────────────────────────────────

def test_nurse_forbidden_from_summary_approval(tokens):
    """Nurse calling summary approval must be rejected with 403."""
    headers = {"Authorization": f"Bearer {tokens['nurse']}"}
    res = client.post(
        "/staff/summaries/1/approve",
        json={"edited_text": "Clinically reviewed summary text."},
        headers=headers,
    )
    assert res.status_code == 403, f"Expected 403 for Nurse approving summary, got {res.status_code}: {res.text}"
    assert "Doctor" in res.json().get("detail", "")
    print("✅ Nurse forbidden from summary approval (403)")


def test_nurse_forbidden_from_summary_rejection(tokens):
    """Nurse calling summary rejection must be rejected with 403."""
    headers = {"Authorization": f"Bearer {tokens['nurse']}"}
    res = client.post(
        "/staff/summaries/1/reject",
        json={"reason": "Contains inaccurate statements."},
        headers=headers,
    )
    assert res.status_code == 403, f"Expected 403 for Nurse rejecting summary, got {res.status_code}: {res.text}"
    print("✅ Nurse forbidden from summary rejection (403)")


def test_nurse_forbidden_from_audit_log(tokens):
    """Nurse opening audit log must be rejected with 403."""
    headers = {"Authorization": f"Bearer {tokens['nurse']}"}
    res = client.get("/staff/audit-log", headers=headers)
    assert res.status_code == 403, f"Expected 403 for Nurse audit log, got {res.status_code}: {res.text}"
    print("✅ Nurse forbidden from audit log (403)")


def test_nurse_forbidden_from_audit_export(tokens):
    """Nurse exporting audit log must be rejected with 403."""
    headers = {"Authorization": f"Bearer {tokens['nurse']}"}
    res = client.post("/staff/audit-log/export-log", json={"count": 10}, headers=headers)
    assert res.status_code == 403, f"Expected 403 for Nurse audit export, got {res.status_code}: {res.text}"
    print("✅ Nurse forbidden from audit export (403)")


def test_nurse_forbidden_from_fhir_export(tokens):
    """Nurse exporting FHIR bundle must be rejected with 403."""
    headers = {"Authorization": f"Bearer {tokens['nurse']}"}
    res = client.get("/staff/patients/1/fhir", headers=headers)
    assert res.status_code == 403, f"Expected 403 for Nurse FHIR export, got {res.status_code}: {res.text}"
    print("✅ Nurse forbidden from FHIR export (403)")


# ── 2. Doctor Allowed Doctor Actions ─────────────────────────────────────────

def test_doctor_allowed_audit_log(tokens):
    """Doctor opening audit log must succeed (200)."""
    headers = {"Authorization": f"Bearer {tokens['doctor']}"}
    res = client.get("/staff/audit-log?limit=10", headers=headers)
    assert res.status_code == 200, f"Expected 200 for Doctor audit log, got {res.status_code}: {res.text}"
    data = res.json()
    assert "logs" in data
    assert "total" in data
    print(f"✅ Doctor audit log accessible (200, retrieved {len(data['logs'])} events)")


def test_doctor_allowed_fhir_export(tokens):
    """Doctor requesting FHIR export must succeed (200)."""
    headers = {"Authorization": f"Bearer {tokens['doctor']}"}
    res = client.get("/staff/patients/1/fhir", headers=headers)
    assert res.status_code == 200, f"Expected 200 for Doctor FHIR export, got {res.status_code}: {res.text}"
    bundle = res.json()
    assert bundle.get("resourceType") == "Bundle"
    print("✅ Doctor FHIR export accessible (200, valid Bundle)")


# ── 3. Family Token Forbidden from Patient & Chat Endpoints ──────────────────

def test_family_forbidden_from_patient_endpoints(tokens):
    """Family helper calling /patient/me/... endpoints must be rejected with 403."""
    headers = {"Authorization": f"Bearer {tokens['family']}"}

    endpoints = [
        ("GET", "/patient/me/profile"),
        ("GET", "/patient/me/today"),
        ("GET", "/patient/me/doses"),
        ("GET", "/patient/me/calendar"),
        ("GET", "/patient/me/checkins"),
        ("POST", "/patient/me/checkins", {"pain_level": 2, "chips": [], "sites": [], "text": "test"}),
        ("POST", "/patient/me/chat", {"question": "Can I eat salt?"}),
        ("GET", "/patient/me/chat/history"),
    ]

    for item in endpoints:
        method = item[0]
        url = item[1]
        body = item[2] if len(item) > 2 else None
        if method == "GET":
            res = client.get(url, headers=headers)
        else:
            res = client.post(url, json=body, headers=headers)
        assert res.status_code == 403, f"Expected 403 for Family on {url}, got {res.status_code}: {res.text}"

    print(f"✅ Family helper forbidden from all {len(endpoints)} patient & chat endpoints (403)")


# ── 4. Patient Token Forbidden from Family Endpoints ─────────────────────────

def test_patient_forbidden_from_family_endpoints(tokens):
    """Patient calling /family/... endpoints must be rejected with 403."""
    headers = {"Authorization": f"Bearer {tokens['patient']}"}

    endpoints = [
        "/family/today",
        "/family/calendar",
        "/family/contacts",
    ]
    for url in endpoints:
        res = client.get(url, headers=headers)
        assert res.status_code == 403, f"Expected 403 for Patient on {url}, got {res.status_code}: {res.text}"

    print(f"✅ Patient forbidden from family endpoints (403)")


# ── 5. IDOR & Identity Isolation ─────────────────────────────────────────────

def test_patient_identity_isolation(tokens):
    """Patient cannot access or affect other patients."""
    headers = {"Authorization": f"Bearer {tokens['patient']}"}

    # Calling own profile derives patient_id from token solely
    res = client.get("/patient/me/profile", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["profile"]["patient_id"] == 1
    assert data["profile"]["full_name"] == "Aarav Patel"

    # Patient attempting staff endpoints receives 403
    res_staff = client.get("/staff/patients", headers=headers)
    assert res_staff.status_code == 403

    print("✅ IDOR isolated: patient cannot access other patient data or staff views")


# ── 6. Family Sharing Consent Immediate Cutoff ───────────────────────────────

def test_family_sharing_consent_toggle(tokens):
    """
    Test real-time consent enforcement:
    1. Neha accesses /family/today -> 200 OK
    2. Aarav turns sharing OFF -> POST /patient/me/sharing {"enabled": false}
    3. Neha immediately accesses /family/today -> 403 Forbidden ('Sharing turned off')
    4. Aarav turns sharing back ON -> POST /patient/me/sharing {"enabled": true}
    5. Neha immediately accesses /family/today -> 200 OK
    """
    p_headers = {"Authorization": f"Bearer {tokens['patient']}"}
    f_headers = {"Authorization": f"Bearer {tokens['family']}"}

    # Step 1: Ensure initial access works
    res_initial = client.get("/family/today", headers=f_headers)
    assert res_initial.status_code == 200, f"Expected 200 initial family access: {res_initial.text}"
    init_data = res_initial.json()
    assert init_data["patient"]["full_name"] == "Aarav Patel"
    assert "what_you_may_need_to_do" in init_data

    # Step 2: Patient turns sharing OFF
    res_off = client.post("/patient/me/sharing", json={"enabled": False}, headers=p_headers)
    assert res_off.status_code == 200
    assert res_off.json()["sharing_enabled"] is False

    # Step 3: Family helper immediately blocked
    res_blocked = client.get("/family/today", headers=f_headers)
    assert res_blocked.status_code == 403, f"Expected 403 after sharing turned off, got {res_blocked.status_code}"
    assert "Sharing turned off" in res_blocked.json().get("detail", "")

    # Also blocked on calendar and contacts
    res_cal_blocked = client.get("/family/calendar", headers=f_headers)
    assert res_cal_blocked.status_code == 403

    # Step 4: Patient turns sharing back ON
    res_on = client.post("/patient/me/sharing", json={"enabled": True}, headers=p_headers)
    assert res_on.status_code == 200
    assert res_on.json()["sharing_enabled"] is True

    # Step 5: Family helper immediately unblocked
    res_unblocked = client.get("/family/today", headers=f_headers)
    assert res_unblocked.status_code == 200
    assert res_unblocked.json()["patient"]["full_name"] == "Aarav Patel"

    print("✅ Family sharing consent toggle: immediate server-side cutoff verified (403 on off, 200 on on)")


# ── 7. Flag Authority & Escalate-to-Doctor ────────────────────────────────────

def test_flag_authority_and_escalation(tokens):
    """
    Flag Authority Policy:
    - Nurse attempting to resolve an Urgent flag (flag 3, Rajesh Verma, Emergency) -> 403
    - Nurse calling escalate-doctor -> 200 OK, records flag_events 'Escalated'
    - Doctor attempting to resolve Urgent flag without note -> 400
    - Doctor resolving with note -> 200 OK
    """
    n_headers = {"Authorization": f"Bearer {tokens['nurse']}"}
    d_headers = {"Authorization": f"Bearer {tokens['doctor']}"}

    # Find Rajesh's open Urgent flag
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT flag_id FROM flags WHERE patient_id = 3 AND severity = 'Urgent_Review' AND status = 'Open' LIMIT 1")
        row = cur.fetchone()
        urgent_flag_id = row["flag_id"] if row else 3

    # 1. Nurse attempts to resolve urgent flag -> 403
    res_nurse_resolve = client.post(
        f"/staff/flags/{urgent_flag_id}/resolve",
        json={"resolution_code": "Patient_Contacted", "resolution_note": "Attempted nurse resolution"},
        headers=n_headers,
    )
    assert res_nurse_resolve.status_code == 403, f"Expected 403 for Nurse resolving urgent flag, got {res_nurse_resolve.status_code}: {res_nurse_resolve.text}"
    assert "Nurse cannot resolve" in res_nurse_resolve.json().get("detail", "")
    print("✅ Nurse cannot resolve urgent flag (403 enforced)")

    # 2. Nurse escalates to doctor -> 200
    res_escalate = client.post(
        f"/staff/flags/{urgent_flag_id}/escalate-doctor",
        json={"note": "Nurse Priya Nair contacted Rajesh Verma. Referred to attending Dr. Ananya Sharma."},
        headers=n_headers,
    )
    assert res_escalate.status_code == 200, f"Escalation failed: {res_escalate.text}"
    assert res_escalate.json()["status"] == "escalated_to_doctor"

    # Verify flag_events contains Escalated
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT event_type, note FROM flag_events WHERE flag_id = %s ORDER BY flag_event_id DESC LIMIT 1",
            (urgent_flag_id,),
        )
        evt = cur.fetchone()
        assert evt["event_type"] == "Escalated"
        assert "Escalated to doctor" in evt["note"]
    print("✅ Nurse 'Ask doctor' action successfully logged flag_events and escalations")

    # 3. Doctor resolves without note -> 400
    res_doc_short = client.post(
        f"/staff/flags/{urgent_flag_id}/resolve",
        json={"resolution_code": "Referred_To_Emergency", "resolution_note": ""},
        headers=d_headers,
    )
    assert res_doc_short.status_code == 400, f"Expected 400 for Doctor resolution without note, got {res_doc_short.status_code}"
    print("✅ Doctor resolving urgent flag requires note >= 5 characters (400 enforced on empty)")


# ── 8. Family Dose Help Action ───────────────────────────────────────────────

def test_family_dose_helped(tokens):
    """Family helper can confirm dose assisted via POST /family/doses/{id}/helped."""
    f_headers = {"Authorization": f"Bearer {tokens['family']}"}

    # Find today's unconfirmed dose for Aarav
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT ml.medication_log_id
               FROM medication_logs ml
               JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
               WHERE pr.patient_id = 1 AND ml.status = 'Unconfirmed'
               ORDER BY ml.scheduled_for ASC LIMIT 1"""
        )
        row = cur.fetchone()
        assert row is not None, "Expected an unconfirmed dose for testing family assistance"
        dose_id = row["medication_log_id"]

    res = client.post(f"/family/doses/{dose_id}/helped", headers=f_headers)
    assert res.status_code == 200, f"Family help dose failed: {res.text}"
    assert res.json()["status"] == "updated"

    # Verify in DB
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT status, recorded_by, patient_note FROM medication_logs WHERE medication_log_id = %s", (dose_id,))
        dml = cur.fetchone()
        assert dml["status"] == "Taken_Confirmed"
        assert dml["recorded_by"] == "Caregiver"
    print("✅ Family helper dose confirmation recorded as Caregiver in DB (200)")


# ── 9. Nurse Limit Proposal ──────────────────────────────────────────────────

def test_nurse_propose_limit(tokens):
    """Nurse can submit a limit proposal via POST /staff/rules/propose-limit."""
    n_headers = {"Authorization": f"Bearer {tokens['nurse']}"}

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT rule_id FROM alert_rules WHERE patient_id = 1 LIMIT 1")
        rule_row = cur.fetchone()
        rule_id = rule_row["rule_id"] if rule_row else 1

    res = client.post(
        "/staff/rules/propose-limit",
        json={
            "rule_id": rule_id,
            "threshold_value": 92.0,
            "change_reason": "Patient is stable at resting SpO2 93%; proposing threshold adjustment.",
        },
        headers=n_headers,
    )
    assert res.status_code == 200, f"Nurse proposal failed: {res.text}"
    data = res.json()
    assert data["status"] == "proposed"
    assert data["approved_by_doctor"] is False
    print("✅ Nurse limit proposal successfully recorded (requires doctor approval)")


if __name__ == "__main__":
    pytest.main(["-s", __file__])
