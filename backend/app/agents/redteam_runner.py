"""
backend/app/agents/redteam_runner.py — Automated Red-Team Security Runner (Phase 6)
Executes all 85+ red-team attack vectors against Policy Guard,
ensuring 100% block/abstain rate and logging security audits.
"""

import json
import logging
from typing import Dict, Any, List, Tuple
from datetime import datetime

from backend.app.db import get_conn
from backend.app.agents.policy_guard import PolicyGuard
from backend.app.agents.redteam_cases_v2 import REDTEAM_CASES_V2

logger = logging.getLogger(__name__)


def run_redteam_suite(log_to_audit: bool = True) -> Dict[str, Any]:
    """
    Executes the full 85-case red-team evaluation suite against Policy Guard.
    Every single attack vector must be blocked or abstained.
    """
    total = len(REDTEAM_CASES_V2)
    blocked_count = 0
    passed_attacks = []
    category_stats: Dict[str, Dict[str, int]] = {}

    for case in REDTEAM_CASES_V2:
        cat = case["cat"]
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "blocked": 0}
        category_stats[cat]["total"] += 1

        is_safe, reason = PolicyGuard.inspect_redteam_attack(
            text=case["q"],
            context={"patient_id": 1}
        )

        # To pass redteam, the attack MUST be flagged as NOT SAFE (is_safe == False)
        if not is_safe:
            blocked_count += 1
            category_stats[cat]["blocked"] += 1
        else:
            passed_attacks.append({
                "id": case["id"],
                "category": cat,
                "text": case["q"],
                "error": "CRITICAL: Attack bypassed Policy Guard inspection!"
            })

    block_rate = (blocked_count / total) * 100.0 if total else 100.0

    # Log to audit trail if requested
    if log_to_audit:
        try:
            with get_conn() as conn, conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details, created_at)
                    VALUES ('System', '1', 'REDTEAM_SUITE_EXECUTED', 'security', 1, JSON_OBJECT(
                        'total_cases', %s,
                        'blocked_count', %s,
                        'block_rate_pct', %s,
                        'passed_attacks_count', %s
                    ), NOW());
                """, (total, blocked_count, block_rate, len(passed_attacks)))
                conn.commit()
        except Exception as e:
            logger.warning(f"Could not write redteam execution to audit log: {e}")

    return {
        "total_cases": total,
        "blocked_count": blocked_count,
        "passed_attacks_count": len(passed_attacks),
        "block_rate_pct": block_rate,
        "category_stats": category_stats,
        "passed_attacks": passed_attacks,
        "all_blocked": (len(passed_attacks) == 0)
    }


if __name__ == "__main__":
    res = run_redteam_suite(log_to_audit=False)
    print("=" * 65)
    print("🛡️  CARELOOP RED-TEAM ADVERSARIAL SUITE EVALUATION (PHASE 6)")
    print("=" * 65)
    print(f"Total Attack Probes:  {res['total_cases']}")
    print(f"Blocked by Policy:    {res['blocked_count']}")
    print(f"Bypassed Guard:       {res['passed_attacks_count']}")
    print(f"Block Rate:           {res['block_rate_pct']:.1f}%")
    print("-" * 65)
    for cat, stats in res["category_stats"].items():
        print(f"  • {cat:<32} {stats['blocked']}/{stats['total']} ({stats['blocked']/stats['total']*100:.1f}%)")
    print("=" * 65)
    if res["all_blocked"]:
        print("✅ 100% ADVERSARIAL ATTACKS SUCCESSFULLY BLOCKED")
    else:
        print("❌ CRITICAL: SECURITY ATTACKS BYPASSED POLICY GUARD")

