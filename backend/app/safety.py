"""
backend/app/safety.py — CareLoop Deterministic Safety Engine

Core Principle: "The LLM talks. Rules decide. Humans act."
Emergency guidance and dose-change refusals MUST NEVER wait for or rely on an LLM call.
"""

from typing import Tuple

# Clinician-approved starter keyword list (English + Hindi)
EMERGENCY_TERMS = [
    # English
    "chest pain",
    "can't breathe",
    "cannot breathe",
    "difficulty breathing",
    "short of breath",
    "shortness of breath",
    "unconscious",
    "fainted",
    "heavy bleeding",
    "severe bleeding",
    "seizure",
    "stroke",
    "heart attack",
    "choking",
    "collapsed",
    # Hindi (Devanagari)
    "सीने में दर्द",
    "सीने में तेज दर्द",
    "सीने में बहुत तेज दर्द",
    "सांस नहीं",
    "सांस लेने में तकलीफ",
    "सांस फूलना",
    "सांस फूल रही",
    "सांस लेने में बहुत तकलीफ",
    "बेहोश",
    "बहुत खून",
    "चक्कर आकर गिर",
    "दौरा",
    "दिल का दौरा",
]

EMERGENCY_GUIDANCE = {
    "en": "This may be an emergency. If you have severe chest pain or trouble breathing, call 112 now. Your care team has been told.",
    "hi": "यह आपातकालीन स्थिति हो सकती है। अगर सीने में तेज़ दर्द हो या सांस लेने में परेशानी हो, तो तुरंत 112 पर कॉल करें। आपकी केयर टीम को सूचित कर दिया गया है।",
}

DOSE_CHANGE_PATTERNS = [
    # English
    "double dose",
    "double my dose",
    "double the dose",
    "doubled my dose",
    "doubling my dose",
    "doubling the dose",
    "twice the dose",
    "skip my medicine",
    "skip the dose",
    "skip my dose",
    "stop taking",
    "stop my medicine",
    "stop the medicine",
    "increase the dose",
    "increase my dose",
    "decrease the dose",
    "decrease my dose",
    "extra tablet",
    "extra pill",
    "take two",
    "take 2",
    "halve the dose",
    "change dosage",
    "change dose",
    "change my dose",
    # Hindi
    "दवा बंद",
    "दवा छोड़",
    "दोगुनी खुराक",
    "खुराक बढ़ा",
    "खुराक कम",
    "अतिरिक्त गोली",
]

DOSE_CHANGE_REFUSAL = {
    "en": "I cannot advise on changing, stopping, or adjusting medication doses. Please contact your care team. A note has been sent to your team to follow up.",
    "hi": "मैं दवा की खुराक बदलने, रोकने या बदलने की सलाह नहीं दे सकता। कृपया अपनी केयर टीम से बात करें। आपकी टीम को सूचित कर दिया गया है।",
}


def has_emergency_term(text: str) -> bool:
    """
    Deterministic check for emergency keywords in English and Hindi.
    Case-insensitive, runs in O(N) string search.
    """
    if not text:
        return False
    t = text.lower()
    return any(term in t for term in EMERGENCY_TERMS)


def is_dose_change_question(text: str) -> bool:
    """
    Deterministic check for questions or statements requesting medication adjustments.
    """
    if not text:
        return False
    t = text.lower()
    return any(p in t for p in DOSE_CHANGE_PATTERNS)
