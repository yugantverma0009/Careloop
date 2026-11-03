"""
backend/app/assistant_router.py — Assistant v2 Intent Router and Small Talk Handler

Principle: "The LLM talks. Rules decide. Humans act."
- Rule-first intent routing: emergency, dose_change, small_talk, tool_lookup, document_question, out_of_scope.
- Small talk: fixed friendly replies, no LLM, no source citations, patient name inserted by code.
- Strict PII boundary: patient names, phone numbers, and contact details are NEVER sent to LLMs.
"""

import re
from typing import Dict, Any, Optional, Tuple
from .safety import has_emergency_term, is_dose_change_question
from .rag_config import (
    INTENT_EMERGENCY,
    INTENT_REFUSAL_DOSE,
    INTENT_REFUSAL_MEDICAL,
    INTENT_OUT_OF_SCOPE,
    INTENT_APPOINTMENT,
    INTENT_TODAY_DOSES,
    INTENT_MEDICINE_PLAN,
    INTENT_VITALS,
    INTENT_WARNING_SIGNS,
    INTENT_ACTIVITY,
    INTENT_DIET,
    INTENT_WOUND_CARE,
    INTENT_GENERAL_DOCS,
    INTENT_CONTACTS,
    INTENT_PLAN_ITEMS,
)

INTENT_SMALL_TALK = "small_talk"

# ─── Small Talk Subtypes and Patterns (English and Hindi) ─────────────────────

THANKS_PATTERNS = [
    r"\bthank\s+you\b",
    r"\bthanks\b",
    r"\bthx\b",
    r"\bthank\s+u\b",
    r"\bmany\s+thanks\b",
    r"\bappreciate\s+it\b",
    r"\bgrateful\b",
    r"धन्यवाद",
    r"शुक्रिया",
    r"मेहरबानी",
    r"\bdhanyawad\b",
    r"\bshukriya\b",
]

GREETING_PATTERNS = [
    r"\bhello\b",
    r"\bhi\b",
    r"\bhey\b",
    r"\bgood\s+morning\b",
    r"\bgood\s+afternoon\b",
    r"\bgood\s+evening\b",
    r"नमस्ते",
    r"नमस्कार",
    r"प्रणाम",
    r"\bnamaste\b",
    r"\bnamaskar\b",
]

GOODBYE_PATTERNS = [
    r"\bbye\b",
    r"\bgoodbye\b",
    r"\bsee\s+you\b",
    r"\btake\s+care\b",
    r"\bhave\s+a\s+good\s+day\b",
    r"अलविदा",
    r"बाय",
    r"फिर मिलेंगे",
    r"\balvida\b",
]

AFFIRMATION_PATTERNS = [
    r"^\s*ok\s*$",
    r"^\s*okay\s*$",
    r"^\s*understood\s*$",
    r"^\s*got\s+it\s*$",
    r"^\s*alright\s*$",
    r"^\s*fine\s*$",
    r"^\s*sure\s*$",
    r"^\s*ठीक है\s*$",
    r"^\s*समझ गया\s*$",
    r"^\s*अच्छा\s*$",
    r"^\s*theek hai\s*$",
    r"^\s*samajh gaya\s*$",
    r"^\s*achha\s*$",
]


def detect_small_talk(query: str) -> Optional[str]:
    """
    Returns small talk subtype ('thanks', 'greeting', 'goodbye', 'affirmation')
    or None if the query is not small talk.
    Small talk queries must be brief conversational phrases, not substantive clinical questions.
    """
    q = query.lower().strip()
    words = q.split()

    # If the message is long (> 12 words) and contains clinical terms, it's not small talk
    clinical_keywords = ["medicine", "dose", "tablet", "pain", "wound", "doctor", "appointment", "spo2", "heart", "दवा", "दर्द", "घाव"]
    if len(words) > 8 and any(k in q for k in clinical_keywords):
        return None

    # Check affirmations first (exact matches)
    for pat in AFFIRMATION_PATTERNS:
        if re.search(pat, q):
            return "affirmation"

    # Check thanks
    for pat in THANKS_PATTERNS:
        if re.search(pat, q):
            return "thanks"

    # Check greeting (only if short)
    if len(words) <= 5:
        for pat in GREETING_PATTERNS:
            if re.search(pat, q):
                return "greeting"

    # Check goodbye
    if len(words) <= 5:
        for pat in GOODBYE_PATTERNS:
            if re.search(pat, q):
                return "goodbye"

    return None


def get_first_name(full_name: Optional[str]) -> str:
    """Extracts first name from full name, stripping titles (Dr., Mr., etc.)."""
    if not full_name:
        return "Aarav"
    cleaned = re.sub(r"^(dr\.|mr\.|mrs\.|ms\.)\s*", "", full_name.strip(), flags=re.IGNORECASE)
    parts = cleaned.split()
    return parts[0] if parts else "Aarav"


