"""
backend/app/main.py — CareLoop API

Core Rule: "The LLM talks. Rules decide. Humans act."
All patient endpoints strictly extract patient_id from the authenticated JWT token.
"""

import os
import calendar
import re
from datetime import datetime, timedelta, date, timezone
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Header, HTTPException, Depends, Request, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import pymysql
import json
from contextlib import asynccontextmanager
from .db import get_conn
from .auth import verify_login, make_token, require_role, current_user
from .safety import has_emergency_term, EMERGENCY_GUIDANCE
from .rag import answer as rag_answer
from .llm import generate
from . import scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(
    title="CareLoop API",
    description="Agentic Post-Discharge Care System — Single source of truth: MySQL 8.0.16+",
    version="2.0.0",
    lifespan=lifespan,
)

IST = ZoneInfo("Asia/Kolkata")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Pydantic Schemas ─────────────────────────────────────────────────────────

class LoginIn(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    account_id: int
    patient_id: Optional[int] = None
    caregiver_id: Optional[int] = None
    staff_id: Optional[int] = None
    name: str


class ChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    language: Optional[str] = "en"


class ReviewSummaryIn(BaseModel):
    action: str = Field(..., pattern="^(Approve|Reject)$")
    notes: Optional[str] = None


# ─── System & Auth Endpoints ─────────────────────────────────────────────────

@app.get("/health")
def health_check():
    """System health check and MySQL connectivity verification."""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT DATABASE() AS db, NOW() AS server_time, @@time_zone AS tz")
            info = cur.fetchone()
        return {
            "status": "healthy",
            "system": "CareLoop",
            "database": info["db"],
            "server_time": str(info["server_time"]),
            "session_timezone": info["tz"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database unreachable: {e}")


@app.post("/auth/login", response_model=LoginResponse)
def login(b: LoginIn):
    """
    Authenticate Patient, Caregiver, Doctor, or Nurse using email + password.
    Returns HS256 JWT with 8-hour expiry.
    """
    acct = verify_login(b.email, b.password)
    if not acct:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Fetch user's display name based on role
    name = "User"
    with get_conn() as conn, conn.cursor() as cur:
        if acct["account_role"] == "Patient" and acct["patient_id"]:
            cur.execute("SELECT full_name FROM patients WHERE patient_id=%s", (acct["patient_id"],))
            p = cur.fetchone()
            if p:
                name = p["full_name"]
        elif acct["account_role"] == "Caregiver" and acct["caregiver_id"]:
            cur.execute("SELECT full_name FROM caregivers WHERE caregiver_id=%s", (acct["caregiver_id"],))
            c = cur.fetchone()
            if c:
                name = c["full_name"]
        elif acct["account_role"] in ("Doctor", "Nurse") and acct["staff_id"]:
            cur.execute("SELECT full_name FROM care_staff WHERE staff_id=%s", (acct["staff_id"],))
            s = cur.fetchone()
            if s:
                name = s["full_name"]

    token = make_token(acct)
    return LoginResponse(
        access_token=token,
        role=acct["account_role"],
        account_id=acct["account_id"],
        patient_id=acct["patient_id"],
        caregiver_id=acct["caregiver_id"],
        staff_id=acct["staff_id"],
        name=name,
    )


@app.get("/auth/me")
def get_current_user_profile(user: Dict[str, Any] = Depends(current_user)):
    """Return claims from the caller's validated JWT token."""
    return user


# ─── Role Verification & Profile Endpoints ────────────────────────────────────


def get_effective_patient_id(user: Dict[str, Any]) -> int:
    """Extract authenticated patient_id from JWT or through authorized Caregiver link."""
    pid = user.get("patient_id")
    if pid:
        return int(pid)
    if user.get("role") == "Caregiver" and user.get("caregiver_id"):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT patient_id, consent_granted FROM caregivers WHERE caregiver_id=%s",
                (user["caregiver_id"],),
            )
            cg = cur.fetchone()
            if cg and cg.get("consent_granted"):
                return int(cg["patient_id"])
    raise HTTPException(status_code=403, detail="No authorized patient associated with this account")

@app.get("/patient/me/profile")
def get_my_patient_profile(user: Dict[str, Any] = Depends(require_role("Patient", "Caregiver"))):
    """
    Patient profile access.
    PATIENT_ID IS SOLELY EXTRACTED FROM THE JWT. NEVER ACCEPTED VIA URL.
    """
    pid = get_effective_patient_id(user)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT patient_id, full_name, phone, date_of_birth, preferred_language, consent_status, created_at
               FROM patients WHERE patient_id=%s""",
            (pid,),
        )
        patient = cur.fetchone()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient profile not found")

        # Fetch active discharge summary
        cur.execute(
            """SELECT discharge_id, discharge_date, condition_summary, follow_up_due
               FROM discharge_records WHERE patient_id=%s ORDER BY discharge_date DESC LIMIT 1""",
            (pid,),
        )
        discharge = cur.fetchone()

        # Fetch caregiver
        cur.execute(
            """SELECT caregiver_id, full_name, relationship, phone, consent_granted, is_primary
               FROM caregivers WHERE patient_id=%s""",
            (pid,),
        )
        caregivers = cur.fetchall()

    return {
        "profile": patient,
        "discharge_record": discharge,
        "caregivers": caregivers,
    }


@app.get("/caregiver/me/profile")
def get_my_caregiver_profile(user: Dict[str, Any] = Depends(require_role("Caregiver"))):
    """Caregiver profile access."""
    cid = user["caregiver_id"]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT caregiver_id, patient_id, full_name, relationship, phone, consent_granted, is_primary
               FROM caregivers WHERE caregiver_id=%s""",
            (cid,),
        )
        caregiver = cur.fetchone()
        if not caregiver:
            raise HTTPException(status_code=404, detail="Caregiver profile not found")
    return caregiver


@app.get("/staff/me/profile")
def get_my_staff_profile(user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse"))):
    """Staff profile access for Doctors and Nurses."""
    sid = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT staff_id, full_name, staff_role, email, phone, specialization FROM care_staff WHERE staff_id=%s""",
            (sid,),
        )
        staff = cur.fetchone()
        if not staff:
            raise HTTPException(status_code=404, detail="Staff member not found")
    return staff


# ─── Device Data Ingestion (Milestone M2) ────────────────────────────────────

class ReadingIn(BaseModel):
    device_id: str
    measurement_type: str = Field(pattern="^(Heart_Rate|SpO2)$")
    value: float
    unit: str
    measured_at: int                 # epoch seconds (UTC) from the device
    quality: str = Field(pattern="^(Good|Questionable|Simulated)$")


@app.post("/device/readings")
def ingest_reading(r: ReadingIn, x_device_key: str = Header(...)):
    """
    Idempotent IoT reading ingestion endpoint.
    - Authenticates device via X-Device-Key header.
    - Converts UTC epoch seconds to Asia/Kolkata (IST).
    - Prevents duplicates via UNIQUE (device_id, measurement_type, measured_at).
    - Triggers in MySQL automatically evaluate approved alert_rules and update heartbeat.
    """
    configured_key = os.getenv("DEVICE_API_KEY", "demo-device-key-change-me")
    if x_device_key != configured_key:
        raise HTTPException(status_code=401, detail="Bad device key")

    when = datetime.fromtimestamp(r.measured_at, tz=IST).replace(tzinfo=None)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT patient_id FROM devices WHERE device_id=%s", (r.device_id,))
        dev = cur.fetchone()
        if not dev:
            raise HTTPException(status_code=404, detail=f"Unknown device '{r.device_id}'")

        try:
            cur.execute(
                """INSERT INTO sensor_readings
                   (patient_id, device_id, measurement_type, measurement_value, unit, measured_at, quality_status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (dev["patient_id"], r.device_id, r.measurement_type, r.value, r.unit, when, r.quality),
            )
        except pymysql.err.IntegrityError as e:
            if e.args[0] == 1062:  # Duplicate key error: retried upload
                return {"status": "duplicate_ignored"}
            raise

    return {"status": "stored"}


# ─── Patient Medication Doses (Milestone M3 / Phase 1 Upgrade) ────────────────

class DoseConfirmIn(BaseModel):
    status: str = Field(pattern="^(Taken_Confirmed|Skipped)$")
    patient_note: Optional[str] = None


class DoseTakenIn(BaseModel):
    taken_at: Optional[str] = None


class DoseSkipIn(BaseModel):
    reason: str = Field(default="other", pattern="^(felt_unwell|ran_out|forgot|side_effects|other)$")


DOSE_EARLY_WINDOW_MIN = 60
UNDO_WINDOW_MIN = 5


@app.get("/patient/me/today")
def get_patient_today(user: Dict[str, Any] = Depends(require_role("Patient", "Caregiver"))):
    """
    Unified Today Overview endpoint (Brief Section 8.1):
    Single query payload rendering greeting, day after discharge, banner state,
    counts, next dose, grouped doses, latest readings, device, next appointment, and week strip.
    """
    pid = get_effective_patient_id(user)
    now_ist = datetime.now(IST)
    today_ist = now_ist.date()

    with get_conn() as conn, conn.cursor() as cur:
        # 1. Patient basic profile & discharge info
        cur.execute("SELECT full_name FROM patients WHERE patient_id=%s", (pid,))
        p_row = cur.fetchone()
        name = p_row["full_name"] if p_row else "Patient"

        cur.execute(
            """SELECT discharge_date FROM discharge_records
               WHERE patient_id = %s ORDER BY discharge_date DESC LIMIT 1""",
            (pid,)
        )
        d_row = cur.fetchone()
        if d_row and d_row.get("discharge_date"):
            dis_date = d_row["discharge_date"]
            if isinstance(dis_date, datetime):
                dis_date = dis_date.date()
            day_after_discharge = max(1, (today_ist - dis_date).days)
        else:
            day_after_discharge = 1

        # 2. Banner state & Needs a look
        cur.execute(
            """SELECT flag_id, severity, source_type, reason, created_at, acknowledged_at, status
               FROM flags
               WHERE patient_id = %s
                 AND (
                   status = 'Open'
                   OR (status = 'Acknowledged' AND acknowledged_at >= NOW() - INTERVAL 24 HOUR)
                 )
               ORDER BY created_at DESC""",
            (pid,)
        )
        flags = cur.fetchall()

        banner_state = "none"
        banner_msg_key = None
        banner_raised_at = None
        needs_a_look = None

        urgent_flag = next((f for f in flags if f["status"] == "Open" and (f["severity"] in ("Urgent_Review", "Immediate_Review") or f["source_type"] == "Emergency")), None)
        review_flag = next((f for f in flags if f["status"] == "Open" and f["severity"] == "Review_Soon"), None)
        seen_flag = next((f for f in flags if f["status"] == "Acknowledged"), None)

        if urgent_flag:
            banner_state = "urgent"
            banner_msg_key = "urgent_alert"
            banner_raised_at = urgent_flag["created_at"].isoformat() if urgent_flag.get("created_at") else None
            needs_a_look = {
                "item": "Emergency notice" if urgent_flag["source_type"] == "Emergency" else "High-priority clinical update",
                "raised_at": urgent_flag["created_at"].strftime("%I:%M %p") if urgent_flag.get("created_at") else ""
            }
        elif review_flag:
            banner_state = "review"
            banner_msg_key = "review_alert"
            banner_raised_at = review_flag["created_at"].isoformat() if review_flag.get("created_at") else None
            needs_a_look = {
                "item": "Reading waiting for care team review",
                "raised_at": review_flag["created_at"].strftime("%I:%M %p") if review_flag.get("created_at") else ""
            }
        elif seen_flag:
            banner_state = "seen"
            banner_msg_key = "seen_alert"
            banner_raised_at = (seen_flag.get("acknowledged_at") or seen_flag.get("created_at")).isoformat() if (seen_flag.get("acknowledged_at") or seen_flag.get("created_at")) else None

        # 3. Today's doses
        cur.callproc("sp_generate_daily_doses", (today_ist,))
        cur.execute(
            """SELECT ml.medication_log_id, m.medicine_name, pr.dose_instructions,
                      ml.scheduled_for, ml.status, ml.reminder_sent_at, ml.recorded_at, ml.patient_note
               FROM medication_logs ml
               JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
               JOIN medicines m ON m.medicine_id = pr.medicine_id
               WHERE pr.patient_id = %s
                 AND ml.scheduled_for >= CURDATE()
                 AND ml.scheduled_for < CURDATE() + INTERVAL 1 DAY
               ORDER BY ml.scheduled_for ASC""",
            (pid,)
        )
        raw_doses = cur.fetchall()

        morning, afternoon, evening, night = [], [], [], []
        planned = len(raw_doses)
        taken = sum(1 for d in raw_doses if d["status"] in ("Taken", "Taken_Confirmed"))
        skipped = sum(1 for d in raw_doses if d["status"] == "Skipped")
        not_confirmed = sum(1 for d in raw_doses if d["status"] == "Missed")
        pending = sum(1 for d in raw_doses if d["status"] == "Unconfirmed")

        next_dose = None

        for d in raw_doses:
            sched_dt = d["scheduled_for"]
            if isinstance(sched_dt, datetime) and sched_dt.tzinfo is None:
                sched_dt = sched_dt.replace(tzinfo=IST)
            elif isinstance(sched_dt, datetime):
                sched_dt = sched_dt.astimezone(IST)

            diff_sec = (sched_dt - now_ist).total_seconds()
            diff_min = int(round(diff_sec / 60))

            if d["status"] in ("Taken", "Taken_Confirmed"):
                rel = "taken"
                pill_label = "Taken"
                pill_color = "green"
            elif d["status"] == "Skipped":
                rel = "skipped"
                pill_label = f"Skipped: {d.get('patient_note') or 'by patient'}"
                pill_color = "grey"
            elif d["status"] == "Missed":
                rel = "not_confirmed"
                pill_label = "Not confirmed"
                pill_color = "amber"
            else:  # Unconfirmed
                if diff_min > 60:
                    rel = "upcoming"
                    pill_label = "Upcoming"
                    pill_color = "grey"
                elif 0 <= diff_min <= 60:
                    rel = f"in_{diff_min}_min"
                    pill_label = f"In {diff_min} min" if diff_min > 1 else "Due now"
                    pill_color = "blue"
                elif -30 <= diff_min < 0:
                    rel = "due_now"
                    pill_label = "Due now"
                    pill_color = "amber"
                else:
                    rel = f"{abs(diff_min)}_min_late"
                    pill_label = f"{abs(diff_min)} min late"
                    pill_color = "amber"

            dose_obj = {
                "id": d["medication_log_id"],
                "medicine": d["medicine_name"],
                "dose_instructions": d["dose_instructions"] or "Prescribed oral dose",
                "scheduled_for": d["scheduled_for"].strftime("%Y-%m-%d %H:%M:%S") if isinstance(d["scheduled_for"], datetime) else str(d["scheduled_for"]),
                "scheduled_time": sched_dt.strftime("%I:%M %p"),
                "status": d["status"],
                "relative": rel,
                "pill_label": pill_label,
                "pill_color": pill_color,
                "recorded_at": d["recorded_at"].isoformat() if d.get("recorded_at") else None,
                "patient_note": d.get("patient_note"),
            }

            h = sched_dt.hour
            if h < 12:
                morning.append(dose_obj)
            elif h < 17:
                afternoon.append(dose_obj)
            elif h < 21:
                evening.append(dose_obj)
            else:
                night.append(dose_obj)

            if next_dose is None and d["status"] in ("Unconfirmed", "Missed"):
                next_dose = dose_obj

        # 4. Readings
        cur.execute(
            """SELECT measurement_type, measurement_value, unit, measured_at, quality_status
               FROM v_latest_sensor_readings WHERE patient_id=%s""",
            (pid,)
        )
        readings_rows = cur.fetchall()
        readings = [
            {
                "type": r["measurement_type"],
                "value": round(float(r["measurement_value"]), 1) if r["measurement_value"] is not None else None,
                "unit": r["unit"],
                "measured_at": r["measured_at"].strftime("%Y-%m-%d %H:%M:%S") if r.get("measured_at") else None,
                "measured_time": r["measured_at"].strftime("%I:%M %p") if r.get("measured_at") else None,
                "quality": r["quality_status"] or "Valid"
            }
            for r in readings_rows
        ]

        # 5. Device
        cur.execute(
            """SELECT connectivity_status, last_seen_at FROM v_device_status
               WHERE patient_id=%s ORDER BY last_seen_at DESC LIMIT 1""",
            (pid,)
        )
        dev = cur.fetchone()
        device_status = {
            "status": dev["connectivity_status"] if dev else "Online",
            "last_seen_at": dev["last_seen_at"].strftime("%I:%M %p") if (dev and dev.get("last_seen_at")) else None
        }

        # 6. Next appointment
        cur.execute(
            """SELECT a.appointment_id, a.appointment_date, a.appointment_type, a.status, s.full_name AS doctor_name
               FROM appointments a
               JOIN care_staff s ON s.staff_id = a.staff_id
               WHERE a.patient_id=%s AND a.status='Scheduled' AND a.appointment_date >= NOW()
               ORDER BY a.appointment_date ASC LIMIT 1""",
            (pid,)
        )
        appt_row = cur.fetchone()
        next_appt = {
            "id": appt_row["appointment_id"],
            "at": appt_row["appointment_date"].strftime("%Y-%m-%d %H:%M:%S"),
            "formatted_date": appt_row["appointment_date"].strftime("%d %b, %I:%M %p"),
            "with": appt_row["doctor_name"],
            "type": appt_row["appointment_type"],
        } if appt_row else None

        # 7. Week strip (Monday to Sunday)
        start_of_week = today_ist - timedelta(days=today_ist.weekday())
        week = []
        for i in range(7):
            w_date = start_of_week + timedelta(days=i)
            cur.execute(
                """SELECT COUNT(*) AS planned,
                          SUM(status = 'Taken_Confirmed') AS taken
                   FROM medication_logs ml
                   JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
                   WHERE pr.patient_id = %s
                     AND ml.scheduled_for >= %s AND ml.scheduled_for < %s + INTERVAL 1 DAY""",
                (pid, w_date, w_date)
            )
            w_dose = cur.fetchone() or {"planned": 0, "taken": 0}

            cur.execute(
                "SELECT 1 FROM appointments WHERE patient_id=%s AND DATE(appointment_date) = %s LIMIT 1",
                (pid, w_date)
            )
            has_appt = bool(cur.fetchone())

            cur.execute(
                "SELECT 1 FROM symptom_reports WHERE patient_id=%s AND DATE(reported_at) = %s LIMIT 1",
                (pid, w_date)
            )
            has_checkin = bool(cur.fetchone())

            week.append({
                "date": w_date.strftime("%Y-%m-%d"),
                "day_name": w_date.strftime("%a"),
                "day_initial": w_date.strftime("%a")[0],
                "day_num": w_date.strftime("%d"),
                "is_today": w_date == today_ist,
                "planned": int(w_dose["planned"] or 0),
                "taken": int(w_dose["taken"] or 0),
                "appointment": has_appt,
                "checkin": has_checkin,
            })

        # 8. Plan checklist (Brief Sec 6.6)
        cur.execute(
            """SELECT MAX(end_date) AS course_end FROM prescriptions
               WHERE patient_id = %s AND active_status = TRUE""",
            (pid,)
        )
        course_row = cur.fetchone()
        course_end = course_row["course_end"] if course_row else None
        course_end_str = course_end.strftime("%d %b %Y") if course_end else None

        cur.execute(
            """SELECT COUNT(DISTINCT DATE(reported_at)) AS checkins_count
               FROM symptom_reports
               WHERE patient_id = %s
                 AND reported_at >= %s AND reported_at < %s + INTERVAL 7 DAY""",
            (pid, start_of_week, start_of_week)
        )
        c_row = cur.fetchone() or {"checkins_count": 0}
        checkins_this_week_str = f"{int(c_row['checkins_count'] or 0)} of 7 days"

        plan_checklist = {
            "next_appointment": {
                "id": next_appt["id"] if next_appt else None,
                "date": next_appt["formatted_date"] if next_appt else None,
                "doctor": next_appt["with"] if next_appt else None,
                "type": next_appt["type"] if next_appt else None,
            } if next_appt else None,
            "course_end_date": course_end_str,
            "checkins_this_week": checkins_this_week_str,
            "day_after_discharge": day_after_discharge,
        }

    return {
        "date": today_ist.strftime("%Y-%m-%d"),
        "formatted_date": now_ist.strftime("%A, %d %B %Y"),
        "name": name,
        "day_after_discharge": day_after_discharge,
        "banner": {
            "state": banner_state,
            "message_key": banner_msg_key,
            "raised_at": banner_raised_at,
        },
        "needs_a_look": needs_a_look,
        "counts": {
            "planned": planned,
            "taken": taken,
            "skipped": skipped,
            "not_confirmed": not_confirmed,
            "pending": pending,
        },
        "next_dose": next_dose,
        "doses": {
            "morning": morning,
            "afternoon": afternoon,
            "evening": evening,
            "night": night,
        },
        "all_doses": morning + afternoon + evening + night,
        "readings": readings,
        "device": device_status,
        "next_appointment": next_appt,
        "week": week,
        "plan_checklist": plan_checklist,
    }


@app.post("/patient/me/doses/{log_id}/taken")
def mark_dose_taken(
    log_id: int,
    body: DoseTakenIn = DoseTakenIn(),
    user: Dict[str, Any] = Depends(require_role("Patient", "Caregiver")),
):
    """
    Mark dose as Taken (Brief Section 6.2, 8.2).
    - Checks 60-min early window (>60 min ahead returns 409).
    - Idempotent on repeated taps.
    - Writes immutable audit log.
    """
    pid = get_effective_patient_id(user)
    actor_role = user["role"]
    now_ist = datetime.now(IST)

    with get_conn() as conn, conn.cursor() as cur:
        # Verify ownership
        cur.execute(
            """SELECT ml.medication_log_id, ml.scheduled_for, ml.status, m.medicine_name
               FROM medication_logs ml
               JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
               JOIN medicines m ON m.medicine_id = pr.medicine_id
               WHERE ml.medication_log_id = %s AND pr.patient_id = %s""",
            (log_id, pid),
        )
        dose = cur.fetchone()
        if not dose:
            raise HTTPException(status_code=404, detail="Medication dose log not found for this patient")

        # Idempotent if already taken
        if dose["status"] == "Taken_Confirmed":
            return {"status": "updated", "dose_id": log_id, "recorded_status": "Taken_Confirmed"}

        # Check early window (>60 min in future)
        sched_dt = dose["scheduled_for"]
        if isinstance(sched_dt, datetime) and sched_dt.tzinfo is None:
            sched_dt = sched_dt.replace(tzinfo=IST)
        diff_sec = (sched_dt - now_ist).total_seconds()
        if diff_sec > DOSE_EARLY_WINDOW_MIN * 60:
            raise HTTPException(
                status_code=409,
                detail=f"This dose is scheduled for {sched_dt.strftime('%I:%M %p')}. You can mark it starting 1 hour before.",
            )

        # Update dose
        cur.execute(
            """UPDATE medication_logs
               SET status = 'Taken_Confirmed', recorded_at = NOW(), recorded_by = %s, patient_note = NULL
               WHERE medication_log_id = %s""",
            (actor_role, log_id),
        )

        # Audit log
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES (%s, %s, 'TAKE_DOSE', 'medication_log', %s,
                       JSON_OBJECT('status', 'Taken_Confirmed', 'medicine', %s, 'patient_id', %s))""",
            (actor_role, str(user["account_id"]), log_id, dose["medicine_name"], pid),
        )

    return {"status": "updated", "dose_id": log_id, "recorded_status": "Taken_Confirmed"}


@app.post("/patient/me/doses/{log_id}/skip")
def skip_dose(
    log_id: int,
    body: DoseSkipIn,
    user: Dict[str, Any] = Depends(require_role("Patient", "Caregiver")),
):
    """
    Skip dose with patient-provided reason (Brief Section 6.2, 8.2).
    - Preserves distinction between user-skipped and system unconfirmed.
    - Writes immutable audit log.
    """
    pid = get_effective_patient_id(user)
    actor_role = user["role"]

    with get_conn() as conn, conn.cursor() as cur:
        # Verify ownership
        cur.execute(
            """SELECT ml.medication_log_id, ml.status, m.medicine_name
               FROM medication_logs ml
               JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
               JOIN medicines m ON m.medicine_id = pr.medicine_id
               WHERE ml.medication_log_id = %s AND pr.patient_id = %s""",
            (log_id, pid),
        )
        dose = cur.fetchone()
        if not dose:
            raise HTTPException(status_code=404, detail="Medication dose log not found for this patient")

        # Update dose
        cur.execute(
            """UPDATE medication_logs
               SET status = 'Skipped', recorded_at = NOW(), recorded_by = %s, patient_note = %s
               WHERE medication_log_id = %s""",
            (actor_role, body.reason, log_id),
        )

        # Audit log
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES (%s, %s, 'SKIP_DOSE', 'medication_log', %s,
                       JSON_OBJECT('status', 'Skipped', 'reason', %s, 'medicine', %s, 'patient_id', %s))""",
            (actor_role, str(user["account_id"]), log_id, body.reason, dose["medicine_name"], pid),
        )

    return {"status": "updated", "dose_id": log_id, "recorded_status": "Skipped"}


@app.post("/patient/me/doses/{log_id}/undo")
def undo_dose(
    log_id: int,
    user: Dict[str, Any] = Depends(require_role("Patient", "Caregiver")),
):
    """
    Undo dose action within 5-minute safety window (Brief Section 6.2, 8.2).
    - Reverts dose to Unconfirmed.
    - Returns 409 if 5-minute undo window expired.
    - Writes immutable audit log.
    """
    pid = get_effective_patient_id(user)
    actor_role = user["role"]

    with get_conn() as conn, conn.cursor() as cur:
        # Verify ownership
        cur.execute(
            """SELECT ml.medication_log_id, ml.status, m.medicine_name
               FROM medication_logs ml
               JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
               JOIN medicines m ON m.medicine_id = pr.medicine_id
               WHERE ml.medication_log_id = %s AND pr.patient_id = %s""",
            (log_id, pid),
        )
        dose = cur.fetchone()
        if not dose:
            raise HTTPException(status_code=404, detail="Medication dose log not found for this patient")

        if dose["status"] not in ("Taken_Confirmed", "Skipped"):
            raise HTTPException(status_code=409, detail="Dose is not currently marked as taken or skipped.")

        # Check undo window against last audit_log entry
        cur.execute(
            """SELECT created_at FROM audit_log
               WHERE entity_type = 'medication_log' AND entity_id = %s
                 AND action IN ('TAKE_DOSE', 'SKIP_DOSE', 'CONFIRM_DOSE')
               ORDER BY created_at DESC LIMIT 1""",
            (log_id,),
        )
        alog = cur.fetchone()
        if not alog:
            raise HTTPException(status_code=409, detail="No recent action found to undo.")

        elapsed = (datetime.now() - alog["created_at"]).total_seconds()
        if elapsed > UNDO_WINDOW_MIN * 60:
            raise HTTPException(status_code=409, detail="Undo window of 5 minutes has expired.")

        # Reset dose to Unconfirmed
        cur.execute(
            """UPDATE medication_logs
               SET status = 'Unconfirmed', recorded_at = NULL, recorded_by = NULL, patient_note = NULL
               WHERE medication_log_id = %s""",
            (log_id,),
        )

        # Audit log
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES (%s, %s, 'UNDO_DOSE', 'medication_log', %s,
                       JSON_OBJECT('status', 'Unconfirmed', 'medicine', %s, 'patient_id', %s))""",
            (actor_role, str(user["account_id"]), log_id, dose["medicine_name"], pid),
        )

    return {"status": "updated", "dose_id": log_id, "recorded_status": "Unconfirmed"}


@app.get("/patient/me/calendar")
def get_patient_calendar(
    month: Optional[str] = None,
    user: Dict[str, Any] = Depends(require_role("Patient", "Caregiver")),
):
    """
    Calendar Month Summary endpoint (Brief Sec 8.3 & 6.3):
    Returns month summary of doses (planned, taken, skipped, not_confirmed),
    appointments, check-ins, max pain score for each day, and upcoming appointments.
    """
    pid = get_effective_patient_id(user)
    now_ist = datetime.now(IST)
    today_ist = now_ist.date()

    if not month:
        month = now_ist.strftime("%Y-%m")
    elif not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", month):
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_month_format", "message": "Month must be in YYYY-MM format (e.g. 2026-10)"}
        )

    year, month_num = map(int, month.split("-"))
    num_days = calendar.monthrange(year, month_num)[1]
    start_dt = date(year, month_num, 1)
    end_dt = date(year + 1, 1, 1) if month_num == 12 else date(year, month_num + 1, 1)

    with get_conn() as conn, conn.cursor() as cur:
        # 1. Dose aggregation by day (range predicate instead of DATE on scheduled_for)
        cur.execute(
            """SELECT DATE(ml.scheduled_for) AS log_day,
                      COUNT(*) AS planned,
                      SUM(ml.status = 'Taken_Confirmed') AS taken,
                      SUM(ml.status = 'Skipped') AS skipped,
                      SUM(ml.status IN ('Missed', 'Unconfirmed')) AS not_confirmed
               FROM medication_logs ml
               JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
               WHERE pr.patient_id = %s
                 AND ml.scheduled_for >= %s AND ml.scheduled_for < %s
               GROUP BY DATE(ml.scheduled_for)""",
            (pid, start_dt, end_dt)
        )
        dose_rows = cur.fetchall()
        doses_by_day = {
            r["log_day"]: {
                "planned": int(r["planned"] or 0),
                "taken": int(r["taken"] or 0),
                "skipped": int(r["skipped"] or 0),
                "not_confirmed": int(r["not_confirmed"] or 0),
            }
            for r in dose_rows
        }

        # 2. Appointments in month
        cur.execute(
            """SELECT a.appointment_id, a.appointment_date, a.appointment_type, a.status,
                      s.full_name AS doctor_name, s.specialization
               FROM appointments a
               JOIN care_staff s ON s.staff_id = a.staff_id
               WHERE a.patient_id = %s
                 AND a.appointment_date >= %s AND a.appointment_date < %s
               ORDER BY a.appointment_date ASC""",
            (pid, start_dt, end_dt)
        )
        appts = cur.fetchall()
        appts_by_day = {}
        for a in appts:
            a_date = a["appointment_date"].date() if isinstance(a["appointment_date"], datetime) else a["appointment_date"]
            if a_date not in appts_by_day:
                appts_by_day[a_date] = []
            appts_by_day[a_date].append({
                "id": a["appointment_id"],
                "scheduled_at": a["appointment_date"].strftime("%Y-%m-%d %H:%M:%S") if isinstance(a["appointment_date"], datetime) else str(a["appointment_date"]),
                "formatted_time": a["appointment_date"].strftime("%I:%M %p") if isinstance(a["appointment_date"], datetime) else "",
                "doctor_name": a["doctor_name"],
                "department": a["specialization"] or "Care Clinic",
                "type": a["appointment_type"],
                "status": a["status"],
            })

        # 3. Check-ins in month
        cur.execute(
            """SELECT symptom_report_id, reported_at, pain_level
               FROM symptom_reports
               WHERE patient_id = %s
                 AND reported_at >= %s AND reported_at < %s
               ORDER BY reported_at ASC""",
            (pid, start_dt, end_dt)
        )
        checkin_rows = cur.fetchall()
        checkins_by_day = {}
        for c in checkin_rows:
            c_date = c["reported_at"].date() if isinstance(c["reported_at"], datetime) else c["reported_at"]
            if c_date not in checkins_by_day:
                checkins_by_day[c_date] = []
            checkins_by_day[c_date].append(c)

        # 4. Upcoming scheduled appointments for this patient
        cur.execute(
            """SELECT a.appointment_id, a.appointment_date, a.appointment_type, a.status,
                      s.full_name AS doctor_name, s.specialization, a.notes
               FROM appointments a
               JOIN care_staff s ON s.staff_id = a.staff_id
               WHERE a.patient_id = %s AND a.status = 'Scheduled'
                 AND a.appointment_date >= NOW() - INTERVAL 1 DAY
               ORDER BY a.appointment_date ASC LIMIT 5""",
            (pid,)
        )
        upcoming_rows = cur.fetchall()
        upcoming_appointments = [
            {
                "id": u["appointment_id"],
                "scheduled_at": u["appointment_date"].strftime("%Y-%m-%d %H:%M:%S") if isinstance(u["appointment_date"], datetime) else str(u["appointment_date"]),
                "formatted_date": u["appointment_date"].strftime("%a, %d %b %Y at %I:%M %p") if isinstance(u["appointment_date"], datetime) else "",
                "doctor_name": u["doctor_name"],
                "department": u["specialization"] or "Care Clinic",
                "type": u["appointment_type"],
                "status": u["status"],
            }
            for u in upcoming_rows
        ]

        # 5. Build days array
        days = []
        for d in range(1, num_days + 1):
            curr_date = date(year, month_num, d)
            d_doses = doses_by_day.get(curr_date, {"planned": 0, "taken": 0, "skipped": 0, "not_confirmed": 0})
            d_appts = appts_by_day.get(curr_date, [])
            d_checkins = checkins_by_day.get(curr_date, [])
            pain_scores = [c["pain_level"] for c in d_checkins if c["pain_level"] is not None]
            max_pain = max(pain_scores) if pain_scores else None

            days.append({
                "date": curr_date.strftime("%Y-%m-%d"),
                "day": d,
                "day_of_week": curr_date.weekday(),  # 0=Monday, 6=Sunday
                "is_today": curr_date == today_ist,
                "is_past": curr_date < today_ist,
                "is_future": curr_date > today_ist,
                "planned": d_doses["planned"],
                "taken": d_doses["taken"],
                "skipped": d_doses["skipped"],
                "not_confirmed": d_doses["not_confirmed"],
                "has_appointment": len(d_appts) > 0,
                "appointments": d_appts,
                "has_checkin": len(d_checkins) > 0,
                "checkin_count": len(d_checkins),
                "max_pain": max_pain,
            })

    return {
        "month": month,
        "month_name": start_dt.strftime("%B %Y"),
        "days": days,
        "upcoming_appointments": upcoming_appointments,
    }


@app.get("/patient/me/day")
def get_patient_day(
    date_str: str = Query(..., alias="date"),
    user: Dict[str, Any] = Depends(require_role("Patient", "Caregiver")),
):
    """
    Day Inspection Sheet endpoint (Brief Sec 8.3 & 6.3):
    Returns full detail for the day sheet drawer:
    all doses with status, appointments, and check-ins (pain score and notes).
    """
    pid = get_effective_patient_id(user)
    if not re.match(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$", date_str):
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_date_format", "message": "Date must be in YYYY-MM-DD format"}
        )

    try:
        y, m, d = map(int, date_str.split("-"))
        target_date = date(y, m, d)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_date", "message": "Invalid calendar date"}
        )

    with get_conn() as conn, conn.cursor() as cur:
        # Doses
        cur.execute(
            """SELECT ml.medication_log_id, m.medicine_name, pr.dose_instructions,
                      ml.scheduled_for, ml.status, ml.recorded_at, ml.patient_note
               FROM medication_logs ml
               JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
               JOIN medicines m ON m.medicine_id = pr.medicine_id
               WHERE pr.patient_id = %s
                 AND ml.scheduled_for >= %s AND ml.scheduled_for < %s + INTERVAL 1 DAY
               ORDER BY ml.scheduled_for ASC""",
            (pid, target_date, target_date)
        )
        dose_rows = cur.fetchall()
        doses = [
            {
                "id": d["medication_log_id"],
                "medicine": d["medicine_name"],
                "dose_instructions": d["dose_instructions"] or "Prescribed dose",
                "scheduled_for": d["scheduled_for"].strftime("%Y-%m-%d %H:%M:%S") if isinstance(d["scheduled_for"], datetime) else str(d["scheduled_for"]),
                "scheduled_time": d["scheduled_for"].strftime("%I:%M %p") if isinstance(d["scheduled_for"], datetime) else "",
                "status": d["status"],
                "recorded_at": d["recorded_at"].strftime("%I:%M %p") if isinstance(d.get("recorded_at"), datetime) else None,
                "patient_note": d.get("patient_note"),
            }
            for d in dose_rows
        ]

        # Appointments
        cur.execute(
            """SELECT a.appointment_id, a.appointment_date, a.appointment_type, a.status,
                      s.full_name AS doctor_name, s.specialization, a.notes
               FROM appointments a
               JOIN care_staff s ON s.staff_id = a.staff_id
               WHERE a.patient_id = %s
                 AND a.appointment_date >= %s AND a.appointment_date < %s + INTERVAL 1 DAY
               ORDER BY a.appointment_date ASC""",
            (pid, target_date, target_date)
        )
        appts_rows = cur.fetchall()
        appointments = [
            {
                "id": a["appointment_id"],
                "scheduled_at": a["appointment_date"].strftime("%Y-%m-%d %H:%M:%S") if isinstance(a["appointment_date"], datetime) else str(a["appointment_date"]),
                "formatted_time": a["appointment_date"].strftime("%I:%M %p") if isinstance(a["appointment_date"], datetime) else "",
                "doctor_name": a["doctor_name"],
                "department": a["specialization"] or "Care Clinic",
                "type": a["appointment_type"],
                "status": a["status"],
            }
            for a in appts_rows
        ]

        # Checkins
        cur.execute(
            """SELECT sr.symptom_report_id, sr.reported_at, sr.pain_level, sr.symptom_text, sr.input_method
               FROM symptom_reports sr
               WHERE sr.patient_id = %s
                 AND sr.reported_at >= %s AND sr.reported_at < %s + INTERVAL 1 DAY
               ORDER BY sr.reported_at ASC""",
            (pid, target_date, target_date)
        )
        checkin_rows = cur.fetchall()
        checkins = [
            {
                "id": c["symptom_report_id"],
                "reported_at": c["reported_at"].strftime("%I:%M %p") if isinstance(c["reported_at"], datetime) else str(c["reported_at"]),
                "pain_level": c["pain_level"],
                "note": c["symptom_text"],
                "input_method": c["input_method"],
            }
            for c in checkin_rows
        ]

    return {
        "date": date_str,
        "formatted_date": target_date.strftime("%A, %d %B %Y"),
        "doses": doses,
        "appointments": appointments,
        "checkins": checkins,
    }


@app.get("/patient/me/appointments/{appointment_id}.ics")
def download_appointment_ics(
    appointment_id: int,
    user: Dict[str, Any] = Depends(require_role("Patient", "Caregiver")),
):
    """
    Export appointment to standard RFC 5545 iCalendar file (.ics).
    Brief Sec 8.3 & 8.5:
    - Times converted to UTC (IST is UTC+5:30)
    - Strictly no clinical diagnosis details in summary or description
    - 404 if not found or belongs to another patient
    """
    pid = get_effective_patient_id(user)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT a.appointment_id, a.appointment_date, a.appointment_type, a.status,
                      s.full_name AS doctor_name, s.specialization
               FROM appointments a
               JOIN care_staff s ON s.staff_id = a.staff_id
               WHERE a.appointment_id = %s AND a.patient_id = %s""",
            (appointment_id, pid),
        )
        appt = cur.fetchone()
        if not appt:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": "Appointment not found for this patient"}
            )

        appt_dt = appt["appointment_date"]
        # Convert IST datetime to UTC
        if appt_dt.tzinfo is None:
            appt_dt_ist = appt_dt.replace(tzinfo=IST)
        else:
            appt_dt_ist = appt_dt.astimezone(IST)
        appt_dt_utc = appt_dt_ist.astimezone(timezone.utc)
        appt_end_utc = appt_dt_utc + timedelta(minutes=30)

        dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dtstart = appt_dt_utc.strftime("%Y%m%dT%H%M%SZ")
        dtend = appt_end_utc.strftime("%Y%m%dT%H%M%SZ")

        doc_name = appt["doctor_name"] or "Care Team Clinician"
        dept = appt["specialization"] or "Follow-up Clinic"

        # Strictly non-clinical text (Brief Sec 8.5)
        summary = f"Follow-up visit with {doc_name}"
        description = f"Follow-up appointment at CareLoop ({dept}). Please arrive 10 minutes early with your discharge summary papers."

        ics_lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//CareLoop//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "BEGIN:VEVENT",
            f"UID:appointment-{appointment_id}@careloop",
            f"DTSTAMP:{dtstamp}",
            f"DTSTART:{dtstart}",
            f"DTEND:{dtend}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{description}",
            "STATUS:CONFIRMED",
            "END:VEVENT",
            "END:VCALENDAR",
        ]
        ics_content = "\r\n".join(ics_lines) + "\r\n"

        return Response(
            content=ics_content,
            media_type="text/calendar; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="appointment_{appointment_id}.ics"',
                "Cache-Control": "no-cache",
            },
        )


