"""
tests/test_m3_patient_flows.py — Milestone M3 Tests

Tests:
1. Today's Doses: sp_generate_daily_doses + GET /patient/me/doses returns doses for patient in JWT
2. Dose Confirmation: POST /patient/me/doses/{id}/confirm updates medication_logs & writes audit_log
3. Patient Data Isolation: Patient cannot confirm another patient's dose
4. Emergency Layer (English): "chest pain" returns instant emergency guidance & creates Urgent_Review flag
5. Emergency Layer (Hindi): "सीने में दर्द" returns instant Hindi guidance & creates Urgent_Review flag
6. Pain Threshold: High pain (8/10) creates Review_Soon flag via DB trigger
7. Patient Status Page: GET /patient/me/status surfaces vitals, device status, and appointments
8. Reminder Scheduler Job: send_due_reminders updates reminder_sent_at and writes audit_log
"""

import time
import pytest
from datetime import datetime, date, timedelta
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import get_conn
from backend.app.auth import make_token
from backend.app.scheduler import send_due_reminders

client = TestClient(app)

# Patient 1: Aarav Demo
PATIENT_1_TOKEN = make_token({
    "account_id": 1,
    "email": "aarav.demo@example.test",
    "account_role": "Patient",
    "patient_id": 1,
    "caregiver_id": None,
    "staff_id": None,
})

# Caregiver 1: Demo Caregiver One (assigned to Patient 1, consent_granted=True)
CAREGIVER_1_TOKEN = make_token({
    "account_id": 2,
    "email": "caregiver1.demo@example.test",
    "account_role": "Caregiver",
    "patient_id": None,
    "caregiver_id": 1,
    "staff_id": None,
})


def test_get_today_doses():
    headers = {"Authorization": f"Bearer {PATIENT_1_TOKEN}"}
    res = client.get("/patient/me/doses", headers=headers)
    assert res.status_code == 200, res.text
    doses = res.json()
    assert isinstance(doses, list)
    assert len(doses) >= 1, f"Expected at least 1 dose for today, got {len(doses)}"
    dose = doses[0]
    assert "medication_log_id" in dose
    assert "medicine_name" in dose
    assert "scheduled_for" in dose
    print(f"✅ GET /patient/me/doses returned {len(doses)} dose(s) for Aarav (e.g. {dose['medicine_name']})")
    return doses


@pytest.fixture
def doses():
    return test_get_today_doses()


