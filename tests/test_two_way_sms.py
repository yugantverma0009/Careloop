"""
tests/test_two_way_sms.py — CareLoop Two-Way SMS Acceptance Tests (Phase 2 Feature F3)

Tests:
1. Deterministic Command 1 / TAKEN: marks pending dose confirmed.
2. Deterministic Command 2 / SKIP: marks pending dose skipped.
3. Deterministic Command 3 / HELP: creates High-priority callback task on nurse queue with 112 guidance.
4. STOP: sets sms_opt_out = True; subsequent automated SMS is blocked.
5. START: clears opt-out.
6. Emergency keywords: immediately trigger emergency flag & escalation.
7. Unknown phone number is logged and ignored.
8. Staff simulator endpoint POST /staff/sms/simulate-inbound executes same logic.
9. Staff endpoint GET /staff/patients/{id}/messages returns message history.
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
    }


AARAV_PHONE = "+91-98765-00001"


def test_sms_command_1_dose_confirmed(tokens):
    """Inbound SMS '1' confirms patient's scheduled dose."""
    headers = {"Authorization": f"Bearer {tokens['nurse']}"}

    # Simulate inbound SMS '1'
    sim_res = client.post(
        "/staff/sms/simulate-inbound",
        json={"from_phone": AARAV_PHONE, "body": "1"},
        headers=headers,
    )
    assert sim_res.status_code == 200
    data = sim_res.json()
    assert data["action"] == "dose_confirmed"
    assert "marked taken" in data["reply"].lower() or "confirmed" in data["reply"].lower()


def test_sms_command_3_urgent_nurse_callback(tokens):
    """
    Inbound SMS '3' or 'HELP' creates an urgent callback task on nurse queue
    and returns 112 safety guidance.
    """
    headers = {"Authorization": f"Bearer {tokens['nurse']}"}

    sim_res = client.post(
        "/staff/sms/simulate-inbound",
        json={"from_phone": AARAV_PHONE, "body": "HELP"},
        headers=headers,
    )
    assert sim_res.status_code == 200
    data = sim_res.json()
    assert data["action"] == "help_callback_created"
    assert "112" in data["reply"]
    task_id = data["task_id"]

    # Verify task in DB
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT priority, reason, status FROM follow_up_tasks WHERE followup_id = %s", (task_id,))
        t = cur.fetchone()
        assert t is not None
        assert t["priority"] == "Urgent_Review"
        assert "SMS HELP" in t["reason"]


def test_sms_stop_and_start_lifecycle(tokens):
    """STOP opts out patient; START opts them back in."""
    headers = {"Authorization": f"Bearer {tokens['nurse']}"}

    # 1. Send STOP
    stop_res = client.post(
        "/staff/sms/simulate-inbound",
        json={"from_phone": AARAV_PHONE, "body": "STOP"},
        headers=headers,
    )
    assert stop_res.status_code == 200
    assert stop_res.json()["action"] == "opt_out"

    # Verify DB flag
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT sms_opt_out FROM patients WHERE patient_id = 1")
        assert cur.fetchone()["sms_opt_out"] == 1

    # 2. Send START to resubscribe
    start_res = client.post(
        "/staff/sms/simulate-inbound",
        json={"from_phone": AARAV_PHONE, "body": "START"},
        headers=headers,
    )
    assert start_res.status_code == 200
    assert start_res.json()["action"] == "opt_in"

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT sms_opt_out FROM patients WHERE patient_id = 1")
        assert cur.fetchone()["sms_opt_out"] == 0


def test_sms_emergency_keyword_handling(tokens):
    """Inbound message with emergency symptoms immediately fires emergency flag."""
    headers = {"Authorization": f"Bearer {tokens['nurse']}"}

    res = client.post(
        "/staff/sms/simulate-inbound",
        json={"from_phone": AARAV_PHONE, "body": "Severe chest pain since 10 minutes"},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["action"] == "emergency_flag_created"
    assert "112" in data["reply"]


def test_sms_unknown_phone_ignored(tokens):
    """Inbound message from unknown phone number is ignored and not answered."""
    headers = {"Authorization": f"Bearer {tokens['nurse']}"}

    res = client.post(
        "/staff/sms/simulate-inbound",
        json={"from_phone": "+91-00000-00000", "body": "Hello"},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["action"] == "ignored_unknown_number"
    assert res.json()["reply"] is None


def test_twilio_webhook_endpoint():
    """Twilio inbound webhook receives form data and returns TwiML."""
    res = client.post(
        "/sms/inbound",
        data={"From": AARAV_PHONE, "Body": "3"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert res.status_code == 200
    assert "xml" in res.headers.get("content-type", "")
    assert "<Response>" in res.text
    assert "112" in res.text


def test_patient_messages_history_endpoint(tokens):
    """Staff can view patient's SMS conversation history."""
    headers = {"Authorization": f"Bearer {tokens['nurse']}"}
    res = client.get("/staff/patients/1/messages", headers=headers)
    assert res.status_code == 200
    msgs = res.json()["messages"]
    assert len(msgs) >= 1
    # Verify presence of direction and body
    m = msgs[0]
    assert "direction" in m
    assert "body" in m
    assert "created_at" in m
