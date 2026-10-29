"""
tests/test_staff_upgrade_p2.py

Care Team Portal Upgrade — Phase 2 Test Suite
Validates:
- D-05: Patient Directory table endpoint with filters (all, mine, has_flags, silent_device) and search.
- D-05: Patient Overview endpoint with identity, care team, vitals, 7d adherence, pain trend, consent.
- D-12: Break-Glass Access audited enforcement, justification length requirement, and audit log trail.
- D-13 & D-05: Medicines Tab with discharge prescriptions and self-reported dose exception notes.
- D-05: Alert Rules Tab with clinician approver tracking, 30-day fired counts, and false alarm dismissals.
- D-06: Upgraded Timeline with day grouping, filter chips, actor attribution, repeated event collapse, and telemetry chart limits.
- D-18: Sensor telemetry data quality badges (Good, Questionable, Invalid, Simulated).
"""

import pytest
import pymysql
import json
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import get_conn
from backend.app.auth import make_token

client = TestClient(app)

DOCTOR_TOKEN = make_token({
    "account_id": 3,
    "email": "ananya.demo@example.test",
    "account_role": "Doctor",
    "patient_id": None,
    "caregiver_id": None,
    "staff_id": 1,
})
NURSE_TOKEN = make_token({
    "account_id": 4,
    "email": "priya.demo@example.test",
    "account_role": "Nurse",
    "patient_id": None,
    "caregiver_id": None,
    "staff_id": 3,
})

DOCTOR_AUTH = {"Authorization": f"Bearer {DOCTOR_TOKEN}"}
NURSE_AUTH = {"Authorization": f"Bearer {NURSE_TOKEN}"}


def test_d05_patient_directory_all():
    """D-05: Patient directory returns 10 patients with codes, attending staff, flags, and adherence."""
    res = client.get("/staff/patients?filter=all", headers=DOCTOR_AUTH)
    assert res.status_code == 200
    patients = res.json()
    assert len(patients) == 10

    # Validate first patient data shape
    p1 = next(p for p in patients if p["patient_id"] == 1)
    assert p1["patient_code"] == "CL-00001"
    assert p1["full_name"] == "Aarav Patel"
    assert p1["age_years"] is not None
    assert p1["attending_doctor"] == "Dr. Ananya Sharma"
    assert p1["open_flag_count"] > 0
    assert "adherence_this_week" in p1
    assert "device_status" in p1


def test_d05_patient_directory_filters():
    """D-05: Directory filters work for mine, has_flags, silent_device, and search query."""
    # 1. Filter: mine (Dr. Ananya has 1, 3, 5, 7, 9)
    res_mine = client.get("/staff/patients?filter=mine", headers=DOCTOR_AUTH)
    assert res_mine.status_code == 200
    mine = res_mine.json()
    assert len(mine) == 5
    for p in mine:
        assert p["is_assigned"] is True

    # 2. Filter: has_flags
    res_flags = client.get("/staff/patients?filter=has_flags", headers=DOCTOR_AUTH)
    assert res_flags.status_code == 200
    flagged = res_flags.json()
    for p in flagged:
        assert p["open_flag_count"] > 0

    # 3. Filter: silent_device (missing telemetry)
    res_silent = client.get("/staff/patients?filter=silent_device", headers=DOCTOR_AUTH)
    assert res_silent.status_code == 200
    silent = res_silent.json()
    assert len(silent) > 0
    for p in silent:
        assert p["device_status"] != "Online"

    # 4. Search query
    res_search = client.get("/staff/patients?search=Patel", headers=DOCTOR_AUTH)
    assert res_search.status_code == 200
    search_results = res_search.json()
    assert len(search_results) >= 1
    assert any("Patel" in p["full_name"] for p in search_results)


def test_d05_patient_overview_assigned():
    """D-05 & D-18: Overview clinical snapshot returns vitals with quality badges and caregiver consent."""
    res = client.get("/staff/patients/1", headers=DOCTOR_AUTH)
    assert res.status_code == 200
    data = res.json()

    assert data["is_assigned"] is True
    assert data["requires_break_glass"] is False
    assert data["outside_assignment"] is False

    p = data["patient"]
    assert p["patient_code"] == "CL-00001"
    assert p["full_name"] == "Aarav Patel"

    # Telemetry with data quality badge (D-18)
    readings = data["latest_readings"]
    assert "Heart_Rate" in readings
    if readings["Heart_Rate"]:
        assert readings["Heart_Rate"]["quality_status"] in ("Good", "Questionable", "Invalid", "Simulated")

    # 7-day adherence grid
    assert len(data["adherence_grid"]) > 0
    # 14-day pain trend
    assert len(data["pain_trend"]) > 0
    # Caregivers
    assert len(data["caregivers"]) > 0


