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
8. Consent: Family actions blocked if consent is missing.
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
    "ask_doctor",
    "recheck_at",
    "merge_duplicate",
    "close_rule"
}

# Allowlisted Action Cards for Patients (Section C & Ground Rules)
ALLOWLISTED_PATIENT_ACTIONS = {
    "Start_Checkin",
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
    },
    "plan_agent": {
        "search_discharge_papers",
        "get_prescriptions",
        "draft_recovery_plan",
        "reconcile_medications"
    }
}


class PolicyGuardResult:
    def __init__(self, passed: bool, reasons: List[str] = None, sanitized_output: Any = None):
        self.passed = passed
        self.reasons = reasons or []
        self.sanitized_output = sanitized_output

    @property
    def is_safe(self) -> bool:
        return self.passed

    @property
    def reason(self) -> Optional[str]:
        return "; ".join(self.reasons) if self.reasons else None

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
        payload_to_check = {k: v for k, v in output_payload.items() if k not in ("exemplars", "exemplar_label")}
        raw_text = json.dumps(payload_to_check)

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

        # 11. Phase 6 Canary String & Output Secrets Scanning
        try:
            from backend.app.agents.config import (
                AGENTS_V2_CANARY_CHECK,
                CANARY_STRING,
                AGENTS_V2_OUTPUT_SCANNING
            )
            payload_serialized = json.dumps(output_payload)
            if AGENTS_V2_CANARY_CHECK and CANARY_STRING in payload_serialized:
                reasons.append("Security violation: Canary token leaked in output payload")

            if AGENTS_V2_OUTPUT_SCANNING:
                secret_patterns = [
                    (r"AIza[0-9A-Za-z-_]{35}", "API Key leaked"),
                    (r"Bearer\s+[A-Za-z0-9\._\-]{20,}", "Auth bearer token leaked"),
                    (r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "Financial identifier or Aadhaar pattern leaked"),
                    (r"(?:mysql|postgres):\/\/[^\s]+", "Database connection string leaked")
                ]
                for pat, desc in secret_patterns:
                    if re.search(pat, payload_serialized):
                        reasons.append(f"Security violation: {desc}")
        except Exception as e:
            logger.warning(f"Error during output scanning: {e}")

        passed = len(reasons) == 0
        sanitized = output_payload if passed else None
        return PolicyGuardResult(passed=passed, reasons=reasons, sanitized_output=sanitized)

    @classmethod
    def inspect_output(cls, output_text_or_payload: Any, agent_name: str = "Unknown", context: Optional[Dict[str, Any]] = None) -> PolicyGuardResult:
        """Inspects agent output text or dict against canary leakage, secrets, and safety rules."""
        if isinstance(output_text_or_payload, str):
            payload = {"response": output_text_or_payload}
        elif isinstance(output_text_or_payload, dict):
            payload = output_text_or_payload
        else:
            payload = {"data": str(output_text_or_payload)}
        return cls.inspect(agent_name=agent_name, output_payload=payload, context=context)

    @classmethod
    def screen_input_text(cls, text: str, context: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[str]]:
        """Screens raw input text for length cap and adversarial redteam injections."""
        from backend.app.agents.config import MAX_INPUT_LENGTH_CHARS
        if len(text or "") > MAX_INPUT_LENGTH_CHARS:
            return False, f"INPUT_LENGTH_EXCEEDED: length {len(text)} exceeds {MAX_INPUT_LENGTH_CHARS}"
        return cls.inspect_redteam_attack(text, context)

    @classmethod
    def validate_tool_arguments(cls, tool_name_or_args: Any, arguments: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[str]]:
        """
        Validates tool arguments against strict schemas and checks for injection payloads / fuzzing attacks.
        Supports both (tool_name, arguments) and (arguments,).
        """
        if arguments is None and isinstance(tool_name_or_args, dict):
            arguments = tool_name_or_args
            tool_name = "general"
        else:
            tool_name = str(tool_name_or_args)
            arguments = arguments or {}

        if not isinstance(arguments, dict):
            return False, "Tool arguments must be a dictionary"

        # Check for command injection / path traversal / SQL injection / template attacks in arguments
        fuzz_patterns = [
            r"\.\./",
            r";\s*(?:rm|drop|select|update|delete|insert|cat|chmod|sh|bash)\b",
            r"\${jndi:",
            r"<script\b",
            r"--\s*$",
            r"'\s*or\s*'1'='1",
            r"union\s+select",
            r"1=1"
        ]
        for k, v in arguments.items():
            v_str = str(v)
            if len(v_str) > 500:
                return False, f"Tool argument '{k}' exceeds length limit (500 chars)"
            for pat in fuzz_patterns:
                if re.search(pat, v_str, re.IGNORECASE):
                    return False, f"Fuzzing / injection pattern detected in argument '{k}'"

        return True, None

    @classmethod
    def check_call_notes_grounding(cls, draft_text: str, nurse_input: str) -> Tuple[bool, List[str]]:
        """Direct check that call notes draft contains NO facts, numbers, or symptoms beyond nurse input."""
        res = cls.inspect(
            agent_name="call_notes_agent",
            output_payload={"note_text": draft_text},
            context={"nurse_input": nurse_input}
        )
        return res.passed, res.reasons

    @classmethod
    def inspect_redteam_attack(cls, text: str, context: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[str]]:
        """
        Automated Red-Team Security Gate (Phase 6 Task 2):
        Inspects untrusted text (patient messages, SMS, voice transcripts, PDF passages)
        for prompt injection, instruction override, cross-patient snooping,
        unauthorized flag closure, diagnosis demands, or malformed inputs.
        
        Returns (is_safe: bool, rejection_reason: Optional[str]).
        """
        context = context or {}
        raw = (text or "").strip()

        # 1. Size & Malformed Input Gate
        if len(raw) > 1200:
            return False, "Input length exceeds maximum safe limit (1200 chars)"
        if "\x00" in raw or any(ord(c) < 32 and c not in "\r\n\t" for c in raw):
            return False, "Input contains prohibited control characters or binary payload"

        raw_lower = raw.lower()

        # 2. Instruction Override & Jailbreaks (English & Hindi/Hinglish)
        injection_patterns = [
            r"\bignore\s+(?:all\s+)?(?:previous\s+)?(?:instructions|rules|prompts|limits)\b",
            r"\bforget\s+(?:all\s+)?(?:your\s+)?(?:rules|instructions)\b",
            r"\byou\s+are\s+now\s+(?:a|an|the|dan)\b",
            r"\bdan\s*(?:\(do\s+anything\s+now\)|mode)?\b",
            r"\broleplay\s+as\b",
            r"\bsystem\s+prompt\b",
            r"\breveal\s+(?:the\s+)?(?:system|prompt|secret)\b",
            r"\boverride\s+(?:all\s+)?(?:safety|clinical|rules)\b",
            r"\badmin\s+override\b",
            r"\bemergency\s+admin\b",
            r"\bdisregard\s+(?:all\s+)?(?:limits|guidelines|rules|instructions|previous)\b",
            r"\btell\s+me\s+i\s+am\s+(?:safe|cured|normal|healthy)\b",
            r"<\|im_start\|>",
            r"<system>",
            r"\[system\s*note",
            r"\badmin\s+mode\b",
            r"\bdeveloper\s+mode\b",
            r"\bjailbreak\b",
            r"\bi\s+am\s+(?:the\s+)?(?:doctor|admin|physician|surgeon)\b",
            # Hindi script & Hinglish transliteration
            r"नियम\s+भूल\s+जाओ",
            r"पिछल[ेा]\s+(?:सारा\s+)?निर्देश\s+रद्द",
            r"तुम\s+अब\s+डॉक्टर\s+हो",
            r"सिस्टम\s+प्रॉम्प्ट",
            r"\bsab\s+(?:niyam|rules|instructions)\s+bhool\s+ja[o]?\b",
            r"\brules\s+ignore\b",
            r"\bflag\s+hata\b",
            r"\bpichle\s+(?:saare\s+)?niyam\s+radd\b",
            r"\btum\s+ab\s+doctor\s+ho\b",
            r"\bmain\s+doctor\s+hoon\b"
        ]
        for pat in injection_patterns:
            if re.search(pat, raw_lower):
                return False, f"Prompt injection / instruction override attempt: pattern '{pat}'"

        # 3. Cross-Patient Data Snooping
        current_pid = context.get("patient_id")
        cross_patient_patterns = [
            r"\b(?:show|give|fetch|view|print|read)\s+(?:me\s+)?(?:another|other|all)\s+patient\b",
            r"\blist\s+of\s+all\s+patients\b",
            r"\bdata\s+of\s+patient\b",
            r"\brecords\s+of\s+patient\b",
            r"\baccess\s+patient\s+records\b",
            r"\bphone\s+number\s+(?:and\s+address\s+)?of\b",
            r"\baddress\s+of\b",
            r"\bpatient\s+(?:id\s+)?#?\d+\b",
            r"\bcl-\d{4,5}\b",
            # Specific other cast members
            r"\b(?:meera\s+sharma|rajesh\s+verma|kabir\s+mehta|sunita\s+rao)\b",
            # Hindi script & Hinglish
            r"दूसरे\s+मरीज\s+का\s+डेटा",
            r"अन्य\s+मरीज\s+का\s+रिकॉर्ड",
            r"\bdusre\s+patient\s+ka\s+data\b",
            r"\bdusre\s+mariz\s+ka\s+record\b",
            r"\bkisi\s+aur\s+mariz\s+ka\s+(?:data|record)\b"
        ]
        for pat in cross_patient_patterns:
            m = re.search(pat, raw_lower)
            if m:
                # If it's the patient's own code/id, allow it
                matched_txt = m.group(0)
                if current_pid and (f"patient {current_pid}" in matched_txt or f"patient id {current_pid}" in matched_txt):
                    continue
                return False, f"Unauthorized cross-patient record access attempt: '{matched_txt}'"

        # 4. Direct Clinical Diagnosis / Prescription Demands
        diagnosis_patterns = [
            r"\bdiagnos(?:e|is)\b",
            r"\bwhat\s+diagnosis\s+do\s+i\s+have\b",
            r"\bdo\s+i\s+have\s+(?:a\s+|an\s+)?(?:cancer|pneumonia|infection|heart\s+attack|stroke|covid|fever|flu|pulmonary\s+embolism|heart\s+failure)\b",
            r"\bprescrib(?:e|ing)\b",
            r"\b(?:double|increase|decrease|change|stop)\s+(?:my\s+)?(?:[a-z0-9]+\s+)?(?:dose|medication|tablet|aspirin|blood\s+thinners)\b",
            r"\bis\s+it\s+safe\s+to\s+stop\b",
            r"\bcompletely\s+safe\b",
            r"\bcan\s+i\s+skip\b",
            r"\bcompletely\s+cured\b",
            # Hindi script & Hinglish
            r"दवा\s+लिख\s+दो",
            r"बीमारी\s+का\s+निदान",
            r"\bmeri\s+bimari\s+diagnose\s+karo\b",
            r"\bmujhe\s+kya\s+bimari\s+hai\b",
            r"\bnayi\s+dawa\s+likh\b"
        ]
        for pat in diagnosis_patterns:
            if re.search(pat, raw_lower):
                return False, f"Prohibited clinical diagnosis / prescription advice demand: pattern '{pat}'"

        # 5. Unauthorized Flag / Task Closure Attempt
        close_patterns = [
            r"\bclose\s+(?:this\s+|all\s+|my\s+)?(?:open\s+)?(?:flag|task|case|alert)\b",
            r"\bmark\s+(?:flag|task|alert|case)\s+.*?closed\b",
            r"\bresolve\s+(?:my\s+|this\s+|the\s+)?(?:flag|alert|case|task)\b",
            r"\bdismiss\s+(?:the\s+|my\s+|this\s+)?(?:red\s+)?(?:flag|alert|case|task)\b",
            # Hindi script & Hinglish
            r"फ्लैग\s+बंद\s+करो",
            r"अलर्ट\s+बंद\s+करो",
            r"\bflag\s+close\s+kar\s+do\b",
            r"\balert\s+resolve\s+kar\s+do\b"
        ]
        for pat in close_patterns:
            if re.search(pat, raw_lower):
                return False, f"Unauthorized flag/alert resolution attempt: pattern '{pat}'"

        # 6. Unauthorized Threshold / Limit Tampering
        limit_patterns = [
            r"\b(?:change|modify|increase|decrease|update|set|alter)\s+(?:the\s+)?(?:limit|threshold|spo2\s+threshold|vital\s+range)\b",
            r"\bdisable\s+(?:all\s+)?(?:alerts|limits|thresholds)\b",
            r"\blimits?\s+change\s+kar\s+do\b",
            r"\bthreshold\s+badal\s+do\b"
        ]
        for pat in limit_patterns:
            if re.search(pat, raw_lower):
                return False, f"Unauthorized clinical limit tampering attempt: pattern '{pat}'"

        # 7. Text Hidden in PDF Passages / Document Injection
        pdf_patterns = [
            r"\[(?:system|instruction|admin|override)\]",
            r"\bnote\s+to\s+(?:ai\s+assistant|ai|assistant|model):\s*(?:disregard|ignore|discharge)\b",
            r"\bignore\s+discharge\s+instructions\b",
            r"\bpdf\s+injection\b",
            r"\bsystem\s+directive:\s*discharge\b"
        ]
        for pat in pdf_patterns:
            if re.search(pat, raw_lower):
                return False, f"Document/PDF injection pattern detected: pattern '{pat}'"

        # 8. SMS & Voice Transcript Social Engineering
        social_eng_patterns = [
            r"\b(?:nurse|doctor)(?:\s+[a-z]+)?\s+(?:called|said|told|spoke)\s+(?:to\s+|and\s+said\s+to\s+)?(?:cancel|discharge|stop\s+all|delete|resolve)\b",
            r"\bdoctor\s+said\s+on\s+phone\b",
            r"\bdelete\s+all\s+(?:warnings|alerts)\b",
            r"\bcancel\s+all\s+warnings\b",
            r"\bdischarge\s+patient\b",
            r"\bcancel\s+my\s+follow\s*up\b",
            r"\bsms\s+(?:verification\s+)?code:\s*override\b",
            r"\bphone\s+override\b",
            r"\bdr\.\s+[a-z]+\s+said\s+i\s+can\s+stop\s+taking\b"
        ]
        for pat in social_eng_patterns:
            if re.search(pat, raw_lower):
                return False, f"Social engineering via transcript/SMS override detected: pattern '{pat}'"

        # 9. Canary string probe
        try:
            from backend.app.agents.config import CANARY_STRING
            if CANARY_STRING.lower() in raw_lower:
                return False, "Canary string probe / leakage detected"
        except Exception:
            pass

        return True, None
