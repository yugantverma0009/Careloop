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
from .clinical_summaries import (
    build_deterministic_fact_sheet,
    produce_clinical_summary,
    run_summary_guard,
    generate_fallback_summary,
)
from .governance_interop import (
    PATHWAY_TEMPLATES,
    compute_lace_score,
    compute_operational_insights,
    build_fhir_r4_bundle,
)
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


from .rag_config import USE_UPGRADED_RAG
from .rag_pipeline import answer_patient_query


class ChatIn(BaseModel):
    message: Optional[str] = Field(None, max_length=1000)
    question: Optional[str] = Field(None, max_length=1000)
    conversation_id: Optional[str] = None
    language: Optional[str] = Field(default="en", pattern="^(en|hi)$")


class FeedbackIn(BaseModel):
    rating: int = Field(..., ge=-1, le=1)
    comment: Optional[str] = Field(default=None, max_length=255)


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

# ─── Clinician & Escalation Workflow (Milestone M4 & Upgrade Phase 1) ──────────

class AcknowledgeIn(BaseModel):
    note: str = ""
    create_task: bool = False

class ResolveIn(BaseModel):
    resolution_code: str
    resolution_note: str = ""

class DismissIn(BaseModel):
    resolution_code: str = "False_Alarm"
    resolution_note: str = ""

class AssignIn(BaseModel):
    target_staff_id: int
    note: str = ""

class EscalateIn(BaseModel):
    note: str = ""


@app.get("/staff/members")
def get_staff_members(user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse"))):
    """Returns list of active care team staff members."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT staff_id, full_name, staff_role, email, phone, specialization
               FROM care_staff ORDER BY staff_role DESC, full_name ASC"""
        )
        return cur.fetchall()


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