@app.get("/patient/me/doses")
def get_my_doses(user: Dict[str, Any] = Depends(require_role("Patient", "Caregiver"))):
    """
    Returns today's scheduled medication doses for the authenticated patient.
    PATIENT_ID IS STRICTLY EXTRACTED FROM JWT.
    """
    pid = get_effective_patient_id(user)
    with get_conn() as conn, conn.cursor() as cur:
        # Generate daily doses if not yet generated
        cur.callproc("sp_generate_daily_doses", (datetime.now(IST).date(),))

        cur.execute(
            """SELECT ml.medication_log_id, m.medicine_name, pr.dose_instructions,
                      ml.scheduled_for, ml.status, ml.reminder_sent_at, ml.recorded_at, ml.patient_note
               FROM medication_logs ml
               JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
               JOIN medicines m ON m.medicine_id = pr.medicine_id
               WHERE pr.patient_id = %s
                 AND ml.scheduled_for >= CURDATE()
                 AND ml.scheduled_for < CURDATE() + INTERVAL 1 DAY
               ORDER BY ml.scheduled_for""",
            (pid,),
        )
        return cur.fetchall()


@app.post("/patient/me/doses/{log_id}/confirm")
def confirm_my_dose(
    log_id: int,
    body: DoseConfirmIn,
    user: Dict[str, Any] = Depends(require_role("Patient", "Caregiver")),
):
    """
    Confirm a dose as Taken_Confirmed or Skipped.
    Allowed for:
    - Patient (confirms own dose)
    - Caregiver (confirms on patient's behalf if consent granted)
    Writes to audit_log.
    """
    actor_role = user["role"]
    pid = user["patient_id"]

    with get_conn() as conn, conn.cursor() as cur:
        if actor_role == "Caregiver":
            # Look up caregiver's assigned patient
            cur.execute(
                "SELECT patient_id, consent_granted FROM caregivers WHERE caregiver_id=%s",
                (user["caregiver_id"],),
            )
            cg = cur.fetchone()
            if not cg or not cg["consent_granted"]:
                raise HTTPException(status_code=403, detail="Caregiver consent not granted for this patient")
            pid = cg["patient_id"]

        # Ensure dose log belongs to this patient
        cur.execute(
            """SELECT ml.medication_log_id, ml.status, m.medicine_name
               FROM medication_logs ml
               JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
               JOIN medicines m ON m.medicine_id = pr.medicine_id
               WHERE ml.medication_log_id = %s AND pr.patient_id = %s""",
            (log_id, pid),
        )
        dose = cur.fetchone()
        if not dose:
            raise HTTPException(status_code=404, detail="Medication dose log not found for this patient")

        # Update log
        cur.execute(
            """UPDATE medication_logs
               SET status = %s, recorded_at = NOW(), recorded_by = %s, patient_note = %s
               WHERE medication_log_id = %s""",
            (body.status, actor_role, body.patient_note, log_id),
        )

        # Write immutable audit log
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES (%s, %s, 'CONFIRM_DOSE', 'medication_log', %s,
                       JSON_OBJECT('status', %s, 'medicine', %s, 'patient_id', %s))""",
            (actor_role, str(user["account_id"]), log_id, body.status, dose["medicine_name"], pid),
        )

    return {"status": "updated", "dose_id": log_id, "recorded_status": body.status}


# ─── Symptom Check-in & Emergency Layer (Milestone M3 & Phase 3) ──────────────

class SymptomIn(BaseModel):
    text: str
    pain_level: int = Field(default=0, ge=0, le=10)
    input_method: str = Field(default="Text", pattern="^(Text|Voice_Transcript|Caregiver)$")
    language: str = Field(default="en", pattern="^(en|hi)$")


class CheckinIn(BaseModel):
    pain_level: Optional[int] = Field(None, ge=0, le=10)
    chips: List[str] = Field(default_factory=list)
    sites: List[str] = Field(default_factory=list)
    trend: Optional[str] = None  # 'better' | 'same' | 'worse' | None
    text: str = Field(default="", max_length=1000)
    language: str = Field(default="en", pattern="^(en|hi)$")
    input_method: str = Field(default="Text", pattern="^(Text|Voice_Transcript|Caregiver)$")


def extract_and_save_symptom_tags(report_id: int, symptom_text: str):
    """
    Extract 1-3 short tags from symptom text using LLM.
    Convenience feature (C10.4): fails silently if LLM is unavailable.
    """
    try:
        prompt = (
            "Extract 1 to 3 concise symptom tags describing the patient's complaint. "
            "Reply strictly with a JSON array of lowercase strings (e.g. [\"headache\", \"mild fever\"]). "
            "Do not include any diagnosis or explanations.\n\n"
            f"Patient complaint: {symptom_text}"
        )
        out = generate("You are a medical tagger. Return valid JSON only.", prompt)
        start_idx = out.find("[")
        end_idx = out.rfind("]")
        if start_idx != -1 and end_idx != -1:
            tags = json.loads(out[start_idx : end_idx + 1])
            if isinstance(tags, list):
                with get_conn() as conn, conn.cursor() as cur:
                    for tag in tags[:3]:
                        tag_clean = str(tag).strip().lower()[:40]
                        if tag_clean:
                            cur.execute(
                                """INSERT IGNORE INTO symptom_report_tags (symptom_report_id, tag, extracted_by)
                                   VALUES (%s, %s, 'LLM')""",
                                (report_id, tag_clean),
                            )
    except Exception:
        pass


@app.post("/patient/me/checkins")
def submit_patient_checkin(
    body: CheckinIn,
    user: Dict[str, Any] = Depends(require_role("Patient", "Caregiver")),
):
    """
    Phase 3 Daily Check-in Endpoint (Brief Sec 6.4 & 8.4):
    - Multi-select symptom chips, pain location sites, trend vs yesterday.
    - Deterministic emergency detector (English + Hindi words + emergency chips: short_of_breath, chest_pain).
    - Emergency guidance returned immediately without waiting for LLM!
    - Duplicate protection: same patient, same text, same pain within 60s returns existing report.
    - Tags written to symptom_report_tags with extracted_by = 'Patient_Form'.
    - Patient audit_log recorded.
    """
    pid = get_effective_patient_id(user)

    # Emergency detection on chips or note
    emergency_chips = {"short_of_breath", "chest_pain", "सांस_लेने_में_तकलीफ", "सीने_में_दर्द"}
    has_emergency_chip = any(c.strip().lower().replace(" ", "_") in emergency_chips for c in body.chips)
    emergency = has_emergency_chip or has_emergency_term(body.text)
    guidance = EMERGENCY_GUIDANCE.get(body.language, EMERGENCY_GUIDANCE["en"]) if emergency else None

    # Assemble text if empty
    effective_text = body.text.strip()
    if not effective_text:
        parts = []
        if body.pain_level is not None:
            parts.append(f"Pain {body.pain_level}/10")
        if body.chips:
            parts.append("Symptoms: " + ", ".join(body.chips))
        if body.sites:
            parts.append("Locations: " + ", ".join(body.sites))
        if body.trend:
            parts.append(f"Trend: {body.trend}")
        effective_text = " | ".join(parts) if parts else "Daily check-in"

    with get_conn() as conn, conn.cursor() as cur:
        # Duplicate protection (Brief Sec 6.4): same patient, same text, same pain within 60s
        cur.execute(
            """SELECT symptom_report_id, emergency_keyword_hit
               FROM symptom_reports
               WHERE patient_id = %s
                 AND symptom_text = %s
                 AND (pain_level = %s OR (pain_level IS NULL AND %s IS NULL))
                 AND reported_at >= NOW() - INTERVAL 60 SECOND
               ORDER BY reported_at DESC LIMIT 1""",
            (pid, effective_text, body.pain_level, body.pain_level),
        )
        dup = cur.fetchone()
        if dup:
            is_emerg = bool(dup["emergency_keyword_hit"])
            return {
                "status": "duplicate_prevented",
                "report_id": dup["symptom_report_id"],
                "emergency": is_emerg,
                "guidance": EMERGENCY_GUIDANCE.get(body.language, EMERGENCY_GUIDANCE["en"]) if is_emerg else None,
            }

        cur.execute(
            """INSERT INTO symptom_reports
               (patient_id, symptom_text, pain_level, input_method, language, emergency_keyword_hit)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (pid, effective_text, body.pain_level, body.input_method, body.language, emergency),
        )
        report_id = cur.lastrowid

        # Insert structured tags from form (Brief Sec 6.4)
        for chip in body.chips:
            c_tag = chip.strip().lower()[:40]
            if c_tag and c_tag not in ("none_of_these", "none"):
                cur.execute(
                    """INSERT IGNORE INTO symptom_report_tags (symptom_report_id, tag, extracted_by)
                       VALUES (%s, %s, 'Patient_Form')""",
                    (report_id, c_tag),
                )
        for site in body.sites:
            s_tag = f"site:{site.strip().lower()}"[:40]
            cur.execute(
                """INSERT IGNORE INTO symptom_report_tags (symptom_report_id, tag, extracted_by)
                   VALUES (%s, %s, 'Patient_Form')""",
                (report_id, s_tag),
            )
        if body.trend:
            t_tag = f"trend:{body.trend.strip().lower()}"[:40]
            cur.execute(
                """INSERT IGNORE INTO symptom_report_tags (symptom_report_id, tag, extracted_by)
                   VALUES (%s, %s, 'Patient_Form')""",
                (report_id, t_tag),
            )

        # Audit log
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Patient', %s, 'SUBMIT_CHECKIN', 'symptom_report', %s,
                       JSON_OBJECT('emergency_hit', %s, 'pain_level', %s, 'lang', %s, 'input_method', %s))""",
            (str(user["account_id"]), report_id, emergency, body.pain_level, body.language, body.input_method),
        )

    # Optional background LLM tag extraction
    if body.text.strip():
        extract_and_save_symptom_tags(report_id, body.text)

    return {
        "status": "recorded",
        "report_id": report_id,
        "emergency": emergency,
        "guidance": guidance,
    }


@app.get("/patient/me/checkins")
def get_patient_checkins(
    days: int = Query(14, ge=1, le=90),
    user: Dict[str, Any] = Depends(require_role("Patient", "Caregiver")),
):
    """
    Returns last N days of check-in reports for the authenticated patient.
    Brief Sec 8.4:
    - Pain score, note text, date, tags, input_method.
    """
    pid = get_effective_patient_id(user)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT sr.symptom_report_id, sr.reported_at, sr.pain_level, sr.symptom_text,
                      sr.input_method, sr.language, sr.emergency_keyword_hit,
                      GROUP_CONCAT(srt.tag SEPARATOR ',') AS tags
               FROM symptom_reports sr
               LEFT JOIN symptom_report_tags srt ON srt.symptom_report_id = sr.symptom_report_id
               WHERE sr.patient_id = %s
                 AND sr.reported_at >= NOW() - INTERVAL %s DAY
               GROUP BY sr.symptom_report_id
               ORDER BY sr.reported_at DESC""",
            (pid, days),
        )
        rows = cur.fetchall()
        reports = [
            {
                "id": r["symptom_report_id"],
                "reported_at": r["reported_at"].strftime("%Y-%m-%d %H:%M:%S") if isinstance(r["reported_at"], datetime) else str(r["reported_at"]),
                "formatted_date": r["reported_at"].strftime("%d %b, %I:%M %p") if isinstance(r["reported_at"], datetime) else "",
                "date": r["reported_at"].strftime("%Y-%m-%d") if isinstance(r["reported_at"], datetime) else "",
                "pain_level": r["pain_level"],
                "text": r["symptom_text"],
                "input_method": r["input_method"],
                "language": r["language"],
                "emergency": bool(r["emergency_keyword_hit"]),
                "tags": [t.strip() for t in r["tags"].split(",")] if r.get("tags") else [],
            }
            for r in rows
        ]
        return {"days": days, "count": len(reports), "reports": reports}


