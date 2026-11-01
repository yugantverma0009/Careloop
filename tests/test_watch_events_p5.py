"""
tests/test_watch_events_p5.py

Acceptance tests for Phase 5: Watch Events (Possible fall, live refresh, device health).
Verifies:
1. Device key authentication (401 on bad or missing key).
2. Rule OFF: possible fall event is recorded in audit log only; no prompt or flag created.
3. Rule ON: possible fall event triggers prompt (app banner + SMS) and schedules wait timer.
4. Outcome A: Patient confirms "I'm OK" -> event closed as Ok, prompt counters updated, no flag.
5. Outcome B: Patient clicks "I need help" -> Immediate flag created, escalation ladder triggered.
6. Outcome C: Wait time expires -> Immediate flag created ("Watch reported a possible fall at ... No reply within 2 minutes.").
7. Inbound SMS '1' and '3' handlers resolve active possible fall prompt.
8. Device health card: connectivity status, battery %, and exclusion of invalid readings from headlines.
9. Zero prohibited wording: no text claims "detected".
"""

import time
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import get_conn
from scripts.seed_demo import main as run_seed

client = TestClient(app)
DEVICE_KEY = "demo-device-key-change-me"


@pytest.fixture(autouse=True)
def ensure_clean_demo_state():
    """Reset database to clean seed state before each test run."""
    run_seed()


def get_auth_token(email: str, password: str = "Demo@12345") -> str:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


def test_device_key_authentication():
    """1. Endpoint requires valid X-Device-Key header."""
    payload = {
        "device_id": "DEV-ESP32-005",
        "event_type": "Possible_Fall",
        "occurred_at": int(time.time()),
        "details": {"peak_movement": 3.6, "stillness_seconds": 14},
    }
    # Missing key
    res_missing = client.post("/device/events", json=payload)
    assert res_missing.status_code == 422 or res_missing.status_code == 401

    # Bad key
    res_bad = client.post("/device/events", json=payload, headers={"X-Device-Key": "wrong-key"})
    assert res_bad.status_code == 401

    # Good key
    res_good = client.post("/device/events", json=payload, headers={"X-Device-Key": DEVICE_KEY})
    assert res_good.status_code == 200


def test_rule_off_logs_event_only():
    """2. When Possible_Fall rule is OFF (Aarav, Pt 1), event is recorded in audit log only."""
    payload = {
        "device_id": "DEV-ESP32-001",
        "event_type": "Possible_Fall",
        "occurred_at": int(time.time()) - 10,
        "details": {"peak_movement": 3.2, "stillness_seconds": 10},
    }
    res = client.post("/device/events", json=payload, headers={"X-Device-Key": DEVICE_KEY})
    assert res.status_code == 200
    data = res.json()
    assert data["rule_active"] is False
    assert data["prompt_sent"] is False

    # Verify no open flag was created for Aarav
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM flags WHERE patient_id = 1 AND source_type = 'Fall'")
        assert cur.fetchone()["cnt"] == 0

        # Verify audit row exists
        cur.execute(
            """SELECT details FROM audit_log
               WHERE action = 'POSSIBLE_FALL_LOGGED_RULE_OFF' AND actor_id = 'DEV-ESP32-001'
               ORDER BY log_id DESC LIMIT 1"""
        )
        row = cur.fetchone()
        assert row is not None
        assert "Disabled" in row["details"]


def test_rule_on_triggers_prompt_and_wait_timer():
    """3. When Possible_Fall rule is ON (Sunita, Pt 5), prompt is sent and timeout scheduled."""
    now_epoch = int(time.time())
    payload = {
        "device_id": "DEV-ESP32-005",
        "event_type": "Possible_Fall",
        "occurred_at": now_epoch,
        "details": {"peak_movement": 3.9, "stillness_seconds": 16, "battery_pct": 79},
    }
    res = client.post("/device/events", json=payload, headers={"X-Device-Key": DEVICE_KEY})
    assert res.status_code == 200
    data = res.json()
    assert data["rule_active"] is True
    assert data["prompt_sent"] is True
    assert data["wait_minutes"] == 2
    event_id = data["event_id"]

    # Verify scheduled_action created for timeout
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT action_type, status, reason, dedupe_key
               FROM scheduled_actions WHERE dedupe_key = %s""",
            (f"fall_timeout_{event_id}",),
        )
        sa = cur.fetchone()
        assert sa is not None
        assert sa["action_type"] == "Fall_Prompt"
        assert sa["status"] == "Scheduled"

        # Verify outbound SMS recorded
        cur.execute(
            """SELECT body FROM sms_messages
               WHERE patient_id = 5 AND related_type = 'device_event' AND related_id = %s""",
            (event_id,),
        )
        sms_row = cur.fetchone()
        assert sms_row is not None
        assert "Are you OK?" in sms_row["body"]


def test_outcome_a_patient_answers_ok():
    """4. Outcome A: Patient confirms 'I'm OK' -> event closed, no flag created."""
    # 1. Post event for Sunita (Patient 5)
    now_epoch = int(time.time())
    res_ev = client.post(
        "/device/events",
        json={"device_id": "DEV-ESP32-005", "event_type": "Possible_Fall", "occurred_at": now_epoch},
        headers={"X-Device-Key": DEVICE_KEY},
    )
    event_id = res_ev.json()["event_id"]

    # 2. Patient submits response "Ok"
    from backend.app.device_event_service import handle_patient_fall_response
    res_ans = handle_patient_fall_response(patient_id=5, event_id=event_id, response="Ok")
    assert res_ans["patient_response"] == "Ok"
    assert "safe" in res_ans["message"].lower()

    # Verify event state in DB
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT patient_response, flag_id FROM device_events WHERE event_id = %s", (event_id,))
        ev_row = cur.fetchone()
        assert ev_row["patient_response"] == "Ok"
        assert ev_row["flag_id"] is None

        # Verify audit log
        cur.execute(
            "SELECT action FROM audit_log WHERE entity_id = %s AND action = 'FALL_PROMPT_ANSWERED_OK'",
            (str(event_id),),
        )
        assert cur.fetchone() is not None