@app.get("/staff/worklist")
def get_staff_worklist(
    scope: str = "mine",       # 'mine', 'team', 'unassigned', 'all' (D-12 defaults to 'mine')
    status_filter: str = "open", # 'open', 'seen', 'closed', 'all'
    severity_filter: str = "all", # 'immediate', 'urgent', 'review_soon', 'routine', 'all'
    search: str = "",
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-02 / D-04 / D-12: Grouped Clinician Worklist.
    Returns collapsed patient cards from v_worklist_by_patient with SLA tiers,
    explainable attention score breakdown, nested patient flags, and assignment awareness.
    Defaults to scope='mine' (assigned / attended patients).
    """
    current_staff_id = user["staff_id"]
    is_doctor = user.get("account_role") == "Doctor"

    with get_conn() as conn, conn.cursor() as cur:
        # 1. Fetch assigned patient IDs for current staff (D-12)
        cur.execute(
            """SELECT patient_id FROM care_assignments
               WHERE staff_id = %s AND (ends_at IS NULL OR ends_at > NOW())""",
            (current_staff_id,),
        )
        assigned_pids = {r["patient_id"] for r in (cur.fetchall() or [])}

        if is_doctor:
            cur.execute(
                "SELECT patient_id FROM discharge_records WHERE attending_staff_id = %s",
                (current_staff_id,),
            )
            for r in (cur.fetchall() or []):
                assigned_pids.add(r["patient_id"])

        # 2. Fetch grouped patient rows
        cur.execute(
            """SELECT w.patient_id, w.patient_code, w.full_name, w.age_years,
                      w.open_flag_count, w.distinct_reasons, w.top_severity_rank,
                      w.has_emergency, w.not_yet_seen, w.first_flag_at, w.latest_flag_at,
                      w.owner_staff_id, s.full_name AS owner_name,
                      d.condition_summary, doc.full_name AS attending_doctor
               FROM v_worklist_by_patient w
               LEFT JOIN care_staff s ON s.staff_id = w.owner_staff_id
               LEFT JOIN discharge_records d ON d.patient_id = w.patient_id
               LEFT JOIN care_staff doc ON doc.staff_id = d.attending_staff_id
               ORDER BY w.has_emergency DESC, w.top_severity_rank DESC, w.first_flag_at ASC"""
        )
        patient_rows = cur.fetchall()

        # 3. Fetch all active flags for nested display
        cur.execute(
            """SELECT f.flag_id, f.patient_id, f.source_type, f.reason, f.severity, f.status,
                      f.created_at, f.acknowledged_at, f.acknowledged_by_staff_id,
                      f.owner_staff_id, f.resolved_at, f.resolution_code, f.resolution_note,
                      s.full_name AS owner_name, ack_s.full_name AS acknowledged_by_name,
                      ROUND(TIMESTAMPDIFF(MINUTE, f.created_at, NOW()) / 60.0, 1) AS hours_open
               FROM flags f
               LEFT JOIN care_staff s ON s.staff_id = f.owner_staff_id
               LEFT JOIN care_staff ack_s ON ack_s.staff_id = f.acknowledged_by_staff_id
               ORDER BY FIELD(f.severity, 'Urgent_Review', 'Review_Soon', 'Info'), f.created_at ASC"""
        )
        all_flags = cur.fetchall()

    # Map flags by patient_id
    flags_by_patient: Dict[int, List[Dict[str, Any]]] = {}
    for fl in all_flags:
        pid = fl["patient_id"]
        if pid not in flags_by_patient:
            flags_by_patient[pid] = []
        flags_by_patient[pid].append(fl)

    now = datetime.now()
    patients = []
    
    immediate_total = 0
    urgent_total = 0
    review_soon_total = 0
    not_yet_seen_total = 0
    overdue_total = 0

    for r in patient_rows:
        pid = r["patient_id"]
        has_emerg = bool(r.get("has_emergency"))
        top_rank = r.get("top_severity_rank") or 1
        first_at = r.get("first_flag_at")

        # SLA Tier Calculation (D-02)
        if has_emerg or top_rank >= 4:
            tier = "Immediate"
            sla_target = "< 15 min"
            sla_limit_min = 15
            immediate_total += 1
        elif top_rank == 3:
            tier = "Urgent"
            sla_target = "< 2 h"
            sla_limit_min = 120
            urgent_total += 1
        elif top_rank == 2:
            tier = "Review_Soon"
            sla_target = "< 24 h"
            sla_limit_min = 1440
            review_soon_total += 1
        else:
            tier = "Routine"
            sla_target = "Routine"
            sla_limit_min = 4320

        # Overdue Check
        is_overdue = False
        overdue_display = None
        if first_at:
            delta_min = max(0, int((now - first_at).total_seconds() / 60))
            if tier == "Immediate" and delta_min > 15:
                is_overdue = True
                overdue_display = f"Overdue by {delta_min - 15}m"
            elif tier == "Urgent" and delta_min > 120:
                is_overdue = True
                hrs = round((delta_min - 120) / 60.0, 1)
                overdue_display = f"Overdue by {hrs}h"
            elif tier == "Review_Soon" and delta_min > 1440:
                is_overdue = True
                hrs = round((delta_min - 1440) / 60.0, 1)
                overdue_display = f"Overdue by {hrs}h"

        if is_overdue:
            overdue_total += 1

        not_seen = int(r.get("not_yet_seen") or 0)
        not_yet_seen_total += not_seen

        # Explainable Attention Score Calculation (D-02)
        factors = []
        score = 0
        if tier == "Immediate":
            score += 40
            factors.append({"label": "Immediate Emergency severity", "points": 40})
        elif tier == "Urgent":
            score += 30
            factors.append({"label": "Urgent Review severity", "points": 30})
        elif tier == "Review_Soon":
            score += 15
            factors.append({"label": "Review Soon severity", "points": 15})
        else:
            score += 5
            factors.append({"label": "Routine severity", "points": 5})

        dist_reasons = int(r.get("distinct_reasons") or 1)
        reason_pts = min(dist_reasons * 10, 30)
        score += reason_pts
        factors.append({"label": f"{dist_reasons} distinct flag reason{'s' if dist_reasons > 1 else ''}", "points": reason_pts})

        if has_emerg:
            score += 10
            factors.append({"label": "Active Emergency keyword trigger", "points": 10})

        if is_overdue:
            score += 20
            factors.append({"label": "SLA target exceeded", "points": 20})

        score = min(100, score)

        # Patient flags & deduplication check
        p_flags = flags_by_patient.get(pid, [])
        # Group duplicates for display (D-04)
        grouped_flags = []
        seen_flag_keys = {}
        for fl in p_flags:
            key = (fl["source_type"], fl["reason"])
            if key not in seen_flag_keys:
                fl_copy = dict(fl)
                fl_copy["occurrence_count"] = 1
                fl_copy["first_created_at"] = fl["created_at"]
                fl_copy["last_created_at"] = fl["created_at"]
                seen_flag_keys[key] = len(grouped_flags)
                grouped_flags.append(fl_copy)
            else:
                idx = seen_flag_keys[key]
                grouped_flags[idx]["occurrence_count"] += 1
                grouped_flags[idx]["last_created_at"] = fl["created_at"]

        patient_card = {
            "patient_id": pid,
            "patient_code": r["patient_code"],
            "full_name": r["full_name"],
            "age_years": r["age_years"],
            "condition": r["condition_summary"] or "Post-Discharge Recovery",
            "attending_doctor": r["attending_doctor"] or "Attending Physician",
            "open_flag_count": int(r["open_flag_count"] or 0),
            "distinct_reasons": dist_reasons,
            "has_emergency": has_emerg,
            "not_yet_seen": not_seen,
            "first_flag_at": r["first_flag_at"],
            "latest_flag_at": r["latest_flag_at"],
            "owner_staff_id": r["owner_staff_id"],
            "owner_name": r["owner_name"],
            "is_mine": (r["owner_staff_id"] == current_staff_id or pid in assigned_pids),
            "outside_assignment": not (r["owner_staff_id"] == current_staff_id or pid in assigned_pids),
            "tier": tier,
            "sla_target": sla_target,
            "is_overdue": is_overdue,
            "overdue_display": overdue_display,
            "attention_score": score,
            "attention_factors": factors,
            "flags": grouped_flags,
            "raw_flags": p_flags,
        }

        # Filtering logic
        # 1. Scope (D-12)
        if scope == "mine" and not patient_card["is_mine"]:
            continue
        elif scope == "unassigned" and patient_card["is_mine"]:
            continue

        # 2. Status
        if status_filter == "open" and not_seen == 0 and int(r["open_flag_count"] or 0) == 0:
            continue
        elif status_filter == "seen" and not_seen > 0:
            continue

        # 3. Severity
        if severity_filter == "immediate" and tier != "Immediate":
            continue
        elif severity_filter == "urgent" and tier != "Urgent":
            continue
        elif severity_filter == "review_soon" and tier != "Review_Soon":
            continue
        elif severity_filter == "routine" and tier != "Routine":
            continue

        # 4. Search query
        if search:
            q = search.lower().strip()
            match = (
                q in r["full_name"].lower()
                or q in (r["patient_code"] or "").lower()
                or q in (r["condition_summary"] or "").lower()
                or any(q in fl["reason"].lower() for fl in p_flags)
            )
            if not match:
                continue

        patients.append(patient_card)

    return {
        "summary": {
            "total_patients": len(patients),
            "total_open_flags": sum(p["open_flag_count"] for p in patients),
            "immediate_count": immediate_total,
            "urgent_count": urgent_total,
            "review_soon_count": review_soon_total,
            "not_yet_seen_count": not_yet_seen_total,
            "overdue_count": overdue_total,
        },
        "patients": patients,
    }


@app.get("/staff/flags/{flag_id}")
def get_flag_detail(
    flag_id: int,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-03 Flag Detail Drawer endpoint.
    Returns:
    - Why: reason text, severity, tier, created time, age.
    - Evidence: vital reading, symptom report, dose logs, or emergency keywords with data quality.
    - Rule: rule type, threshold, approver name, approved time.
    - Escalation ladder: 4-step sequence with status and countdown.
    - History: flag_events audit trail.
    """
    with get_conn() as conn, conn.cursor() as cur:
        # Flag and Patient Identity
        cur.execute(
            """SELECT f.flag_id, f.patient_id, f.rule_id, f.source_type, f.source_ref_id,
                      f.reason, f.severity, f.status, f.created_at,
                      f.acknowledged_by_staff_id, f.acknowledged_at,
                      f.owner_staff_id, f.resolved_at, f.resolved_by_staff_id,
                      f.resolution_code, f.resolution_note,
                      p.patient_code, p.full_name AS patient_name,
                      TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age_years,
                      d.condition_summary,
                      s_ack.full_name AS acknowledged_by_name,
                      s_own.full_name AS owner_name,
                      s_res.full_name AS resolved_by_name
               FROM flags f
               JOIN patients p ON p.patient_id = f.patient_id
               LEFT JOIN discharge_records d ON d.patient_id = p.patient_id
               LEFT JOIN care_staff s_ack ON s_ack.staff_id = f.acknowledged_by_staff_id
               LEFT JOIN care_staff s_own ON s_own.staff_id = f.owner_staff_id
               LEFT JOIN care_staff s_res ON s_res.staff_id = f.resolved_by_staff_id
               WHERE f.flag_id = %s""",
            (flag_id,),
        )
        flag = cur.fetchone()
        if not flag:
            raise HTTPException(status_code=404, detail="Flag not found")

        # Evidence detail
        evidence = {"source_type": flag["source_type"], "details": None, "data_quality": "Good"}
        if flag["source_type"] == "Sensor" and flag["source_ref_id"]:
            cur.execute(
                """SELECT reading_id, measurement_type AS metric, measurement_value AS value,
                          unit, measured_at AS recorded_at, quality_status AS data_quality, device_id
                   FROM sensor_readings WHERE reading_id = %s""",
                (flag["source_ref_id"],),
            )
            v = cur.fetchone()
            if v:
                evidence["details"] = v
                evidence["data_quality"] = v.get("data_quality", "Good")
        elif flag["source_type"] == "Symptom" and flag["source_ref_id"]:
            cur.execute(
                """SELECT symptom_report_id AS report_id, pain_level AS pain_score,
                          symptom_text, reported_at AS recorded_at, input_method, language
                   FROM symptom_reports WHERE symptom_report_id = %s""",
                (flag["source_ref_id"],),
            )
            s = cur.fetchone()
            if s:
                evidence["details"] = s
                evidence["data_quality"] = "Patient-reported"
        elif flag["source_type"] == "Medication" and flag["source_ref_id"]:
            cur.execute(
                """SELECT l.medication_log_id, l.scheduled_for, l.recorded_at, l.status,
                          l.recorded_by, l.patient_note, m.medicine_name
                   FROM medication_logs l
                   JOIN prescriptions p ON p.prescription_id = l.prescription_id
                   JOIN medicines m ON m.medicine_id = p.medicine_id
                   WHERE l.medication_log_id = %s""",
                (flag["source_ref_id"],),
            )
            m = cur.fetchone()
            if m:
                evidence["details"] = m
                evidence["data_quality"] = "Self-reported"
        elif flag["source_type"] == "Emergency":
            evidence["details"] = {
                "reason": flag["reason"],
                "notice": "Triggered by critical safety keyword in patient report",
            }
            evidence["data_quality"] = "High Priority"

        # Rule detail
        rule = None
        if flag["rule_id"]:
            cur.execute(
                """SELECT r.rule_id, r.rule_type, r.measurement_type, r.threshold_value,
                          r.window_hours, r.severity, r.approved_at,
                          s.full_name AS approved_by_name
                   FROM alert_rules r
                   LEFT JOIN care_staff s ON s.staff_id = r.approved_by_staff_id
                   WHERE r.rule_id = %s""",
                (flag["rule_id"],),
            )
            rule = cur.fetchone()
        if not rule:
            rule = {
                "rule_type": "Safety_Protocol",
                "rule_name": "Emergency Keyword / Patient-Reported Threshold",
                "threshold_value": "Immediate Clinical Review",
                "approved_by_name": "Clinical Safety Protocol",
                "approved_at": None,
            }

        # Escalation ladder (D-10)
        cur.execute(
            """SELECT escalation_id, step_no, step_type, channel, sent_at,
                      delivery_status, responded_at, notes
               FROM escalations
               WHERE flag_id = %s
               ORDER BY step_no ASC""",
            (flag_id,),
        )
        escalations = cur.fetchall()

        if not escalations:
            # Generate default 4-step ladder
            flag_status = flag["status"]
            escalations = [
                {
                    "step_no": 1,
                    "step_type": "Patient_Prompt",
                    "channel": "App",
                    "delivery_status": "Acknowledged" if flag_status != "Open" else "Sent",
                    "sent_at": flag["created_at"],
                    "responded_at": flag["acknowledged_at"],
                    "notes": "Patient prompted for clarification via app",
                },
                {
                    "step_no": 2,
                    "step_type": "Caregiver_SMS",
                    "channel": "SMS",
                    "delivery_status": "Acknowledged" if flag_status != "Open" else "Sent",
                    "sent_at": flag["created_at"],
                    "responded_at": flag["acknowledged_at"],
                    "notes": "Caregiver notified (consent verified)",
                },
                {
                    "step_no": 3,
                    "step_type": "Nurse_Alert",
                    "channel": "Dashboard",
                    "delivery_status": "Acknowledged" if flag_status != "Open" else "Sent",
                    "sent_at": flag["created_at"],
                    "responded_at": flag["acknowledged_at"],
                    "notes": "Escalated to triage nursing queue",
                },
                {
                    "step_no": 4,
                    "step_type": "Doctor_Alert",
                    "channel": "Dashboard",
                    "delivery_status": "Acknowledged" if flag_status != "Open" else "Queued",
                    "sent_at": flag["created_at"],
                    "responded_at": flag["acknowledged_at"],
                    "notes": "Physician notification standby",
                },
            ]

        # Audit History from flag_events
        cur.execute(
            """SELECT fe.flag_event_id, fe.event_type, fe.note, fe.created_at,
                      cs.full_name AS staff_name
               FROM flag_events fe
               LEFT JOIN care_staff cs ON cs.staff_id = fe.staff_id
               WHERE fe.flag_id = %s
               ORDER BY fe.created_at ASC""",
            (flag_id,),
        )
        history = cur.fetchall()

        # Tier calculation
        sev = flag["severity"]
        src = flag["source_type"]
        if src == "Emergency" or sev == "Urgent_Review":
            tier = "Immediate" if src == "Emergency" else "Urgent"
        elif sev == "Review_Soon":
            tier = "Review_Soon"
        else:
            tier = "Routine"

    return {
        "flag_id": flag["flag_id"],
        "patient": {
            "patient_id": flag["patient_id"],
            "patient_code": flag["patient_code"],
            "full_name": flag["patient_name"],
            "age_years": flag["age_years"],
            "condition": flag["condition_summary"] or "Post-Discharge Recovery",
        },
        "reason": flag["reason"],
        "severity": flag["severity"],
        "tier": tier,
        "source_type": flag["source_type"],
        "status": flag["status"],
        "created_at": flag["created_at"],
        "owner_staff_id": flag["owner_staff_id"],
        "owner_name": flag["owner_name"],
        "acknowledged_at": flag["acknowledged_at"],
        "acknowledged_by_name": flag["acknowledged_by_name"],
        "resolved_at": flag["resolved_at"],
        "resolved_by_name": flag["resolved_by_name"],
        "resolution_code": flag["resolution_code"],
        "resolution_note": flag["resolution_note"],
        "evidence": evidence,
        "rule": rule,
        "escalation_ladder": escalations,
        "history": history,
    }


@app.post("/staff/flags/{flag_id}/acknowledge")
def acknowledge_flag(
    flag_id: int,
    body: AcknowledgeIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    Acknowledge Flag Endpoint (D-03):
    - Calls sp_acknowledge_flag(flag_id, staff_id, note, create_task).
    - Locks row, marks flag Acknowledged, sets pending escalations Acknowledged,
      optionally creates follow-up task, and writes flag_events & audit_log.
    - Double staff acting at once: first wins, second gets HTTP 409 with exact clinician info.
    """
    staff_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        try:
            cur.callproc("sp_acknowledge_flag", (flag_id, staff_id, body.note, body.create_task))
        except (pymysql.err.OperationalError, pymysql.err.InternalError) as e:
            err_msg = str(e)
            if (
                "45000" in err_msg
                or "already acknowledged" in err_msg.lower()
                or "not in open status" in err_msg.lower()
            ):
                cur.execute(
                    """SELECT f.status, cs.full_name, f.acknowledged_at
                       FROM flags f
                       LEFT JOIN care_staff cs ON cs.staff_id = f.acknowledged_by_staff_id
                       WHERE f.flag_id = %s""",
                    (flag_id,),
                )
                row = cur.fetchone()
                if row and row.get("full_name"):
                    ack_time = row["acknowledged_at"].strftime("%H:%M") if row.get("acknowledged_at") else "earlier"
                    detail = f"Already acknowledged by {row['full_name']} at {ack_time}"
                else:
                    detail = "Flag not found or already acknowledged"
                raise HTTPException(status_code=409, detail=detail)
            raise

    return {"status": "acknowledged", "flag_id": flag_id, "staff_id": staff_id}


@app.post("/staff/flags/{flag_id}/resolve")
def resolve_flag(
    flag_id: int,
    body: ResolveIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    Resolve Flag Endpoint (D-03):
    - Calls sp_resolve_flag with p_dismiss=FALSE.
    - Requires resolution code.
    - Urgent and Immediate flags enforce note length >= 5 characters.
    """
    staff_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        try:
            cur.callproc("sp_resolve_flag", (flag_id, staff_id, body.resolution_code, body.resolution_note, False))
        except (pymysql.err.OperationalError, pymysql.err.InternalError) as e:
            err_msg = str(e)
            if "at least 5 characters" in err_msg:
                raise HTTPException(
                    status_code=400,
                    detail="A clinical note of at least 5 characters is required to resolve an urgent/immediate flag.",
                )
            if "already closed" in err_msg:
                raise HTTPException(status_code=409, detail="Flag is already closed")
            if "not found" in err_msg:
                raise HTTPException(status_code=404, detail="Flag not found")
            raise

    return {"status": "resolved", "flag_id": flag_id, "staff_id": staff_id}


@app.post("/staff/flags/{flag_id}/dismiss")
def dismiss_flag(
    flag_id: int,
    body: DismissIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    Dismiss Flag as False Alarm / Duplicate Endpoint (D-03):
    - Calls sp_resolve_flag with p_dismiss=TRUE.
    - Feeds false alarm quality tracking.
    """
    staff_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        try:
            cur.callproc("sp_resolve_flag", (flag_id, staff_id, body.resolution_code, body.resolution_note, True))
        except (pymysql.err.OperationalError, pymysql.err.InternalError) as e:
            err_msg = str(e)
            if "at least 5 characters" in err_msg:
                raise HTTPException(status_code=400, detail="A clinical note of at least 5 characters is required.")
            if "already closed" in err_msg:
                raise HTTPException(status_code=409, detail="Flag is already closed")
            if "not found" in err_msg:
                raise HTTPException(status_code=404, detail="Flag not found")
            raise

    return {"status": "dismissed", "flag_id": flag_id, "staff_id": staff_id}


@app.post("/staff/flags/{flag_id}/assign")
def assign_flag(
    flag_id: int,
    body: AssignIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    Assign Flag Endpoint (D-03):
    - Calls sp_assign_flag to set owner_staff_id, record flag_events and audit_log.
    """
    staff_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        try:
            cur.callproc("sp_assign_flag", (flag_id, staff_id, body.target_staff_id, body.note))
        except (pymysql.err.OperationalError, pymysql.err.InternalError) as e:
            err_msg = str(e)
            if "not found" in err_msg:
                raise HTTPException(status_code=404, detail="Flag not found")
            raise

    return {"status": "assigned", "flag_id": flag_id, "target_staff_id": body.target_staff_id}


@app.post("/staff/flags/{flag_id}/escalate")
def escalate_flag_now(
    flag_id: int,
    body: EscalateIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    Escalate Now Endpoint (D-10):
    - Writes escalation record, flag_events entry, and audit_log.
    """
    staff_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT flag_id, status FROM flags WHERE flag_id = %s", (flag_id,))
        fl = cur.fetchone()
        if not fl:
            raise HTTPException(status_code=404, detail="Flag not found")

        cur.execute(
            """INSERT INTO escalations (flag_id, step_no, step_type, channel, delivery_status, notes)
               VALUES (%s, 4, 'Doctor_Alert', 'Dashboard', 'Sent', %s)""",
            (flag_id, f"Manual escalation by Staff #{staff_id}: {body.note}".strip(": ")),
        )
        cur.execute(
            """INSERT INTO flag_events (flag_id, event_type, staff_id, note)
               VALUES (%s, 'Escalated', %s, %s)""",
            (flag_id, staff_id, f"Manual immediate escalation: {body.note}".strip(": ")),
        )
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Staff', %s, 'ESCALATE_FLAG', 'flag', %s, JSON_OBJECT('note', %s))""",
            (str(staff_id), flag_id, body.note),
        )
        conn.commit()

    return {"status": "escalated", "flag_id": flag_id}


# ─── Follow-up Tasks Queue (Feature D-07) ────────────────────────────────────

class TaskAssignIn(BaseModel):
    target_staff_id: int
    note: Optional[str] = ""


class TaskCompleteIn(BaseModel):
    outcome_code: str
    outcome_notes: Optional[str] = ""


class TaskSnoozeIn(BaseModel):
    hours: int
    reason: str


VALID_OUTCOME_CODES = {
    "Reached_And_Advised",
    "Appointment_Set",
    "No_Answer",
    "Escalated_To_Doctor",
    "No_Action_Needed",
}


def _format_due_label(diff_minutes: Optional[float], is_overdue: bool) -> str:
    if diff_minutes is None:
        return "No due date"
    if is_overdue:
        # diff_minutes is positive (minutes past due_at)
        mins = abs(int(diff_minutes))
        if mins < 60:
            return f"Overdue by {mins}m"
        hours = mins // 60
        days = hours // 24
        rem_h = hours % 24
        if days > 0:
            return f"Overdue by {days}d {rem_h}h" if rem_h > 0 else f"Overdue by {days}d"
        return f"Overdue by {hours}h"
    else:
        # due in future: diff_minutes is negative or <= 0
        mins = abs(int(diff_minutes))
        if mins < 60:
            return f"Due in {max(1, mins)}m"
        hours = mins // 60
        days = hours // 24
        rem_h = hours % 24
        if days > 0:
            return f"Due in {days}d {rem_h}h" if rem_h > 0 else f"Due in {days}d"
        return f"Due in {hours}h"


@app.get("/staff/tasks")
def get_staff_tasks(
    scope: str = "mine",          # 'mine', 'team', 'unassigned', 'all'
    status: str = "pending",      # 'pending', 'completed', 'all'
    overdue: Optional[bool] = None,
    priority: str = "all",        # 'all', 'Urgent_Review', 'Review_Soon', 'Routine'
    search: str = "",
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-07: Real task work queue with due dates, overdue badges, priority labels,
    and assigned ownership.
    """
    staff_id = user["staff_id"]
    now_dt = datetime.now()

    query = """
        SELECT t.followup_id,
               t.patient_id,
               p.patient_code,
               p.full_name AS patient_name,
               TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age_years,
               t.flag_id,
               fl.severity AS flag_severity,
               t.assigned_staff_id,
               u.full_name AS assigned_staff_name,
               t.reason,
               t.priority,
               CASE 
                   WHEN t.priority = 'Urgent_Review' THEN 'Urgent'
                   WHEN t.priority = 'Review_Soon' THEN 'Review soon'
                   ELSE 'Routine'
               END AS priority_label,
               t.status,
               t.created_at,
               t.due_at,
               t.outcome_code,
               t.outcome_notes,
               t.completed_at
        FROM follow_up_tasks t
        JOIN patients p ON p.patient_id = t.patient_id
        LEFT JOIN care_staff u ON u.staff_id = t.assigned_staff_id
        LEFT JOIN flags fl ON fl.flag_id = t.flag_id
        WHERE 1=1
    """
    params: List[Any] = []

    # Scope filter
    if scope == "mine":
        query += " AND t.assigned_staff_id = %s"
        params.append(staff_id)
    elif scope == "unassigned":
        query += " AND (t.assigned_staff_id IS NULL OR t.assigned_staff_id = 0)"
    elif scope == "team":
        query += " AND t.assigned_staff_id IS NOT NULL AND t.assigned_staff_id != 0"
    # 'all' has no assigned filter

    # Status filter
    if status == "pending":
        query += " AND t.status != 'Resolved'"
    elif status == "completed":
        query += " AND t.status = 'Resolved'"

    # Overdue filter
    if overdue is True:
        query += " AND t.status != 'Resolved' AND t.due_at IS NOT NULL AND t.due_at < NOW()"
    elif overdue is False:
        query += " AND (t.due_at >= NOW() OR t.due_at IS NULL OR t.status = 'Resolved')"

    # Priority filter
    if priority != "all":
        query += " AND t.priority = %s"
        params.append(priority)

    # Search filter
    if search.strip():
        term = f"%{search.strip()}%"
        query += " AND (p.full_name LIKE %s OR p.patient_code LIKE %s OR t.reason LIKE %s)"
        params.extend([term, term, term])

    # Sorting
    if status == "completed":
        query += " ORDER BY t.completed_at DESC, t.followup_id DESC"
    else:
        # Overdue first, then Urgent priority, then earliest due_at
        query += """ ORDER BY 
            (t.due_at IS NOT NULL AND t.due_at < NOW()) DESC,
            FIELD(t.priority, 'Urgent_Review', 'Review_Soon', 'Routine'),
            t.due_at ASC,
            t.created_at ASC"""

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(query, tuple(params))
        rows = cur.fetchall() or []

    result = []
    for r in rows:
        due_at = r.get("due_at")
        is_overdue = False
        hours_overdue = 0.0
        diff_mins = None

        if due_at:
            # calculate difference
            diff_seconds = (now_dt - due_at).total_seconds()
            diff_mins = diff_seconds / 60.0
            if r.get("status") != "Resolved" and diff_seconds > 0:
                is_overdue = True
                hours_overdue = round(diff_seconds / 3600.0, 1)

        r_dict = dict(r)
        r_dict["is_overdue"] = is_overdue
        r_dict["hours_overdue"] = hours_overdue
        r_dict["overdue_label"] = _format_due_label(diff_mins, is_overdue)
        result.append(r_dict)

    return result


@app.get("/staff/follow-ups")
def get_pending_follow_ups(user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse"))):
    """Legacy backward-compatible endpoint for pending follow-ups."""
    return get_staff_tasks(scope="all", status="pending", user=user)


@app.post("/staff/tasks/{task_id}/claim")
def claim_task(
    task_id: int,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """D-07: Staff claims unassigned or re-assigned follow-up task."""
    staff_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        try:
            cur.callproc("sp_claim_task", (task_id, staff_id))
            conn.commit()
        except pymysql.MySQLError as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))
    return {"status": "claimed", "task_id": task_id, "assigned_staff_id": staff_id}


@app.post("/staff/tasks/{task_id}/assign")
def assign_task(
    task_id: int,
    body: TaskAssignIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """D-07: Assigns task to a specific team member with optional note."""
    staff_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        try:
            cur.callproc("sp_assign_task", (task_id, staff_id, body.target_staff_id, body.note or ""))
            conn.commit()
        except pymysql.MySQLError as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))
    return {"status": "assigned", "task_id": task_id, "assigned_staff_id": body.target_staff_id}


@app.post("/staff/tasks/{task_id}/complete")
def complete_task(
    task_id: int,
    body: TaskCompleteIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """D-07: Completes task with required outcome code and notes."""
    if body.outcome_code not in VALID_OUTCOME_CODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid outcome_code. Allowed: {sorted(list(VALID_OUTCOME_CODES))}",
        )
    staff_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        try:
            cur.callproc("sp_complete_task", (task_id, staff_id, body.outcome_code, body.outcome_notes or ""))
            conn.commit()
        except pymysql.MySQLError as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))
    return {"status": "completed", "task_id": task_id, "outcome_code": body.outcome_code}


@app.post("/staff/tasks/{task_id}/snooze")
def snooze_task(
    task_id: int,
    body: TaskSnoozeIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """D-07: Snoozes task by X hours with required clinical reason."""
    if body.hours <= 0:
        raise HTTPException(status_code=400, detail="Snooze duration must be greater than 0 hours")
    if not body.reason or len(body.reason.strip()) < 3:
        raise HTTPException(status_code=400, detail="A reason of at least 3 characters is required to snooze")

    staff_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        try:
            cur.callproc("sp_snooze_task", (task_id, staff_id, body.hours, body.reason.strip()))
            conn.commit()
        except pymysql.MySQLError as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))
    return {"status": "snoozed", "task_id": task_id, "hours": body.hours}



# ─── Patient Directory & Overview (Milestone D-05, D-06, D-12) ────────────────

class BreakGlassIn(BaseModel):
    reason: str


@app.get("/staff/patients")
def get_patient_directory(
    filter: str = "all",      # 'all', 'mine', 'has_flags', 'silent_device'
    search: str = "",
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-05: Patient Directory table endpoint.
    Returns: Name, age, code (CL-00001), condition, discharge date and day number,
    attending doctor, open flag count, device status, last check-in, adherence this week.
    """
    staff_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT p.patient_id, p.patient_code, p.full_name,
                      TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age_years,
                      p.date_of_birth,
                      d.discharge_date,
                      DATEDIFF(CURDATE(), d.discharge_date) + 1 AS day_number,
                      d.condition_summary,
                      doc.full_name AS attending_doctor,
                      nurse.full_name AS assigned_nurse,
                      (SELECT COUNT(*) FROM flags f WHERE f.patient_id = p.patient_id AND f.status = 'Open') AS open_flag_count,
                      COALESCE(dev.connectivity_status, 'Missing_Data') AS device_status,
                      dev.last_seen_at AS device_last_seen,
                      dev.minutes_since_last_seen,
                      COALESCE(adh.self_reported_taken_pct, 100.0) AS adherence_this_week,
                      EXISTS(SELECT 1 FROM care_assignments ca WHERE ca.patient_id = p.patient_id AND ca.staff_id = %s) AS is_assigned
               FROM patients p
               LEFT JOIN discharge_records d ON d.patient_id = p.patient_id
               LEFT JOIN care_staff doc ON doc.staff_id = d.attending_staff_id
               LEFT JOIN care_assignments ca_n ON ca_n.patient_id = p.patient_id AND ca_n.assignment_role = 'Nurse'
               LEFT JOIN care_staff nurse ON nurse.staff_id = ca_n.staff_id
               LEFT JOIN v_device_status dev ON dev.patient_id = p.patient_id AND dev.device_type = 'ESP32_Watch'
               LEFT JOIN v_medication_adherence adh ON adh.patient_id = p.patient_id
               ORDER BY p.patient_id ASC""",
            (staff_id,),
        )
        rows = cur.fetchall()

        # Fetch latest checkin for each patient
        cur.execute(
            """SELECT s.patient_id, s.pain_level, s.reported_at
               FROM symptom_reports s
               INNER JOIN (
                   SELECT patient_id, MAX(reported_at) AS max_rep
                   FROM symptom_reports
                   GROUP BY patient_id
               ) latest ON s.patient_id = latest.patient_id AND s.reported_at = latest.max_rep"""
        )
        checkins = {c["patient_id"]: c for c in cur.fetchall()}

    results = []
    for r in rows:
        pid = r["patient_id"]
        chk = checkins.get(pid)
        r["last_checkin_at"] = chk["reported_at"] if chk else None
        r["last_checkin_pain"] = chk["pain_level"] if chk else None
        r["is_assigned"] = bool(r["is_assigned"])

        # Apply filters
        if filter == "mine" and not r["is_assigned"]:
            continue
        elif filter == "has_flags" and r["open_flag_count"] == 0:
            continue
        elif filter == "silent_device" and r["device_status"] == "Online":
            continue

        if search:
            q = search.lower().strip()
            match = (
                q in r["full_name"].lower()
                or q in (r["patient_code"] or "").lower()
                or q in (r["condition_summary"] or "").lower()
            )
            if not match:
                continue

        results.append(r)

    return results


@app.get("/staff/patients/{pid}")
def get_patient_detail(
    pid: int,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-05 Overview Tab: Comprehensive patient clinical snapshot.
    Includes identity, break-glass status (D-12), open flags, latest readings with quality,
    7-day dose adherence grid, 14-day pain trend, device status, caregiver consent, and upcoming appointment.
    """
    staff_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        # Check patient exists
        cur.execute(
            """SELECT p.patient_id, p.patient_code, p.full_name,
                      TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age_years,
                      p.date_of_birth, p.phone, ua.email,
                      d.discharge_date,
                      DATEDIFF(CURDATE(), d.discharge_date) + 1 AS day_number,
                      d.condition_summary, d.instructions, d.follow_up_due,
                      doc.full_name AS attending_doctor
               FROM patients p
               LEFT JOIN user_accounts ua ON ua.patient_id = p.patient_id
               LEFT JOIN discharge_records d ON d.patient_id = p.patient_id
               LEFT JOIN care_staff doc ON doc.staff_id = d.attending_staff_id
               WHERE p.patient_id = %s""",
            (pid,),
        )
        p = cur.fetchone()
        if not p:
            raise HTTPException(status_code=404, detail="Patient not found")

        # Assignment & Break-Glass check (D-12)
        cur.execute(
            """SELECT 1 FROM care_assignments WHERE patient_id = %s AND staff_id = %s""",
            (pid, staff_id),
        )
        is_assigned = cur.fetchone() is not None

        outside_assignment = False
        requires_break_glass = False
        if not is_assigned:
            outside_assignment = True
            cur.execute(
                """SELECT 1 FROM audit_log
                   WHERE actor_id = %s AND action = 'BREAK_GLASS_VIEW'
                     AND entity_type = 'patient' AND entity_id = %s
                     AND created_at >= NOW() - INTERVAL 12 HOUR""",
                (str(staff_id), pid),
            )
            if not cur.fetchone():
                requires_break_glass = True

        # Caregivers & Consent
        cur.execute(
            """SELECT caregiver_id, full_name, phone, relationship, consent_granted, is_primary
               FROM caregivers WHERE patient_id = %s ORDER BY is_primary DESC""",
            (pid,),
        )
        caregivers = cur.fetchall()

        # Open Flags
        cur.execute(
            """SELECT flag_id, severity, source_type, reason, created_at, status
               FROM flags WHERE patient_id = %s AND status IN ('Open', 'Acknowledged')
               ORDER BY FIELD(severity, 'Urgent_Review', 'Review_Soon', 'Info'), created_at DESC""",
            (pid,),
        )
        open_flags = cur.fetchall()

        # Latest readings with quality markers (D-18)
        cur.execute(
            """SELECT reading_id, measurement_type, measurement_value, unit, measured_at,
                      quality_status, device_id
               FROM sensor_readings
               WHERE patient_id = %s AND measured_at >= NOW() - INTERVAL 7 DAY
               ORDER BY measured_at DESC LIMIT 20""",
            (pid,),
        )
        recent_readings = cur.fetchall()

        latest_readings = {"Heart_Rate": None, "SpO2": None}
        for r in recent_readings:
            m_type = r["measurement_type"]
            if m_type in latest_readings and latest_readings[m_type] is None:
                latest_readings[m_type] = r

        # 7-day adherence grid
        cur.execute(
            """SELECT DATE(scheduled_for) AS log_date,
                      COUNT(*) AS total_doses,
                      SUM(status = 'Taken_Confirmed') AS taken_count,
                      SUM(status = 'Skipped') AS skipped_count,
                      SUM(status = 'Missed') AS missed_count,
                      SUM(status = 'Unconfirmed') AS pending_count
               FROM medication_logs l
               JOIN prescriptions pr ON pr.prescription_id = l.prescription_id
               WHERE pr.patient_id = %s AND l.scheduled_for >= NOW() - INTERVAL 7 DAY
               GROUP BY DATE(scheduled_for)
               ORDER BY log_date ASC""",
            (pid,),
        )
        adherence_grid = cur.fetchall()

        # 14-day pain trend
        cur.execute(
            """SELECT symptom_report_id, pain_level, symptom_text, reported_at, emergency_keyword_hit
               FROM symptom_reports
               WHERE patient_id = %s AND reported_at >= NOW() - INTERVAL 14 DAY
               ORDER BY reported_at ASC""",
            (pid,),
        )
        pain_trend = cur.fetchall()

        # Device status
        cur.execute(
            """SELECT device_id, device_type, connectivity_status, last_seen_at, minutes_since_last_seen
               FROM v_device_status WHERE patient_id = %s LIMIT 1""",
            (pid,),
        )
        device = cur.fetchone()

        # Next appointment
        cur.execute(
            """SELECT a.appointment_id, a.appointment_date, a.appointment_type, a.status, a.notes,
                      cs.full_name AS doctor_name
               FROM appointments a
               LEFT JOIN care_staff cs ON cs.staff_id = a.staff_id
               WHERE a.patient_id = %s AND a.appointment_date >= NOW()
               ORDER BY a.appointment_date ASC LIMIT 1""",
            (pid,),
        )
        next_apt = cur.fetchone()

        # Draft summary status
        cur.execute(
            """SELECT summary_id, status, generated_at, model_name
               FROM ai_summaries
               WHERE patient_id = %s
               ORDER BY generated_at DESC LIMIT 1""",
            (pid,),
        )
        draft_sum = cur.fetchone()

    return {
        "patient": p,
        "is_assigned": is_assigned,
        "outside_assignment": outside_assignment,
        "requires_break_glass": requires_break_glass,
        "caregivers": caregivers,
        "open_flags": open_flags,
        "latest_readings": latest_readings,
        "adherence_grid": adherence_grid,
        "pain_trend": pain_trend,
        "device": device,
        "next_appointment": next_apt,
        "draft_summary": draft_sum,
    }


@app.post("/staff/patients/{pid}/break-glass")
def break_glass_access(
    pid: int,
    body: BreakGlassIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-12 Break-Glass Access Endpoint:
    Logs audited justification for reviewing an unassigned patient.
    """
    reason = (body.reason or "").strip()
    if len(reason) < 5:
        raise HTTPException(
            status_code=400,
            detail="A clinical reason of at least 5 characters is required for break-glass access.",
        )

    staff_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT patient_id FROM patients WHERE patient_id = %s", (pid,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Patient not found")

        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Staff', %s, 'BREAK_GLASS_VIEW', 'patient', %s, JSON_OBJECT('reason', %s))""",
            (str(staff_id), pid, reason),
        )
        conn.commit()

    return {"status": "access_granted", "patient_id": pid}


@app.get("/staff/patients/{pid}/medicines")
def get_patient_medicines(
    pid: int,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-05 Medicines Tab Endpoint:
    Discharge prescriptions, 7-day adherence history, and skipped/unconfirmed logs with notes.
    Wording strictly uses 'Self-reported', not 'adherence outcome'.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT pr.prescription_id, pr.dose_instructions, pr.active_status,
                      pr.start_date, pr.end_date, m.medicine_name, m.general_notes
               FROM prescriptions pr
               JOIN medicines m ON m.medicine_id = pr.medicine_id
               WHERE pr.patient_id = %s
               ORDER BY pr.prescription_id ASC""",
            (pid,),
        )
        prescriptions = cur.fetchall()

        cur.execute(
            """SELECT l.medication_log_id, l.prescription_id, l.scheduled_for, l.status,
                      l.recorded_at, l.recorded_by, l.patient_note, m.medicine_name
               FROM medication_logs l
               JOIN prescriptions pr ON pr.prescription_id = l.prescription_id
               JOIN medicines m ON m.medicine_id = pr.medicine_id
               WHERE pr.patient_id = %s AND l.status IN ('Skipped', 'Missed', 'Unconfirmed')
               ORDER BY l.scheduled_for DESC LIMIT 30""",
            (pid,),
        )
        exceptions = cur.fetchall()

    now = datetime.now()
    formatted_exceptions = []
    for ex in exceptions:
        sched = ex["scheduled_for"]
        st = ex["status"]
        if st == "Unconfirmed":
            display_status = "Scheduled" if sched > now else "Not confirmed"
        elif st == "Skipped":
            display_status = "Skipped"
        else:
            display_status = "Missed"

        formatted_exceptions.append({
            "log_id": ex["medication_log_id"],
            "medicine_name": ex["medicine_name"],
            "scheduled_for": sched,
            "status": display_status,
            "patient_note": ex["patient_note"] or "No note provided",
            "recorded_by": ex["recorded_by"] or "Patient",
        })

    return {
        "prescriptions": prescriptions,
        "exceptions": formatted_exceptions,
        "adherence_label": "Self-reported",
    }


@app.get("/staff/patients/{pid}/rules")
def get_patient_rules(
    pid: int,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-05 Rules Tab Endpoint:
    Alert rules with threshold, window, severity, approver, 30-day fired count, and false alarm dismissals.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT r.rule_id, r.rule_type, r.measurement_type, r.threshold_value,
                      r.window_hours, r.severity, r.approved_at, r.is_active,
                      cs.full_name AS approved_by_name,
                      (SELECT COUNT(*) FROM flags f WHERE f.rule_id = r.rule_id AND f.created_at >= NOW() - INTERVAL 30 DAY) AS fired_count_30d,
                      (SELECT COUNT(*) FROM flags f WHERE f.rule_id = r.rule_id AND f.status = 'Dismissed' AND f.resolution_code = 'False_Alarm') AS dismissed_false_count
               FROM alert_rules r
               LEFT JOIN care_staff cs ON cs.staff_id = r.approved_by_staff_id
               WHERE r.patient_id = %s
               ORDER BY r.is_active DESC, r.rule_id ASC""",
            (pid,),
        )
        return {"rules": cur.fetchall()}


@app.get("/staff/patients/{pid}/timeline")
def get_patient_timeline(
    pid: int,
    event_types: str = "All",   # 'All' or comma-separated e.g. 'Readings,Symptoms,Doses,Flags,Calls,Notes'
    date_range: str = "all",     # 'today', '7days', 'all'
    limit: int = 200,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-06 Upgraded Clinical Timeline Endpoint:
    - Filter chips: Readings, Symptoms, Doses, Flags, Calls, Notes.
    - Date range: 'today', '7days', 'all'.
    - Grouped by day with sticky date headers and repeated event collapsing.
    - Future doses show 'Scheduled', past unconfirmed show 'Not confirmed'.
    - Sensor readings telemetry chart with quality markers and approved rule limits.
    """
    limit = min(limit, 200)
    now = datetime.now()

    with get_conn() as conn, conn.cursor() as cur:
        # Patient identity
        cur.execute(
            """SELECT patient_id, patient_code, full_name,
                      TIMESTAMPDIFF(YEAR, date_of_birth, CURDATE()) AS age_years
               FROM patients WHERE patient_id = %s""",
            (pid,),
        )
        patient_info = cur.fetchone()
        if not patient_info:
            raise HTTPException(status_code=404, detail="Patient not found")

        # 1. Readings
        cur.execute(
            """SELECT sr.reading_id AS event_id, sr.measured_at AS event_time, 'Reading' AS event_type,
                      CONCAT(sr.measurement_type, ' ', sr.measurement_value, ' ', sr.unit) AS summary,
                      'Sensor Telemetry' AS actor, sr.quality_status,
                      sr.measurement_type, sr.measurement_value, sr.unit
               FROM sensor_readings sr
               WHERE sr.patient_id = %s
               ORDER BY sr.measured_at DESC LIMIT %s""",
            (pid, limit),
        )
        readings = cur.fetchall()

        # 2. Symptoms
        cur.execute(
            """SELECT s.symptom_report_id AS event_id, s.reported_at AS event_time, 'Symptom' AS event_type,
                      CONCAT('Pain ', COALESCE(s.pain_level, 'n/a'), '/10: ', LEFT(s.symptom_text, 120)) AS summary,
                      'Patient' AS actor, NULL AS quality_status, s.emergency_keyword_hit
               FROM symptom_reports s
               WHERE s.patient_id = %s
               ORDER BY s.reported_at DESC LIMIT %s""",
            (pid, limit),
        )
        symptoms = cur.fetchall()

        # 3. Doses
        cur.execute(
            """SELECT ml.medication_log_id AS event_id, ml.scheduled_for AS event_time, 'Dose' AS event_type,
                      ml.status, ml.scheduled_for, m.medicine_name,
                      COALESCE(ml.recorded_by, 'Patient') AS actor, NULL AS quality_status
               FROM medication_logs ml
               JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
               JOIN medicines m ON m.medicine_id = pr.medicine_id
               WHERE pr.patient_id = %s
               ORDER BY ml.scheduled_for DESC LIMIT %s""",
            (pid, limit),
        )
        doses_raw = cur.fetchall()
        doses = []
        for d in doses_raw:
            st = d["status"]
            sched = d["scheduled_for"]
            if st == "Unconfirmed":
                disp = "Scheduled" if sched > now else "Not confirmed"
            elif st == "Taken_Confirmed":
                disp = "Taken"
            elif st == "Skipped":
                disp = "Skipped"
            else:
                disp = "Missed"
            doses.append({
                "event_id": d["event_id"],
                "event_time": sched,
                "event_type": "Dose",
                "summary": f"{d['medicine_name']} — {disp}",
                "actor": d["actor"],
                "quality_status": None,
                "dose_status": disp,
            })

        # 4. Flags
        cur.execute(
            """SELECT f.flag_id AS event_id, f.created_at AS event_time, 'Flag' AS event_type,
                      CONCAT(f.severity, ': ', f.reason) AS summary,
                      COALESCE(ack_s.full_name, 'System Rule') AS actor, NULL AS quality_status,
                      f.severity, f.status
               FROM flags f
               LEFT JOIN care_staff ack_s ON ack_s.staff_id = f.acknowledged_by_staff_id
               WHERE f.patient_id = %s
               ORDER BY f.created_at DESC LIMIT %s""",
            (pid, limit),
        )
        flags = cur.fetchall()

        # 5. Calls & Contacts
        cur.execute(
            """SELECT c.contact_id AS event_id, c.contacted_at AS event_time, 'Call' AS event_type,
                      CONCAT(c.channel, ' (', c.outcome, '): ', COALESCE(c.summary, 'Clinical outreach')) AS summary,
                      cs.full_name AS actor, NULL AS quality_status
               FROM contact_log c
               LEFT JOIN care_staff cs ON cs.staff_id = c.staff_id
               WHERE c.patient_id = %s
               ORDER BY c.contacted_at DESC LIMIT %s""",
            (pid, limit),
        )
        calls = cur.fetchall()

        # 6. Notes
        cur.execute(
            """SELECT n.note_id AS event_id, n.created_at AS event_time, 'Note' AS event_type,
                      CONCAT(n.note_type, ': ', LEFT(n.note_text, 120)) AS summary,
                      cs.full_name AS actor, NULL AS quality_status
               FROM clinician_notes n
               LEFT JOIN care_staff cs ON cs.staff_id = n.staff_id
               WHERE n.patient_id = %s
               ORDER BY n.created_at DESC LIMIT %s""",
            (pid, limit),
        )
        notes = cur.fetchall()

        # 7. Approved Rule Limits for Chart
        cur.execute(
            """SELECT rule_type, measurement_type, threshold_value
               FROM alert_rules
               WHERE patient_id = %s AND is_active = 1""",
            (pid,),
        )
        rules = cur.fetchall()
        chart_limits = {}
        for r in rules:
            if r["measurement_type"] == "Heart_Rate" and r["rule_type"] == "Reading_Above":
                chart_limits["hr_max"] = float(r["threshold_value"])
            elif r["measurement_type"] == "SpO2" and r["rule_type"] == "Reading_Below":
                chart_limits["spo2_min"] = float(r["threshold_value"])

    # Combine and filter events
    all_events = []
    selected_types = [t.strip().lower() for t in event_types.split(",")] if event_types != "All" else None

    candidates = list(readings) + list(symptoms) + list(doses) + list(flags) + list(calls) + list(notes)
    for ev in candidates:
        ev_type = ev["event_type"].lower()
        if selected_types and ev_type not in selected_types and "all" not in selected_types:
            continue

        ev_time = ev["event_time"]
        if date_range == "today" and ev_time.date() != now.date():
            continue
        elif date_range == "7days" and (now - ev_time).days > 7:
            continue

        all_events.append(ev)

    # Sort all events chronologically descending
    all_events.sort(key=lambda x: x["event_time"], reverse=True)
    all_events = all_events[:limit]

    # Group by Day with deduplication/collapse of repeated events (D-06)
    day_groups = {}
    for ev in all_events:
        day_str = ev["event_time"].strftime("%Y-%m-%d")
        if day_str not in day_groups:
            day_groups[day_str] = []
        day_groups[day_str].append(ev)

    grouped_result = []
    for day_str, items in day_groups.items():
        collapsed_items = []
        seen_keys = {}
        for item in items:
            key = (item["event_type"], item["summary"])
            if key not in seen_keys:
                item_copy = dict(item)
                item_copy["repeat_count"] = 1
                seen_keys[key] = len(collapsed_items)
                collapsed_items.append(item_copy)
            else:
                idx = seen_keys[key]
                collapsed_items[idx]["repeat_count"] += 1

        grouped_result.append({
            "date": day_str,
            "display_date": datetime.strptime(day_str, "%Y-%m-%d").strftime("%A, %d %b %Y"),
            "events": collapsed_items,
        })

    # Prepare chart readings (chronological ascending)
    chart_readings = []
    for r in reversed(readings):
        chart_readings.append({
            "time": r["event_time"].isoformat(),
            "metric": r.get("measurement_type"),
            "value": float(r.get("measurement_value") or 0),
            "unit": r.get("unit"),
            "quality": r.get("quality_status", "Good"),
        })

    return {
        "patient": patient_info,
        "total_events": len(all_events),
        "day_groups": grouped_result,
        "events": all_events,
        "chart_limits": chart_limits,
        "chart_readings": chart_readings,
    }


# ─── Patient Chat & RAG (Milestone M5) ────────────────────────────────────────

@app.post("/patient/me/chat")
def chat_with_assistant(body: ChatIn, user: Dict[str, Any] = Depends(require_role("Patient", "Caregiver"))):
    """
    Patient Chat Endpoint with Grounded RAG & Tool Routing (Brief Sec 7.2 - 7.12 & 8.6):
    - When USE_UPGRADED_RAG is true, routes through upgraded RAG pipeline:
      * Emergency words -> deterministic 112 guidance, no LLM.
      * Dose-change questions -> deterministic refusal + staff task.
      * Intent routing -> structured SQL tools (appointment, today doses, plan, vitals).
      * Hybrid retrieval over discharge chunks -> dense Chroma + keyword MySQL + RRF.
      * Numeric and citation guard -> enforces strict factual grounding.
    - Preserves backward compatibility fields (response, is_grounded, citations).
    """
    pid = get_effective_patient_id(user)
    effective_q = (body.question or body.message or "").strip()
    if not effective_q:
        raise HTTPException(400, "Question or message text cannot be empty.")

    with get_conn() as conn:
        with conn.cursor() as cur:
            # 1. Insert patient message
            cur.execute(
                """INSERT INTO chat_messages (patient_id, sender, message_text, conversation_id)
                   VALUES (%s, 'Patient', %s, %s)""",
                (pid, effective_q, body.conversation_id),
            )

            # Fetch recent conversation history for query rewrite
            cur.execute(
                """SELECT sender AS role, message_text AS content
                   FROM chat_messages
                   WHERE patient_id = %s AND (conversation_id = %s OR conversation_id IS NULL)
                   ORDER BY created_at DESC LIMIT 6""",
                (pid, body.conversation_id),
            )
            raw_hist = cur.fetchall()
            history = [{"role": "user" if r["role"] == "Patient" else "assistant", "content": r["content"]} for r in reversed(raw_hist)]

        # 2. Compute answer
        if USE_UPGRADED_RAG:
            rag_res = answer_patient_query(
                patient_id=pid,
                question=effective_q,
                conversation_id=body.conversation_id,
                language=body.language or "en",
                history=history,
            )
            ans = rag_res["answer"]
            bullets = rag_res.get("bullets", [])
            sources = rag_res.get("sources", [])
            suggestions = rag_res.get("suggestions", [])
            can_ask = rag_res.get("can_ask_care_team", False)
            is_grounded = rag_res.get("is_grounded", False)
            citations = rag_res.get("citations", [])
            answer_type = rag_res.get("answer_type", "grounded")
            debug_data = rag_res.get("retrieval_debug", {})
        else:
            # Legacy fallback
            ans, is_grounded, citations = rag_answer(pid, effective_q, body.language or "en", conn=conn)
            bullets = []
            sources = []
            suggestions = []
            can_ask = not is_grounded
            answer_type = "grounded" if is_grounded else "not_found"
            debug_data = {"legacy": True}

        with conn.cursor() as cur:
            # 3. Insert AI message with answer_type and retrieval_debug
            cur.execute(
                """INSERT INTO chat_messages (patient_id, sender, message_text, is_grounded, answer_type, conversation_id, retrieval_debug)
                   VALUES (%s, 'AI_Nurse', %s, %s, %s, %s, %s)""",
                (pid, ans, is_grounded, answer_type, body.conversation_id, json.dumps(debug_data, ensure_ascii=False)),
            )
            ai_msg_id = cur.lastrowid

            # 4. Link citations
            if citations:
                for vid in citations:
                    cur.execute(
                        "SELECT chunk_id FROM document_chunks WHERE vector_id = %s OR chunk_id = %s LIMIT 1",
                        (str(vid), str(vid)),
                    )
                    crow = cur.fetchone()
                    if crow:
                        cur.execute(
                            """INSERT IGNORE INTO chat_message_sources (message_id, chunk_id)
                               VALUES (%s, %s)""",
                            (ai_msg_id, crow["chunk_id"]),
                        )

            # 5. Audit log
            cur.execute(
                """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                   VALUES ('Patient', %s, 'CHAT_QUERY', 'chat_message', %s,
                           JSON_OBJECT('answer_type', %s, 'is_grounded', %s, 'citations_count', %s))""",
                (str(user["account_id"]), ai_msg_id, answer_type, is_grounded, len(citations)),
            )

    return {
        "message_id": ai_msg_id,
        "conversation_id": body.conversation_id,
        "answer_type": answer_type,
        "answer": ans,
        "bullets": bullets,
        "sources": sources,
        "suggestions": suggestions,
        "can_ask_care_team": can_ask,
        # Backward compatibility fields:
        "response": ans,
        "is_grounded": is_grounded,
        "citations": citations,
    }


@app.get("/patient/me/chat/history")
def get_chat_history(user: Dict[str, Any] = Depends(require_role("Patient", "Caregiver"))):
    """
    Returns patient chat history with answer types, source chips, and feedback ratings (Brief Sec 7.10 & 8.6).
    """
    pid = get_effective_patient_id(user)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT m.message_id, m.patient_id, m.sender, m.message_text,
                      m.is_grounded, m.created_at, m.answer_type, m.conversation_id,
                      f.rating AS feedback_rating
               FROM chat_messages m
               LEFT JOIN chat_feedback f ON f.message_id = m.message_id
               WHERE m.patient_id = %s
               ORDER BY m.created_at ASC LIMIT 100""",
            (pid,),
        )
        rows = cur.fetchall()

        messages = []
        for r in rows:
            msg_id = r["message_id"]
            created = r["created_at"].strftime("%d %b, %I:%M %p") if isinstance(r["created_at"], datetime) else str(r["created_at"])

            # Fetch sources for AI messages
            sources = []
            if r["sender"] == "AI_Nurse":
                cur.execute(
                    """SELECT c.chunk_id, c.chunk_text, c.section_title, c.page_no
                       FROM chat_message_sources s
                       JOIN document_chunks c ON c.chunk_id = s.chunk_id
                       WHERE s.message_id = %s""",
                    (msg_id,),
                )
                for s_row in cur.fetchall():
                    sec = s_row["section_title"] or "Discharge summary"
                    p_num = s_row["page_no"] or 1
                    sources.append({
                        "chunk_id": s_row["chunk_id"],
                        "label": f"Discharge summary · {sec} · p.{p_num}",
                        "snippet": s_row["chunk_text"][:160] + "...",
                        "text": s_row["chunk_text"],
                    })

            messages.append({
                "message_id": msg_id,
                "role": "user" if r["sender"] == "Patient" else "assistant",
                "sender": r["sender"],
                "content": r["message_text"],
                "message_text": r["message_text"],
                "response": r["message_text"],
                "is_grounded": bool(r["is_grounded"]),
                "grounded": bool(r["is_grounded"]),
                "answer_type": r["answer_type"] or ("grounded" if r["is_grounded"] else "not_found"),
                "conversation_id": r["conversation_id"],
                "created_at": created,
                "timestamp": r["created_at"].isoformat() if isinstance(r["created_at"], datetime) else str(r["created_at"]),
                "sources": sources,
                "feedback_rating": r["feedback_rating"],
            })

        return messages


@app.post("/patient/me/chat/{message_id}/ask-care-team")
def ask_care_team_from_chat(
    message_id: int,
    user: Dict[str, Any] = Depends(require_role("Patient", "Caregiver")),
):
    """
    Creates a clinical follow-up task and writes an audit row when a patient escalates a question (Brief Sec 7.7 & 8.6).
    """
    pid = get_effective_patient_id(user)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT message_id, message_text FROM chat_messages
               WHERE message_id = %s AND patient_id = %s""",
            (message_id, pid),
        )
        msg = cur.fetchone()
        if not msg:
            raise HTTPException(404, "Message not found or does not belong to this patient.")

        cur.execute(
            """SELECT attending_staff_id FROM discharge_records
               WHERE patient_id = %s ORDER BY discharge_date DESC LIMIT 1""",
            (pid,),
        )
        drow = cur.fetchone() or {}
        assigned_staff = drow.get("attending_staff_id") or 1

        cur.execute(
            """INSERT INTO follow_up_tasks (patient_id, assigned_staff_id, priority, reason, status)
               VALUES (%s, %s, 'Routine', %s, 'Pending')""",
            (pid, assigned_staff, f"Patient asked care team to follow up on: '{msg['message_text'][:200]}'"),
        )
        task_id = cur.lastrowid

        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Patient', %s, 'ASK_CARE_TEAM', 'chat_message', %s,
                       JSON_OBJECT('task_id', %s, 'assigned_staff', %s))""",
            (str(user["account_id"]), message_id, task_id, assigned_staff),
        )

        return {
            "ok": True,
            "status": "task_created",
            "task_id": task_id,
            "message": "Your question has been forwarded to your care team.",
        }


@app.post("/patient/me/chat/{message_id}/feedback")
def submit_chat_feedback(
    message_id: int,
    body: FeedbackIn,
    user: Dict[str, Any] = Depends(require_role("Patient", "Caregiver")),
):
    """
    Records 👍 (1) or 👎 (-1) rating with optional patient comment (Brief Sec 7.10 & 9.2).
    """
    pid = get_effective_patient_id(user)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT message_id FROM chat_messages
               WHERE message_id = %s AND patient_id = %s""",
            (message_id, pid),
        )
        if not cur.fetchone():
            raise HTTPException(404, "Message not found or does not belong to this patient.")

        cur.execute(
            """INSERT INTO chat_feedback (message_id, rating, comment)
               VALUES (%s, %s, %s)
               ON DUPLICATE KEY UPDATE rating = VALUES(rating), comment = VALUES(comment)""",
            (message_id, body.rating, body.comment),
        )
        feedback_id = cur.lastrowid

        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Patient', %s, 'CHAT_FEEDBACK', 'chat_feedback', %s,
                       JSON_OBJECT('rating', %s, 'message_id', %s))""",
            (str(user["account_id"]), feedback_id, body.rating, message_id),
        )

        return {
            "status": "feedback_recorded",
            "feedback_id": feedback_id,
            "message_id": message_id,
            "rating": body.rating,
        }


# ─── Daily AI Summaries & Clinician Review (Milestone M5) ────────────────────

# ─── Clinical Summaries Rebuilt (Feature D-08) ────────────────────────────────

class GenerateSummaryIn(BaseModel):
    patient_id: int
    target_date: Optional[str] = None


class ApproveSummaryIn(BaseModel):
    edited_text: Optional[str] = None


class RejectSummaryIn(BaseModel):
    reason: str


@app.get("/staff/summaries")
def get_staff_summaries(
    status: str = "all",            # 'draft', 'approved', 'rejected', 'all'
    patient_id: Optional[int] = None,
    search: str = "",
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-08: Clinical summaries directory with SBAR structure, source facts snapshot,
    approver attribution, and status badges.
    """
    query = """
        SELECT s.summary_id,
               s.patient_id,
               p.patient_code,
               p.full_name AS patient_name,
               TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age_years,
               COALESCE(d.condition_summary, 'Post-discharge recovery') AS primary_diagnosis,
               s.period_start,
               s.period_end,
               s.summary_text,
               s.model_name,
               s.generated_at,
               s.status,
               s.reviewed_by_staff_id,
               u.full_name AS reviewed_by_name,
               s.reviewed_at,
               s.edited_text,
               s.reject_reason,
               s.source_snapshot
        FROM ai_summaries s
        JOIN patients p ON p.patient_id = s.patient_id
        LEFT JOIN discharge_records d ON d.patient_id = p.patient_id
        LEFT JOIN care_staff u ON u.staff_id = s.reviewed_by_staff_id
        WHERE 1=1
    """
    params: List[Any] = []

    if status == "draft":
        query += " AND s.status = 'Draft'"
    elif status == "approved":
        query += " AND s.status = 'Approved'"
    elif status == "rejected":
        query += " AND s.status = 'Rejected'"

    if patient_id is not None:
        query += " AND s.patient_id = %s"
        params.append(patient_id)

    if search.strip():
        term = f"%{search.strip()}%"
        query += " AND (p.full_name LIKE %s OR p.patient_code LIKE %s OR COALESCE(d.condition_summary, '') LIKE %s)"
        params.extend([term, term, term])

    query += " ORDER BY s.generated_at DESC"

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(query, tuple(params))
        rows = cur.fetchall() or []

    result = []
    for r in rows:
        r_dict = dict(r)
        st = r.get("status")
        rev_name = r.get("reviewed_by_name")
        rev_at = r.get("reviewed_at")

        # Human status label
        if st == "Draft":
            status_label = "AI draft, not reviewed"
        elif st == "Approved":
            rev_time_str = rev_at.strftime("%d %b %H:%M") if rev_at else ""
            status_label = f"Approved by Dr. {rev_name or 'Doctor'}, {rev_time_str}"
        elif st == "Rejected":
            status_label = f"Rejected: {r.get('reject_reason') or 'Clinical revision required'}"
        else:
            status_label = st

        r_dict["status_label"] = status_label

        # Parse source snapshot if JSON
        snap = r.get("source_snapshot")
        if snap and isinstance(snap, str):
            try:
                r_dict["source_snapshot"] = json.loads(snap)
            except Exception:
                pass

        # Parse summary_text if JSON
        txt = r.get("summary_text")
        parsed_sbar = None
        if txt and isinstance(txt, str) and txt.strip().startswith("{"):
            try:
                parsed_sbar = json.loads(txt)
            except Exception:
                pass
        r_dict["parsed_sbar"] = parsed_sbar

        result.append(r_dict)

    return result


@app.post("/staff/summaries/generate")
def generate_clinical_summary(
    body: GenerateSummaryIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-08: Deterministic Fact Sheet -> SBAR Rewrite -> Mandatory Safety Guard -> Store.
    Never sends patient names to LLM ('the patient').
    """
    pid = body.patient_id
    target_date = body.target_date or datetime.now(IST).strftime("%Y-%m-%d")

    with get_conn() as conn:
        # 1. Build deterministic fact sheet from SQL without patient name
        fact_sheet = build_deterministic_fact_sheet(conn, pid, target_date)

        # 2. LLM rewrite + Guard pipeline (with automatic fallback on any guard violation)
        draft_dict, model_name, guard_status = produce_clinical_summary(fact_sheet)
        summary_text = json.dumps(draft_dict)

        period_start = f"{target_date} 00:00:00"
        period_end = f"{target_date} 23:59:59"
        snapshot_json = json.dumps(fact_sheet)

        with conn.cursor() as cur:
            # Check if an unreviewed Draft already exists for this patient on this date
            cur.execute(
                """SELECT summary_id FROM ai_summaries
                   WHERE patient_id = %s AND period_start = %s AND status = 'Draft'
                   LIMIT 1""",
                (pid, period_start),
            )
            existing = cur.fetchone()
            if existing:
                summary_id = existing["summary_id"]
                cur.execute(
                    """UPDATE ai_summaries
                       SET summary_text = %s, model_name = %s, source_snapshot = %s, generated_at = NOW()
                       WHERE summary_id = %s""",
                    (summary_text, model_name, snapshot_json, summary_id),
                )
            else:
                cur.execute(
                    """INSERT INTO ai_summaries
                       (patient_id, period_start, period_end, summary_text, model_name, status, source_snapshot)
                       VALUES (%s, %s, %s, %s, %s, 'Draft', %s)""",
                    (pid, period_start, period_end, summary_text, model_name, snapshot_json),
                )
                summary_id = cur.lastrowid

            cur.execute(
                """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                   VALUES ('Staff', %s, 'GENERATE_AI_SUMMARY', 'ai_summary', %s,
                           JSON_OBJECT('patient_id', %s, 'date', %s, 'guard_status', %s))""",
                (str(user["staff_id"]), summary_id, pid, target_date, guard_status),
            )
            conn.commit()

    return {
        "summary_id": summary_id,
        "patient_id": pid,
        "period_start": period_start,
        "period_end": period_end,
        "summary_text": summary_text,
        "parsed_sbar": draft_dict,
        "model_name": model_name,
        "guard_status": guard_status,
        "status": "Draft",
        "status_label": "AI draft, not reviewed",
        "source_snapshot": fact_sheet,
    }


@app.post("/staff/patients/{pid}/summaries/generate")
def generate_patient_summary_legacy(
    pid: int,
    summary_date: Optional[str] = None,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Legacy route forwarding to modern D-08 pipeline."""
    return generate_clinical_summary(
        GenerateSummaryIn(patient_id=pid, target_date=summary_date),
        user=user,
    )


@app.get("/staff/summaries/pending")
def get_pending_summaries(user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse"))):
    """Returns AI draft summaries waiting for clinician review."""
    return get_staff_summaries(status="draft", user=user)


@app.post("/staff/summaries/{summary_id}/approve")
def approve_summary(
    summary_id: int,
    body: ApproveSummaryIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-08 & D-12: Approve draft summary.
    STRICT RULE: Doctor role is required! Nurses cannot approve summaries.
    """
    if user.get("role") != "Doctor":
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Only doctors can approve clinical summaries. Nurses can propose but cannot approve.",
        )
    doctor_staff_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        try:
            cur.callproc("sp_approve_summary", (summary_id, doctor_staff_id, body.edited_text))
            conn.commit()
        except pymysql.MySQLError as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))

    return {
        "status": "Approved",
        "summary_id": summary_id,
        "reviewed_by_staff_id": doctor_staff_id,
    }


@app.post("/staff/summaries/{summary_id}/reject")
def reject_summary(
    summary_id: int,
    body: RejectSummaryIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-08 & D-12: Reject draft summary with required clinical reason.
    STRICT RULE: Doctor role is required!
    """
    if user.get("role") != "Doctor":
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Only doctors can reject clinical summaries.",
        )
    if not body.reason or len(body.reason.strip()) < 3:
        raise HTTPException(status_code=400, detail="A reason of at least 3 characters is required to reject a summary")

    doctor_staff_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        try:
            cur.callproc("sp_reject_summary", (summary_id, doctor_staff_id, body.reason.strip()))
            conn.commit()
        except pymysql.MySQLError as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(e))

    return {
        "status": "Rejected",
        "summary_id": summary_id,
        "reviewed_by_staff_id": doctor_staff_id,
        "reason": body.reason.strip(),
    }


@app.post("/staff/summaries/{summary_id}/review")
def review_summary_legacy(
    summary_id: int,
    body: ReviewSummaryIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Legacy review route redirecting to approve/reject."""
    action = (body.action or "").lower()
    if action == "approve":
        return approve_summary(summary_id, ApproveSummaryIn(edited_text=body.notes), user=user)
    else:
        return reject_summary(summary_id, RejectSummaryIn(reason=body.notes or "Rejected by clinician"), user=user)


@app.post("/staff/summaries/generate-all-mine")
def generate_all_mine_summaries(
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-08: Batch generates fresh draft summaries for all patients under clinician's care.
    Never creates duplicate drafts for the same patient and period.
    """
    staff_id = user["staff_id"]
    target_date = datetime.now(IST).strftime("%Y-%m-%d")

    with get_conn() as conn, conn.cursor() as cur:
        # Find all patients assigned to this staff member
        cur.execute(
            """SELECT DISTINCT p.patient_id
               FROM patients p
               LEFT JOIN care_assignments ca ON ca.patient_id = p.patient_id
               LEFT JOIN follow_up_tasks t ON t.patient_id = p.patient_id AND t.assigned_staff_id = %s
               LEFT JOIN flags f ON f.patient_id = p.patient_id AND f.owner_staff_id = %s
               WHERE p.attending_doctor_id = %s
                  OR ca.doctor_staff_id = %s
                  OR ca.nurse_staff_id = %s
                  OR t.assigned_staff_id = %s
                  OR f.owner_staff_id = %s""",
            (staff_id, staff_id, staff_id, staff_id, staff_id, staff_id, staff_id),
        )
        patients = cur.fetchall() or []

    generated = []
    for row in patients:
        pid = row["patient_id"]
        res = generate_clinical_summary(
            GenerateSummaryIn(patient_id=pid, target_date=target_date),
            user=user,
        )
        generated.append(res)

    return {
        "status": "success",
        "generated_count": len(generated),
        "summaries": generated,
    }


# ─── Shift Handoff I-PASS (Feature D-09) ──────────────────────────────────────

class HandoffContingencyIn(BaseModel):
    contingency_note: str


class HandoffExportIn(BaseModel):
    export_format: str = "PDF"  # 'PDF', 'Print', 'CSV'


@app.get("/staff/handoff")
def get_shift_handoff(
    scope: str = "mine",  # 'mine', 'all'
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-09: Shift handoff page with I-PASS sections built from deterministic data:
    - Illness/attention tier (Immediate, Urgent, Review soon, Routine from flags; NO stable/unstable)
    - Patient summary: condition, day number, key facts
    - Action list: open tasks with owners and due times
    - Situation awareness & contingency: open flags, silent devices, upcoming appointments,
      "If X happens call Y" contingency text
    - Synthesis: incoming clinician received check
    """
    staff_id = user["staff_id"]
    now_dt = datetime.now()

    with get_conn() as conn, conn.cursor() as cur:
        # 1. Fetch patients
        p_query = """
            SELECT p.patient_id, p.patient_code, p.full_name,
                   TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age_years,
                   COALESCE(d.condition_summary, 'Post-discharge recovery') AS condition_summary,
                   d.discharge_date,
                   DATEDIFF(CURDATE(), d.discharge_date) + 1 AS day_number,
                   cs.full_name AS attending_doctor
            FROM patients p
            LEFT JOIN discharge_records d ON d.patient_id = p.patient_id
            LEFT JOIN care_staff cs ON cs.staff_id = d.attending_staff_id
            LEFT JOIN care_assignments ca ON ca.patient_id = p.patient_id
            WHERE 1=1
        """
        if scope == "mine":
            p_query += """ AND (ca.doctor_staff_id = %s OR ca.nurse_staff_id = %s 
                                OR d.attending_staff_id = %s OR EXISTS (
                                    SELECT 1 FROM follow_up_tasks ft 
                                    WHERE ft.patient_id = p.patient_id AND ft.assigned_staff_id = %s
                                ))"""
            params = (staff_id, staff_id, staff_id, staff_id)
            cur.execute(p_query, params)
        else:
            cur.execute(p_query)
        patients = cur.fetchall() or []

        # If empty in mine scope, fallback to all patients so handoff is never blank
        if not patients and scope == "mine":
            cur.execute(
                """SELECT p.patient_id, p.patient_code, p.full_name,
                          TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age_years,
                          COALESCE(d.condition_summary, 'Post-discharge recovery') AS condition_summary,
                          d.discharge_date,
                          DATEDIFF(CURDATE(), d.discharge_date) + 1 AS day_number,
                          cs.full_name AS attending_doctor
                   FROM patients p
                   LEFT JOIN discharge_records d ON d.patient_id = p.patient_id
                   LEFT JOIN care_staff cs ON cs.staff_id = d.attending_staff_id"""
            )
            patients = cur.fetchall() or []

        handoff_cards = []
        for p in patients:
            pid = p["patient_id"]

            # Open flags
            cur.execute(
                """SELECT flag_id, severity, reason, status, created_at
                   FROM flags
                   WHERE patient_id = %s AND status IN ('Open', 'Acknowledged')
                   ORDER BY FIELD(severity, 'Immediate', 'Urgent', 'Review_Soon', 'Routine'), created_at DESC""",
                (pid,),
            )
            flags = cur.fetchall() or []

            # Illness tier from flags only: Immediate > Urgent > Review soon > Routine
            if any(f["severity"] == "Immediate" for f in flags):
                illness_tier = "Immediate"
            elif any(f["severity"] == "Urgent" for f in flags):
                illness_tier = "Urgent"
            elif any(f["severity"] == "Review_Soon" for f in flags):
                illness_tier = "Review soon"
            else:
                illness_tier = "Routine"

            # Open tasks
            cur.execute(
                """SELECT t.followup_id, t.reason, t.priority, t.due_at, t.status, cs.full_name AS assigned_staff_name
                   FROM follow_up_tasks t
                   LEFT JOIN care_staff cs ON cs.staff_id = t.assigned_staff_id
                   WHERE t.patient_id = %s AND t.status != 'Resolved'
                   ORDER BY t.due_at ASC""",
                (pid,),
            )
            tasks = cur.fetchall() or []

            # Silent devices
            cur.execute(
                """SELECT device_id, device_type, last_seen_at
                   FROM devices
                   WHERE patient_id = %s AND (last_seen_at IS NULL OR TIMESTAMPDIFF(HOUR, last_seen_at, NOW()) >= 24)""",
                (pid,),
            )
            silent_devices = cur.fetchall() or []

            # Upcoming appointments
            cur.execute(
                """SELECT appointment_id, appointment_date, appointment_type, notes
                   FROM appointments
                   WHERE patient_id = %s AND appointment_date >= CURDATE()
                   ORDER BY appointment_date ASC LIMIT 2""",
                (pid,),
            )
            appts = cur.fetchall() or []

            # Contingency note
            cur.execute(
                """SELECT note_text, created_at
                   FROM clinician_notes
                   WHERE patient_id = %s AND note_type IN ('Plan_Change', 'General')
                   ORDER BY note_id DESC LIMIT 1""",
                (pid,),
            )
            c_note_row = cur.fetchone()
            contingency_note = c_note_row["note_text"] if c_note_row else "Standard escalation protocol: If SpO2 < 90% or severe chest pain, escalate to attending doctor."

            # Synthesis: check if received in last 12 hours
            cur.execute(
                """SELECT created_at, actor_id
                   FROM audit_log
                   WHERE entity_type = 'handoff' AND entity_id = %s AND action = 'HANDOFF_RECEIVED'
                     AND created_at >= NOW() - INTERVAL 12 HOUR
                   ORDER BY log_id DESC LIMIT 1""",
                (pid,),
            )
            rec_row = cur.fetchone()
            is_received = rec_row is not None
            received_at = rec_row["created_at"].strftime("%H:%M") if rec_row else None

            handoff_cards.append({
                "patient_id": pid,
                "patient_code": p["patient_code"],
                "full_name": p["full_name"],
                "age_years": p["age_years"],
                "attending_doctor": p["attending_doctor"] or "Attending Physician",
                "illness_tier": illness_tier,
                "patient_summary": {
                    "condition": p["condition_summary"],
                    "discharge_date": str(p["discharge_date"] or ""),
                    "day_number": max(1, p["day_number"] or 1),
                },
                "action_list": [
                    {
                        "task_id": t["followup_id"],
                        "reason": t["reason"],
                        "priority": t["priority"],
                        "due_at": str(t["due_at"]) if t["due_at"] else "Today",
                        "owner": t["assigned_staff_name"] or "Unassigned",
                    }
                    for t in tasks
                ],
                "situation_awareness": {
                    "open_flags": [
                        {"flag_id": f["flag_id"], "severity": f["severity"], "reason": f["reason"]}
                        for f in flags
                    ],
                    "silent_devices": [
                        {"device_type": d["device_type"], "last_seen": str(d["last_seen_at"] or "Never")}
                        for d in silent_devices
                    ],
                    "appointments": [
                        {"date": str(a["appointment_date"]), "type": a["appointment_type"], "notes": a["notes"] or ""}
                        for a in appts
                    ],
                },
                "contingency_note": contingency_note,
                "is_received": is_received,
                "received_at": received_at,
            })

    return {
        "shift_name": "Day Shift" if 8 <= now_dt.hour < 20 else "Night Shift",
        "date": now_dt.strftime("%d %b %Y"),
        "clinician_name": user.get("name", "Staff Clinician"),
        "role": user.get("role", "Clinician"),
        "patients": handoff_cards,
    }


@app.post("/staff/handoff/{patient_id}/receive")
def receive_patient_handoff(
    patient_id: int,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """D-09: Incoming clinician acknowledges receipt of patient handoff."""
    staff_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Staff', %s, 'HANDOFF_RECEIVED', 'handoff', %s,
                       JSON_OBJECT('staff_id', %s, 'role', %s, 'time', NOW()))""",
            (str(staff_id), patient_id, staff_id, user.get("role", "Staff")),
        )
        conn.commit()
    return {"status": "received", "patient_id": patient_id, "staff_id": staff_id}


@app.post("/staff/handoff/{patient_id}/contingency")
def update_patient_contingency(
    patient_id: int,
    body: HandoffContingencyIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """D-09: Update 'If X happens call Y' contingency note."""
    staff_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO clinician_notes (patient_id, staff_id, note_type, note_text)
               VALUES (%s, %s, 'Plan_Change', %s)""",
            (patient_id, staff_id, body.contingency_note.strip()),
        )
        note_id = cur.lastrowid
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Staff', %s, 'HANDOFF_CONTINGENCY_UPDATED', 'clinician_note', %s,
                       JSON_OBJECT('patient_id', %s, 'note_text', %s))""",
            (str(staff_id), note_id, patient_id, body.contingency_note.strip()),
        )
        conn.commit()
    return {"status": "updated", "patient_id": patient_id, "contingency_note": body.contingency_note.strip()}


@app.post("/staff/handoff/export-log")
def log_handoff_export(
    body: HandoffExportIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """D-09: Audit log whenever a clinician prints or exports handoff."""
    staff_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Staff', %s, 'HANDOFF_EXPORTED', 'handoff_report', 0,
                       JSON_OBJECT('staff_id', %s, 'format', %s))""",
            (str(staff_id), staff_id, body.export_format),
        )
        conn.commit()
    return {"status": "logged", "format": body.export_format}


