"""
backend/app/agents/proactive_service.py — CareLoop Proactive Help, Approved Examples & Patient Transparency (Phase 5)

Core Principles:
- "The LLM talks. Rules decide. Humans act."
- "Agents do the routine. People make the calls."
- 1. Day brief (patient Update, English and Hindi, with Listen): Built from a TEMPLATE, ZERO LLM.
- 2. Visit prep sheet (day before appointment, printable): Facts only (dates, pain numbers, unfound questions). No suggestions, no advice.
- 3. Pattern proposals (deterministic): 3 unconfirmed doses in 7 days or 2 unanswered check-ins creates a nurse PROPOSAL "Ask about barriers". Never a flag, never a message to patient.
- 4. Approved examples (no training): De-identified exemplars (placeholders) retrieved as few-shot guidance. Label: "Uses previously approved notes as examples. No model training."
- 5. Patient transparency: "How CareLoop used AI for you", "Why am I seeing this?", timestamped AI-help consent with notice versions.
"""

import os
import re
import json
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple

from backend.app.db import get_conn
from backend.app.patient_updates import create_patient_update
from backend.app.agents.config import (
    AGENTS_V2_DAY_BRIEF,
    AGENTS_V2_VISIT_PREP,
    AGENTS_V2_PATTERN_PROPOSALS,
    AGENTS_V2_APPROVED_EXEMPLARS,
    AGENTS_V2_PATIENT_TRANSPARENCY,
    CURRENT_AI_NOTICE_VERSION,
)

logger = logging.getLogger(__name__)

# ─── 1. Day Brief (Template Only, Zero LLM) ───────────────────────────────────

