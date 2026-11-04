"""
backend/app/agents/config.py — Configuration flags and thresholds for CareLoop Agents v2
"""

import os

# Capability toggles
AGENTS_V2_VERSION_REGISTRY = os.getenv("AGENTS_V2_VERSION_REGISTRY", "true").lower() in ("true", "1", "yes")
AGENTS_V2_CIRCUIT_BREAKER = os.getenv("AGENTS_V2_CIRCUIT_BREAKER", "true").lower() in ("true", "1", "yes")
AGENTS_V2_INCIDENT_REPORTING = os.getenv("AGENTS_V2_INCIDENT_REPORTING", "true").lower() in ("true", "1", "yes")
AGENTS_V2_INCIDENT_AUTO_DEMOTE = os.getenv("AGENTS_V2_INCIDENT_AUTO_DEMOTE", "true").lower() in ("true", "1", "yes")

# Circuit breaker thresholds
CIRCUIT_BREAKER_MIN_RUNS = int(os.getenv("CIRCUIT_BREAKER_MIN_RUNS", "30"))
CIRCUIT_BREAKER_WINDOW_RUNS = int(os.getenv("CIRCUIT_BREAKER_WINDOW_RUNS", "50"))
CIRCUIT_BREAKER_GUARD_BLOCK_MAX_PCT = float(os.getenv("CIRCUIT_BREAKER_GUARD_BLOCK_MAX_PCT", "10.0"))
CIRCUIT_BREAKER_FAILURE_MAX_PCT = float(os.getenv("CIRCUIT_BREAKER_FAILURE_MAX_PCT", "15.0"))
CIRCUIT_BREAKER_MAX_INCIDENTS_24H = int(os.getenv("CIRCUIT_BREAKER_MAX_INCIDENTS_24H", "2"))
CIRCUIT_BREAKER_MIN_SHADOW_AGREEMENT_PCT = float(os.getenv("CIRCUIT_BREAKER_MIN_SHADOW_AGREEMENT_PCT", "80.0"))

# Regression gate thresholds
REGRESSION_GATE_DEV_RATIO = float(os.getenv("REGRESSION_GATE_DEV_RATIO", "0.80"))
REGRESSION_GATE_MAX_QUALITY_DROP_POINTS = float(os.getenv("REGRESSION_GATE_MAX_QUALITY_DROP_POINTS", "2.0"))

# Phase 2: Agentic RAG v2 Flags
AGENTS_V2_RAG_DECOMPOSITION = os.getenv("AGENTS_V2_RAG_DECOMPOSITION", "true").lower() in ("true", "1", "yes")
AGENTS_V2_SOURCE_CONFLICT = os.getenv("AGENTS_V2_SOURCE_CONFLICT", "true").lower() in ("true", "1", "yes")
AGENTS_V2_RERANKING = os.getenv("AGENTS_V2_RERANKING", "true").lower() in ("true", "1", "yes")
AGENTS_V2_RELATIVE_DATES = os.getenv("AGENTS_V2_RELATIVE_DATES", "true").lower() in ("true", "1", "yes")
AGENTS_V2_CLARIFICATION = os.getenv("AGENTS_V2_CLARIFICATION", "true").lower() in ("true", "1", "yes")
AGENTS_V2_EVIDENCE_STRENGTH = os.getenv("AGENTS_V2_EVIDENCE_STRENGTH", "true").lower() in ("true", "1", "yes")
AGENTS_V2_HINGLISH = os.getenv("AGENTS_V2_HINGLISH", "true").lower() in ("true", "1", "yes")
AGENTS_V2_PARALLEL_EXEC = os.getenv("AGENTS_V2_PARALLEL_EXEC", "true").lower() in ("true", "1", "yes")
AGENTS_V2_RETRIEVAL_CACHE = os.getenv("AGENTS_V2_RETRIEVAL_CACHE", "true").lower() in ("true", "1", "yes")

# Phase 3: Staff Copilot "Ask CareLoop" Flags
AGENTS_V2_COPILOT = os.getenv("AGENTS_V2_COPILOT", "true").lower() in ("true", "1", "yes")
AGENTS_V2_COPILOT_CACHE = os.getenv("AGENTS_V2_COPILOT_CACHE", "true").lower() in ("true", "1", "yes")
AGENTS_V2_COPILOT_CACHE_TTL_SEC = int(os.getenv("AGENTS_V2_COPILOT_CACHE_TTL_SEC", "60"))
AGENTS_V2_COPILOT_VOICE = os.getenv("AGENTS_V2_COPILOT_VOICE", "true").lower() in ("true", "1", "yes")