# ─── Escalation Ladder Visibility (Feature D-10) ──────────────────────────────

@app.get("/staff/flags/{flag_id}/escalations")
def get_flag_escalations(
    flag_id: int,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-10: Shows the ladder as a timeline: Patient prompt, Caregiver SMS (or 'Skipped: no consent'),
    Nurse alert, Doctor alert, with status, time, and countdown.
    Acknowledging stops the ladder and says so.
    """
    with get_conn() as conn, conn.cursor() as cur:
        # Fetch flag
        cur.execute(
            """SELECT f.flag_id, f.severity, f.status, f.created_at, f.acknowledged_at,
                      cs.full_name AS acknowledged_by_name, p.consent_status, p.patient_id
               FROM flags f
               JOIN patients p ON p.patient_id = f.patient_id
               LEFT JOIN care_staff cs ON cs.staff_id = f.owner_staff_id
               WHERE f.flag_id = %s""",
            (flag_id,),
        )
        flag = cur.fetchone()
        if not flag:
            raise HTTPException(status_code=404, detail="Flag not found")

        # Fetch escalation steps from DB
        cur.execute(
            """SELECT escalation_id, step_no, step_type, channel, sent_at, delivery_status, responded_at, notes
               FROM escalations
               WHERE flag_id = %s
               ORDER BY step_no ASC""",
            (flag_id,),
        )
        db_steps = cur.fetchall() or []

        # If no DB steps exist yet, synthesize standard 4-step ladder
        ladder_types = ["Patient_Prompt", "Caregiver_SMS", "Nurse_Alert", "Doctor_Alert"]
        step_labels = {
            "Patient_Prompt": "Step 1: Patient In-App Check-in Prompt",
            "Caregiver_SMS": "Step 2: Caregiver Alert SMS",
            "Nurse_Alert": "Step 3: Primary Nurse Clinical Alert",
            "Doctor_Alert": "Step 4: Attending Physician Escalation",
        }

        ladder = []
        is_flag_closed = flag["status"] in ("Acknowledged", "Resolved")
        ack_by = flag.get("acknowledged_by_name") or "Care Team Member"
        ack_time = flag.get("acknowledged_at")

        for idx, stype in enumerate(ladder_types, start=1):
            matching = next((s for s in db_steps if s["step_type"] == stype), None)
            if matching:
                ladder.append({
                    "step_no": matching["step_no"],
                    "step_type": stype,
                    "title": step_labels.get(stype, stype),
                    "channel": matching["channel"],
                    "sent_at": str(matching["sent_at"]),
                    "delivery_status": matching["delivery_status"],
                    "notes": matching["notes"] or "",
                })
            else:
                # Synthesize step
                if stype == "Patient_Prompt":
                    deliv = "Acknowledged" if is_flag_closed else "Sent"
                    notes = "Delivered to patient smartphone app"
                elif stype == "Caregiver_SMS":
                    has_consent = flag.get("consent_status") == "Granted"
                    deliv = "Sent" if has_consent else "Skipped_No_Consent"
                    notes = "SMS dispatched to registered caregiver" if has_consent else "Skipped: Caregiver consent not granted"
                elif stype == "Nurse_Alert":
                    deliv = "Acknowledged" if is_flag_closed else "Sent"
                    notes = "Priority card highlighted on duty nurse worklist"
                else:
                    deliv = "Acknowledged" if is_flag_closed else "Queued"
                    notes = "Direct pager / SMS escalation"

                ladder.append({
                    "step_no": idx,
                    "step_type": stype,
                    "title": step_labels.get(stype, stype),
                    "channel": "SMS" if "SMS" in stype else "App",
                    "sent_at": str(flag["created_at"]),
                    "delivery_status": deliv,
                    "notes": notes,
                })

        stopped_banner = None
        if is_flag_closed:
            t_str = ack_time.strftime("%H:%M") if ack_time else ""
            stopped_banner = f"Ladder stopped — {flag['status']} by {ack_by} at {t_str}"

    return {
        "flag_id": flag_id,
        "severity": flag["severity"],
        "status": flag["status"],
        "is_stopped": is_flag_closed,
        "stopped_banner": stopped_banner,
        "steps": ladder,
    }


# ─── Notifications (Feature D-11) ─────────────────────────────────────────────

@app.get("/staff/notifications")
def get_staff_notifications(
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-11: Notification bell items needing action:
    - New urgent or immediate flags
    - Flags escalated to me
    - Tasks due within the hour
    - Tasks overdue
    """
    staff_id = user["staff_id"]
    notifications = []

    with get_conn() as conn, conn.cursor() as cur:
        # 1. Urgent & Immediate open flags
        cur.execute(
            """SELECT f.flag_id, f.severity, f.reason, f.created_at, p.patient_code, p.full_name
               FROM flags f
               JOIN patients p ON p.patient_id = f.patient_id
               WHERE f.status = 'Open' AND f.severity IN ('Immediate', 'Urgent')
               ORDER BY FIELD(f.severity, 'Immediate', 'Urgent'), f.created_at DESC LIMIT 10"""
        )
        flags = cur.fetchall() or []
        for f in flags:
            notifications.append({
                "id": f"flag-{f['flag_id']}",
                "entity_type": "flag",
                "entity_id": f["flag_id"],
                "tier": f["severity"],
                "title": f"🚨 {f['severity']} Flag: {f['patient_code']} {f['full_name']}",
                "description": f["reason"],
                "created_at": str(f["created_at"]),
                "can_snooze": False,  # Immediate and Urgent CANNOT be snoozed
            })

        # 2. Overdue tasks
        cur.execute(
            """SELECT t.followup_id, t.priority, t.reason, t.due_at, p.patient_code, p.full_name,
                      ROUND(TIMESTAMPDIFF(MINUTE, t.due_at, NOW()) / 60.0, 1) AS hours_overdue
               FROM follow_up_tasks t
               JOIN patients p ON p.patient_id = t.patient_id
               WHERE t.status != 'Resolved' AND t.due_at IS NOT NULL AND t.due_at < NOW()
                 AND (t.assigned_staff_id = %s OR t.assigned_staff_id IS NULL)
               ORDER BY t.due_at ASC LIMIT 10""",
            (staff_id,),
        )
        overdue_tasks = cur.fetchall() or []
        for ot in overdue_tasks:
            is_routine = ot["priority"] == "Routine"
            notifications.append({
                "id": f"task-od-{ot['followup_id']}",
                "entity_type": "task",
                "entity_id": ot["followup_id"],
                "tier": "Urgent" if ot["priority"] == "Urgent_Review" else "Routine",
                "title": f"⚠️ Overdue Task: {ot['patient_code']} ({ot['hours_overdue']}h overdue)",
                "description": ot["reason"],
                "created_at": str(ot["due_at"]),
                "can_snooze": is_routine,  # Snooze allowed for Routine only
            })

        # 3. Tasks due within the hour
        cur.execute(
            """SELECT t.followup_id, t.priority, t.reason, t.due_at, p.patient_code, p.full_name
               FROM follow_up_tasks t
               JOIN patients p ON p.patient_id = t.patient_id
               WHERE t.status != 'Resolved' AND t.due_at IS NOT NULL
                 AND t.due_at BETWEEN NOW() AND NOW() + INTERVAL 1 HOUR
                 AND (t.assigned_staff_id = %s OR t.assigned_staff_id IS NULL)
               ORDER BY t.due_at ASC LIMIT 10""",
            (staff_id,),
        )
        due_soon = cur.fetchall() or []
        for dt in due_soon:
            is_routine = dt["priority"] == "Routine"
            notifications.append({
                "id": f"task-soon-{dt['followup_id']}",
                "entity_type": "task",
                "entity_id": dt["followup_id"],
                "tier": "Routine",
                "title": f"⏰ Task Due Soon: {dt['patient_code']}",
                "description": dt["reason"],
                "created_at": str(dt["due_at"]),
                "can_snooze": is_routine,
            })

    return {
        "count": len(notifications),
        "notifications": notifications,
    }


# ─── Communication Log (Feature D-15) ─────────────────────────────────────────

class LogContactIn(BaseModel):
    patient_id: int
    flag_id: Optional[int] = None
    task_id: Optional[int] = None
    channel: str  # 'Phone', 'SMS', 'In_Person', 'Video'
    outcome: str  # 'Reached', 'No_Answer', 'Left_Message', 'Wrong_Number', 'Declined'
    summary: Optional[str] = ""


VALID_CHANNELS = {"Phone", "SMS", "In_Person", "Video"}
VALID_CONTACT_OUTCOMES = {"Reached", "No_Answer", "Left_Message", "Wrong_Number", "Declined"}


@app.post("/staff/contacts/log")
def log_contact(
    body: LogContactIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-15: Log call or message: channel, outcome, summary, links to flag or task.
    Saved in contact_log and audit_log.
    """
    if body.channel not in VALID_CHANNELS:
        raise HTTPException(status_code=400, detail=f"Invalid channel. Allowed: {sorted(list(VALID_CHANNELS))}")
    if body.outcome not in VALID_CONTACT_OUTCOMES:
        raise HTTPException(status_code=400, detail=f"Invalid outcome. Allowed: {sorted(list(VALID_CONTACT_OUTCOMES))}")

    staff_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO contact_log (patient_id, staff_id, flag_id, task_id, channel, outcome, summary)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (body.patient_id, staff_id, body.flag_id, body.task_id, body.channel, body.outcome, body.summary or ""),
        )
        contact_id = cur.lastrowid

        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Staff', %s, 'CONTACT_LOGGED', 'contact_log', %s,
                       JSON_OBJECT('patient_id', %s, 'channel', %s, 'outcome', %s, 'summary', %s))""",
            (str(staff_id), contact_id, body.patient_id, body.channel, body.outcome, body.summary or ""),
        )
        conn.commit()

    return {
        "status": "logged",
        "contact_id": contact_id,
        "patient_id": body.patient_id,
        "channel": body.channel,
        "outcome": body.outcome,
    }


@app.get("/staff/patients/{patient_id}/contacts")
def get_patient_contacts(
    patient_id: int,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """D-15: Retrieve communication logs for a patient."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT c.contact_id, c.patient_id, c.staff_id, cs.full_name AS staff_name,
                      c.flag_id, c.task_id, c.channel, c.outcome, c.summary, c.contacted_at
               FROM contact_log c
               LEFT JOIN care_staff cs ON cs.staff_id = c.staff_id
               WHERE c.patient_id = %s
               ORDER BY c.contacted_at DESC""",
            (patient_id,),
        )
        rows = cur.fetchall() or []
    return rows


# ─── Clinical Notes Append-Only (Feature D-16) ────────────────────────────────

class CreateNoteIn(BaseModel):
    note_type: str = "General"  # 'Review', 'Call', 'Plan_Change', 'General'
    note_text: str
    amends_note_id: Optional[int] = None


@app.get("/staff/patients/{patient_id}/notes")
def get_patient_notes(
    patient_id: int,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """D-16: Returns append-only clinical notes history."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT cn.note_id, cn.patient_id, cn.staff_id, cs.full_name AS author_name,
                      cs.staff_role AS author_role, cn.note_type, cn.note_text,
                      cn.amends_note_id, cn.created_at
               FROM clinician_notes cn
               LEFT JOIN care_staff cs ON cs.staff_id = cn.staff_id
               WHERE cn.patient_id = %s
               ORDER BY cn.created_at DESC""",
            (patient_id,),
        )
        return cur.fetchall() or []


@app.post("/staff/patients/{patient_id}/notes")
def add_patient_note(
    patient_id: int,
    body: CreateNoteIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-16: Create or amend a clinical note.
    Preserves author, timestamp, and link to amended note if applicable.
    """
    if not body.note_text or len(body.note_text.strip()) < 3:
        raise HTTPException(status_code=400, detail="Note text must have at least 3 characters")

    staff_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO clinician_notes (patient_id, staff_id, note_type, note_text, amends_note_id)
               VALUES (%s, %s, %s, %s, %s)""",
            (patient_id, staff_id, body.note_type, body.note_text.strip(), body.amends_note_id),
        )
        note_id = cur.lastrowid

        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Staff', %s, 'CLINICAL_NOTE_CREATED', 'clinician_note', %s,
                       JSON_OBJECT('patient_id', %s, 'note_type', %s, 'amends', %s))""",
            (str(staff_id), note_id, patient_id, body.note_type, body.amends_note_id),
        )
        conn.commit()

    return {"status": "created", "note_id": note_id, "patient_id": patient_id}


# ─── Audit Log Viewer (Feature D-17) ──────────────────────────────────────────

@app.get("/staff/audit-log")
def get_audit_log(
    patient_id: Optional[int] = None,
    staff_id: Optional[int] = None,
    action: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 150,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-17: Audit log viewer. Filter by patient, staff, action, date.
    Shows break-glass views, exports, acknowledgments, resolutions, approvals,
    rule changes, notes, and communications.
    """
    with get_conn() as conn, conn.cursor() as cur:
        query = """
            SELECT a.log_id, a.actor_type, a.actor_id, a.action, a.entity_type, a.entity_id,
                   a.details, a.created_at,
                   cs.full_name AS staff_name, cs.staff_role AS staff_role,
                   p.full_name AS patient_name, p.patient_code
            FROM audit_log a
            LEFT JOIN care_staff cs ON cs.staff_id = CAST(a.actor_id AS UNSIGNED) AND a.actor_type = 'Staff'
            LEFT JOIN patients p ON (
                (a.entity_type IN ('Patient', 'patient') AND p.patient_id = a.entity_id)
                OR (JSON_VALID(a.details) AND p.patient_id = CAST(JSON_UNQUOTE(JSON_EXTRACT(a.details, '$.patient_id')) AS UNSIGNED))
            )
            WHERE 1=1
        """
        params = []
        if patient_id is not None:
            query += " AND ((a.entity_type IN ('Patient', 'patient') AND a.entity_id = %s) OR (JSON_VALID(a.details) AND JSON_UNQUOTE(JSON_EXTRACT(a.details, '$.patient_id')) = %s))"
            params.extend([patient_id, str(patient_id)])
        if staff_id is not None:
            query += " AND a.actor_type = 'Staff' AND a.actor_id = %s"
            params.append(str(staff_id))
        if action:
            query += " AND a.action = %s"
            params.append(action)
        if start_date:
            query += " AND a.created_at >= %s"
            params.append(f"{start_date} 00:00:00")
        if end_date:
            query += " AND a.created_at <= %s"
            params.append(f"{end_date} 23:59:59")

        query += " ORDER BY a.created_at DESC LIMIT %s"
        params.append(min(limit, 500))

        cur.execute(query, tuple(params))
        rows = cur.fetchall() or []

        cur.execute("SELECT DISTINCT action FROM audit_log ORDER BY action ASC")
        distinct_actions = [r["action"] for r in (cur.fetchall() or []) if r.get("action")]

        cur.execute("SELECT staff_id, full_name, staff_role FROM care_staff ORDER BY full_name ASC")
        staff_list = cur.fetchall() or []

    for r in rows:
        det = r.get("details")
        if isinstance(det, str):
            try:
                r["details"] = json.loads(det)
            except Exception:
                pass

    return {
        "logs": rows,
        "actions": distinct_actions,
        "staff": staff_list,
        "total": len(rows),
    }


