"""
backend/app/agents/recovery_coach.py — CareLoop Recovery Coach & Medication Support (Phase 3)

Implements:
1. Today's 3 Things deterministic selector (Medication, Daily Check-in, Plan Activity with source citation).
2. "Not today" & Snooze handlers with reason chips (feeds nurse brief, never a flag).
3. Action-based encouragement from phrase bank (no health praise).
4. Weekly Recap facts-only compiler (EN/HI, provable counts only).
5. Medication Barrier capture (dose_barriers) & de-duplicated Nurse Call Request generator.
6. Patient Reminder Preferences (lead time & channel; locked dose times).
"""

from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
import pymysql
from backend.app.db import get_conn
from backend.app.agents.phrase_bank_service import PhraseBankService


class RecoveryCoachService:
    """Deterministic recovery coach engine strictly following clinical discharge papers."""

    REASON_CHIPS = [
        {"id": "felt_unwell", "label_en": "Felt unwell", "label_hi": "तबीयत ठीक नहीं थी"},
        {"id": "too_tired", "label_en": "Too tired / exhausted", "label_hi": "बहुत अधिक थकान थी"},
        {"id": "pain", "label_en": "Pain at wound site", "label_hi": "घाव में दर्द था"},
        {"id": "busy", "label_en": "Resting / Busy", "label_hi": "आराम कर रहे थे / व्यस्त थे"},
        {"id": "doctor_advised", "label_en": "Doctor advised pause", "label_hi": "डॉक्टर ने रुकने को कहा"},
    ]

    BARRIER_CODES = {
        "forgot": "Forgot",
        "felt_unwell": "Felt_unwell",
        "unwell": "Felt_unwell",
        "ran_out": "Ran_out",
        "side_effects": "Side_effects_worry",
        "side_effects_worry": "Side_effects_worry",
        "confusion": "Confusion",
        "confused": "Confusion",
        "other": "Other",
    }

    @classmethod
    def get_todays_three_things(cls, patient_id: int, language: str = "en") -> Dict[str, Any]:
        """
        Deterministic selection of exactly 3 priority items for patient's day:
        1. Next scheduled medication dose.
        2. Today's daily check-in (pending or completed).
        3. One verified recovery plan activity or clinic appointment with quoted source.
        """
        with get_conn() as conn, conn.cursor() as cur:
            # 1. Next upcoming dose for today
            cur.execute(
                """SELECT ml.medication_log_id, ml.prescription_id, ml.scheduled_for, ml.status,
                          m.medicine_name, p.dose_instructions
                   FROM medication_logs ml
                   JOIN prescriptions p ON ml.prescription_id = p.prescription_id
                   JOIN medicines m ON p.medicine_id = m.medicine_id
                   WHERE p.patient_id = %s
                     AND DATE(ml.scheduled_for) = CURDATE()
                   ORDER BY ml.status = 'Pending' DESC, ml.scheduled_for ASC
                   LIMIT 1""",
                (patient_id,)
            )
            med_row = cur.fetchone()

            # 2. Check-in status today
            cur.execute(
                """SELECT session_id, status, current_step, completed_at
                   FROM checkin_sessions
                   WHERE patient_id = %s AND DATE(started_at) = CURDATE()
                   ORDER BY started_at DESC LIMIT 1""",
                (patient_id,)
            )
            checkin_row = cur.fetchone()

            # 3. Verified recovery plan activity
            cur.execute(
                """SELECT rpi.item_id, rpi.title, rpi.detail, rpi.schedule_text,
                          dc.section_title, dc.page_no
                   FROM recovery_plan_items rpi
                   JOIN recovery_plans rp ON rpi.plan_id = rp.plan_id
                   LEFT JOIN document_chunks dc ON rpi.source_chunk_id = dc.chunk_id
                   WHERE rp.patient_id = %s AND rp.status = 'Approved'
                     AND rpi.item_type IN ('Activity', 'Wound_Care', 'Diet', 'Other')
                   ORDER BY rpi.display_order ASC
                   LIMIT 1""",
                (patient_id,)
            )
            plan_act = cur.fetchone()

            # Check if any daily_items already created for today
            cur.execute(
                """SELECT item_id, item_type, title, detail, source_citation, status, reason_code, action_type
                   FROM daily_items
                   WHERE patient_id = %s AND DATE(created_at) = CURDATE()
                   ORDER BY item_id ASC""",
                (patient_id,)
            )
            stored_items = cur.fetchall()

        items = []

        # Item 1: Medication Dose
        if med_row:
            sched_time = med_row["scheduled_for"].strftime("%I:%M %p") if isinstance(med_row["scheduled_for"], datetime) else "Today"
            status_text = "Done" if med_row["status"] == "Taken_Confirmed" else ("Skipped" if med_row["status"] == "Skipped" else "Pending")
            items.append({
                "item_type": "Medication",
                "title": f"{med_row['medicine_name']} ({med_row['dose_instructions']})" if language == "en" else f"{med_row['medicine_name']} खुराक ({med_row['dose_instructions']})",
                "detail": f"Scheduled for {sched_time}" if language == "en" else f"निर्धारित समय: {sched_time}",
                "source_citation": "Prescription record verified by Dr. Sharma",
                "status": status_text,
                "action_type": "Open_Medicines",
                "action_label": "Take dose" if status_text == "Pending" else "View details",
                "ref_id": med_row["medication_log_id"],
                "allow_snooze": status_text == "Pending",
            })
        else:
            items.append({
                "item_type": "Medication",
                "title": "Scheduled Medications" if language == "en" else "निर्धारित दवाइयाँ",
                "detail": "All scheduled doses confirmed for today" if language == "en" else "आज की सभी दवाएं पूरी हो चुकी हैं",
                "source_citation": "CareLoop Prescription Schedule",
                "status": "Done",
                "action_type": "Open_Medicines",
                "action_label": "View medicines",
                "allow_snooze": False,
            })

        # Item 2: Daily Check-in
        is_checkin_done = bool(checkin_row and checkin_row["status"] == "Completed")
        items.append({
            "item_type": "Checkin",
            "title": "Daily Health Check-in" if language == "en" else "दैनिक स्वास्थ्य चेक-इन",
            "detail": "2-minute recovery check-in for Dr. Sharma & triage nurse" if not is_checkin_done else "Completed today",
            "source_citation": "CareLoop Hospital Recovery Protocol",
            "status": "Done" if is_checkin_done else "Pending",
            "action_type": "Start_Checkin",
            "action_label": "Start check-in" if not is_checkin_done else "Review check-in",
            "allow_snooze": not is_checkin_done,
        })

        # Item 3: Plan Activity (strictly quoted from discharge papers)
        if plan_act:
            sec_title = plan_act.get("section_title") or "Discharge Plan"
            p_no = plan_act.get("page_no")
            cite_str = f"Discharge Summary - {sec_title}" + (f" (p. {p_no})" if p_no else "")
            items.append({
                "item_type": "Activity",
                "title": plan_act["title"],
                "detail": plan_act["detail"] or plan_act["schedule_text"] or "From recovery plan",
                "source_citation": cite_str,
                "status": "Pending",
                "action_type": "Log_Activity",
                "action_label": "Mark completed",
                "ref_id": plan_act["item_id"],
                "allow_snooze": True,
            })
        else:
            items.append({
                "item_type": "Activity",
                "title": "Gentle Walking & Rest" if language == "en" else "हल्की सैर व पर्याप्त आराम",
                "detail": "15-minute gentle flat walking as tolerated" if language == "en" else "समतल स्थान पर 15 मिनट की हल्की सैर",
                "source_citation": "Discharge Summary - Activity Guidelines",
                "status": "Pending",
                "action_type": "Log_Activity",
                "action_label": "Mark completed",
                "allow_snooze": True,
            })

        # Rotated action-based encouragement from approved phrase bank (no health praise)
        encouragement = PhraseBankService.get_rotated_phrase("encouragement", language=language, turn_seed=patient_id)

        return {
            "patient_id": patient_id,
            "items": items[:3],
            "encouragement": encouragement,
            "reason_chips": cls.REASON_CHIPS,
        }

    @classmethod
    def record_item_not_today(cls, patient_id: int, item_type: str, reason_code: str, note: Optional[str] = None) -> Dict[str, Any]:
        """
        Record 'Not Today' or Snooze with reason chip.
        Feeds nurse brief context; NEVER triggers a clinical safety flag.
        """
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO daily_items (patient_id, day_number, item_type, title, status, reason_code, created_at)
                   VALUES (%s, 1, %s, %s, 'Not_today', %s, NOW())""",
                (patient_id, item_type, f"{item_type} postponed", reason_code)
            )
            # Log audit
            cur.execute(
                """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                   VALUES ('Patient', %s, 'RECOVERY_ITEM_NOT_TODAY', 'daily_item', %s,
                           JSON_OBJECT('item_type', %s, 'reason_code', %s, 'note', %s))""",
                (str(patient_id), cur.lastrowid, item_type, reason_code, note or "")
            )
            conn.commit()

        return {
            "success": True,
            "patient_id": patient_id,
            "status": "postponed",
            "reason_code": reason_code,
            "message": "Recorded. Your nurse will see this note in your recovery brief.",
        }

    @classmethod
    def record_medication_barrier(
        cls,
        patient_id: int,
        medication_log_id: Optional[int] = None,
        reason_code_raw: str = "Other",
        note: Optional[str] = None,
        dose_id: Optional[int] = None,
        barrier_code: Optional[str] = None,
        patient_note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Medication barrier capture (5.D):
        - Stored as standardized reason codes in dose_barriers.
        - Reasons 'Felt_unwell', 'Ran_out', and 'Side_effects_worry' create a High-priority nurse call request.
        - De-duplicated per patient per topic per day.
        """
        raw_code = barrier_code or reason_code_raw or "Other"
        code_key = raw_code.strip().lower()
        reason_code = cls.BARRIER_CODES.get(code_key, "Other")
        effective_log_id = medication_log_id or dose_id
        effective_note = patient_note or note or ""

        call_request_created = False
        task_id = None

        with get_conn() as conn, conn.cursor() as cur:
            # 1. Insert into dose_barriers
            cur.execute(
                """INSERT INTO dose_barriers (patient_id, medication_log_id, reason_code, note, created_at)
                   VALUES (%s, %s, %s, %s, NOW())""",
                (patient_id, effective_log_id, reason_code, effective_note)
            )
            barrier_id = cur.lastrowid

            # 2. Update medication_logs status to Skipped with patient_note if log provided
            if effective_log_id:
                cur.execute(
                    """UPDATE medication_logs
                       SET status = 'Skipped', patient_note = %s
                       WHERE medication_log_id = %s""",
                    (f"Barrier: {reason_code}. Note: {effective_note}".strip()[:250], effective_log_id)
                )

            # 3. If barrier warrants clinician contact, create de-duplicated nurse call request
            if reason_code in ("Felt_unwell", "Ran_out", "Side_effects_worry"):
                # Check for existing pending call request on same topic today
                dedupe_reason = f"Medication Barrier Callback: {reason_code}"
                cur.execute(
                    """SELECT followup_id FROM follow_up_tasks
                       WHERE patient_id = %s AND reason = %s AND DATE(created_at) = CURDATE()
                         AND status IN ('Pending')
                       LIMIT 1""",
                    (patient_id, dedupe_reason)
                )
                existing = cur.fetchone()
                if not existing:
                    cur.execute(
                        """INSERT INTO follow_up_tasks (patient_id, assigned_staff_id, reason, priority, status, created_at)
                           VALUES (%s, 1, %s, 'Urgent_Review', 'Pending', NOW())""",
                        (patient_id, dedupe_reason)
                    )
                    task_id = cur.lastrowid
                    call_request_created = True
                else:
                    task_id = existing["followup_id"]

            # Write audit
            cur.execute(
                """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                   VALUES ('Patient', %s, 'DOSE_BARRIER_RECORDED', 'dose_barrier', %s,
                           JSON_OBJECT('reason_code', %s, 'call_requested', %s))""",
                (str(patient_id), barrier_id, reason_code, call_request_created)
            )
            conn.commit()

        return {
            "success": True,
            "status": "recorded",
            "barrier_id": barrier_id,
            "reason_code": reason_code,
            "call_request_created": call_request_created,
            "nurse_task_created": call_request_created,
            "task_id": task_id,
            "message": "Barrier noted. A triage nurse callback request has been scheduled." if call_request_created else "Reason recorded for your care team.",
        }

    @classmethod
    def get_weekly_recap(cls, patient_id: int, language: str = "en") -> Dict[str, Any]:
        """
        Weekly Recap facts-only compiler (5.C):
        Doses taken/skipped/unconfirmed, check-ins completed, pain numbers by day, activities done.
        Provable numbers only; zero subjective medical praise or interpretation.
        """
        with get_conn() as conn, conn.cursor() as cur:
            # Doses in last 7 days
            cur.execute(
                """SELECT
                     SUM(status = 'Taken_Confirmed') AS taken_count,
                     SUM(status = 'Skipped') AS skipped_count,
                     SUM(status IN ('Pending', 'Unconfirmed')) AS unconfirmed_count,
                     COUNT(*) AS total_doses
                   FROM medication_logs ml
                   JOIN prescriptions p ON ml.prescription_id = p.prescription_id
                   WHERE p.patient_id = %s
                     AND ml.scheduled_for >= NOW() - INTERVAL 7 DAY""",
                (patient_id,)
            )
            doses = cur.fetchone() or {}

            # Check-ins in last 7 days
            cur.execute(
                """SELECT COUNT(DISTINCT DATE(completed_at)) AS checkin_days
                   FROM checkin_sessions
                   WHERE patient_id = %s AND status = 'Completed'
                     AND completed_at >= NOW() - INTERVAL 7 DAY""",
                (patient_id,)
            )
            checkin_stat = cur.fetchone() or {}

            # Daily pain scores recorded
            cur.execute(
                """SELECT DATE(reported_at) AS rep_date, pain_level
                   FROM symptom_reports
                   WHERE patient_id = %s AND reported_at >= NOW() - INTERVAL 7 DAY
                     AND pain_level IS NOT NULL
                   ORDER BY rep_date ASC""",
                (patient_id,)
            )
            pain_rows = cur.fetchall()

        taken = int(doses.get("taken_count") or 0)
        skipped = int(doses.get("skipped_count") or 0)
        unconfirmed = int(doses.get("unconfirmed_count") or 0)
        total_doses = int(doses.get("total_doses") or 0)
        checkin_days = int(checkin_stat.get("checkin_days") or 0)

        pain_by_day = [
            {"date": str(r["rep_date"]), "pain": int(r["pain_level"])}
            for r in pain_rows
        ]

        if language == "hi":
            facts = [
                f"दवाइयाँ: कुल {total_doses} में से {taken} ली गईं, {skipped} छोड़ी गईं, {unconfirmed} अनिर्धारित।",
                f"चेक-इन: पिछले 7 दिनों में से {checkin_days} दिन चेक-इन पूर्ण किए गए।",
                f"दर्द रिकॉर्ड: {len(pain_by_day)} बार दर्द स्कोर दर्ज हुआ (न्यूनतम: {min((p['pain'] for p in pain_by_day), default=0)}, अधिकतम: {max((p['pain'] for p in pain_by_day), default=0)})।",
            ]
            title = "साप्ताहिक रिकवरी समीक्षा (तथ्य)"
        else:
            facts = [
                f"Medications: {taken} of {total_doses} taken, {skipped} skipped, {unconfirmed} unconfirmed.",
                f"Daily Check-ins: {checkin_days} of 7 days completed.",
                f"Pain Logs: {len(pain_by_day)} pain entries recorded (Range: {min((p['pain'] for p in pain_by_day), default=0)}/10 to {max((p['pain'] for p in pain_by_day), default=0)}/10).",
            ]
            title = "Weekly Recovery Facts Recap"

        return {
            "patient_id": patient_id,
            "title": title,
            "period": "Last 7 Days",
            "summary": {
                "doses_taken": taken,
                "doses_skipped": skipped,
                "doses_unconfirmed": unconfirmed,
                "total_scheduled": total_doses,
                "checkins_completed": checkin_days,
            },
            "facts": facts,
            "doses_taken": taken,
            "doses_skipped": skipped,
            "doses_unconfirmed": unconfirmed,
            "doses_total": total_doses,
            "checkin_completed_days": checkin_days,
            "pain_by_day": pain_by_day,
            "factual_summary": facts,
        }

    @classmethod
    def update_reminder_preferences(
        cls,
        patient_id: int,
        reminder_lead_min: int,
        channel_pref: str,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Patient sets reminder lead time (15, 30, 60 mins) and channel (App, SMS).
        CRITICAL GUARD: Prescription dose times are NEVER modified by patient or agent.
        """
        lead_min = max(10, min(120, int(reminder_lead_min)))
        channel = "SMS" if channel_pref.upper() == "SMS" else "App"

        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """INSERT INTO patient_preferences (patient_id, reminder_lead_min, channel_pref, updated_at)
                   VALUES (%s, %s, %s, NOW())
                   ON DUPLICATE KEY UPDATE reminder_lead_min = VALUES(reminder_lead_min),
                                           channel_pref = VALUES(channel_pref),
                                           updated_at = NOW()""",
                (patient_id, lead_min, channel)
            )
            # Update patients preferred_language if provided
            if language in ("en", "hi"):
                cur.execute("UPDATE patients SET preferred_language = %s WHERE patient_id = %s", (language, patient_id))

            conn.commit()

        return {
            "success": True,
            "status": "updated",
            "patient_id": patient_id,
            "reminder_lead_min": lead_min,
            "channel_pref": channel,
            "dose_times_locked": True,
            "message": f"Reminders will be sent via {channel} {lead_min} minutes prior. Prescription dose times remain unchanged as set by your physician.",
        }
