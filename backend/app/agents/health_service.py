"""
backend/app/agents/health_service.py — Aggregated health metrics for CareLoop Agents

Provides metrics over 24 hours and 7 days:
- runs, success, abstain, blocked, failed
- latency p50 and p95 (ms)
- tokens in/out and estimated cost
- draft accept/edit/reject
- thumbs-down count
- shadow agreement trend
- current autonomy level & mode
- version in use
- doctor view (detailed) and nurse view (read-only high-level summary)
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from backend.app.db import get_conn

logger = logging.getLogger(__name__)

# Standard cost estimation constants:
# Gemini Flash Lite: $0.075 / 1M input tokens, $0.30 / 1M output tokens
COST_PER_MILLION_INPUT = 0.075
COST_PER_MILLION_OUTPUT = 0.30


class AgentHealthService:
    @staticmethod
    def calculate_percentile(values: List[float], percentile: float) -> float:
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        k = (len(sorted_vals) - 1) * (percentile / 100.0)
        f = int(k)
        c = f + 1 if f + 1 < len(sorted_vals) else f
        d = k - f
        return round(sorted_vals[f] + d * (sorted_vals[c] - sorted_vals[f]), 1)

    @staticmethod
    def get_health_metrics(window: str = "24h") -> Dict[str, Any]:
        """Calculates agent health metrics across runs, cases, drafts, and shadow logs."""
        hours = 168 if window == "7d" else 24

        with get_conn() as conn:
            with conn.cursor() as cur:
                # 1. Fetch active versions per agent
                cur.execute("""
                    SELECT agent_name, version_id, prompt_version, model_name 
                    FROM agent_versions WHERE is_active = 1;
                """)
                ver_rows = cur.fetchall() or []
                active_versions = {r["agent_name"]: r for r in ver_rows}

                # 2. Fetch current autonomy matrix
                cur.execute("SELECT action_type, level, mode FROM agent_autonomy;")
                autonomy_rows = cur.fetchall() or []
                autonomy_map = {r["action_type"]: r for r in autonomy_rows}

                # 3. Query agent runs in time window (excluding test suite runs)
                cur.execute("""
                    SELECT run_id, agent_name, trigger_type, started_at, status, 
                           tokens_in, tokens_out, latency_ms, version_id, guard_reasons, source
                    FROM agent_runs
                    WHERE started_at >= NOW() - INTERVAL %s HOUR
                      AND source != 'test'
                    ORDER BY started_at DESC;
                """, (hours,))
                runs = cur.fetchall() or []

                # 4. Query draft decisions from agent_drafts
                cur.execute("""
                    SELECT status, edit_chars, created_at
                    FROM agent_drafts
                    WHERE created_at >= NOW() - INTERVAL %s HOUR;
                """, (hours,))
                draft_records = cur.fetchall() or []

                # 4b. Query thumbs down from chat_feedback
                cur.execute("""
                    SELECT COUNT(*) AS thumbs_down
                    FROM chat_feedback
                    WHERE rating = -1 AND created_at >= NOW() - INTERVAL %s HOUR;
                """, (hours,))
                tf_row = cur.fetchone()
                thumbs_down = tf_row["thumbs_down"] if tf_row else 0

                # 5. Query shadow agreement trend
                cur.execute("""
                    SELECT action_type, agreed, created_at
                    FROM shadow_decisions
                    WHERE created_at >= NOW() - INTERVAL %s HOUR
                    ORDER BY created_at DESC;
                """, (hours,))
                shadow_records = cur.fetchall() or []

                # 6. Query recent incidents (excluding test incidents)
                cur.execute("""
                    SELECT i.*, s.full_name as reported_by_name
                    FROM agent_incidents i
                    LEFT JOIN care_staff s ON s.staff_id = i.reported_by_staff_id
                    WHERE i.created_at >= NOW() - INTERVAL %s HOUR
                      AND i.source != 'test'
                    ORDER BY i.created_at DESC;
                """, (hours,))
                incidents = cur.fetchall() or []

        # Aggregate Runs by Agent (merging PapersAgent / papers_agent into canonical names)
        by_agent: Dict[str, Dict[str, Any]] = {}
        for r in runs:
            raw_name = r["agent_name"]
            if raw_name in ("PapersAgent", "papers_agent"):
                a_name = "papers_agent"
            elif raw_name in ("CasePrepAgent", "case_prep_agent"):
                a_name = "case_prep_agent"
            elif raw_name in ("OutreachAgent", "outreach_agent"):
                a_name = "outreach_agent"
            elif raw_name in ("HandoffAgent", "handoff_agent"):
                a_name = "handoff_agent"
            elif raw_name in ("PlanAgent", "plan_agent"):
                a_name = "plan_agent"
            elif raw_name in ("CallNotesAgent", "call_notes_agent"):
                a_name = "call_notes_agent"
            elif "test" in raw_name.lower():
                continue
            else:
                a_name = raw_name

            if a_name not in by_agent:
                ver_info = active_versions.get(a_name, {})
                by_agent[a_name] = {
                    "agent_name": a_name,
                    "version_in_use": r.get("version_id") or ver_info.get("version_id", "1.0.0"),
                    "prompt_version": ver_info.get("prompt_version", "v1.0"),
                    "model_name": ver_info.get("model_name", "gemini-3.5-flash-lite"),
                    "runs": 0,
                    "success": 0,
                    "abstain": 0,
                    "held": 0,
                    "blocked": 0,
                    "failed": 0,
                    "latencies": [],
                    "tokens_in": 0,
                    "tokens_out": 0,
                }
            entry = by_agent[a_name]
            entry["runs"] += 1
            st = r["status"]
            if st in ("Done", "Answered"):
                entry["success"] += 1
            elif st == "Blocked_By_Guard":
                entry["blocked"] += 1
            elif st == "Abstained":
                entry["abstain"] += 1
            elif st == "Held_By_Limits":
                entry["held"] += 1
            elif st == "Failed":
                entry["failed"] += 1
            else:
                entry["success"] += 1

            if r.get("latency_ms"):
                entry["latencies"].append(float(r["latency_ms"]))
            entry["tokens_in"] += r.get("tokens_in") or 0
            entry["tokens_out"] += r.get("tokens_out") or 0

        agent_table = []
        total_runs = len(runs)
        total_tokens_in = 0
        total_tokens_out = 0

        for a_name, data in by_agent.items():
            lats = data["latencies"]
            p50 = AgentHealthService.calculate_percentile(lats, 50)
            p95 = AgentHealthService.calculate_percentile(lats, 95)
            tin = data["tokens_in"]
            tout = data["tokens_out"]
            total_tokens_in += tin
            total_tokens_out += tout

            if tin == 0 and tout == 0:
                cost_label = "not recorded"
                cost_val = None
            else:
                cost_val = round(((tin / 1_000_000.0) * COST_PER_MILLION_INPUT) + ((tout / 1_000_000.0) * COST_PER_MILLION_OUTPUT), 4)
                cost_label = f"${cost_val:.4f}"

            agent_table.append({
                "agent_name": a_name,
                "version_in_use": data["version_in_use"],
                "model_name": data["model_name"],
                "runs": data["runs"],
                "success": data["success"],
                "abstain": data["abstain"],
                "held": data["held"],
                "blocked": data["blocked"],
                "failed": data["failed"],
                "latency_p50_ms": p50,
                "latency_p95_ms": p95,
                "tokens_in": tin,
                "tokens_out": tout,
                "estimated_cost_usd": cost_val,
                "cost_display": cost_label,
            })

        # Draft accept / edit / reject metrics
        draft_accepted = sum(1 for c in draft_records if c.get("status") in ("Accepted", "Approved"))
        draft_edited = sum(1 for c in draft_records if c.get("status") == "Edited")
        draft_rejected = sum(1 for c in draft_records if c.get("status") == "Rejected")
        edit_sizes = [c["edit_chars"] for c in draft_records if c.get("status") == "Edited" and c.get("edit_chars") is not None]
        avg_edit_chars = round(sum(edit_sizes) / len(edit_sizes), 1) if edit_sizes else 0.0

        # Shadow Agreement by action type
        shadow_by_action: Dict[str, Dict[str, Any]] = {}
        for s in shadow_records:
            act = s["action_type"]
            if act not in shadow_by_action:
                shadow_by_action[act] = {"agreed": 0, "total": 0}
            shadow_by_action[act]["total"] += 1
            if s["agreed"]:
                shadow_by_action[act]["agreed"] += 1

        actions_table = []
        for act, auto in autonomy_map.items():
            sh = shadow_by_action.get(act, {"agreed": 0, "total": 0})
            sh_pct = round((sh["agreed"] / sh["total"]) * 100.0, 1) if sh["total"] > 0 else None
            actions_table.append({
                "action_type": act,
                "level": auto["level"],
                "mode": auto["mode"],
                "shadow_cases": sh["total"],
                "shadow_agreement_pct": sh_pct
            })

        if total_tokens_in == 0 and total_tokens_out == 0:
            total_cost_display = "not recorded"
            total_cost_val = None
        else:
            total_cost_val = round(
                ((total_tokens_in / 1_000_000.0) * COST_PER_MILLION_INPUT) +
                ((total_tokens_out / 1_000_000.0) * COST_PER_MILLION_OUTPUT), 4
            )
            total_cost_display = f"${total_cost_val:.4f}"

        all_latencies = [float(r["latency_ms"]) for r in runs if r.get("latency_ms")]
        overall_p50 = AgentHealthService.calculate_percentile(all_latencies, 50)
        overall_p95 = AgentHealthService.calculate_percentile(all_latencies, 95)

        # High-level summary for Nurse view
        nurse_summary = {
            "window": window,
            "total_runs": total_runs,
            "overall_success_pct": round((sum(a["success"] for a in agent_table) / total_runs * 100.0), 1) if total_runs else 100.0,
            "blocked_by_guard": sum(a["blocked"] for a in agent_table),
            "safety_incidents_open": sum(1 for i in incidents if i["status"] == "Open"),
            "system_status": "Healthy" if sum(1 for i in incidents if i["status"] == "Open") == 0 else "Review Needed",
        }

        return {
            "window": window,
            "summary": {
                "total_runs": total_runs,
                "total_tokens": total_tokens_in + total_tokens_out,
                "estimated_cost_usd": total_cost_val,
                "cost_display": total_cost_display,
                "overall_p50_ms": overall_p50,
                "overall_p95_ms": overall_p95,
                "draft_accepted": draft_accepted,
                "draft_edited": draft_edited,
                "draft_rejected": draft_rejected,
                "avg_edit_chars": avg_edit_chars,
                "thumbs_down_count": thumbs_down,
            },
            "nurse_summary": nurse_summary,
            "by_agent": agent_table,
            "by_action": actions_table,
            "incidents": incidents,
            "active_demotions": [i for i in incidents if i.get("category") in ("Unsafe", "Wrong fact")]
        }