class ExportLogAuditIn(BaseModel):
    count: int = 0
    filters: Optional[Dict[str, Any]] = None


@app.post("/staff/audit-log/export-log")
def log_audit_export(
    body: ExportLogAuditIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-17: Logging audit log export event (compliance requirement).
    """
    staff_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Staff', %s, 'EXPORT_AUDIT_LOG', 'audit_log', NULL,
                       JSON_OBJECT('record_count', %s, 'filters', %s, 'exported_at', NOW()))""",
            (str(staff_id), body.count, json.dumps(body.filters or {})),
        )
        conn.commit()
    return {"status": "logged"}


# ─── Global Command Palette Search (Feature D-21) ────────────────────────────

@app.get("/staff/search")
def global_search(
    q: str = "",
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-21 Command Palette (Ctrl+K) search endpoint.
    Searches patients, active flags, tasks, and clinician notes.
    """
    term = (q or "").strip()
    if len(term) < 2:
        return {"patients": [], "flags": [], "tasks": [], "notes": []}

    pattern = f"%{term}%"
    with get_conn() as conn, conn.cursor() as cur:
        # 1. Patients
        cur.execute(
            """SELECT p.patient_id, p.patient_code, p.full_name, p.date_of_birth,
                      d.condition_summary
               FROM patients p
               LEFT JOIN discharge_records d ON d.patient_id = p.patient_id
               WHERE p.full_name LIKE %s OR p.patient_code LIKE %s
               LIMIT 8""",
            (pattern, pattern),
        )
        patients = cur.fetchall() or []

        # 2. Flags
        cur.execute(
            """SELECT f.flag_id, f.patient_id, f.reason, f.severity, f.status, f.created_at,
                      p.full_name, p.patient_code
               FROM flags f
               JOIN patients p ON p.patient_id = f.patient_id
               WHERE (f.reason LIKE %s OR p.full_name LIKE %s)
                 AND f.status IN ('Open', 'Acknowledged')
               ORDER BY f.created_at DESC
               LIMIT 8""",
            (pattern, pattern),
        )
        flags = cur.fetchall() or []

        # 3. Tasks
        cur.execute(
            """SELECT t.followup_id AS task_id, t.patient_id, t.reason AS task_description,
                      t.priority, t.status, t.due_at, p.full_name, p.patient_code
               FROM follow_up_tasks t
               JOIN patients p ON p.patient_id = t.patient_id
               WHERE (t.reason LIKE %s OR p.full_name LIKE %s)
                 AND t.status != 'Resolved'
               ORDER BY t.due_at ASC
               LIMIT 8""",
            (pattern, pattern),
        )
        tasks = cur.fetchall() or []

        # 4. Clinician Notes
        cur.execute(
            """SELECT cn.note_id, cn.patient_id, cn.note_type, cn.note_text, cn.created_at,
                      cs.full_name AS author_name, p.full_name, p.patient_code
               FROM clinician_notes cn
               JOIN patients p ON p.patient_id = cn.patient_id
               LEFT JOIN care_staff cs ON cs.staff_id = cn.staff_id
               WHERE cn.note_text LIKE %s OR p.full_name LIKE %s
               ORDER BY cn.created_at DESC
               LIMIT 8""",
            (pattern, pattern),
        )
        notes = cur.fetchall() or []

    return {
        "patients": patients,
        "flags": flags,
        "tasks": tasks,
        "notes": notes,
    }


# ─── Care Rules & Pathway Templates (Feature D-13) ───────────────────────────

class ApplyPathwayRuleIn(BaseModel):
    rule_type: str
    measurement_type: Optional[str] = None
    threshold_value: float
    window_hours: Optional[int] = None
    severity: str = "Review_Soon"


class ApplyPathwayIn(BaseModel):
    template_id: str
    rules: List[ApplyPathwayRuleIn]


class UpdateRuleIn(BaseModel):
    threshold_value: float
    window_hours: Optional[int] = None
    severity: Optional[str] = None
    change_reason: str


@app.get("/staff/pathway-templates")
def get_pathway_templates(
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-13: Return available clinical pathway templates with BLANK thresholds.
    The system ships zero default medical thresholds.
    """
    return {"templates": PATHWAY_TEMPLATES}


@app.post("/staff/patients/{pid}/apply-pathway")
def apply_pathway_template(
    pid: int,
    body: ApplyPathwayIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-13: Apply a pathway template to a patient.
    STRICT CLINICAL GOVERNANCE:
    - Only attending doctors can approve and apply clinical pathway templates (403 for nurses).
    - Every rule threshold must be filled by the doctor (no defaults or blanks).
    """
    user_role = user.get("role") or user.get("account_role")
    if user_role != "Doctor":
        raise HTTPException(
            status_code=403,
            detail="Clinical Governance Restriction: Only an attending doctor can approve and apply clinical pathway templates.",
        )

    if not body.rules or len(body.rules) == 0:
        raise HTTPException(status_code=400, detail="At least one clinical rule must be configured.")

    for r in body.rules:
        if r.threshold_value is None:
            raise HTTPException(
                status_code=400,
                detail=f"Blank threshold detected for {r.rule_type}. All clinical thresholds must be explicitly set by the doctor.",
            )

    doctor_id = user["staff_id"]
    template_name = next((t["name"] for t in PATHWAY_TEMPLATES if t["template_id"] == body.template_id), body.template_id)

    with get_conn() as conn, conn.cursor() as cur:
        # Verify patient exists
        cur.execute("SELECT patient_id FROM patients WHERE patient_id = %s", (pid,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Patient not found")

        created_rule_ids = []
        for r in body.rules:
            # Check if active rule already exists for patient and measurement
            cur.execute(
                """SELECT rule_id, threshold_value, window_hours, severity FROM alert_rules
                   WHERE patient_id = %s AND rule_type = %s
                     AND (measurement_type = %s OR (measurement_type IS NULL AND %s IS NULL))
                     AND is_active = 1 LIMIT 1""",
                (pid, r.rule_type, r.measurement_type, r.measurement_type),
            )
            existing_rule = cur.fetchone()

            if existing_rule:
                rule_id = existing_rule["rule_id"]
                old_val = {
                    "threshold_value": float(existing_rule["threshold_value"]),
                    "window_hours": existing_rule["window_hours"],
                    "severity": existing_rule["severity"],
                }
                cur.execute(
                    """UPDATE alert_rules
                       SET threshold_value = %s, window_hours = %s, severity = %s,
                           approved_by_staff_id = %s, approved_at = NOW(), is_active = 1
                       WHERE rule_id = %s""",
                    (r.threshold_value, r.window_hours, r.severity, doctor_id, rule_id),
                )
            else:
                old_val = {}
                cur.execute(
                    """INSERT INTO alert_rules (patient_id, rule_type, measurement_type, threshold_value,
                                              window_hours, severity, approved_by_staff_id, approved_at, is_active)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), 1)""",
                    (pid, r.rule_type, r.measurement_type, r.threshold_value, r.window_hours, r.severity, doctor_id),
                )
                rule_id = cur.lastrowid

            created_rule_ids.append(rule_id)

            # Record in alert_rules_history
            new_val = {
                "threshold_value": r.threshold_value,
                "window_hours": r.window_hours,
                "severity": r.severity,
                "rule_type": r.rule_type,
                "measurement_type": r.measurement_type,
            }
            cur.execute(
                """INSERT INTO alert_rules_history (rule_id, changed_by_staff_id, change_reason, old_values, new_values)
                   VALUES (%s, %s, %s, %s, %s)""",
                (rule_id, doctor_id, f"Pathway activation: {template_name}", json.dumps(old_val), json.dumps(new_val)),
            )

        # Audit log entry
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Staff', %s, 'APPLY_PATHWAY_TEMPLATE', 'patient', %s,
                       JSON_OBJECT('template_id', %s, 'rules_count', %s, 'doctor_id', %s))""",
            (str(doctor_id), pid, body.template_id, len(created_rule_ids), doctor_id),
        )
        conn.commit()

    return {
        "status": "applied",
        "applied": True,
        "template_id": body.template_id,
        "rules_created": len(created_rule_ids),
        "approved_by_doctor_id": doctor_id,
    }