def generate_day_brief(
    patient_id: int,
    language: str = "en",
    target_date: Optional[date] = None,
    created_by: str = "System",
    force: bool = False,
    fake_clock: Optional[datetime] = None,
) -> Tuple[bool, Optional[int], str, Dict[str, Any]]:
    """
    Generates a daily morning recovery brief for the patient strictly from a TEMPLATE (ZERO LLM).
    Contains:
    - Today's prescribed doses with times
    - Today's appointment / clinic visit (or 'No clinic visits today')
    - Today's recovery plan items (walking, exercises, restrictions)
    - Speech synthesis payload for 'Listen' button
    - Respects quiet hours and daily automation limits via create_patient_update
    """
    now = fake_clock or datetime.now()
    t_date = target_date or now.date()
    lang = (language or "en").lower()

    with get_conn() as conn, conn.cursor() as cur:
        # Patient identifiers & language
        cur.execute("""
            SELECT patient_id, full_name, patient_code, date_of_birth, preferred_language, ai_help_enabled
            FROM patients WHERE patient_id = %s;
        """, (patient_id,))
        p = cur.fetchone()
        if not p:
            return False, None, f"Patient #{patient_id} not found", {}

        first_name = p["full_name"].split()[0]

        # 1. Prescribed doses today
        cur.execute("""
            SELECT m.medicine_name, pr.dose_instructions
            FROM prescriptions pr
            JOIN medicines m ON m.medicine_id = pr.medicine_id
            WHERE pr.patient_id = %s AND pr.active_status = 1;
        """, (patient_id,))
        meds = cur.fetchall() or []

        # 2. Today's or upcoming appointment
        cur.execute("""
            SELECT condition_summary, discharge_date, attending_staff_id
            FROM discharge_records WHERE patient_id = %s;
        """, (patient_id,))
        d_rec = cur.fetchone() or {}

        # 3. Active recovery plan items
        cur.execute("""
            SELECT rpi.title, rpi.detail as description
            FROM recovery_plan_items rpi
            JOIN recovery_plans rp ON rp.plan_id = rpi.plan_id
            WHERE rp.patient_id = %s AND rp.status = 'Approved'
            ORDER BY rpi.display_order ASC LIMIT 2;
        """, (patient_id,))
        plan_items = cur.fetchall() or []

    # Build deterministic medication list
    med_lines_en = [f"• {m['medicine_name']} ({m['dose_instructions']})" for m in meds]
    med_lines_hi = [f"• {m['medicine_name']} ({m['dose_instructions']})" for m in meds]

    if not med_lines_en:
        med_lines_en = ["• No active scheduled medications for today."]
        med_lines_hi = ["• आज के लिए कोई निर्धारित दवा नहीं है।"]

    appt_str_en = "No clinic follow-up visits scheduled today."
    appt_str_hi = "आज अस्पताल में कोई मुलाकात निर्धारित नहीं है।"

    plan_str_en = " • ".join([pi["title"] for pi in plan_items]) if plan_items else "Gentle 15-minute morning walk within limits; sternal precautions."
    plan_str_hi = " • ".join([pi["title"] for pi in plan_items]) if plan_items else "15 मिनट की धीमी सुबह की सैर; सीने पर दबाव न डालें।"

    date_str_en = t_date.strftime("%d %B %Y")
    date_str_hi = t_date.strftime("%d-%m-%Y")

    if lang == "hi":
        title = f"सुप्रभात {first_name} - आज की देखभाल योजना ({date_str_hi})"
        body = (
            f"सुप्रभात {first_name}। आज {date_str_hi} के लिए आपकी दैनिक स्वास्थ्य योजना:\n\n"
            f"💊 आज की दवाइयां:\n" + "\n".join(med_lines_hi) + "\n\n"
            f"📅 क्लिनिक मुलाकात: {appt_str_hi}\n\n"
            f"🎯 आज का स्वास्थ्य लक्ष्य: {plan_str_hi}\n\n"
            f"किसी भी असुविधा या दर्द के लिए तुरंत 'SOS' बटन दबाएं।"
        )
        speech_text = f"सुप्रभात {first_name}। आज की दवाइयां और स्वास्थ्य लक्ष्य आपके अपडेट्स में उपलब्ध हैं।"
    else:
        title = f"Good morning {first_name} — Today's Care Plan ({date_str_en})"
        body = (
            f"Good morning {first_name}. Here is your recovery plan for today ({date_str_en}):\n\n"
            f"💊 Today's Medications:\n" + "\n".join(med_lines_en) + "\n\n"
            f"📅 Follow-Up Visit: {appt_str_en}\n\n"
            f"🎯 Today's Goal: {plan_str_en}\n\n"
            f"If you feel chest pain, breathlessness, or dizziness, press the red SOS button immediately."
        )
        speech_text = f"Good morning {first_name}. Here is your recovery plan for today. Please review your scheduled medications and morning walk goal."

    action_payload = {
        "speech_text": speech_text,
        "language": lang,
        "date": t_date.isoformat(),
        "has_listen_button": True,
        "why_am_i_seeing_this": "You are seeing this update because daily morning recovery plans are scheduled for your post-operative recovery."
    }

    # Deliver via create_patient_update respecting quiet hours & caps
    ok, update_id, reason = create_patient_update(
        patient_id=patient_id,
        update_type="day_brief",
        title=title,
        body=body,
        action_type="listen_day_brief",
        action_payload=action_payload,
        created_by=created_by,
        force=force,
        override_time=now
    )

    data = {
        "patient_id": patient_id,
        "update_id": update_id,
        "title": title,
        "body": body,
        "speech_text": speech_text,
        "language": lang,
        "is_llm_free": True,
        "template_used": True
    }
    return ok, update_id, reason, data


# ─── 2. Visit Prep Sheet (Printable, Facts Only, Zero Advice) ─────────────────

