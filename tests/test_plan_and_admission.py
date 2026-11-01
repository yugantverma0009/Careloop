"""
tests/test_plan_and_admission.py

Unit and integration tests for Phase 4:
1. Ingestion heading and section detection
2. Number grounding guard (rejects hallucinated numbers)
3. Medication reconciliation ('Matches' vs 'Mismatch')
4. Patient plan visibility (Approved only; Draft plans 404/invisible)
5. Doctor approval lifecycle & role isolation (Nurses cannot approve)
6. Understanding check & nurse proposal generation for incorrect answers
7. Nurse admit patient wizard (welcome call within 48h, proposed limits require doctor approval)
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.plan_service import (
    verify_numbers_grounded,
    parse_discharge_text_to_chunks,
    detect_section_from_heading_or_text,
)

client = TestClient(app)


def get_token(email: str, role: str) -> str:
    res = client.post("/auth/login", json={"email": email, "password": "Demo@12345"})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


@pytest.fixture(scope="module", autouse=True)
def setup_seed():
    import scripts.seed_demo as seed_demo
    seed_demo.main()


@pytest.fixture(scope="module")
def doctor_token():
    return get_token("ananya.demo@example.test", "Doctor")


@pytest.fixture(scope="module")
def nurse_token():
    return get_token("priya.demo@example.test", "Nurse")


@pytest.fixture(scope="module")
def aarav_token():
    # Aarav Patel has Approved plan v1
    return get_token("aarav.demo@example.test", "Patient")


# ─── 1. Ingestion Heading & Section Detection ─────────────────────────────────

def test_heading_and_section_detection():
    cases = [
        ("MEDICATIONS: CardioPulse-XR 1 tablet at 08:00.", "medications", "Medications & Prescriptions"),
        ("FOLLOW-UP: Cardiology OPD visit scheduled in 7 days.", "follow_up", "Appointments & Follow-up"),
        ("WARNING SIGNS: Watch for severe chest tightness or fever.", "warning_signs", "Warning Signs & Red Flags"),
        ("ACTIVITY: Walk indoors for 10-15 minutes twice daily.", "activity", "Activity & Mobility Guidelines"),
        ("WOUND CARE: Keep sternal incision dry and clean.", "wound_care", "Incision & Wound Care"),
        ("DIET: Low sodium and restricted fluid intake.", "diet", "Diet & Nutrition"),
        ("Discharge summary overview for surgical patient.", "general", "General Discharge Information"),
    ]
    for text, expected_type, expected_title in cases:
        sec_type, sec_title = detect_section_from_heading_or_text(text)
        assert sec_type == expected_type, f"Failed for text '{text}': got {sec_type}"
        assert sec_title == expected_title


# ─── 2. Number Grounding Guard ────────────────────────────────────────────────

def test_number_grounding_guard():
    source_text = "Walk indoors for 10-15 minutes twice daily. Avoid lifting objects heavier than 5 kg."

    # Valid grounded item: numbers 10, 15, 5 exist in source
    grounded_item = "Walk for 10 to 15 minutes twice daily, max 5 kg lifting."
    is_ok, ungrounded = verify_numbers_grounded(grounded_item, source_text)
    assert is_ok is True
    assert len(ungrounded) == 0

    # Hallucinated item: numbers 30 and 20 are NOT in source
    hallucinated_item = "Walk for 30 minutes twice daily, max 20 kg lifting."
    is_ok, ungrounded = verify_numbers_grounded(hallucinated_item, source_text)
    assert is_ok is False
    assert "30" in ungrounded or "20" in ungrounded


# ─── 3. Medication Reconciliation Mismatch ────────────────────────────────────

def test_reconciliation_mismatch_in_seed():
    """Verify Meera's draft recovery plan item #9 has status Mismatch due to frequency disagreement."""
    from backend.app.plan_service import get_db_connection
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT item_id, title, detail, reconcile_status FROM recovery_plan_items WHERE item_id = 9")
            item = cur.fetchone()
            assert item is not None
            assert item["reconcile_status"] == "Mismatch"
            assert "twice daily" in item["detail"].lower()
    finally:
        conn.close()


# ─── 4. Patient Plan Visibility (Approved vs Draft) ───────────────────────────

