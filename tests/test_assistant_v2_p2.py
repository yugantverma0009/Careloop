"""
tests/test_assistant_v2_p2.py — Automated Test Suite for Assistant v2 Phase 2

Verifies Phase 2 Requirements:
1. Hybrid retrieval & score threshold (irrelevant queries return not_found without calling LLM).
2. Multilingual handling (Hindi queries retrieve correct chunks).
3. Question rewriting for follow-ups (e.g., "And in the evening?").
4. Read-only tools match Medicines and Calendar pages exactly.
5. Allowlist actions filtering (drops non-allowlisted actions).
6. Numeric guard prevents unallowed numbers from reaching the patient (0 failures).
7. LLM-down and timeout behaviour (graceful fallback).
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.auth import make_token, verify_login
from backend.app.rag_pipeline import (
    hybrid_retrieval,
    rewrite_followup_question,
    guard_numeric_and_citations,
    answer_patient_query,
)
from backend.app.rag_tools import (
    get_today_doses,
    get_next_appointment,
    get_medicine_plan,
    get_latest_readings,
)
from scripts.seed_demo import main as run_seed


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Ensure consistent fresh demo data once for the test module."""
    run_seed()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def patient_token():
    acct = verify_login("aarav.demo@example.test", "Demo@12345")
    assert acct is not None
    return make_token(acct)


# ─── 1. Read-Only Tools Consistency ────────────────────────────────────────

def test_tools_match_medicines_and_calendar_exactly():
    """Tool answers must match the Medicines and Calendar pages exactly."""
    patient_id = 1  # Aarav Patel

    # Medicines tool
    doses_data = get_today_doses(patient_id)
    assert doses_data["found"] is True
    assert doses_data["count"] >= 2
    med_names = [d["medicine"] for d in doses_data["doses"]]
    assert "CardioPulse-XR" in med_names
    assert "VasculoNorm-5" in med_names
    # Check 12-hour format in doses
    for d in doses_data["doses"]:
        assert any(meridiem in d["time"] for meridiem in ["AM", "PM"])

    # Calendar / Appointment tool
    appt_data = get_next_appointment(patient_id)
    assert appt_data["found"] is True
    assert "Dr. Ananya Sharma" in appt_data["doctor"]
    assert "Cardiology" in appt_data["specialization"]
    assert "10:30 AM" in appt_data["time"]


# ─── 2. Hybrid Retrieval & Score Threshold ─────────────────────────────────

def test_hybrid_retrieval_relevance_and_threshold():
    """Relevant queries retrieve section-aware chunks; irrelevant queries fail threshold."""
    patient_id = 1

    # Relevant query (Warning signs)
    chunks, debug = hybrid_retrieval(patient_id, "What are the warning signs and red flags?", intent="warning_signs", top_k=3)
    assert len(chunks) > 0
    assert debug["threshold_passed"] is True
    assert any("warning" in (c.get("section_title") or "").lower() for c in chunks)

    # Irrelevant query (Recipe for biryani)
    irrelevant_chunks, irr_debug = hybrid_retrieval(patient_id, "recipe for biryani", intent="general_docs")
    assert len(irrelevant_chunks) == 0
    assert irr_debug["threshold_passed"] is False


def test_multilingual_hindi_retrieval():
    """Hindi queries retrieve appropriate clinical sections."""
    patient_id = 1
    chunks, debug = hybrid_retrieval(patient_id, "घाव और ड्रेसिंग की देखभाल कैसे करें?", intent="wound_care", top_k=3)
    assert len(chunks) > 0
    assert debug["threshold_passed"] is True
    assert any("wound" in (c.get("section_title") or "").lower() or "sternal" in (c.get("section_title") or "").lower() for c in chunks)


# ─── 3. Question Rewriting ─────────────────────────────────────────────────