@app.get("/staff/rules/{rule_id}/history")
def get_rule_history(
    rule_id: int,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """D-13: Return complete modification audit trail for an alert rule."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT h.history_id, h.rule_id, h.changed_by_staff_id, cs.full_name AS changed_by_name,
                      cs.staff_role AS changed_by_role, h.change_reason, h.old_values, h.new_values, h.changed_at
               FROM alert_rules_history h
               LEFT JOIN care_staff cs ON cs.staff_id = h.changed_by_staff_id
               WHERE h.rule_id = %s
               ORDER BY h.changed_at DESC, h.history_id DESC""",
            (rule_id,),
        )
        rows = cur.fetchall() or []

    for r in rows:
        for fld in ("old_values", "new_values"):
            if isinstance(r.get(fld), str):
                try:
                    r[fld] = json.loads(r[fld])
                except Exception:
                    r[fld] = {}
            elif not isinstance(r.get(fld), dict):
                r[fld] = {}
        r["old_threshold"] = (r.get("old_values") or {}).get("threshold_value")
        r["new_threshold"] = (r.get("new_values") or {}).get("threshold_value")
        r["approved_by_doctor"] = not (r.get("new_values") or {}).get("proposed_only", False)

    return {"rule_id": rule_id, "history": rows}


@app.post("/staff/rules/{rule_id}/update")
def update_alert_rule(
    rule_id: int,
    body: UpdateRuleIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-13: Update or propose an alert rule threshold.
    - Doctors apply changes directly with audit history.
    - Nurses submit proposed updates requiring doctor approval.
    """
    if not body.change_reason or len(body.change_reason.strip()) < 5:
        raise HTTPException(status_code=400, detail="A clinical justification of at least 5 characters is required.")

    staff_id = user["staff_id"]
    is_doctor = (user.get("role") or user.get("account_role")) == "Doctor"

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT rule_id, patient_id, threshold_value, window_hours, severity, is_active
               FROM alert_rules WHERE rule_id = %s""",
            (rule_id,),
        )
        current = cur.fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="Alert rule not found")

        old_val = {
            "threshold_value": float(current["threshold_value"]),
            "window_hours": current["window_hours"],
            "severity": current["severity"],
            "is_active": current["is_active"],
        }
        new_val = {
            "threshold_value": body.threshold_value,
            "window_hours": body.window_hours if body.window_hours is not None else current["window_hours"],
            "severity": body.severity or current["severity"],
            "is_active": current["is_active"],
            "proposed_only": not is_doctor,
        }

        if is_doctor:
            cur.execute(
                """UPDATE alert_rules
                   SET threshold_value = %s, window_hours = %s, severity = %s,
                       approved_by_staff_id = %s, approved_at = NOW()
                   WHERE rule_id = %s""",
                (new_val["threshold_value"], new_val["window_hours"], new_val["severity"], staff_id, rule_id),
            )
            action_desc = "RULE_UPDATED"
        else:
            action_desc = "RULE_CHANGE_PROPOSED"

        cur.execute(
            """INSERT INTO alert_rules_history (rule_id, changed_by_staff_id, change_reason, old_values, new_values)
               VALUES (%s, %s, %s, %s, %s)""",
            (rule_id, staff_id, body.change_reason.strip(), json.dumps(old_val), json.dumps(new_val)),
        )

        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Staff', %s, %s, 'alert_rule', %s,
                       JSON_OBJECT('reason', %s, 'is_doctor', %s, 'new_threshold', %s))""",
            (str(staff_id), action_desc, rule_id, body.change_reason.strip(), is_doctor, body.threshold_value),
        )
        conn.commit()

    return {
        "status": "updated" if is_doctor else "proposed",
        "rule_id": rule_id,
        "is_doctor_approved": is_doctor,
        "approved_by_doctor": is_doctor,
        "message": "Alert rule threshold updated successfully." if is_doctor else "Rule modification proposal submitted for doctor review.",
    }


# ─── Operational Insights (Feature D-14) ─────────────────────────────────────

@app.get("/staff/insights")
def get_operational_insights(
    date_range: str = "30d",    # '7d', '30d', '90d'
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-14: Operational insights dashboard.
    Returns metrics with transparent clinical definitions (NO outcome/readmission claims).
    """
    with get_conn() as conn:
        return compute_operational_insights(conn, date_range=date_range)


