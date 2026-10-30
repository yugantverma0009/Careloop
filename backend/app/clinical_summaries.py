"""
backend/app/clinical_summaries.py

D-08: Clinical Summaries Rebuilt Pipeline
1. Deterministic fact sheet builder from SQL (no patient names sent, uses 'the patient').
2. LLM SBAR rewriter (prompt conforming strictly to Section 10.2).
3. Mandatory Guard checking:
   - 11 banned judgment words
   - Numbers in draft must exist in fact sheet
   - Items for review must come from open flags or open tasks
   - Fallback to 'Generated without AI wording' on any guard failure or missing LLM.
"""

import json
import re
import os
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, Tuple, Optional, List, Set

from .llm import generate

logger = logging.getLogger(__name__)

BANNED_WORDS = [
    "stable",
    "normal",
    "abnormal",
    "improving",
    "worsening",
    "deteriorating",
    "safe",
    "concerning",
    "healthy",
    "recovering well",
    "optimal",
]

SBAR_PROMPT_SYSTEM = """You rewrite a FACT SHEET into a short handoff note for a clinician. You are not a clinician.

RULES
1. Use only the facts in FACT SHEET. Do not add, infer, calculate, round or compare.
2. Copy every number, date, time, unit and name of medicine exactly.
3. Do not use judgment words such as stable, normal, abnormal, improving, worsening, safe, concerning, healthy, or recovering well.
4. Do not recommend any action, test, treatment or dose change.
5. If a fact is missing, write "not available". Never fill gaps.
6. Refer to the person only as "the patient".
7. Maximum 120 words.

FORMAT (JSON only):
{"situation": "...", "background": "...", "assessment_facts": ["..."], "items_for_review": ["..."]}
"items_for_review" may only repeat open flag reasons and open tasks from the fact sheet.
"""


def extract_numbers(val: Any) -> Set[str]:
    """Extracts all numeric representations from string or nested data structure."""
    text = json.dumps(val) if not isinstance(val, str) else val
    matches = re.findall(r'-?\d+(?:\.\d+)?', text)
    return set(matches)


