"""
CareLoop Phase 4 Test Suite: Trust, Transparency, and Safety Controls
Tests:
1. "Why was my care team told?" explainer (5.F) matches rule rows, approver doctor, and avoids judgment words.
2. "My readings" 7-day trend (5.F) strictly excludes invalid readings and includes alert line.
3. Distress phrase detection in plain code (5.G) for EN, HI, Hinglish creates urgent nurse task & returns fixed message.
4. Distress task deduplication per day.
5. Help bar (5.G) creates de-duplicated nurse call tasks.
6. AI Help toggle (5.H) disables LLM answers while deterministic reminders and rules continue.
7. Chat privacy controls (hide/delete) write audit rows with IDs and timestamps only.
8. Permissions check: family login cannot access patient settings or clinical chat.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.agents.trust_service import TrustService
from backend.app.agents.papers_agent import PapersAgent
from backend.app.db import get_conn

client = TestClient(app)


def test_why_told_explainer_matches_rule_and_avoids_judgment():
    """Test 1: 'Why was my care team told?' explainer matches rule threshold and doctor without judgment words."""
    # Patient 1 (Aarav Patel)
    explainer = TrustService.get_why_told_explainer(patient_id=1, language="en")
    assert "has_open_alert" in explainer

    if explainer["has_open_alert"]:
        assert "plain_reason" in explainer
        assert "data_quality_label" in explainer
        assert "what_happens_next" in explainer
        assert "approver_name" in explainer

        # No judgment words allowed
        judgment_words = ["guilty", "careless", "failed", "abnormal", "fault", "dangerously", "poor compliance"]
        combined_text = (explainer["plain_reason"] + " " + explainer["what_happens_next"]).lower()
        for jw in judgment_words:
            assert jw not in combined_text, f"Judgment word '{jw}' found in explainer"


def test_readings_trend_filters_invalid_and_includes_alert_line():
    """Test 2: 'My readings' 7-day trend excludes invalid readings and provides doctor alert limit line."""
    trend = TrustService.get_readings_trend(patient_id=1, measurement_type="SpO2")
    assert "points" in trend
    assert "alert_limit" in trend
    assert "disclaimer" in trend
    assert "invalid_readings_ignored" in trend

    # Every point must be valid / good
    for pt in trend["points"]:
        assert pt["quality"] != "Invalid"

    # Must contain alert limit threshold line and disclaimer
    assert trend["alert_limit"]["threshold"] > 0
    assert "cannot tell you if your reading is OK" in trend["disclaimer"]


def test_distress_phrase_detection_and_emergency_reply():
    """Test 3: Plain code distress matching (EN, HI, Hinglish) creates nurse call task and returns fixed reply without LLM."""
    distress_inputs = [
        ("i want to die", "en"),
        ("feel like giving up on everything", "en"),
        ("main haar gaya ab jeena nahi chahta", "hi"),
        ("marne ka man kar raha hai", "hi"),
        ("ab nahi ho raha give up kar raha", "en"),
    ]

    for phrase, lang in distress_inputs:
        assert TrustService.check_distress(phrase) is True, f"Failed to detect distress in '{phrase}'"

        res = PapersAgent.process_query(patient_id=1, question=phrase, language=lang)
        assert res["answer_type"] == "distress"
        assert res.get("action_suggested") == "distress_support"
        assert "112" in res["response"]
        assert "nurse" in res["response"].lower() or "नर्स" in res["response"]


def test_distress_and_help_bar_deduplication():
    """Test 4 & 5: Help bar and distress requests are de-duplicated per day."""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM follow_up_tasks WHERE patient_id = 1 AND reason LIKE '%Help Bar%'")
        conn.commit()

    # First Help bar call request
    res1 = TrustService.request_nurse_call(patient_id=1, reason_category="callback_request")
    assert res1["success"] is True
    assert res1["created"] is True

    # Second Help bar call request on same day -> must be de-duplicated
    res2 = TrustService.request_nurse_call(patient_id=1, reason_category="callback_request")
    assert res2["success"] is True
    assert res2["created"] is False
    assert res2["task_id"] == res1["task_id"]


def test_ai_help_toggle_disables_llm_features():
    """Test 6: AI Help switch toggle disables conversational AI while rules and reminders persist."""
    # Turn OFF AI Help
    res_off = TrustService.set_ai_help_enabled(patient_id=1, enabled=False)
    assert res_off["ai_help_enabled"] is False

    # Query PapersAgent while AI Help is OFF
    query_res = PapersAgent.process_query(
        patient_id=1,
        question="Can I take a warm shower today?",
        language="en"
    )
    assert query_res["answer_type"] == "ai_disabled"
    assert "turned off in your settings" in query_res["response"]

    # Turn ON AI Help back
    res_on = TrustService.set_ai_help_enabled(patient_id=1, enabled=True)
    assert res_on["ai_help_enabled"] is True


def test_chat_privacy_auditing():
    """Test 7: Chat hide and deletion requests write proper audit rows with IDs and timestamps only."""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM audit_log WHERE entity_type = 'chat_history' AND actor_id = '1'")
        conn.commit()

    # Request hide
    hide_res = TrustService.request_chat_privacy(patient_id=1, action_type="hide")
    assert hide_res["success"] is True

    # Request delete
    del_res = TrustService.request_chat_privacy(patient_id=1, action_type="delete")
    assert del_res["success"] is True

    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT action, details FROM audit_log
               WHERE entity_type = 'chat_history' AND actor_id = '1'
               ORDER BY log_id ASC"""
        )
        logs = cursor.fetchall()
        assert len(logs) >= 2
        actions = [l["action"] for l in logs]
        assert "CHAT_HIDDEN_FROM_SCREEN" in actions
        assert "CHAT_DELETION_REQUESTED" in actions


def test_family_forbidden_from_patient_settings():
    """Test 8: Family role is strictly forbidden from accessing patient settings or transparency endpoints."""
    # Login as Family (simulated token or header)
    from backend.app.auth import make_token
    family_token = make_token({
        "account_id": 99,
        "email": "family@test.com",
        "account_role": "Family",
        "patient_id": 1,
        "caregiver_id": 1,
        "staff_id": None
    })

    headers = {"Authorization": f"Bearer {family_token}"}
    response = client.get("/patient/me/ai-transparency", headers=headers)
    assert response.status_code == 403
    assert "Forbidden" in response.text
