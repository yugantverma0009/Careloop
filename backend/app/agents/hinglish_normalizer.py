"""
backend/app/agents/hinglish_normalizer.py — Hinglish & Spoken Hindi Normalizer (Phase 2 Task 6)

Normalizes transcribed voice or typed Hinglish inputs into deterministic structured answers
for the Care Guide daily check-in questions.
Rule: "The LLM talks. Rules decide. Humans act."
"""

import re
from typing import Dict, Any, Optional, Tuple


HINDI_NUMBER_MAP: Dict[str, int] = {
    "shunya": 0, "sunya": 0, "zero": 0, "sifar": 0,
    "ek": 1, "one": 1,
    "do": 2, "doh": 2, "two": 2,
    "teen": 3, "tin": 3, "three": 3,
    "chaar": 4, "char": 4, "four": 4,
    "paanch": 5, "panch": 5, "five": 5,
    "chhah": 6, "che": 6, "chhe": 6, "six": 6,
    "saat": 7, "sat": 7, "seven": 7,
    "aath": 8, "ath": 8, "eight": 8,
    "nau": 9, "no": 9, "nine": 9,
    "das": 10, "dus": 10, "ten": 10,
}

YES_WORDS = {
    "haan", "ha", "haa", "han", "haanji", "haji", "ji haan", "ji ha", "bilkul", "sahi", "yes", "yeah", "yep", "true"
}

NO_WORDS = {
    "nahi", "na", "nahin", "naa", "nahiji", "ji nahi", "bilkul nahi", "no", "nope", "false", "kuch nahi"
}

MED_ALL_WORDS = {
    "all", "sab", "sabhi", "saari", "sari", "puri", "sab le li", "saari le li", "sari dawai", "saari dawai", "puri le li",
    "haan sab", "yes all", "all taken"
}

MED_SOME_WORDS = {
    "some", "kuch", "thodi", "thoda", "aadha", "adha", "sirf", "baaki", "baki", "kuch li", "thodi li", "some taken", "partial"
}

MED_NONE_WORDS = {
    "none", "koi nahi", "ek bhi nahi", "nahi li", "kuch nahi li", "none taken", "bilkul nahi", "nahi le paya", "nahi"
}

WOUND_FINE_WORDS = {
    "fine", "theek", "thik", "theek hai", "thik hai", "achha", "achha hai", "sahi hai",
    "healing", "healing well", "no concern", "bilkul theek"
}

WOUND_MILD_WORDS = {
    "mild", "thoda", "thoda dard", "halka", "halka dard", "unsure", "not sure",
    "pata nahi", "doubt", "discomfort"
}

WOUND_WORRIED_WORDS = {
    "worried", "chinta", "bahut dard", "laal", "laal hai", "red", "painful",
    "pus", "kharab", "danger", "swelling", "sujan"
}

BARRIER_MAP: Dict[str, str] = {
    "bhool": "Forgot",
    "bhul": "Forgot",
    "forgot": "Forgot",
    "unwell": "Felt_Unwell",
    "kharab": "Felt_Unwell",
    "chakkar": "Felt_Unwell",
    "vomit": "Felt_Unwell",
    "ultee": "Felt_Unwell",
    "ulti": "Felt_Unwell",
    "khatam": "Ran_Out",
    "ran out": "Ran_Out",
    "khatam ho gayi": "Ran_Out",
    "side effect": "Side_Effects",
    "darr": "Side_Effects",
    "reaction": "Side_Effects",
    "confused": "Confused",
    "samajh": "Confused",
    "instructions": "Confused",
}