def build_deterministic_fact_sheet(conn, patient_id: int, target_date_str: str) -> Dict[str, Any]:
    """
    Builds the deterministic clinical fact sheet from SQL without patient name.
    Strictly anonymizes to 'the patient' and uses patient_code.
    """
    with conn.cursor() as cur:
        # 1. Patient identity & condition (NO full_name)
        cur.execute(
            """SELECT p.patient_id, p.patient_code,
                      TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age_years,
                      d.discharge_date, d.condition_summary,
                      DATEDIFF(%s, d.discharge_date) + 1 AS day_number
               FROM patients p
               LEFT JOIN discharge_records d ON d.patient_id = p.patient_id
               WHERE p.patient_id = %s
               ORDER BY d.discharge_date DESC LIMIT 1""",
            (target_date_str, patient_id),
        )
        p_row = cur.fetchone()
        if not p_row:
            raise ValueError(f"Patient {patient_id} not found")

        discharge_date = str(p_row.get("discharge_date") or target_date_str)
        day_num = max(1, int(p_row.get("day_number") or 1))
        condition = p_row.get("condition_summary") or "Post-discharge recovery"
        patient_code = p_row.get("patient_code") or f"CL-{patient_id:05d}"
        age_years = p_row.get("age_years") or 0

        # 2. Medications & counts for target_date
        cur.execute(
            """SELECT m.medicine_name, pr.dose_instructions,
                      COALESCE(SUM(CASE WHEN ml.status = 'Taken_Confirmed' THEN 1 ELSE 0 END), 0) AS taken_count,
                      COALESCE(SUM(CASE WHEN ml.status IN ('Skipped', 'Missed') THEN 1 ELSE 0 END), 0) AS skipped_count,
                      COALESCE(SUM(CASE WHEN ml.status = 'Unconfirmed' THEN 1 ELSE 0 END), 0) AS not_confirmed_count,
                      COUNT(ml.medication_log_id) AS total_scheduled
               FROM prescriptions pr
               JOIN medicines m ON m.medicine_id = pr.medicine_id
               LEFT JOIN medication_logs ml ON ml.prescription_id = pr.prescription_id AND DATE(ml.scheduled_for) = %s
               WHERE pr.patient_id = %s AND pr.active_status = 1
               GROUP BY pr.prescription_id, m.medicine_name, pr.dose_instructions""",
            (target_date_str, patient_id),
        )
        meds = cur.fetchall() or []
        med_list = []
        tot_taken = 0
        tot_skipped = 0
        tot_unconfirmed = 0
        for m in meds:
            t = int(m.get("taken_count") or 0)
            s = int(m.get("skipped_count") or 0)
            nc = int(m.get("not_confirmed_count") or 0)
            tot_taken += t
            tot_skipped += s
            tot_unconfirmed += nc
            med_list.append({
                "medication_name": m.get("medicine_name"),
                "dose_instructions": m.get("dose_instructions") or "As directed",
                "taken_count": t,
                "skipped_count": s,
                "not_confirmed_count": nc,
            })

        # 3. Latest sensor readings with measurement time and quality status
        cur.execute(
            """SELECT r.reading_id, r.measurement_type, r.measurement_value, r.unit,
                      r.measured_at, r.quality_status
               FROM sensor_readings r
               WHERE r.patient_id = %s AND DATE(r.measured_at) = %s
               ORDER BY r.measured_at DESC""",
            (patient_id, target_date_str),
        )
        readings_rows = cur.fetchall() or []
        latest_readings = {}
        for r in readings_rows:
            mtype = r.get("measurement_type")
            if mtype not in latest_readings:
                latest_readings[mtype] = {
                    "measurement_type": mtype,
                    "value": float(r.get("measurement_value") or 0),
                    "unit": r.get("unit") or "",
                    "reading_time": str(r.get("measured_at")),
                    "quality_status": r.get("quality_status") or "Good",
                }

        # 4. Device connectivity / last seen
        cur.execute(
            """SELECT device_id, device_type, last_seen_at
               FROM devices
               WHERE patient_id = %s
               ORDER BY last_seen_at DESC LIMIT 1""",
            (patient_id,),
        )
        dev_row = cur.fetchone()
        device_status = None
        if dev_row:
            device_status = {
                "device_type": dev_row.get("device_type"),
                "last_synced_at": str(dev_row.get("last_seen_at")) if dev_row.get("last_seen_at") else "None",
            }

        # 5. Check-ins & symptoms on target date
        cur.execute(
            """SELECT symptom_report_id, pain_level, symptom_text, emergency_keyword_hit, reported_at
               FROM symptom_reports
               WHERE patient_id = %s AND DATE(reported_at) = %s
               ORDER BY reported_at DESC LIMIT 1""",
            (patient_id, target_date_str),
        )
        checkin_row = cur.fetchone()
        checkin_info = None
        if checkin_row:
            checkin_info = {
                "pain_level": int(checkin_row.get("pain_level") or 0),
                "symptom_text": checkin_row.get("symptom_text") or "None reported",
                "emergency_flag": bool(checkin_row.get("emergency_keyword_hit")),
            }

        # 6. Open flags with reasons
        cur.execute(
            """SELECT flag_id, severity, reason, created_at
               FROM flags
               WHERE patient_id = %s AND status IN ('Open', 'Acknowledged')
               ORDER BY created_at DESC""",
            (patient_id,),
        )
        flags_rows = cur.fetchall() or []
        open_flag_reasons = [f.get("reason") for f in flags_rows if f.get("reason")]

        # 7. Open tasks with reasons
        cur.execute(
            """SELECT followup_id, priority, reason, due_at
               FROM follow_up_tasks
               WHERE patient_id = %s AND status != 'Resolved'
               ORDER BY due_at ASC""",
            (patient_id,),
        )
        tasks_rows = cur.fetchall() or []
        open_task_texts = [t.get("reason") for t in tasks_rows if t.get("reason")]

        # 8. Appointments
        cur.execute(
            """SELECT a.appointment_id, a.appointment_date, cs.full_name AS doctor_name, a.notes
               FROM appointments a
               LEFT JOIN care_staff cs ON cs.staff_id = a.staff_id
               WHERE a.patient_id = %s AND a.appointment_date >= %s
               ORDER BY a.appointment_date ASC LIMIT 2""",
            (patient_id, target_date_str),
        )
        appts = cur.fetchall() or []
        appts_list = [
            {
                "scheduled_for": str(a.get("appointment_date")),
                "doctor_name": a.get("doctor_name") or "Treating Physician",
                "location": a.get("notes") or "Clinic",
            }
            for a in appts
        ]

    fact_sheet = {
        "target_date": target_date_str,
        "patient_code": patient_code,
        "age_years": age_years,
        "discharge_date": discharge_date,
        "day_number": day_num,
        "condition": condition,
        "total_medications_scheduled": len(med_list),
        "total_doses_taken": tot_taken,
        "total_doses_skipped": tot_skipped,
        "total_doses_unconfirmed": tot_unconfirmed,
        "medications": med_list,
        "latest_readings": list(latest_readings.values()),
        "device_status": device_status,
        "checkin": checkin_info,
        "open_flag_reasons": open_flag_reasons,
        "open_task_texts": open_task_texts,
        "appointments": appts_list,
    }
    return fact_sheet