@app.post("/patient/me/symptoms")
def submit_symptom_checkin(body: SymptomIn, user: Dict[str, Any] = Depends(require_role("Patient", "Caregiver"))):
    """
    Legacy Symptom Check-in Endpoint (maintained for backward compatibility):
    Forwards to submit_patient_checkin.
    """
    checkin_body = CheckinIn(
        pain_level=body.pain_level,
        chips=[],
        sites=[],
        trend=None,
        text=body.text,
        language=body.language,
        input_method=body.input_method,
    )
    return submit_patient_checkin(checkin_body, user)


# ─── Patient Status Page (Milestone M3) ──────────────────────────────────────

@app.get("/patient/me/status")
def get_my_status(user: Dict[str, Any] = Depends(require_role("Patient", "Caregiver"))):
    """
    Patient Status Page:
    - Latest readings with quality label from v_latest_sensor_readings.
    - Device connectivity status from v_device_status (flags Missing_Data).
    - Next scheduled appointment.
    - Active clinical flags.
    Never shows missing data as 0 or normal!
    """
    pid = get_effective_patient_id(user)
    with get_conn() as conn, conn.cursor() as cur:
        # 1. Latest readings
        cur.execute(
            """SELECT measurement_type, measurement_value, unit, measured_at, quality_status
               FROM v_latest_sensor_readings WHERE patient_id=%s""",
            (pid,),
        )
        readings = cur.fetchall()

        # 2. Devices status
        cur.execute(
            """SELECT device_id, device_type, connectivity_status, last_seen_at
               FROM v_device_status WHERE patient_id=%s""",
            (pid,),
        )
        devices = cur.fetchall()

        # 3. Next appointment
        cur.execute(
            """SELECT a.appointment_id, a.appointment_date, a.appointment_type, a.status, s.full_name AS doctor_name
               FROM appointments a
               JOIN care_staff s ON s.staff_id = a.staff_id
               WHERE a.patient_id=%s AND a.status='Scheduled' AND a.appointment_date >= NOW()
               ORDER BY a.appointment_date LIMIT 1""",
            (pid,),
        )
        appt = cur.fetchone()

        # 4. Open clinical flags
        cur.execute(
            """SELECT flag_id, severity, source_type, reason, created_at
               FROM flags WHERE patient_id=%s AND status IN ('Open', 'Acknowledged')
               ORDER BY created_at DESC""",
            (pid,),
        )
        active_flags = cur.fetchall()

    return {
        "readings": readings,
        "devices": devices,
        "next_appointment": appt,
        "active_flags": active_flags,
    }