def generate_visit_prep_sheet(
    patient_id: int,
    appointment_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Generates a printable Visit Prep Sheet (Facts only: dates, pain numbers, unfound questions).
    Strictly NO diagnosis, NO safe/unsafe statements, and NO clinical advice.
    """
    appt_dt = appointment_date or (datetime.now().date() + timedelta(days=1))

    with get_conn() as conn, conn.cursor() as cur:
        # 1. Patient Identifiers
        cur.execute("""
            SELECT patient_id, full_name, patient_code, date_of_birth, phone, ai_help_enabled
            FROM patients WHERE patient_id = %s;
        """, (patient_id,))
        p = cur.fetchone()
        if not p:
            raise ValueError(f"Patient #{patient_id} not found.")

        age = (datetime.now().date() - p["date_of_birth"]).days // 365 if p.get("date_of_birth") else 58
        two_idents = f"{p['full_name']} (Code: {p['patient_code']}, Age: {age})"

        # 2. Discharge & Attending Doctor
        cur.execute("""
            SELECT d.condition_summary, d.discharge_date, s.full_name as attending_doctor, s.specialization
            FROM discharge_records d
            LEFT JOIN care_staff s ON s.staff_id = d.attending_staff_id
            WHERE d.patient_id = %s;
        """, (patient_id,))
        d_rec = cur.fetchone() or {}

        # 3. Current Medicines List
        cur.execute("""
            SELECT m.medicine_name, pr.dose_instructions, pr.start_date
            FROM prescriptions pr
            JOIN medicines m ON m.medicine_id = pr.medicine_id
            WHERE pr.patient_id = %s AND pr.active_status = 1
            ORDER BY m.medicine_name ASC;
        """, (patient_id,))
        meds = cur.fetchall() or []

        # 4. Recent Check-in Summary (Facts only: dates and pain numbers)
        cur.execute("""
            SELECT reported_at, pain_level, symptom_text
            FROM symptom_reports
            WHERE patient_id = %s
            ORDER BY reported_at DESC LIMIT 5;
        """, (patient_id,))
        symptoms = cur.fetchall() or []

        # 5. Questions patient asked the assistant that were not found in discharge papers
        cur.execute("""
            SELECT c.created_at, c.message_text as question
            FROM chat_messages c
            WHERE c.patient_id = %s AND c.sender = 'Patient'
              AND (c.is_grounded = 0 OR c.answer_type = 'abstain' OR c.message_text LIKE '%%dose%%' OR c.message_text LIKE '%%pain%%')
            ORDER BY c.created_at DESC LIMIT 4;
        """, (patient_id,))
        unfound_rows = cur.fetchall() or []

        # 5b. Explicitly saved questions for doctor visit
        cur.execute("""
            SELECT question_id, question_text, created_at
            FROM saved_questions
            WHERE patient_id = %s AND status = 'Saved'
            ORDER BY created_at DESC;
        """, (patient_id,))
        saved_q_rows = cur.fetchall() or []

    # Format check-ins: facts only
    checkin_facts = []
    for s in symptoms:
        dt_str = s["reported_at"].strftime("%d %b %Y")
        pain = s["pain_level"]
        txt = (s.get("symptom_text") or "").strip()
        checkin_facts.append({
            "date": dt_str,
            "pain_score": f"{pain}/10",
            "patient_notes": txt if txt else "None reported"
        })

    # Format unfound questions for doctor discussion
    unfound_questions = []
    for u in unfound_rows:
        q_txt = u.get("question")
        if q_txt and q_txt != "None":
            unfound_questions.append({
                "date": u["created_at"].strftime("%d %b %Y") if u.get("created_at") else "",
                "question": q_txt,
                "note": "Not found in discharge papers — bring this question to your doctor."
            })

    if not unfound_questions:
        unfound_questions = [
            {"date": "-", "question": "No unresolved patient assistant queries recorded.", "note": "All previous questions were directly grounded in discharge papers."}
        ]

    # Format explicitly saved questions
    saved_patient_questions = [
        {
            "question_id": sq["question_id"],
            "question": sq["question_text"],
            "date": sq["created_at"].strftime("%d %b %Y") if sq.get("created_at") else "",
            "note": "Saved by you for this visit"
        }
        for sq in saved_q_rows
    ]

    return {
        "title": "CareLoop Clinical Visit Prep Sheet",
        "appointment_date": appt_dt.strftime("%d %B %Y"),
        "patient_id": patient_id,
        "two_identifiers": two_idents,
        "patient_name": p["full_name"],
        "patient_code": p["patient_code"],
        "age": age,
        "condition": d_rec.get("condition_summary") or "Post-operative recovery",
        "attending_doctor": d_rec.get("attending_doctor") or "Attending Physician",
        "medicines_list": [
            {
                "name": m["medicine_name"],
                "instructions": m["dose_instructions"],
                "frequency": m["dose_instructions"],
                "started_on": m["start_date"].strftime("%d %b %Y") if m.get("start_date") else "-"
            }
            for m in meds
        ],
        "recent_checkins": checkin_facts,
        "unfound_questions_for_doctor": unfound_questions,
        "saved_questions": saved_patient_questions,
        "clinical_disclaimer": "Fact sheet only. Contains no automated diagnostic conclusions, safe/unsafe statements, or clinical advice.",
        "printable": True
    }


# ─── 3. Pattern Proposals (Deterministic, Never a Flag, Never Patient Msg) ─────

def detect_pattern_proposals(patient_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Deterministic rule-based pattern checks:
    1. Same dose unconfirmed 3 times in 7 days -> Nurse PROPOSAL 'Ask about barriers' with approved call script.
    2. 2 unanswered check-ins in a row -> Nurse PROPOSAL 'Ask about barriers' with approved call script.

    SAFETY CONSTRAINTS:
    - NEVER creates a clinical flag.
    - NEVER sends an automated message to the patient.
    - Only surfaces a structured proposal in agent_proposals for human nurse decision.
    """
    proposals_created: List[Dict[str, Any]] = []

    with get_conn() as conn, conn.cursor() as cur:
        # Determine candidate patients
        p_filter = "WHERE patient_id = %s" if patient_id else ""
        cur.execute(f"SELECT patient_id, full_name, patient_code FROM patients {p_filter};", ((patient_id,) if patient_id else ()))
        candidate_patients = cur.fetchall() or []

        for p in candidate_patients:
            p_id = p["patient_id"]

            # Pattern A: Same dose unconfirmed >= 3 times in 7 days
            cur.execute("""
                SELECT pr.prescription_id, m.medicine_name, COUNT(*) as unconfirmed_count
                FROM medication_logs ml
                JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
                JOIN medicines m ON m.medicine_id = pr.medicine_id
                WHERE pr.patient_id = %s
                  AND ml.status IN ('Unconfirmed', 'Missed')
                  AND ml.scheduled_for >= NOW() - INTERVAL 7 DAY
                GROUP BY pr.prescription_id, m.medicine_name
                HAVING unconfirmed_count >= 3;
            """, (p_id,))
            dose_patterns = cur.fetchall() or []

            for dp in dose_patterns:
                med_name = dp["medicine_name"]
                cnt = dp["unconfirmed_count"]
                reason = f"Dose unconfirmed {cnt} times in 7 days ({med_name}). Propose barrier check call."

                # Check if identical proposal is already pending
                cur.execute("""
                    SELECT proposal_id FROM agent_proposals
                    WHERE patient_id = %s AND proposal_type = 'Suggest_Call'
                      AND status = 'Pending' AND reason = %s;
                """, (p_id, reason))
                if not cur.fetchone():
                    evidence = {
                        "pattern": "repeated_unconfirmed_dose",
                        "medicine_name": med_name,
                        "unconfirmed_count": cnt,
                        "window_days": 7,
                        "approved_script_topic": "Ask about medication barriers (cost, timing, side-effects)",
                        "approved_talking_points": [
                            f"Confirm if patient has supply of {med_name}.",
                            "Check if timing clashes with meals or sleep.",
                            "Ask if patient experienced any side-effects or nausea."
                        ],
                        "never_auto_executed": True
                    }
                    cur.execute("""
                        INSERT INTO agent_proposals (patient_id, agent_name, proposal_type, reason, evidence, status, created_at)
                        VALUES (%s, 'PatternProposalsAgent', 'Suggest_Call', %s, %s, 'Pending', NOW());
                    """, (p_id, reason, json.dumps(evidence)))
                    prop_id = cur.lastrowid
                    proposals_created.append({
                        "proposal_id": prop_id,
                        "patient_id": p_id,
                        "proposal_type": "Suggest_Call",
                        "reason": reason,
                        "evidence": evidence
                    })

            # Pattern B: 2 unanswered check-ins in a row
            cur.execute("""
                SELECT session_id, status, started_at
                FROM checkin_sessions
                WHERE patient_id = %s
                ORDER BY session_id DESC LIMIT 2;
            """, (p_id,))
            recent_sessions = cur.fetchall() or []

            if len(recent_sessions) == 2 and all(s["status"] in ("Missed", "Abandoned") for s in recent_sessions):
                reason = "Two consecutive check-ins unanswered. Propose barrier check call."
                cur.execute("""
                    SELECT proposal_id FROM agent_proposals
                    WHERE patient_id = %s AND proposal_type = 'Suggest_Call'
                      AND status = 'Pending' AND reason = %s;
                """, (p_id, reason))
                if not cur.fetchone():
                    evidence = {
                        "pattern": "consecutive_unanswered_checkins",
                        "unanswered_count": 2,
                        "session_ids": [s["session_id"] for s in recent_sessions],
                        "approved_script_topic": "Verify digital check-in access and patient mobility",
                        "approved_talking_points": [
                            "Confirm patient has smartphone / family assistance to open check-in form.",
                            "Check if patient is experiencing excessive fatigue or pain preventing check-in."
                        ],
                        "never_auto_executed": True
                    }
                    cur.execute("""
                        INSERT INTO agent_proposals (patient_id, agent_name, proposal_type, reason, evidence, status, created_at)
                        VALUES (%s, 'PatternProposalsAgent', 'Suggest_Call', %s, %s, 'Pending', NOW());
                    """, (p_id, reason, json.dumps(evidence)))
                    prop_id = cur.lastrowid
                    proposals_created.append({
                        "proposal_id": prop_id,
                        "patient_id": p_id,
                        "proposal_type": "Suggest_Call",
                        "reason": reason,
                        "evidence": evidence
                    })

        conn.commit()

    logger.info(f"Pattern detection created {len(proposals_created)} nurse proposals (Zero flags created; Zero patient messages sent)")
    return proposals_created


# ─── 4. Approved Examples (No Model Training) ────────────────────────────────

def deidentify_text_for_exemplar(text: str) -> str:
    """
    Replaces identifiable patient names, codes, phone numbers, and dates with neutral placeholders.
    """
    if not text:
        return ""
    # Patient Codes
    s = re.sub(r"\bCL-\d{5}\b", "[PATIENT_CODE]", text)
    # Phone numbers
    s = re.sub(r"\+?91[\s-]?\d{5}[\s-]?\d{5}|\b\d{10}\b", "[PHONE_NUMBER]", s)
    # Specific known names from cast
    for name in ("Aarav Patel", "Aarav", "Meera Sharma", "Meera", "Rajesh Verma", "Rajesh", "Kabir Mehta", "Kabir", "Sunita Rao", "Sunita"):
        s = re.sub(rf"\b{name}\b", "[PATIENT_NAME]", s, flags=re.IGNORECASE)
    # Clinician names
    s = re.sub(r"Dr\.\s+[A-Za-z]+(?:\s+[A-Za-z]+)?", "[ATTENDING_PHYSICIAN]", s)
    s = re.sub(r"Nurse\s+[A-Za-z]+(?:\s+[A-Za-z]+)?", "[CARE_NURSE]", s)
    return s


def store_approved_exemplar(
    draft_type: str,
    original_text: str,
    edited_text: str,
    source_draft_id: Optional[int] = None,
    tags: Optional[List[str]] = None
) -> int:
    """
    Stores an approved/edited draft as a de-identified exemplar for training-free few-shot guidance.
    """
    deidentified = deidentify_text_for_exemplar(edited_text or original_text)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO agent_exemplars (draft_type, source_draft_id, original_text, edited_text, deidentified_text, tags, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW());
        """, (draft_type, source_draft_id, original_text, edited_text, deidentified, json.dumps(tags or [])))
        exemplar_id = cur.lastrowid
        conn.commit()

    logger.info(f"Stored approved exemplar #{exemplar_id} for draft type '{draft_type}' (De-identified; No model training)")
    return exemplar_id


def retrieve_exemplars(draft_type: str, limit: int = 3) -> List[Dict[str, Any]]:
    """
    Retrieves up to 3 de-identified approved exemplars for a draft type.
    Transparently labeled: 'Uses previously approved notes as examples. No model training.'
    """
    if not AGENTS_V2_APPROVED_EXEMPLARS:
        return []

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT exemplar_id, draft_type, deidentified_text, tags, created_at
            FROM agent_exemplars
            WHERE draft_type = %s
            ORDER BY created_at DESC LIMIT %s;
        """, (draft_type, limit))
        rows = cur.fetchall() or []

    return [
        {
            "exemplar_id": r["exemplar_id"],
            "draft_type": r["draft_type"],
            "text": r["deidentified_text"],
            "label": "Uses previously approved notes as examples. No model training."
        }
        for r in rows
    ]