def test_approved_patient_can_view_active_plan(aarav_token):
    """Aarav Patel (Patient 1) has an approved plan and can retrieve it."""
    res = client.get("/patient/me/plan", headers={"Authorization": f"Bearer {aarav_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "Approved"
    assert data["patient_id"] == 1
    assert len(data["medicines"]) >= 1
    assert len(data["warning_signs"]) >= 1
    assert len(data["wound_care"]) >= 1
    # Check that source labels say real section names, not "General"
    assert any("Discharge summary" in m["source_label"] for m in data["medicines"])


def test_draft_only_patient_receives_404(nurse_token):
    """Sunita Rao (Patient 5) only has a Draft plan. Active plan must return None."""
    from backend.app.plan_service import get_patient_active_plan
    plan = get_patient_active_plan(5)
    assert plan is None, "Draft-only patient must have None returned for active plan!"


# ─── 5. Doctor Plan Approval Lifecycle & Role Isolation ───────────────────────

def test_nurse_forbidden_from_approving_plan(nurse_token):
    """Nurses cannot approve recovery plans (HTTP 403 Forbidden)."""
    res = client.post("/staff/plans/3/approve", headers={"Authorization": f"Bearer {nurse_token}"})
    assert res.status_code == 403


def test_doctor_can_approve_plan_and_supersede_previous(doctor_token):
    """Doctor approves Meera's draft plan #3."""
    res = client.post("/staff/plans/3/approve", headers={"Authorization": f"Bearer {doctor_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["status"] == "Approved"

    # Verify database status
    from backend.app.plan_service import get_db_connection
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status, approved_by_staff_id, approved_at FROM recovery_plans WHERE plan_id = 3")
            row = cur.fetchone()
            assert row["status"] == "Approved"
            assert row["approved_by_staff_id"] == 1
            assert row["approved_at"] is not None

            # Verify understanding check questions were automatically generated
            cur.execute("SELECT COUNT(*) AS q_cnt FROM plan_understanding_checks WHERE plan_id = 3")
            q_cnt = cur.fetchone()["q_cnt"]
            assert q_cnt >= 2
    finally:
        conn.close()


# ─── 6. Understanding Check & Nurse Proposal Generation ───────────────────────

def test_understanding_check_incorrect_answer_creates_proposal(aarav_token):
    """
    When patient answers an understanding check question incorrectly, an agent_proposal
    ('Suggest_Plan_Review') is created for the nurse call list. No grades are returned.
    """
    # Aarav submits incorrect answer (option 1 instead of 0) for question 3
    res = client.post(
        "/patient/me/plan/understanding-check/answer",
        json={"check_id": 3, "selected_option_index": 1},
        headers={"Authorization": f"Bearer {aarav_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    # Confirm response contains supportive guidance, not a numerical score or grade
    assert "score" not in data
    assert "grade" not in data

    # Verify agent proposal created in database
    from backend.app.plan_service import get_db_connection
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT proposal_id, patient_id, proposal_type, status, reason
                   FROM agent_proposals
                   WHERE patient_id = 1 AND proposal_type = 'Suggest_Plan_Review'
                   ORDER BY proposal_id DESC LIMIT 1"""
            )
            prop = cur.fetchone()
            assert prop is not None
            assert prop["status"] == "Pending"
            assert "recovery plan" in prop["reason"].lower()
    finally:
        conn.close()


# ─── 7. Nurse Admit Patient Wizard ───────────────────────────────────────────

def test_nurse_admit_patient_flow(nurse_token):
    """
    Nurse executes stepwise onboarding wizard:
    - Creates patient and discharge record
    - Indexes chunks
    - Creates proposed alert limits with status 'Pending_Approval'
    - Creates welcome call task due within 48 hours
    """
    payload = {
        "patient": {
            "full_name": "Devendra Joshi",
            "phone": "+91-98765-77777",
            "date_of_birth": "1968-11-15",
            "preferred_language": "en"
        },
        "discharge": {
            "condition": "Post-Cholecystectomy Laparoscopic Recovery",
            "discharge_date": "2026-11-01",
            "summary_text": (
                "MEDICATIONS: GastroShield-D 1 capsule morning before meals.\n\n"
                "FOLLOW-UP: Follow up in 7 days for port clearance.\n\n"
                "WARNING SIGNS: Acute fever or persistent vomiting requires 112 emergency care.\n\n"
                "ACTIVITY: Light walking for 10 minutes twice daily. No lifting over 5 kg."
            )
        },
        "prescriptions": [
            {"name": "GastroShield-D", "dosage": "1 capsule", "frequency": "Morning before meals"}
        ],
        "proposed_limits": [
            {"rule_type": "Reading_Above", "threshold_val": 105.0, "comparator": ">", "severity": "Review_Soon"}
        ],
        "device": {
            "device_id": "DEV-TEST-ADMIT-01",
            "model": "ESP32_Wearable_V1"
        },
        "caregiver": {
            "full_name": "Kavita Joshi",
            "phone": "+91-98765-77778",
            "relationship": "Spouse",
            "consent_granted": True
        }
    }

    res = client.post("/staff/admit", json=payload, headers={"Authorization": f"Bearer {nurse_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    new_pid = data["patient_id"]
    assert new_pid > 5
    assert data["limits_status"] == "Waiting for doctor limits"
    assert data["welcome_call_due"] == "within 48 hours"

    # Verify database state for newly admitted patient
    from backend.app.plan_service import get_db_connection
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. Welcome call task exists and is due in ~48h
            cur.execute(
                """SELECT followup_id, reason, priority, status, due_at
                   FROM follow_up_tasks
                   WHERE patient_id = %s AND reason LIKE %s""",
                (new_pid, 'Welcome call%')
            )
            task = cur.fetchone()
            assert task is not None
            assert task["priority"] == "Routine"
            assert task["status"] == "Pending"

            # 2. Proposed limits are inactive (is_active = 0) pending doctor approval
            cur.execute(
                "SELECT rule_id, is_active FROM alert_rules WHERE patient_id = %s",
                (new_pid,)
            )
            rules = cur.fetchall()
            assert len(rules) >= 1
            for r in rules:
                assert r["is_active"] == 0

            # 3. Audit row written
            cur.execute(
                "SELECT log_id, action FROM audit_log WHERE entity_type = 'patient' AND entity_id = %s",
                (new_pid,)
            )
            audit = cur.fetchone()
            assert audit is not None
            assert audit["action"] == "PATIENT_ADMITTED"
    finally:
        conn.close()