class ExportLogAuditIn(BaseModel):
    date_range: Optional[str] = "30d"
    count: Optional[int] = 0
    filters: Optional[Dict[str, Any]] = None


@app.post("/staff/insights/export-log")
def log_insights_export(
    body: ExportLogAuditIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """D-14: Compliance logging for insights metrics export."""
    staff_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Staff', %s, 'INSIGHTS_EXPORT', 'insights', NULL,
                       JSON_OBJECT('format', 'CSV', 'date_range', %s, 'count', %s, 'exported_at', NOW()))""",
            (str(staff_id), body.date_range or "30d", body.count or 0),
        )
        conn.commit()
    return {"status": "logged", "logged": True}


# ─── FHIR R4 Export (Feature D-19) ───────────────────────────────────────────

@app.get("/staff/patients/{pid}/fhir")
def get_patient_fhir_bundle(
    pid: int,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    D-19: Returns a standard-compliant FHIR R4 JSON Bundle for follow-up data.
    Audit logs the export operation per clinical data exchange compliance.
    """
    with get_conn() as conn, conn.cursor() as cur:
        try:
            bundle = build_fhir_r4_bundle(conn, pid)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Staff', %s, 'FHIR_EXPORT', 'patient', %s,
                       JSON_OBJECT('entries_count', %s, 'exported_at', NOW()))""",
            (str(user["staff_id"]), pid, bundle.get("total", 0)),
        )
        conn.commit()

    return bundle


# ─── LACE Score Context (Feature D-20) ────────────────────────────────────────

class RecordLaceIn(BaseModel):
    length_of_stay_days: int
    acute_admission: bool
    charlson_index: int
    ed_visits_6m: int


@app.get("/staff/patients/{pid}/lace")
def get_patient_lace(
    pid: int,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """D-20: Retrieve latest clinician-entered LACE context score for a patient."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT r.risk_context_id, r.patient_id, r.length_of_stay_days, r.acute_admission,
                      r.charlson_index, r.ed_visits_6m, r.entered_at,
                      cs.full_name AS entered_by_name
               FROM risk_context r
               LEFT JOIN care_staff cs ON cs.staff_id = r.entered_by_staff_id
               WHERE r.patient_id = %s
               ORDER BY r.entered_at DESC LIMIT 1""",
            (pid,),
        )
        latest = cur.fetchone()

    if not latest:
        # Default placeholder context
        return compute_lace_score(los_days=2, acute=True, charlson=1, ed_visits=0)

    res = compute_lace_score(
        los_days=latest["length_of_stay_days"],
        acute=bool(latest["acute_admission"]),
        charlson=latest["charlson_index"],
        ed_visits=latest["ed_visits_6m"],
    )
    res["entered_at"] = latest["entered_at"].isoformat() if isinstance(latest["entered_at"], datetime) else str(latest["entered_at"])
    res["entered_by_name"] = latest.get("entered_by_name")
    return res


@app.post("/staff/patients/{pid}/lace")
def record_patient_lace(
    pid: int,
    body: RecordLaceIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """D-20: Record clinician-entered LACE parameters and compute score."""
    staff_id = user["staff_id"]
    lace_calc = compute_lace_score(
        los_days=body.length_of_stay_days,
        acute=body.acute_admission,
        charlson=body.charlson_index,
        ed_visits=body.ed_visits_6m,
    )

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT patient_id FROM patients WHERE patient_id = %s", (pid,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Patient not found")

        cur.execute(
            """INSERT INTO risk_context (patient_id, entered_by_staff_id, length_of_stay_days,
                                       acute_admission, charlson_index, ed_visits_6m)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (pid, staff_id, body.length_of_stay_days, 1 if body.acute_admission else 0, body.charlson_index, body.ed_visits_6m),
        )
        rec_id = cur.lastrowid

        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Staff', %s, 'RECORD_LACE_CONTEXT', 'risk_context', %s,
                       JSON_OBJECT('patient_id', %s, 'score', %s))""",
            (str(staff_id), rec_id, pid, lace_calc["score"]),
        )
        conn.commit()

    lace_calc["risk_context_id"] = rec_id
    return lace_calc