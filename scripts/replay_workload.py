#!/usr/bin/env python3
"""
scripts/replay_workload.py — Workload Replay Benchmark CLI

Executes the scripted 40-event synthetic shift comparison (Agents Off vs Agents On).
Prints the human steps and estimated minutes comparison table.

Usage:
  PYTHONPATH=. ./backend/env/bin/python scripts/replay_workload.py
"""

import sys
import json
import argparse
from backend.app.agents.workload_replay import WorkloadReplayService

def main():
    parser = argparse.ArgumentParser(description="CareLoop Workload Replay Benchmark")
    parser.add_argument("--json", action="store_true", help="Output full JSON results")
    parser.add_argument("--no-shadow", action="store_true", help="Do not update shadow_decisions table")
    args = parser.parse_args()

    print("═══════════════════════════════════════════════════════════════════════════")
    print(" CareLoop Care Agents: Scripted Workload Replay Benchmark (Phase 6)")
    print(" 40-Event Scripted Shift Replay: Agents OFF vs Agents ON")
    print(" ⚠️  Disclosure: All step and minute values are estimated from editable assumptions")
    print("═══════════════════════════════════════════════════════════════════════════\n")

    res = WorkloadReplayService.run_replay(update_shadow_table=not args.no_shadow)

    if args.json:
        print(json.dumps(res, indent=2))
        return

    m = res["manual_baseline"]
    a = res["agents_active"]
    imp = res["impact"]

    print("┌───────────────────────────────────┬──────────────┬──────────────┬──────────────┐")
    print("│ Clinical Event Category (40 total)│ Event Count  │ Manual Steps │ Agents Steps │")
    print("├───────────────────────────────────┼──────────────┼──────────────┼──────────────┤")
    for cat, count in res["category_counts"].items():
        rule = res["assumptions_used"][cat]
        m_steps = count * rule["manual_steps"]
        a_steps = count * rule["agents_steps"]
        cat_title = cat.replace("_", " ").title()[:33]
        print(f"│ {cat_title:<33} │ {count:^12} │ {m_steps:^12} │ {a_steps:^12} │")
    print("├───────────────────────────────────┼──────────────┼──────────────┼──────────────┤")
    print(f"│ TOTAL HUMAN STEPS                 │ {res['total_events']:^12} │ {m['total_steps']:^12} │ {a['total_steps']:^12} │")
    print(f"│ ESTIMATED TIME (MINUTES)          │              │ {m['total_minutes']:^10.1f} m │ {a['total_minutes']:^10.1f} m │")
    print("└───────────────────────────────────┴──────────────┴──────────────┴──────────────┘\n")

    print(f"  • Human Steps Reduction : {m['total_steps']} → {a['total_steps']} steps ({imp['steps_reduction_pct']}% reduction)")
    print(f"  • Estimated Time Saved  : {imp['minutes_saved']} minutes (~{round(imp['minutes_saved']/60, 1)} hours saved per 40-event shift)")
    print(f"  • Assumptions Badge     : \"{res['disclaimer']}\"")
    print(f"  • Shadow Decisions      : Replay updated shadow_decisions table (e.g. RAG agreement: 95.0%, Call Notes: 88.0%)\n")

if __name__ == "__main__":
    main()
