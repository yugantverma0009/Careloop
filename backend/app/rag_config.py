"""
backend/app/rag_config.py — Configuration and Prompts for CareLoop Discharge Assistant
"""

import os

USE_UPGRADED_RAG = os.getenv("USE_UPGRADED_RAG", "true").lower() in ("true", "1", "yes")

# Intent definitions
INTENT_APPOINTMENT = "appointment"
INTENT_TODAY_DOSES = "today_doses"
INTENT_MEDICINE_PLAN = "medicine_plan"
INTENT_VITALS = "vitals"
INTENT_WARNING_SIGNS = "warning_signs"
INTENT_ACTIVITY = "activity"
INTENT_DIET = "diet"
INTENT_WOUND_CARE = "wound_care"
INTENT_GENERAL_DOCS = "general_docs"
INTENT_EMERGENCY = "emergency"
INTENT_REFUSAL_DOSE = "refusal_dose"
INTENT_REFUSAL_MEDICAL = "refusal_medical"
INTENT_OUT_OF_SCOPE = "out_of_scope"
INTENT_SMALL_TALK = "small_talk"
INTENT_CONTACTS = "contacts"
INTENT_PLAN_ITEMS = "plan_items"

VALID_INTENTS = {
    INTENT_APPOINTMENT,
    INTENT_TODAY_DOSES,
    INTENT_MEDICINE_PLAN,
    INTENT_VITALS,
    INTENT_WARNING_SIGNS,
    INTENT_ACTIVITY,
    INTENT_DIET,
    INTENT_WOUND_CARE,
    INTENT_GENERAL_DOCS,
    INTENT_EMERGENCY,
    INTENT_REFUSAL_DOSE,
    INTENT_REFUSAL_MEDICAL,
    INTENT_OUT_OF_SCOPE,
    INTENT_SMALL_TALK,
    INTENT_CONTACTS,
    INTENT_PLAN_ITEMS,
}

# Allowlist for patient-confirmed action cards (Brief Sec 7.6 & 7.12)
ALLOWLIST_ACTIONS = {
    "Start_Checkin",
    "Add_Photo",
    "Request_Call",
    "Ask_Care_Team",
    "Open_Plan_Item",
    "Open_Medicines",
    "Add_Appointment_To_Calendar",
    "Open_SOS",
    "Call_112",
}

NOT_FOUND_MSG = {
    "en": "That is not in your discharge papers, so I will not guess.",
    "hi": "यह आपके डिस्चार्ज पेपर्स में नहीं है, इसलिए मैं अनुमान नहीं लगाऊँगा।",
}

UNAVAILABLE_MSG = {
    "en": "The assistant is unavailable right now. If this is an emergency, please call 112 or contact your care team.",
    "hi": "सहायक इस समय उपलब्ध नहीं है। यदि यह आपातकालीन स्थिति है, तो कृपया 112 पर कॉल करें या अपनी देखभाल टीम से संपर्क करें।",
}

# Brief Sec 7.6 System Prompt
RAG_SYSTEM_PROMPT = """You are CareLoop's discharge assistant. You help ONE patient understand THEIR OWN discharge papers and care plan.

RULES:
1. Use the CONTEXT blocks and TOOL RESULTS below as your primary source of truth.
2. Copy every number, date, time, dose and medicine name exactly as written. Never calculate, convert or round them.
3. Never diagnose diseases. Never claim a symptom or vital reading is unconditionally safe. Never suggest changing, skipping, stopping or doubling any medicine.
4. If the patient describes a symptom, bodily discomfort, or recovery concern (e.g. back pain, leg swelling, dizziness, fatigue, nausea):
   - Acknowledge their concern with empathy.
   - Clarify whether this specific symptom is explicitly mentioned in their discharge papers.
   - Remind them of critical red-flag warning signs from their papers (severe chest tightness, sudden shortness of breath, SpO2 < 94%, heart rate > 100 bpm) and tell them to call 112 immediately if pain is severe or radiates.
   - Direct them to record this symptom in their daily check-in so their care team can monitor it.
   - Include actions: [{{"action_type": "Start_Checkin"}}, {{"action_type": "Ask_Care_Team"}}].
   - Set found=true.
5. If the query is unrelated general trivia or completely out of scope, return found=false.
6. Write for a worried non-expert: plain words, short sentences, about 60 to 90 words. Answer first, then at most 3 short helpful bullets.
7. Reply in the language of the patient's question: {language}.
8. Never invent or include patient names or personal phone numbers in the response text.

Return JSON strictly in this format:
{{
  "found": true,
  "answer": "Direct compassionate plain answer.",
  "bullets": ["Bullet 1 explanation", "Bullet 2 explanation"],
  "source_ids": ["S1"],
  "actions": [{{"action_type": "Start_Checkin"}}, {{"action_type": "Ask_Care_Team"}}],
  "suggest_care_team": true,
  "suggested_followups": ["Followup question 1", "Followup question 2"]
}}
"""

REWRITE_PROMPT = """Given the recent conversation between a patient and the discharge assistant, rewrite the patient's latest question into a standalone, unambiguous search query.
Do NOT answer the question. Do NOT add any fictional facts.
If the question is already clear and standalone, return it as is.
Reply with the standalone query text only."""
