#!/usr/bin/env python3
"""
scripts/load_test.py — CareLoop Concurrency & Load Stress Test (Phase 6)

Executes:
- 50 concurrent patient questions (PapersAgent & deterministic tools)
- 20 concurrent staff copilot queries (Template extraction & query execution)

Measures and Reports:
- Total requests and error rate (%)
- p50 and p95 latency (ms)
- Average tokens per query and estimated cost per 100 interactions
"""

import os
import sys
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List

# Ensure project root is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.agents.papers_agent import PapersAgent
from backend.app.agents.copilot_service import ask_careloop


# 50 Patient Questions (bilingual mix of calendar, medicines, and discharge instructions)
PATIENT_LOAD_QUERIES = [
    "When is my next appointment?",
    "What are my scheduled medicines for today?",
    "Can I do morning walking exercises?",
    "What is the dose for Metformin?",
    "When do I visit Dr. Ananya Sharma?",
    "Is my follow up visit confirmed?",
    "What time should I take Atorvastatin?",
    "मेरी अगली मुलाकात कब है?",
    "आज की दवाइयां क्या हैं?",
    "What are sternal precautions after surgery?",
] * 5  # 50 total

# 20 Staff Copilot Queries
STAFF_LOAD_QUERIES = [
    "who missed 2 doses in 24 hours",
    "explain alert for flag 1",
    "patient snapshot for patient 1",
    "which patients have open flags",
    "who has no checkin today",
    "draft dose reminder message for patient 1",
    "what changed since yesterday",
    "protocol faq for sternal wound care",
    "who has missing family consent",
    "explain alert for flag 2",
] * 2  # 20 total


def execute_patient_query(q: str, idx: int) -> Dict[str, Any]:
    t0 = time.time()
    try:
        res = PapersAgent.process_query(
            patient_id=1,
            question=q,
            language="hi" if "है" in q else "en"
        )
        latency = (time.time() - t0) * 1000.0
        tokens_in = len(q.split()) * 2 + 120
        tokens_out = len(res.get("answer", "").split()) * 2
        return {
            "type": "patient",
            "idx": idx,
            "success": bool(res.get("answer")),
            "latency_ms": latency,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "error": None
        }
    except Exception as e:
        latency = (time.time() - t0) * 1000.0
        return {
            "type": "patient",
            "idx": idx,
            "success": False,
            "latency_ms": latency,
            "tokens_in": 0,
            "tokens_out": 0,
            "error": str(e)
        }


def execute_staff_query(q: str, idx: int) -> Dict[str, Any]:
    t0 = time.time()
    try:
        user = {"staff_id": 1, "role": "Doctor", "full_name": "Dr. Ananya Sharma"}
        res = ask_careloop(
            query=q,
            user=user
        )
        latency = (time.time() - t0) * 1000.0
        tokens_in = len(q.split()) * 2 + 80
        tokens_out = 45
        return {
            "type": "staff",
            "idx": idx,
            "success": bool(res.get("status") in ("ok", "success") or "template" in res),
            "latency_ms": latency,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "error": None
        }
    except Exception as e:
        latency = (time.time() - t0) * 1000.0
        return {
            "type": "staff",
            "idx": idx,
            "success": False,
            "latency_ms": latency,
            "tokens_in": 0,
            "tokens_out": 0,
            "error": str(e)
        }


def run_load_test() -> Dict[str, Any]:
    print("=" * 70)
    print("⚡ CARELOOP CONCURRENCY & LOAD TEST (PHASE 6)")
    print("   • 50 Concurrent Patient Questions")
    print("   • 20 Concurrent Staff Copilot Queries")
    print("=" * 70)

    start_total = time.time()
    results: List[Dict[str, Any]] = []

    # Execute all 70 queries across a pool of 24 worker threads
    with ThreadPoolExecutor(max_workers=24) as pool:
        futures = []
        for i, q in enumerate(PATIENT_LOAD_QUERIES):
            futures.append(pool.submit(execute_patient_query, q, i))
        for j, q in enumerate(STAFF_LOAD_QUERIES):
            futures.append(pool.submit(execute_staff_query, q, j))

        for f in as_completed(futures):
            results.append(f.result())

    total_duration = time.time() - start_total

    # Compute Metrics
    total_reqs = len(results)
    successes = sum(1 for r in results if r["success"])
    failures = total_reqs - successes
    error_rate_pct = (failures / total_reqs) * 100.0 if total_reqs else 0.0

    latencies = [r["latency_ms"] for r in results]
    latencies.sort()
    p50_latency = statistics.median(latencies) if latencies else 0.0
    p95_idx = int(0.95 * len(latencies))
    p95_latency = latencies[min(p95_idx, len(latencies) - 1)] if latencies else 0.0

    total_tokens_in = sum(r["tokens_in"] for r in results)
    total_tokens_out = sum(r["tokens_out"] for r in results)
    total_tokens = total_tokens_in + total_tokens_out

    # Gemini 2.5 Flash Lite pricing: $0.075 / 1M prompt tokens; $0.30 / 1M output tokens
    cost_usd = (total_tokens_in * 0.000000075) + (total_tokens_out * 0.00000030)
    cost_per_100 = (cost_usd / total_reqs) * 100.0 if total_reqs else 0.0

    # Patient vs Staff breakdown
    p_lats = [r["latency_ms"] for r in results if r["type"] == "patient"]
    s_lats = [r["latency_ms"] for r in results if r["type"] == "staff"]

    print("\n📊 LOAD TEST EXECUTION RESULTS:")
    print(f"  • Total Requests:     {total_reqs} ({len(PATIENT_LOAD_QUERIES)} patient, {len(STAFF_LOAD_QUERIES)} staff)")
    print(f"  • Total Wall Time:    {total_duration:.2f}s ({total_reqs / total_duration:.1f} req/s throughput)")
    print(f"  • Success Rate:       {successes}/{total_reqs} ({100.0 - error_rate_pct:.1f}%)")
    print(f"  • Error Rate:         {error_rate_pct:.1f}%")
    print(f"  • Overall p50 Latency: {p50_latency:.1f} ms")
    print(f"  • Overall p95 Latency: {p95_latency:.1f} ms")
    if p_lats:
        print(f"  • Patient Qs p50/p95:  {statistics.median(p_lats):.1f} ms / {p_lats[int(0.95*len(p_lats))]:.1f} ms")
    if s_lats:
        print(f"  • Staff Copilot p50/95: {statistics.median(s_lats):.1f} ms / {s_lats[int(0.95*len(s_lats))]:.1f} ms")
    print(f"  • Total Tokens:       {total_tokens} (In: {total_tokens_in}, Out: {total_tokens_out})")
    print(f"  • Estimated Cost/100: ${cost_per_100:.6f} USD")
    print("=" * 70)

    return {
        "total_requests": total_reqs,
        "successes": successes,
        "failures": failures,
        "error_rate_pct": error_rate_pct,
        "total_duration_sec": total_duration,
        "throughput_rps": total_reqs / total_duration if total_duration else 0.0,
        "p50_latency_ms": p50_latency,
        "p95_latency_ms": p95_latency,
        "total_tokens": total_tokens,
        "cost_per_100_interactions_usd": cost_per_100,
        "passed": (error_rate_pct == 0.0)
    }


if __name__ == "__main__":
    res = run_load_test()
    if not res["passed"]:
        sys.exit(1)
    sys.exit(0)
