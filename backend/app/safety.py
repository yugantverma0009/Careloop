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
    "असहनीय दर्द",
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
    "increase my",
    "increase dose",
    "decrease the dose",
    "decrease my dose",
    "decrease my",
    "decrease dose",
    "adjust my",
    "adjust the",
    "adjust dose",
    "higher dose",
    "lower dose",
    "extra tablet",
    "extra pill",
    "take two",
    "take 2",
    "halve the dose",
    "change dosage",
    "change dose",
    "change my dose",
    "change my",
    "reduce my",
    "reduce the dose",
    "reduce dose",
    "half my",
    # Hindi (with and without nukta)
    "दवा बंद",
    "दवा छोड़",
    "दवा रोक",
    "दवा बदल",
    "दवा आधी",
    "गोली बंद",
    "आधी गोली",
    "गोली आधी",
    "दोगुनी",
    "दोगुनी खुराक",
    "दोगुनी ख़ुराक",
    "ख़ुराक दोगुनी",
    "खुराक दोगुनी",
    "खुराक बढ़ा",
    "ख़ुराक बढ़ा",
    "खुराक कम",
    "ख़ुराक कम",
    "खुराक आधी",
    "ख़ुराक आधी",
    "अतिरिक्त गोली",
]

DOSE_CHANGE_REFUSAL = {
    "en": "I cannot advise on changing, stopping, or adjusting medication doses. Please contact your care team. A note has been sent to your team to follow up.",
    "hi": "मैं दवा की खुराक बदलने, रोकने या बदलने की सलाह नहीं दे सकता। कृपया अपनी केयर टीम से बात करें। आपकी टीम को सूचित कर दिया गया है।",
}


import re

def has_emergency_term(text: str) -> bool:
    """
    Deterministic check for emergency keywords in English and Hindi.
    Case-insensitive, word-boundary safe for Hindi terms (e.g. avoiding false match of दौरा inside दौरान).
    """
    if not text:
        return False
    t = text.lower()
    for term in EMERGENCY_TERMS:
        if term == "दौरा":
            # Guard against "दौरान" ("during") - must match as standalone word or दौरे
            if re.search(r"(?<![^\s,।!?])दौरा(?![^\s,।!?])", t) or re.search(r"(?<![^\s,।!?])दौरे(?![^\s,।!?])", t):
                return True
            continue
        if term in t:
            return True
    if re.search(r"सीने में.*दर्द", t):
        return True
    return False


def is_dose_change_question(text: str) -> bool:
    """
    Deterministic check for questions or statements requesting medication adjustments.
    """
    if not text:
        return False
    t = text.lower()
    if any(p in t for p in DOSE_CHANGE_PATTERNS):
        return True
    if re.search(r"\b(double|halve|skip|increase|decrease|stop|change|adjust)\b.*?\b(dose|dosage|tablet|pill|medicine|medication)\b", t):
        return True
    if re.search(r"(दवा|गोली|खुराक|ख़ुराक).*?(छोड़|रोक|बढ़ा|कम|बदल|दोगुनी|आधी)", t):
        return True
    if re.search(r"(छोड़|रोक|बढ़ा|कम|बदल|दोगुनी|आधी).*?(दवा|गोली|खुराक|ख़ुराक)", t):
        return True
    return False
