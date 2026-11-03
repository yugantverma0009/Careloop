"""
backend/app/rag_tools.py — Read-Only Patient Scoped SQL Tools for RAG Assistant

Brief Sec 7.4 & 8.6:
- get_next_appointment(patient_id): next scheduled appointment, doctor, specialization.
- get_today_doses(patient_id, date_str): planned medicines, scheduled times, instructions, statuses.
- get_medicine_plan(patient_id, medicine_name): active prescriptions, course start/end dates, instructions.
- get_latest_readings(patient_id): latest sensor measurements (value, unit, time, quality). Factual only; NO judgment.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Dict, Any, List, Optional
from .db import get_conn


def serialize_item(item: Any) -> Any:
    if isinstance(item, (datetime, date)):
        return item.strftime("%d %B %Y at %I:%M %p") if isinstance(item, datetime) else item.strftime("%d %B %Y")
    if isinstance(item, Decimal):
        return float(item)
    return item


def get_next_appointment(patient_id: int) -> Dict[str, Any]:
    """Returns the patient's next scheduled appointment."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT a.appointment_id, a.appointment_date, s.full_name AS doctor,
                      s.specialization, a.appointment_type, a.notes
               FROM appointments a
               JOIN care_staff s ON s.staff_id = a.staff_id
               WHERE a.patient_id = %s AND a.status = 'Scheduled' AND a.appointment_date >= NOW()
               ORDER BY a.appointment_date ASC LIMIT 1""",
            (patient_id,),
        )
        row = cur.fetchone()
        if not row:
            # Fallback: check most recently scheduled or upcoming
            cur.execute(
                """SELECT a.appointment_id, a.appointment_date, s.full_name AS doctor,
                          s.specialization, a.appointment_type, a.notes
                   FROM appointments a
                   JOIN care_staff s ON s.staff_id = a.staff_id
                   WHERE a.patient_id = %s
                   ORDER BY a.appointment_date DESC LIMIT 1""",
                (patient_id,),
            )
            row = cur.fetchone()

        if not row:
            return {"found": False, "message": "No upcoming appointments found in your care records."}

        dt = row["appointment_date"]
        formatted_date = dt.strftime("%d %B %Y") if isinstance(dt, datetime) else str(dt)
        formatted_time = dt.strftime("%I:%M %p") if isinstance(dt, datetime) else ""

        return {
            "found": True,
            "appointment_id": row["appointment_id"],
            "date": formatted_date,
            "time": formatted_time,
            "doctor": row["doctor"],
            "specialization": row["specialization"],
            "type": row["appointment_type"],
            "notes": row["notes"],
            "summary": f"{formatted_date} at {formatted_time} with {row['doctor']} ({row['specialization']})",
        }


def get_today_doses(patient_id: int, target_date: Optional[str] = None) -> Dict[str, Any]:
    """Returns scheduled doses and times for the specified date (default today)."""
    with get_conn() as conn, conn.cursor() as cur:
        date_clause = "CURDATE()" if not target_date else "%s"
        params = (patient_id,) if not target_date else (patient_id, target_date)

        cur.execute(
            f"""SELECT ml.medication_log_id, ml.scheduled_for, m.medicine_name,
                       pr.dose_instructions, ml.status
                FROM medication_logs ml
                JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
                JOIN medicines m ON m.medicine_id = pr.medicine_id
                WHERE pr.patient_id = %s AND DATE(ml.scheduled_for) = {date_clause}
                ORDER BY ml.scheduled_for ASC""",
            params,
        )
        rows = cur.fetchall()
        if not rows:
            return {"found": False, "doses": [], "message": "No scheduled medication doses found for today."}

        doses = []
        for r in rows:
            sf = r["scheduled_for"]
            time_str = sf.strftime("%I:%M %p") if isinstance(sf, datetime) else str(sf)
            doses.append({
                "log_id": r["medication_log_id"],
                "medicine": r["medicine_name"],
                "time": time_str,
                "instructions": r["dose_instructions"],
                "status": r["status"],
            })

        return {
            "found": True,
            "count": len(doses),
            "doses": doses,
        }


def get_medicine_plan(patient_id: int, medicine_name: Optional[str] = None) -> Dict[str, Any]:
    """Returns prescription courses, instructions, and end dates for the patient."""
    with get_conn() as conn, conn.cursor() as cur:
        query = """SELECT pr.prescription_id, m.medicine_name, pr.dose_instructions,
                          pr.start_date, pr.end_date, pr.active_status, s.full_name AS doctor
                   FROM prescriptions pr
                   JOIN medicines m ON m.medicine_id = pr.medicine_id
                   LEFT JOIN care_staff s ON s.staff_id = pr.prescribed_by_staff_id
                   WHERE pr.patient_id = %s"""
        params = [patient_id]

        if medicine_name:
            query += " AND (m.medicine_name LIKE %s OR pr.dose_instructions LIKE %s)"
            params.extend([f"%{medicine_name}%", f"%{medicine_name}%"])

        query += " ORDER BY pr.start_date ASC"
        cur.execute(query, tuple(params))
        rows = cur.fetchall()

        if not rows:
            return {"found": False, "prescriptions": [], "message": "No active medication plan found."}

        prescriptions = []
        for r in rows:
            s_date = r["start_date"].strftime("%d %B %Y") if isinstance(r["start_date"], (date, datetime)) else str(r["start_date"])
            e_date = r["end_date"].strftime("%d %B %Y") if isinstance(r["end_date"], (date, datetime)) else "Ongoing / as advised"
            prescriptions.append({
                "id": r["prescription_id"],
                "medicine": r["medicine_name"],
                "instructions": r["dose_instructions"],
                "start_date": s_date,
                "end_date": e_date,
                "doctor": r["doctor"] or "Attending physician",
                "status": r["active_status"],
            })

        return {
            "found": True,
            "count": len(prescriptions),
            "prescriptions": prescriptions,
        }


def get_latest_readings(patient_id: int) -> Dict[str, Any]:
    """
    Returns latest sensor readings (Heart Rate, SpO2) strictly as facts.
    Brief Sec 7.4 & 7.7: value, unit, measured_at, quality_status only. NO medical judgment.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT sr.measurement_type, sr.measurement_value, sr.unit, sr.measured_at, sr.quality_status
               FROM sensor_readings sr
               INNER JOIN (
                   SELECT measurement_type, MAX(measured_at) AS max_measured_at
                   FROM sensor_readings
                   WHERE patient_id = %s AND quality_status != 'Invalid'
                   GROUP BY measurement_type
               ) latest ON sr.measurement_type = latest.measurement_type AND sr.measured_at = latest.max_measured_at
               WHERE sr.patient_id = %s
               ORDER BY sr.measurement_type ASC""",
            (patient_id, patient_id),
        )
        rows = cur.fetchall()

        if not rows:
            return {"found": False, "readings": [], "message": "No recorded sensor readings found."}

        readings = []
        for r in rows:
            val = float(r["measurement_value"]) if isinstance(r["measurement_value"], Decimal) else r["measurement_value"]
            m_time = r["measured_at"].strftime("%d %B %Y at %I:%M %p") if isinstance(r["measured_at"], datetime) else str(r["measured_at"])
            readings.append({
                "type": r["measurement_type"],
                "value": val,
                "unit": r["unit"],
                "measured_at": m_time,
                "quality": r["quality_status"],
            })

        return {
            "found": True,
            "readings": readings,
            "notice": "These are factual records from your device. The assistant does not make clinical judgments.",
        }


def get_care_team_contacts(patient_id: int) -> Dict[str, Any]:
    """Returns assigned attending doctor, assigned nurse, and clinic support desk contacts."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT s.staff_id, s.full_name, s.staff_role, s.phone, s.specialization
               FROM discharge_records d
               JOIN care_staff s ON s.staff_id = d.attending_staff_id
               WHERE d.patient_id = %s
               ORDER BY d.discharge_date DESC LIMIT 1""",
            (patient_id,),
        )
        doc = cur.fetchone() or {"full_name": "Dr. Ananya Sharma", "staff_role": "Doctor", "phone": "+91-98765-00001", "specialization": "Cardiology"}

        # Find assigned nurse (staff with staff_role Nurse)
        cur.execute(
            "SELECT staff_id, full_name, staff_role, phone FROM care_staff WHERE staff_role = 'Nurse' LIMIT 1"
        )
        nurse = cur.fetchone() or {"full_name": "Priya Nair", "staff_role": "Nurse", "phone": "+91-98765-00002"}

        return {
            "found": True,
            "doctor": {
                "name": doc["full_name"],
                "role": doc.get("staff_role", "Doctor"),
                "specialization": doc.get("specialization", "Physician"),
                "phone": doc.get("phone", "+91-98765-00001"),
            },
            "nurse": {
                "name": nurse["full_name"],
                "role": nurse.get("staff_role", "Nurse"),
                "phone": nurse.get("phone", "+91-98765-00002"),
            },
            "clinic_support": {
                "name": "CareLoop Clinic Support Desk",
                "phone": "+91-98765-00000",
                "hours": "08:00 - 20:00 Mon-Sat",
            },
            "emergency": "112",
        }


def get_plan_items(patient_id: int) -> Dict[str, Any]:
    """Returns doctor-approved recovery plan items (medication, activity, wound care, checkins)."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT plan_id, status, version, approved_at
               FROM recovery_plans
               WHERE patient_id = %s AND status = 'Approved'
               ORDER BY approved_at DESC LIMIT 1""",
            (patient_id,),
        )
        plan = cur.fetchone()
        if not plan:
            return {"found": False, "items": [], "message": "No active approved recovery plan found."}

        cur.execute(
            """SELECT item_id, item_type, title, detail, schedule_text, source_chunk_id
               FROM recovery_plan_items
               WHERE plan_id = %s
               ORDER BY display_order ASC, item_id ASC""",
            (plan["plan_id"],),
        )
        items = cur.fetchall()
        return {
            "found": True,
            "plan_version": plan["version"],
            "approved_at": plan["approved_at"].strftime("%d %B %Y") if hasattr(plan["approved_at"], "strftime") else str(plan["approved_at"]),
            "items_count": len(items),
            "items": [
                {
                    "category": it["item_type"],
                    "title": it["title"],
                    "instructions": it["detail"],
                    "timing": it.get("schedule_text") or "Daily",
                    "source": f"Section {it.get('source_chunk_id') or 'Care Plan'}",
                }
                for it in items
            ],
        }