# Phase 4: Case Workflow, Explainable Prioritisation & Routine Drafts
AGENTS_V2_CASE_WORKFLOW = os.getenv("AGENTS_V2_CASE_WORKFLOW", "true").lower() in ("true", "1", "yes")
AGENTS_V2_EXPLAINABLE_QUEUE = os.getenv("AGENTS_V2_EXPLAINABLE_QUEUE", "true").lower() in ("true", "1", "yes")
AGENTS_V2_ROUTINE_DRAFT_REVIEW = os.getenv("AGENTS_V2_ROUTINE_DRAFT_REVIEW", "true").lower() in ("true", "1", "yes")
AGENTS_V2_BATCH_APPROVAL_THRESHOLD = float(os.getenv("AGENTS_V2_BATCH_APPROVAL_THRESHOLD", "95.0"))

# Doctor-approved types for batch approval (when shadow agreement >= 95%)
BATCH_APPROVED_DRAFT_TYPES = ["Case_Brief", "Patient_Message", "Summary"]

# Configurable SLA timers per case state (in seconds)
CASE_SLA_SECONDS = {
    "Raised": int(os.getenv("CASE_SLA_RAISED_SEC", "900")),           # 15 min
    "Briefed": int(os.getenv("CASE_SLA_BRIEFED_SEC", "1800")),         # 30 min
    "Contacting": int(os.getenv("CASE_SLA_CONTACTING_SEC", "2700")),   # 45 min
    "Waiting_For_Doctor": int(os.getenv("CASE_SLA_WAITING_SEC", "3600")), # 60 min
    "Decided": int(os.getenv("CASE_SLA_DECIDED_SEC", "7200")),         # 120 min
    "Closed": int(os.getenv("CASE_SLA_CLOSED_SEC", "86400")),         # 24 h
    "Reopened": int(os.getenv("CASE_SLA_REOPENED_SEC", "900")),        # 15 min
}

# Rule-based explainable queue weights (No Machine Learning)
CASE_QUEUE_WEIGHTS = {
    # 1. Tier severity weights
    "tier": {
        "Immediate": 100,
        "Urgent": 50,
        "Review_Soon": 20,
        "Routine": 0
    },
    # 2. Minutes overdue bucket
    "minutes_overdue_buckets": [
        {"min": 120, "points": 40, "label": "Overdue > 120 min"},
        {"min": 60, "points": 25, "label": "Overdue 60–120 min"},
        {"min": 30, "points": 15, "label": "Overdue 30–60 min"},
        {"min": 15, "points": 5, "label": "Overdue 15–30 min"},
    ],
    # 3. Number of no-answers (outreach attempts without patient response)
    "no_answer_per_attempt": 15,
    "no_answer_max_points": 45,
    # 4. Device silent weights
    "device_silent": {
        "silent_over_24h": 30,
        "silent_over_12h": 15,
    },
    # 5. Consent missing penalty
    "consent_missing_penalty": -20,
    # 6. SOS active distress alert
    "sos_points": 150
}

# Phase 5: Proactive Help, Approved Examples & Patient Transparency
AGENTS_V2_DAY_BRIEF = os.getenv("AGENTS_V2_DAY_BRIEF", "true").lower() in ("true", "1", "yes")
AGENTS_V2_VISIT_PREP = os.getenv("AGENTS_V2_VISIT_PREP", "true").lower() in ("true", "1", "yes")
AGENTS_V2_PATTERN_PROPOSALS = os.getenv("AGENTS_V2_PATTERN_PROPOSALS", "true").lower() in ("true", "1", "yes")
AGENTS_V2_APPROVED_EXEMPLARS = os.getenv("AGENTS_V2_APPROVED_EXEMPLARS", "true").lower() in ("true", "1", "yes")
AGENTS_V2_PATIENT_TRANSPARENCY = os.getenv("AGENTS_V2_PATIENT_TRANSPARENCY", "true").lower() in ("true", "1", "yes")

# Current AI governance notice version
CURRENT_AI_NOTICE_VERSION = os.getenv("CURRENT_AI_NOTICE_VERSION", "v2.0-2026-11")

# Phase 6: Hardening, Misuse Prevention & Retention Flags
AGENTS_V2_HARDENING = os.getenv("AGENTS_V2_HARDENING", "true").lower() in ("true", "1", "yes")
AGENTS_V2_CANARY_CHECK = os.getenv("AGENTS_V2_CANARY_CHECK", "true").lower() in ("true", "1", "yes")
CANARY_STRING = os.getenv("CARELOOP_CANARY_STRING", "CARELOOP_CANARY_SECRET_TOKEN_9182")
AGENTS_V2_INPUT_SCREENING = os.getenv("AGENTS_V2_INPUT_SCREENING", "true").lower() in ("true", "1", "yes")
AGENTS_V2_OUTPUT_SCANNING = os.getenv("AGENTS_V2_OUTPUT_SCANNING", "true").lower() in ("true", "1", "yes")
AGENTS_V2_RETENTION = os.getenv("AGENTS_V2_RETENTION", "true").lower() in ("true", "1", "yes")
AGENTS_V2_RETENTION_DAYS = int(os.getenv("AGENTS_V2_RETENTION_DAYS", "30"))
MAX_INPUT_LENGTH_CHARS = int(os.getenv("MAX_INPUT_LENGTH_CHARS", "1200"))





