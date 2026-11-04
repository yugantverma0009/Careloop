#!/usr/bin/env python3
"""
scripts/redteam_runner.py — CLI wrapper to run the 85-case red-team evaluation suite.
"""

import sys
import os

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.agents.redteam_runner import run_redteam_suite

if __name__ == "__main__":
    res = run_redteam_suite(log_to_audit=True)
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
        sys.exit(0)
    else:
        print("❌ CRITICAL: SECURITY ATTACKS BYPASSED POLICY GUARD")
        sys.exit(1)

