"""
tests/test_phase7_acceptance.py

Phase 7 Final Acceptance Test Suite:
1. LLM-Off Resilience:
   - When LLM provider is unavailable / raises exception, chat falls back gracefully to NOT_FOUND message
   - Dose inquiry refusal still works deterministically
   - Emergency keyword detection (English & Hindi) bypasses LLM and triggers Call 112 immediately
   - AI summary generation falls back to deterministic SBAR fact sheet without judgment words
2. Section 10 Final Checklist Verification:
   - Exactly 4 logins and 4 distinct first screens
   - Nurse forbidden from Approvals, Audit log, and FHIR export
   - Family helper forbidden from clinical chat, symptom free-text, and clinical notes
   - Database reset produces exactly 5 patients, 3 open flags, 5 open tasks
   - Headline valid vitals filters out 450 bpm invalid spike
   - All 4 role pitches present on landing page with required regulatory footer
"""

import os
import sys
import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

# Ensure root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app
from backend.app.db import get_conn

client = TestClient(app)


def get_token(email: str, password: str = "Demo@12345") -> str:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


@pytest.fixture(autouse=True)
def clean_baseline():
    client.post("/demo/reset")
    yield
    client.post("/demo/reset")


# ── 1. LLM-Off Resilience & Graceful Fallback ────────────────────────────────