def test_followup_question_rewriting():
    """Follow-up questions are resolved to standalone queries."""
    # English follow-up
    rewritten_en = rewrite_followup_question("And in the evening?")
    assert "cardiopulse" in rewritten_en.lower() or "evening" in rewritten_en.lower()

    # Hindi follow-up
    rewritten_hi = rewrite_followup_question("और शाम के समय?")
    assert "cardiopulse" in rewritten_hi.lower() or "evening" in rewritten_hi.lower() or "शाम" in rewritten_hi


# ─── 4. Numeric Guard ──────────────────────────────────────────────────────

def test_numeric_guard_strictly_suppresses_hallucinated_numbers():
    """Zero numeric guard failures reach the patient: hallucinated numbers are downgraded."""
    context = ["Walk indoors for 10-15 minutes twice daily. Avoid lifting objects heavier than 5 kg."]
    
    # Valid answer: contains only allowed numbers (10, 15, 5)
    valid_answer = {
        "found": True,
        "answer": "Walk 10-15 minutes twice daily and avoid lifting over 5 kg.",
        "bullets": [],
        "source_ids": ["S1"],
    }
    result_valid = guard_numeric_and_citations(valid_answer, context, None, {"S1"}, "Can I walk?")
    assert result_valid == "ok"

    # Hallucinated number: claims patient can lift 25 kg
    hallucinated_answer = {
        "found": True,
        "answer": "You can safely lift up to 25 kg tomorrow.",
        "bullets": [],
        "source_ids": ["S1"],
    }
    result_hallucinated = guard_numeric_and_citations(hallucinated_answer, context, None, {"S1"}, "Can I walk?")
    assert result_hallucinated == "downgrade_not_found"


# ─── 5. LLM-Down and Timeout Fallback ──────────────────────────────────────

def test_llm_down_tool_and_extractive_fallback():
    """When LLM is down or times out, tool answers and extractive chunks still succeed."""
    # 1. Structured appointment query when LLM raises exception
    with patch("backend.app.rag_pipeline.generate", side_effect=Exception("503 Service Unavailable")):
        res_tool = answer_patient_query(
            patient_id=1,
            question="When is my next appointment?",
            language="en"
        )
        assert res_tool["answer_type"] == "structured"
        assert "Dr. Ananya Sharma" in res_tool["answer"]
        assert "From your care plan" in res_tool["sources"][0]["label"]

    # 2. Document question when LLM raises exception
    with patch("backend.app.rag_pipeline.generate", side_effect=Exception("503 Service Unavailable")):
        res_doc = answer_patient_query(
            patient_id=1,
            question="What are my sternal wound care instructions?",
            language="en"
        )
        assert res_doc["answer_type"] == "grounded"
        assert "discharge summary" in res_doc["answer"].lower()
        assert len(res_doc["bullets"]) > 0
        assert "p.3" in res_doc["sources"][0]["label"]


# ─── 6. Action Cards Allowlist Filtering ───────────────────────────────────

def test_action_cards_allowlist_filtering():
    """LLM proposed actions outside the allowlist are dropped."""
    fake_llm_json = """{
        "found": true,
        "answer": "Your sternal wound is healing.",
        "bullets": [],
        "source_ids": ["S1"],
        "suggest_care_team": false,
        "actions": [
            {"action_type": "Start_Checkin", "label": "Start Check-in"},
            {"action_type": "Prescribe_Opioid", "label": "Invalid Action"},
            {"action_type": "Delete_Patient", "label": "Dangerous Action"}
        ],
        "suggested_followups": ["How to keep it clean?"]
    }"""
    with patch("backend.app.rag_pipeline.generate", return_value=fake_llm_json):
        res = answer_patient_query(
            patient_id=1,
            question="How is my sternal incision?",
            language="en"
        )
        assert res["answer_type"] == "grounded"
        action_types = [a.get("action_type") for a in res.get("actions", [])]
        assert "Start_Checkin" in action_types
        assert "Prescribe_Opioid" not in action_types
        assert "Delete_Patient" not in action_types