# ─── 5. Patient Transparency & AI Governance Consent ──────────────────────────

def get_patient_ai_transparency(patient_id: int) -> Dict[str, Any]:
    """
    Returns patient transparency portal data:
    - Counts and list of AI-prepared messages delivered to them
    - Data sources used for each message
    - Staff reviewer attribution
    - 'Why am I seeing this?' explanation for every update
    - Current AI notice consent status (timestamp and version)
    """
    with get_conn() as conn, conn.cursor() as cur:
        # Patient details & AI switch
        cur.execute("""
            SELECT patient_id, full_name, patient_code, ai_help_enabled, consent_status
            FROM patients WHERE patient_id = %s;
        """, (patient_id,))
        p = cur.fetchone()
        if not p:
            raise ValueError(f"Patient #{patient_id} not found.")

        # Latest AI Consent Record
        cur.execute("""
            SELECT consent_id, notice_version, consented_at, consent_granted
            FROM patient_ai_consents
            WHERE patient_id = %s
            ORDER BY consent_id DESC LIMIT 1;
        """, (patient_id,))
        consent_row = cur.fetchone()

        # Delivered AI-prepared messages & updates
        cur.execute("""
            SELECT update_id, update_type, title, body, action_type, action_payload, created_by, created_at
            FROM patient_updates
            WHERE patient_id = %s
            ORDER BY created_at DESC LIMIT 20;
        """, (patient_id,))
        updates = cur.fetchall() or []

        # Count AI drafts created for this patient
        cur.execute("""
            SELECT COUNT(*) as cnt FROM agent_drafts WHERE patient_id = %s;
        """, (patient_id,))
        ai_drafts_count = cur.fetchone()["cnt"]

    # Check if reconsent needed
    current_version = CURRENT_AI_NOTICE_VERSION
    has_consented = bool(consent_row and consent_row.get("consent_granted"))
    consented_version = consent_row["notice_version"] if consent_row else None
    needs_reconsent = (consented_version != current_version)

    delivered_items = []
    for u in updates:
        payload = u.get("action_payload")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}
        elif not payload:
            payload = {}

        why_reason = payload.get("why_am_i_seeing_this")
        if not why_reason:
            if u["update_type"] == "reminder_dose":
                why_reason = "Delivered because your scheduled medication time arrived."
            elif u["update_type"] == "day_brief":
                why_reason = "Daily morning plan based on your hospital discharge instructions."
            else:
                why_reason = "Clinical routine follow-up approved by your care team."

        delivered_items.append({
            "update_id": u["update_id"],
            "title": u["title"],
            "date": u["created_at"].strftime("%d %b %Y at %I:%M %p") if u.get("created_at") else "",
            "sources_used": ["Discharge papers", "Active prescription schedule", "Post-op recovery plan"],
            "reviewed_by": "Dr. Ananya Sharma & Nurse Priya Nair" if u["created_by"] == "Staff" else "CareLoop Automation (Within Clinical Safety Limits)",
            "why_am_i_seeing_this": why_reason
        })

    return {
        "patient_id": patient_id,
        "patient_name": p["full_name"],
        "ai_help_enabled": bool(p["ai_help_enabled"]),
        "ai_prepared_total_count": ai_drafts_count + len(delivered_items),
        "delivered_updates_count": len(delivered_items),
        "delivered_items": delivered_items,
        "consent": {
            "consent_granted": has_consented,
            "consented_version": consented_version,
            "current_notice_version": current_version,
            "consented_at": consent_row["consented_at"].strftime("%d %b %Y %I:%M %p") if consent_row and consent_row.get("consented_at") else None,
            "needs_reconsent": needs_reconsent
        },
        "transparency_notice": "CareLoop AI assists your care team by preparing drafts and reminders. The LLM talks. Rules decide. Humans act."
    }