def run_summary_guard(draft: Dict[str, Any], fact_sheet: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Mandatory safety guard for clinical draft summaries (Section 10.3).
    Returns (True, None) if clean, or (False, reason) if violated.
    """
    if not isinstance(draft, dict):
        return False, "draft_not_dict"

    req_keys = ["situation", "background", "assessment_facts", "items_for_review"]
    for k in req_keys:
        if k not in draft or not draft[k]:
            return False, f"missing_or_empty_section_{k}"

    situation = str(draft.get("situation", ""))
    background = str(draft.get("background", ""))
    assessment_facts = draft.get("assessment_facts", [])
    if isinstance(assessment_facts, str):
        assessment_facts = [assessment_facts]
    items_for_review = draft.get("items_for_review", [])
    if isinstance(items_for_review, str):
        items_for_review = [items_for_review]

    all_draft_text = " ".join([situation, background, *assessment_facts, *items_for_review]).lower()

    # 1. Banned words check
    for word in BANNED_WORDS:
        pattern = r'\b' + re.escape(word) + r'\b'
        if re.search(pattern, all_draft_text):
            return False, f"banned_word_{word}"

    # 2. Number check: every number in draft must exist in fact sheet
    allowed_numbers = extract_numbers(fact_sheet)
    draft_numbers = extract_numbers(all_draft_text)
    unauthorized_numbers = draft_numbers - allowed_numbers
    if unauthorized_numbers:
        return False, f"numbers_not_in_facts_{list(unauthorized_numbers)}"

    # 3. Review items check: must be in open_flag_reasons or open_task_texts
    allowed_review_items = set(fact_sheet.get("open_flag_reasons", []) + fact_sheet.get("open_task_texts", []))
    for item in items_for_review:
        if item not in allowed_review_items:
            matched = any(item.strip() in allowed or allowed in item.strip() for allowed in allowed_review_items if allowed)
            if not matched:
                return False, f"review_item_not_from_facts_{item}"

    return True, None


def generate_fallback_summary(fact_sheet: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic rule-based SBAR draft when AI is unavailable or guard fails.
    Conforms strictly to Section 10.2 structure without any banned words.
    """
    day_num = fact_sheet.get("day_number", 1)
    cond = fact_sheet.get("condition", "Post-discharge recovery")
    disch = fact_sheet.get("discharge_date", "not available")
    med_count = fact_sheet.get("total_medications_scheduled", 0)
    taken = fact_sheet.get("total_doses_taken", 0)
    skipped = fact_sheet.get("total_doses_skipped", 0)
    unconf = fact_sheet.get("total_doses_unconfirmed", 0)

    situation = f"The patient is on post-discharge day {day_num} for {cond}."
    background = f"Discharged on {disch}. Prescriptions: {med_count} active medications."

    assessment_facts = []
    assessment_facts.append(
        f"Medication logs recorded: {taken} doses taken, {skipped} skipped, {unconf} not confirmed."
    )

    readings = fact_sheet.get("latest_readings", [])
    if readings:
        for r in readings:
            val = r.get("value")
            unit = r.get("unit", "")
            mtype = r.get("measurement_type", "")
            q = r.get("quality_status", "Good")
            time_str = r.get("reading_time", "")
            assessment_facts.append(
                f"{mtype} recorded {val} {unit} at {time_str} ({q})."
            )
    else:
        assessment_facts.append("No sensor readings recorded for this date.")

    checkin = fact_sheet.get("checkin")
    if checkin:
        pain = checkin.get("pain_level", 0)
        symptom = checkin.get("symptom_text", "None reported")
        assessment_facts.append(
            f"Check-in recorded pain level {pain} with note: {symptom}."
        )

    dev = fact_sheet.get("device_status")
    if dev:
        dtype = dev.get("device_type", "Device")
        last_s = dev.get("last_synced_at", "None")
        assessment_facts.append(f"{dtype} last synced at {last_s}.")

    items_for_review = []
    for r in fact_sheet.get("open_flag_reasons", []):
        if r not in items_for_review:
            items_for_review.append(r)
    for t in fact_sheet.get("open_task_texts", []):
        if t not in items_for_review:
            items_for_review.append(t)

    if not items_for_review:
        items_for_review = ["None"]

    return {
        "situation": situation,
        "background": background,
        "assessment_facts": assessment_facts,
        "items_for_review": items_for_review,
        "is_fallback": True,
        "note": "Generated without AI wording",
    }


def produce_clinical_summary(fact_sheet: Dict[str, Any]) -> Tuple[Dict[str, Any], str, str]:
    """
    Executes pipeline:
    1. Attempts LLM rewrite using SBAR prompt.
    2. Runs Guard.
    3. If guard fails or LLM fails, falls back to deterministic SBAR.
    Returns: (summary_dict, model_name, guard_status)
    """
    fact_sheet_json = json.dumps(fact_sheet, indent=2)
    user_prompt = f"FACT SHEET:\n{fact_sheet_json}"
    model_name = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")

    try:
        raw_llm_out = generate(SBAR_PROMPT_SYSTEM, user_prompt)
        if raw_llm_out and raw_llm_out != "NOT_IN_DOCUMENTS":
            cleaned = raw_llm_out.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
                cleaned = re.sub(r"\n?```$", "", cleaned)
            draft = json.loads(cleaned)
            passed, reason = run_summary_guard(draft, fact_sheet)
            if passed:
                return draft, model_name, "PASSED_GUARD"
            else:
                logger.warning(f"AI draft failed guard: {reason}. Falling back to deterministic SBAR.")
    except Exception as e:
        logger.warning(f"LLM rewrite exception: {e}. Falling back to deterministic SBAR.")

    fallback_draft = generate_fallback_summary(fact_sheet)
    return fallback_draft, "SBAR-Deterministic-Rule-Engine", "FALLBACK_WITHOUT_AI_WORDING"