def normalize_pain_answer(raw_text: str) -> Optional[int]:
    """Extracts a 0-10 pain score from digits, Hindi, or Hinglish phrases."""
    if raw_text is None:
        return None
    text = str(raw_text).strip().lower()

    # Pattern for "das me se aath" or "10 me se 8" (out of 10, X)
    m_das = re.search(r"(?:10|das|dus|ten)\s+(?:me\s+se|mein\s+se)\s+([a-zA-Z0-9]+)", text)
    if m_das:
        tok = m_das.group(1)
        if tok.isdigit():
            return int(tok)
        if tok in HINDI_NUMBER_MAP:
            return HINDI_NUMBER_MAP[tok]

    # Pattern for "X out of 10" or "X me se 10"
    m_out = re.search(r"([a-zA-Z0-9]+)\s+(?:out\s+of|me\s+se|mein\s+se)\s+(?:10|das|dus|ten)", text)
    if m_out:
        tok = m_out.group(1)
        if tok.isdigit():
            return int(tok)
        if tok in HINDI_NUMBER_MAP:
            return HINDI_NUMBER_MAP[tok]

    # Direct digit match
    digit_match = re.search(r"\b([0-9]|10)\b", text)
    if digit_match:
        return int(digit_match.group(1))

    # Token match against spoken number dictionary
    words = re.findall(r"[a-zA-Z]+", text)
    for w in words:
        if w in HINDI_NUMBER_MAP:
            return HINDI_NUMBER_MAP[w]

    # Semantic level keywords
    if any(k in text for k in ["no pain", "dard nahi", "zero"]):
        return 0
    if any(k in text for k in ["halka", "thoda", "mild"]):
        return 3
    if any(k in text for k in ["tez", "bahut", "severe", "jyada"]):
        return 8

    return None


def normalize_yes_no(raw_text: str) -> Optional[str]:
    """Normalizes affirmative or negative response from Hinglish/Hindi/English."""
    if not raw_text:
        return None
    text = str(raw_text).strip().lower()

    # Exact checks first
    if text in YES_WORDS:
        return "yes"
    if text in NO_WORDS:
        return "no"

    words = re.findall(r"[a-zA-Z]+", text)
    for w in words:
        if w in YES_WORDS:
            return "yes"
        if w in NO_WORDS:
            return "no"

    return None


def normalize_medication_answer(raw_text: str) -> Optional[str]:
    """Normalizes medication adherence choice (all / some / none)."""
    if not raw_text:
        return None
    text = str(raw_text).strip().lower()

    if any(w in text for w in MED_NONE_WORDS):
        return "none"
    if any(w in text for w in MED_SOME_WORDS):
        return "some"
    if any(w in text for w in MED_ALL_WORDS):
        return "all"

    # Fallback to yes/no logic
    yn = normalize_yes_no(text)
    if yn == "yes":
        return "all"
    if yn == "no":
        return "none"

    return None


def normalize_wound_status(raw_text: str) -> Optional[str]:
    """Normalizes wound recovery status (fine / mild / worried)."""
    if not raw_text:
        return None
    text = str(raw_text).strip().lower()

    if any(w in text for w in WOUND_WORRIED_WORDS):
        return "worried"
    if any(w in text for w in WOUND_MILD_WORDS):
        return "mild"
    if any(w in text for w in WOUND_FINE_WORDS):
        return "fine"

    return None


def extract_barrier_code(raw_text: str) -> Optional[str]:
    """Identifies medication barrier reason code from text."""
    if not raw_text:
        return None
    text = str(raw_text).strip().lower()

    for pattern, code in BARRIER_MAP.items():
        if pattern in text:
            return code
    return "Other"


class HinglishNormalizer:
    """Class wrapper for Hinglish and Hindi clinical normalizations."""

    @staticmethod
    def normalize_number(text: str) -> Optional[int]:
        return normalize_pain_answer(text)

    @staticmethod
    def normalize_yes_no(text: str) -> Optional[bool]:
        res = normalize_yes_no(text)
        if res == "yes":
            return True
        if res == "no":
            return False
        return None

    @staticmethod
    def normalize_med_adherence(text: str) -> Optional[str]:
        return normalize_medication_answer(text)

    @staticmethod
    def normalize_wound_status(text: str) -> Optional[str]:
        return normalize_wound_status(text)

    @staticmethod
    def extract_barriers(text: str) -> Dict[str, Any]:
        code = extract_barrier_code(text)
        return {
            "barrier": code.lower() if code else "other",
            "raw": text,
        }

