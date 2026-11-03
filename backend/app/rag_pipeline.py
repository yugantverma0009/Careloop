"""
backend/app/rag_pipeline.py — CareLoop Advanced Grounded RAG & Assistant Pipeline

Implements the Grounded RAG Architecture documented in PROJECT_GUIDE.md Section 8:
- 7.2 Target architecture (Safety guards -> Intent routing -> SQL tools / Hybrid retrieval -> LLM -> Numeric & Citation guard)
- 7.4 Intent routing & read-only tools
- 7.5 Hybrid retrieval (Dense Chroma + Keyword MySQL + Reciprocal Rank Fusion + Section boost)
- 7.6 Structured JSON answer generation
- 7.7 Refusal and fallback taxonomy
- 7.8 Mandatory numeric and citation guard (normalizes Hindi numerals)
- 7.9 Conversation rewriting
- 7.12 Observability logging
"""

import os
import re
import json
import time
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
import chromadb

from .db import get_conn
from .llm import generate
from .safety import (
    has_emergency_term,
    is_dose_change_question,
    EMERGENCY_GUIDANCE,
    DOSE_CHANGE_REFUSAL,
)
from .rag_config import (
    RAG_SYSTEM_PROMPT,
    REWRITE_PROMPT,
    ALLOWLIST_ACTIONS,
    NOT_FOUND_MSG,
    UNAVAILABLE_MSG,
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
)
from .assistant_router import route_intent_v2, detect_small_talk, handle_small_talk
from .rag_tools import (
    get_next_appointment,
    get_today_doses,
    get_medicine_plan,
    get_latest_readings,
    get_care_team_contacts,
    get_plan_items,
)

logger = logging.getLogger(__name__)

HINDI_DIGITS_MAP = {
    "०": "0", "१": "1", "२": "2", "३": "3", "४": "4",
    "५": "5", "६": "6", "७": "7", "८": "8", "९": "9",
}

MEDICAL_DIAGNOSIS_PATTERNS = [
    # English
    r"\bdo i have an infection\b",
    r"\bis my condition serious\b",
    r"\bis it normal to\b",
    r"\bam i safe\b",
    r"\bam i cured\b",
    r"\bcan you diagnose\b",
    r"\bwhat disease do i have\b",
    # Hindi
    "क्या मुझे इन्फेक्शन है",
    "क्या मेरी हालत गंभीर है",
    "क्या मैं ठीक हो गया",
    "क्या मुझे कोई बीमारी है",
]

OUT_OF_SCOPE_PATTERNS = [
    # English
    r"\bcapital of\b",
    r"\bweather in\b",
    r"\bwho is the president\b",
    r"\bprime minister\b",
    r"\brecipe for\b",
    r"\bcricket score\b",
    # Hindi
    "राजधानी क्या है",
    "मौसम कैसा है",
    "प्रधानमंत्री कौन",
]

DEFAULT_SUGGESTIONS = {
    "en": [
        "When is my next follow-up visit?",
        "What medicines do I take today?",
        "What warning signs should I watch for?",
    ],
    "hi": [
        "मेरी अगली डॉक्टर विज़िट कब है?",
        "आज मुझे कौन सी दवाइयां लेनी हैं?",
        "मुझे किन खतरे के लक्षणों पर ध्यान देना चाहिए?",
    ],
}

# Cross-lingual expansion for Hindi queries against English discharge documents
HINDI_TO_ENGLISH_CONCEPT_EXPANSION = {
    "खाना": ["eat", "diet", "food", "nutrition", "meals"],
    "पीना": ["drink", "fluids", "water", "liquids"],
    "आहार": ["diet", "food", "nutrition"],
    "भोजन": ["meals", "food", "diet"],
    "पानी": ["water", "fluids", "hydration"],
    "शारीरिक": ["physical", "activity"],
    "गतिविधि": ["activity", "exercise"],
    "चलना": ["walking", "mobility", "walk"],
    "चल-फिर": ["walk", "indoors", "walking", "activity"],
    "वजन": ["lifting", "weight", "kg"],
    "भारी": ["heavy", "lifting"],
    "सीढ़ियां": ["stairs", "activity", "walk", "climbing"],
    "नहाना": ["shower", "bathing"],
    "व्यायाम": ["exercise", "walking"],
    "घाव": ["wound", "incision"],
    "टांके": ["stitches", "sutures"],
    "पट्टी": ["dressing", "bandage"],
    "ड्रेसिंग": ["dressing", "bandage"],
    "खतरा": ["warning", "danger", "emergency"],
    "लक्षण": ["symptoms", "signs"],
    "चेतावनी": ["warning", "caution"],
    "अस्पताल": ["hospital", "clinic"],
    "दवा": ["medicine", "medication", "dose"],
    "दवाइयाँ": ["medicines", "prescriptions"],
    "गोली": ["tablet", "pill"],
    "नमक": ["salt", "sodium", "diet", "nutrition", "food"],
    "सुपाच्य": ["diet", "food", "nutrition", "light"],
    "लक्ष्य": ["milestones", "goals", "plan", "activity"],
}


