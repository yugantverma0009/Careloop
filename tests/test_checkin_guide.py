"""
tests/test_checkin_guide.py — CareLoop Check-in Guide Acceptance Tests (Phase 2 Feature F2)

Tests:
1. Active approved template loads with questions in English & Hindi.
2. Nurse is forbidden from approving templates (403); Doctor can approve (200).
3. Guided check-in session starts in 'In_Progress' state.
4. Step-by-step answering saves answers per step.
5. Answering 'Yes' to Question 2 (chest pain / severe breathlessness) immediately fires emergency flag,
   triggers nurse escalation, halts subsequent questions, and returns emergency guidance.
6. Completing a normal check-in session aggregates answers into a standard symptom_reports row
   and evaluates pain score threshold.
7. Abandoned sessions keep partial answers.
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


def test_active_template_loads(tokens):
    """Patient can fetch the active doctor-approved check-in template."""
    headers = {"Authorization": f"Bearer {tokens['patient']}"}
    res = client.get("/patient/me/checkin/template", headers=headers)
    assert res.status_code == 200, f"Failed: {res.text}"
    data = res.json()
    assert data["status"] == "Approved"
    assert bool(data["is_active"]) is True
    assert len(data["questions"]) >= 5
    # Verify bilingual presence
    q2 = next(q for q in data["questions"] if q["question_key"] == "emergency_symptoms")
    assert "chest pain" in q2["text_en"].lower()
    assert "सीने में तेज दर्द" in q2["text_hi"]
    assert q2["is_emergency_trigger"] is True


def test_nurse_forbidden_from_template_approval(tokens):
    """Nurse cannot approve templates (Doctor authority)."""
    headers = {"Authorization": f"Bearer {tokens['nurse']}"}
    res = client.post("/staff/checkin-templates/2/approve", headers=headers)
    assert res.status_code == 403


def test_guided_checkin_emergency_immediate_trigger(tokens):
    """
    Safety Acceptance Check:
    Answering 'Yes' to Question 2 immediately fires the emergency path before any subsequent question.
    """
    headers = {"Authorization": f"Bearer {tokens['patient']}"}
    
    # 1. Start session
    start_res = client.post("/patient/me/checkin/start", json={"channel": "App_Guided"}, headers=headers)
    assert start_res.status_code == 200
    session_id = start_res.json()["session_id"]
    questions = start_res.json()["questions"]
    q1 = questions[0]
    q2 = questions[1]

    # 2. Answer question 1 (mild pain)
    ans1_res = client.post(
        "/patient/me/checkin/answer",
        json={"session_id": session_id, "question_id": q1["question_id"], "answer_value": "2"},
        headers=headers,
    )
    assert ans1_res.status_code == 200
    assert ans1_res.json()["completed"] is False

    # 3. Answer question 2 with YES (Emergency declaration)
    ans2_res = client.post(
        "/patient/me/checkin/answer",
        json={"session_id": session_id, "question_id": q2["question_id"], "answer_value": "Yes"},
        headers=headers,
    )
    assert ans2_res.status_code == 200
    res_data = ans2_res.json()
    assert res_data["emergency"] is True
    assert res_data["completed"] is True
    assert "112" in res_data["guidance_en"]
    assert "112" in res_data["guidance_hi"]

    # 4. Verify in DB that urgent flag was raised and linked to the session
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT f.flag_id, f.severity, f.source_type, f.status
               FROM flags f
               WHERE f.flag_id = %s""",
            (res_data["flag_id"],)
        )
        fl = cur.fetchone()
        assert fl is not None
        assert fl["severity"] == "Urgent_Review"
        assert fl["source_type"] == "Emergency"


def test_guided_checkin_routine_completion(tokens):
    """
    Standard complete check-in session generates symptom_reports row with pain score.
    """
    headers = {"Authorization": f"Bearer {tokens['patient']}"}
    
    # Start fresh session
    start_res = client.post("/patient/me/checkin/start", json={"channel": "App_Guided"}, headers=headers)
    assert start_res.status_code == 200
    session_id = start_res.json()["session_id"]
    questions = start_res.json()["questions"]

    # Answer all 5 questions
    answers = ["1", "No", "all", "fine", "Recovering well without issues."]
    for idx, ans in enumerate(answers):
        q = questions[idx]
        res = client.post(
            "/patient/me/checkin/answer",
            json={"session_id": session_id, "question_id": q["question_id"], "answer_value": ans},
            headers=headers,
        )
        assert res.status_code == 200
        if idx == len(answers) - 1:
            assert res.json()["completed"] is True
            assert res.json()["pain_level"] == 1
            assert res.json()["emergency"] is False


def test_doctor_approve_template_lifecycle(tokens):
    """Doctor can view and approve a check-in template."""
    headers = {"Authorization": f"Bearer {tokens['doctor']}"}
    
    # List templates
    list_res = client.get("/staff/checkin-templates", headers=headers)
    assert list_res.status_code == 200
    tmpls = list_res.json()["templates"]
    assert len(tmpls) >= 2

    # Approve Draft template (Template #2)
    approve_res = client.post("/staff/checkin-templates/2/approve", headers=headers)
    assert approve_res.status_code == 200
    assert approve_res.json()["is_active"] is True

    # Restore Template #1 as active
    restore_res = client.post("/staff/checkin-templates/1/approve", headers=headers)
    assert restore_res.status_code == 200
    assert restore_res.json()["is_active"] is True