def test_llm_offline_rag_not_found_fallback():
    """When LLM provider is down or question is out of scope, chat safely returns calm refusal."""
    p_tok = get_token("aarav.demo@example.test")

    with patch("backend.app.rag_pipeline.generate", side_effect=RuntimeError("Simulated LLM Provider Outage")):
        res = client.post(
            "/patient/me/chat",
            headers={"Authorization": f"Bearer {p_tok}"},
            json={"message": "What is the capital of France?", "language": "en"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_grounded"] is False
        assert data["answer_type"] == "not_found"
        assert "discharge papers" in data["response"].lower() or "care plan" in data["response"].lower()


def test_llm_offline_rag_extractive_fallback():
    """When LLM is offline, grounded queries fall back deterministically to extracted sentences from papers."""
    p_tok = get_token("aarav.demo@example.test")

    with patch("backend.app.rag_pipeline.generate", side_effect=RuntimeError("Simulated LLM Provider Outage")):
        res = client.post(
            "/patient/me/chat",
            headers={"Authorization": f"Bearer {p_tok}"},
            json={"message": "What are my discharge activity restrictions?", "language": "en"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_grounded"] is True
        assert "discharge summary" in data["response"].lower() or "care plan" in data["response"].lower()


def test_llm_offline_dose_refusal_still_works():
    """Dose refusal is code-enforced before/during LLM call and refuses dose advice."""
    p_tok = get_token("aarav.demo@example.test")

    with patch("backend.app.rag_pipeline.generate", side_effect=RuntimeError("Simulated LLM Provider Outage")):
        res = client.post(
            "/patient/me/chat",
            headers={"Authorization": f"Bearer {p_tok}"},
            json={"message": "Can I double my dose of Metoprolol?", "language": "en"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_grounded"] is False
        assert "cannot give advice on changing your medicine dose" in data["response"].lower() or "cannot advise" in data["response"].lower()


def test_llm_offline_emergency_bypass_english_and_hindi():
    """Emergency detection is plain deterministic code and never waits for or depends on LLM."""
    p_tok = get_token("aarav.demo@example.test")

    with patch("backend.app.rag_pipeline.generate", side_effect=RuntimeError("Simulated LLM Provider Outage")):
        # English emergency keyword
        res_en = client.post(
            "/patient/me/chat",
            headers={"Authorization": f"Bearer {p_tok}"},
            json={"message": "I have severe chest pain", "language": "en"},
        )
        assert res_en.status_code == 200
        data_en = res_en.json()
        assert "112" in data_en["response"]
        assert "emergency" in data_en["response"].lower()

        # Hindi emergency keyword
        res_hi = client.post(
            "/patient/me/chat",
            headers={"Authorization": f"Bearer {p_tok}"},
            json={"message": "सीने में बहुत तेज दर्द हो रहा है", "language": "hi"},
        )
        assert res_hi.status_code == 200
        data_hi = res_hi.json()
        assert "112" in data_hi["response"]


def test_llm_offline_summary_fallback_sbar():
    """When LLM is offline, summary generation falls back to deterministic SBAR fact sheet."""
    d_tok = get_token("ananya.demo@example.test")

    with patch("backend.app.clinical_summaries.generate", side_effect=RuntimeError("Simulated LLM Outage")):
        res = client.post(
            "/staff/patients/2/summaries/generate?summary_date=2026-10-28",
            headers={"Authorization": f"Bearer {d_tok}"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "summary_id" in data
        assert data["status"] in ("AI draft, not reviewed", "Draft")
        # Ensure fallback contains structured clinical facts without judgment adjectives
        text = str(data["summary_text"]).lower()
        for banned in ["stable", "optimal", "improving", "worsening"]:
            assert banned not in text, f"Banned judgment word '{banned}' leaked into fallback summary"


# ── 2. Section 10 Final Checklist Verification ───────────────────────────────

def test_section10_database_counts():
    """Reset must yield 5 patients, 2 staff, 4 logins, 3 open flags, 5 open tasks, 3 summaries."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM patients")
        assert cur.fetchone()["c"] == 5

        cur.execute("SELECT COUNT(*) AS c FROM care_staff")
        assert cur.fetchone()["c"] == 2

        cur.execute("SELECT COUNT(*) AS c FROM user_accounts")
        assert cur.fetchone()["c"] == 4

        cur.execute("SELECT COUNT(*) AS c FROM flags WHERE status = 'Open'")
        assert cur.fetchone()["c"] == 3

        cur.execute("SELECT COUNT(*) AS c FROM follow_up_tasks WHERE status = 'Pending'")
        assert cur.fetchone()["c"] == 5

        cur.execute("SELECT COUNT(*) AS c FROM ai_summaries")
        assert cur.fetchone()["c"] == 3


def test_section10_role_boundaries_isolation():
    """
    Nurse cannot open Approvals, Audit or Export.
    Family cannot see chat, symptom text or clinical notes.
    """
    n_tok = get_token("priya.demo@example.test")
    f_tok = get_token("caregiver1.demo@example.test")

    # Nurse blocked from doctor-only endpoints
    assert client.get("/staff/doctor/decisions", headers={"Authorization": f"Bearer {n_tok}"}).status_code == 403
    assert client.get("/staff/audit-log", headers={"Authorization": f"Bearer {n_tok}"}).status_code == 403
    assert client.get("/staff/patients/1/fhir", headers={"Authorization": f"Bearer {n_tok}"}).status_code == 403
    assert client.post("/staff/summaries/1/review", headers={"Authorization": f"Bearer {n_tok}"}, json={"action": "Approve"}).status_code == 403

    # Family blocked from clinical endpoints
    assert client.get("/patient/me/today", headers={"Authorization": f"Bearer {f_tok}"}).status_code == 403
    assert client.get("/patient/me/chat/history", headers={"Authorization": f"Bearer {f_tok}"}).status_code == 403
    assert client.get("/staff/nurse/call-list", headers={"Authorization": f"Bearer {f_tok}"}).status_code == 403


def test_section10_headline_vital_quality_filtering():
    """Aarav's headline heart rate must be 74 bpm, filtering out 450 bpm invalid spike."""
    p_tok = get_token("aarav.demo@example.test")
    res = client.get("/patient/me/today", headers={"Authorization": f"Bearer {p_tok}"}).json()
    hr_reading = next((r for r in res.get("readings", []) if r.get("type") == "Heart_Rate"), None)
    assert hr_reading is not None, "Heart_Rate reading not found in readings"
    assert hr_reading["value"] == 74.0, f"Expected 74.0 bpm headline, got {hr_reading['value']}"
    assert hr_reading["quality"] == "Good"
    assert res.get("data_check_note") == "1 reading ignored: impossible value"


def test_section10_landing_page_contract():
    """Landing page must contain four role pitches, real counts, and regulatory notice."""
    landing_path = os.path.abspath("frontend/src/components/Landingpage.jsx")
    with open(landing_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "The doctor decides, approves and exports." in content
    assert "The nurse calls, logs, rechecks and escalates." in content
    assert "The patient acts, checks in and asks their papers." in content
    assert "The family helper supports, is informed with consent, and calls 112 if needed." in content
    assert "The LLM talks. Rules decide. Humans act." in content
    assert "Sample data. Not medical advice. Synthetic-data prototype, not a medical device." in content
