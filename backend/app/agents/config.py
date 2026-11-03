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