# ─── Clinician & Escalation Workflow (Milestone M4) ──────────────────────────

class AcknowledgeIn(BaseModel):
    note: str = ""


@app.get("/staff/triage")
def get_triage_board(user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse"))):
    """
    Returns the clinician triage board backed by MySQL view v_triage_board.
    Sorted by severity (Urgent_Review first), then flagged_at.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT patient_id, patient_name, flag_id, severity, source_type,
                      reason, status, flagged_at, minutes_open, risk_score, risk_level
               FROM v_triage_board
               ORDER BY FIELD(severity, 'Urgent_Review', 'Review_Soon', 'Info'), flagged_at"""
        )
        return cur.fetchall()


@app.post("/staff/flags/{flag_id}/acknowledge")
def acknowledge_flag(
    flag_id: int,
    body: AcknowledgeIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    Acknowledge Flag Endpoint:
    - Calls sp_acknowledge_flag inside an atomic MySQL transaction.
    - Locks row, marks flag Acknowledged, sets pending escalations Acknowledged,
      creates a follow-up task, and writes an audit_log entry.
    - Raises HTTP 409 if flag does not exist or was already acknowledged.
    """
    staff_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        try:
            cur.callproc("sp_acknowledge_flag", (flag_id, staff_id, body.note))
        except (pymysql.err.OperationalError, pymysql.err.InternalError) as e:
            err_msg = str(e)
            if (
                "45000" in err_msg
                or "already acknowledged" in err_msg.lower()
                or "not in open status" in err_msg.lower()
            ):
                raise HTTPException(status_code=409, detail="Flag not found or already acknowledged")
            raise

    return {"status": "acknowledged", "flag_id": flag_id, "staff_id": staff_id}


@app.get("/staff/follow-ups")
def get_pending_follow_ups(user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse"))):
    """Returns pending clinical tasks from v_pending_followups view."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT followup_id, patient_id, patient_name, priority, reason,
                      assigned_to, status, created_at,
                      ROUND(TIMESTAMPDIFF(MINUTE, created_at, NOW()) / 60.0, 1) AS hours_pending
               FROM v_pending_followups
               ORDER BY FIELD(priority, 'Urgent_Review', 'Review_Soon', 'Routine'), created_at ASC"""
        )
        return cur.fetchall()


@app.get("/staff/patients/{pid}/timeline")
def get_patient_timeline(pid: int, user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse"))):
    """
    Returns unified chronological clinical timeline for a patient from v_patient_timeline.
    Includes readings, symptoms, doses, and flags.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT patient_id, event_time, event_type, summary
               FROM v_patient_timeline
               WHERE patient_id = %s
               ORDER BY event_time DESC LIMIT 200""",
            (pid,),
        )
        return cur.fetchall()


# ─── Patient Chat & RAG (Milestone M5) ────────────────────────────────────────

@app.post("/patient/me/chat")
def chat_with_assistant(body: ChatIn, user: Dict[str, Any] = Depends(require_role("Patient", "Caregiver"))):
    """
    Patient Chat Endpoint with Grounded RAG:
    - Answers ONLY from clinician-approved discharge document excerpts.
    - Deterministic emergency phrases show guidance immediately and raise urgent flags.
    - Dose-change questions are refused deterministically and create staff follow-up tasks.
    - Links citations to document_chunks via chat_message_sources.
    - Ungrounded answers create a follow_up_task for clinical staff.
    """
    pid = get_effective_patient_id(user)

    with get_conn() as conn:
        with conn.cursor() as cur:
            # 1. Insert patient message
            cur.execute(
                """INSERT INTO chat_messages (patient_id, sender, message_text)
                   VALUES (%s, 'Patient', %s)""",
                (pid, body.message),
            )

        # 2. Compute grounded answer
        ans, is_grounded, citations = rag_answer(pid, body.message, body.language or "en", conn=conn)

        with conn.cursor() as cur:
            # 3. Insert AI message
            cur.execute(
                """INSERT INTO chat_messages (patient_id, sender, message_text, is_grounded)
                   VALUES (%s, 'AI_Nurse', %s, %s)""",
                (pid, ans, is_grounded),
            )
            ai_msg_id = cur.lastrowid

            # 4. Link citations
            if citations:
                for vid in citations:
                    cur.execute(
                        "SELECT chunk_id FROM document_chunks WHERE vector_id = %s LIMIT 1",
                        (vid,),
                    )
                    crow = cur.fetchone()
                    if crow:
                        cur.execute(
                            """INSERT IGNORE INTO chat_message_sources (message_id, chunk_id)
                               VALUES (%s, %s)""",
                            (ai_msg_id, crow["chunk_id"]),
                        )

            # 5. Create follow-up task if ungrounded or dose change
            if not is_grounded:
                cur.execute(
                    """SELECT attending_staff_id FROM discharge_records
                       WHERE patient_id = %s ORDER BY discharge_date DESC LIMIT 1""",
                    (pid,),
                )
                drow = cur.fetchone() or {}
                assigned_staff = drow.get("attending_staff_id") or 1
                reason = f"Unanswered patient question: {body.message}"[:255]
                cur.execute(
                    """INSERT INTO follow_up_tasks (patient_id, assigned_staff_id, priority, reason, status)
                       VALUES (%s, %s, 'Routine', %s, 'Pending')""",
                    (pid, assigned_staff, reason),
                )

            # 6. Audit log
            cur.execute(
                """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                   VALUES ('Patient', %s, 'CHAT_QUERY', 'chat_message', %s,
                           JSON_OBJECT('is_grounded', %s, 'citations_count', %s))""",
                (str(user["account_id"]), ai_msg_id, is_grounded, len(citations)),
            )

    return {
        "response": ans,
        "is_grounded": is_grounded,
        "citations": citations,
    }


@app.get("/patient/me/chat/history")
def get_chat_history(user: Dict[str, Any] = Depends(require_role("Patient", "Caregiver"))):
    """Returns patient chat history with groundness flags."""
    pid = get_effective_patient_id(user)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT message_id, patient_id, sender, message_text, is_grounded, created_at
               FROM chat_messages
               WHERE patient_id = %s
               ORDER BY created_at ASC LIMIT 100""",
            (pid,),
        )
        return cur.fetchall()


