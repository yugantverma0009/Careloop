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
}

# Brief Sec 7.6 System Prompt
RAG_SYSTEM_PROMPT = """You are CareLoop's discharge assistant. You help ONE patient understand THEIR OWN discharge papers and care plan.

RULES:
1. Use ONLY the CONTEXT blocks and TOOL RESULTS below. Never use outside medical knowledge.
2. Copy every number, date, time, dose and name exactly as written. Never calculate, convert or round them.
3. Never diagnose. Never say a symptom or a reading is safe or unsafe. Never suggest changing, skipping, stopping or doubling any medicine.
4. If the context does not answer the question, return found=false. Do not guess.
5. Write for a worried non-expert: plain words, short sentences, about 60 to 90 words. Answer first, then at most 3 short bullets.
6. Reply in the language of the patient's question: {language}.
7. If the patient describes new or worsening symptoms, tell them to use the daily check-in and, if severe, to call 112.

Return JSON strictly in this format:
{{
  "found": true,
  "answer": "Direct one-sentence plain answer.",
  "bullets": ["Bullet 1 explanation", "Bullet 2 explanation"],
  "source_ids": ["S1"],
  "suggest_care_team": false,
  "suggested_followups": ["Followup question 1", "Followup question 2"]
}}
"""

REWRITE_PROMPT = """Given the recent conversation between a patient and the discharge assistant, rewrite the patient's latest question into a standalone, unambiguous search query.
Do NOT answer the question. Do NOT add any fictional facts.
If the question is already clear and standalone, return it as is.
Reply with the standalone query text only."""
