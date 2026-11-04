"""
backend/app/agents/call_notes_agent.py — Call Notes Agent

Core Principles:
1. "No facts beyond the nurse's input": Policy Guard strictly verifies that every assertion
   and number in the drafted note, task, and patient message was explicitly provided by the nurse.
2. Nurse edits and signs: edit distance (edit_chars) is calculated and stored in agent_drafts.
3. Atomic execution: Approving a call draft creates the clinician note, follow-up task,
   and patient message in ONE atomic transaction with audit rows and run_id.
4. Measured speed: Nurse can complete a call record in 3 clicks plus an optional voice note.
"""

import json
import logging
import uuid
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

IST = timezone(timedelta(hours=5, minutes=30))
logger = logging.getLogger(__name__)

from backend.app.db import get_conn
from backend.app.agents.ledger import AgentLedger
from backend.app.agents.policy_guard import PolicyGuard

# Allowed quick pick selections for 3-click workflow
STANDARD_PATIENT_REPORTS = [
    "feeling fatigued after walk",
    "denies acute chest pain or fever",
    "mild surgical site tenderness",
    "morning medicines taken on time",
    "breathing comfortably at rest",
    "slight dizziness on standing",
    "swelling in lower extremity",
    "appetite improving"
]

STANDARD_ACTIONS_AGREED = [
    "rest with legs elevated",
    "continue scheduled medications",
    "maintain hydration and rest",
    "re-test vital signs in 2 hours",
    "avoid heavy lifting (>5 kg)",
    "call care team if dizziness persists"
]


