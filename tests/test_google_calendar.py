"""
CareLoop — Google Calendar Integration Tests
Tests appointment Google Calendar URL generation, formatting, and endpoint access.
"""
import pytest
from datetime import datetime
from starlette.testclient import TestClient
from backend.app.main import app, make_google_calendar_url
from backend.app.auth import make_token

client = TestClient(app)

def test_make_google_calendar_url_formatting():
    appt_dt = datetime(2026, 11, 5, 10, 0, 0)
    url = make_google_calendar_url(
        appointment_id=1,
        appt_dt=appt_dt,
        doctor_name="Dr. Vikram Rao",
        specialization="Cardiology"
    )
    assert url.startswith("https://calendar.google.com/calendar/render?")
    assert "action=TEMPLATE" in url
    assert "Follow-up+visit+with+Dr.+Vikram+Rao" in url or "Follow-up%20visit" in url or "Dr.+Vikram+Rao" in url
    # IST 10:00 is UTC 04:30
    assert "20261105T043000Z%2F20261105T050000Z" in url or "20261105T043000Z/20261105T050000Z" in url
    assert "CareLoop+Hospital" in url or "CareLoop%20Hospital" in url

def test_patient_today_contains_google_calendar_url():
    token = make_token({"account_id": 1, "patient_id": 1, "account_role": "Patient", "caregiver_id": None, "staff_id": None, "email": "aarav@careloop.local"})
    res = client.get("/patient/me/today", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    if data.get("next_appointment"):
        assert "google_calendar_url" in data["next_appointment"]
        assert "calendar.google.com" in data["next_appointment"]["google_calendar_url"]
    if data.get("plan_checklist", {}).get("next_appointment"):
        next_app = data["plan_checklist"]["next_appointment"]
        assert "google_calendar_url" in next_app
        assert "calendar.google.com" in next_app["google_calendar_url"]

def test_patient_calendar_contains_google_calendar_url():
    token = make_token({"account_id": 1, "patient_id": 1, "account_role": "Patient", "caregiver_id": None, "staff_id": None, "email": "aarav@careloop.local"})
    res = client.get("/patient/me/calendar?month=2026-10", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    for appt in data.get("upcoming_appointments", []):
        assert "google_calendar_url" in appt
        assert "calendar.google.com" in appt["google_calendar_url"]

def test_appointment_google_calendar_endpoint():
    token = make_token({"account_id": 1, "patient_id": 1, "account_role": "Patient", "caregiver_id": None, "staff_id": None, "email": "aarav@careloop.local"})
    # Patient 1 has appointment 1 in seed data
    res = client.get("/patient/me/appointments/1/google-calendar-url", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["appointment_id"] == 1
    assert "google_calendar_url" in data
    assert "calendar.google.com" in data["google_calendar_url"]