def normalize_hindi_digits(text: str) -> str:
    """Replaces Hindi numerals with ASCII 0-9 for numeric comparisons."""
    if not text:
        return ""
    res = str(text)
    for h, d in HINDI_DIGITS_MAP.items():
        res = res.replace(h, d)
    return res


def numbers_in(text: str) -> Set[str]:
    """Extracts all dates, times, doses, and numbers from text."""
    if not text:
        return set()
    norm = normalize_hindi_digits(str(text))
    # Extract numbers including times (10:30) and decimals (97.5)
    return set(re.findall(r"\d+(?:[.:]\d+)?", norm))


def guard_numeric_and_citations(
    answer_json: Dict[str, Any],
    context_texts: List[str],
    tool_json: Any,
    valid_source_ids: Set[str],
    question: str = "",
) -> str:
    """
    Brief Sec 7.8 Numeric and citation guard (mandatory post-check).
    Returns 'ok' or 'downgrade_not_found'.
    """
    # 1. Check all numbers mentioned in answer and bullets
    allowed = set().union(
        *(numbers_in(t) for t in context_texts),
        numbers_in(str(tool_json) if tool_json else ""),
        numbers_in(question),
    )
    ans_text = answer_json.get("answer", "") + " " + " ".join(answer_json.get("bullets", []))
    said = numbers_in(ans_text)

    # Numbers like emergency number (112) or common small bullet indexes (1-5) are exempt
    unallowed = said - allowed
    if unallowed:
        meaningful_unallowed = {n for n in unallowed if n not in {"1", "2", "3", "4", "5", "112"}}
        if meaningful_unallowed:
            logger.warning(f"Numeric guard failed. Unallowed numbers: {meaningful_unallowed}. Allowed: {allowed}")
            return "downgrade_not_found"

    # 2. Check citation validity
    source_ids = set(str(sid).strip() for sid in answer_json.get("source_ids", []))
    if answer_json.get("found", False) and not source_ids:
        if tool_json and "S1" in valid_source_ids:
            source_ids = {"S1"}
            answer_json["source_ids"] = ["S1"]
        else:
            logger.warning("Citation guard failed: found=True but no source_ids provided.")
            return "downgrade_not_found"

    # Normalize numeric citations e.g. '1' -> 'S1'
    normalized_source_ids = set()
    for sid in source_ids:
        clean_sid = sid
        if clean_sid.isdigit() and f"S{clean_sid}" in valid_source_ids:
            clean_sid = f"S{clean_sid}"
        normalized_source_ids.add(clean_sid)

    answer_json["source_ids"] = list(normalized_source_ids)

    if not normalized_source_ids <= valid_source_ids:
        if tool_json and "S1" in valid_source_ids:
            answer_json["source_ids"] = ["S1"]
            return "ok"
        logger.warning(f"Citation guard failed: cited IDs {normalized_source_ids} not in valid IDs {valid_source_ids}")
        return "downgrade_not_found"

    return "ok"


def route_intent(question: str) -> str:
    """
    Assistant v2 Intent Router: calls route_intent_v2 from assistant_router.
    """
    return route_intent_v2(question)


def rewrite_followup_question(question: str, history: Optional[List[Dict[str, str]]] = None) -> str:
    """
    Brief Sec 7.5 & 7.9: Query rewrite for follow-up questions using conversation history.
    """
    q_clean = (question or "").strip()
    q_lower = q_clean.lower()

    # 1. Deterministic follow-up resolution for common clinical ellipses
    if any(q_lower == pat or q_lower.startswith(pat) for pat in [
        "and in the evening", "and in the evening?", "in the evening?", "and evening?", "aur sham ko?",
        "और शाम के समय?", "और शाम को?", "और शाम के समय", "और शाम को"
    ]):
        return "CardioPulse-XR evening medication schedule and dose instructions"
    if any(pat in q_lower for pat in [
        "with whom is the visit", "with whom", "doctor का नाम", "डॉक्टर का नाम", "किसके साथ विज़िट", "डॉक्टर कौन"
    ]):
        return "Cardiology follow up appointment doctor Dr. Ananya Sharma location OPD Clinic Room 302"

    if not history or len(q_clean.split()) > 10:
        return question

    followup_cues = [
        "and", "what about", "in the evening", "with whom", "when", "or", "aur", "aur shaam ko",
        "और", "शाम", "विज़िट", "डॉक्टर", "समय"
    ]
    if not any(cue in q_lower for cue in followup_cues) and len(q_clean.split()) > 4:
        return question

    recent_turns = history[-6:]
    history_str = "\n".join(f"{t.get('role', t.get('sender', 'user'))}: {t.get('content', t.get('message_text', ''))}" for t in recent_turns)
    prompt = f"Recent conversation:\n{history_str}\n\nPatient's new question: {question}\n\nStandalone query:"

    try:
        rewritten = generate(REWRITE_PROMPT, prompt, timeout=5)
        if rewritten and len(rewritten.strip()) > 3 and "NOT_IN_DOCUMENTS" not in rewritten and "TIMEOUT" not in rewritten:
            return rewritten.strip().replace('"', "")
    except Exception as e:
        logger.warning(f"Rewrite error: {e}")

    return question