# ─── Daily AI Summaries & Clinician Review (Milestone M5) ────────────────────

@app.post("/staff/patients/{pid}/summaries/generate")
def generate_patient_summary(
    pid: int,
    summary_date: Optional[str] = None,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    Generate factual daily AI draft summary using sp_daily_report.
    Strict rule: 'AI draft, not reviewed'. No advice, no interpretation.
    """
    target_date = summary_date or datetime.now(IST).strftime("%Y-%m-%d")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.callproc("sp_daily_report", (pid, target_date))
            pinfo_rows = cur.fetchall()
            pinfo = pinfo_rows[0] if pinfo_rows else {"full_name": f"Patient {pid}", "patient_id": pid}

            cur.nextset()
            meds = cur.fetchall()
            cur.nextset()
            vitals = cur.fetchall()
            cur.nextset()
            symptoms = cur.fetchall()
            cur.nextset()
            flags = cur.fetchall()

        # Build fact sheet
        taken_count = sum(1 for m in meds if m.get("status") == "Taken")
        fact_sheet = (
            f"Patient: {pinfo.get('full_name')} (ID: {pid}), Date: {target_date}\n"
            f"Medications: {len(meds)} doses scheduled, {taken_count} recorded as taken.\n"
            f"Vitals: {[v['measurement_type'] + ': avg ' + str(v['avg_value']) for v in vitals]}\n"
            f"Symptoms: {[s['symptom_text'] for s in symptoms]}\n"
            f"Flags: {[f['severity'] + ': ' + f['reason'] for f in flags]}\n"
        )

        prompt = (
            "You are a factual clinical summarizer. Rewrite the provided facts into a concise "
            "2-3 sentence factual clinical note for staff. DO NOT add advice. DO NOT interpret. "
            "DO NOT recommend medication changes or diagnoses. State only the recorded facts."
        )
        summary_text = generate(prompt, fact_sheet)

        period_start = f"{target_date} 00:00:00"
        period_end = f"{target_date} 23:59:59"
        model_name = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")

        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ai_summaries
                   (patient_id, period_start, period_end, summary_text, model_name, reviewed_by_staff_id, reviewed_at)
                   VALUES (%s, %s, %s, %s, %s, NULL, NULL)""",
                (pid, period_start, period_end, summary_text, model_name),
            )
            summary_id = cur.lastrowid

            cur.execute(
                """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                   VALUES ('Staff', %s, 'GENERATE_AI_SUMMARY', 'ai_summary', %s,
                           JSON_OBJECT('patient_id', %s, 'date', %s))""",
                (str(user["staff_id"]), summary_id, pid, target_date),
            )

    return {
        "summary_id": summary_id,
        "patient_id": pid,
        "summary_date": target_date,
        "summary_text": summary_text,
        "status": "AI draft, not reviewed",
        "model_name": model_name,
    }


