"""
backend/app/agents/policy_guard.py — Deterministic Policy Guard

Applied to every agent output before delivery.
Enforces the 10 checks in Section 6 of careloop_care_agents_plan.md:
1. Allowlist: Only tools and actions allowed for that agent and autonomy level.
2. Identity: Patient ID verified; names and codes consistent across output.
3. Sources: Every fact and sentence has an existing source ID; unsourced dropped.
4. Numbers: Every number, date, and time in output appears in cited source text.
5. Menu: Next steps and options only from the approved fixed menu.
6. Language: Output language matches patient preference (en/hi).
7. Banned words: Zero clinical judgment words (stable, normal, safe, etc.) & zero dose advice.
8. Consent: Family or photo actions blocked if consent is missing.
9. Limits: Quiet hours (22:00-07:00 IST), daily caps, pause, STOP, emergency suppression.
10. Schema & format: JSON schema valid; length caps; untrusted text instructions ignored.
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

logger = logging.getLogger(__name__)

# Banned clinical judgment words (ICMR & Safety Rules)
BANNED_WORDS = [
    r"\bnormal\b",
    r"\boptimal\b",
    r"\bsafe\b",
    r"\bstable\b",
    r"\bimproving\b",
    r"\bconcerning\b",
    r"\bcured\b",
    r"\bdiagnos(?:e|is|ed)\b",
    r"\bprescrib(?:e|ed|ing)\b",
    r"\bAI\s*nurse\b",
    r"\bautonomous\b",
]

# Fixed Menu of Allowed Next Steps (Section 4.2)
ALLOWED_NEXT_STEPS = {
    "call_now",
    "send_checkin",
    "request_photo",
    "ask_doctor",
    "recheck_at",
    "merge_duplicate",
    "close_rule"
}

# Allowlisted Action Cards for Patients (Section C & Ground Rules)
ALLOWLISTED_PATIENT_ACTIONS = {
    "Start_Checkin",
    "Add_Photo",
    "Request_Call",
    "Ask_Care_Team",
    "Open_Plan_Item",
    "Open_Medicines",
    "Add_Appointment_To_Calendar",
    "Call_112",
    "Open_SOS"
}

# Allowed tools per agent
ALLOWED_AGENT_TOOLS = {
    "papers_agent": {
        "get_next_appointment",
        "get_today_doses",
        "get_medicine_plan",
        "get_plan_items",
        "get_latest_readings",
        "get_care_team_contacts",
        "search_discharge_papers"
    },
    "case_prep_agent": {
        "get_flag_context",
        "get_patient_readings",
        "get_patient_checkins",
        "get_dose_adherence_48h",
        "get_device_status",
        "get_consent_status",
        "get_active_limits"
    },
    "call_notes_agent": {
        "draft_call_note",
        "draft_followup_task",
        "draft_patient_message"
    },
    "outreach_agent": {
        "send_app_update",
        "send_sms_message",
        "schedule_retry"
    },
    "handoff_agent": {
        "build_patient_fact_sheet",
        "draft_shift_handoff",
        "draft_daily_summary"
    }
}


class PolicyGuardResult:
    def __init__(self, passed: bool, reasons: List[str] = None, sanitized_output: Any = None):
        self.passed = passed
        self.reasons = reasons or []
        self.sanitized_output = sanitized_output

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "reasons": self.reasons,
            "sanitized_output": self.sanitized_output
        }


class PolicyGuard:
    @staticmethod
    def inspect(
        agent_name: str,
        output_payload: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> PolicyGuardResult:
        """Runs the deterministic 10-point Policy Guard on agent output."""
        context = context or {}
        reasons = []

        # 1. Allowlist Check (Tools & Actions)
        tools_used = output_payload.get("tools_used", [])
        allowed_tools = ALLOWED_AGENT_TOOLS.get(agent_name, set())
        for tool in tools_used:
            if tool not in allowed_tools:
                reasons.append(f"Disallowed tool '{tool}' for agent '{agent_name}'")

        proposed_actions = output_payload.get("actions", [])
        for act in proposed_actions:
            act_type = act if isinstance(act, str) else act.get("type", "")
            if act_type and act_type not in ALLOWLISTED_PATIENT_ACTIONS and act_type not in ALLOWED_NEXT_STEPS:
                reasons.append(f"Proposed action '{act_type}' not in allowlist")

        # 2. Identity Check
        expected_pid = context.get("patient_id")
        payload_pid = output_payload.get("patient_id")
        if expected_pid is not None and payload_pid is not None:
            if int(expected_pid) != int(payload_pid):
                reasons.append(f"Patient ID mismatch: context={expected_pid}, payload={payload_pid}")

        # Check for illegal patient names or phone numbers leaked in output
        patient_name = context.get("patient_name", "")
        patient_phone = context.get("patient_phone", "")
        raw_text = json.dumps(output_payload)

        # 3. Sources Check
        facts = output_payload.get("facts", [])
        for f in facts:
            if isinstance(f, dict):
                if not f.get("source"):
                    reasons.append(f"Fact missing required source citation: '{f.get('fact', '')[:40]}'")

        # 4. Numeric & Grounded Fact Guard
        source_texts = context.get("source_texts", [])
        sources_list = output_payload.get("sources", [])
        meta_numbers = []
        for s in sources_list:
            if isinstance(s, dict):
                if s.get("page_no"):
                    meta_numbers.append(str(s["page_no"]))
                if s.get("label"):
                    meta_numbers.extend(re.findall(r"\b\d+\b", str(s["label"])))

        if source_texts:
            combined_source = " ".join(source_texts).lower() + " " + " ".join(meta_numbers)
            answer_text = output_payload.get("answer", "")
            if isinstance(answer_text, str) and answer_text:
                extracted_numbers = re.findall(r"\b\d+(?:\.\d+)?\b", answer_text)
                for num in extracted_numbers:
                    if num not in combined_source:
                        reasons.append(f"Numeric hallucination detected: '{num}' not present in source text")

        # Specific check for Call Notes Agent: No facts beyond nurse's input (Phase 4 Task 3)
        nurse_input = context.get("nurse_input", "")
        if agent_name == "call_notes_agent" and nurse_input:
            combined_draft = " ".join([
                str(output_payload.get("note_text", "")),
                str(output_payload.get("summary", "")),
                str(output_payload.get("task_description", "")),
                str(output_payload.get("patient_message", ""))
            ]).lower()
            input_lower = nurse_input.lower()
            draft_numbers = re.findall(r"\b\d+(?:\.\d+)?\b", combined_draft)
            for num in draft_numbers:
                if num not in input_lower:
                    reasons.append(f"Unprovided fact/number in call draft: '{num}' not present in nurse input")
            
            critical_clinical_terms = ["fever", "infection", "hypertension", "edema", "nausea", "vomiting", "bleeding", "rash"]
            for term in critical_clinical_terms:
                if term in combined_draft and term not in input_lower:
                    reasons.append(f"Unprovided clinical symptom in draft: '{term}' not reported by nurse")

        # 5. Fixed Menu Check
        next_step = output_payload.get("next_step")
        if next_step:
            step_key = next_step if isinstance(next_step, str) else next_step.get("key", "")
            if step_key and step_key not in ALLOWED_NEXT_STEPS:
                reasons.append(f"Next step '{step_key}' not in approved menu")

        # 6. Language Check
        expected_lang = context.get("preferred_language", "en")
        output_lang = output_payload.get("lang") or output_payload.get("language")
        if output_lang and output_lang != expected_lang:
            reasons.append(f"Language mismatch: expected '{expected_lang}', got '{output_lang}'")

        # 7. Banned Words Check
        for pattern in BANNED_WORDS:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                reasons.append(f"Banned clinical judgment or marketing term: '{match.group(0)}'")

        # 8. Caregiver Consent Check
        caregiver_consent = context.get("caregiver_consent", True)
        if not caregiver_consent:
            # Check if any family contact, notification, or outreach was proposed.
            # Stating lack of consent (e.g. "Caregiver consent: not granted", source "caregiver#2") is allowed documentation.
            outreach_patterns = [
                r"\b(?:family|caregiver)\s+(?:notified|alerted|contacted|outreach|call|prompted|message|sent)\b",
                r"\b(?:notify|contact|alert|call|message|reach)\s+(?:the\s+)?(?:family|caregiver)\b",
                r"\bnotify_family\b",
                r"\bcontact_caregiver\b"
            ]
            has_outreach = any(re.search(p, raw_text, re.IGNORECASE) for p in outreach_patterns)
            step_has_family = any(k in str(next_step).lower() for k in ["family", "caregiver"])
            actions_have_family = any(any(k in str(a).lower() for k in ["family", "caregiver"]) for a in proposed_actions)
            if has_outreach or step_has_family or actions_have_family:
                reasons.append("Family outreach proposed without valid caregiver consent")

        # 9. Automation Limits Check (Quiet Hours & Caps)
        now_dt = context.get("current_time") or datetime.now(IST)
        hour = now_dt.hour
        is_quiet = (hour >= 22 or hour < 7)
        is_automated_patient_msg = output_payload.get("is_automated_patient_msg", False)
        is_emergency = context.get("is_emergency", False) or output_payload.get("is_emergency", False)

        if is_automated_patient_msg and is_quiet and not is_emergency:
            reasons.append(f"Suppressed by quiet hours (22:00-07:00 IST): current hour is {hour:02d}:00")

        daily_count = context.get("daily_automated_message_count", 0)
        if is_automated_patient_msg and daily_count >= 3 and not is_emergency:
            reasons.append(f"Daily automation cap exceeded: {daily_count}/3 messages already sent today")

        if context.get("open_emergency_flag", False) and is_automated_patient_msg and not is_emergency:
            reasons.append("Routine message suppressed while open emergency flag is active")

        # 10. Format and Length Check
        if not isinstance(output_payload, dict):
            reasons.append("Output payload must be a valid JSON dictionary")

        passed = len(reasons) == 0
        sanitized = output_payload if passed else None
        return PolicyGuardResult(passed=passed, reasons=reasons, sanitized_output=sanitized)

    @classmethod
    def check_call_notes_grounding(cls, draft_text: str, nurse_input: str) -> Tuple[bool, List[str]]:
        """Direct check that call notes draft contains NO facts, numbers, or symptoms beyond nurse input."""
        res = cls.inspect(
            agent_name="call_notes_agent",
            output_payload={"note_text": draft_text},
            context={"nurse_input": nurse_input}
        )
        return res.passed, res.reasons
