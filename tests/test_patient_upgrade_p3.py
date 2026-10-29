"""
tests/test_patient_upgrade_p3.py

Milestone Phase 3 Tests: Pain and Daily Check-in Upgrade:
- POST /patient/me/checkins:
  * Pain scale 0 to 10 validation (0-10 allowed, boundary check, -1 and 11 rejected).
  * Structured symptom chips, pain location sites, and trend tags saved to symptom_report_tags.
  * Deterministic emergency detection on emergency chips (short_of_breath, chest_pain) and emergency words.
  * Immediate emergency guidance returned without waiting for LLM.
  * Duplicate protection: same patient, same text, same pain within 60s returns existing report.
  * Voice transcript input_method stored and recorded.
  * Audit log recorded with SUBMIT_CHECKIN.
- GET /patient/me/checkins:
  * Returns last N days (default 14) check-in reports with pain score, formatted dates, tags.
  * Enforces patient token isolation (403 for doctor/nurse).
"""

import time
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import get_conn

client = TestClient(app)


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


def test_checkin_validation_and_boundaries(patient_token):
    # 1. Invalid pain > 10
    res_high = client.post(
        "/patient/me/checkins",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={"pain_level": 11, "text": "Testing high pain"},
    )
    assert res_high.status_code == 422

    # 2. Invalid pain < 0
    res_low = client.post(
        "/patient/me/checkins",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={"pain_level": -1, "text": "Testing negative pain"},
    )
    assert res_low.status_code == 422

    # 3. Invalid language
    res_lang = client.post(
        "/patient/me/checkins",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={"pain_level": 2, "language": "fr", "text": "Testing invalid language"},
    )
    assert res_lang.status_code == 422

    # 4. Text over 1000 characters
    res_len = client.post(
        "/patient/me/checkins",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={"pain_level": 2, "text": "A" * 1001},
    )
    assert res_len.status_code == 422