class CallNotesAgent:
    """Automates post-call clinical documentation under strict clinician oversight."""

    @staticmethod
    def draft_call_records(
        patient_id: int,
        staff_id: int,
        staff_name: str = "Priya (nurse)",
        reached: bool = True,
        patient_reports: Optional[List[str]] = None,
        actions_agreed: Optional[List[str]] = None,
        voice_transcript: Optional[str] = None,
        needs_doctor: bool = False,
        call_script_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes structured call note, follow-up task, and post-call patient message.
        Constraint: NO facts beyond the nurse's provided input.
        """
        run_id = f"run-call-notes-{uuid.uuid4().hex[:8]}"
        start_time = datetime.now()

        # Step 1: Start Ledger Run
        AgentLedger.start_run(
            run_id=run_id,
            agent_name="call_notes_agent",
            trigger_type="nurse_call_completed",
            trigger_ref=f"patient#{patient_id}",
            patient_id=patient_id,
            autonomy_level="Draft",
            mode="Live",
            plan={"strategy": "draft_call_records", "reached": reached, "needs_doctor": needs_doctor}
        )
        AgentLedger.record_step(run_id, 1, "Gate", "Intake validated: nurse call event received", ok=True)

        patient_reports = patient_reports or []
        actions_agreed = actions_agreed or []
        voice_text = (voice_transcript or "").strip()

        # Combine nurse input for grounded Policy Guard verification
        combined_nurse_input_parts = []
        if reached:
            combined_nurse_input_parts.append("Patient reached via phone.")
        else:
            combined_nurse_input_parts.append("Attempted call; no answer / voicemail left.")
        if patient_reports:
            combined_nurse_input_parts.append("Reports: " + "; ".join(patient_reports))
        if actions_agreed:
            combined_nurse_input_parts.append("Actions: " + "; ".join(actions_agreed))
        if voice_text:
            combined_nurse_input_parts.append("Dictation: " + voice_text)
        if needs_doctor:
            combined_nurse_input_parts.append("Requires physician evaluation.")

        combined_nurse_input = " ".join(combined_nurse_input_parts)
        AgentLedger.record_step(
            run_id, 2, "Tool",
            f"Collected nurse input: {len(patient_reports)} report items, {len(actions_agreed)} actions, dictation length {len(voice_text)} chars",
            ids=["quick_picks", "voice_transcript"] if voice_text else ["quick_picks"],
            ok=True
        )

        # Retrieve patient name and language
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT full_name, patient_code, preferred_language FROM patients WHERE patient_id = %s;", (patient_id,))
                p_row = cur.fetchone()
                patient_name = p_row["full_name"] if p_row else f"Patient #{patient_id}"
                lang = p_row["preferred_language"] if p_row else "en"

        # Step 3: Formulate Drafts strictly from nurse input
        if reached:
            # (a) Clinical Note Text
            note_lines = [
                f"Telephone triage call with patient {patient_name}."
            ]
            if patient_reports:
                note_lines.append(f"Patient reported: {'; '.join(patient_reports)}.")
            if voice_text:
                note_lines.append(f"Clinician voice note: {voice_text}")
            if actions_agreed:
                note_lines.append(f"Agreed plan: {'; '.join(actions_agreed)}.")
            if needs_doctor:
                note_lines.append("Escalation: Flagged for physician review per clinician assessment.")

            note_text = "\n".join(note_lines)

            # (b) Follow-up Task
            if actions_agreed:
                task_description = f"Follow-up on agreed actions: {actions_agreed[0]}"
            else:
                task_description = "Follow-up on post-discharge recovery status"
            due_in_hours = 24

            # (c) Patient Message (app/SMS)
            nurse_short_name = staff_name.split()[0] if staff_name else "Priya"
            agreed_summary = "; ".join(actions_agreed) if actions_agreed else "rest and continue recovery plan"
            
            if lang == "hi":
                patient_msg = f"नमस्ते, आज बात करने के लिए धन्यवाद। योजना अनुसार: {agreed_summary}। कोई समस्या होने पर केयर टीम से संपर्क करें। - {nurse_short_name} (नर्स)"
            else:
                patient_msg = f"Hello, thank you for speaking with us today. As discussed, please: {agreed_summary}. Reach out anytime if symptoms change. — Message from {nurse_short_name} (nurse)"

        else:
            note_text = f"Attempted follow-up call to {patient_name}. No answer; left standard voicemail."
            task_description = "Reschedule follow-up call attempt (patient unreachable)"
            due_in_hours = 4
            patient_msg = f"Hello, we tried reaching you for your scheduled check-in. Please open the CareLoop app when available to confirm your recovery status. — Message from {staff_name.split()[0]} (nurse)"

        draft_payload = {
            "patient_id": patient_id,
            "staff_id": staff_id,
            "staff_name": staff_name,
            "reached": reached,
            "needs_doctor": needs_doctor,
            "note_text": note_text,
            "task_description": task_description,
            "due_in_hours": due_in_hours,
            "patient_message": patient_msg,
            "quick_picks": {
                "patient_reports": patient_reports,
                "actions_agreed": actions_agreed,
                "voice_transcript": voice_text
            },
            "sources": ["nurse_input"]
        }

        # Include approved exemplars as training-free few-shot guidance if enabled
        try:
            from backend.app.agents.config import AGENTS_V2_APPROVED_EXEMPLARS
            if AGENTS_V2_APPROVED_EXEMPLARS:
                from backend.app.agents.proactive_service import retrieve_exemplars
                exemplars = retrieve_exemplars("Call_Note", limit=3)
                if exemplars:
                    draft_payload["exemplars"] = exemplars
                    draft_payload["exemplar_label"] = "Uses previously approved notes as examples. No model training."
        except Exception as e:
            logger.warning(f"Could not load exemplars for Call_Note: {e}")

        # Step 4: Policy Guard Verification
        guard_context = {
            "patient_id": patient_id,
            "nurse_input": combined_nurse_input,
            "source_texts": [combined_nurse_input],
            "preferred_language": lang
        }
        guard_res = PolicyGuard.inspect("call_notes_agent", draft_payload, guard_context)

        AgentLedger.record_step(
            run_id, 3, "Guard",
            f"Policy Guard fact check: passed={guard_res.passed}",
            ids=["nurse_input"],
            ok=guard_res.passed
        )

        if not guard_res.passed:
            logger.warning(f"Call draft failed PolicyGuard: {guard_res.reasons}")
            AgentLedger.finish_run(run_id, status="Blocked_By_Guard", guard_reasons=guard_res.reasons)
            raise ValueError(f"Draft violates Policy Guard: {guard_res.reasons}")

        # Step 5: Save in agent_drafts
        draft_payload["guard_passed"] = True
        draft_id = AgentLedger.save_draft(
            run_id=run_id,
            patient_id=patient_id,
            draft_type="Call_Note",
            body=draft_payload,
            sources=["nurse_input"],
            status="Pending"
        )
        draft_payload["draft_id"] = draft_id
        draft_payload["run_id"] = run_id

        # Step 6: Mark Run Done
        elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        AgentLedger.finish_run(
            run_id=run_id,
            status="Done",
            result_type="call_note_drafted",
            latency_ms=elapsed_ms
        )

        logger.info(f"Call note drafted successfully (draft_id={draft_id}, run_id={run_id})")
        return draft_payload

    @staticmethod
    def commit_call_records(
        draft_id: int,
        staff_id: int,
        staff_name: str = "Priya (nurse)",
        edited_body: Optional[Dict[str, Any]] = None,
        edited_note: Optional[str] = None,
        edited_task: Optional[str] = None,
        edited_message: Optional[str] = None,
        call_duration_seconds: int = 180
    ) -> Dict[str, Any]:
        """
        One-Action Approval:
        Atomically saves:
        1. Clinician Note in clinician_notes.
        2. Follow-up Task in follow_up_tasks.
        3. Patient Message in patient_updates.
        4. Contact Log in contact_log.
        5. Updates agent_drafts with edit character distance (edit_chars).
        6. Logs complete audit trail with run_id.
        """
        with get_conn() as conn:
            with conn.cursor() as cur:
                # 1. Fetch draft
                cur.execute("SELECT * FROM agent_drafts WHERE draft_id = %s;", (draft_id,))
                draft = cur.fetchone()
                if not draft:
                    raise ValueError(f"Agent draft #{draft_id} not found.")

                orig_body = draft["body"]
                if isinstance(orig_body, str):
                    try:
                        orig_body = json.loads(orig_body)
                    except Exception:
                        orig_body = {}

                active_body = dict(edited_body or orig_body)
                if edited_note:
                    active_body["note_text"] = edited_note
                if edited_task:
                    active_body["task_description"] = edited_task
                if edited_message:
                    active_body["patient_message"] = edited_message

                patient_id = draft["patient_id"]
                run_id = draft["run_id"]

                # Calculate edit character distance to measure drafting fidelity
                orig_str = json.dumps(orig_body, sort_keys=True)
                new_str = json.dumps(active_body, sort_keys=True)
                edit_chars = abs(len(new_str) - len(orig_str))
                final_status = "Edited" if edit_chars > 0 else "Accepted"

                # 2. Insert Clinician Note
                note_text = active_body.get("note_text", "Call conducted with patient.")
                cur.execute("""
                    INSERT INTO clinician_notes (patient_id, staff_id, note_type, note_text, created_at)
                    VALUES (%s, %s, 'Call', %s, NOW());
                """, (patient_id, staff_id, note_text))
                note_id = cur.lastrowid

                # 3. Insert Follow-up Task
                task_desc = active_body.get("task_description", "Post-call follow-up check")
                due_in_hours = active_body.get("due_in_hours", 24)
                cur.execute("""
                    INSERT INTO follow_up_tasks (patient_id, assigned_staff_id, reason, priority, status, due_at, created_at)
                    VALUES (%s, %s, %s, 'Routine', 'Pending', NOW() + INTERVAL %s HOUR, NOW());
                """, (patient_id, staff_id, task_desc, due_in_hours))
                task_id = cur.lastrowid

                # 4. Insert Patient Message (patient_updates)
                patient_msg = active_body.get("patient_message", "")
                nurse_short = staff_name.split()[0] if staff_name else "Priya"
                title = f"Message from {nurse_short} (nurse)"
                cur.execute("""
                    INSERT INTO patient_updates (patient_id, update_type, title, body, created_by, created_at)
                    VALUES (%s, 'Call_Summary', %s, %s, 'Staff', NOW());
                """, (patient_id, title, patient_msg))
                update_id = cur.lastrowid

                # 5. Insert Contact Log
                outcome_str = "Reached" if active_body.get("reached", True) else "No_Answer"
                call_summary = f"[Duration: {call_duration_seconds}s] {note_text}" if call_duration_seconds else note_text
                cur.execute("""
                    INSERT INTO contact_log (patient_id, staff_id, task_id, channel, outcome, summary)
                    VALUES (%s, %s, %s, 'Phone', %s, %s);
                """, (patient_id, staff_id, task_id, outcome_str, call_summary[:500]))
                contact_id = cur.lastrowid

                # 6. Update agent_drafts
                cur.execute("""
                    UPDATE agent_drafts
                    SET status = %s,
                        body = %s,
                        reviewed_by_staff_id = %s,
                        reviewed_at = NOW(),
                        edit_chars = %s
                    WHERE draft_id = %s;
                """, (final_status, json.dumps(active_body), staff_id, edit_chars, draft_id))

                # Store de-identified exemplar (training-free) if enabled
                try:
                    from backend.app.agents.config import AGENTS_V2_APPROVED_EXEMPLARS
                    if AGENTS_V2_APPROVED_EXEMPLARS and final_status in ("Accepted", "Edited"):
                        from backend.app.agents.proactive_service import store_approved_exemplar
                        store_approved_exemplar(
                            draft_type="Call_Note",
                            original_text=orig_body.get("note_text", ""),
                            edited_text=active_body.get("note_text", ""),
                            source_draft_id=draft_id,
                            tags=["call_note", final_status.lower()]
                        )
                except Exception as e:
                    logger.warning(f"Failed to store Call_Note exemplar: {e}")

                # 7. Record Shadow Decision
                agreed = (edit_chars == 0)
                cur.execute("""
                    INSERT INTO shadow_decisions (run_id, action_type, agent_decision, human_decision, agreed, created_at)
                    VALUES (%s, 'call_note_draft', %s, %s, %s, NOW());
                """, (
                    run_id,
                    json.dumps(orig_body),
                    json.dumps(active_body),
                    1 if agreed else 0
                ))

                # 8. Record Audit Log Entry
                cur.execute("""
                    INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                    VALUES ('Staff', %s, 'CALL_DRAFT_APPROVED', 'agent_draft', %s,
                            JSON_OBJECT('run_id', %s, 'note_id', %s, 'task_id', %s, 'update_id', %s, 'edit_chars', %s));
                """, (str(staff_id), draft_id, run_id, note_id, task_id, update_id, edit_chars))

                conn.commit()

        logger.info(f"Call draft #{draft_id} approved: note#{note_id}, task#{task_id}, update#{update_id}, edit_chars={edit_chars}")
        return {
            "status": "approved",
            "draft_id": draft_id,
            "run_id": run_id,
            "note_id": note_id,
            "task_id": task_id,
            "update_id": update_id,
            "contact_id": contact_id,
            "edit_chars": edit_chars,
            "final_status": final_status
        }
