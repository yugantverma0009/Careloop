"""
tests/test_patient_upgrade_p2.py

Milestone Phase 2 Tests: Calendar & Plan Checklist:
- GET /patient/me/calendar:
  * Returns month summary (month, month_name, days[], upcoming_appointments).
  * Days array has planned, taken, skipped, not_confirmed, appointments, checkin_count, max_pain.
  * Rejects invalid month format with 400.
  * Enforces patient token isolation (403 for doctor/nurse).
- GET /patient/me/day?date=YYYY-MM-DD:
  * Returns day inspection sheet payload (doses, appointments, checkins).
  * Rejects invalid date format with 400.
- GET /patient/me/appointments/{id}.ics:
  * Generates standard RFC 5545 iCalendar (.ics) file.
  * Formats UTC timestamps (DTSTART, DTEND).
  * Contains SUMMARY and DESCRIPTION with no clinical diagnosis details.
  * Returns 404 for non-existent appointment or appointment belonging to another patient.
- Plan checklist on /patient/me/today:
  * Contains next_appointment, course_end_date, checkins_this_week, day_after_discharge.
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


def test_calendar_endpoint_schema_and_isolation(patient_token, doctor_token):
    # 1. Doctor token forbidden
    res_doc = client.get("/patient/me/calendar", headers={"Authorization": f"Bearer {doctor_token}"})
    assert res_doc.status_code == 403

    # 2. Patient token success
    res = client.get("/patient/me/calendar?month=2026-10", headers={"Authorization": f"Bearer {patient_token}"})
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["month"] == "2026-10"
    assert "October 2026" in data["month_name"]
    assert "days" in data
    assert len(data["days"]) == 31  # October has 31 days

    # Check day shape
    day1 = data["days"][0]
    assert "date" in day1
    assert "day" in day1
    assert "day_of_week" in day1
    assert "planned" in day1
    assert "taken" in day1
    assert "skipped" in day1
    assert "not_confirmed" in day1
    assert "has_appointment" in day1
    assert "has_checkin" in day1
    assert "max_pain" in day1

    # Check 2026-10-29 has activity from seed data
    day29 = [d for d in data["days"] if d["date"] == "2026-10-29"][0]
    assert day29["planned"] > 0
    assert day29["has_checkin"] is True

    # 3. Invalid month returns 400
    res_bad = client.get("/patient/me/calendar?month=2026-13", headers={"Authorization": f"Bearer {patient_token}"})
    assert res_bad.status_code == 400

    res_bad2 = client.get("/patient/me/calendar?month=invalid", headers={"Authorization": f"Bearer {patient_token}"})
    assert res_bad2.status_code == 400


def test_day_endpoint_detail(patient_token):
    # 1. Valid date inspection
    res = client.get("/patient/me/day?date=2026-10-29", headers={"Authorization": f"Bearer {patient_token}"})
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["date"] == "2026-10-29"
    assert "doses" in data
    assert "appointments" in data
    assert "checkins" in data
    assert isinstance(data["doses"], list)
    assert isinstance(data["appointments"], list)
    assert isinstance(data["checkins"], list)

    # Doses should have status and instructions
    if data["doses"]:
        d = data["doses"][0]
        assert "medicine" in d
        assert "dose_instructions" in d
        assert "status" in d

    # 2. Invalid date format returns 400
    res_bad = client.get("/patient/me/day?date=bad-date", headers={"Authorization": f"Bearer {patient_token}"})
    assert res_bad.status_code == 400

    res_bad2 = client.get("/patient/me/day?date=2026-02-31", headers={"Authorization": f"Bearer {patient_token}"})
    assert res_bad2.status_code == 400


def test_appointment_ics_download_and_safety(patient_token):
    # 1. Fetch Aarav's appointment ID
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT appointment_id FROM appointments WHERE patient_id=1 LIMIT 1")
        appt = cur.fetchone()
        assert appt is not None, "Seed data must have at least one appointment for patient 1"
        appt_id = appt["appointment_id"]

    # 2. Download .ics file
    res = client.get(f"/patient/me/appointments/{appt_id}.ics", headers={"Authorization": f"Bearer {patient_token}"})
    assert res.status_code == 200, res.text
    assert "text/calendar" in res.headers["content-type"]
    assert f'filename="appointment_{appt_id}.ics"' in res.headers.get("content-disposition", "")

    ics_text = res.text
    assert "BEGIN:VCALENDAR" in ics_text
    assert "VERSION:2.0" in ics_text
    assert "BEGIN:VEVENT" in ics_text
    assert f"UID:appointment-{appt_id}@careloop" in ics_text
    assert "DTSTART:" in ics_text
    assert "DTEND:" in ics_text
    assert "SUMMARY:Follow-up visit with" in ics_text
    assert "END:VEVENT" in ics_text
    assert "END:VCALENDAR" in ics_text

    # Safety check: Strictly no diagnosis details in the ICS export (Brief Sec 8.5)
    forbidden_terms = ["Coronary", "Hypertension", "CABG", "Infarction", "Ischemia", "Diabetes"]
    for term in forbidden_terms:
        assert term.lower() not in ics_text.lower(), f"Forbidden clinical term '{term}' leaked into ICS file"

    # 3. Non-existent appointment returns 404
    res_404 = client.get("/patient/me/appointments/999999.ics", headers={"Authorization": f"Bearer {patient_token}"})
    assert res_404.status_code == 404


def test_appointment_ics_wrong_patient_isolation(patient_token):
    # If appointment belongs to another patient, accessing it must return 404
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT appointment_id FROM appointments WHERE patient_id != 1 LIMIT 1")
        row = cur.fetchone()
        assert row is not None, "Need at least one appointment belonging to another patient"
        other_appt_id = row["appointment_id"]

    # Patient 1 (Aarav) requests another patient's appointment
    res = client.get(f"/patient/me/appointments/{other_appt_id}.ics", headers={"Authorization": f"Bearer {patient_token}"})
    assert res.status_code == 404, f"Expected 404 for other patient appointment, got {res.status_code}"


def test_today_plan_checklist(patient_token):
    # Verify plan checklist fields on /patient/me/today
    res = client.get("/patient/me/today", headers={"Authorization": f"Bearer {patient_token}"})
    assert res.status_code == 200, res.text
    data = res.json()

    assert "plan_checklist" in data
    chk = data["plan_checklist"]
    assert "next_appointment" in chk
    assert "course_end_date" in chk
    assert "checkins_this_week" in chk
    assert "day_after_discharge" in chk

    # Checkins this week must have "X of 7 days" format
    assert "of 7 days" in chk["checkins_this_week"]
    assert chk["day_after_discharge"] >= 1