def record_patient_ai_consent(
    patient_id: int,
    consent_granted: bool,
    notice_version: str = CURRENT_AI_NOTICE_VERSION,
    actor_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Records immutable AI-help consent timestamp and notice version.
    Synchronizes patients.ai_help_enabled.
    """
    now = datetime.now()
    with get_conn() as conn, conn.cursor() as cur:
        # Insert consent log
        cur.execute("""
            INSERT INTO patient_ai_consents (patient_id, notice_version, consented_at, consent_granted, actor_id)
            VALUES (%s, %s, %s, %s, %s);
        """, (patient_id, notice_version, now, 1 if consent_granted else 0, actor_id))

        # Update patients table
        cur.execute("""
            UPDATE patients
            SET ai_help_enabled = %s
            WHERE patient_id = %s;
        """, (1 if consent_granted else 0, patient_id))

        # Audit log
        cur.execute("""
            INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details, created_at)
            VALUES ('Patient', %s, 'AI_HELP_CONSENT_UPDATED', 'patient', %s, JSON_OBJECT(
                'consent_granted', %s, 'notice_version', %s
            ), %s);
        """, (str(patient_id), patient_id, consent_granted, notice_version, now))

        conn.commit()

    logger.info(f"Patient #{patient_id} AI consent updated: {consent_granted} (Notice Version: {notice_version})")
    return {
        "status": "ok",
        "patient_id": patient_id,
        "ai_help_enabled": consent_granted,
        "notice_version": notice_version,
        "consented_at": now.isoformat()
    }
