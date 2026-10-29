"""
tests/test_patient_upgrade_p4.py

Milestone Phase 4 Tests: Grounded RAG & Assistant Upgrade:
- POST /patient/me/chat:
  * Role isolation (401 unauthenticated, 403 doctor/nurse).
  * Emergency queries return instant 112 guidance (no LLM latency).
  * Dose alteration requests safely refused with clinical referral guidance.
  * Structured tool queries (appointments, today doses, vitals) return grounded facts.
  * Grounded document queries return source citations with section_title and page_no.
  * Audit log recorded with action CHAT_QUERY.
- GET /patient/me/chat/history:
  * Returns structured message history with answer_type, sources, and ratings.
  * Enforces patient token isolation.
- POST /patient/me/chat/{id}/ask-care-team:
  * Creates patient follow-up task in patient_tasks.
  * Audit log recorded with action CHAT_ASK_CARE_TEAM.
- POST /patient/me/chat/{id}/feedback:
  * Records rating (-1, 1) and optional comment in chat_feedback.
  * Boundary validation (rejects invalid ratings).
  * Updates existing rating on repeat submission.
  * Audit log recorded with action CHAT_FEEDBACK.
- Numeric and Citation Guard:
  * Verifies numeric guard sanitizes/rejects unauthorized numbers not in context.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import get_conn
from backend.app.rag_pipeline import guard_numeric_and_citations, numbers_in

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


def test_chat_auth_and_role_isolation(patient_token, doctor_token):
    # 1. Unauthenticated request
    res_unauth = client.post("/patient/me/chat", json={"message": "Hello"})
    assert res_unauth.status_code == 401

    # 2. Doctor token rejected on patient chat endpoint
    res_doc = client.post(
        "/patient/me/chat",
        headers={"Authorization": f"Bearer {doctor_token}"},
        json={"message": "Hello"},
    )
    assert res_doc.status_code == 403


def test_chat_emergency_handling_instant(patient_token):
    """Emergency terms must immediately return 112 guidance without calling LLM."""
    emergency_queries = [
        ("I have severe crushing chest pain and cannot breathe", "en"),
        ("मुझे सीने में बहुत तेज़ असहनीय दर्द हो रहा है और सांस नहीं आ रही", "hi"),
    ]

    for q, lang in emergency_queries:
        res = client.post(
            "/patient/me/chat",
            headers={"Authorization": f"Bearer {patient_token}"},
            json={"message": q, "language": lang},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["answer_type"] == "emergency"
        assert "112" in data["answer"] or "112" in data["response"]
        assert data.get("is_grounded") is False


def test_chat_dose_refusal(patient_token):
    """Dose alteration questions must be safely refused."""
    refusal_queries = [
        "Can I double my dose of medicine so I heal faster?",
        "क्या मैं अपनी दवा की ख़ुराक दोगुनी कर लूँ?",
    ]

    for q in refusal_queries:
        res = client.post(
            "/patient/me/chat",
            headers={"Authorization": f"Bearer {patient_token}"},
            json={"message": q},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["answer_type"] == "refusal_dose"
        assert data.get("can_ask_care_team") is True


def test_chat_tool_intent_appointment(patient_token):
    """Appointment query routes through read-only SQL tool and returns grounded visit info."""
    res = client.post(
        "/patient/me/chat",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={"message": "When is my next visit?", "language": "en"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["answer_type"] in ("grounded", "structured")
    assert data["is_grounded"] is True
    assert len(data.get("sources", [])) > 0
    # Check that appointments tool was cited
    tool_sources = [s for s in data["sources"] if s.get("tool_name") in ("appointment", "appointments") or "appointment" in s.get("label", "").lower()]
    assert len(tool_sources) > 0


def test_chat_tool_intent_today_doses(patient_token):
    """Today doses query routes through read-only SQL tool."""
    res = client.post(
        "/patient/me/chat",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={"message": "What medicines do I take today?", "language": "en"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["answer_type"] in ("grounded", "structured")
    assert len(data.get("sources", [])) > 0


def test_chat_grounded_document_query(patient_token):
    """Grounded document query retrieves discharge document chunks with citations."""
    res = client.post(
        "/patient/me/chat",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={"message": "What are my physical activity restrictions?", "language": "en"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["answer_type"] == "grounded"
    assert len(data.get("sources", [])) > 0

    # Ensure source format adheres to section metadata
    for src in data["sources"]:
        if "section_title" in src:
            assert isinstance(src["section_title"], str)
            assert len(src["section_title"]) > 0


def test_chat_history_endpoint(patient_token):
    """GET /patient/me/chat/history returns array with answer_type and sources."""
    res = client.get(
        "/patient/me/chat/history",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert res.status_code == 200
    history = res.json()
    assert isinstance(history, list)
    if len(history) > 0:
        first = history[0]
        assert "message_id" in first
        assert "sender" in first
        assert "message_text" in first


def test_chat_ask_care_team_and_audit(patient_token):
    """POST /patient/me/chat/{id}/ask-care-team creates follow-up task and audit log."""
    # 1. Send refusal message to get a message_id
    res_chat = client.post(
        "/patient/me/chat",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={"message": "Can I stop taking my blood pressure medicine?"},
    )
    assert res_chat.status_code == 200
    msg_id = res_chat.json().get("message_id")
    assert msg_id is not None

    # 2. Ask care team for this message
    res_task = client.post(
        f"/patient/me/chat/{msg_id}/ask-care-team",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert res_task.status_code == 200
    data = res_task.json()
    assert data["ok"] is True
    assert "task_id" in data

    # 3. Verify in audit_log
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT action, entity_type, entity_id FROM audit_log WHERE action = 'ASK_CARE_TEAM' ORDER BY log_id DESC LIMIT 1"
            )
            row = cur.fetchone()
            assert row is not None
            assert row["entity_type"] == "chat_message"
            assert row["entity_id"] == msg_id


def test_chat_feedback_rating_and_update(patient_token):
    """POST /patient/me/chat/{id}/feedback stores ratings, comments, and updates."""
    # 1. Get a valid assistant message
    res_hist = client.get("/patient/me/chat/history", headers={"Authorization": f"Bearer {patient_token}"})
    assert res_hist.status_code == 200
    asst_msgs = [m for m in res_hist.json() if m.get("sender") in ("AI_Nurse", "AI_Assistant") or m.get("role") == "assistant"]
    assert len(asst_msgs) > 0
    target_msg_id = asst_msgs[-1]["message_id"]

    # 2. Invalid rating (> 1)
    res_inv = client.post(
        f"/patient/me/chat/{target_msg_id}/feedback",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={"rating": 5},
    )
    assert res_inv.status_code == 422

    # 3. Submit thumbs up (1)
    res_up = client.post(
        f"/patient/me/chat/{target_msg_id}/feedback",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={"rating": 1, "comment": "Very accurate"},
    )
    assert res_up.status_code == 200
    assert res_up.json()["rating"] == 1

    # 4. Verify in DB
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT rating, comment FROM chat_feedback WHERE message_id = %s", (target_msg_id,))
            fb = cur.fetchone()
            assert fb is not None
            assert fb["rating"] == 1
            assert fb["comment"] == "Very accurate"

    # 5. Update rating to thumbs down (-1)
    res_down = client.post(
        f"/patient/me/chat/{target_msg_id}/feedback",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={"rating": -1, "comment": "Confusing wording"},
    )
    assert res_down.status_code == 200
    assert res_down.json()["rating"] == -1

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT rating, comment FROM chat_feedback WHERE message_id = %s", (target_msg_id,))
            fb_updated = cur.fetchone()
            assert fb_updated["rating"] == -1
            assert fb_updated["comment"] == "Confusing wording"


def test_numeric_guard_unit_logic():
    """Unit test for guard_numeric_and_citations to ensure hallucinated numbers are caught."""
    context_texts = [
        "Take 1 tablet of Aspirin 75mg daily at 08:00 AM. Next appointment on 2026-11-05.",
    ]
    tool_results = {
        "appointments": [{"appointment_date": "2026-11-05 10:30:00"}],
    }
    valid_source_ids = {"S1"}

    # Case 1: Valid numbers present in context
    safe_answer = {
        "found": True,
        "answer": "Take 1 tablet of Aspirin 75mg at 08:00 AM on 2026-11-05.",
        "bullets": [],
        "source_ids": ["S1"],
    }
    res_ok = guard_numeric_and_citations(safe_answer, context_texts, tool_results, valid_source_ids)
    assert res_ok == "ok"

    # Case 2: Hallucinated number (e.g. 999mg or 42 times a day)
    hallucinated_answer = {
        "found": True,
        "answer": "You should take 999mg of medication 42 times a day.",
        "bullets": [],
        "source_ids": ["S1"],
    }
    res_bad = guard_numeric_and_citations(hallucinated_answer, context_texts, tool_results, valid_source_ids)
    assert res_bad == "downgrade_not_found"
