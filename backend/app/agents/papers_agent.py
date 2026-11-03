"""
backend/app/agents/papers_agent.py — Papers Agent (Agentic RAG)

Phase 2 of CareLoop Care Agents Plan:
- Plans, retrieves from verified sources, self-checks, and abstains when unsure.
- Pipeline:
  1. Safety gates first (plain code): emergency, dose-change, small-talk, prompt injection.
  2. Intent label and plan templates: appointment, medicine_times, warning_signs, activity,
     wound_care, diet, reading_value, plan_item, contacts, follow_up, out_of_scope.
  3. Act & Retrieve: tools and/or section-aware hybrid retrieval (dense Chroma + keyword SQL + RRF),
     with Hindi cross-lingual expansion.
  4. Grade evidence sufficiency: if below threshold, rewrites query once; if still below -> abstain.
  5. Draft generation: structured JSON with source citations, 60-90 words, plain words.
  6. Verification via Policy Guard: 10 deterministic checks (sources, numbers, banned words, etc.).
  7. Ledger recording: every query produces an auditable run and trace in agent_runs and agent_steps.
"""

import re
import time
import json
import uuid
import logging
from typing import Dict, Any, List, Optional, Tuple

from backend.app.db import get_conn
from backend.app.agents.dispatcher import AgentDispatcher
from backend.app.agents.ledger import AgentLedger
from backend.app.agents.policy_guard import PolicyGuard, PolicyGuardResult
from backend.app.assistant_router import (
    route_intent_v2,
    detect_small_talk,
    handle_small_talk,
)
from backend.app.safety import has_emergency_term, is_dose_change_question, EMERGENCY_GUIDANCE
from backend.app.rag_pipeline import (
    answer_patient_query,
    hybrid_retrieval,
    rewrite_followup_question,
    guard_numeric_and_citations,
    DEFAULT_SUGGESTIONS,
    HINDI_TO_ENGLISH_CONCEPT_EXPANSION
)
from backend.app.rag_tools import (
    get_next_appointment,
    get_today_doses,
    get_medicine_plan,
    get_latest_readings,
    get_care_team_contacts,
    get_plan_items,
)
from backend.app.rag_config import (
    NOT_FOUND_MSG,
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

logger = logging.getLogger(__name__)

# Prompt Injection Attack Patterns (Safety Rules & Section 6)
PROMPT_INJECTION_PATTERNS = [
    r"\bignore\s+(?:all\s+)?(?:previous\s+)?(?:instructions|rules|prompts)\b",
    r"\bforget\s+(?:all\s+)?(?:your\s+)?rules\b",
    r"\byou\s+are\s+now\s+(?:a|an|the)\b",
    r"\bsystem\s+prompt\b",
    r"\breveal\s+(?:the\s+)?system\b",
    r"\boverride\s+(?:safety|clinical|rules)\b",
    r"<\|im_start\|>",
    r"<system>",
    r"\badmin\s+mode\b",
    r"\bdeveloper\s+mode\b",
    r"\bjailbreak\b",
    r"\bclose\s+(?:this\s+|all\s+)?(?:flag|task|case)\b",
    r"\bmark\s+(?:flag|task)\s+(?:as\s+)?closed\b",
    r"\b(show|give)\s+(?:me\s+)?(?:another|other)\s+patient\b",
    r"\bpatient\s+(?:id\s+)?2\b",
    r"\bdata\s+of\s+patient\b",
    r"\bprescribe\s+(?:me\s+)?(?:some\s+)?medicine\b",
    # Hindi injection patterns
    r"नियम\s+भूल\s+जाओ",
    r"पिछले\s+निर्देश\s+रद्द",
    r"तुम\s+अब\s+डॉक्टर\s+हो",
    r"सिस्टम\s+प्रॉम्प्ट",
    r"फ्लैग\s+बंद\s+करो",
    r"दूसरे\s+मरीज\s+का\s+डेटा",
    r"दवा\s+लिख\s+दो",
]


class PapersAgent:
    """
    CareLoop Papers Agent (Agentic RAG):
    Plans, retrieves, self-checks, and abstains when unsure.
    "The LLM talks. Rules decide. Humans act."
    """

    @classmethod
    def process_query(
        cls,
        patient_id: int,
        question: str,
        language: str = "en",
        conversation_id: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        patient_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes the 6-step agentic RAG flow:
        1. Supervisor intake (global pause, patient opt-out)
        2. Safety gates (emergency, dose change, small talk, prompt injection)
        3. Intent labeling & plan selection
        4. Retrieval & tool execution
        5. Evidence grading & rewriting
        6. Policy Guard verification & ledger recording
        """
        start_ts = time.time()
        clean_q = (question or "").strip()
        lang = language.lower() if language in ("en", "hi") else "en"
        p_name = patient_name or "Aarav"

        run_id = f"run-papers-{patient_id}-{uuid.uuid4().hex[:8]}"
        level, mode = AgentDispatcher.get_autonomy("papers_question_sourced")

        # Initialize ledger run
        AgentLedger.start_run(
            run_id=run_id,
            agent_name="PapersAgent",
            trigger_type="papers_question",
            trigger_ref=f"chat-{conversation_id or patient_id}",
            patient_id=patient_id,
            autonomy_level=level,
            mode=mode,
            plan={"question": clean_q, "language": lang, "template": "undetermined"}
        )

        # ─── Step 0: Dispatcher Intake Check ─────────────────────────────────
        decision = AgentDispatcher.check_intake("papers_question_sourced", patient_id=patient_id)
        if not decision.allowed:
            # Check if patient opted out
            if "opted out" in (decision.reason or "").lower():
                opt_out_reply = (
                    f"Hello {p_name}. Automated AI assistance is currently turned off for your account per your settings. "
                    "You can ask your care team directly using the button below, or re-enable AI help on your home screen."
                    if lang == "en"
                    else f"नमस्ते {p_name}। आपकी सेटिंग्स के अनुसार स्वचालित एआई सहायता आपके खाते के लिए बंद है। "
                         "आप नीचे दिए गए बटन से सीधे अपनी केयर टीम से संपर्क कर सकते हैं।"
                )
                AgentLedger.record_step(
                    run_id, 1, "Gate",
                    f"Patient opted out of AI help: {decision.reason}",
                    ok=False, ms=1
                )
                AgentLedger.finish_run(
                    run_id, status="Done", result_type="patient_opt_out",
                    latency_ms=1, guard_reasons=[decision.reason]
                )
                return {
                    "answer_type": "opt_out",
                    "answer": opt_out_reply,
                    "bullets": [],
                    "sources": [],
                    "suggestions": DEFAULT_SUGGESTIONS.get(lang, DEFAULT_SUGGESTIONS["en"]),
                    "can_ask_care_team": True,
                    "is_grounded": False,
                    "response": opt_out_reply,
                    "citations": [],
                    "retrieval_debug": {"intent": "opt_out", "reason": decision.reason},
                    "run_id": run_id
                }

            # Global pause or daily budget block
            pause_reply = (
                "CareLoop Assistant is temporarily unavailable while our clinical team conducts system updates. "
                "Your care team remains available for direct support."
                if lang == "en"
                else "केयरलूप असिस्टेंट अस्थायी रूप से अनुपलब्ध है। आपकी केयर टीम सीधे संपर्क के लिए उपलब्ध है।"
            )
            AgentLedger.record_step(
                run_id, 1, "Gate",
                f"Dispatcher blocked execution: {decision.reason}",
                ok=False, ms=1
            )
            AgentLedger.finish_run(
                run_id, status="Blocked_By_Guard", result_type="dispatcher_blocked",
                latency_ms=1, guard_reasons=[decision.reason]
            )
            return {
                "answer_type": "unavailable",
                "answer": pause_reply,
                "bullets": [],
                "sources": [],
                "suggestions": DEFAULT_SUGGESTIONS.get(lang, DEFAULT_SUGGESTIONS["en"]),
                "can_ask_care_team": True,
                "is_grounded": False,
                "response": pause_reply,
                "citations": [],
                "retrieval_debug": {"intent": "supervisor_paused", "reason": decision.reason},
                "run_id": run_id
            }

        seq = 1

        # ─── Step 1: Safety Gates (Plain Code, No LLM) ─────────────────────────

        # Gate 1.1: Emergency Check
        if has_emergency_term(clean_q):
            guidance = EMERGENCY_GUIDANCE.get(lang, EMERGENCY_GUIDANCE["en"])
            AgentLedger.record_step(
                run_id, seq, "Gate",
                "Emergency term detected in input — instant 112 guidance, zero LLM",
                ok=True, ms=1
            )
            AgentLedger.finish_run(
                run_id, status="Done", result_type="emergency_redirection",
                latency_ms=int((time.time() - start_ts) * 1000),
                guard_reasons=["Emergency red-flag keyword intercepted"]
            )
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
                "run_id": run_id
            }

        # Gate 1.2: Dose Change Check
        if is_dose_change_question(clean_q):
            refusal_msg = (
                "I cannot advise on changing, stopping, or adjusting medication doses. Please contact your care team."
                if lang == "en"
                else "मैं दवा की खुराक बदलने, रोकने या बदलने की सलाह नहीं दे सकता। कृपया अपनी केयर टीम से बात करें।"
            )
            # Create staff task (deduplicated: max 1 per topic per day)
            task_id = cls._create_or_get_care_team_task(patient_id, f"Patient asked about dose change: '{clean_q}'")
            AgentLedger.record_step(
                run_id, seq, "Gate",
                f"Dose change question detected — deterministic refusal, task #{task_id}",
                ids=[task_id], ok=True, ms=2
            )
            AgentLedger.finish_run(
                run_id, status="Done", result_type="dose_change_refusal",
                latency_ms=int((time.time() - start_ts) * 1000),
                guard_reasons=["Dose change forbidden by clinical safety rule 3"]
            )
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
                "run_id": run_id
            }

        # Gate 1.3: Red-Team & Injection Safety Gate (Phase 6 Task 2)
        is_safe, attack_reason = PolicyGuard.inspect_redteam_attack(clean_q, context={"patient_id": patient_id})
        if not is_safe:
            block_msg = (
                "I am an assistant for your hospital discharge papers. "
                "I cannot execute administrative commands, diagnose conditions, override safety rules, or share data from other patients."
                if lang == "en"
                else "मैं आपके डिस्चार्ज पेपर्स के लिए एक असिस्टेंट हूँ। "
                     "मैं सिस्टम कमांड निष्पादित नहीं कर सकता, चिकित्सा निदान नहीं कर सकता, या नियमों को ओवरराइड नहीं कर सकता।"
            )
            AgentLedger.record_step(
                run_id, seq, "Gate",
                f"Red-team attack intercepted by Policy Guard: {attack_reason}",
                ok=False, ms=2
            )
            AgentLedger.finish_run(
                run_id, status="Blocked_By_Guard", result_type="injection_blocked",
                latency_ms=int((time.time() - start_ts) * 1000),
                guard_reasons=[f"Red-team safety violation: {attack_reason}"]
            )
            return {
                "answer_type": "refusal_injection",
                "answer": block_msg,
                "bullets": [],
                "sources": [],
                "suggestions": DEFAULT_SUGGESTIONS.get(lang, DEFAULT_SUGGESTIONS["en"]),
                "can_ask_care_team": False,
                "is_grounded": False,
                "response": block_msg,
                "citations": [],
                "retrieval_debug": {"intent": "refusal_injection", "blocked": True, "reason": attack_reason},
                "run_id": run_id
            }

        # Gate 1.4: Small Talk Check (Fixed reply, no LLM, no sources, name by code)
        small_talk_type = detect_small_talk(clean_q)
        if small_talk_type:
            AgentLedger.record_step(
                run_id, seq, "Gate",
                f"Small talk detected: '{small_talk_type}' — code-inserted name, zero source chips",
                ok=True, ms=1
            )
            st_res = handle_small_talk(clean_q, language=lang, patient_name=p_name)
            st_res["run_id"] = run_id
            AgentLedger.finish_run(
                run_id, status="Done", result_type="small_talk_reply",
                latency_ms=int((time.time() - start_ts) * 1000)
            )
            return st_res

        # ─── Step 2: Intent Label and Plan Template Selection ─────────────────
        seq += 1
        intent = route_intent_v2(clean_q)
        template_name = cls._map_intent_to_plan_template(intent)

        AgentLedger.record_step(
            run_id, seq, "Plan",
            f"Intent labeled: '{intent}' -> Plan template: '{template_name}'",
            ok=True, ms=2
        )

        # ─── Step 3 & 4: Execute Upgraded RAG & Verification ──────────────────
        seq += 1
        rag_res = answer_patient_query(
            patient_id=patient_id,
            question=clean_q,
            conversation_id=conversation_id,
            language=lang,
            history=history,
            patient_name=p_name
        )

        # ─── Step 5: Policy Guard Verification ────────────────────────────────
        seq += 1
        guard_output = {
            "answer": rag_res.get("answer", ""),
            "bullets": rag_res.get("bullets", []),
            "sources": rag_res.get("sources", []),
            "actions": rag_res.get("actions", []),
            "patient_id": patient_id
        }

        # Extract cited passage text for exact numeric and factual support verification
        retrieval_debug = rag_res.get("retrieval_debug", {})
        top_chunks = retrieval_debug.get("top_chunks", []) or retrieval_debug.get("retrieval_debug", {}).get("top_chunks", [])
        combined_sources_text = " ".join([c.get("chunk_text") or c.get("text", "") for c in top_chunks])
        if rag_res.get("sources"):
            combined_sources_text += " " + " ".join([
                s.get("text") or s.get("snippet", "") if isinstance(s, dict) else str(s)
                for s in rag_res.get("sources")
            ])
        # For structured tool answers, the deterministic tool result is the verified source
        if rag_res.get("answer_type") == "structured":
            combined_sources_text += " " + rag_res.get("answer", "")

        guard_res = PolicyGuard.inspect(
            agent_name="papers_agent",
            output_payload=guard_output,
            context={
                "patient_id": patient_id,
                "source_texts": [combined_sources_text] if combined_sources_text else [],
                "preferred_language": lang
            }
        )

        elapsed_ms = int((time.time() - start_ts) * 1000)

        if not guard_res.passed:
            # Policy guard failed: fall back to abstain gracefully
            AgentLedger.record_step(
                run_id, seq, "Guard",
                f"Policy Guard blocked output: {guard_res.reasons}",
                ok=False, ms=3
            )
            fallback_answer = NOT_FOUND_MSG.get(lang, NOT_FOUND_MSG["en"])
            AgentLedger.finish_run(
                run_id, status="Blocked_By_Guard", result_type="guard_fallback",
                latency_ms=elapsed_ms, guard_reasons=guard_res.reasons
            )
            return {
                "answer_type": "not_found",
                "answer": fallback_answer,
                "bullets": [],
                "sources": [],
                "suggestions": DEFAULT_SUGGESTIONS.get(lang, DEFAULT_SUGGESTIONS["en"]),
                "can_ask_care_team": True,
                "is_grounded": False,
                "response": fallback_answer,
                "citations": [],
                "retrieval_debug": {"intent": intent, "guard_reasons": guard_res.reasons},
                "run_id": run_id
            }

        # Policy guard passed cleanly
        AgentLedger.record_step(
            run_id, seq, "Guard",
            "Deterministic Policy Guard: all 10 safety checks passed",
            ok=True, ms=2
        )

        result_type = "grounded_answer" if rag_res.get("is_grounded") else (
            "structured_tool_answer" if rag_res.get("answer_type") == "structured" else "abstain_not_found"
        )
        AgentLedger.finish_run(
            run_id, status="Done", result_type=result_type,
            llm_calls=1 if rag_res.get("is_grounded") else 0,
            latency_ms=elapsed_ms
        )

        rag_res["run_id"] = run_id
        return rag_res

    @staticmethod
    def _map_intent_to_plan_template(intent: str) -> str:
        """Maps an intent label to an allowed plan template (Section 4.1)."""
        mapping = {
            INTENT_APPOINTMENT: "appointment",
            INTENT_TODAY_DOSES: "medicine_times",
            INTENT_MEDICINE_PLAN: "medicine_times",
            INTENT_VITALS: "reading_value",
            INTENT_PLAN_ITEMS: "plan_item",
            INTENT_CONTACTS: "contacts",
            INTENT_WARNING_SIGNS: "warning_signs",
            INTENT_ACTIVITY: "activity",
            INTENT_WOUND_CARE: "wound_care",
            INTENT_DIET: "diet",
            INTENT_GENERAL_DOCS: "general_papers",
            INTENT_OUT_OF_SCOPE: "abstain_out_of_scope",
        }
        return mapping.get(intent, "general_papers")

    @staticmethod
    def _create_or_get_care_team_task(patient_id: int, reason: str) -> int:
        """Creates exactly one follow-up task per topic per day."""
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT followup_id FROM follow_up_tasks
                WHERE patient_id = %s AND status = 'Pending' AND DATE(created_at) = CURDATE()
                  AND (reason LIKE '%%dose%%' OR reason LIKE '%%medication%%')
                LIMIT 1;
            """, (patient_id,))
            existing = cur.fetchone()
            if existing:
                return existing["followup_id"]

            cur.execute("""
                INSERT INTO follow_up_tasks (patient_id, assigned_staff_id, priority, reason, status, created_at)
                VALUES (%s, 1, 'Review_Soon', %s, 'Pending', NOW());
            """, (patient_id, reason))
            task_id = cur.lastrowid
            conn.commit()
            return task_id