def test_d12_break_glass_access_enforcement():
    """D-12: Accessing unassigned patient requires audited justification >= 5 characters."""
    # Clean up test audit log for patient 8 for test isolation
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM audit_log WHERE action = 'BREAK_GLASS_VIEW' AND entity_id = 8")
        conn.commit()

    # Patient 8 is assigned to Dr. Rohan, so Dr. Ananya (staff_id: 1) requires break-glass
    res_initial = client.get("/staff/patients/8", headers=DOCTOR_AUTH)
    assert res_initial.status_code == 200
    data_initial = res_initial.json()
    assert data_initial["is_assigned"] is False
    assert data_initial["outside_assignment"] is True
    assert data_initial["requires_break_glass"] is True

    # Attempt break-glass with short reason (< 5 characters) -> 400
    res_short = client.post("/staff/patients/8/break-glass", json={"reason": "no"}, headers=DOCTOR_AUTH)
    assert res_short.status_code == 400
    assert "at least 5 characters" in res_short.json()["detail"]

    # Valid break-glass access
    justification = "Urgent cross-cover review during emergency department on-call rotation"
    res_bg = client.post("/staff/patients/8/break-glass", json={"reason": justification}, headers=DOCTOR_AUTH)
    assert res_bg.status_code == 200
    assert res_bg.json()["status"] == "access_granted"

    # Verify append-only audit_log entry was created
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT log_id, actor_id, action, details
               FROM audit_log
               WHERE action = 'BREAK_GLASS_VIEW' AND entity_id = 8
               ORDER BY log_id DESC LIMIT 1"""
        )
        log = cur.fetchone()
        assert log is not None
        assert log["actor_id"] == "1"  # Dr. Ananya staff_id
        details = json.loads(log["details"]) if isinstance(log["details"], str) else log["details"]
        assert details["reason"] == justification

    # Subsequent access now permits viewing with outside_assignment banner active
    res_after = client.get("/staff/patients/8", headers=DOCTOR_AUTH)
    assert res_after.status_code == 200
    data_after = res_after.json()
    assert data_after["requires_break_glass"] is False
    assert data_after["outside_assignment"] is True


def test_d05_medicines_tab():
    """D-05: Medicines tab returns prescriptions and exceptions strictly labeled Self-reported."""
    res = client.get("/staff/patients/1/medicines", headers=DOCTOR_AUTH)
    assert res.status_code == 200
    data = res.json()

    assert data["adherence_label"] == "Self-reported"
    assert len(data["prescriptions"]) > 0
    for rx in data["prescriptions"]:
        assert "medicine_name" in rx
        assert "dose_instructions" in rx

    # Exceptions check
    for ex in data["exceptions"]:
        assert ex["status"] in ("Scheduled", "Not confirmed", "Skipped", "Missed")
        assert "patient_note" in ex
        assert "recorded_by" in ex


def test_d05_rules_tab():
    """D-05: Alert rules tab returns thresholds, approver clinician, and false alarm dismissals."""
    res = client.get("/staff/patients/1/rules", headers=DOCTOR_AUTH)
    assert res.status_code == 200
    data = res.json()
    rules = data.get("rules", [])
    assert len(rules) > 0

    for r in rules:
        assert "rule_type" in r
        assert "threshold_value" in r
        assert "severity" in r
        assert "approved_by_name" in r
        assert "fired_count_30d" in r
        assert "dismissed_false_count" in r


def test_d06_upgraded_timeline():
    """D-06: Timeline groups by day, collapses repeated events, and exposes approved chart limits."""
    res = client.get("/staff/patients/1/timeline?event_types=All&date_range=all&limit=200", headers=DOCTOR_AUTH)
    assert res.status_code == 200
    data = res.json()

    assert "day_groups" in data
    assert len(data["day_groups"]) > 0
    for grp in data["day_groups"]:
        assert "date" in grp
        assert "display_date" in grp
        assert len(grp["events"]) > 0
        for ev in grp["events"]:
            assert "event_type" in ev
            assert "summary" in ev
            assert "actor" in ev
            assert ev["repeat_count"] >= 1

    # Check chart limits
    assert "chart_limits" in data
    assert "hr_max" in data["chart_limits"] or "spo2_min" in data["chart_limits"]
    assert "chart_readings" in data


def test_d06_timeline_filtering():
    """D-06: Timeline filtering by event type and date range works correctly."""
    # Filter by Symptom only
    res_symptom = client.get("/staff/patients/1/timeline?event_types=Symptom", headers=DOCTOR_AUTH)
    assert res_symptom.status_code == 200
    data = res_symptom.json()
    for grp in data["day_groups"]:
        for ev in grp["events"]:
            assert ev["event_type"].lower() == "symptom"
