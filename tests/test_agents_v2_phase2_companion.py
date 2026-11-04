"""
CareLoop Phase 2 Test Suite: Recovery Companion, Conversational Check-in,
Phrase Bank, Hinglish Normalizer, and Emergency Intercept.
"""

import pytest
from backend.app.agents.hinglish_normalizer import HinglishNormalizer
from backend.app.agents.phrase_bank_service import PhraseBankService
from backend.app.checkin import get_patient_checkin_context, record_checkin_answer, start_checkin_session, get_active_checkin_template
from backend.app.db import get_conn


def test_hinglish_normalizer_20_turns():
    """Verify 20 diverse spoken Hinglish, Hindi, and English turns across numbers, adherence, and wound."""
    normalizer = HinglishNormalizer()

    # 1-7: Numbers in Hindi/Hinglish
    assert normalizer.normalize_number("shunya") == 0
    assert normalizer.normalize_number("paanch") == 5
    assert normalizer.normalize_number("panch dard hai") == 5
    assert normalizer.normalize_number("saat") == 7
    assert normalizer.normalize_number("das me se aath") == 8
    assert normalizer.normalize_number("dus") == 10
    assert normalizer.normalize_number("tin") == 3

    # 8-11: Yes / No
    assert normalizer.normalize_yes_no("haanji bilkul") is True
    assert normalizer.normalize_yes_no("nahi bilkul nahi") is False
    assert normalizer.normalize_yes_no("na") is False
    assert normalizer.normalize_yes_no("yes i do") is True

    # 12-14: Med Adherence
    assert normalizer.normalize_med_adherence("maine sari dawai le li") == "all"
    assert normalizer.normalize_med_adherence("sirf subah ki li, sham ki baaki") == "some"
    assert normalizer.normalize_med_adherence("aaj bilkul nahi le paya") == "none"

    # 15-17: Wound site status
    assert normalizer.normalize_wound_status("wound is healing fine sab theek hai") == "fine"
    assert normalizer.normalize_wound_status("thoda dard hai slight discomfort") == "mild"
    assert normalizer.normalize_wound_status("bahut laal hai aur pas aa raha hai bohot chinta hai") == "worried"

    # 18-20: Missed Medication Barriers Extraction
    b1 = normalizer.extract_barriers("bhool gaya tha lena")
    assert b1["barrier"] == "forgot"

    b2 = normalizer.extract_barriers("tabiyat kharab lag rahi thi ulti jaisa")
    assert b2["barrier"] in ("unwell", "felt_unwell")

    b3 = normalizer.extract_barriers("goli khatam ho gayi thi")
    assert b3["barrier"] == "ran_out"


def test_phrase_bank_retrieval_and_reading_grade():
    """Verify doctor-approved phrase bank returns valid greetings, acknowledgements, and low reading grade."""
    PhraseBankService.seed_initial_phrases()
    phrases = PhraseBankService.get_approved_phrases("greeting", "hi")
    assert len(phrases) > 0
    assert any("नमस्ते" in p["phrase_text"] or "प्रणाम" in p["phrase_text"] for p in phrases)

    en_closing = PhraseBankService.get_random_approved("closing", "en")
    assert en_closing is not None
    assert len(en_closing) > 5

    emergency = PhraseBankService.get_random_approved("emergency", "hi")
    assert emergency is not None
    assert "112" in emergency


def test_checkin_context_retrieval():
    """Verify get_patient_checkin_context returns completed status, yesterday fact, and rotating greeting."""
    ctx = get_patient_checkin_context(patient_id=1, language="en")
    assert "completed_today" in ctx
    assert "yesterday_fact" in ctx
    assert "greeting" in ctx
    assert ctx["patient_id"] == 1


def test_conversational_checkin_turn_progression_and_branching():
    """Verify turn-by-turn check-in progression, pain branching (>= 7), med barrier branching, and completion."""
    tmpl = get_active_checkin_template()
    assert tmpl is not None
    assert len(tmpl["questions"]) >= 5

    sess = start_checkin_session(patient_id=1, channel="App_Guided")
    session_id = sess["session_id"]

    # Q1: Pain rating of 8 should trigger pain_details branching
    res1 = record_checkin_answer(session_id, question_id=1, raw_answer="aath", language="hi")
    assert res1["normalized_value"] == 8
    assert res1["branching"]["ask_pain_details"] is True

    # Q2: Emergency symptoms = No
    res2 = record_checkin_answer(session_id, question_id=2, raw_answer="nahi", language="hi")
    assert res2["emergency"] is False

    # Q3: Med adherence = Some should trigger med_barriers branching
    res3 = record_checkin_answer(session_id, question_id=3, raw_answer="kuch li thi", language="hi")
    assert res3["normalized_value"] == "some"
    assert res3["branching"]["ask_med_barriers"] is True

    # Q4: Wound status = Healing well
    res4 = record_checkin_answer(session_id, question_id=4, raw_answer="sab theek hai", language="hi")
    assert res4["normalized_value"] == "fine"

    # Q5: Additional notes -> completes session
    res5 = record_checkin_answer(session_id, question_id=5, raw_answer="None", language="en")
    assert res5["completed"] is True
    assert "facts_summary" in res5
    assert len(res5["facts_summary"]) >= 4
    assert res5["closing_phrase"] is not None


def test_emergency_interception():
    """Verify Q2 emergency affirmative immediately halts routine questions and alerts triage nurse."""
    sess = start_checkin_session(patient_id=2, channel="App_Guided")
    session_id = sess["session_id"]

    # Q1: Moderate pain
    record_checkin_answer(session_id, question_id=1, raw_answer="4", language="en")

    # Q2: Emergency Symptoms = Yes!
    res_em = record_checkin_answer(session_id, question_id=2, raw_answer="haan bohot seene me dard hai", language="hi")
    assert res_em["emergency"] is True
    assert res_em["status"] == "emergency_triggered"
    assert res_em["halt_flow"] is True
    assert "112" in res_em["guidance"]

    # Verify flag was written to flags table
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT flag_id, source_type, reason, severity FROM flags WHERE patient_id = 2 ORDER BY flag_id DESC LIMIT 1")
            flag = cur.fetchone()
            assert flag is not None
            assert flag["source_type"] == "Emergency"
            assert "emergency" in flag["reason"].lower()
