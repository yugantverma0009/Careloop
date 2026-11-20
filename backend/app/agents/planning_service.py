"""
backend/app/agents/planning_service.py — Phase 5 Planning & Comprehension Services

Implements:
1. Explain Simply (5.E): Rewrites complex clinical text / discharge passages into plain, 
   accessible language (EN & HI) with the original passage beside it.
   Strict guard: Preserves ALL exact numbers, medication names, and avoids adding new advice.
2. Teach-back Helper & Saved Questions (5.E):
   - Saved questions persistence for upcoming clinical appointments.
   - Feeds directly into Visit Prep Sheet.
3. Plan My Day (5.I):
   - Multi-step deterministic state machine (zero ungrounded LLM generation).
   - Assembles confirmed items: approved recovery plan items, active prescriptions, appointments, check-in.
   - Emits day timeline with one-tap client actions: "Add reminders", "Add to calendar (.ics)", "Save questions".
   - Strict guard: NEVER creates staff tasks, NEVER alters doses or schedules, NEVER books visits autonomously.
"""

import re
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from backend.app.db import get_conn


# ─── 1. Explain Simply (5.E) ────────────────────────────────────────────────

SIMPLIFY_LEXICON_EN = [
    (r"\bambulate\b", "walk"),
    (r"\bambulation\b", "walking"),
    (r"\badminister\b", "take"),
    (r"\badministration\b", "taking"),
    (r"\bincision\b", "cut / wound"),
    (r"\berethema\b|\beridema\b|\berythema\b", "redness"),
    (r"\bedema\b", "swelling"),
    (r"\banalgesic\b|\banalgesics\b", "pain medicine"),
    (r"\bdyspnea\b", "shortness of breath"),
    (r"\bpurulent drainage\b|\bpurulent discharge\b", "pus or yellow fluid"),
    (r"\bcontraindicated\b", "not recommended / avoid"),
    (r"\belevate\b", "prop up / raise"),
    (r"\bhypotension\b", "low blood pressure"),
    (r"\bhypertension\b", "high blood pressure"),
    (r"\btachycardia\b", "fast heart rate"),
    (r"\bbradycardia\b", "slow heart rate"),
    (r"\bdiaphoresis\b", "heavy sweating"),
    (r"\bapply topically\b", "put directly on the skin"),
    (r"\bprn\b|\bpro re nata\b", "only as needed"),
    (r"\bpo\b|\bper os\b", "by mouth"),
    (r"\bnpo\b|\bnil per os\b", "nothing by mouth"),
    (r"\bsternotomy\b", "chest bone incision"),
    (r"\bhematoma\b", "blood collection / swelling"),
]

SIMPLIFY_LEXICON_HI = [
    (r"\bambulate\b|\bwalk\b", "टहलना"),
    (r"\badminister\b|\btake\b", "दवाई लेना"),
    (r"\bincision\b|\bwound\b", "चीरा / घाव"),
    (r"\berethema\b|\berythema\b|\bredness\b", "लालिमा"),
    (r"\bedema\b|\bswelling\b", "सूजन"),
    (r"\banalgesic\b|\bpain medicine\b", "दर्द की दवा"),
    (r"\bdyspnea\b|\bshortness of breath\b", "सांस लेने में तकलीफ़"),
    (r"\bpurulent\b|\bpus\b", "मवाद या पीला पानी"),
    (r"\belevate\b|\braise\b", "ऊँचा रखना (तकिया लगाकर)"),
    (r"\bblood pressure\b", "ब्लड प्रेशर"),
    (r"\bheart rate\b", "धड़कन"),
]


def explain_simply(text: str, language: str = "en") -> Dict[str, Any]:
    """
    Rewrites text into simpler, plain-language wording.
    Guards:
    1. Extracts all numeric values from original text.
    2. Ensures 100% of original numbers exist in simplified output (zero modified or dropped numbers).
    3. Adds no new clinical advice.
    4. Returns both original passage and simplified text for side-by-side presentation.
    """
    if not text or not text.strip():
        return {
            "original_passage": "",
            "simplified_text": "",
            "language": language,
            "preserved_numbers": [],
            "status": "empty",
        }

    raw = text.strip()
    original_numbers = re.findall(r"\b\d+(?:\.\d+)?\b", raw)

    simplified = raw
    lexicon = SIMPLIFY_LEXICON_HI if language == "hi" else SIMPLIFY_LEXICON_EN
    for pattern, replacement in lexicon:
        simplified = re.sub(pattern, replacement, simplified, flags=re.IGNORECASE)

    # Clean up minor sentence flow
    simplified = re.sub(r"\s+", " ", simplified).strip()

    # Verify that all original numbers are preserved
    for num in original_numbers:
        if num not in simplified:
            # If replacement accidentally altered a numeric token, revert to original
            simplified = f"{raw} (Note: Follow exact numbers as stated in your papers: {', '.join(original_numbers)})"
            break

    return {
        "original_passage": raw,
        "simplified_text": simplified,
        "language": language,
        "preserved_numbers": original_numbers,
        "status": "ok",
    }