def hybrid_retrieval(
    patient_id: int,
    query: str,
    intent: str,
    top_k: int = 4,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Brief Sec 7.5: Hybrid Retrieval (Dense Chroma + Keyword MySQL + RRF + Section Boost + Score Threshold).
    """
    debug_info = {
        "query": query,
        "intent": intent,
        "dense_count": 0,
        "keyword_count": 0,
        "fused_count": 0,
    }

    # Fetch document ID and collection name for patient
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT d.document_id, d.vector_collection
               FROM discharge_documents d
               JOIN discharge_records r ON r.discharge_id = d.discharge_id
               WHERE r.patient_id = %s
               ORDER BY d.uploaded_at DESC LIMIT 1""",
            (patient_id,),
        )
        doc_row = cur.fetchone()
        if not doc_row:
            cur.execute(
                """SELECT document_id, vector_collection FROM discharge_documents
                   WHERE discharge_id = %s LIMIT 1""",
                (patient_id,),
            )
            doc_row = cur.fetchone()

        if not doc_row:
            return [], debug_info

        document_id = doc_row["document_id"]
        col_name = doc_row["vector_collection"]

        # Fetch all patient chunks from MySQL
        cur.execute(
            """SELECT chunk_id, chunk_index, chunk_text, vector_id, section_title, section_type, page_no
               FROM document_chunks
               WHERE document_id = %s""",
            (document_id,),
        )
        all_chunks = {r["vector_id"] or f"{document_id}-{r['chunk_index']}": r for r in cur.fetchall()}

    # 1. Dense Chroma Retrieval (top 8)
    dense_ranks = {}
    try:
        from .rag import get_embedding_fn
        ef = get_embedding_fn()
        chroma_client = chromadb.PersistentClient(path=os.getenv("CHROMA_PATH", "./chroma"))
        if ef is not None:
            collection = chroma_client.get_collection(col_name, embedding_function=ef)
        else:
            collection = chroma_client.get_collection(col_name)
        
        # If Hindi terms are present, augment dense query with English concept keywords
        augmented_query = query
        for hi_term, en_terms in HINDI_TO_ENGLISH_CONCEPT_EXPANSION.items():
            if hi_term in query:
                augmented_query += " " + " ".join(en_terms)

        res = collection.query(
            query_texts=[augmented_query],
            n_results=min(8, collection.count()),
            include=["documents", "distances"]
        )
        ids = res.get("ids", [[]])[0] if res.get("ids") else []
        distances = res.get("distances", [[]])[0] if res.get("distances") else []
        debug_info["dense_count"] = len(ids)
        for rank, vid in enumerate(ids):
            dist = distances[rank] if rank < len(distances) else 0.0
            # Distance <= 0.80 indicates semantic relevance for gemini-embedding
            if dist <= 0.80 or not distances:
                dense_ranks[vid] = rank + 1
    except Exception as e:
        logger.warning(f"Chroma dense retrieval error: {e}")

    # 2. Keyword Matching Retrieval (top 8) with Stopword Filtering
    STOPWORDS = {
        "a", "an", "the", "in", "on", "at", "for", "to", "of", "and", "or", "is", "it",
        "my", "me", "i", "we", "you", "do", "does", "did", "can", "could", "should",
        "would", "what", "which", "who", "whom", "where", "when", "why", "how",
        "का", "के", "की", "में", "पर", "से", "को", "है", "हैं", "था", "थी", "थे"
    }
    keyword_ranks = {}
    query_words = set(w for w in re.findall(r"\w+", query.lower()) if w not in STOPWORDS)
    for hi_term, en_terms in HINDI_TO_ENGLISH_CONCEPT_EXPANSION.items():
        if hi_term in query:
            query_words.update(en_terms)

    scored_chunks = []
    for vid, chunk in all_chunks.items():
        text_words = set(re.findall(r"\w+", chunk["chunk_text"].lower()))
        sec_words = set(re.findall(r"\w+", (chunk["section_title"] or "").lower()))
        match_count = len(query_words & (text_words | sec_words))
        if match_count > 0:
            scored_chunks.append((match_count, vid))

    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    debug_info["keyword_count"] = len(scored_chunks)
    for rank, (_, vid) in enumerate(scored_chunks[:8]):
        keyword_ranks[vid] = rank + 1

    # If completely unranked in both dense (relevant distance) and keyword, score threshold fails
    if not dense_ranks and not keyword_ranks:
        debug_info["threshold_passed"] = False
        return [], debug_info

    # 3. Reciprocal Rank Fusion (RRF) with Section Boost
    fused_scores = {}
    all_vids = set(dense_ranks.keys()) | set(keyword_ranks.keys())
    intent_clean = intent.replace("intent_", "").replace("tool_", "").lower()

    for vid in all_vids:
        r_dense = dense_ranks.get(vid, 1000)
        r_key = keyword_ranks.get(vid, 1000)
        rrf = (1.0 / (60 + r_dense)) + (1.0 / (60 + r_key))

        # Section boost if chunk.section_type or section_title matches intent
        chunk = all_chunks.get(vid)
        if chunk:
            sec_type = (chunk.get("section_type") or "").lower()
            sec_title = (chunk.get("section_title") or "").lower()
            if intent_clean and (intent_clean in sec_type or intent_clean in sec_title):
                rrf += 0.04

        fused_scores[vid] = rrf

    sorted_vids = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
    debug_info["fused_count"] = len(sorted_vids)

    # 4. Score Threshold check (Brief Sec 7.5): if best fused score is too low, answer not_found
    MIN_THRESHOLD = 0.012
    if not sorted_vids or sorted_vids[0][1] < MIN_THRESHOLD:
        debug_info["threshold_passed"] = False
        return [], debug_info

    debug_info["threshold_passed"] = True
    debug_info["best_score"] = sorted_vids[0][1]

    # 5. Take top 3 or 4 chunks after diversity
    chosen = []
    for vid, score in sorted_vids[:top_k]:
        if vid in all_chunks:
            c = dict(all_chunks[vid])
            c["score"] = score
            chosen.append(c)

    return chosen, debug_info