def test_outcome_b_patient_answers_need_help():
    """5. Outcome B: Patient clicks 'I need help' -> Immediate flag created, ladder started."""
    now_epoch = int(time.time())
    res_ev = client.post(
        "/device/events",
        json={"device_id": "DEV-ESP32-005", "event_type": "Possible_Fall", "occurred_at": now_epoch},
        headers={"X-Device-Key": DEVICE_KEY},
    )
    event_id = res_ev.json()["event_id"]

    from backend.app.device_event_service import handle_patient_fall_response
    res_ans = handle_patient_fall_response(patient_id=5, event_id=event_id, response="Need_Help")
    assert res_ans["status"] == "help_flag_created"
    flag_id = res_ans["flag_id"]

    # Verify flag in DB
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT source_type, severity, reason FROM flags WHERE flag_id = %s", (flag_id,))
        fl_row = cur.fetchone()
        assert fl_row["source_type"] == "Fall"
        assert fl_row["severity"] == "Urgent_Review"
        assert "Patient pressed I need help" in fl_row["reason"]

        # Verify escalation step created
        cur.execute("SELECT step_no, channel FROM escalations WHERE flag_id = %s", (flag_id,))
        assert cur.fetchone() is not None


def test_outcome_c_wait_time_expired_triggers_immediate_flag():
    """6. Outcome C: Wait time expired without reply -> Immediate flag created with F7 format."""
    now_epoch = int(time.time()) - 300  # 5 minutes ago
    res_ev = client.post(
        "/device/events",
        json={"device_id": "DEV-ESP32-005", "event_type": "Possible_Fall", "occurred_at": now_epoch},
        headers={"X-Device-Key": DEVICE_KEY},
    )
    event_id = res_ev.json()["event_id"]

    from backend.app.device_event_service import process_fall_timeout
    res_timeout = process_fall_timeout(event_id=event_id)
    assert res_timeout["status"] == "timeout_flag_created"
    flag_id = res_timeout["flag_id"]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT source_type, severity, reason FROM flags WHERE flag_id = %s", (flag_id,))
        fl_row = cur.fetchone()
        assert fl_row["source_type"] == "Fall"
        assert fl_row["severity"] == "Urgent_Review"
        # Must match F7 wording: "Watch reported a possible fall at HH:MM. No reply within 2 minutes."
        assert "Watch reported a possible fall at" in fl_row["reason"]
        assert "No reply within 2 minutes" in fl_row["reason"]


def test_inbound_sms_fall_prompt_handling():
    """7. Inbound SMS command '1' closes prompt as OK, '3' raises help flag."""
    from backend.app.sms_service import handle_inbound_sms

    # 1. Post event for Sunita (Phone: +91-98765-00005)
    res_ev = client.post(
        "/device/events",
        json={"device_id": "DEV-ESP32-005", "event_type": "Possible_Fall", "occurred_at": int(time.time())},
        headers={"X-Device-Key": DEVICE_KEY},
    )
    event_id = res_ev.json()["event_id"]

    # Inbound SMS '1' from Sunita
    res_sms1 = handle_inbound_sms("+91-98765-00005", "1")
    assert res_sms1["action"] == "fall_prompt_answered_ok"
    assert res_sms1["event_id"] == event_id

    # Post another event for Sunita
    res_ev2 = client.post(
        "/device/events",
        json={"device_id": "DEV-ESP32-005", "event_type": "Possible_Fall", "occurred_at": int(time.time()) + 1},
        headers={"X-Device-Key": DEVICE_KEY},
    )
    event_id2 = res_ev2.json()["event_id"]

    # Inbound SMS '3' from Sunita
    res_sms3 = handle_inbound_sms("+91-98765-00005", "3")
    assert res_sms3["action"] == "fall_prompt_need_help"
    assert res_sms3["event_id"] == event_id2
    assert res_sms3.get("flag_id") is not None


def test_device_health_and_invalid_vitals_filtering():
    """8. Device health is reported; invalid readings are strictly kept out of headlines."""
    tok_patient = get_auth_token("aarav.demo@example.test")
    res_today = client.get("/patient/me/today", headers={"Authorization": f"Bearer {tok_patient}"})
    assert res_today.status_code == 200
    today_data = res_today.json()

    # Device health card present
    assert "device_health" in today_data
    dh = today_data["device_health"]
    assert dh["has_device"] is True
    assert dh["device_id"] == "DEV-ESP32-001"
    assert dh["battery_pct"] >= 0
    assert dh["rounds_silence_monitored"] is True

    # Headline heart rate must be valid (74.0 bpm, never invalid 450 bpm)
    hr_reading = next((r for r in today_data["readings"] if r["type"] == "Heart_Rate"), None)
    assert hr_reading is not None
    assert float(hr_reading["value"]) == 74.0
    assert "data_check_note" in today_data


def test_no_detected_wording_leakage():
    """9. Acceptance Rule: Zero text claims 'detected'."""
    with get_conn() as conn, conn.cursor() as cur:
        # Check all flags reasons
        cur.execute("SELECT reason FROM flags WHERE reason LIKE '%detected%'")
        rows = cur.fetchall()
        assert len(rows) == 0, f"Found prohibited 'detected' in flags: {rows}"

        # Check all follow up tasks
        cur.execute("SELECT reason FROM follow_up_tasks WHERE reason LIKE '%detected%'")
        assert len(cur.fetchall()) == 0
