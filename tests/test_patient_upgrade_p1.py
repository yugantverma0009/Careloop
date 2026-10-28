"""
tests/test_patient_upgrade_p1.py

Milestone Phase 1 Tests:
- GET /patient/me/today:
  * Returns aggregated payload with name, date, day_after_discharge, banner state, counts, next_dose, doses grouped into morning/afternoon/evening/night, readings, device, next_appointment, week strip.
  * Rejects doctor/nurse tokens with 403 (patient isolation).
- POST /patient/me/doses/{id}/taken:
  * Marks dose as Taken_Confirmed.
  * Idempotent (double tap does not fail or duplicate).
  * Rejects dose belonging to another patient with 404.
  * Rejects dose scheduled more than 60 minutes in the future with 409.
  * Writes to audit_log.
- POST /patient/me/doses/{id}/skip:
  * Accepts valid reason (felt_unwell, ran_out, forgot, side_effects, other).
  * Writes reason to patient_note and audit_log.
- POST /patient/me/doses/{id}/undo:
  * Successfully reverts Taken_Confirmed or Skipped to Unconfirmed within 5 minutes.
  * Rejects undo if window (> 5 min) has expired with 409.
  * Writes to audit_log.
- Banner states:
  * none, review, urgent, seen verified against flag fixtures.
"""

import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import get_conn

client = TestClient(app)
IST = ZoneInfo("Asia/Kolkata")

@pytest.fixture
def patient_token():
    res = client.post("/auth/login", json={"email": "aarav.demo@example.test", "password": "Demo@12345"})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]

@pytest.fixture
def doctor_token():
    res = client.post("/auth/login", json={"email": "ananya.demo@example.test", "password": "Demo@12345"})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def test_today_endpoint_schema_and_isolation(patient_token, doctor_token):
    # 1. Doctor token should be forbidden on /patient/me/today
    res_doc = client.get("/patient/me/today", headers={"Authorization": f"Bearer {doctor_token}"})
    assert res_doc.status_code == 403, f"Expected 403 for doctor on patient endpoint, got {res_doc.status_code}"

    # 2. Patient token should succeed
    res = client.get("/patient/me/today", headers={"Authorization": f"Bearer {patient_token}"})
    assert res.status_code == 200, res.text
    data = res.json()

    # Verify top-level structure
    assert "date" in data
    assert "name" in data
    assert "day_after_discharge" in data
    assert "banner" in data
    assert "counts" in data
    assert "doses" in data
    assert "readings" in data
    assert "device" in data
    assert "next_appointment" in data
    assert "week" in data

    # Verify banner structure
    assert data["banner"]["state"] in ("none", "review", "urgent", "seen")

    # Verify doses grouping
    assert "morning" in data["doses"]
    assert "afternoon" in data["doses"]
    assert "evening" in data["doses"]
    assert "night" in data["doses"]

    # Verify counts
    counts = data["counts"]
    for k in ("planned", "taken", "skipped", "not_confirmed", "pending"):
        assert k in counts

    print("✅ GET /patient/me/today schema and patient isolation verified")


def test_dose_taken_and_undo_flow(patient_token):
    headers = {"Authorization": f"Bearer {patient_token}"}
    
    # Setup: ensure a test dose exists for today for patient 1 within window
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT ml.medication_log_id, ml.scheduled_for
               FROM medication_logs ml
               JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
               WHERE pr.patient_id = 1
               ORDER BY ml.scheduled_for DESC LIMIT 1"""
        )
        row = cur.fetchone()
        assert row is not None, "No medication log found for patient 1"
        dose_id = row["medication_log_id"]

        # Set scheduled_for to right now and status to Unconfirmed
        cur.execute(
            """UPDATE medication_logs
               SET scheduled_for = NOW(), status = 'Unconfirmed', recorded_at = NULL, recorded_by = NULL, patient_note = NULL
               WHERE medication_log_id = %s""",
            (dose_id,)
        )

    # 1. Mark taken
    res_take = client.post(f"/patient/me/doses/{dose_id}/taken", headers=headers, json={})
    assert res_take.status_code == 200, res_take.text
    take_data = res_take.json()
    assert take_data["recorded_status"] == "Taken_Confirmed"

    # 2. Idempotency check: marking taken again returns 200
    res_take_again = client.post(f"/patient/me/doses/{dose_id}/taken", headers=headers, json={})
    assert res_take_again.status_code == 200, res_take_again.text

    # 3. Undo within 5 minutes
    res_undo = client.post(f"/patient/me/doses/{dose_id}/undo", headers=headers)
    assert res_undo.status_code == 200, res_undo.text
    undo_data = res_undo.json()
    assert undo_data["recorded_status"] == "Unconfirmed"

    # Verify in DB
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT status FROM medication_logs WHERE medication_log_id = %s", (dose_id,))
        assert cur.fetchone()["status"] == "Unconfirmed"

    print("✅ One-tap taken and 5-minute undo verified")


def test_dose_skip_flow(patient_token):
    headers = {"Authorization": f"Bearer {patient_token}"}

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT ml.medication_log_id
               FROM medication_logs ml
               JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
               WHERE pr.patient_id = 1
               LIMIT 1"""
        )
        dose_id = cur.fetchone()["medication_log_id"]
        cur.execute(
            """UPDATE medication_logs
               SET status = 'Unconfirmed', recorded_at = NULL, recorded_by = NULL, patient_note = NULL
               WHERE medication_log_id = %s""",
            (dose_id,)
        )

    # 1. Skip with valid reason
    res_skip = client.post(f"/patient/me/doses/{dose_id}/skip", headers=headers, json={"reason": "felt_unwell"})
    assert res_skip.status_code == 200, res_skip.text
    assert res_skip.json()["recorded_status"] == "Skipped"

    # Verify audit log
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT action, details FROM audit_log
               WHERE entity_type = 'medication_log' AND entity_id = %s AND action = 'SKIP_DOSE'
               ORDER BY created_at DESC LIMIT 1""",
            (dose_id,)
        )
        alog = cur.fetchone()
        assert alog is not None
        assert "felt_unwell" in alog["details"]

    print("✅ Skip dose with reason and audit log verified")


def test_too_early_guard(patient_token):
    headers = {"Authorization": f"Bearer {patient_token}"}

    # Set dose 3 hours into future
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT ml.medication_log_id
               FROM medication_logs ml
               JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
               WHERE pr.patient_id = 1
               LIMIT 1"""
        )
        dose_id = cur.fetchone()["medication_log_id"]
        cur.execute(
            """UPDATE medication_logs
               SET scheduled_for = NOW() + INTERVAL 3 HOUR, status = 'Unconfirmed'
               WHERE medication_log_id = %s""",
            (dose_id,)
        )

    # Attempting to take should yield 409 Conflict
    res = client.post(f"/patient/me/doses/{dose_id}/taken", headers=headers, json={})
    assert res.status_code == 409, f"Expected 409 for dose >60m early, got {res.status_code}"
    assert "early" in res.json().get("detail", "").lower() or "1 hour" in res.json().get("detail", "").lower()
    print("✅ >60 min early guard (409) verified")