@app.get("/staff/summaries/pending")
def get_pending_summaries(user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse"))):
    """Returns AI draft summaries waiting for clinician review (Query Q15)."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT s.summary_id, s.patient_id, p.full_name AS patient_name,
                      s.period_start, s.period_end, s.summary_text, s.model_name,
                      s.generated_at, 'AI draft, not reviewed' AS status
               FROM ai_summaries s
               JOIN patients p ON p.patient_id = s.patient_id
               WHERE s.reviewed_by_staff_id IS NULL
               ORDER BY s.generated_at DESC"""
        )
        return cur.fetchall()


@app.post("/staff/summaries/{summary_id}/review")
def review_summary(
    summary_id: int,
    body: ReviewSummaryIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Clinician reviews and approves/rejects an AI draft summary."""
    staff_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT summary_id FROM ai_summaries WHERE summary_id = %s", (summary_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Summary not found")

        cur.execute(
            """UPDATE ai_summaries
               SET reviewed_by_staff_id = %s, reviewed_at = NOW()
               WHERE summary_id = %s""",
            (staff_id, summary_id),
        )

        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Staff', %s, 'REVIEW_AI_SUMMARY', 'ai_summary', %s,
                       JSON_OBJECT('action', %s, 'staff_id', %s, 'notes', %s))""",
            (str(staff_id), summary_id, body.action, staff_id, body.notes),
        )

    return {
        "status": f"{body.action}ed",
        "summary_id": summary_id,
        "reviewed_by_staff_id": staff_id,
    }