def test_submit_checkin_success_and_tags(patient_token):
    unique_text = f"Phase 3 test check-in at {time.time()} - walking felt okay"
    payload = {
        "pain_level": 3,
        "chips": ["tired", "wound_pain"],
        "sites": ["wound_site"],
        "trend": "same",
        "text": unique_text,
        "language": "en",
        "input_method": "Text",
    }

    res = client.post(
        "/patient/me/checkins",
        headers={"Authorization": f"Bearer {patient_token}"},
        json=payload,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "recorded"
    assert "report_id" in data
    assert data["emergency"] is False
    assert data["guidance"] is None
    report_id = data["report_id"]

    # Verify Database State
    with get_conn() as conn, conn.cursor() as cur:
        # Check symptom_reports table
        cur.execute(
            "SELECT pain_level, symptom_text, input_method, emergency_keyword_hit FROM symptom_reports WHERE symptom_report_id = %s",
            (report_id,),
        )
        row = cur.fetchone()
        assert row is not None
        assert row["pain_level"] == 3
        assert row["symptom_text"] == unique_text
        assert row["input_method"] == "Text"
        assert row["emergency_keyword_hit"] == 0

        # Check structured tags in symptom_report_tags
        cur.execute(
            "SELECT tag, extracted_by FROM symptom_report_tags WHERE symptom_report_id = %s",
            (report_id,),
        )
        tags = cur.fetchall()
        tag_dict = {t["tag"]: t["extracted_by"] for t in tags}
        assert "tired" in tag_dict
        assert "wound_pain" in tag_dict
        assert "site:wound_site" in tag_dict
        assert "trend:same" in tag_dict
        assert tag_dict["tired"] == "Patient_Form"

        # Check audit_log
        cur.execute(
            "SELECT action, entity_type, entity_id FROM audit_log WHERE entity_type = 'symptom_report' AND entity_id = %s ORDER BY log_id DESC LIMIT 1",
            (report_id,),
        )
        audit = cur.fetchone()
        assert audit is not None
        assert audit["action"] == "SUBMIT_CHECKIN"


def test_submit_checkin_emergency_chip(patient_token):
    # Emergency chip: short_of_breath or chest_pain
    unique_text = f"Breathing difficulty test at {time.time()}"
    payload = {
        "pain_level": 7,
        "chips": ["short_of_breath"],
        "sites": ["chest"],
        "trend": "worse",
        "text": unique_text,
        "language": "en",
        "input_method": "Text",
    }

    res = client.post(
        "/patient/me/checkins",
        headers={"Authorization": f"Bearer {patient_token}"},
        json=payload,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["emergency"] is True
    assert data["guidance"] is not None
    assert "112" in data["guidance"]

    # Verify DB flag hit
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT emergency_keyword_hit FROM symptom_reports WHERE symptom_report_id = %s",
            (data["report_id"],),
        )
        row = cur.fetchone()
        assert row["emergency_keyword_hit"] == 1


def test_submit_checkin_emergency_hindi(patient_token):
    # Hindi emergency text: सीने में दर्द
    unique_text = f"मुझे सीने में बहुत तेज दर्द हो रहा है {time.time()}"
    payload = {
        "pain_level": 8,
        "chips": [],
        "sites": ["chest"],
        "trend": "worse",
        "text": unique_text,
        "language": "hi",
        "input_method": "Text",
    }

    res = client.post(
        "/patient/me/checkins",
        headers={"Authorization": f"Bearer {patient_token}"},
        json=payload,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["emergency"] is True
    assert data["guidance"] is not None
    assert "112" in data["guidance"]


def test_submit_checkin_duplicate_protection(patient_token):
    # Duplicate check: same patient, same text, same pain within 60s
    dup_text = f"Identical submission test at {time.time()}"
    payload = {
        "pain_level": 2,
        "chips": ["tired"],
        "sites": [],
        "trend": "same",
        "text": dup_text,
        "language": "en",
        "input_method": "Text",
    }

    # 1. First submission
    res1 = client.post(
        "/patient/me/checkins",
        headers={"Authorization": f"Bearer {patient_token}"},
        json=payload,
    )
    assert res1.status_code == 200, res1.text
    data1 = res1.json()
    assert data1["status"] == "recorded"
    orig_report_id = data1["report_id"]

    # 2. Second submission immediately with identical text and pain
    res2 = client.post(
        "/patient/me/checkins",
        headers={"Authorization": f"Bearer {patient_token}"},
        json=payload,
    )
    assert res2.status_code == 200, res2.text
    data2 = res2.json()
    assert data2["status"] == "duplicate_prevented"
    assert data2["report_id"] == orig_report_id


def test_submit_checkin_voice_transcript(patient_token):
    # Voice input method test
    unique_text = f"Dictated via microphone test at {time.time()}"
    payload = {
        "pain_level": 1,
        "chips": [],
        "sites": ["legs"],
        "trend": "better",
        "text": unique_text,
        "language": "en",
        "input_method": "Voice_Transcript",
    }

    res = client.post(
        "/patient/me/checkins",
        headers={"Authorization": f"Bearer {patient_token}"},
        json=payload,
    )
    assert res.status_code == 200, res.text
    data = res.json()

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT input_method FROM symptom_reports WHERE symptom_report_id = %s",
            (data["report_id"],),
        )
        row = cur.fetchone()
        assert row["input_method"] == "Voice_Transcript"


def test_get_checkins_history_and_isolation(patient_token, doctor_token):
    # 1. Doctor token forbidden
    res_doc = client.get("/patient/me/checkins", headers={"Authorization": f"Bearer {doctor_token}"})
    assert res_doc.status_code == 403

    # 2. Patient token success
    res = client.get("/patient/me/checkins?days=14", headers={"Authorization": f"Bearer {patient_token}"})
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["days"] == 14
    assert "count" in data
    assert "reports" in data
    assert isinstance(data["reports"], list)
    assert len(data["reports"]) > 0

    first = data["reports"][0]
    assert "id" in first
    assert "reported_at" in first
    assert "formatted_date" in first
    assert "pain_level" in first
    assert "text" in first
    assert "input_method" in first
    assert "language" in first
    assert "emergency" in first
    assert "tags" in first