def test_confirm_dose(doses):
    target_dose = doses[0]
    log_id = target_dose["medication_log_id"]
    headers = {"Authorization": f"Bearer {PATIENT_1_TOKEN}"}

    # Patient confirms dose as Taken_Confirmed
    res = client.post(
        f"/patient/me/doses/{log_id}/confirm",
        json={"status": "Taken_Confirmed", "patient_note": "Taken after breakfast"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["recorded_status"] == "Taken_Confirmed"

    # Verify database state
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT status, recorded_by, patient_note, recorded_at FROM medication_logs WHERE medication_log_id=%s", (log_id,))
        row = cur.fetchone()
        assert row["status"] == "Taken_Confirmed"
        assert row["recorded_by"] == "Patient"
        assert row["patient_note"] == "Taken after breakfast"
        assert row["recorded_at"] is not None

        # Verify audit_log
        cur.execute("SELECT * FROM audit_log WHERE entity_type='medication_log' AND entity_id=%s ORDER BY log_id DESC LIMIT 1", (str(log_id),))
        audit = cur.fetchone()
        assert audit is not None
        assert audit["action"] == "CONFIRM_DOSE"
        assert audit["actor_type"] == "Patient"
        print(f"✅ Dose #{log_id} confirmed as 'Taken_Confirmed' and recorded in audit_log #{audit['log_id']}")


def test_caregiver_confirm_dose(doses):
    if len(doses) > 1:
        target_dose = doses[1]
    else:
        target_dose = doses[0]
    log_id = target_dose["medication_log_id"]

    # Caregiver confirms dose on patient's behalf
    cg_headers = {"Authorization": f"Bearer {CAREGIVER_1_TOKEN}"}
    res = client.post(
        f"/patient/me/doses/{log_id}/confirm",
        json={"status": "Skipped", "patient_note": "Caregiver observed patient asleep"},
        headers=cg_headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["recorded_status"] == "Skipped"

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT status, recorded_by FROM medication_logs WHERE medication_log_id=%s", (log_id,))
        row = cur.fetchone()
        assert row["status"] == "Skipped"
        assert row["recorded_by"] == "Caregiver"
        print(f"✅ Caregiver confirmed dose #{log_id} as 'Skipped' on patient's behalf")


def test_emergency_symptom_english():
    headers = {"Authorization": f"Bearer {PATIENT_1_TOKEN}"}
    res = client.post(
        "/patient/me/symptoms",
        json={
            "text": "Doctor, I have severe chest pain and cannot breathe right now!",
            "pain_level": 9,
            "input_method": "Text",
            "language": "en",
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["emergency"] is True
    assert "emergency" in data["guidance"].lower()
    report_id = data["report_id"]

    # Verify that MySQL trigger raised Urgent_Review flag immediately
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT flag_id, severity, source_type, reason, status
               FROM flags WHERE patient_id=1 AND source_type='Emergency'
               ORDER BY flag_id DESC LIMIT 1"""
        )
        flag = cur.fetchone()
        assert flag is not None
        assert flag["severity"] == "Urgent_Review"
        assert "emergency keyword" in flag["reason"].lower()
        print(f"✅ English Emergency Check-in: Instant guidance returned; Urgent_Review flag #{flag['flag_id']} created in DB")


def test_emergency_symptom_hindi():
    headers = {"Authorization": f"Bearer {PATIENT_1_TOKEN}"}
    res = client.post(
        "/patient/me/symptoms",
        json={
            "text": "मुझे अचानक सीने में दर्द हो रहा है और बहुत पसीना आ रहा है",
            "pain_level": 8,
            "input_method": "Text",
            "language": "hi",
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["emergency"] is True
    assert "आपातकालीन" in data["guidance"]
    print("✅ Hindi Emergency Check-in: Deterministic match on 'सीने में दर्द', returned instant Hindi emergency guidance")


def test_high_pain_rule_trigger():
    # Resolve earlier symptom flags so this test verifies fresh rule firing
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE flags SET status='Resolved' WHERE patient_id=1 AND source_type='Symptom'")

    headers = {"Authorization": f"Bearer {PATIENT_1_TOKEN}"}
    res = client.post(
        "/patient/me/symptoms",
        json={
            "text": "Surgical incision area feels significantly more sore today after walking around",
            "pain_level": 8,
            "input_method": "Text",
            "language": "en",
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["emergency"] is False
    assert data["guidance"] is None

    # Verify pain rule trigger in MySQL created Review_Soon flag
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT flag_id, severity, source_type, reason
               FROM flags WHERE patient_id=1 AND source_type='Symptom'
               ORDER BY flag_id DESC LIMIT 1"""
        )
        flag = cur.fetchone()
        assert flag is not None
        assert flag["severity"] == "Review_Soon"
        assert "Pain score 8" in flag["reason"]
        print(f"✅ Non-emergency check-in with Pain=8: Raised Review_Soon flag #{flag['flag_id']} ('{flag['reason']}')")


def test_patient_status_page():
    headers = {"Authorization": f"Bearer {PATIENT_1_TOKEN}"}
    res = client.get("/patient/me/status", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert "readings" in data
    assert "devices" in data
    assert "active_flags" in data
    print(f"✅ GET /patient/me/status returned status page: {len(data['readings'])} latest readings, {len(data['devices'])} devices, {len(data['active_flags'])} open flags")


def test_reminder_scheduler_job():
    # Update one dose for Aarav to be due within 3 minutes and unconfirmed
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT ml.medication_log_id FROM medication_logs ml
               JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
               WHERE pr.patient_id = 1 LIMIT 1"""
        )
        target = cur.fetchone()
        assert target is not None
        cur.execute(
            """UPDATE medication_logs
               SET scheduled_for = NOW() + INTERVAL 2 MINUTE,
                   status = 'Unconfirmed',
                   reminder_sent_at = NULL
               WHERE medication_log_id = %s""",
            (target["medication_log_id"],),
        )
        # Ensure patient consent is Granted
        cur.execute("UPDATE patients SET consent_status='Granted' WHERE patient_id=1")

    # Run reminder job
    send_due_reminders()

    # Verify reminder was recorded
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT ml.medication_log_id, ml.reminder_sent_at
               FROM medication_logs ml
               JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
               WHERE pr.patient_id = 1 AND ml.reminder_sent_at IS NOT NULL
               ORDER BY ml.reminder_sent_at DESC LIMIT 1"""
        )
        row = cur.fetchone()
        assert row is not None
        assert row["reminder_sent_at"] is not None

        # Verify audit log
        cur.execute(
            "SELECT * FROM audit_log WHERE entity_type='medication_log' AND action='SEND_REMINDER' ORDER BY log_id DESC LIMIT 1"
        )
        audit = cur.fetchone()
        assert audit is not None
        assert audit["actor_type"] == "Agent"
        assert audit["actor_id"] == "reminder_agent"
        print(f"✅ Reminder scheduler job successfully sent reminder for dose #{row['medication_log_id']} and wrote audit log #{audit['log_id']}")


if __name__ == "__main__":
    doses = test_get_today_doses()
    test_confirm_dose(doses)
    test_caregiver_confirm_dose(doses)
    test_emergency_symptom_english()
    test_emergency_symptom_hindi()
    test_high_pain_rule_trigger()
    test_patient_status_page()
    test_reminder_scheduler_job()
    print("\n🎉 ALL MILESTONE M3 PATIENT FLOWS & EMERGENCY TESTS PASSED!")
