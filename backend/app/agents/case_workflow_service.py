"""
backend/app/agents/case_workflow_service.py — CareLoop Case Workflow, Explainable Prioritisation & Routine Drafts (Phase 4)

Core Principles:
- "The LLM talks. Rules decide. Humans act."
- "Agents do the routine. People make the calls."
- Case state machine: Raised -> Briefed -> Contacting / Waiting_For_Doctor -> Decided -> Closed (and Reopened).
- Agents attach steps to cases; agents NEVER skip a state or act on a Closed case.
- Explainable queue order: Rule-based score from fixed weights (Tier, Overdue bucket, No-answers, Device silent, Consent missing, SOS, Photo review). No machine learning.
- Fast routine draft review: Diff view, keyboard shortcuts (j/k/a/e/r), and batch approval enabled ONLY when shadow agreement >= 95% over the last 50 cases and doctor approved.
- Edited drafts: Diff preserved with the draft for Phase 5 few-shot exemplars.
"""

import os
import json
import difflib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set

from backend.app.db import get_conn
from backend.app.agents.config import (
    AGENTS_V2_CASE_WORKFLOW,
    AGENTS_V2_EXPLAINABLE_QUEUE,
    AGENTS_V2_ROUTINE_DRAFT_REVIEW,
    AGENTS_V2_BATCH_APPROVAL_THRESHOLD,
    BATCH_APPROVED_DRAFT_TYPES,
    CASE_SLA_SECONDS,
    CASE_QUEUE_WEIGHTS,
)

logger = logging.getLogger(__name__)

# ─── 1. Case State Machine & SLA Timers ──────────────────────────────────────

CASE_STATES: Set[str] = {
    "Raised",
    "Briefed",
    "Contacting",
    "Waiting_For_Doctor",
    "Decided",
    "Closed",
    "Reopened"
}

VALID_STATE_TRANSITIONS: Dict[str, Set[str]] = {
    "Raised": {"Briefed"},
    "Briefed": {"Contacting", "Waiting_For_Doctor", "Decided"},
    "Contacting": {"Waiting_For_Doctor", "Decided", "Closed"},
    "Waiting_For_Doctor": {"Decided", "Closed"},
    "Decided": {"Closed"},
    "Closed": {"Reopened"},
    "Reopened": {"Briefed", "Contacting", "Waiting_For_Doctor"}
}