def handle_small_talk(
    query: str,
    language: str = "en",
    patient_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Produces deterministic, friendly small-talk responses in English or Hindi.
    - NO LLM is called.
    - NO source chips are returned (sources=[]).
    - Patient name is inserted strictly by Python string formatting.
    """
    subtype = detect_small_talk(query) or "thanks"
    first_name = get_first_name(patient_name)
    lang = language.lower() if language in ("en", "hi") else "en"

    if subtype == "thanks":
        answer_en = f"You are welcome, {first_name}. Please rest and reach out if you notice any warning signs."
        answer_hi = f"आपका स्वागत है, {first_name}। कृपया आराम करें और यदि कोई खतरे के लक्षण दिखें तो तुरंत संपर्क करें।"
    elif subtype == "greeting":
        answer_en = f"Hello {first_name}. How can I help you with your discharge papers today?"
        answer_hi = f"नमस्ते {first_name}। आज मैं आपके डिस्चार्ज पेपर्स को समझने में आपकी क्या मदद करूँ?"
    elif subtype == "goodbye":
        answer_en = f"Take care, {first_name}. Remember to follow your medication schedule."
        answer_hi = f"ख्याल रखें, {first_name}। अपनी दवाओं का समय याद रखें।"
    else:  # affirmation
        answer_en = f"Glad to help, {first_name}. Let me know if you have any other questions about your recovery."
        answer_hi = f"मदद करके खुशी हुई, {first_name}। यदि आपकी रिकवरी के बारे में कोई अन्य प्रश्न हो तो अवश्य बताएं।"

    ans_text = answer_hi if lang == "hi" else answer_en

    return {
        "answer_type": "small_talk",
        "answer": ans_text,
        "bullets": [],
        "sources": [],  # STRICT REQUIREMENT: No source chips for small talk
        "suggestions": [
            "What medicines do I take today?" if lang == "en" else "आज मुझे कौन सी दवा लेनी है?",
            "When is my next appointment?" if lang == "en" else "मेरी अगली डॉक्टर विज़िट कब है?",
            "What warning signs should I watch for?" if lang == "en" else "किन खतरे के लक्षणों पर ध्यान दूँ?",
        ],
        "can_ask_care_team": False,
        "is_grounded": False,
        "response": ans_text,
        "citations": [],
        "retrieval_debug": {
            "intent": "small_talk",
            "subtype": subtype,
            "llm_called": False,
            "name_inserted_by_code": True,
        },
    }


def route_intent_v2(question: str) -> str:
    """
    Assistant v2 Rule-First Intent Router (Brief Sec A):
    emergency, dose_change, small_talk, tool_lookup, document_question, out_of_scope.
    """
    q = question.lower().strip()

    # 1. Deterministic Emergency Check (Instant, No LLM)
    if has_emergency_term(q):
        return INTENT_EMERGENCY

    # 2. Deterministic Dose-Change Check (Instant Refusal, No LLM)
    if is_dose_change_question(q):
        return INTENT_REFUSAL_DOSE

    # 3. Small-talk Check (Instant Friendly Reply, No LLM, No Sources)
    if detect_small_talk(q):
        return INTENT_SMALL_TALK

    # 4. Medical Diagnosis Refusal Check
    medical_diagnosis_patterns = [
        r"\bdo i have an infection\b",
        r"\bis my condition serious\b",
        r"\bis it normal to\b",
        r"\bam i safe\b",
        r"\bam i cured\b",
        r"\bcan you diagnose\b",
        r"\bwhat disease do i have\b",
        "क्या मुझे इन्फेक्शन है",
        "क्या मेरी हालत गंभीर है",
        "क्या मैं ठीक हो गया",
        "क्या मुझे कोई बीमारी है",
    ]
    for pat in medical_diagnosis_patterns:
        if re.search(pat, q):
            return INTENT_REFUSAL_MEDICAL

    # 5. Out of Scope Check
    out_of_scope_patterns = [
        r"\bcapital of\b",
        r"\bweather in\b",
        r"\bwho is the president\b",
        r"\bprime minister\b",
        r"\brecipe for\b",
        r"\bcricket score\b",
        "राजधानी क्या है",
        "मौसम कैसा है",
        "प्रधानमंत्री कौन",
    ]
    for pat in out_of_scope_patterns:
        if re.search(pat, q):
            return INTENT_OUT_OF_SCOPE

    # 6. Read-Only Structured SQL Tools
    # Care Team Contacts
    contacts_keywords = [
        "contact", "helpline", "support desk", "phone number", "hospital helpline",
        "अस्पताल केयर टीम", "केयर टीम का नंबर", "हेल्पलाइन", "सम्पर्क", "संपर्क", "फोन नंबर", "फ़ोन नंबर"
    ]
    if any(k in q for k in contacts_keywords):
        return INTENT_CONTACTS

    # Care / Recovery Plan Items
    plan_items_keywords = [
        "recovery milestone", "milestones", "exercise items in my plan", "walking goal",
        "plan items", "recovery plan", "approved exercise", "लक्ष्य", "केयर प्लान में क्या लक्ष्य"
    ]
    if any(k in q for k in plan_items_keywords) and not any(k in q for k in ["medicine", "tablet", "दवा"]):
        return INTENT_PLAN_ITEMS

    # Appointments
    appointment_keywords = [
        "appointment", "visit", "doctor", "follow up", "follow-up", "whom", "next visit", "physician", "clinic in",
        "मिलना", "विज़िट", "डॉक्टर", "अपॉइंटमेंट", "कब आना है", "अगली विज़िट", "मुलाक़ात", "मुलाकात", "अगली मुलाक़ात"
    ]
    if any(k in q for k in appointment_keywords) and not any(k in q for k in ["medicine", "tablet", "दवा"]):
        return INTENT_APPOINTMENT

    # Today's Scheduled Doses
    today_doses_keywords = [
        "what medicine", "which medicine", "which tablet", "medicines today", "doses today", "take today", "morning dose",
        "evening dose", "night dose", "what time do i take", "time do i take", "when do i take", "after meals",
        "दवाइयां आज", "आज कौन सी दवा", "रात की दवा", "सुबह की दवा", "दवा का समय",
        "कौन सी दवाइयाँ", "कौन सी दवा", "दवा लेनी है", "गोली खानी है", "दवाइयां लेनी"
    ]
    if any(k in q for k in today_doses_keywords):
        return INTENT_TODAY_DOSES

    # Active Prescription Courses / Plan End
    medicine_plan_keywords = [
        "until when", "how long do i take", "course end", "finish medicine", "finish",
        "last date of medicine", "course duration", "कब तक लेनी है", "दवा कब तक", "कोर्स कब खत्म", "कब तक दवा",
        "कब तक दवाइयाँ", "दवा कब समाप्त होगी", "कब खत्म होगी", "कोर्स कब"
    ]
    if any(k in q for k in medicine_plan_keywords):
        return INTENT_MEDICINE_PLAN

    # Device Readings / Vitals
    vitals_keywords = [
        "oxygen", "pulse", "heart rate", "spo2", "reading", "sensor", "blood pressure", "vitals",
        "ऑक्सीजन", "हार्ट रेट", "पल्स", "रीडिंग", "बीपी", "दिल की धड़कन", "ब्लड प्रेशर", "रक्तचाप", "ताज़ा पल्स"
    ]
    for k in vitals_keywords:
        if re.search(r"\b" + re.escape(k) + r"\b", q):
            return INTENT_VITALS

    # 7. Document Question Categories
    # Warning signs
    warning_signs_keywords = [
        "warning sign", "warning signs", "red flag", "danger", "emergency sign", "watch for", "when to call", "call the hospital", "threshold",
        "खतरे के लक्षण", "ख़तरे के लक्षण", "चेतावनी", "सावधानी", "खतरा", "अस्पताल को सूचना", "खतरे का संकेत"
    ]
    if any(k in q for k in warning_signs_keywords):
        return INTENT_WARNING_SIGNS

    # Activity & Restrictions
    activity_keywords = [
        "shower", "bath", "exercise", "walk", "walking", "lift", "heavy lifting", "heavy objects", "stairs", "bending", "physical activity",
        "सीढ़ियां", "सीढ़ी", "नहाना", "वजन उठाना", "भारी वजन", "व्यायाम", "चलना", "शारीरिक गतिविधि", "चलने-फिरने", "चल-फिर"
    ]
    if any(k in q for k in activity_keywords):
        return INTENT_ACTIVITY

    # Diet & Nutrition
    diet_keywords = [
        "diet", "food", "eat", "drink", "water", "meal", "eat and drink", "salt", "sodium", "fluid", "fluids",
        "खाना", "आहार", "भोजन", "पानी", "डाइट", "पानी पीना", "नमक", "सोडियम", "सुपाच्य"
    ]
    if any(k in q for k in diet_keywords) and not any(k in q for k in ["medicine", "tablet", "दवा", "pill", "goli"]):
        return INTENT_DIET

    # Wound Care & Incision
    wound_care_keywords = [
        "wound", "dressing", "incision", "bandage", "stitches", "surgical wound",
        "टांके", "घाव", "पट्टी", "ड्रेसिंग", "घाव की देखभाल"
    ]
    if any(k in q for k in wound_care_keywords):
        return INTENT_WOUND_CARE

    return INTENT_GENERAL_DOCS

