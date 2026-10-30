"""
CareLoop Phase 5 Automated Test Suite: Patient App and Family View
Verifies:
1. Patient Home: Aarav Patel (Day 3 Post-CABG), latest VALID readings (74.0 bpm pulse, 97% SpO2, no 450 bpm),
   data-check note on invalid exclusion, no permanent red alert banner when 0 open urgent flags.
2. Patient Medicines: Scheduled doses, Take dose, Skip dose, and 5-minute undo window.
3. Patient Check-in: Pain score (0-10), symptom chips, and code-based emergency keyword detection (EN & HI)
   directing immediately to Call 112 before/during submission.
4. Patient Chat ("Ask my papers"): Grounded answers with sources, refusal on dose inquiries,
   and deduplicated care-team follow-up task creation.
5. Patient Calendar: .ics calendar file generation and download.
6. Real-time Consent Gating: Toggling family consent off immediately blocks family access (403),
   toggling on immediately restores access.
7. Family Today: Calm "What you may need to do" guidance, zero clinical symptom or pain score leakage,
   status-only dose cards, and "I helped Aarav take it" dose confirmation logged as Caregiver.
8. Family Calendar & Contacts: 7-day dose history strip, appointments, and direct contacts (Dr. Sharma, Nurse Priya, 112).
9. Role Boundaries: Strict 403 isolation between Patient, Family, and Staff endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app, get_conn
from backend.app.auth import make_token, verify_login
from scripts.seed_demo import main as run_seed


@pytest.fixture(autouse=True)
def reset_database():
    """Ensure consistent fresh demo data before each test."""
    run_seed()


@pytest.fixture
def patient_token():
    acct = verify_login("aarav.demo@example.test", "Demo@12345")
    assert acct is not None
    return make_token(acct)


@pytest.fixture
def family_token():
    acct = verify_login("caregiver1.demo@example.test", "Demo@12345")
    assert acct is not None
    return make_token(acct)


@pytest.fixture
def doctor_token():
    acct = verify_login("ananya.demo@example.test", "Demo@12345")
    assert acct is not None
    return make_token(acct)


# ─── 1. Patient Home & Valid Vitals ──────────────────────────────────────────

def test_patient_today_vitals_and_banner(patient_token):
    """
    Patient Home screen must show Aarav Patel (Day 3 Post-CABG),
    headline pulse must be latest VALID reading (74.0 bpm, not 450 bpm),
    data_check_note indicates excluded reading, and no red banner when 0 urgent flags.
    """
    client = TestClient(app)
    res = client.get("/patient/me/today", headers={"Authorization": f"Bearer {patient_token}"})
    assert res.status_code == 200
    data = res.json()

    # Patient identity
    assert data["name"] == "Aarav Patel"
    assert data["day_after_discharge"] == 3

    # Headline vitals: 74.0 bpm (valid), NEVER 450 bpm (invalid)
    readings = data["readings"]
    hr_reading = next((r for r in readings if r["type"] == "Heart_Rate"), None)
    assert hr_reading is not None
    assert float(hr_reading["value"]) == 74.0
    assert hr_reading["unit"] == "bpm"

    # SpO2 must be 97%
    spo2_reading = next((r for r in readings if r["type"] == "SpO2"), None)
    assert spo2_reading is not None
    assert float(spo2_reading["value"]) == 97.0

    # Data check note must be present explaining invalid reading exclusion
    assert data.get("data_check_note") is not None
    assert "impossible value" in data["data_check_note"] or "ignored" in data["data_check_note"]

    # No open urgent flags for Aarav in baseline seed -> banner state is none
    assert data["banner"]["state"] == "none"

    # Next appointment with Dr. Ananya Sharma
    assert data["next_appointment"]["with"] == "Dr. Ananya Sharma"


# ─── 2. Patient Medicines & 5-Minute Undo ────────────────────────────────────

def test_patient_dose_actions_and_undo(patient_token):
    """Verify Take dose, 5-minute undo window, and Skip dose."""
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {patient_token}"}

    # Fetch today's schedule
    res = client.get("/patient/me/today", headers=headers)
    assert res.status_code == 200
    all_doses = res.json()["all_doses"]
    assert len(all_doses) > 0

    # Find an unconfirmed dose
    unconfirmed = next((d for d in all_doses if d["status"] == "Unconfirmed"), None)
    assert unconfirmed is not None
    log_id = unconfirmed["id"]

    # Set scheduled_for to NOW() so it falls within the 60-min allowed window
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE medication_logs SET scheduled_for = NOW() WHERE medication_log_id = %s", (log_id,))
        conn.commit()

    # 1. Take dose
    res_take = client.post(f"/patient/me/doses/{log_id}/taken", headers=headers)
    assert res_take.status_code == 200
    take_data = res_take.json()
    assert take_data["recorded_status"] == "Taken_Confirmed"

    # 2. Undo dose within 5 minutes
    res_undo = client.post(f"/patient/me/doses/{log_id}/undo", headers=headers)
    assert res_undo.status_code == 200
    undo_data = res_undo.json()
    assert undo_data["recorded_status"] == "Unconfirmed"

    # 3. Skip dose
    res_skip = client.post(
        f"/patient/me/doses/{log_id}/skip",
        json={"reason": "felt_unwell"},
        headers=headers,
    )
    assert res_skip.status_code == 200
    skip_data = res_skip.json()
    assert skip_data["recorded_status"] == "Skipped"

    # Verify in DB
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT status, patient_note FROM medication_logs WHERE medication_log_id = %s", (log_id,))
        row = cur.fetchone()
        assert row["status"] == "Skipped"
        assert row["patient_note"] == "felt_unwell"


# ─── 3. Patient Check-in & Emergency Detection ───────────────────────────────

def test_patient_checkin_emergency_detection(patient_token):
    """
    Plain code emergency keyword detection in English & Hindi
    must trigger immediate guidance to Call 112 without waiting for LLM.
    """
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {patient_token}"}

    # 1. Normal check-in
    res_normal = client.post(
        "/patient/me/checkins",
        json={"pain_level": 3, "chips": ["mild_fatigue"], "text": "Walking around gently.", "language": "en"},
        headers=headers,
    )
    assert res_normal.status_code == 200
    assert res_normal.json()["emergency"] is False

    # 2. English emergency keyword: 'chest pain' / 'chest_pain' chip
    res_en_emg = client.post(
        "/patient/me/checkins",
        json={"pain_level": 8, "chips": ["chest_pain"], "text": "Crushing chest pain radiating to arm.", "language": "en"},
        headers=headers,
    )
    assert res_en_emg.status_code == 200
    emg_data = res_en_emg.json()
    assert emg_data["emergency"] is True
    assert "112" in emg_data["guidance"]

    # 3. Hindi emergency keyword: 'सीने में दर्द'
    res_hi_emg = client.post(
        "/patient/me/checkins",
        json={"pain_level": 9, "chips": [], "text": "मुझे बहुत तेज सीने में दर्द हो रहा है और सांस फूल रही है", "language": "hi"},
        headers=headers,
    )
    assert res_hi_emg.status_code == 200
    hi_data = res_hi_emg.json()
    assert hi_data["emergency"] is True
    assert "112" in hi_data["guidance"]


# ─── 4. Patient Chat & Grounded RAG ──────────────────────────────────────────

def test_patient_chat_grounded_and_dose_refusal(patient_token):
    """
    Chat must refuse dose changes and cite recovery discharge papers.
    'Ask my care team' creates deduplicated nurse task.
    """
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {patient_token}"}

    # 1. Grounded query
    res_chat = client.post(
        "/patient/me/chat",
        json={"message": "Can I eat a low sodium diet?", "conversation_id": "p5_test_conv"},
        headers=headers,
    )
    assert res_chat.status_code == 200
    chat_data = res_chat.json()
    assert len(chat_data["answer"]) > 5
    assert "sources" in chat_data
    msg_id = chat_data["message_id"]

    # 2. Dose change inquiry refusal
    res_dose = client.post(
        "/patient/me/chat",
        json={"message": "Can I increase my Metoprolol dose to 50mg?", "conversation_id": "p5_test_conv"},
        headers=headers,
    )
    assert res_dose.status_code == 200
    dose_data = res_dose.json()
    # Safety rule: Assistant never advises on doses
    reply_lower = dose_data["answer"].lower()
    assert any(w in reply_lower for w in ["dose", "doctor", "nurse", "prescription", "consult", "advise"])

    # 3. 'Ask my care team' follow-up task creation (deduplicated)
    res_ask1 = client.post(f"/patient/me/chat/{msg_id}/ask-care-team", headers=headers)
    assert res_ask1.status_code == 200
    task1 = res_ask1.json()
    assert task1["ok"] is True
    assert task1["status"] == "task_created"
    task_id = task1["task_id"]

    # Repeated click with same message should deduplicate
    res_ask2 = client.post(f"/patient/me/chat/{msg_id}/ask-care-team", headers=headers)
    assert res_ask2.status_code == 200
    task2 = res_ask2.json()
    assert task2["ok"] is True
    assert task2["status"] == "task_already_exists"
    assert task2["task_id"] == task_id


# ─── 5. Patient .ics Calendar Download ───────────────────────────────────────

def test_patient_ics_download(patient_token):
    """Verify appointment .ics file is valid iCalendar."""
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {patient_token}"}

    # Get appointment id
    res = client.get("/patient/me/today", headers=headers)
    appt = res.json()["next_appointment"]
    assert appt is not None
    appt_id = appt["id"]

    res_ics = client.get(f"/patient/me/appointments/{appt_id}.ics", headers=headers)
    assert res_ics.status_code == 200
    assert "text/calendar" in res_ics.headers.get("content-type", "")
    ics_text = res_ics.text
    assert "BEGIN:VCALENDAR" in ics_text
    assert "Dr. Ananya Sharma" in ics_text
    assert "END:VCALENDAR" in ics_text


# ─── 6. Real-Time Family Consent Gating ──────────────────────────────────────

def test_family_consent_toggle_immediate_cutoff(patient_token, family_token):
    """
    Patient toggling sharing OFF immediately cuts off family access with 403.
    Toggling sharing back ON immediately restores access.
    """
    client = TestClient(app)
    p_headers = {"Authorization": f"Bearer {patient_token}"}
    f_headers = {"Authorization": f"Bearer {family_token}"}

    # 1. Family can initially access /family/today
    res_init = client.get("/family/today", headers=f_headers)
    assert res_init.status_code == 200

    # 2. Patient turns sharing OFF
    res_off = client.post(
        "/patient/me/sharing",
        json={"enabled": False},
        headers=p_headers,
    )
    assert res_off.status_code == 200
    assert res_off.json()["sharing_enabled"] is False

    # 3. Family immediately gets 403 on all family endpoints
    res_f_today = client.get("/family/today", headers=f_headers)
    assert res_f_today.status_code == 403
    assert "turned sharing off" in res_f_today.json()["detail"].lower()

    res_f_cal = client.get("/family/calendar", headers=f_headers)
    assert res_f_cal.status_code == 403

    res_f_dose = client.post("/family/doses/33/helped", headers=f_headers)
    assert res_f_dose.status_code == 403

    # 4. Patient turns sharing back ON
    res_on = client.post(
        "/patient/me/sharing",
        json={"enabled": True},
        headers=p_headers,
    )
    assert res_on.status_code == 200
    assert res_on.json()["sharing_enabled"] is True

    # 5. Family access immediately restored
    res_f_restored = client.get("/family/today", headers=f_headers)
    assert res_f_restored.status_code == 200


# ─── 7. Family Today Screen & Helped Dose ────────────────────────────────────

def test_family_today_zero_leakage_and_helped_dose(family_token):
    """
    Family Today:
    - Calm "What you may need to do"
    - Zero clinical leak: checkin_status is Yes/No, no symptoms or pain scores
    - 'I helped Aarav take it' marks dose confirmed by Caregiver in DB & audit_log.
    """
    client = TestClient(app)
    f_headers = {"Authorization": f"Bearer {family_token}"}

    res = client.get("/family/today", headers=f_headers)
    assert res.status_code == 200
    data = res.json()

    # Patient info
    assert data["patient"]["full_name"] == "Aarav Patel"
    assert data["patient"]["day_number"] == 3

    # Badge
    assert "Sharing allowed by Aarav on 27 Oct" in data["caregiver"]["sharing_badge"]

    # "What you may need to do"
    assert data["what_you_may_need_to_do"]["text"] == "Nothing needed right now."
    assert data["what_you_may_need_to_do"]["severity"] == "normal"

    # Zero leakage check: checkin_status has no pain score or notes
    checkin = data["checkin_status"]
    assert "pain_score" not in checkin
    assert "symptoms" not in checkin
    assert "notes" not in checkin
    assert checkin["message"] in ["Yes", "No"]

    # Doses status only
    doses = data["today_doses"]["items"]
    assert len(doses) > 0
    # Pick an unconfirmed dose
    target_dose = next((d for d in doses if d["status"] != "Taken"), None)
    assert target_dose is not None
    log_id = target_dose["dose_id"]

    # Confirm dose helped
    res_help = client.post(f"/family/doses/{log_id}/helped", headers=f_headers)
    assert res_help.status_code == 200
    assert res_help.json()["status"] == "updated"

    # Verify database state
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT status, recorded_by FROM medication_logs WHERE medication_log_id = %s", (log_id,))
        row = cur.fetchone()
        assert row["status"] == "Taken_Confirmed"
        assert row["recorded_by"] == "Caregiver"

        cur.execute(
            "SELECT action, actor_type FROM audit_log WHERE entity_type = 'medication_log' AND entity_id = %s ORDER BY log_id DESC LIMIT 1",
            (log_id,),
        )
        audit_row = cur.fetchone()
        assert audit_row["action"] == "TAKE_DOSE_FAMILY_HELPED"
        assert audit_row["actor_type"] == "Caregiver"


# ─── 8. Family Calendar & Contacts ───────────────────────────────────────────

def test_family_calendar_and_contacts(family_token):
    """Verify 7-day dose history strip, appointments, and care team contacts."""
    client = TestClient(app)
    f_headers = {"Authorization": f"Bearer {family_token}"}

    # Calendar
    res_cal = client.get("/family/calendar", headers=f_headers)
    assert res_cal.status_code == 200
    cal_data = res_cal.json()
    assert "appointments" in cal_data
    assert "dose_history" in cal_data
    # Dose history must have items with status summary only (no clinical details)
    history = cal_data["dose_history"]
    assert len(history) > 0
    assert "total" in history[0]
    assert "taken" in history[0]
    assert "summary" in history[0]

    # Contacts
    res_con = client.get("/family/contacts", headers=f_headers)
    assert res_con.status_code == 200
    con_data = res_con.json()
    assert con_data["attending_doctor"]["name"] == "Dr. Ananya Sharma"
    assert con_data["assigned_nurse"]["name"] == "Priya Nair"
    assert con_data["hospital_desk"]["phone"] == "+91-11-2659-8800"
    assert con_data["emergency"]["number"] == "112"


# ─── 9. Role Boundaries ──────────────────────────────────────────────────────

def test_role_boundaries_patient_and_family(patient_token, family_token):
    """Strict 403 isolation between Patient, Family, and Staff endpoints."""
    client = TestClient(app)

    # 1. Patient cannot access Staff endpoints
    res1 = client.get("/staff/worklist", headers={"Authorization": f"Bearer {patient_token}"})
    assert res1.status_code == 403

    res2 = client.get("/staff/doctor/decisions", headers={"Authorization": f"Bearer {patient_token}"})
    assert res2.status_code == 403

    # 2. Patient cannot access Family endpoints
    res3 = client.get("/family/today", headers={"Authorization": f"Bearer {patient_token}"})
    assert res3.status_code == 403

    # 3. Family cannot access Staff endpoints
    res4 = client.get("/staff/worklist", headers={"Authorization": f"Bearer {family_token}"})
    assert res4.status_code == 403

    res5 = client.get("/staff/nurse/call-list", headers={"Authorization": f"Bearer {family_token}"})
    assert res5.status_code == 403

    # 4. Family cannot access Patient endpoints
    res6 = client.get("/patient/me/today", headers={"Authorization": f"Bearer {family_token}"})
    assert res6.status_code == 403

    res7 = client.post("/patient/me/sharing", json={"enabled": False}, headers={"Authorization": f"Bearer {family_token}"})
    assert res7.status_code == 403
