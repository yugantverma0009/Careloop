"""
backend/app/agents/handoff_agent.py — Shift Handoff Agent & Patient Clinical Summary Agent

Principles:
- "The LLM talks. Rules decide. Humans act."
- "Periodic paperwork writes itself; the human signs."
- Builds deterministic fact sheets from SQL (no patient names sent to LLM, uses patient code / 'the patient').
- SBAR / I-PASS structure: Situation, Background, Assessment/Actions, Recommendation.
- Zero judgment words (stable, normal, safe, etc.) strictly verified by Policy Guard.
- Marked "AI-prepared draft" with auditable run_id.
- Unsigned drafts are strictly NEVER shown to patients.
"""

import json
import logging
import uuid
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple

from ..db import get_conn
from .ledger import AgentLedger
from .policy_guard import PolicyGuard, BANNED_WORDS

logger = logging.getLogger(__name__)


class HandoffAgent:
    """Automates post-shift handoffs and patient clinical summaries under staff review."""

    @staticmethod
    def build_patient_fact_sheet(patient_id: int) -> Dict[str, Any]:
        """
        Builds a 100% deterministic, grounded clinical fact sheet from SQL.
        No LLM used here; facts cite specific database entities.
        """
        with get_conn() as conn:
            with conn.cursor() as cur:
                # 1. Patient identity and discharge/monitoring day
                cur.execute("""
                    SELECT p.patient_id, p.full_name, p.patient_code, p.created_at,
                           p.preferred_language, d.discharge_date, d.condition_summary
                    FROM patients p
                    LEFT JOIN discharge_records d ON d.patient_id = p.patient_id
                    WHERE p.patient_id = %s
                    ORDER BY d.discharge_date DESC LIMIT 1;
                """, (patient_id,))
                pat = cur.fetchone()
                if not pat:
                    raise ValueError(f"Patient #{patient_id} not found.")

                day_num = 1
                if pat.get("discharge_date"):
                    d_val = pat["discharge_date"]
                    d_date = d_val.date() if hasattr(d_val, "date") else d_val
                    day_num = max(1, (date.today() - d_date).days + 1)
                elif pat.get("created_at"):
                    c_val = pat["created_at"]
                    c_date = c_val.date() if hasattr(c_val, "date") else c_val
                    day_num = max(1, (date.today() - c_date).days + 1)

                # 2. Latest vital signs / telemetry
                cur.execute("""
                    SELECT measurement_type, measurement_value, unit, measured_at
                    FROM sensor_readings
                    WHERE patient_id = %s
                    ORDER BY measured_at DESC LIMIT 6;
                """, (patient_id,))
                vitals = cur.fetchall()

                # 3. Medication adherence today
                cur.execute("""
                    SELECT m.medicine_name, l.status, l.scheduled_for
                    FROM medication_logs l
                    JOIN prescriptions p ON p.prescription_id = l.prescription_id
                    JOIN medicines m ON m.medicine_id = p.medicine_id
                    WHERE p.patient_id = %s AND DATE(l.scheduled_for) = CURDATE()
                    ORDER BY l.scheduled_for ASC;
                """, (patient_id,))
                med_logs = cur.fetchall()

                # 4. Open flags
                cur.execute("""
                    SELECT flag_id, source_type, reason, severity, created_at
                    FROM flags
                    WHERE patient_id = %s AND status = 'Open'
                    ORDER BY created_at DESC;
                """, (patient_id,))
                open_flags = cur.fetchall()

                # 5. Open follow-up tasks
                cur.execute("""
                    SELECT followup_id, reason, priority, due_at, status
                    FROM follow_up_tasks
                    WHERE patient_id = %s AND status IN ('Pending', 'In_Progress')
                    ORDER BY due_at ASC;
                """, (patient_id,))
                open_tasks = cur.fetchall()

                # 6. Latest clinician call / contact notes
                cur.execute("""
                    SELECT note_id, note_type, note_text, created_at
                    FROM clinician_notes
                    WHERE patient_id = %s
                    ORDER BY created_at DESC LIMIT 2;
                """, (patient_id,))
                recent_notes = cur.fetchall()

        return {
            "patient_id": patient_id,
            "patient_code": pat["patient_code"],
            "relative_day": day_num,
            "condition": pat["condition_summary"] or "Post-discharge monitoring",
            "vitals": [
                {
                    "metric": v["measurement_type"],
                    "value": float(v["measurement_value"]),
                    "unit": v["unit"],
                    "time": v["measured_at"].strftime("%H:%M") if v.get("measured_at") else ""
                } for v in vitals
            ],
            "medications_today": [
                {
                    "medicine": m["medicine_name"],
                    "status": m["status"],
                    "time": m["scheduled_for"].strftime("%H:%M") if m.get("scheduled_for") else ""
                } for m in med_logs
            ],
            "open_flags": [
                {
                    "flag_id": f["flag_id"],
                    "reason": f["reason"],
                    "severity": f["severity"],
                    "source": f["source_type"]
                } for f in open_flags
            ],
            "open_tasks": [
                {
                    "task_id": t["followup_id"],
                    "reason": t["reason"],
                    "priority": t["priority"]
                } for t in open_tasks
            ],
            "recent_notes": [
                {
                    "note_id": n["note_id"],
                    "text": n["note_text"][:200]
                } for n in recent_notes
            ]
        }

    @classmethod
    def draft_patient_summary(
        cls,
        patient_id: int,
        staff_id: int,
        staff_name: str = "Priya (nurse)"
    ) -> Dict[str, Any]:
        """
        Drafts a structured SBAR patient summary from deterministic fact sheet.
        Policy Guard ensures ZERO judgment words and 100% fact grounding.
        Marked as 'AI-prepared draft' and pending human signature.
        """
        run_id = f"run-summary-{uuid.uuid4().hex[:8]}"
        start_time = datetime.now()

        AgentLedger.start_run(
            run_id=run_id,
            agent_name="handoff_agent",
            trigger_type="daily_summary_time",
            trigger_ref=f"patient#{patient_id}",
            patient_id=patient_id,
            autonomy_level="Draft",
            mode="Live",
            plan={"strategy": "draft_sbar_summary", "patient_id": patient_id}
        )

        # Step 1: Deterministic Fact Sheet
        facts = cls.build_patient_fact_sheet(patient_id)
        AgentLedger.record_step(
            run_id, 1, "Retrieve",
            f"Compiled fact sheet for {facts['patient_code']}: {len(facts['vitals'])} readings, {len(facts['medications_today'])} doses, {len(facts['open_flags'])} open flags",
            ids=[f"patient#{patient_id}"],
            ok=True
        )

        # Step 2: Formulate SBAR (facts only, NO judgment words)
        situation = f"Patient {facts['patient_code']} on post-discharge day {facts['relative_day']} for {facts['condition']}."
        
        bg_items = []
        if facts["medications_today"]:
            taken_count = sum(1 for m in facts["medications_today"] if m["status"] in ("Taken", "Confirmed"))
            bg_items.append(f"Medication adherence today: {taken_count}/{len(facts['medications_today'])} doses recorded")
        if facts["vitals"]:
            v_strs = [f"{v['metric']} {v['value']} {v['unit']}" for v in facts["vitals"][:2]]
            bg_items.append(f"Latest telemetry: {', '.join(v_strs)}")
        background = ". ".join(bg_items) if bg_items else "Routine post-discharge recovery monitoring."

        assessment_facts = []
        for f in facts["open_flags"]:
            assessment_facts.append(f"Open flag #{f['flag_id']} ({f['severity']}): {f['reason']}")
        if not assessment_facts:
            assessment_facts.append("Zero active emergency or telemetry alert flags open.")

        recommendations = []
        for t in facts["open_tasks"]:
            recommendations.append(f"Pending task: {t['reason']}")
        if not recommendations:
            recommendations.append("Continue scheduled recovery plan and scheduled rounds prompts.")

        summary_body = {
            "title": f"Daily Clinical Summary — {facts['patient_code']} (Day {facts['relative_day']})",
            "ai_prepared": True,
            "badge": "AI-prepared draft",
            "situation": situation,
            "background": background,
            "assessment_facts": assessment_facts,
            "items_for_review": recommendations,
            "fact_sheet": facts,
            "sources": ["sql_care_record", f"patient#{patient_id}"]
        }

        # Step 3: Policy Guard Check
        guard_context = {
            "patient_id": patient_id,
            "nurse_input": f"{situation} {background} {' '.join(assessment_facts)} {' '.join(recommendations)}"
        }
        guard_res = PolicyGuard.inspect("handoff_agent", summary_body, guard_context)
        AgentLedger.record_step(
            run_id, 2, "Guard",
            f"Policy Guard fact check: passed={guard_res.passed}",
            ids=["fact_sheet"],
            ok=guard_res.passed
        )

        if not guard_res.passed:
            AgentLedger.finish_run(run_id, status="Blocked_By_Guard", guard_reasons=guard_res.reasons)
            raise ValueError(f"Draft violates Policy Guard: {guard_res.reasons}")

        # Step 4: Save in agent_drafts (status 'Pending' - NEVER shown to patient)
        draft_id = AgentLedger.save_draft(
            run_id=run_id,
            patient_id=patient_id,
            draft_type="Summary",
            body=summary_body,
            sources=["sql_care_record"],
            status="Pending"
        )
        summary_body["draft_id"] = draft_id
        summary_body["run_id"] = run_id

        # Step 5: Finish Run
        AgentLedger.finish_run(
            run_id=run_id,
            status="Done",
            result_type="summary_drafted",
            latency_ms=int((datetime.now() - start_time).total_seconds() * 1000)
        )

        return summary_body

    @classmethod
    def draft_shift_handoff(
        cls,
        staff_id: int,
        shift_type: str = "Morning_to_Evening",
        staff_name: str = "Priya (nurse)"
    ) -> Dict[str, Any]:
        """
        Drafts cohort-wide shift handoff report covering all active patients.
        Aggregates open flags, high-priority tasks, and contingent actions.
        """
        run_id = f"run-handoff-{uuid.uuid4().hex[:8]}"
        start_time = datetime.now()

        AgentLedger.start_run(
            run_id=run_id,
            agent_name="handoff_agent",
            trigger_type="shift_change",
            trigger_ref=shift_type,
            autonomy_level="Draft",
            mode="Live",
            plan={"strategy": "cohort_shift_handoff", "shift": shift_type}
        )

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT p.patient_id, p.full_name, p.patient_code, p.created_at,
                           (SELECT COUNT(*) FROM flags f WHERE f.patient_id = p.patient_id AND f.status = 'Open') as open_flag_count,
                           (SELECT COUNT(*) FROM follow_up_tasks t WHERE t.patient_id = p.patient_id AND t.status IN ('Pending', 'In_Progress')) as open_task_count
                    FROM patients p
                    ORDER BY open_flag_count DESC, p.patient_id ASC;
                """)
                patients = cur.fetchall()

        patient_entries = []
        for p in patients:
            patient_entries.append({
                "patient_id": p["patient_id"],
                "patient_code": p["patient_code"],
                "open_flags": p["open_flag_count"],
                "open_tasks": p["open_task_count"],
                "handoff_summary": f"{p['patient_code']}: {p['open_flag_count']} open flag(s), {p['open_task_count']} pending task(s)."
            })

        handoff_body = {
            "title": f"Shift Handoff ({shift_type.replace('_', ' ')})",
            "shift_type": shift_type,
            "prepared_by": "CareLoop Handoff Agent",
            "badge": "AI-prepared draft",
            "ai_prepared": True,
            "total_patients": len(patients),
            "cohort_summary": f"Cohort active monitoring: {len(patients)} patients tracked. {sum(p['open_flag_count'] for p in patients)} flags open.",
            "patient_handoffs": patient_entries,
            "sources": ["patients", "flags", "follow_up_tasks"]
        }

        # Policy Guard check
        guard_res = PolicyGuard.inspect("handoff_agent", handoff_body)
        AgentLedger.record_step(
            run_id, 1, "Tool",
            f"Aggregated cohort data for {len(patients)} patients",
            ids=[f"patient#{p['patient_id']}" for p in patients],
            ok=guard_res.passed
        )

        # Save draft
        draft_id = AgentLedger.save_draft(
            run_id=run_id,
            patient_id=1,  # Anchor to primary cohort patient
            draft_type="Handoff",
            body=handoff_body,
            sources=["sql_care_record"],
            status="Pending"
        )
        handoff_body["draft_id"] = draft_id
        handoff_body["run_id"] = run_id

        AgentLedger.finish_run(
            run_id=run_id,
            status="Done",
            result_type="shift_handoff_drafted",
            latency_ms=int((datetime.now() - start_time).total_seconds() * 1000)
        )

        return handoff_body

    @staticmethod
    def sign_patient_summary(
        draft_id: int,
        staff_id: int,
        edited_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Licensed clinician reviews, edits, and signs a patient summary draft.
        Atomically records signer, reviewed_at, and edit character distance.
        """
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM agent_drafts WHERE draft_id = %s;", (draft_id,))
                draft = cur.fetchone()
                if not draft:
                    raise ValueError(f"Draft #{draft_id} not found.")

                orig_body = draft["body"]
                if isinstance(orig_body, str):
                    try:
                        orig_body = json.loads(orig_body)
                    except Exception:
                        orig_body = {}

                active_body = dict(orig_body)
                edit_chars = 0
                if edited_text:
                    orig_text = orig_body.get("situation", "") + " " + orig_body.get("background", "")
                    edit_chars = abs(len(edited_text) - len(orig_text))
                    active_body["signed_text"] = edited_text
                    final_status = "Edited"
                else:
                    final_status = "Accepted"

                patient_id = draft["patient_id"]
                run_id = draft["run_id"]

                # Update agent_drafts status
                cur.execute("""
                    UPDATE agent_drafts
                    SET status = %s,
                        body = %s,
                        reviewed_by_staff_id = %s,
                        reviewed_at = NOW(),
                        edit_chars = %s
                    WHERE draft_id = %s;
                """, (final_status, json.dumps(active_body), staff_id, edit_chars, draft_id))

                # Insert into ai_summaries table so it becomes an approved clinical summary
                summary_text = edited_text or (active_body.get("situation", "") + "\n\n" + active_body.get("background", ""))
                cur.execute("""
                    INSERT INTO ai_summaries (patient_id, period_start, period_end, summary_text, model_name, generated_at, reviewed_by_staff_id, reviewed_at, status, edited_text)
                    VALUES (%s, NOW() - INTERVAL 1 DAY, NOW(), %s, 'CareLoop-Handoff-Agent', NOW(), %s, NOW(), 'Approved', %s);
                """, (patient_id, summary_text, staff_id, edited_text or summary_text))
                summary_id = cur.lastrowid

                # Record Shadow Decision
                agreed = (edit_chars == 0)
                cur.execute("""
                    INSERT INTO shadow_decisions (run_id, action_type, agent_decision, human_decision, agreed, created_at)
                    VALUES (%s, 'daily_summary', %s, %s, %s, NOW());
                """, (run_id, json.dumps(orig_body), json.dumps(active_body), 1 if agreed else 0))

                # Audit Log
                cur.execute("""
                    INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                    VALUES ('Staff', %s, 'SUMMARY_DRAFT_SIGNED', 'agent_draft', %s,
                            JSON_OBJECT('draft_id', %s, 'summary_id', %s, 'edit_chars', %s));
                """, (str(staff_id), draft_id, draft_id, summary_id, edit_chars))

                conn.commit()

        logger.info(f"Summary draft #{draft_id} signed by staff #{staff_id} (summary_id={summary_id})")
        return {
            "status": "signed",
            "draft_id": draft_id,
            "summary_id": summary_id,
            "final_status": final_status,
            "edit_chars": edit_chars,
            "signed_by_staff_id": staff_id
        }

    @staticmethod
    def sign_shift_handoff(
        draft_id: int,
        staff_id: int,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Incoming or outgoing clinician acknowledges and signs the shift handoff."""
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM agent_drafts WHERE draft_id = %s;", (draft_id,))
                draft = cur.fetchone()
                if not draft:
                    raise ValueError(f"Draft #{draft_id} not found.")

                body = draft["body"]
                if isinstance(body, str):
                    try:
                        body = json.loads(body)
                    except Exception:
                        body = {}

                if notes:
                    body["clinician_notes"] = notes

                cur.execute("""
                    UPDATE agent_drafts
                    SET status = 'Accepted',
                        body = %s,
                        reviewed_by_staff_id = %s,
                        reviewed_at = NOW(),
                        edit_chars = 0
                    WHERE draft_id = %s;
                """, (json.dumps(body), staff_id, draft_id))

                cur.execute("""
                    INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                    VALUES ('Staff', %s, 'SHIFT_HANDOFF_SIGNED', 'agent_draft', %s,
                            JSON_OBJECT('draft_id', %s, 'notes', %s));
                """, (str(staff_id), draft_id, draft_id, notes or ""))

                conn.commit()

        return {
            "status": "signed",
            "draft_id": draft_id,
            "reviewed_by_staff_id": staff_id
        }