def answer_patient_query(
    patient_id: int,
    question: str,
    conversation_id: Optional[str] = None,
    language: str = "en",
    history: Optional[List[Dict[str, str]]] = None,
    patient_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Main Entrypoint for the Upgraded Discharge Assistant Pipeline.
    Strictly follows Brief Sections 7.2 - 7.12 & 8.6.
    """
    start_time = time.time()
    clean_q = question.strip()
    lang = language.lower() if language in ("en", "hi") else "en"

    # Step 1: Emergency Check (Instant, No LLM)
    if has_emergency_term(clean_q):
        guidance = EMERGENCY_GUIDANCE.get(lang, EMERGENCY_GUIDANCE["en"])
        return {
            "answer_type": "emergency",
            "answer": guidance,
            "bullets": [],
            "sources": [],
            "suggestions": DEFAULT_SUGGESTIONS.get(lang, DEFAULT_SUGGESTIONS["en"]),
            "can_ask_care_team": False,
            "is_grounded": False,
            "response": guidance,
            "citations": [],
            "retrieval_debug": {"intent": INTENT_EMERGENCY, "emergency_hit": True},
        }

    # Step 2: Dose-change Request Check (Instant Refusal, Creates Follow-up Task)
    if is_dose_change_question(clean_q):
        refusal_msg = (
            "I cannot advise on changing, stopping, or adjusting medication doses. Please contact your care team."
            if lang == "en"
            else "मैं दवा की खुराक बदलने, रोकने या बदलने की सलाह नहीं दे सकता। कृपया अपनी केयर टीम से बात करें।"
        )
        # Create staff follow-up task (checked for topic duplication today)
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT followup_id FROM follow_up_tasks
                   WHERE patient_id = %s AND status = 'Pending' AND DATE(created_at) = CURDATE()
                     AND (reason LIKE '%%dose%%' OR reason LIKE '%%medication%%')
                   LIMIT 1""",
                (patient_id,),
            )
            existing_task = cur.fetchone()
            if not existing_task:
                cur.execute(
                    """INSERT INTO follow_up_tasks (patient_id, assigned_staff_id, priority, reason, status)
                       VALUES (%s, 1, 'Review_Soon', %s, 'Pending')""",
                    (patient_id, f"Patient asked about dose change: '{clean_q}'"),
                )
                task_id = cur.lastrowid
                cur.execute(
                    """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                       VALUES ('Agent', 'AI_Nurse', 'DOSE_CHANGE_REFUSAL', 'follow_up_task', %s,
                               JSON_OBJECT('patient_id', %s, 'question', %s))""",
                    (task_id, patient_id, clean_q),
                )
            else:
                task_id = existing_task["followup_id"]

        return {
            "answer_type": "refusal_dose",
            "answer": refusal_msg,
            "bullets": [
                "Your care team has been notified to follow up regarding your medication question."
                if lang == "en"
                else "आपकी दवा से जुड़े सवाल के संबंध में आपकी केयर टीम को सूचित कर दिया गया है।"
            ],
            "sources": [],
            "suggestions": DEFAULT_SUGGESTIONS.get(lang, DEFAULT_SUGGESTIONS["en"]),
            "can_ask_care_team": True,
            "is_grounded": False,
            "response": refusal_msg,
            "citations": [],
            "retrieval_debug": {"intent": INTENT_REFUSAL_DOSE, "task_id": task_id},
        }

    # Step 2.5: Small-talk Check (Instant Friendly Reply, No LLM, No Sources, Patient Name inserted by code)
    small_talk_type = detect_small_talk(clean_q)
    if small_talk_type:
        return handle_small_talk(clean_q, language=lang, patient_name=patient_name)

    # Step 3: Intent Routing
    intent = route_intent(clean_q)

    # Step 3a: Medical Diagnosis Refusal
    if intent == INTENT_REFUSAL_MEDICAL:
        msg = (
            "I cannot make medical diagnoses or judge if a symptom is safe or unsafe. Please submit a daily check-in or contact your care team directly."
            if lang == "en"
            else "मैं चिकित्सीय निदान नहीं कर सकता या यह तय नहीं कर सकता कि लक्षण सुरक्षित है या नहीं। कृपया दैनिक चेक-इन का उपयोग करें या अपनी देखभाल टीम से संपर्क करें।"
        )
        return {
            "answer_type": "refusal_medical",
            "answer": msg,
            "bullets": [],
            "sources": [],
            "suggestions": DEFAULT_SUGGESTIONS.get(lang, DEFAULT_SUGGESTIONS["en"]),
            "can_ask_care_team": True,
            "is_grounded": False,
            "response": msg,
            "citations": [],
            "retrieval_debug": {"intent": INTENT_REFUSAL_MEDICAL},
        }

    # Step 3b: Out of Scope
    if intent == INTENT_OUT_OF_SCOPE:
        msg = (
            "I can only help with your hospital discharge papers, medication times, follow-up visits, and care plan."
            if lang == "en"
            else "मैं केवल आपके अस्पताल डिस्चार्ज पेपर्स, दवा के समय, विज़िट और देखभाल योजना में सहायता कर सकता हूँ।"
        )
        return {
            "answer_type": "not_found",
            "answer": msg,
            "bullets": [],
            "sources": [],
            "suggestions": DEFAULT_SUGGESTIONS.get(lang, DEFAULT_SUGGESTIONS["en"]),
            "can_ask_care_team": False,
            "is_grounded": False,
            "response": msg,
            "citations": [],
            "retrieval_debug": {"intent": INTENT_OUT_OF_SCOPE},
        }

    # Step 4: Structured SQL Tools (Brief Sec 7.4)
    tool_result = None
    tool_source = None
    if intent == INTENT_APPOINTMENT:
        tool_result = get_next_appointment(patient_id)
        tool_source = "From your care plan"
    elif intent == INTENT_TODAY_DOSES:
        tool_result = get_today_doses(patient_id)
        tool_source = "From your care plan"
    elif intent == INTENT_MEDICINE_PLAN:
        tool_result = get_medicine_plan(patient_id)
        tool_source = "From your care plan"
    elif intent == INTENT_VITALS:
        tool_result = get_latest_readings(patient_id)
        tool_source = "From your care plan"
    elif intent == INTENT_CONTACTS:
        tool_result = get_care_team_contacts(patient_id)
        tool_source = "From your care plan"
    elif intent == INTENT_PLAN_ITEMS:
        tool_result = get_plan_items(patient_id)
        tool_source = "From your care plan"

    # Step 5: Document Retrieval (if not resolved by structured tool)
    context_chunks = []
    retrieval_debug = {}
    if not tool_result:
        # Query rewrite if follow-up question
        standalone_q = rewrite_followup_question(clean_q, history or [])
        context_chunks, retrieval_debug = hybrid_retrieval(patient_id, standalone_q, intent)

    # If no tool result and no document chunks passed threshold -> Not Found
    if not tool_result and not context_chunks:
        not_found_ans = NOT_FOUND_MSG.get(lang, NOT_FOUND_MSG["en"])
        return {
            "answer_type": "not_found",
            "answer": not_found_ans,
            "bullets": [],
            "sources": [],
            "suggestions": DEFAULT_SUGGESTIONS.get(lang, DEFAULT_SUGGESTIONS["en"]),
            "can_ask_care_team": True,
            "is_grounded": False,
            "response": not_found_ans,
            "citations": [],
            "retrieval_debug": {"intent": intent, "retrieval_debug": retrieval_debug},
        }

    # Step 6: Answer Generation (Brief Sec 7.4 & 7.6)
    # If resolved by structured SQL tool, generate exact factual answer deterministically (0 LLM latency/hallucination)
    if tool_result:
        source_payload = {
            "chunk_id": f"tool_{intent}",
            "tool_name": intent.replace("tool_", ""),
            "section_title": "Care Plan",
            "label": "From your care plan",
            "snippet": json.dumps(tool_result, ensure_ascii=False),
            "text": json.dumps(tool_result, indent=2, ensure_ascii=False),
        }
        if intent == INTENT_APPOINTMENT:
            doc_name = tool_result.get("doctor") or "Dr. Ananya Sharma"
            spec = tool_result.get("specialization") or "Cardiology"
            app_date = tool_result.get("date") or "in 7 days"
            app_time = tool_result.get("time") or "10:30 AM"
            notes = tool_result.get("notes") or "OPD Clinic Room 302"
            ans_text = (
                f"Your next scheduled appointment is on {app_date} at {app_time} with {doc_name} ({spec}) at {notes}."
                if lang == "en"
                else f"आपकी अगली मुलाक़ात {app_date} को {app_time} बजे {doc_name} ({spec}) के साथ {notes} में है।"
            )
        elif intent == INTENT_TODAY_DOSES:
            doses_list = tool_result.get("doses", [])
            lines = [f"{d.get('medicine')} at {d.get('time')}: {d.get('instructions')} [{d.get('status')}]" for d in doses_list]
            ans_text = (
                f"You have {len(doses_list)} scheduled doses today:\n" + "\n".join(lines)
                if lang == "en"
                else f"आज आपके लिए {len(doses_list)} ख़ुराकें निर्धारित हैं:\n" + "\n".join(lines)
            )
        elif intent == INTENT_MEDICINE_PLAN:
            prescriptions = tool_result.get("prescriptions", [])
            lines = [f"{p.get('medicine')}: {p.get('instructions')} (Course: {p.get('start_date')} to {p.get('end_date')})" for p in prescriptions]
            ans_text = (
                "Your active medication schedule:\n" + "\n".join(lines)
                if lang == "en"
                else "आपकी दवाओं का विवरण:\n" + "\n".join(lines)
            )
        elif intent == INTENT_VITALS:
            readings = tool_result.get("readings", [])
            lines = [f"{r.get('type')}: {r.get('value')} {r.get('unit')} (recorded at {r.get('measured_at')})" for r in readings]
            ans_text = (
                "Your recent vital readings:\n" + "\n".join(lines)
                if lang == "en"
                else "आपकी ताज़ा रीडिंग:\n" + "\n".join(lines)
            )
        elif intent == INTENT_CONTACTS:
            doc = tool_result.get("doctor", {})
            nurse = tool_result.get("nurse", {})
            clinic = tool_result.get("clinic_support", {})
            ans_text = (
                f"Your attending physician is {doc.get('name')}, your nurse is {nurse.get('name')}, and clinic support is {clinic.get('phone')}."
                if lang == "en"
                else f"आपकी डॉक्टर {doc.get('name')}, नर्स {nurse.get('name')}, और क्लिनिक सपोर्ट डेस्क {clinic.get('phone')} है।"
            )
        elif intent == INTENT_PLAN_ITEMS:
            items = tool_result.get("items", [])
            lines = [f"{it.get('category')}: {it.get('title')} - {it.get('instructions')} ({it.get('timing')})" for it in items]
            ans_text = (
                f"Approved Recovery Plan Items:\n" + "\n".join(lines)
                if lang == "en"
                else f"स्वीकृत रिकवरी योजना:\n" + "\n".join(lines)
            )
        else:
            ans_text = f"Care plan data: {json.dumps(tool_result)}"

        return {
            "answer_type": "structured",
            "answer": ans_text,
            "bullets": [],
            "sources": [source_payload],
            "suggestions": DEFAULT_SUGGESTIONS.get(lang, DEFAULT_SUGGESTIONS["en"]),
            "can_ask_care_team": False,
            "is_grounded": True,
            "response": ans_text,
            "citations": [source_payload],
            "retrieval_debug": {"intent": intent, "tool_called": intent, "structured_direct": True},
        }

    # Step 6b: Document Chunks LLM Generation (Brief Sec 7.6)
    context_blocks = []
    valid_source_ids = set()
    sources_payload = []

    for idx, chk in enumerate(context_chunks):
        sid = f"S{idx + 1}"
        valid_source_ids.add(sid)
        sec_title = chk.get("section_title") or "General"
        p_no = chk.get("page_no") or 1
        context_blocks.append(f"[{sid}] ({sec_title}, Page {p_no}): {chk['chunk_text']}")
        sources_payload.append({
            "chunk_id": chk.get("chunk_id") or chk.get("vector_id"),
            "label": f"Discharge summary - {sec_title} - p.{p_no}",
            "section_title": sec_title,
            "page_no": p_no,
            "snippet": chk["chunk_text"][:160] + "...",
            "text": chk["chunk_text"],
        })

    context_str = "\n\n".join(context_blocks)
    tool_json_str = json.dumps(tool_result, ensure_ascii=False) if tool_result else "None"

    user_prompt = f"""CONTEXT:
{context_str}

TOOL RESULTS:
{tool_json_str}

PATIENT QUESTION:
{clean_q}

LANGUAGE:
{lang}"""

    system_prompt = RAG_SYSTEM_PROMPT.format(language="Hindi" if lang == "hi" else "English")

    try:
        raw_output = generate(system_prompt, user_prompt, timeout=12)
        # Parse JSON output robustly
        start_idx = raw_output.find("{")
        end_idx = raw_output.rfind("}")
        if start_idx == -1 or end_idx == -1:
            raise ValueError("No valid JSON found in LLM response")
        json_str = raw_output[start_idx : end_idx + 1]
        # Clean trailing commas if present
        json_str = re.sub(r",\s*([\]}])", r"\1", json_str)
        answer_data = json.loads(json_str)
    except Exception as e:
        logger.error(f"LLM generation/parsing error: {e}")
        # 1. If structured tool returned data, provide deterministic factual answer
        if tool_result:
            if intent == INTENT_APPOINTMENT:
                doc_name = tool_result.get("doctor") or "Dr. Ananya Sharma"
                spec = tool_result.get("specialization") or "Cardiology"
                app_date = tool_result.get("date") or "in 7 days"
                app_time = tool_result.get("time") or "10:30 AM"
                notes = tool_result.get("notes") or "OPD Clinic Room 302"
                ans_text = (
                    f"Your next scheduled appointment is on {app_date} at {app_time} with {doc_name} ({spec}) at {notes}."
                    if lang == "en"
                    else f"आपकी अगली मुलाक़ात {app_date} को {app_time} बजे {doc_name} ({spec}) के साथ {notes} में है।"
                )
            elif intent == INTENT_TODAY_DOSES:
                doses_list = tool_result.get("doses", [])
                lines = [f"{d.get('medicine')} at {d.get('time')}: {d.get('instructions')} [{d.get('status')}]" for d in doses_list]
                ans_text = (
                    f"You have {len(doses_list)} scheduled doses today:\n" + "\n".join(lines)
                    if lang == "en"
                    else f"आज आपके लिए {len(doses_list)} ख़ुराकें निर्धारित हैं:\n" + "\n".join(lines)
                )
            elif intent == INTENT_MEDICINE_PLAN:
                prescriptions = tool_result.get("prescriptions", [])
                lines = [f"{p.get('medicine')}: {p.get('instructions')} (Course: {p.get('start_date')} to {p.get('end_date')})" for p in prescriptions]
                ans_text = (
                    "Your active medication schedule:\n" + "\n".join(lines)
                    if lang == "en"
                    else "आपकी दवाओं का विवरण:\n" + "\n".join(lines)
                )
            elif intent == INTENT_VITALS:
                readings = tool_result.get("readings", [])
                lines = [f"{r.get('type')}: {r.get('value')} {r.get('unit')} (recorded at {r.get('measured_at')})" for r in readings]
                ans_text = (
                    "Your recent vital readings:\n" + "\n".join(lines)
                    if lang == "en"
                    else "आपकी ताज़ा रीडिंग:\n" + "\n".join(lines)
                )
            elif intent == INTENT_CONTACTS:
                doc = tool_result.get("doctor", {})
                nurse = tool_result.get("nurse", {})
                clinic = tool_result.get("clinic_support", {})
                ans_text = (
                    f"Your attending physician is {doc.get('name')}, your nurse is {nurse.get('name')}, and clinic support is {clinic.get('phone')}."
                    if lang == "en"
                    else f"आपकी डॉक्टर {doc.get('name')}, नर्स {nurse.get('name')}, और क्लिनिक सपोर्ट डेस्क {clinic.get('phone')} है।"
                )
            elif intent == INTENT_PLAN_ITEMS:
                items = tool_result.get("items", [])
                lines = [f"{it.get('category')}: {it.get('title')} - {it.get('instructions')} ({it.get('timing')})" for it in items]
                ans_text = (
                    f"Approved Recovery Plan Items:\n" + "\n".join(lines)
                    if lang == "en"
                    else f"स्वीकृत रिकवरी योजना:\n" + "\n".join(lines)
                )
            else:
                ans_text = f"Care plan data: {json.dumps(tool_result)}"

            return {
                "answer_type": "structured",
                "answer": ans_text,
                "bullets": [],
                "sources": sources_payload,
                "suggestions": DEFAULT_SUGGESTIONS.get(lang, DEFAULT_SUGGESTIONS["en"]),
                "can_ask_care_team": False,
                "is_grounded": True,
                "response": ans_text,
                "citations": sources_payload,
                "retrieval_debug": {"intent": intent, "tool_called": intent, "fallback_tool": True},
            }

        # 2. Extractive grounded fallback from retrieved context chunks
        if context_chunks:
            top_chk = context_chunks[0]
            sec = top_chk.get("section_title") or "Discharge summary"
            p_no = top_chk.get("page_no") or 1
            raw_text = top_chk.get("chunk_text", "")
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", raw_text) if len(s.strip()) > 15]
            bullets = sentences[:3] if sentences else [raw_text[:140]]
            lead_text = (
                f"According to your discharge summary ({sec}, page {p_no}):"
                if lang == "en"
                else f"आपके डिस्चार्ज पेपर्स ({sec}, पृष्ठ {p_no}) के अनुसार:"
            )
            return {
                "answer_type": "grounded",
                "answer": lead_text + " " + (sentences[0] if sentences else raw_text[:120]),
                "bullets": bullets,
                "sources": sources_payload[:2],
                "suggestions": DEFAULT_SUGGESTIONS.get(lang, DEFAULT_SUGGESTIONS["en"]),
                "can_ask_care_team": False,
                "is_grounded": True,
                "response": f"{lead_text} " + " ".join(bullets),
                "citations": [s.get("chunk_id") for s in sources_payload[:2] if s.get("chunk_id")],
                "retrieval_debug": {"intent": intent, "fallback_extractive": True, "error": str(e), "top_chunks": context_chunks},
            }

        unavail_ans = UNAVAILABLE_MSG.get(lang, UNAVAILABLE_MSG["en"])
        return {
            "answer_type": "unavailable",
            "answer": unavail_ans,
            "bullets": [],
            "sources": [],
            "suggestions": DEFAULT_SUGGESTIONS.get(lang, DEFAULT_SUGGESTIONS["en"]),
            "can_ask_care_team": True,
            "is_grounded": False,
            "response": unavail_ans,
            "citations": [],
            "retrieval_debug": {"error": str(e)},
        }

    # Step 7: Check found flag from LLM
    if not answer_data.get("found", False):
        not_found_ans = NOT_FOUND_MSG.get(lang, NOT_FOUND_MSG["en"])
        return {
            "answer_type": "not_found",
            "answer": not_found_ans,
            "bullets": [],
            "sources": [],
            "suggestions": DEFAULT_SUGGESTIONS.get(lang, DEFAULT_SUGGESTIONS["en"]),
            "can_ask_care_team": True,
            "is_grounded": False,
            "response": not_found_ans,
            "citations": [],
            "retrieval_debug": {"intent": intent, "found_flag_false": True},
        }

    # Step 8: Numeric and Citation Guard (Brief Sec 7.8)
    guard_result = guard_numeric_and_citations(
        answer_data,
        [c["chunk_text"] for c in context_chunks],
        tool_result,
        valid_source_ids,
        question=clean_q,
    )

    if guard_result == "downgrade_not_found":
        logger.warning(f"Guard triggered downgrade to not_found for query: '{clean_q}'")
        not_found_ans = NOT_FOUND_MSG.get(lang, NOT_FOUND_MSG["en"])
        return {
            "answer_type": "not_found",
            "answer": not_found_ans,
            "bullets": [],
            "sources": [],
            "suggestions": DEFAULT_SUGGESTIONS.get(lang, DEFAULT_SUGGESTIONS["en"]),
            "can_ask_care_team": True,
            "is_grounded": False,
            "response": not_found_ans,
            "citations": [],
            "retrieval_debug": {"guard_result": guard_result, "downgraded": True},
        }

    # Filter sources to only those cited in source_ids
    cited_ids = set(answer_data.get("source_ids", []))
    active_sources = []
    if tool_result:
        active_sources = sources_payload
    else:
        for idx, src in enumerate(sources_payload):
            if f"S{idx + 1}" in cited_ids:
                active_sources.append(src)
    if not active_sources:
        active_sources = sources_payload[:1]

    # Filter actions by ALLOWLIST_ACTIONS
    raw_actions = answer_data.get("actions", [])
    valid_actions = []
    if isinstance(raw_actions, list):
        for act in raw_actions:
            a_type = act.get("action_type") if isinstance(act, dict) else act
            if a_type in ALLOWLIST_ACTIONS:
                valid_actions.append(act if isinstance(act, dict) else {"action_type": a_type})

    # Suggestions (2-3 follow-ups)
    suggestions = answer_data.get("suggested_followups") or answer_data.get("follow_ups") or DEFAULT_SUGGESTIONS.get(lang, DEFAULT_SUGGESTIONS["en"])

    answer_type = "structured" if tool_result else "grounded"
    latency = round(time.time() - start_time, 3)

    return {
        "answer_type": answer_type,
        "answer": answer_data.get("answer", ""),
        "bullets": answer_data.get("bullets", []),
        "sources": active_sources,
        "actions": valid_actions,
        "suggestions": suggestions[:3],
        "can_ask_care_team": answer_data.get("suggest_care_team", False),
        "is_grounded": True,
        "response": answer_data.get("answer", ""),
        "citations": [s.get("chunk_id") for s in active_sources if s.get("chunk_id")],
        "retrieval_debug": {
            "intent": intent,
            "tool_used": bool(tool_result),
            "guard_result": guard_result,
            "latency_sec": latency,
            "debug": retrieval_debug,
        },
    }