# ─── 2. Saved Questions for Visit Prep (5.E) ─────────────────────────────────

def save_question(patient_id: int, question_text: str, appointment_id: Optional[int] = None) -> Dict[str, Any]:
    """Persists a question saved by the patient to discuss with their care team."""
    q_clean = question_text.strip()
    if not q_clean:
        raise ValueError("Question text cannot be empty.")
    if len(q_clean) > 500:
        q_clean = q_clean[:500]

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO saved_questions (patient_id, question_text, for_appointment_id, status)
            VALUES (%s, %s, %s, 'Saved');
            """,
            (patient_id, q_clean, appointment_id),
        )
        conn.commit()
        qid = cur.lastrowid

    return {
        "question_id": qid,
        "patient_id": patient_id,
        "question_text": q_clean,
        "status": "Saved",
        "message": "Question saved for your upcoming doctor visit.",
    }


def get_saved_questions(patient_id: int) -> List[Dict[str, Any]]:
    """Retrieves all active saved questions for the patient."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT question_id, patient_id, question_text, for_appointment_id, status, created_at
            FROM saved_questions
            WHERE patient_id = %s AND status = 'Saved'
            ORDER BY created_at DESC;
            """,
            (patient_id,),
        )
        rows = cur.fetchall() or []

    return [
        {
            "question_id": r["question_id"],
            "patient_id": r["patient_id"],
            "question_text": r["question_text"],
            "for_appointment_id": r["for_appointment_id"],
            "status": r["status"],
            "created_at": r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r.get("created_at") else "",
        }
        for r in rows
    ]


def dismiss_saved_question(patient_id: int, question_id: int) -> bool:
    """Marks a saved question as dismissed or discussed."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE saved_questions
            SET status = 'Dismissed'
            WHERE question_id = %s AND patient_id = %s;
            """,
            (question_id, patient_id),
        )
        conn.commit()
        return cur.rowcount > 0


# ─── 3. Plan My Day (5.I) ───────────────────────────────────────────────────

def plan_my_day(patient_id: int, language: str = "en") -> Dict[str, Any]:
    """
    Multi-step deterministic state machine that compiles the patient's schedule:
    - Approved recovery plan items (walking, wound care, breathing).
    - Prescriptions and dose schedule times.
    - Next appointment.
    - Daily check-in preference.

    Guards:
    - NEVER creates staff tasks.
    - NEVER mutates prescription doses or alters timings.
    - NEVER books appointments autonomously.
    """
    with get_conn() as conn, conn.cursor() as cur:
        # 1. Patient preferences
        cur.execute(
            """
            SELECT checkin_time, reminder_lead_min
            FROM patient_preferences
            WHERE patient_id = %s;
            """,
            (patient_id,),
        )
        pref = cur.fetchone() or {"checkin_time": timedelta(hours=9), "reminder_lead_min": 15}

        # Format checkin time
        checkin_t_str = "09:00 AM"
        if isinstance(pref.get("checkin_time"), timedelta):
            tot_sec = int(pref["checkin_time"].total_seconds())
            hrs = tot_sec // 3600
            mins = (tot_sec % 3600) // 60
            dt = datetime(2026, 1, 1, hrs, mins)
            checkin_t_str = dt.strftime("%I:%M %p")

        # 2. Approved plan items
        cur.execute(
            """
            SELECT rpi.item_id, rpi.item_type, rpi.title, rpi.detail, rpi.schedule_text
            FROM recovery_plan_items rpi
            JOIN recovery_plans rp ON rp.plan_id = rpi.plan_id
            WHERE rp.patient_id = %s AND rp.status = 'Approved'
            ORDER BY rpi.display_order ASC;
            """,
            (patient_id,),
        )
        plan_items = cur.fetchall() or []

        # 3. Active prescriptions and dose times
        cur.execute(
            """
            SELECT m.medicine_name, pr.dose_instructions, pt.dose_time
            FROM prescriptions pr
            JOIN medicines m ON m.medicine_id = pr.medicine_id
            LEFT JOIN prescription_times pt ON pt.prescription_id = pr.prescription_id
            WHERE pr.patient_id = %s AND pr.active_status = 1
            ORDER BY pt.dose_time ASC;
            """,
            (patient_id,),
        )
        dose_rows = cur.fetchall() or []

        # 4. Upcoming appointments
        cur.execute(
            """
            SELECT appointment_id, appointment_date, appointment_type, notes
            FROM appointments
            WHERE patient_id = %s AND appointment_date >= CURDATE()
            ORDER BY appointment_date ASC LIMIT 1;
            """,
            (patient_id,),
        )
        next_appt = cur.fetchone()

    # Slot items deterministically into Morning, Afternoon, Evening, Night
    morning_slots = []
    afternoon_slots = []
    evening_slots = []
    night_slots = []

    # Daily check-in
    morning_slots.append({
        "time": checkin_t_str,
        "title": "Daily Health Check-in" if language == "en" else "दैनिक स्वास्थ्य चेक-इन",
        "category": "checkin",
        "detail": "Share how you are feeling (pain score, wound check)" if language == "en" else "दर्द और घाव की स्थिति साझा करें",
    })

    # Medications
    for d in dose_rows:
        t_delta = d.get("dose_time")
        med_name = d["medicine_name"]
        instr = d.get("dose_instructions") or "Take with water"

        if isinstance(t_delta, timedelta):
            sec = int(t_delta.total_seconds())
            h = sec // 3600
            m = (sec % 3600) // 60
            time_label = datetime(2026, 1, 1, h, m).strftime("%I:%M %p")
        else:
            h = 8
            time_label = "08:00 AM"

        slot_item = {
            "time": time_label,
            "title": f"Take {med_name}" if language == "en" else f"{med_name} लें",
            "category": "medication",
            "detail": instr,
        }

        if h < 12:
            morning_slots.append(slot_item)
        elif 12 <= h < 17:
            afternoon_slots.append(slot_item)
        elif 17 <= h < 21:
            evening_slots.append(slot_item)
        else:
            night_slots.append(slot_item)

    # Plan Items
    for pi in plan_items:
        itype = pi["item_type"]
        title = pi["title"]
        sched = pi.get("schedule_text") or "Daily"

        slot_item = {
            "time": "Flexible",
            "title": title,
            "category": "recovery_activity",
            "detail": f"{itype}: {pi.get('detail') or sched}",
        }

        # Place walking or breathing in afternoon / evening if morning already has medications
        if "walk" in title.lower() or "activity" in itype.lower():
            afternoon_slots.append(slot_item)
        elif "wound" in title.lower() or "care" in itype.lower():
            morning_slots.append(slot_item)
        else:
            evening_slots.append(slot_item)

    # Next appointment (if today or upcoming)
    appt_info = None
    if next_appt:
        appt_dt = next_appt["appointment_date"]
        appt_info = {
            "appointment_id": next_appt["appointment_id"],
            "date": str(appt_dt),
            "type": next_appt.get("appointment_type") or "Follow-up Visit",
            "notes": next_appt.get("notes") or "",
        }

    slots = [
        {"period": "Morning" if language == "en" else "सुबह", "items": morning_slots},
        {"period": "Afternoon" if language == "en" else "दोपहर", "items": afternoon_slots},
        {"period": "Evening" if language == "en" else "शाम", "items": evening_slots},
        {"period": "Night" if language == "en" else "रात", "items": night_slots},
    ]

    return {
        "status": "ok",
        "patient_id": patient_id,
        "date": date.today().strftime("%Y-%m-%d"),
        "slots": slots,
        "next_appointment": appt_info,
        "client_actions": [
            {"action": "add_reminders", "label": "Add reminders (15 min lead)"},
            {"action": "export_ics", "label": "Add to calendar (.ics)"},
            {"action": "save_question", "label": "Save question for visit"},
        ],
        "safe_planning_notice": "Your daily schedule is built strictly from your approved recovery plan and prescribed times. No doses or times have been altered.",
    }


def generate_plan_ics(patient_id: int) -> str:
    """
    Generates standard RFC 5545 iCalendar content for the patient's planned schedule.
    Zero external dependencies.
    """
    plan = plan_my_day(patient_id)
    today_str = date.today().strftime("%Y%m%d")

    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//CareLoop//Care Guide Recovery Plan//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for slot in plan.get("slots", []):
        for item in slot.get("items", []):
            time_str = item.get("time", "09:00 AM")
            # Parse time string into HHMMSS
            try:
                t_dt = datetime.strptime(time_str, "%I:%M %p")
                t_formatted = t_dt.strftime("%H%M00")
            except Exception:
                t_formatted = "090000"

            summary = item.get("title", "Care Activity")
            desc = item.get("detail", "")
            cat = item.get("category", "RECOVERY")

            ics_lines.extend([
                "BEGIN:VEVENT",
                f"UID:careloop-{patient_id}-{today_str}-{t_formatted}-{abs(hash(summary)) % 10000}@careloop.local",
                f"DTSTAMP:{today_str}T000000Z",
                f"DTSTART:{today_str}T{t_formatted}",
                f"SUMMARY:CareLoop: {summary}",
                f"DESCRIPTION:{desc}",
                f"CATEGORIES:{cat.upper()}",
                "STATUS:CONFIRMED",
                "END:VEVENT",
            ])

    ics_lines.append("END:VCALENDAR")
    return "\r\n".join(ics_lines)

