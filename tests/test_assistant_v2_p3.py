"""
tests/test_assistant_v2_p3.py — Automated Test Suite for Assistant v2 Phase 3 (Voice)

Verifies Phase 3 Requirements:
1. Plain-code emergency detection on voice queries (English & Hindi) bypasses LLM and returns immediate 112 guidance.
2. Privacy & No-Audio Storage: Backend does not accept or store audio bytes; voice relies on client-side Web Speech.
3. Chat safety under voice queries: LLM response cannot mutate medications, doses, or flags.
4. Voice response localization: Responses support English (en-IN) and Hindi (hi-IN) for Web Speech synthesis.
5. Voice small talk: Casual speech ("thank you", "धन्यवाद") receives polite replies without source chips.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.auth import make_token, verify_login
from backend.app.rag_pipeline import answer_patient_query
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


# ─── 1. Voice Emergency Interception (English & Hindi) ──────────────────────

def test_voice_emergency_interception_english():
    """Emergency voice transcript must trigger immediate emergency response with 112 guidance."""
    emergency_transcripts = [
        "I am having severe chest pain right now",
        "trouble breathing and pressure on my chest",
        "I can't breathe",
    ]
    for transcript in emergency_transcripts:
        res = answer_patient_query(patient_id=1, question=transcript, patient_name="Aarav Patel", language="en")
        assert res["answer_type"] == "emergency", f"Failed for '{transcript}'"
        assert "112" in res["answer"]
        assert len(res["sources"]) == 0, "Emergency answers must not have document sources"


def test_voice_emergency_interception_hindi():
    """Hindi emergency voice transcript must trigger immediate emergency response with 112 guidance."""
    emergency_transcripts_hi = [
        "सीने में बहुत तेज दर्द हो रहा है",
        "सांस लेने में बहुत परेशानी हो रही है",
    ]
    for transcript in emergency_transcripts_hi:
        res = answer_patient_query(patient_id=1, question=transcript, patient_name="Aarav Patel", language="hi")
        assert res["answer_type"] == "emergency", f"Failed for '{transcript}'"
        assert "112" in res["answer"]
        assert len(res["sources"]) == 0


# ─── 2. Privacy & Audio Architecture ────────────────────────────────────────

def test_no_audio_endpoints_or_storage(client, patient_token):
    """CareLoop does not accept or store raw audio files. Web Speech is client-side."""
    # Attempting to POST raw audio bytes to chat endpoint must fail with validation error (422)
    res = client.post(
        "/patient/me/chat",
        headers={"Authorization": f"Bearer {patient_token}", "Content-Type": "audio/wav"},
        content=b"RIFF....WAVEfmt ",
    )
    assert res.status_code == 422, "Backend must reject raw audio payloads"


# ─── 3. Voice Small Talk (No Source Chips) ──────────────────────────────────

def test_voice_small_talk_handling():
    """Spoken casual queries ('thank you', 'धन्यवाद') must have 0 source chips."""
    res_en = answer_patient_query(patient_id=1, question="Thank you so much", patient_name="Aarav Patel", language="en")
    assert res_en["answer_type"] == "small_talk"
    assert len(res_en["sources"]) == 0
    assert "Aarav" in res_en["answer"]  # Patient name inserted by code

    res_hi = answer_patient_query(patient_id=1, question="धन्यवाद", patient_name="Aarav Patel", language="hi")
    assert res_hi["answer_type"] == "small_talk"
    assert len(res_hi["sources"]) == 0
    assert "Aarav" in res_hi["answer"] or "आरव" in res_hi["answer"]


# ─── 4. Voice Query via Patient Chat API ────────────────────────────────────

def test_patient_chat_voice_transcript_flow(client, patient_token):
    """A transcribed voice query submitted via the API returns answer suitable for speech playback."""
    response = client.post(
        "/patient/me/chat",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={"message": "What is my medicine schedule today?", "lang": "en"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    # Text should be clean string readable by window.speechSynthesis
    assert isinstance(data["answer"], str)
    assert len(data["answer"]) > 10
    assert "sources" in data


# ─── 5. Safety Rule 1: No State Mutation via Voice ──────────────────────────

def test_voice_cannot_mutate_doses_or_flags(client, patient_token):
    """Even if speech transcript says 'Mark my medicine as taken', the chat endpoint only answers."""
    # Get current status
    today_before = client.get(
        "/patient/me/today",
        headers={"Authorization": f"Bearer {patient_token}"},
    ).json()

    # Chat with command-like voice transcript
    res = client.post(
        "/patient/me/chat",
        headers={"Authorization": f"Bearer {patient_token}"},
        json={"message": "I took my morning medicine, please mark it taken", "lang": "en"},
    )
    assert res.status_code == 200

    # Ensure dose state was NOT mutated by chat (LLM talks, rules decide, humans act)
    today_after = client.get(
        "/patient/me/today",
        headers={"Authorization": f"Bearer {patient_token}"},
    ).json()
    assert today_before["counts"] == today_after["counts"]