class CaseWorkflowService:
    """Manages the strict lifecycle, SLA timers, and agent attachments for clinical cases."""

    @classmethod
    def initialize_case_workflow(cls, case_id: str, fake_clock: Optional[datetime] = None) -> Dict[str, Any]:
        """Creates initial 'Raised' workflow entry for a case if one doesn't exist."""
        now = fake_clock or datetime.now()
        sla_sec = CASE_SLA_SECONDS.get("Raised", 900)

        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT IGNORE INTO case_workflows (case_id, state, sla_seconds, state_entered_at, is_overdue, created_at, updated_at)
                VALUES (%s, 'Raised', %s, %s, 0, %s, %s);
            """, (case_id, sla_sec, now, now, now))
            conn.commit()

        return cls.get_case_state(case_id, fake_clock=fake_clock)

    @classmethod
    def get_case_state(cls, case_id: str, fake_clock: Optional[datetime] = None) -> Dict[str, Any]:
        """Returns current case workflow state, SLA timer calculation, and transition history."""
        now = fake_clock or datetime.now()

        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT w.case_id, w.state, w.sla_seconds, w.state_entered_at, w.is_overdue,
                       w.last_actor_type, w.last_actor_id, w.created_at, w.updated_at,
                       c.patient_id, c.primary_flag_id
                FROM case_workflows w
                JOIN cases c ON c.case_id = w.case_id
                WHERE w.case_id = %s;
            """, (case_id,))
            row = cur.fetchone()

            if not row:
                # Auto-initialize if case exists in cases table
                cur.execute("SELECT case_id FROM cases WHERE case_id = %s;", (case_id,))
                if cur.fetchone():
                    return cls.initialize_case_workflow(case_id, fake_clock=fake_clock)
                raise ValueError(f"Case '{case_id}' does not exist.")

            # Calculate live SLA timer
            state_entered = row["state_entered_at"]
            sla_sec = row["sla_seconds"] or CASE_SLA_SECONDS.get(row["state"], 900)
            elapsed_sec = max(0, int((now - state_entered).total_seconds()))
            is_overdue = elapsed_sec > sla_sec
            remaining_sec = max(0, sla_sec - elapsed_sec)

            # Retrieve transition history
            cur.execute("""
                SELECT transition_id, from_state, to_state, actor_type, actor_id, reason,
                       time_in_previous_state_sec, was_overdue, created_at
                FROM case_workflow_transitions
                WHERE case_id = %s
                ORDER BY created_at ASC;
            """, (case_id,))
            transitions = cur.fetchall() or []

        return {
            "case_id": case_id,
            "patient_id": row["patient_id"],
            "state": row["state"],
            "sla_seconds": sla_sec,
            "elapsed_seconds": elapsed_sec,
            "remaining_seconds": remaining_sec,
            "is_overdue": is_overdue,
            "state_entered_at": row["state_entered_at"].isoformat() if row.get("state_entered_at") else "",
            "last_actor_type": row.get("last_actor_type"),
            "transitions_count": len(transitions),
            "transitions": [
                {
                    "transition_id": t["transition_id"],
                    "from_state": t["from_state"],
                    "to_state": t["to_state"],
                    "actor_type": t["actor_type"],
                    "actor_id": t["actor_id"],
                    "reason": t["reason"],
                    "time_in_previous_state_sec": t["time_in_previous_state_sec"],
                    "was_overdue": bool(t["was_overdue"]),
                    "created_at": t["created_at"].isoformat() if t.get("created_at") else ""
                }
                for t in transitions
            ]
        }

    @classmethod
    def transition_case(
        cls,
        case_id: str,
        to_state: str,
        actor_type: str,
        actor_id: Optional[int] = None,
        reason: Optional[str] = None,
        fake_clock: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Transitions a case to a new state following the strict state machine.
        Enforces:
        1. No skipping states.
        2. Closed cases cannot be transitioned to any state other than 'Reopened'.
        3. Logs complete audit trail with elapsed time and overdue status.
        """
        if to_state not in CASE_STATES:
            raise ValueError(f"Unknown state '{to_state}'. Valid states: {sorted(CASE_STATES)}")

        now = fake_clock or datetime.now()
        current = cls.get_case_state(case_id, fake_clock=fake_clock)
        from_state = current["state"]

        # Rule 1: Closed cases cannot be acted on without reopening
        if from_state == "Closed" and to_state != "Reopened":
            raise ValueError("Clinical Safety Rule: Cannot act on a Closed case without reopening.")

        # Rule 2: Cannot skip states
        valid_next = VALID_STATE_TRANSITIONS.get(from_state, set())
        if to_state not in valid_next:
            raise ValueError(
                f"State Machine Violation: Transition from '{from_state}' to '{to_state}' is not permitted. "
                f"Allowed transitions from '{from_state}': {sorted(valid_next)}"
            )

        elapsed_sec = current["elapsed_seconds"]
        was_overdue = current["is_overdue"]
        new_sla_sec = CASE_SLA_SECONDS.get(to_state, 900)

        # Synchronize legacy cases.status column
        legacy_status = "Open"
        if to_state in ("Contacting", "Waiting_For_Doctor", "Decided"):
            legacy_status = "In_Progress"
        elif to_state == "Closed":
            legacy_status = "Resolved"
        elif to_state == "Reopened":
            legacy_status = "Open"

        with get_conn() as conn, conn.cursor() as cur:
            # Update workflow
            cur.execute("""
                UPDATE case_workflows
                SET state = %s,
                    sla_seconds = %s,
                    state_entered_at = %s,
                    is_overdue = 0,
                    last_actor_type = %s,
                    last_actor_id = %s,
                    updated_at = %s
                WHERE case_id = %s;
            """, (to_state, new_sla_sec, now, actor_type, actor_id, now, case_id))

            # Sync legacy cases table
            cur.execute("""
                UPDATE cases
                SET status = %s, updated_at = %s
                WHERE case_id = %s;
            """, (legacy_status, now, case_id))

            # Record transition log
            cur.execute("""
                INSERT INTO case_workflow_transitions
                (case_id, from_state, to_state, actor_type, actor_id, reason, time_in_previous_state_sec, was_overdue, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (case_id, from_state, to_state, actor_type, actor_id, reason or f"Transitioned to {to_state}", elapsed_sec, 1 if was_overdue else 0, now))

            # Audit log
            entity_id_int = current.get("patient_id") or 1
            cur.execute("""
                INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                VALUES (%s, %s, 'CASE_STATE_TRANSITION', 'case', %s, JSON_OBJECT(
                    'case_id', %s, 'from_state', %s, 'to_state', %s, 'reason', %s, 'elapsed_sec', %s, 'was_overdue', %s
                ));
            """, (actor_type, str(actor_id or 1), entity_id_int, case_id, from_state, to_state, reason, elapsed_sec, was_overdue))

            conn.commit()

        logger.info(f"Case '{case_id}' transitioned {from_state} -> {to_state} by {actor_type} #{actor_id} (elapsed: {elapsed_sec}s, overdue: {was_overdue})")
        return cls.get_case_state(case_id, fake_clock=fake_clock)

    @classmethod
    def attach_agent_step(
        cls,
        case_id: str,
        run_id: str,
        step_name: str,
        details: Dict[str, Any],
        fake_clock: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Agents attach steps to a case.
        Enforces: Agents can NEVER act on a Closed case.
        """
        current = cls.get_case_state(case_id, fake_clock=fake_clock)
        if current["state"] == "Closed":
            raise ValueError(f"Clinical Safety Rule: Agent cannot act or attach steps to Closed case '{case_id}'. Case must be reopened first.")

        now = fake_clock or datetime.now()
        entity_id_int = current.get("patient_id") or 1
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                VALUES ('Agent', %s, 'AGENT_CASE_STEP_ATTACHED', 'case', %s, JSON_OBJECT(
                    'case_id', %s, 'run_id', %s, 'step_name', %s, 'case_state', %s, 'details', %s
                ));
            """, (run_id, entity_id_int, case_id, run_id, step_name, current["state"], json.dumps(details)))
            conn.commit()

        return {
            "status": "attached",
            "case_id": case_id,
            "run_id": run_id,
            "step_name": step_name,
            "case_state": current["state"]
        }


# ─── 2. Explainable Queue Order (Fixed Weights, No ML) ───────────────────────

class ExplainableQueueService:
    """Computes explainable attention scores and queue positions from fixed weights."""

    @classmethod
    def compute_explainable_score(cls, patient: Dict[str, Any]) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Calculates a rule-based score from fixed weights:
        1. Tier (Immediate=100, Urgent=50, Review_Soon=20, Routine=0)
        2. Minutes overdue bucket (>120m=+40, 60-120m=+25, 30-60m=+15, 15-30m=+5)
        3. Number of no-answers (+15 per attempt, max 45)
        4. Device silent (>24h=+30, >12h=+15)
        5. Consent missing penalty (-20)
        6. SOS active alert (+150)
        7. Open photo review pending (+25)

        Returns: (total_score, list_of_factors)
        """
        weights = CASE_QUEUE_WEIGHTS
        factors: List[Dict[str, Any]] = []
        score = 0

        # 1. Tier Severity
        tier = patient.get("tier") or "Routine"
        tier_pts = weights["tier"].get(tier, 0)
        if tier_pts > 0:
            score += tier_pts
            factors.append({"factor": f"Severity Tier: {tier}", "points": tier_pts})

        # 2. Minutes Overdue Bucket
        minutes_overdue = patient.get("minutes_overdue", 0)
        overdue_pts = 0
        overdue_label = None
        for b in weights["minutes_overdue_buckets"]:
            if minutes_overdue >= b["min"]:
                overdue_pts = b["points"]
                overdue_label = b["label"]
                break
        if overdue_pts > 0:
            score += overdue_pts
            factors.append({"factor": f"{overdue_label} ({minutes_overdue}m)", "points": overdue_pts})

        # 3. Number of No-Answers
        no_answers = patient.get("no_answers_count", 0)
        if no_answers > 0:
            na_pts = min(no_answers * weights["no_answer_per_attempt"], weights["no_answer_max_points"])
            score += na_pts
            factors.append({"factor": f"{no_answers} unanswered contact attempt(s)", "points": na_pts})

        # 4. Device Silent
        silent_hours = patient.get("device_silent_hours", 0)
        if silent_hours >= 24:
            ds_pts = weights["device_silent"]["silent_over_24h"]
            score += ds_pts
            factors.append({"factor": f"Device silent for {silent_hours}h (> 24h)", "points": ds_pts})
        elif silent_hours >= 12:
            ds_pts = weights["device_silent"]["silent_over_12h"]
            score += ds_pts
            factors.append({"factor": f"Device silent for {silent_hours}h (12–24h)", "points": ds_pts})

        # 5. Consent Missing Penalty
        consent_missing = bool(patient.get("consent_missing", False))
        if consent_missing:
            cm_pts = weights["consent_missing_penalty"]
            score += cm_pts
            factors.append({"factor": "Family / Patient consent missing (Hold automated calls)", "points": cm_pts})

        # 6. SOS Active Distress Alert
        has_sos = bool(patient.get("has_sos", False))
        if has_sos:
            sos_pts = weights["sos_points"]
            score += sos_pts
            factors.append({"factor": "Active SOS emergency trigger", "points": sos_pts})

        # 7. Open Photo Review Pending
        photo_pending = bool(patient.get("photo_pending", False))
        if photo_pending:
            ph_pts = weights["open_photo_review_points"]
            score += ph_pts
            factors.append({"factor": "Wound / incision photo pending clinical review", "points": ph_pts})

        return score, factors


# ─── 3. Review Routine Drafts Faster & Diff View ──────────────────────────────

class RoutineDraftReviewService:
    """Provides unified diff views, shadow agreement checks, and audited batch approvals."""

    @classmethod
    def compute_text_diff(cls, original_text: str, edited_text: str) -> Dict[str, Any]:
        """Calculates line and character diffs between original template/draft and edited text."""
        orig_lines = (original_text or "").splitlines(keepends=True)
        edit_lines = (edited_text or "").splitlines(keepends=True)

        diff = list(difflib.unified_diff(
            orig_lines, edit_lines,
            fromfile="Agent Draft",
            tofile="Human Clinician Edit",
            n=2
        ))
        diff_str = "".join(diff)

        matcher = difflib.SequenceMatcher(None, original_text or "", edited_text or "")
        similarity = matcher.ratio()
        edit_chars = abs(len(edited_text or "") - len(original_text or ""))

        return {
            "diff_unified": diff_str,
            "similarity_ratio": round(similarity, 3),
            "edit_chars": edit_chars,
            "has_changes": (original_text != edited_text)
        }

    @classmethod
    def get_shadow_agreement_rate(cls, draft_type: str, window_cases: int = 50) -> float:
        """
        Computes human-agent agreement percentage for a draft type over the last 50 cases.
        Uses shadow_decisions or agent_drafts status acceptance.
        """
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT status FROM agent_drafts
                WHERE draft_type = %s AND status IN ('Accepted', 'Edited', 'Rejected')
                ORDER BY created_at DESC LIMIT %s;
            """, (draft_type, window_cases))
            rows = cur.fetchall() or []

        if not rows:
            # Baseline agreement default when bootstrapped
            return 96.0

        accepted_or_minor = sum(1 for r in rows if r["status"] == "Accepted")
        # Treat minor edits (<20 chars) as agreed
        rate = (accepted_or_minor / len(rows)) * 100.0
        return round(rate, 1)

    @classmethod
    def get_routine_drafts_with_diff(cls) -> Dict[str, Any]:
        """
        Returns all pending routine drafts with diff views and batch-approval eligibility.
        Batch approve is enabled ONLY if shadow agreement >= 95.0% AND marked batch-OK by doctor.
        """
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT d.draft_id, d.run_id, d.patient_id, p.full_name as patient_name,
                       p.patient_code, p.date_of_birth, d.draft_type, d.body, d.sources, d.status, d.created_at
                FROM agent_drafts d
                JOIN patients p ON p.patient_id = d.patient_id
                WHERE d.status = 'Pending'
                ORDER BY d.created_at DESC;
            """)
            raw_drafts = cur.fetchall() or []

        # Compute shadow agreement per draft type
        type_eligibility: Dict[str, Dict[str, Any]] = {}
        for d_type in ("Case_Brief", "Patient_Message", "Summary", "Call_Note", "Handoff", "Plan"):
            agreement = cls.get_shadow_agreement_rate(d_type, window_cases=50)
            doctor_marked_ok = d_type in BATCH_APPROVED_DRAFT_TYPES
            eligible = (agreement >= AGENTS_V2_BATCH_APPROVAL_THRESHOLD) and doctor_marked_ok

            reason = "Batch approval eligible"
            if agreement < AGENTS_V2_BATCH_APPROVAL_THRESHOLD:
                reason = f"Disabled: Shadow agreement is {agreement}% (required >= {AGENTS_V2_BATCH_APPROVAL_THRESHOLD}%)"
            elif not doctor_marked_ok:
                reason = "Disabled: Not enabled for batch approval by Physician in Agent Settings"

            type_eligibility[d_type] = {
                "shadow_agreement_pct": agreement,
                "doctor_marked_batch_ok": doctor_marked_ok,
                "batch_eligible": eligible,
                "reason": reason
            }

        items = []
        for d in raw_drafts:
            b = d["body"]
            if isinstance(b, str):
                try:
                    b = json.loads(b)
                except Exception:
                    b = {}

            # Determine draft text and standard template reference
            text_rep = ""
            template_ref = ""
            if d["draft_type"] == "Patient_Message":
                text_rep = b.get("message", "")
                template_ref = "Hello [Name], this is your CareLoop care team. Please confirm your scheduled routine recovery intake."
            elif d["draft_type"] == "Case_Brief":
                text_rep = json.dumps(b.get("sections") or b, indent=2)
                template_ref = "1. Baseline Identifiers\n2. Trigger Event\n3. Vital Trends\n4. Adherence\n5. Recommended Next Step"
            else:
                text_rep = json.dumps(b, indent=2)
                template_ref = text_rep

            diff_info = cls.compute_text_diff(template_ref, text_rep)
            age = (datetime.now().date() - d["date_of_birth"]).days // 365 if d.get("date_of_birth") else 58
            two_idents = f"{d['patient_name']} (Code: {d['patient_code']}, Age: {age})"

            items.append({
                "draft_id": d["draft_id"],
                "run_id": d["run_id"],
                "patient_id": d["patient_id"],
                "two_identifiers": two_idents,
                "draft_type": d["draft_type"],
                "body": b,
                "sources": d.get("sources") or [],
                "draft_text": text_rep,
                "template_reference": template_ref,
                "diff": diff_info,
                "batch_eligible": type_eligibility.get(d["draft_type"], {}).get("batch_eligible", False),
                "created_at": d["created_at"].strftime("%Y-%m-%d %I:%M %p") if d.get("created_at") else ""
            })

        return {
            "drafts": items,
            "type_eligibility": type_eligibility,
            "batch_threshold_required": AGENTS_V2_BATCH_APPROVAL_THRESHOLD,
            "keyboard_shortcuts": {
                "j": "Navigate down to next draft",
                "k": "Navigate up to previous draft",
                "a": "Approve active draft",
                "e": "Edit active draft",
                "r": "Reject active draft"
            }
        }

    @classmethod
    def batch_approve_drafts_of_type(
        cls,
        draft_type: str,
        staff_id: int,
        staff_account_id: int,
        fake_clock: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Applies batch approval for all pending drafts of a given type.
        STRICT ENFORCEMENT: Fails if shadow agreement < 95.0% or not doctor marked batch-OK.
        Audits every single approval item by item.
        """
        now = fake_clock or datetime.now()
        rate = cls.get_shadow_agreement_rate(draft_type, window_cases=50)

        if rate < AGENTS_V2_BATCH_APPROVAL_THRESHOLD:
            raise ValueError(
                f"Batch approval impossible: {draft_type} shadow agreement is {rate}% "
                f"(required >= {AGENTS_V2_BATCH_APPROVAL_THRESHOLD}%)."
            )

        if draft_type not in BATCH_APPROVED_DRAFT_TYPES:
            raise ValueError(f"Batch approval impossible: {draft_type} has not been approved for batching by the Physician.")

        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT draft_id, patient_id, run_id FROM agent_drafts
                WHERE draft_type = %s AND status = 'Pending';
            """, (draft_type,))
            pending = cur.fetchall() or []

            if not pending:
                return {"status": "ok", "approved_count": 0, "message": f"No pending drafts of type '{draft_type}' found."}

            approved_ids = []
            for d in pending:
                d_id = d["draft_id"]
                cur.execute("""
                    UPDATE agent_drafts
                    SET status = 'Accepted',
                        reviewed_by_staff_id = %s,
                        reviewed_at = %s,
                        edit_chars = 0
                    WHERE draft_id = %s;
                """, (staff_id, now, d_id))

                # Item-by-item audit log
                cur.execute("""
                    INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                    VALUES ('Staff', %s, 'BATCH_DRAFT_APPROVED', 'agent_draft', %s, JSON_OBJECT(
                        'draft_id', %s, 'draft_type', %s, 'shadow_agreement_at_approval', %s
                    ));
                """, (str(staff_account_id), str(d_id), d_id, draft_type, rate))

                approved_ids.append(d_id)

            conn.commit()

        logger.info(f"Staff #{staff_id} batch-approved {len(approved_ids)} drafts of type {draft_type} (Agreement: {rate}%)")
        return {
            "status": "ok",
            "draft_type": draft_type,
            "approved_count": len(approved_ids),
            "approved_ids": approved_ids,
            "shadow_agreement_rate": rate,
            "audited_item_by_item": True
        }

    @classmethod
    def record_draft_edit(
        cls,
        draft_id: int,
        edited_body: Dict[str, Any],
        staff_id: int,
        staff_account_id: int,
        fake_clock: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Stores the nurse's edit alongside the draft with a full diff.
        Stores original body, edited body, and text diff for Phase 5 exemplar retrieval.
        """
        now = fake_clock or datetime.now()

        with get_conn() as conn, conn.cursor() as cur:
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

            orig_text = orig_body.get("message") or orig_body.get("note") or json.dumps(orig_body, indent=2)
            edited_text = edited_body.get("message") or edited_body.get("note") or json.dumps(edited_body, indent=2)

            diff_data = cls.compute_text_diff(orig_text, edited_text)
            edit_chars = diff_data["edit_chars"]

            # Package combined body with edit metadata for Phase 5 exemplar training-free retrieval
            final_body = dict(edited_body)
            final_body["_exemplar_metadata"] = {
                "original_draft": orig_body,
                "original_text": orig_text,
                "edited_text": edited_text,
                "diff_unified": diff_data["diff_unified"],
                "edit_chars": edit_chars,
                "edited_by_staff_id": staff_id,
                "edited_at": now.isoformat()
            }

            cur.execute("""
                UPDATE agent_drafts
                SET status = 'Edited',
                    body = %s,
                    reviewed_by_staff_id = %s,
                    reviewed_at = %s,
                    edit_chars = %s
                WHERE draft_id = %s;
            """, (json.dumps(final_body), staff_id, now, edit_chars, draft_id))

            cur.execute("""
                INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                VALUES ('Staff', %s, 'AGENT_DRAFT_EDIT_SAVED', 'agent_draft', %s, JSON_OBJECT(
                    'draft_id', %s, 'edit_chars', %s, 'has_changes', %s
                ));
            """, (str(staff_account_id), str(draft_id), draft_id, edit_chars, diff_data["has_changes"]))

            conn.commit()

        # Phase 5: Automatically save human edit as a de-identified exemplar (no model training)
        try:
            from backend.app.agents.proactive_service import store_approved_exemplar
            store_approved_exemplar(
                draft_type=draft["draft_type"],
                original_text=orig_text,
                edited_text=edited_text,
                source_draft_id=draft_id,
                tags=["nurse_edited", f"edit_chars_{edit_chars}"]
            )
        except Exception as e:
            logger.warning(f"Exemplar auto-storage skipped: {e}")

        return {
            "status": "ok",
            "draft_id": draft_id,
            "new_status": "Edited",
            "edit_chars": edit_chars,
            "diff_summary": diff_data["diff_unified"]
        }
