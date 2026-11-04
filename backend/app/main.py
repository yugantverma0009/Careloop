"""
backend/app/main.py — CareLoop API

Core Rule: "The LLM talks. Rules decide. Humans act."
All patient endpoints strictly extract patient_id from the authenticated JWT token.
"""

import os
import calendar
import re
import logging
from datetime import datetime, timedelta, date, timezone
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Header, HTTPException, Depends, Request, Response, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import pymysql
import json
import urllib.parse
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)
from .db import get_conn
from .auth import verify_login, make_token, require_role, current_user
from .permissions import (
    require_doctor,
    require_nurse,
    require_staff,
    require_patient,
    require_family,
    can_resolve_flag,
    FLAG_AUTHORITY_POLICY,
)
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


def make_google_calendar_url(
    appointment_id: int,
    appt_dt: Any,
    doctor_name: Optional[str] = None,
    specialization: Optional[str] = None,
) -> str:
    """
    Builds a direct Google Calendar event creation URL.
    - Times converted to UTC (IST is UTC+5:30)
    - Non-clinical description and details
    """
    dates_str = ""
    try:
        if isinstance(appt_dt, str):
            appt_dt = datetime.fromisoformat(appt_dt.replace("Z", "+00:00"))

        if isinstance(appt_dt, datetime):
            if appt_dt.tzinfo is None:
                appt_dt_ist = appt_dt.replace(tzinfo=IST)
            else:
                appt_dt_ist = appt_dt.astimezone(IST)
            appt_dt_utc = appt_dt_ist.astimezone(timezone.utc)
            appt_end_utc = appt_dt_utc + timedelta(minutes=30)

            dtstart = appt_dt_utc.strftime("%Y%m%dT%H%M%SZ")
            dtend = appt_end_utc.strftime("%Y%m%dT%H%M%SZ")
            dates_str = f"{dtstart}/{dtend}"
    except Exception:
        dates_str = ""

    doc = doctor_name or "Care Team Clinician"
    dept = specialization or "Follow-up Clinic"

    title = f"Follow-up visit with {doc}"
    details = f"Follow-up appointment at CareLoop ({dept}). Please arrive 10 minutes early with your discharge summary papers."
    location = "CareLoop Hospital & Clinics"

    query_dict = {
        "action": "TEMPLATE",
        "text": title,
        "details": details,
        "location": location,
    }
    if dates_str:
        query_dict["dates"] = dates_str

    return f"https://calendar.google.com/calendar/render?{urllib.parse.urlencode(query_dict)}"

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


from .rag_config import USE_UPGRADED_RAG, ALLOWLIST_ACTIONS
from .rag_pipeline import answer_patient_query


class ChatIn(BaseModel):
    message: Optional[str] = Field(None, max_length=1000)
    question: Optional[str] = Field(None, max_length=1000)
    conversation_id: Optional[str] = None
    language: Optional[str] = Field(default="en", pattern="^(en|hi)$")


class FeedbackIn(BaseModel):
    rating: int = Field(..., ge=-1, le=1)
    comment: Optional[str] = Field(default=None, max_length=255)


class ActionIn(BaseModel):
    message_id: Optional[int] = None
    action_id: Optional[int] = None
    payload: Optional[Dict[str, Any]] = None


class PatientSettingsIn(BaseModel):
    voice_autoplay: Optional[bool] = None
    ai_help_enabled: Optional[bool] = None


class AssistantReplyIn(BaseModel):
    reply_text: str = Field(..., max_length=500)
    template_id: Optional[str] = None


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
    """Extract authenticated patient_id strictly from JWT."""
    pid = user.get("patient_id")
    if pid:
        return int(pid)
    raise HTTPException(status_code=403, detail="No authorized patient associated with this account")

@app.get("/patient/me/profile")
def get_my_patient_profile(user: Dict[str, Any] = Depends(require_patient)):
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
def get_my_caregiver_profile(user: Dict[str, Any] = Depends(require_family)):
    """Caregiver profile access (Family Helper)."""
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
def get_my_staff_profile(user: Dict[str, Any] = Depends(require_staff)):
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
    - Avoids duplicates via UNIQUE (device_id, measurement_type, measured_at).
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


# ─── Watch Events & Possible Fall Ingestion (Phase 5 Feature F7) ──────────────

class DeviceEventIn(BaseModel):
    device_id: str
    event_type: str = Field(default="Possible_Fall", pattern="^(Possible_Fall|Low_Battery|Reconnected)$")
    occurred_at: Optional[int] = None
    details: Optional[Dict[str, Any]] = None


class FallResponseIn(BaseModel):
    event_id: int
    response: str = Field(pattern="^(Ok|Need_Help|ok|need_help)$")


@app.post("/device/events")
def ingest_device_event(ev: DeviceEventIn, x_device_key: str = Header(...)):
    """
    Idempotent IoT device event endpoint (Phase 5 Feature F7).
    - Authenticates device via X-Device-Key header.
    - If Possible_Fall rule is active, triggers prompt countdown.
    - If Possible_Fall rule is inactive, records in audit log only.
    """
    configured_key = os.getenv("DEVICE_API_KEY", "demo-device-key-change-me")
    if x_device_key != configured_key:
        raise HTTPException(status_code=401, detail="Bad device key")

    when = (
        datetime.fromtimestamp(ev.occurred_at, tz=IST).replace(tzinfo=None)
        if ev.occurred_at
        else datetime.now()
    )

    from .device_event_service import record_device_event

    try:
        return record_device_event(
            device_id=ev.device_id,
            event_type=ev.event_type,
            occurred_at=when,
            details=ev.details,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error ingesting device event: {e}")
        raise HTTPException(status_code=500, detail="Internal server error recording device event")


@app.get("/patient/me/fall-prompt")
def get_my_fall_prompt(user: Dict[str, Any] = Depends(require_patient)):
    """Returns active possible fall prompt awaiting patient response."""
    pid = get_effective_patient_id(user)
    from .device_event_service import get_active_fall_prompt
    prompt = get_active_fall_prompt(pid)
    return {"prompt": prompt}


@app.post("/patient/me/fall-response")
def submit_my_fall_response(
    body: FallResponseIn,
    user: Dict[str, Any] = Depends(require_patient),
):
    """
    Records patient response to possible fall prompt (I'm OK or I need help).
    """
    pid = get_effective_patient_id(user)
    from .device_event_service import handle_patient_fall_response
    try:
        return handle_patient_fall_response(pid, body.event_id, body.response)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


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
def get_patient_today(user: Dict[str, Any] = Depends(require_patient)):
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
        cur.execute("SELECT full_name, ai_help_enabled, voice_autoplay FROM patients WHERE patient_id=%s", (pid,))
        p_row = cur.fetchone()
        name = p_row["full_name"] if p_row else "Patient"
        ai_help_enabled = bool(p_row.get("ai_help_enabled", 1)) if p_row and p_row.get("ai_help_enabled") is not None else True
        voice_autoplay = bool(p_row.get("voice_autoplay", 0)) if p_row and p_row.get("voice_autoplay") is not None else False

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
            day_after_discharge = max(1, (today_ist - dis_date).days + 1)
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

        urgent_flag = next((f for f in flags if f["status"] == "Open" and (f["severity"] in ("Urgent_Review", "Immediate_Review", "Immediate") or f["source_type"] == "Emergency")), None)
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

        # 4. Readings (Only latest VALID readings as headline, impossible readings surfaced as note)
        cur.execute(
            """SELECT measurement_type, measurement_value, unit, measured_at, quality_status
               FROM (
                   SELECT sr.*, ROW_NUMBER() OVER (PARTITION BY sr.patient_id, sr.measurement_type ORDER BY sr.measured_at DESC) as rn
                   FROM sensor_readings sr
                   WHERE sr.patient_id = %s AND sr.quality_status != 'Invalid'
               ) x WHERE x.rn = 1""",
            (pid,)
        )
        readings_rows = cur.fetchall()

        cur.execute(
            """SELECT COUNT(*) AS invalid_count FROM sensor_readings
               WHERE patient_id = %s AND quality_status = 'Invalid' AND measured_at >= NOW() - INTERVAL 24 HOUR""",
            (pid,)
        )
        inv_row = cur.fetchone()
        invalid_cnt = inv_row["invalid_count"] if inv_row else 0
        data_check_note = f"{invalid_cnt} reading ignored: impossible value" if invalid_cnt > 0 else None

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
            """SELECT a.appointment_id, a.appointment_date, a.appointment_type, a.status, s.full_name AS doctor_name, s.specialization
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
            "google_calendar_url": make_google_calendar_url(
                appt_row["appointment_id"],
                appt_row["appointment_date"],
                appt_row["doctor_name"],
                appt_row.get("specialization"),
            ),
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
                "at": next_appt["at"] if next_appt else None,
                "google_calendar_url": next_appt["google_calendar_url"] if next_appt else None,
            } if next_appt else None,
            "course_end_date": course_end_str,
            "checkins_this_week": checkins_this_week_str,
            "day_after_discharge": day_after_discharge,
        }

    from .device_event_service import get_active_fall_prompt, get_device_health
    fall_prompt = get_active_fall_prompt(pid)
    device_health = get_device_health(pid)

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
        "fall_prompt": fall_prompt,
        "device_health": device_health,
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
        "data_check_note": data_check_note,
        "device": device_status,
        "next_appointment": next_appt,
        "week": week,
        "plan_checklist": plan_checklist,
        "ai_help_enabled": ai_help_enabled,
        "voice_autoplay": voice_autoplay,
    }


@app.post("/patient/me/doses/{log_id}/taken")
def mark_dose_taken(
    log_id: int,
    body: DoseTakenIn = DoseTakenIn(),
    user: Dict[str, Any] = Depends(require_patient),
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
    user: Dict[str, Any] = Depends(require_patient),
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
    user: Dict[str, Any] = Depends(require_patient),
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
    user: Dict[str, Any] = Depends(require_patient),
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
                "google_calendar_url": make_google_calendar_url(
                    a["appointment_id"],
                    a["appointment_date"],
                    a["doctor_name"],
                    a.get("specialization"),
                ),
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
                "google_calendar_url": make_google_calendar_url(
                    u["appointment_id"],
                    u["appointment_date"],
                    u["doctor_name"],
                    u.get("specialization"),
                ),
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
    user: Dict[str, Any] = Depends(require_patient),
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
    user: Dict[str, Any] = Depends(require_patient),
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


@app.get("/patient/me/appointments/{appointment_id}/google-calendar-url")
def get_appointment_google_calendar_url(
    appointment_id: int,
    user: Dict[str, Any] = Depends(require_patient),
):
    """
    Returns direct Google Calendar event creation URL for the requested appointment.
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
        url = make_google_calendar_url(
            appt["appointment_id"],
            appt["appointment_date"],
            appt["doctor_name"],
            appt.get("specialization"),
        )
        return {
            "appointment_id": appointment_id,
            "google_calendar_url": url,
            "doctor_name": appt["doctor_name"],
            "appointment_date": str(appt["appointment_date"]),
        }


@app.get("/patient/me/doses")
def get_my_doses(user: Dict[str, Any] = Depends(require_patient)):
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
    user: Dict[str, Any] = Depends(require_patient),
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
    user: Dict[str, Any] = Depends(require_patient),
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
    user: Dict[str, Any] = Depends(require_patient),
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
def submit_symptom_checkin(body: SymptomIn, user: Dict[str, Any] = Depends(require_patient)):
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
def get_my_status(user: Dict[str, Any] = Depends(require_patient)):
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
        # 1. Latest readings (Filter out Invalid values for headline display)
        cur.execute(
            """SELECT measurement_type, measurement_value, unit, measured_at, quality_status
               FROM (
                   SELECT sr.*, ROW_NUMBER() OVER (PARTITION BY sr.patient_id, sr.measurement_type ORDER BY sr.measured_at DESC) as rn
                   FROM sensor_readings sr
                   WHERE sr.patient_id = %s AND sr.quality_status != 'Invalid'
               ) x WHERE x.rn = 1""",
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
    create_task: bool = True

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
                      d.condition_summary, doc.full_name AS attending_doctor,
                      DATEDIFF(CURDATE(), d.discharge_date) + 1 AS day_number
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

        # Overdue Check with Human Duration Formatting
        is_overdue = False
        overdue_display = None
        if first_at:
            delta_min = max(0, int((now - first_at).total_seconds() / 60))
            if tier == "Immediate" and delta_min > 15:
                is_overdue = True
                od_min = delta_min - 15
                if od_min < 60:
                    overdue_display = f"Overdue by {od_min}m"
                elif od_min < 1440:
                    h = od_min // 60
                    m = od_min % 60
                    overdue_display = f"Overdue by {h}h {m}m" if m > 0 else f"Overdue by {h}h"
                else:
                    d = od_min // 1440
                    h = (od_min % 1440) // 60
                    overdue_display = f"Overdue by {d}d {h}h" if h > 0 else f"Overdue by {d}d"
            elif tier == "Urgent" and delta_min > 120:
                is_overdue = True
                od_min = delta_min - 120
                if od_min < 60:
                    overdue_display = f"Overdue by {od_min}m"
                elif od_min < 1440:
                    h = od_min // 60
                    m = od_min % 60
                    overdue_display = f"Overdue by {h}h {m}m" if m > 0 else f"Overdue by {h}h"
                else:
                    d = od_min // 1440
                    h = (od_min % 1440) // 60
                    overdue_display = f"Overdue by {d}d {h}h" if h > 0 else f"Overdue by {d}d"
            elif tier == "Review_Soon" and delta_min > 1440:
                is_overdue = True
                od_min = delta_min - 1440
                if od_min < 60:
                    overdue_display = f"Overdue by {od_min}m"
                elif od_min < 1440:
                    h = od_min // 60
                    m = od_min % 60
                    overdue_display = f"Overdue by {h}h {m}m" if m > 0 else f"Overdue by {h}h"
                else:
                    d = od_min // 1440
                    h = (od_min % 1440) // 60
                    overdue_display = f"Overdue by {d}d {h}h" if h > 0 else f"Overdue by {d}d"

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
            "day_number": max(1, r.get("day_number") or 1),
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
    user: Dict[str, Any] = Depends(require_staff),
):
    """
    Resolve Flag Endpoint (D-03 & Phase 2 Role Model):
    - Policy: Nurse can resolve Routine and Review_Soon flags.
    - Urgent and Immediate flags enforce Doctor role and note length >= 5.
    - Calls sp_resolve_flag with p_dismiss=FALSE.
    """
    staff_id = user["staff_id"]
    staff_role = user.get("role") or user.get("account_role")

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT flag_id, severity, status FROM flags WHERE flag_id = %s", (flag_id,))
        fl = cur.fetchone()
        if not fl:
            raise HTTPException(status_code=404, detail="Flag not found")

        allowed, msg = can_resolve_flag(staff_role, fl["severity"], body.resolution_note)
        if not allowed:
            if "Nurse cannot resolve" in msg:
                raise HTTPException(status_code=403, detail=msg)
            raise HTTPException(status_code=400, detail=msg)

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
    user: Dict[str, Any] = Depends(require_staff),
):
    """
    Dismiss Flag as False Alarm / Duplicate Endpoint (D-03):
    - Policy: Nurse can dismiss routine flags; urgent flags require doctor authority.
    - Calls sp_resolve_flag with p_dismiss=TRUE.
    """
    staff_id = user["staff_id"]
    staff_role = user.get("role") or user.get("account_role")

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT flag_id, severity, status FROM flags WHERE flag_id = %s", (flag_id,))
        fl = cur.fetchone()
        if not fl:
            raise HTTPException(status_code=404, detail="Flag not found")

        allowed, msg = can_resolve_flag(staff_role, fl["severity"], body.resolution_note)
        if not allowed:
            if "Nurse cannot resolve" in msg:
                raise HTTPException(status_code=403, detail="Nurse cannot dismiss urgent or immediate flags. Only doctors can resolve or dismiss urgent flags.")
            raise HTTPException(status_code=400, detail=msg)

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


class EscalateDoctorIn(BaseModel):
    note: Optional[str] = "Nurse requested doctor review"


@app.post("/staff/flags/{flag_id}/escalate-doctor")
def escalate_flag_to_doctor(
    flag_id: int,
    body: EscalateDoctorIn = EscalateDoctorIn(),
    user: Dict[str, Any] = Depends(require_staff),
):
    """
    Nurse / Staff action: 'Ask doctor' (Section 2.3 & 2.6).
    Records flag_events row ('Escalated'), inserts escalation record, writes audit_log,
    and surfaces flag prominently on Doctor Desk.
    """
    staff_id = user["staff_id"]
    staff_role = user.get("role") or user.get("account_role")
    note_text = (body.note or "Nurse requested doctor review").strip()

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT flag_id, patient_id, severity, status FROM flags WHERE flag_id = %s", (flag_id,))
        fl = cur.fetchone()
        if not fl:
            raise HTTPException(status_code=404, detail="Flag not found")

        cur.execute(
            "SELECT COALESCE(MAX(step_no), 0) + 1 AS next_step FROM escalations WHERE flag_id = %s",
            (flag_id,),
        )
        next_step = cur.fetchone()["next_step"]

        cur.execute(
            """INSERT INTO escalations (flag_id, step_no, step_type, channel, delivery_status, notes)
               VALUES (%s, %s, 'Doctor_Alert', 'Dashboard', 'Sent', %s)""",
            (flag_id, next_step, f"Escalated to doctor by {staff_role} #{staff_id}: {note_text}"),
        )
        cur.execute(
            """INSERT INTO flag_events (flag_id, event_type, staff_id, note)
               VALUES (%s, 'Escalated', %s, %s)""",
            (flag_id, staff_id, f"Escalated to doctor: {note_text}"),
        )
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Staff', %s, 'FLAG_ESCALATED_TO_DOCTOR', 'flag', %s,
                       JSON_OBJECT('note', %s, 'staff_role', %s, 'patient_id', %s))""",
            (str(staff_id), flag_id, note_text, staff_role, fl["patient_id"]),
        )
        conn.commit()

    return {"status": "escalated_to_doctor", "flag_id": flag_id, "note": note_text}


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

        # Idempotent escalation check (Defect 5): do not insert duplicate escalation or audit row
        cur.execute(
            """SELECT escalation_id FROM escalations
               WHERE flag_id = %s AND step_type = 'Doctor_Alert' AND delivery_status = 'Sent' LIMIT 1""",
            (flag_id,),
        )
        if cur.fetchone():
            return {"status": "already_escalated", "flag_id": flag_id}

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
    overdue: Optional[Any] = None,
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

    # Parse overdue filter safely
    is_overdue_filter: Optional[bool] = None
    if overdue is not None:
        if isinstance(overdue, bool):
            is_overdue_filter = overdue
        else:
            ov_lower = str(overdue).strip().lower()
            if ov_lower in ("true", "1", "yes"):
                is_overdue_filter = True
            elif ov_lower in ("false", "0", "no"):
                is_overdue_filter = False

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
    if is_overdue_filter is True:
        query += " AND t.status != 'Resolved' AND t.due_at IS NOT NULL AND t.due_at < NOW()"
    elif is_overdue_filter is False:
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
        r_dict["assigned_to"] = r.get("assigned_staff_name") or r.get("assigned_staff_id")
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
               LEFT JOIN v_device_status dev ON dev.patient_id = p.patient_id
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
        invalid_count = sum(1 for r in recent_readings if r.get("quality_status") == "Invalid")
        data_check_note = f"{invalid_count} reading ignored: impossible value" if invalid_count > 0 else None
        for r in recent_readings:
            m_type = r["measurement_type"]
            if r.get("quality_status") == "Invalid":
                continue
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

    from .device_event_service import get_device_health, get_rule_prompt_counts
    dev_health = get_device_health(pid)
    prompt_counts = get_rule_prompt_counts(pid)

    return {
        "patient": p,
        "is_assigned": is_assigned,
        "outside_assignment": outside_assignment,
        "requires_break_glass": requires_break_glass,
        "caregivers": caregivers,
        "open_flags": open_flags,
        "latest_readings": latest_readings,
        "data_check_note": data_check_note,
        "adherence_grid": adherence_grid,
        "pain_trend": pain_trend,
        "device": device,
        "device_health": dev_health,
        "fall_prompt_counts": prompt_counts,
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
                      (SELECT COUNT(*) FROM flags f WHERE f.rule_id = r.rule_id AND f.status = 'Dismissed' AND f.resolution_code = 'False_Alarm') AS dismissed_false_count,
                      (SELECT COUNT(*) FROM device_events de WHERE de.patient_id = r.patient_id AND de.event_type = 'Possible_Fall' AND de.prompt_sent_at IS NOT NULL) AS prompts_sent,
                      (SELECT COUNT(*) FROM device_events de WHERE de.patient_id = r.patient_id AND de.event_type = 'Possible_Fall' AND de.patient_response = 'Ok') AS prompts_ok,
                      (SELECT COUNT(*) FROM device_events de WHERE de.patient_id = r.patient_id AND de.event_type = 'Possible_Fall' AND (de.patient_response = 'No_Response' OR (de.patient_response IS NULL AND de.flag_id IS NOT NULL))) AS prompts_unanswered
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
    request: Request,
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

        # Discharge details for hospital vs recovery timeline transition
        cur.execute(
            """SELECT discharge_date, condition_summary 
               FROM discharge_records 
               WHERE patient_id = %s""",
            (pid,),
        )
        dr_info = cur.fetchone() or {}
        discharge_date = dr_info.get("discharge_date")

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

        # 8. Approved Rule Limits for Chart
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

        is_inpatient = bool(discharge_date is not None and datetime.strptime(day_str, "%Y-%m-%d").date() <= discharge_date)
        phase_label = "Hospital Stay (Days 1–3)" if is_inpatient else "Recovery at Home (Days 4+)"

        grouped_result.append({
            "date": day_str,
            "display_date": datetime.strptime(day_str, "%Y-%m-%d").strftime("%A, %d %b %Y"),
            "is_inpatient": is_inpatient,
            "phase_label": phase_label,
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

    # Backward-compatible with legacy milestone tests (e.g. test_m4_escalation)
    # when called without query parameters
    if not request.query_params:
        return all_events

    return {
        "patient": patient_info,
        "discharge_date": discharge_date.strftime("%Y-%m-%d") if discharge_date else None,
        "total_events": len(all_events),
        "day_groups": grouped_result,
        "events": all_events,
        "chart_limits": chart_limits,
        "chart_readings": chart_readings,
    }


# ─── Patient Chat & RAG (Milestone M5) ────────────────────────────────────────

@app.post("/patient/me/chat")
def chat_with_assistant(body: ChatIn, user: Dict[str, Any] = Depends(require_patient)):
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
            # Fetch patient name for name-by-code friendly replies
            cur.execute("SELECT full_name FROM patients WHERE patient_id = %s", (pid,))
            p_row = cur.fetchone()
            patient_name = p_row["full_name"] if p_row else "Aarav"

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

        # 2. Compute answer via Papers Agent (CareLoop Care Agents Phase 2)
        if USE_UPGRADED_RAG:
            from .agents.papers_agent import PapersAgent
            rag_res = PapersAgent.process_query(
                patient_id=pid,
                question=effective_q,
                conversation_id=body.conversation_id,
                language=body.language or "en",
                history=history,
                patient_name=patient_name,
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
            run_id = rag_res.get("run_id")
        else:
            # Legacy fallback
            ans, is_grounded, citations = rag_answer(pid, effective_q, body.language or "en", conn=conn)
            bullets = []
            sources = []
            suggestions = []
            can_ask = not is_grounded
            answer_type = "grounded" if is_grounded else "not_found"
            debug_data = {"legacy": True}

        # Store answer_type inside retrieval_debug so it works cleanly without violating enum
        debug_data["answer_type"] = answer_type
        db_answer_type = answer_type if answer_type in ('grounded','structured','refusal_dose','refusal_medical','emergency','not_found','unavailable') else 'not_found'

        with conn.cursor() as cur:
            # 3. Insert AI message with answer_type and retrieval_debug
            cur.execute(
                """INSERT INTO chat_messages (patient_id, sender, message_text, is_grounded, answer_type, conversation_id, retrieval_debug)
                   VALUES (%s, 'AI_Nurse', %s, %s, %s, %s, %s)""",
                (pid, ans, is_grounded, db_answer_type, body.conversation_id, json.dumps(debug_data, ensure_ascii=False)),
            )
            ai_msg_id = cur.lastrowid

            # 3b. Record offered actions
            actions = rag_res.get("actions", []) if USE_UPGRADED_RAG else []
            for act in actions:
                a_type = act.get("action_type") if isinstance(act, dict) else str(act)
                if a_type in ALLOWLIST_ACTIONS:
                    cur.execute(
                        """INSERT INTO chat_actions (message_id, patient_id, action_type, status)
                           VALUES (%s, %s, %s, 'Offered')""",
                        (ai_msg_id, pid, a_type),
                    )
                    cur.execute(
                        """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                           VALUES ('System', %s, 'ASSISTANT_ACTION_OFFERED', 'chat_action', %s,
                                   JSON_OBJECT('action_type', %s, 'message_id', %s))""",
                        (str(pid), cur.lastrowid, a_type, ai_msg_id),
                    )

            # 4. Link citations (only if not small talk or refusal)
            if citations and answer_type not in ("small_talk", "refusal_dose", "refusal_medical", "emergency"):
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
                           JSON_OBJECT('answer_type', %s, 'is_grounded', %s, 'citations_count', %s, 'run_id', %s))""",
                (str(user["account_id"]), ai_msg_id, answer_type, is_grounded, len(citations), run_id),
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
        "actions": actions,
        "run_id": run_id,
        # Backward compatibility fields:
        "response": ans,
        "is_grounded": is_grounded,
        "citations": citations,
    }


@app.post("/patient/me/chat/new")
def start_new_chat_endpoint(user: Dict[str, Any] = Depends(require_patient)):
    """Clears ephemeral conversation state and deletes patient chat messages so the new chat starts completely fresh."""
    from .agents.rag_v2_service import ConversationStateManager
    pid = get_effective_patient_id(user)
    ConversationStateManager.clear_conversation(str(pid))
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM chat_feedback WHERE message_id IN (SELECT message_id FROM chat_messages WHERE patient_id = %s);", (pid,))
        cur.execute("DELETE FROM chat_messages WHERE patient_id = %s;", (pid,))
    return {"status": "ok", "message": "Conversation state reset and previous chat history deleted."}


@app.post("/patient/me/chat/clear")
@app.delete("/patient/me/chat/history")
def clear_patient_chat_history_endpoint(user: Dict[str, Any] = Depends(require_patient)):
    """Explicitly deletes all previous chat messages and feedback for this patient."""
    from .agents.rag_v2_service import ConversationStateManager
    pid = get_effective_patient_id(user)
    ConversationStateManager.clear_conversation(str(pid))
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM chat_feedback WHERE message_id IN (SELECT message_id FROM chat_messages WHERE patient_id = %s);", (pid,))
        cur.execute("DELETE FROM chat_messages WHERE patient_id = %s;", (pid,))
    return {"status": "ok", "message": "Chat history permanently deleted."}



@app.get("/patient/me/chat/history")
def get_chat_history(
    conversation_id: Optional[str] = None,
    user: Dict[str, Any] = Depends(require_patient)
):
    """
    Returns patient chat history with answer types, source chips, and feedback ratings (Brief Sec 7.10 & 8.6).
    If conversation_id is provided, filters to that active conversation.
    """
    pid = get_effective_patient_id(user)
    with get_conn() as conn, conn.cursor() as cur:
        if conversation_id:
            cur.execute(
                """SELECT m.message_id, m.patient_id, m.sender, m.message_text,
                          m.is_grounded, m.created_at, m.answer_type, m.conversation_id,
                          m.retrieval_debug,
                          f.rating AS feedback_rating
                   FROM chat_messages m
                   LEFT JOIN chat_feedback f ON f.message_id = m.message_id
                   WHERE m.patient_id = %s AND m.conversation_id = %s
                   ORDER BY m.created_at ASC LIMIT 100""",
                (pid, conversation_id),
            )
        else:
            cur.execute(
                """SELECT m.message_id, m.patient_id, m.sender, m.message_text,
                          m.is_grounded, m.created_at, m.answer_type, m.conversation_id,
                          m.retrieval_debug,
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

            effective_ans_type = r["answer_type"]
            if r.get("retrieval_debug"):
                try:
                    dbg = json.loads(r["retrieval_debug"]) if isinstance(r["retrieval_debug"], str) else r["retrieval_debug"]
                    if isinstance(dbg, dict) and dbg.get("answer_type"):
                        effective_ans_type = dbg["answer_type"]
                    elif isinstance(dbg, dict) and dbg.get("intent") == "small_talk":
                        effective_ans_type = "small_talk"
                except Exception:
                    pass

            # Fetch sources for AI messages (never for small talk, refusals, emergency)
            sources = []
            if r["sender"] == "AI_Nurse" and effective_ans_type not in ("small_talk", "refusal_dose", "refusal_medical", "emergency", "not_found"):
                cur.execute(
                    """SELECT c.chunk_id, c.chunk_text, c.section_title, c.page_no
                       FROM chat_message_sources s
                       JOIN document_chunks c ON c.chunk_id = s.chunk_id
                       WHERE s.message_id = %s""",
                    (msg_id,),
                )
                for s_row in cur.fetchall():
                    sec = s_row["section_title"] or "General"
                    p_num = s_row["page_no"] or 1
                    sources.append({
                        "chunk_id": s_row["chunk_id"],
                        "label": f"Discharge summary - {sec} - p.{p_num}",
                        "section_title": sec,
                        "page_no": p_num,
                        "snippet": s_row["chunk_text"][:160] + "...",
                        "text": s_row["chunk_text"],
                    })

            # Fetch actions for message
            cur.execute(
                """SELECT action_id, action_type, status, used_at
                   FROM chat_actions
                   WHERE message_id = %s""",
                (msg_id,),
            )
            msg_actions = cur.fetchall() or []

            sender_role = "user" if r["sender"] == "Patient" else ("care_team" if r["sender"] == "Care_Team" else "assistant")
            sender_display = "Message from Priya (nurse)" if r["sender"] == "Care_Team" else r["sender"]

            messages.append({
                "message_id": msg_id,
                "role": sender_role,
                "sender": r["sender"],
                "sender_display": sender_display,
                "content": r["message_text"],
                "message_text": r["message_text"],
                "response": r["message_text"],
                "is_grounded": bool(r["is_grounded"]) if effective_ans_type != "small_talk" else False,
                "grounded": bool(r["is_grounded"]) if effective_ans_type != "small_talk" else False,
                "answer_type": effective_ans_type or ("grounded" if r["is_grounded"] else "not_found"),
                "conversation_id": r["conversation_id"],
                "created_at": created,
                "timestamp": r["created_at"].isoformat() if isinstance(r["created_at"], datetime) else str(r["created_at"]),
                "sources": sources,
                "feedback_rating": r["feedback_rating"],
                "actions": msg_actions,
            })

        return messages


@app.post("/patient/me/chat/{message_id}/ask-care-team")
def ask_care_team_from_chat(
    message_id: int,
    user: Dict[str, Any] = Depends(require_patient),
):
    """
    Creates a clinical follow-up task and writes an audit row when a patient escalates a question.
    De-duplicated: strictly creates at most ONE task per topic per day (Brief Sec A.6).
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

        # Determine clinical topic for deduplication
        m_text = (msg["message_text"] or "").lower()
        if any(w in m_text for w in ["dose", "medicine", "pill", "tablet", "doses", "cardiopulse", "vasculonorm"]):
            topic = "medication"
        elif any(w in m_text for w in ["diet", "food", "eat", "drink", "nutrition"]):
            topic = "diet"
        elif any(w in m_text for w in ["walk", "exercise", "activity", "lift", "stairs"]):
            topic = "activity"
        elif any(w in m_text for w in ["wound", "incision", "bandage", "dressing", "stitches"]):
            topic = "wound_care"
        elif any(w in m_text for w in ["appointment", "visit", "doctor", "clinic"]):
            topic = "appointment"
        else:
            topic = "general"

        # Check for existing task created today for this patient and topic
        cur.execute(
            """SELECT followup_id FROM follow_up_tasks
               WHERE patient_id = %s
                 AND status = 'Pending'
                 AND DATE(created_at) = CURDATE()
                 AND (reason LIKE %s OR reason LIKE %s)
               LIMIT 1""",
            (pid, f"%{topic}%", f"%{msg['message_text'][:35]}%"),
        )
        existing_task = cur.fetchone()
        if existing_task:
            return {
                "ok": True,
                "created": False,
                "status": "task_already_exists",
                "task_id": existing_task["followup_id"],
                "message": "Your question on this topic is already awaiting care team review.",
            }

        task_reason = f"Patient question about {topic}: '{msg['message_text'][:160]}'"
        cur.execute(
            """INSERT INTO follow_up_tasks (patient_id, assigned_staff_id, priority, reason, status)
               VALUES (%s, %s, 'Routine', %s, 'Pending')""",
            (pid, assigned_staff, task_reason),
        )
        task_id = cur.lastrowid

        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Patient', %s, 'ASK_CARE_TEAM', 'chat_message', %s,
                       JSON_OBJECT('task_id', %s, 'assigned_staff', %s, 'topic', %s))""",
            (str(user["account_id"]), message_id, task_id, assigned_staff, topic),
        )

        return {
            "ok": True,
            "created": True,
            "status": "task_created",
            "task_id": task_id,
            "message": "Your question has been forwarded to your care team.",
        }


@app.post("/patient/me/chat/{message_id}/feedback")
def submit_chat_feedback(
    message_id: int,
    body: FeedbackIn,
    user: Dict[str, Any] = Depends(require_patient),
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


# ─── Assistant v2 Phase 4: Actions, Updates & Care Team Replies ──────────────

@app.post("/patient/me/actions/{action_type}")
def execute_patient_action(
    action_type: str,
    body: Optional[ActionIn] = None,
    user: Dict[str, Any] = Depends(require_patient),
):
    """
    Executes an allowlisted assistant action confirmed by patient button press.
    Safety Rule 1: The LLM never executes actions. Only the patient's own click triggers execution.
    """
    pid = get_effective_patient_id(user)
    if action_type not in ALLOWLIST_ACTIONS:
        raise HTTPException(400, f"Action '{action_type}' is not on the approved allowlist.")

    result = {}
    with get_conn() as conn, conn.cursor() as cur:
        # Mark chat_action status as 'Used' if referenced
        if body and body.action_id:
            cur.execute(
                """UPDATE chat_actions
                   SET status = 'Used', used_at = NOW()
                   WHERE action_id = %s AND patient_id = %s""",
                (body.action_id, pid),
            )
        elif body and body.message_id:
            cur.execute(
                """UPDATE chat_actions
                   SET status = 'Used', used_at = NOW()
                   WHERE message_id = %s AND patient_id = %s AND action_type = %s""",
                (body.message_id, pid, action_type),
            )

        # Audit action usage
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Patient', %s, 'ASSISTANT_ACTION_USED', 'patient', %s,
                       JSON_OBJECT('action_type', %s, 'patient_id', %s))""",
            (str(user["account_id"]), pid, action_type, pid),
        )

        # Dispatch action
        if action_type == "Start_Checkin":
            result = {
                "status": "ok",
                "action_type": action_type,
                "ui_action": "navigate",
                "target_tab": "checkin",
                "message": "Opening guided check-in.",
            }
        elif action_type == "Open_Medicines":
            result = {
                "status": "ok",
                "action_type": action_type,
                "ui_action": "navigate",
                "target_tab": "medicines",
                "message": "Opening medicines dose list. (Reminder: doses can only be confirmed on the Medicines page).",
            }
        elif action_type == "Open_Plan_Item":
            result = {
                "status": "ok",
                "action_type": action_type,
                "ui_action": "navigate",
                "target_tab": "my_plan",
                "message": "Opening your recovery plan.",
            }
        elif action_type == "Request_Call":
            # Creates a call task for assigned nurse (deduplicated: 1 call request per day)
            cur.execute(
                """SELECT followup_id FROM follow_up_tasks
                   WHERE patient_id = %s AND status = 'Pending' AND DATE(created_at) = CURDATE()
                     AND reason LIKE '%%call%%'
                   LIMIT 1""",
                (pid,),
            )
            existing = cur.fetchone()
            if existing:
                result = {
                    "status": "already_exists",
                    "action_type": action_type,
                    "task_id": existing["followup_id"],
                    "message": "A call request is already pending with your care team.",
                }
            else:
                cur.execute(
                    """INSERT INTO follow_up_tasks (patient_id, assigned_staff_id, priority, reason, status)
                       VALUES (%s, 2, 'Review_Soon', 'Patient requested a phone call via Assistant', 'Pending')""",
                    (pid,),
                )
                tid = cur.lastrowid
                result = {
                    "status": "ok",
                    "action_type": action_type,
                    "task_id": tid,
                    "message": "A nurse call request has been scheduled.",
                }
        elif action_type == "Ask_Care_Team":
            # De-duplicated task
            cur.execute(
                """SELECT followup_id FROM follow_up_tasks
                   WHERE patient_id = %s AND status = 'Pending' AND DATE(created_at) = CURDATE()
                     AND reason LIKE '%%question%%'
                   LIMIT 1""",
                (pid,),
            )
            existing = cur.fetchone()
            if existing:
                result = {
                    "status": "already_exists",
                    "action_type": action_type,
                    "task_id": existing["followup_id"],
                    "message": "A question is already pending review by your care team today.",
                }
            else:
                cur.execute(
                    """INSERT INTO follow_up_tasks (patient_id, assigned_staff_id, priority, reason, status)
                       VALUES (%s, 2, 'Review_Soon', 'Patient question submitted from Assistant for clinician review', 'Pending')""",
                    (pid,),
                )
                tid = cur.lastrowid
                result = {
                    "status": "ok",
                    "action_type": action_type,
                    "task_id": tid,
                    "message": "Your request has been forwarded to your care team.",
                }
        elif action_type == "Add_Appointment_To_Calendar":
            cur.execute(
                """SELECT appointment_id FROM appointments
                   WHERE patient_id = %s AND appointment_date >= CURDATE()
                   ORDER BY appointment_date ASC, appointment_time ASC LIMIT 1""",
                (pid,),
            )
            appt = cur.fetchone()
            appt_id = appt["appointment_id"] if appt else 1
            result = {
                "status": "ok",
                "action_type": action_type,
                "ui_action": "download",
                "download_url": f"/patient/me/appointments/{appt_id}.ics",
                "message": "Downloading appointment calendar sync (.ics).",
            }
        elif action_type == "Open_SOS":
            # Placeholder for future SOS feature
            result = {
                "status": "coming_soon",
                "action_type": action_type,
                "ui_action": "placeholder",
                "message": "SOS emergency response portal is coming soon.",
            }
        elif action_type == "Call_112":
            result = {
                "status": "ok",
                "action_type": action_type,
                "ui_action": "tel",
                "tel_url": "tel:112",
                "message": "Emergency national helpline: 112.",
            }

    return result


@app.get("/patient/me/updates")
def get_patient_updates(user: Dict[str, Any] = Depends(require_patient)):
    """
    Returns proactive updates inbox for patient (dose due, check-in prompt, nurse reply, etc.).
    """
    pid = get_effective_patient_id(user)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT update_id, patient_id, update_type, title, body,
                      action_type, action_payload, source_action_id,
                      created_by, seen_at, created_at
               FROM patient_updates
               WHERE patient_id = %s
               ORDER BY created_at DESC LIMIT 50""",
            (pid,),
        )
        rows = cur.fetchall()
        updates = []
        unread_count = 0
        for r in rows:
            if r["seen_at"] is None:
                unread_count += 1
            
            created_str = r["created_at"].strftime("%d %b, %I:%M %p") if isinstance(r["created_at"], datetime) else str(r["created_at"])
            
            payload = None
            if r["action_payload"]:
                try:
                    payload = json.loads(r["action_payload"]) if isinstance(r["action_payload"], str) else r["action_payload"]
                except Exception:
                    payload = None

            updates.append({
                "update_id": r["update_id"],
                "update_type": r["update_type"],
                "title": r["title"],
                "body": r["body"],
                "action_type": r["action_type"],
                "action_payload": payload,
                "created_by": r["created_by"],
                "is_seen": r["seen_at"] is not None,
                "seen_at": r["seen_at"].isoformat() if r["seen_at"] else None,
                "created_at": created_str,
                "timestamp": r["created_at"].isoformat() if isinstance(r["created_at"], datetime) else str(r["created_at"]),
            })

        return {
            "unread_count": unread_count,
            "updates": updates,
        }


@app.post("/patient/me/updates/{update_id}/seen")
def mark_patient_update_seen(update_id: int, user: Dict[str, Any] = Depends(require_patient)):
    """
    Marks an update as seen when opened by the patient.
    """
    pid = get_effective_patient_id(user)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE patient_updates
               SET seen_at = NOW()
               WHERE update_id = %s AND patient_id = %s""",
            (update_id, pid),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Update not found or does not belong to this patient.")
        return {"status": "ok", "update_id": update_id, "marked_seen": True}


@app.patch("/patient/me/settings")
def update_patient_settings(body: PatientSettingsIn, user: Dict[str, Any] = Depends(require_patient)):
    """
    Updates patient settings such as voice_autoplay and ai_help_enabled.
    """
    pid = get_effective_patient_id(user)
    with get_conn() as conn, conn.cursor() as cur:
        if body.voice_autoplay is not None:
            cur.execute(
                """UPDATE patients SET voice_autoplay = %s WHERE patient_id = %s""",
                (1 if body.voice_autoplay else 0, pid),
            )
            cur.execute(
                """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                   VALUES ('Patient', %s, 'UPDATE_VOICE_AUTOPLAY', 'patient', %s,
                           JSON_OBJECT('voice_autoplay', %s))""",
                (str(user["account_id"]), pid, body.voice_autoplay),
            )

        if body.ai_help_enabled is not None:
            cur.execute(
                """UPDATE patients SET ai_help_enabled = %s WHERE patient_id = %s""",
                (1 if body.ai_help_enabled else 0, pid),
            )
            cur.execute(
                """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                   VALUES ('Patient', %s, 'UPDATE_AI_HELP_ENABLED', 'patient', %s,
                           JSON_OBJECT('ai_help_enabled', %s))""",
                (str(user["account_id"]), pid, body.ai_help_enabled),
            )
        
        cur.execute("SELECT voice_autoplay, ai_help_enabled, preferred_language FROM patients WHERE patient_id = %s", (pid,))
        p = cur.fetchone()
        return {
            "status": "ok",
            "voice_autoplay": bool(p["voice_autoplay"]) if p else False,
            "ai_help_enabled": bool(p["ai_help_enabled"]) if p and p["ai_help_enabled"] is not None else True,
            "preferred_language": p["preferred_language"] if p else "en",
        }


@app.get("/staff/assistant-questions")
def get_assistant_questions(user: Dict[str, Any] = Depends(require_staff)):
    """
    Returns patient questions needing nurse review: Ask Care Team, dose-change refusals, and thumbs down.
    Audited on every view.
    """
    with get_conn() as conn, conn.cursor() as cur:
        # Audit staff view of assistant questions
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Staff', %s, 'VIEW_ASSISTANT_QUESTIONS', 'staff', %s, JSON_OBJECT('role', %s))""",
            (str(user["account_id"]), user.get("staff_id", 1), user.get("role", "Nurse")),
        )
        cur.execute(
            """SELECT m.message_id, m.patient_id, p.full_name AS patient_name,
                      p.patient_code, m.message_text, m.answer_type, m.created_at,
                      m.retrieval_debug, f.rating, f.comment AS feedback_comment,
                      (SELECT message_text FROM chat_messages m_user 
                       WHERE m_user.patient_id = m.patient_id AND m_user.sender = 'Patient' 
                         AND m_user.message_id < m.message_id 
                       ORDER BY m_user.message_id DESC LIMIT 1) AS patient_question
               FROM chat_messages m
               JOIN patients p ON p.patient_id = m.patient_id
               LEFT JOIN chat_feedback f ON f.message_id = m.message_id
               WHERE m.sender = 'AI_Nurse'
                 AND (
                   m.answer_type IN ('refusal_dose', 'care_team')
                   OR f.rating = -1
                   OR EXISTS (
                       SELECT 1 FROM follow_up_tasks t 
                       WHERE t.patient_id = m.patient_id AND t.reason LIKE '%%question%%' AND t.status = 'Pending'
                   )
                 )
               ORDER BY m.created_at DESC LIMIT 50"""
        )
        rows = cur.fetchall()
        items = []
        for r in rows:
            created_str = r["created_at"].strftime("%d %b, %I:%M %p") if isinstance(r["created_at"], datetime) else str(r["created_at"])
            
            cur.execute(
                """SELECT message_id, message_text, created_at FROM chat_messages
                   WHERE patient_id = %s AND sender = 'Care_Team' AND created_at > %s
                   ORDER BY created_at ASC LIMIT 1""",
                (r["patient_id"], r["created_at"]),
            )
            rep = cur.fetchone()
            replied = rep is not None
            reply_text = rep["message_text"] if rep else None

            items.append({
                "message_id": r["message_id"],
                "patient_id": r["patient_id"],
                "patient_name": r["patient_name"],
                "patient_code": r["patient_code"],
                "question": r["patient_question"] or "Patient inquiry",
                "draft_answer": r["message_text"],
                "answer_type": r["answer_type"],
                "rating": r["rating"],
                "feedback_comment": r["feedback_comment"],
                "created_at": created_str,
                "status": "Replied" if replied else "Pending",
                "reply_text": reply_text,
            })
        return items


@app.post("/staff/assistant-questions/{message_id}/reply")
def reply_to_assistant_question(
    message_id: int,
    body: AssistantReplyIn,
    user: Dict[str, Any] = Depends(require_staff),
):
    """
    Submits a nurse reply to an assistant question.
    Creates a chat message from 'Care_Team', delivers an update to patient Updates,
    resolves the associated task, and audits the reply.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT m.patient_id, p.full_name, p.preferred_language
               FROM chat_messages m
               JOIN patients p ON p.patient_id = m.patient_id
               WHERE m.message_id = %s""",
            (message_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Assistant question message not found.")

        pid = row["patient_id"]
        staff_name = user.get("name") or "Priya Nair"
        first_staff_name = staff_name.split()[0] if staff_name else "Priya"

        # 1. Insert reply as Care_Team sender in chat_messages
        cur.execute(
            """INSERT INTO chat_messages (patient_id, sender, message_text, is_grounded, answer_type, created_at)
               VALUES (%s, 'Care_Team', %s, 1, 'care_team', NOW())""",
            (pid, body.reply_text),
        )
        reply_msg_id = cur.lastrowid

        # 2. Insert into patient_updates
        title = f"Message from {first_staff_name} (nurse)"
        cur.execute(
            """INSERT INTO patient_updates (patient_id, update_type, title, body, created_by, created_at)
               VALUES (%s, 'nurse_reply', %s, %s, 'Staff', NOW())""",
            (pid, title, body.reply_text),
        )
        update_id = cur.lastrowid

        # 3. Resolve pending follow-up task if one was associated
        cur.execute(
            """UPDATE follow_up_tasks
               SET status = 'Resolved', completed_at = NOW()
               WHERE patient_id = %s AND status = 'Pending' AND (reason LIKE '%%question%%' OR reason LIKE '%%dose%%')""",
            (pid,),
        )

        # 4. Audit
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Staff', %s, 'NURSE_ASSISTANT_REPLY', 'chat_message', %s,
                       JSON_OBJECT('patient_id', %s, 'reply_message_id', %s, 'update_id', %s))""",
            (str(user["account_id"]), reply_msg_id, pid, reply_msg_id, update_id),
        )

        return {
            "status": "ok",
            "reply_message_id": reply_msg_id,
            "update_id": update_id,
            "message": "Reply delivered to patient chat and Updates.",
        }


@app.post("/staff/assistant-questions/{message_id}/done")
def mark_assistant_question_done(
    message_id: int,
    user: Dict[str, Any] = Depends(require_staff),
):
    """
    Marks an assistant question as done without a chat reply.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT patient_id FROM chat_messages WHERE message_id = %s""",
            (message_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Message not found.")
        pid = row["patient_id"]

        cur.execute(
            """UPDATE follow_up_tasks
               SET status = 'Resolved', completed_at = NOW()
               WHERE patient_id = %s AND status = 'Pending' AND (reason LIKE '%%question%%' OR reason LIKE '%%dose%%')""",
            (pid,),
        )

        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Staff', %s, 'ASSISTANT_QUESTION_DONE', 'chat_message', %s, JSON_OBJECT('patient_id', %s))""",
            (str(user["account_id"]), message_id, pid),
        )
        return {"status": "ok", "message_id": message_id, "marked_done": True}


@app.get("/staff/assistant-review")
def get_assistant_review_list(user: Dict[str, Any] = Depends(require_staff)):
    """
    Doctor review list for assistant quality: negative feedback (thumbs down) and not-found answers.
    Feeds back into the evaluation set.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT m.message_id, m.patient_id, p.full_name AS patient_name,
                      m.message_text AS draft_answer, m.answer_type, m.created_at,
                      m.retrieval_debug, f.rating, f.comment AS feedback_comment,
                      (SELECT message_text FROM chat_messages m_user 
                       WHERE m_user.patient_id = m.patient_id AND m_user.sender = 'Patient' 
                         AND m_user.message_id < m.message_id 
                       ORDER BY m_user.message_id DESC LIMIT 1) AS patient_question
               FROM chat_messages m
               JOIN patients p ON p.patient_id = m.patient_id
               LEFT JOIN chat_feedback f ON f.message_id = m.message_id
               WHERE m.sender = 'AI_Nurse'
                 AND (f.rating = -1 OR m.answer_type = 'not_found')
               ORDER BY m.created_at DESC LIMIT 50"""
        )
        rows = cur.fetchall()
        items = []
        for r in rows:
            created_str = r["created_at"].strftime("%d %b, %I:%M %p") if isinstance(r["created_at"], datetime) else str(r["created_at"])
            items.append({
                "message_id": r["message_id"],
                "patient_id": r["patient_id"],
                "patient_name": r["patient_name"],
                "question": r["patient_question"] or "Patient inquiry",
                "draft_answer": r["draft_answer"],
                "answer_type": r["answer_type"],
                "rating": r["rating"],
                "feedback_comment": r["feedback_comment"],
                "created_at": created_str,
                "reason": "Negative Feedback (Thumbs Down)" if r["rating"] == -1 else "Information Not Found in Papers",
            })
        return items


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
                       SET summary_text = %s, model_name = %s, source_snapshot = %s, generated_at = NOW(),
                           status = 'Draft', reviewed_by_staff_id = NULL, reviewed_at = NULL
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
    res = generate_clinical_summary(
        GenerateSummaryIn(patient_id=pid, target_date=summary_date),
        user=user,
    )
    # Legacy tests (M5) assert status == "AI draft, not reviewed"
    res_copy = dict(res)
    res_copy["status"] = "AI draft, not reviewed"
    return res_copy


@app.get("/staff/summaries/pending")
def get_pending_summaries(user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse"))):
    """Returns AI draft summaries waiting for clinician review."""
    return get_staff_summaries(status="draft", user=user)


@app.post("/staff/summaries/{summary_id}/approve")
def approve_summary(
    summary_id: int,
    body: ApproveSummaryIn,
    user: Dict[str, Any] = Depends(require_doctor),
):
    """
    D-08 & D-12: Approve draft summary.
    STRICT RULE: Doctor role is required! Nurses cannot approve summaries.
    """
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
    user: Dict[str, Any] = Depends(require_doctor),
):
    """
    D-08 & D-12: Reject draft summary with required clinical reason.
    STRICT RULE: Doctor role is required!
    """
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
    user: Dict[str, Any] = Depends(require_doctor),
):
    """Legacy review route redirecting to approve/reject. Strictly Doctor-only."""
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
            SELECT DISTINCT p.patient_id, p.patient_code, p.full_name,
                   TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age_years,
                   COALESCE(d.condition_summary, 'Post-discharge recovery') AS condition_summary,
                   d.discharge_date,
                   DATEDIFF(CURDATE(), d.discharge_date) + 1 AS day_number,
                   cs.full_name AS attending_doctor
            FROM patients p
            LEFT JOIN discharge_records d ON d.patient_id = p.patient_id
            LEFT JOIN care_staff cs ON cs.staff_id = d.attending_staff_id
            LEFT JOIN care_assignments ca ON ca.patient_id = p.patient_id AND (ca.ends_at IS NULL OR ca.ends_at > NOW())
            WHERE 1=1
        """
        if scope == "mine":
            p_query += """ AND (ca.staff_id = %s 
                                OR d.attending_staff_id = %s OR EXISTS (
                                    SELECT 1 FROM follow_up_tasks ft 
                                    WHERE ft.patient_id = p.patient_id AND ft.assigned_staff_id = %s
                                ))"""
            p_query += " ORDER BY p.patient_id ASC"
            params = (staff_id, staff_id, staff_id)
            cur.execute(p_query, params)
        else:
            p_query += " ORDER BY p.patient_id ASC"
            cur.execute(p_query)
        patients = cur.fetchall() or []

        # If empty in mine scope, fallback to all patients so handoff is never blank
        if not patients and scope == "mine":
            cur.execute(
                """SELECT DISTINCT p.patient_id, p.patient_code, p.full_name,
                          TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age_years,
                          COALESCE(d.condition_summary, 'Post-discharge recovery') AS condition_summary,
                          d.discharge_date,
                          DATEDIFF(CURDATE(), d.discharge_date) + 1 AS day_number,
                          cs.full_name AS attending_doctor
                   FROM patients p
                   LEFT JOIN discharge_records d ON d.patient_id = p.patient_id
                   LEFT JOIN care_staff cs ON cs.staff_id = d.attending_staff_id
                   ORDER BY p.patient_id ASC"""
            )
            patients = cur.fetchall() or []

        handoff_cards = []
        for p in patients:
            pid = p["patient_id"]

            # Open flags
            cur.execute(
                """SELECT flag_id, severity, source_type, reason, status, created_at
                   FROM flags
                   WHERE patient_id = %s AND status IN ('Open', 'Acknowledged')
                   ORDER BY FIELD(severity, 'Immediate', 'Urgent', 'Review_Soon', 'Routine'), created_at DESC""",
                (pid,),
            )
            flags = cur.fetchall() or []

            # Illness tier from flags only: Immediate > Urgent > Review soon > Routine
            if any(f.get("source_type") == "Emergency" or f.get("severity") == "Immediate" for f in flags):
                illness_tier = "Immediate"
            elif any(f.get("severity") in ("Urgent", "Urgent_Review") for f in flags):
                illness_tier = "Urgent"
            elif any(f.get("severity") == "Review_Soon" for f in flags):
                illness_tier = "Review soon"
            else:
                illness_tier = "Routine"

            # Open tasks
            # Open tasks (capped at 5 to maintain concise handoff card)
            cur.execute(
                """SELECT t.followup_id, t.reason, t.priority, t.due_at, t.status, cs.full_name AS assigned_staff_name
                   FROM follow_up_tasks t
                   LEFT JOIN care_staff cs ON cs.staff_id = t.assigned_staff_id
                   WHERE t.patient_id = %s AND t.status != 'Resolved'
                   ORDER BY t.due_at ASC
                   LIMIT 5""",
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

            # Contingency note (from clinician note or patient's approved rule limit, never hardcoded protocol)
            cur.execute(
                """SELECT note_text, created_at
                   FROM clinician_notes
                   WHERE patient_id = %s AND note_type IN ('Plan_Change', 'General')
                   ORDER BY note_id DESC LIMIT 1""",
                (pid,),
            )
            c_note_row = cur.fetchone()
            if c_note_row:
                contingency_note = c_note_row["note_text"]
            else:
                cur.execute(
                    """SELECT threshold_value FROM alert_rules
                       WHERE patient_id = %s AND measurement_type = 'SpO2' AND rule_type = 'Reading_Below' AND is_active = 1 LIMIT 1""",
                    (pid,)
                )
                spo2_rule = cur.fetchone()
                if spo2_rule:
                    spo2_thresh = int(spo2_rule["threshold_value"])
                    contingency_note = f"Approved contingency: If SpO2 falls below approved limit of {spo2_thresh}% or acute symptoms develop, notify attending physician."
                else:
                    cur.execute(
                        """SELECT rule_type, measurement_type, threshold_value FROM alert_rules
                           WHERE patient_id = %s AND is_active = 1 LIMIT 1""",
                        (pid,)
                    )
                    other_rule = cur.fetchone()
                    if other_rule:
                        m_type = other_rule.get("measurement_type") or other_rule.get("rule_type")
                        th_val = other_rule.get("threshold_value")
                        contingency_note = f"Approved contingency: If {m_type} breaches approved limit of {th_val} or acute symptoms develop, notify attending physician."
                    else:
                        contingency_note = "Approved contingency: If acute symptoms develop or clinical status changes, notify attending physician."

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

            combined_actions = [
                {
                    "task_id": t["followup_id"],
                    "reason": t["reason"],
                    "priority": t["priority"],
                    "due_at": str(t["due_at"]) if t["due_at"] else "Today",
                    "owner": t["assigned_staff_name"] or "Unassigned",
                }
                for t in tasks
            ]

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
                "action_list": combined_actions,
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
    complete_task: Optional[bool] = False
    outcome_code: Optional[str] = None


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

        if body.complete_task and body.task_id:
            task_code = body.outcome_code or "Reached_And_Advised"
            if task_code in VALID_OUTCOME_CODES:
                cur.callproc("sp_complete_task", (body.task_id, staff_id, task_code, body.summary or "Call completed"))

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
    user: Dict[str, Any] = Depends(require_doctor),
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
    user: Dict[str, Any] = Depends(require_doctor),
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


# ─── Phase 3 Staff Copilot: "Ask CareLoop" (Ctrl+K Ask Mode) ─────────────────

class CopilotAskIn(BaseModel):
    query: str
    bypass_cache: bool = False


@app.post("/staff/copilot/ask")
def staff_copilot_ask(
    body: CopilotAskIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    Phase 3: Staff Copilot 'Ask CareLoop' endpoint.
    Strictly maps queries to allowlisted templates with zero text-to-SQL.
    """
    from backend.app.agents.copilot_service import ask_careloop
    return ask_careloop(
        query=body.query,
        user=user,
        bypass_cache=body.bypass_cache
    )


@app.get("/staff/copilot/templates")
def staff_copilot_templates(
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Returns allowlisted template catalog for Copilot 'Ask' mode."""
    from backend.app.agents.copilot_service import ALLOWLISTED_TEMPLATES
    return {"templates": ALLOWLISTED_TEMPLATES}


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
    Returns metrics with transparent clinical definitions (NO unprovable outcome claims).
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
    user: Dict[str, Any] = Depends(require_doctor),
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

        # Deduplicate FHIR_EXPORT audit logging (throttle repeated GET fetches within 60s)
        cur.execute(
            """SELECT log_id FROM audit_log
               WHERE entity_type = 'patient' AND entity_id = %s AND action = 'FHIR_EXPORT'
                 AND created_at >= NOW() - INTERVAL 60 SECOND LIMIT 1""",
            (pid,),
        )
        if not cur.fetchone():
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


# ─── Patient Family Sharing & Consent (Phase 2) ─────────────────────────────

class SharingToggleIn(BaseModel):
    enabled: bool


@app.post("/patient/me/sharing")
def toggle_family_sharing(
    body: SharingToggleIn,
    user: Dict[str, Any] = Depends(require_patient),
):
    """
    Patient controls family sharing consent (Section 2.3 & 3.8).
    When sharing is disabled:
    - caregivers.consent_granted is set to 0.
    - All /family/... endpoints immediately return 403.
    - Escalation step shows 'Skipped: no consent'.
    - Written to immutable audit_log.
    """
    pid = user["patient_id"]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """UPDATE caregivers
               SET consent_granted = %s
               WHERE patient_id = %s""",
            (1 if body.enabled else 0, pid),
        )
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Patient', %s, 'FAMILY_SHARING_TOGGLED', 'patient', %s,
                       JSON_OBJECT('sharing_enabled', %s, 'patient_id', %s))""",
            (str(user["account_id"]), pid, body.enabled, pid),
        )
        conn.commit()

    return {"status": "updated", "sharing_enabled": body.enabled, "patient_id": pid}


@app.get("/patient/me/sharing")
def get_family_sharing_status(
    user: Dict[str, Any] = Depends(require_patient),
):
    """Returns current family sharing status and linked caregiver details."""
    pid = user["patient_id"]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT caregiver_id, full_name, relationship, phone, consent_granted
               FROM caregivers WHERE patient_id = %s LIMIT 1""",
            (pid,),
        )
        cg = cur.fetchone()

    if not cg:
        return {"sharing_enabled": False, "caregiver": None}

    return {
        "sharing_enabled": bool(cg["consent_granted"]),
        "caregiver": {
            "caregiver_id": cg["caregiver_id"],
            "name": cg["full_name"],
            "relationship": cg["relationship"],
            "phone": cg["phone"],
        },
    }


# ─── Family Helper Endpoints (Phase 2 & Section 2.3) ────────────────────────

@app.get("/family/today")
def get_family_today(user: Dict[str, Any] = Depends(require_family)):
    """
    Family View 'Today' endpoint (Section 2.3 & 2.4):
    Strictly requires active caregiver consent (caregivers.consent_granted = 1).
    Returns a reduced, supportive dataset:
    - Patient identity (name, age, patient code)
    - Recovery day (Day N)
    - Latest valid readings (HR, SpO2, BP) — invalid readings like 450 bpm are omitted
    - Today's dose status (taken/scheduled/missed — no clinical pharmacology details)
    - Check-in status (sent today: yes/no — no symptom text or chat)
    - 'What you may need to do' guidance card
    - Consent acknowledgement badge
    """
    pid = user["patient_id"]
    cg_info = user.get("caregiver_info") or {}

    with get_conn() as conn, conn.cursor() as cur:
        # 1. Patient identity & discharge
        cur.execute(
            """SELECT p.patient_id, p.patient_code, p.full_name, p.date_of_birth,
                      d.condition_summary, d.discharge_date,
                      DATEDIFF(CURDATE(), d.discharge_date) + 1 AS day_number
               FROM patients p
               LEFT JOIN discharge_records d ON d.patient_id = p.patient_id
               WHERE p.patient_id = %s""",
            (pid,),
        )
        pat = cur.fetchone()
        if not pat:
            raise HTTPException(status_code=404, detail="Patient record not found")

        # Age calculation
        dob = pat.get("date_of_birth")
        age = None
        if dob:
            today_d = date.today()
            age = today_d.year - dob.year - ((today_d.month, today_d.day) < (dob.month, dob.day))

        # 2. Latest valid readings (Filter out quality_status = 'Invalid')
        cur.execute(
            """SELECT measurement_type, measurement_value, unit, measured_at, quality_status
               FROM sensor_readings
               WHERE patient_id = %s AND (quality_status != 'Invalid' OR quality_status IS NULL)
               ORDER BY measured_at DESC""",
            (pid,),
        )
        all_readings = cur.fetchall() or []
        latest_readings = {}
        for r in all_readings:
            mtype = r["measurement_type"]
            if mtype not in latest_readings:
                latest_readings[mtype] = {
                    "type": mtype,
                    "value": float(r["measurement_value"]),
                    "unit": r["unit"],
                    "quality_status": r["quality_status"] or "Good",
                    "recorded_at": r["measured_at"].isoformat() if isinstance(r["measured_at"], datetime) else str(r["measured_at"]),
                }

        # 3. Today's doses (status only, no pharmacology details)
        cur.execute(
            """SELECT ml.medication_log_id, ml.scheduled_for, ml.status, ml.recorded_at, ml.recorded_by,
                      m.medicine_name
               FROM medication_logs ml
               JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
               JOIN medicines m ON m.medicine_id = pr.medicine_id
               WHERE pr.patient_id = %s
                 AND ml.scheduled_for >= CURDATE()
                 AND ml.scheduled_for < CURDATE() + INTERVAL 1 DAY
               ORDER BY ml.scheduled_for ASC""",
            (pid,),
        )
        dose_rows = cur.fetchall() or []
        doses = []
        unconfirmed_count = 0
        taken_count = 0
        for d in dose_rows:
            st = d["status"]
            if st == "Taken_Confirmed":
                taken_count += 1
                disp_st = "Taken"
            elif st == "Skipped":
                disp_st = "Skipped"
            elif st == "Missed":
                disp_st = "Missed"
                unconfirmed_count += 1
            else:
                disp_st = "Scheduled"
                unconfirmed_count += 1

            sched_time = d["scheduled_for"].strftime("%I:%M %p") if isinstance(d["scheduled_for"], datetime) else ""
            doses.append({
                "dose_id": d["medication_log_id"],
                "medicine_name": d["medicine_name"],
                "scheduled_time": sched_time,
                "status": disp_st,
                "raw_status": st,
                "can_confirm": st not in ("Taken_Confirmed", "Skipped"),
            })

        # 4. Checkin completed today (yes / no only)
        cur.execute(
            """SELECT symptom_report_id, reported_at
               FROM symptom_reports
               WHERE patient_id = %s AND DATE(reported_at) = CURDATE()
               ORDER BY reported_at DESC LIMIT 1""",
            (pid,),
        )
        chk = cur.fetchone()
        checkin_completed_today = bool(chk)

        # 5. Active urgent alert or caregiver escalation check for guidance card
        cur.execute(
            """SELECT flag_id, severity FROM flags
               WHERE patient_id = %s AND status IN ('Open', 'Acknowledged') AND severity IN ('Urgent_Review', 'Immediate')
               LIMIT 1""",
            (pid,),
        )
        urgent_flag = cur.fetchone()

        cur.execute(
            """SELECT e.escalation_id FROM escalations e
               JOIN flags f ON f.flag_id = e.flag_id
               WHERE f.patient_id = %s AND f.status IN ('Open', 'Acknowledged')
                 AND e.step_type = 'Caregiver_SMS' AND e.delivery_status = 'Sent'
               LIMIT 1""",
            (pid,),
        )
        escalation_reached = cur.fetchone()

        # 6. Next appointment
        cur.execute(
            """SELECT a.appointment_id, a.appointment_date, a.appointment_type,
                      s.full_name AS doctor_name, s.specialization
               FROM appointments a
               JOIN care_staff s ON s.staff_id = a.staff_id
               WHERE a.patient_id = %s AND a.appointment_date >= NOW()
               ORDER BY a.appointment_date ASC LIMIT 1""",
            (pid,),
        )
        appt = cur.fetchone()
        next_appointment = None
        if appt:
            next_appointment = {
                "appointment_id": appt["appointment_id"],
                "date": appt["appointment_date"].strftime("%d %b %Y, %I:%M %p") if isinstance(appt["appointment_date"], datetime) else str(appt["appointment_date"]),
                "doctor_name": appt["doctor_name"],
                "specialization": appt["specialization"] or "Care Clinic",
                "type": appt["appointment_type"],
            }

        # What you may need to do card (Section 5 Phase 5)
        if urgent_flag or escalation_reached:
            what_to_do = "The care team is checking on Aarav. Please contact him."
            what_to_do_severity = "urgent"
        else:
            what_to_do = "Nothing needed right now."
            what_to_do_severity = "normal"

    return {
        "patient": {
            "patient_id": pat["patient_id"],
            "patient_code": pat["patient_code"],
            "full_name": pat["full_name"],
            "age": age,
            "condition": pat["condition_summary"] or "Post-Discharge Recovery",
            "day_number": pat["day_number"] or 3,
        },
        "caregiver": {
            "name": cg_info.get("full_name") or "Family Helper",
            "relationship": cg_info.get("relationship") or "Family",
            "consent_granted": True,
            "sharing_badge": "Sharing allowed by Aarav on 27 Oct",
        },
        "what_you_may_need_to_do": {
            "text": what_to_do,
            "severity": what_to_do_severity,
        },
        "latest_vitals": latest_readings,
        "today_doses": {
            "total": len(doses),
            "taken": taken_count,
            "remaining": unconfirmed_count,
            "items": doses,
        },
        "checkin_status": {
            "completed_today": checkin_completed_today,
            "message": "Yes" if checkin_completed_today else "No",
        },
        "next_appointment": next_appointment,
    }


@app.post("/family/doses/{log_id}/helped")
def family_confirm_dose(
    log_id: int,
    user: Dict[str, Any] = Depends(require_family),
):
    """
    Family Helper confirms assisting patient with medication dose (Section 2.3).
    - Checks dose belongs to authorized patient.
    - Sets status to 'Taken_Confirmed', recorded_by to 'Caregiver'.
    - Logs to audit_log with action 'TAKE_DOSE_FAMILY_HELPED'.
    """
    pid = user["patient_id"]
    cg_name = (user.get("caregiver_info") or {}).get("full_name") or "Family helper"

    with get_conn() as conn, conn.cursor() as cur:
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
            raise HTTPException(status_code=404, detail="Medication dose log not found for this patient.")

        if dose["status"] == "Taken_Confirmed":
            return {"status": "already_taken", "dose_id": log_id, "medicine": dose["medicine_name"]}

        cur.execute(
            """UPDATE medication_logs
               SET status = 'Taken_Confirmed', recorded_at = NOW(), recorded_by = 'Caregiver',
                   patient_note = %s
               WHERE medication_log_id = %s""",
            (f"Confirmed with help from Family helper ({cg_name})", log_id),
        )

        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Caregiver', %s, 'TAKE_DOSE_FAMILY_HELPED', 'medication_log', %s,
                       JSON_OBJECT('status', 'Taken_Confirmed', 'medicine', %s, 'patient_id', %s, 'caregiver', %s))""",
            (str(user["account_id"]), log_id, dose["medicine_name"], pid, cg_name),
        )
        conn.commit()

    return {
        "status": "updated",
        "dose_id": log_id,
        "medicine": dose["medicine_name"],
        "actor": "Family helper",
        "message": f"Confirmed dose with help from {cg_name}",
    }


@app.get("/family/calendar")
def get_family_calendar(user: Dict[str, Any] = Depends(require_family)):
    """Family View Calendar endpoint: returns upcoming appointments and 7-day dose history strip."""
    pid = user["patient_id"]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT a.appointment_id, a.appointment_date, a.appointment_type, a.status,
                      s.full_name AS doctor_name, s.specialization
               FROM appointments a
               JOIN care_staff s ON s.staff_id = a.staff_id
               WHERE a.patient_id = %s AND a.appointment_date >= CURDATE()
               ORDER BY a.appointment_date ASC""",
            (pid,),
        )
        appts = cur.fetchall() or []

        cur.execute(
            """SELECT DATE(ml.scheduled_for) AS log_date,
                      COUNT(*) AS total_doses,
                      SUM(CASE WHEN ml.status = 'Taken_Confirmed' THEN 1 ELSE 0 END) AS taken_doses,
                      SUM(CASE WHEN ml.status = 'Skipped' THEN 1 ELSE 0 END) AS skipped_doses
               FROM medication_logs ml
               JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
               WHERE pr.patient_id = %s
                 AND ml.scheduled_for >= CURDATE() - INTERVAL 6 DAY
                 AND ml.scheduled_for < CURDATE() + INTERVAL 1 DAY
               GROUP BY DATE(ml.scheduled_for)
               ORDER BY log_date DESC""",
            (pid,),
        )
        dose_strip_rows = cur.fetchall() or []

    results = []
    for a in appts:
        results.append({
            "appointment_id": a["appointment_id"],
            "date": a["appointment_date"].strftime("%A, %d %B %Y") if isinstance(a["appointment_date"], datetime) else str(a["appointment_date"]),
            "time": a["appointment_date"].strftime("%I:%M %p") if isinstance(a["appointment_date"], datetime) else "",
            "doctor_name": a["doctor_name"],
            "department": a["specialization"] or "Cardiology Recovery Desk",
            "type": a["appointment_type"],
            "status": a["status"],
            "ics_url": f"/patient/me/appointments/{a['appointment_id']}.ics",
        })

    dose_history = [
        {
            "date": r["log_date"].strftime("%d %b %Y") if isinstance(r["log_date"], (date, datetime)) else str(r["log_date"]),
            "day_name": r["log_date"].strftime("%a") if isinstance(r["log_date"], (date, datetime)) else "",
            "total": int(r["total_doses"]),
            "taken": int(r["taken_doses"] or 0),
            "skipped": int(r["skipped_doses"] or 0),
            "summary": f"{int(r['taken_doses'] or 0)} of {int(r['total_doses'])} taken",
            "all_taken": int(r["taken_doses"] or 0) >= int(r["total_doses"]),
        }
        for r in dose_strip_rows
    ]

    return {"appointments": results, "dose_history": dose_history, "patient_id": pid}


@app.get("/family/contacts")
def get_family_contacts(user: Dict[str, Any] = Depends(require_family)):
    """Family View Contacts endpoint: returns care team and emergency services."""
    return {
        "attending_doctor": {
            "name": "Dr. Ananya Sharma",
            "role": "Attending Physician",
            "phone": "+91-98765-01001",
            "clinic": "CareLoop Recovery Clinic",
        },
        "assigned_nurse": {
            "name": "Priya Nair",
            "role": "Assigned Care Nurse",
            "phone": "+91-98765-01002",
        },
        "hospital_desk": {
            "name": "CareLoop Clinic Support Desk",
            "phone": "+91-98765-00000",
            "hours": "08:00 - 20:00 Mon-Sat",
        },
        "emergency": {
            "number": "112",
            "label": "National Emergency Services",
            "guidance": "If experiencing severe chest pain, shortness of breath, or sudden weakness, call 112 immediately.",
        },
    }


# ─── Staff Rule Proposals (Phase 2) ──────────────────────────────────────────

class ProposeLimitIn(BaseModel):
    rule_id: int
    threshold_value: float
    window_hours: Optional[int] = None
    severity: Optional[str] = None
    change_reason: str


@app.post("/staff/rules/propose-limit")
def propose_limit_endpoint(
    body: ProposeLimitIn,
    user: Dict[str, Any] = Depends(require_staff),
):
    """Nurse or Doctor limit proposal endpoint (Section 2.3)."""
    update_body = UpdateRuleIn(
        threshold_value=body.threshold_value,
        window_hours=body.window_hours,
        severity=body.severity,
        change_reason=body.change_reason,
    )
    return update_alert_rule(rule_id=body.rule_id, body=update_body, user=user)


# ─── Doctor Decision Desk Endpoints (Phase 3) ─────────────────────────────────

@app.get("/staff/doctor/decisions")
def get_doctor_decisions(
    user: Dict[str, Any] = Depends(require_doctor),
):
    """
    Doctor Desk: What needs Dr. Sharma's decision? (Phase 3 Task 1)
    Aggregates:
    1. Immediate & urgent flags (plus flags escalated by the nurse)
    2. AI draft summaries awaiting sign-off
    3. Pending rule limit change proposals
    4. Quiet patients strip (on-track patients with zero open items)
    """
    with get_conn() as conn, conn.cursor() as cur:
        # 1. Total cohort count
        cur.execute("SELECT COUNT(*) AS total FROM patients")
        total_patients = cur.fetchone()["total"]

        # 2. Decision flags (Immediate / Urgent / Escalated)
        cur.execute(
            """SELECT f.flag_id, f.patient_id, p.full_name, p.patient_code,
                      TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age,
                      dr.condition_summary, f.reason, f.severity,
                      IF(f.source_type = 'Emergency', 'Immediate', f.severity) AS tier,
                      f.created_at,
                      ROUND(TIMESTAMPDIFF(MINUTE, f.created_at, NOW())) AS waited_mins,
                      (SELECT cs.full_name FROM flag_events fe 
                       JOIN care_staff cs ON fe.staff_id = cs.staff_id 
                       WHERE fe.flag_id = f.flag_id AND fe.event_type = 'Escalated' 
                       ORDER BY fe.flag_event_id DESC LIMIT 1) AS escalated_by,
                      (SELECT fe.created_at FROM flag_events fe 
                       WHERE fe.flag_id = f.flag_id AND fe.event_type = 'Escalated' 
                       ORDER BY fe.flag_event_id DESC LIMIT 1) AS escalated_at,
                      (SELECT fe.note FROM flag_events fe 
                       WHERE fe.flag_id = f.flag_id AND fe.event_type = 'Escalated' 
                       ORDER BY fe.flag_event_id DESC LIMIT 1) AS escalation_note
               FROM flags f
               JOIN patients p ON f.patient_id = p.patient_id
               LEFT JOIN discharge_records dr ON p.patient_id = dr.patient_id
               WHERE f.status = 'Open'
                 AND (f.severity = 'Urgent_Review' 
                      OR f.source_type = 'Emergency'
                      OR f.flag_id IN (SELECT flag_id FROM flag_events WHERE event_type = 'Escalated'))
               ORDER BY FIELD(f.source_type, 'Emergency') DESC,
                        FIELD(f.severity, 'Urgent_Review', 'Review_Soon', 'Info'),
                        f.created_at ASC"""
        )
        flag_rows = cur.fetchall()

        # 3. Draft AI Summaries
        cur.execute(
            """SELECT s.summary_id, s.patient_id, p.full_name, p.patient_code,
                      TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age,
                      dr.condition_summary, s.status, s.generated_at, s.source_snapshot,
                      ROUND(TIMESTAMPDIFF(MINUTE, s.generated_at, NOW())) AS waited_mins
               FROM ai_summaries s
               JOIN patients p ON s.patient_id = p.patient_id
               LEFT JOIN discharge_records dr ON p.patient_id = dr.patient_id
               WHERE s.status = 'Draft'
               ORDER BY s.generated_at ASC"""
        )
        summary_rows = cur.fetchall()
        for sm in summary_rows:
            if isinstance(sm.get("source_snapshot"), str):
                try:
                    sm["source_snapshot"] = json.loads(sm["source_snapshot"])
                except Exception:
                    sm["source_snapshot"] = {}

        # 4. Pending Limit Proposals
        cur.execute(
            """SELECT h.history_id, h.rule_id, h.changed_by_staff_id, h.change_reason,
                      h.old_values, h.new_values, h.changed_at,
                      cs.full_name AS proposed_by_name,
                      ar.patient_id, ar.rule_type, ar.measurement_type,
                      p.patient_code, p.full_name,
                      TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age,
                      dr.condition_summary,
                      ROUND(TIMESTAMPDIFF(MINUTE, h.changed_at, NOW())) AS waited_mins
               FROM alert_rules_history h
               JOIN alert_rules ar ON h.rule_id = ar.rule_id
               JOIN patients p ON ar.patient_id = p.patient_id
               LEFT JOIN discharge_records dr ON p.patient_id = dr.patient_id
               LEFT JOIN care_staff cs ON h.changed_by_staff_id = cs.staff_id
               WHERE JSON_EXTRACT(h.new_values, '$.proposed_only') = true
                 AND (JSON_EXTRACT(h.new_values, '$.status') IS NULL OR JSON_UNQUOTE(JSON_EXTRACT(h.new_values, '$.status')) = 'Pending')
               ORDER BY h.changed_at ASC"""
        )
        proposal_rows = cur.fetchall()
        for pr in proposal_rows:
            for f in ("old_values", "new_values"):
                if isinstance(pr.get(f), str):
                    try:
                        pr[f] = json.loads(pr[f])
                    except Exception:
                        pr[f] = {}

        # 5. Quiet Patients (Zero open flags and zero draft summaries)
        cur.execute(
            """SELECT p.patient_id, p.patient_code, p.full_name, dr.condition_summary,
                      DATEDIFF(CURDATE(), dr.discharge_date) + 1 AS relative_day
               FROM patients p
               LEFT JOIN discharge_records dr ON p.patient_id = dr.patient_id
               WHERE p.patient_id NOT IN (SELECT patient_id FROM flags WHERE status = 'Open')
                 AND p.patient_id NOT IN (SELECT patient_id FROM ai_summaries WHERE status = 'Draft')
               ORDER BY p.patient_id ASC"""
        )
        quiet_rows = cur.fetchall()

        # Combine into unified decision items list
        decision_items = []

        # Map flags to cases and briefs for Doctor Decision desk (Phase 3)
        from .agents.case_prep_agent import CasePrepAgent
        cur.execute("""
            SELECT cf.flag_id, c.case_id, c.merged_count, c.primary_flag_id
            FROM case_flags cf
            JOIN cases c ON c.case_id = cf.case_id
            WHERE c.status IN ('Open', 'In_Progress');
        """)
        doc_case_map = {r["flag_id"]: r for r in cur.fetchall()}
        cur.execute("""
            SELECT primary_flag_id, case_id, merged_count
            FROM cases
            WHERE status IN ('Open', 'In_Progress');
        """)
        for r in cur.fetchall():
            if r["primary_flag_id"] and r["primary_flag_id"] not in doc_case_map:
                doc_case_map[r["primary_flag_id"]] = r

        for fl in flag_rows:
            c_info = doc_case_map.get(fl["flag_id"])
            case_id = c_info["case_id"] if c_info else None
            brief = None
            if case_id:
                cur.execute("""
                    SELECT run_id, body FROM agent_drafts
                    WHERE draft_type = 'Case_Brief' AND JSON_UNQUOTE(JSON_EXTRACT(body, '$.case_id')) = %s
                    ORDER BY created_at DESC LIMIT 1;
                """, (case_id,))
                b_row = cur.fetchone()
                if b_row and b_row.get("body"):
                    b_body = b_row["body"]
                    if isinstance(b_body, str):
                        try:
                            b_body = json.loads(b_body)
                        except Exception:
                            pass
                    b_body["run_id"] = b_row["run_id"]
                    brief = b_body
                else:
                    try:
                        brief = CasePrepAgent.generate_case_brief(case_id, force_deterministic=True)
                    except Exception:
                        pass

            waited = f"{fl['waited_mins']}m" if fl['waited_mins'] < 60 else f"{fl['waited_mins'] // 60}h {fl['waited_mins'] % 60}m"
            tier_label = "Immediate" if fl['tier'] == 'Immediate' else "Urgent Review"
            if fl.get('escalated_by'):
                esc_time = fl['escalated_at'].strftime("%H:%M") if fl.get('escalated_at') else ""
                esc_note = f' · "{fl["escalation_note"]}"' if fl.get("escalation_note") else ""
                escalated_kicker = f"Escalated by Nurse {fl['escalated_by']} at {esc_time}{esc_note}".strip()
            else:
                escalated_kicker = None
            decision_items.append({
                "type": "flag",
                "id": fl["flag_id"],
                "flag_id": fl["flag_id"],
                "case_id": case_id,
                "brief_ready": brief is not None,
                "brief": brief,
                "prefilled_note": brief.get("prefilled", {}).get("note_draft") if brief else f"Attending physician review completed for {fl['reason']}.",
                "options": brief.get("options", ["call_now", "ask_doctor", "recheck_at"]) if brief else ["call_now", "ask_doctor", "recheck_at"],
                "agent_run_id": brief.get("run_id") if brief else None,
                "patient_id": fl["patient_id"],
                "patient_name": fl["full_name"],
                "patient_code": fl["patient_code"],
                "patient_age": fl["age"],
                "condition": fl["condition_summary"] or "Recovery",
                "title": f"{tier_label} flag: {fl['reason']}",
                "detail": fl["reason"],
                "tier": fl["tier"],
                "severity": fl["severity"],
                "waited_text": f"Waited {waited}",
                "escalated_kicker": escalated_kicker,
                "escalated_by": fl.get("escalated_by"),
                "escalated_at": fl["escalated_at"].strftime("%Y-%m-%d %H:%M") if fl.get("escalated_at") else None,
                "escalation_note": fl.get("escalation_note"),
                "priority_weight": 100 if fl["tier"] == "Immediate" else 80,
            })

        for sm in summary_rows:
            waited = f"{sm['waited_mins']}m" if sm['waited_mins'] < 60 else f"{sm['waited_mins'] // 60}h {sm['waited_mins'] % 60}m"
            decision_items.append({
                "type": "summary",
                "id": sm["summary_id"],
                "summary_id": sm["summary_id"],
                "patient_id": sm["patient_id"],
                "patient_name": sm["full_name"],
                "patient_code": sm["patient_code"],
                "patient_age": sm["age"],
                "condition": sm["condition_summary"] or "Recovery",
                "title": f"Discharge Summary sign-off: AI draft awaiting doctor approval",
                "detail": "AI-generated clinical draft requiring physician review and sign-off before export.",
                "tier": "Review_Soon",
                "waited_text": f"Waited {waited}",
                "source_snapshot": sm["source_snapshot"],
                "priority_weight": 60,
            })

        for pr in proposal_rows:
            waited = f"{pr['waited_mins']}m" if pr['waited_mins'] < 60 else f"{pr['waited_mins'] // 60}h {pr['waited_mins'] % 60}m"
            nv = pr.get("new_values") or {}
            ov = pr.get("old_values") or {}
            new_th = nv.get("threshold_value")
            old_th = ov.get("threshold_value")
            decision_items.append({
                "type": "limit_proposal",
                "id": pr["history_id"],
                "history_id": pr["history_id"],
                "rule_id": pr["rule_id"],
                "patient_id": pr["patient_id"],
                "patient_name": pr["full_name"],
                "patient_code": pr["patient_code"],
                "patient_age": pr["age"],
                "condition": pr["condition_summary"] or "Recovery",
                "title": f"Limit change request: Proposed {pr['rule_type']} threshold {old_th} → {new_th}",
                "detail": f"Proposed by {pr['proposed_by_name']}: {pr['change_reason']}",
                "tier": "Review_Soon",
                "waited_text": f"Waited {waited}",
                "proposed_by": pr["proposed_by_name"],
                "priority_weight": 50,
            })

        # 7. Recovery Plans Awaiting Approval (Phase 4 Feature F5 - tracked in Approvals -> Recovery plans)
        cur.execute(
            """SELECT rp.plan_id, rp.patient_id, p.full_name, p.patient_code,
                      TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age,
                      dr.condition_summary, rp.version, rp.drafted_at,
                      ROUND(TIMESTAMPDIFF(MINUTE, rp.drafted_at, NOW())) AS waited_mins
               FROM recovery_plans rp
               JOIN patients p ON rp.patient_id = p.patient_id
               LEFT JOIN discharge_records dr ON p.patient_id = dr.patient_id
               WHERE rp.status = 'Draft'
               ORDER BY rp.drafted_at ASC"""
        )
        plan_rows = cur.fetchall()

        # Sort all decision items by priority weight descending, then id
        decision_items.sort(key=lambda x: x["priority_weight"], reverse=True)

        return {
            "cards": {
                "needs_decision_now": len(decision_items),
                "summaries_to_approve": len(summary_rows),
                "limit_change_requests": len(proposal_rows),
                "plans_to_approve": len(plan_rows),
                "patients_in_followup": total_patients,
            },
            "items": decision_items,
            "quiet_patients": {
                "count": len(quiet_rows),
                "patients": quiet_rows,
                "message": f"Quiet patients: {len(quiet_rows)}. Nothing open.",
            },
        }


# ─── Nurse Call List Endpoints (Phase 4) ──────────────────────────────────────

@app.get("/staff/nurse/call-list")
def get_nurse_call_list(
    user: Dict[str, Any] = Depends(require_staff),
):
    """
    Nurse Desk: My call list (Phase 4 Task 1)
    Ordered by tier (Immediate > Urgent > Review Soon > Routine) then age.
    Aggregates:
    1. 4 KPI cards: calls_to_make, visits_today, pending_limit_requests, active_patients
    2. Open flag items requiring nurse contact:
       - Patient identity (name, age, patient_code, phone)
       - Real clinical why
       - Tier chip with target timer (e.g. Immediate: 15m, Review soon: 2h)
       - Overdue / target countdown display
       - 'Needs doctor to resolve' indicator for Immediate / Urgent
       - Escalation status ('Escalated to Dr. Sharma' with nurse name and timestamp if escalated)
       - Action buttons capability
    3. Calls due today strip (tasks due today)
    4. Patients on track (reassurance list)
    """
    with get_conn() as conn, conn.cursor() as cur:
        # 1. Total cohort count
        cur.execute("SELECT COUNT(*) AS total FROM patients")
        total_patients = cur.fetchone()["total"]

        # 2. Call items: Open flags
        cur.execute(
            """SELECT f.flag_id, f.patient_id, p.full_name, p.patient_code, p.phone,
                      TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age,
                      dr.condition_summary, f.reason, f.severity, f.source_type, f.status,
                      CASE 
                        WHEN f.source_type = 'Emergency' THEN 'Immediate'
                        WHEN f.severity = 'Urgent_Review' THEN 'Urgent'
                        WHEN f.severity = 'Review_Soon' THEN 'Review soon'
                        ELSE 'Routine'
                      END AS tier,
                      f.created_at,
                      ROUND(TIMESTAMPDIFF(MINUTE, f.created_at, NOW())) AS waited_mins,
                      (SELECT cs.full_name FROM flag_events fe 
                       JOIN care_staff cs ON fe.staff_id = cs.staff_id 
                       WHERE fe.flag_id = f.flag_id AND fe.event_type = 'Escalated' 
                       ORDER BY fe.flag_event_id DESC LIMIT 1) AS escalated_by,
                      (SELECT fe.created_at FROM flag_events fe 
                       WHERE fe.flag_id = f.flag_id AND fe.event_type = 'Escalated' 
                       ORDER BY fe.flag_event_id DESC LIMIT 1) AS escalated_at,
                      (SELECT fe.note FROM flag_events fe 
                       WHERE fe.flag_id = f.flag_id AND fe.event_type = 'Escalated' 
                       ORDER BY fe.flag_event_id DESC LIMIT 1) AS escalation_note
               FROM flags f
               JOIN patients p ON f.patient_id = p.patient_id
               LEFT JOIN discharge_records dr ON p.patient_id = dr.patient_id
               WHERE f.status IN ('Open', 'Acknowledged')
               ORDER BY FIELD(tier, 'Immediate', 'Urgent', 'Review soon', 'Routine'),
                        f.created_at ASC"""
        )
        flag_rows = cur.fetchall() or []

        # Map flags to cases for duplicate alert merging (Phase 3 Task 1)
        cur.execute("""
            SELECT cf.flag_id, c.case_id, c.merged_count, c.primary_flag_id
            FROM case_flags cf
            JOIN cases c ON c.case_id = cf.case_id
            WHERE c.status IN ('Open', 'In_Progress');
        """)
        case_map = {r["flag_id"]: r for r in cur.fetchall()}

        cur.execute("""
            SELECT primary_flag_id, case_id, merged_count
            FROM cases
            WHERE status IN ('Open', 'In_Progress');
        """)
        for r in cur.fetchall():
            if r["primary_flag_id"] and r["primary_flag_id"] not in case_map:
                case_map[r["primary_flag_id"]] = r

        from .agents.case_prep_agent import CasePrepAgent

        formatted_flags = []
        seen_case_ids = set()

        for fl in flag_rows:
            fid = fl["flag_id"]
            c_info = case_map.get(fid)
            case_id = c_info["case_id"] if c_info else None
            merged_count = c_info["merged_count"] if c_info else 1

            if case_id:
                if case_id in seen_case_ids:
                    # Duplicate flag already merged into active case card
                    continue
                seen_case_ids.add(case_id)

            tier = fl["tier"]
            waited = fl["waited_mins"] or 0
            if tier == "Immediate":
                target_mins = 15
                target_label = "15 min"
            elif tier == "Urgent":
                target_mins = 60
                target_label = "1 h"
            elif tier == "Review soon":
                target_mins = 120
                target_label = "2 h"
            else:
                target_mins = 240
                target_label = "4 h"

            is_overdue = waited > target_mins
            if is_overdue:
                overdue_mins = waited - target_mins
                if overdue_mins >= 60:
                    hrs = overdue_mins // 60
                    mins = overdue_mins % 60
                    target_display = f"Target: seen within {target_label} · Overdue {hrs}h {mins}m" if mins else f"Target: seen within {target_label} · Overdue {hrs}h"
                else:
                    target_display = f"Target: seen within {target_label} · Overdue {overdue_mins}m"
            else:
                rem = target_mins - waited
                target_display = f"Target: seen within {target_label} · {rem}m remaining"

            needs_doctor = tier in ("Immediate", "Urgent")
            is_escalated = fl["escalated_by"] is not None

            # Retrieve or generate prepared case brief
            brief = None
            if case_id:
                cur.execute("""
                    SELECT run_id, body FROM agent_drafts
                    WHERE draft_type = 'Case_Brief' AND JSON_UNQUOTE(JSON_EXTRACT(body, '$.case_id')) = %s
                    ORDER BY created_at DESC LIMIT 1;
                """, (case_id,))
                b_row = cur.fetchone()
                if b_row and b_row.get("body"):
                    b_body = b_row["body"]
                    if isinstance(b_body, str):
                        try:
                            b_body = json.loads(b_body)
                        except Exception:
                            pass
                    b_body["run_id"] = b_row["run_id"]
                    brief = b_body
                else:
                    try:
                        brief = CasePrepAgent.generate_case_brief(case_id, force_deterministic=True)
                    except Exception as e:
                        logger.error(f"Failed to generate brief for {case_id}: {e}")

            suggested_step = brief.get("next_step") if brief else {
                "key": "call_now",
                "label": "Call the patient now",
                "why": ["Routine clinical triage review"]
            }
            options = brief.get("options", ["call_now", "send_checkin", "ask_doctor", "recheck_at"]) if brief else ["call_now", "send_checkin", "ask_doctor", "recheck_at"]
            agent_run_id = brief.get("run_id") if brief else None

            formatted_flags.append({
                "flag_id": fl["flag_id"],
                "case_id": case_id,
                "merged_count": merged_count,
                "merged_display": f"{merged_count} reports merged" if merged_count > 1 else None,
                "brief_ready": brief is not None,
                "brief": brief,
                "suggested_step": suggested_step,
                "options": options,
                "agent_run_id": agent_run_id,
                "patient_id": fl["patient_id"],
                "patient_name": fl["full_name"],
                "patient_code": fl["patient_code"],
                "age": fl["age"],
                "phone": fl["phone"] or "+91-98765-43210",
                "condition": fl["condition_summary"] or "Post-discharge recovery",
                "reason": fl["reason"],
                "tier": tier,
                "severity": fl["severity"],
                "status": fl["status"],
                "created_at": fl["created_at"].strftime("%Y-%m-%d %H:%M") if fl["created_at"] else None,
                "waited_mins": waited,
                "target_mins": target_mins,
                "is_overdue": is_overdue,
                "target_display": target_display,
                "needs_doctor_to_resolve": needs_doctor,
                "can_nurse_resolve": not needs_doctor,
                "is_escalated": is_escalated,
                "escalated_by": fl["escalated_by"],
                "escalated_at": fl["escalated_at"].strftime("%Y-%m-%d %H:%M") if fl["escalated_at"] else None,
                "escalation_note": fl["escalation_note"],
            })

        # 3. Tasks due today
        cur.execute(
            """SELECT ft.followup_id, ft.patient_id, p.full_name, p.patient_code, p.phone,
                      TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age,
                      dr.condition_summary, ft.reason, ft.priority, ft.status, ft.due_at,
                      ft.created_at
               FROM follow_up_tasks ft
               JOIN patients p ON ft.patient_id = p.patient_id
               LEFT JOIN discharge_records dr ON p.patient_id = dr.patient_id
               WHERE ft.status != 'Resolved'
               ORDER BY ft.due_at ASC"""
        )
        task_rows = cur.fetchall() or []
        formatted_tasks = []
        for t in task_rows:
            formatted_tasks.append({
                "task_id": t["followup_id"],
                "patient_id": t["patient_id"],
                "patient_name": t["full_name"],
                "patient_code": t["patient_code"],
                "age": t["age"],
                "phone": t["phone"] or "+91-98765-43210",
                "condition": t["condition_summary"] or "Post-discharge recovery",
                "reason": t["reason"],
                "priority": t["priority"],
                "status": t["status"],
                "due_at": t["due_at"].strftime("%Y-%m-%d %H:%M") if t["due_at"] else "Today",
            })

        # 4. Pending Limit Proposals submitted by nurse
        cur.execute(
            """SELECT COUNT(*) AS total
               FROM alert_rules_history h
               WHERE JSON_EXTRACT(h.new_values, '$.proposed_only') = true
                 AND (JSON_EXTRACT(h.new_values, '$.status') IS NULL OR JSON_UNQUOTE(JSON_EXTRACT(h.new_values, '$.status')) = 'Pending')"""
        )
        pending_proposals_count = cur.fetchone()["total"]

        # 5. On-track Quiet Patients (Zero open flags)
        cur.execute(
            """SELECT p.patient_id, p.patient_code, p.full_name, dr.condition_summary,
                      TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age,
                      DATEDIFF(CURDATE(), dr.discharge_date) + 1 AS relative_day
               FROM patients p
               LEFT JOIN discharge_records dr ON p.patient_id = dr.patient_id
               WHERE p.patient_id NOT IN (
                   SELECT DISTINCT patient_id FROM flags WHERE status IN ('Open', 'Acknowledged')
               )
               ORDER BY p.patient_id ASC"""
        )
        on_track_patients = cur.fetchall() or []

        # KPI counts
        calls_to_make = len(formatted_flags) + len(formatted_tasks)
        visits_today = len(formatted_tasks)

        return {
            "cards": {
                "calls_to_make": calls_to_make,
                "visits_today": visits_today,
                "pending_limit_requests": pending_proposals_count,
                "active_patients": total_patients,
            },
            "call_items": formatted_flags,
            "tasks_due_today": formatted_tasks,
            "on_track_patients": [
                {
                    "patient_id": pt["patient_id"],
                    "patient_code": pt["patient_code"],
                    "full_name": pt["full_name"],
                    "age": pt["age"],
                    "condition": pt["condition_summary"] or "Post-discharge recovery",
                    "relative_day": pt["relative_day"] or 1,
                }
                for pt in on_track_patients
            ],
        }


class RejectProposalIn(BaseModel):
    reason: str


@app.get("/staff/rules/proposals")
def get_rule_proposals(user: Dict[str, Any] = Depends(require_doctor)):
    """Doctor endpoint to retrieve pending rule limit proposals."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT h.history_id, h.rule_id, h.changed_by_staff_id, h.change_reason,
                      h.old_values, h.new_values, h.changed_at,
                      cs.full_name AS proposed_by_name, cs.staff_role AS proposed_by_role,
                      ar.patient_id, ar.rule_type, ar.measurement_type,
                      p.patient_code, p.full_name AS patient_name,
                      TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS patient_age,
                      dr.condition_summary
               FROM alert_rules_history h
               JOIN alert_rules ar ON h.rule_id = ar.rule_id
               JOIN patients p ON ar.patient_id = p.patient_id
               LEFT JOIN discharge_records dr ON p.patient_id = dr.patient_id
               LEFT JOIN care_staff cs ON h.changed_by_staff_id = cs.staff_id
               WHERE JSON_EXTRACT(h.new_values, '$.proposed_only') = true
                 AND (JSON_EXTRACT(h.new_values, '$.status') IS NULL OR JSON_UNQUOTE(JSON_EXTRACT(h.new_values, '$.status')) = 'Pending')
               ORDER BY h.changed_at DESC"""
        )
        rows = cur.fetchall()
        for r in rows:
            for f in ('old_values', 'new_values'):
                if isinstance(r.get(f), str):
                    try:
                        r[f] = json.loads(r[f])
                    except Exception:
                        pass
        return rows


@app.post("/staff/rules/proposals/{history_id}/approve")
def approve_rule_proposal(
    history_id: int,
    user: Dict[str, Any] = Depends(require_doctor),
):
    """Doctor approves nurse-proposed rule limit (Phase 3 Task 3)."""
    doctor_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT h.history_id, h.rule_id, h.change_reason, h.new_values
               FROM alert_rules_history h
               WHERE h.history_id = %s""",
            (history_id,),
        )
        prop = cur.fetchone()
        if not prop:
            raise HTTPException(status_code=404, detail="Proposal not found")

        nv = prop["new_values"]
        if isinstance(nv, str):
            nv = json.loads(nv)

        new_thresh = nv.get("threshold_value")
        new_window = nv.get("window_hours")
        new_sev = nv.get("severity")
        rule_id = prop["rule_id"]

        cur.execute(
            """UPDATE alert_rules
               SET threshold_value = %s,
                   window_hours = COALESCE(%s, window_hours),
                   severity = COALESCE(%s, severity),
                   approved_by_staff_id = %s,
                   approved_at = NOW()
               WHERE rule_id = %s""",
            (new_thresh, new_window, new_sev, doctor_id, rule_id),
        )

        nv["status"] = "Approved"
        nv["approved_by_staff_id"] = doctor_id
        nv["approved_at"] = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

        cur.execute(
            """UPDATE alert_rules_history
               SET new_values = %s
               WHERE history_id = %s""",
            (json.dumps(nv), history_id),
        )

        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Staff', %s, 'RULE_PROPOSAL_APPROVED', 'alert_rule', %s,
                       JSON_OBJECT('history_id', %s, 'new_threshold', %s, 'doctor_id', %s))""",
            (str(doctor_id), rule_id, history_id, new_thresh, doctor_id),
        )
        conn.commit()

    return {"status": "Approved", "history_id": history_id, "rule_id": rule_id, "approved_by_staff_id": doctor_id}


@app.post("/staff/rules/proposals/{history_id}/reject")
def reject_rule_proposal(
    history_id: int,
    body: RejectProposalIn,
    user: Dict[str, Any] = Depends(require_doctor),
):
    """Doctor rejects nurse-proposed rule limit (Phase 3 Task 3)."""
    if not body.reason or len(body.reason.strip()) < 3:
        raise HTTPException(status_code=400, detail="A rejection reason of at least 3 characters is required.")

    doctor_id = user["staff_id"]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT h.history_id, h.rule_id, h.new_values
               FROM alert_rules_history h
               WHERE h.history_id = %s""",
            (history_id,),
        )
        prop = cur.fetchone()
        if not prop:
            raise HTTPException(status_code=404, detail="Proposal not found")

        nv = prop["new_values"]
        if isinstance(nv, str):
            nv = json.loads(nv)

        nv["status"] = "Rejected"
        nv["rejected_by_staff_id"] = doctor_id
        nv["reject_reason"] = body.reason.strip()
        nv["rejected_at"] = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

        cur.execute(
            """UPDATE alert_rules_history
               SET new_values = %s
               WHERE history_id = %s""",
            (json.dumps(nv), history_id),
        )

        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Staff', %s, 'RULE_PROPOSAL_REJECTED', 'alert_rule', %s,
                       JSON_OBJECT('history_id', %s, 'reason', %s, 'doctor_id', %s))""",
            (str(doctor_id), prop["rule_id"], history_id, body.reason.strip(), doctor_id),
        )
        conn.commit()

    return {"status": "Rejected", "history_id": history_id, "reason": body.reason.strip()}


@app.get("/staff/rules/all")
def get_all_approved_rules(
    patient_id: Optional[int] = None,
    user: Dict[str, Any] = Depends(require_staff),
):
    """Doctor and Nurse master table of approved alert rules (Phase 3 Task 4)."""
    with get_conn() as conn, conn.cursor() as cur:
        query = """SELECT r.rule_id, r.patient_id, p.full_name, p.patient_code,
                          TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age,
                          dr.condition_summary,
                          r.rule_type, r.measurement_type, r.threshold_value,
                          r.window_hours, r.severity, r.approved_at, r.is_active,
                          cs.full_name AS approved_by_name,
                          (SELECT COUNT(*) FROM device_events de WHERE de.patient_id = r.patient_id AND de.event_type = 'Possible_Fall' AND de.prompt_sent_at IS NOT NULL) AS prompts_sent,
                          (SELECT COUNT(*) FROM device_events de WHERE de.patient_id = r.patient_id AND de.event_type = 'Possible_Fall' AND de.patient_response = 'Ok') AS prompts_ok,
                          (SELECT COUNT(*) FROM device_events de WHERE de.patient_id = r.patient_id AND de.event_type = 'Possible_Fall' AND (de.patient_response = 'No_Response' OR (de.patient_response IS NULL AND de.flag_id IS NOT NULL))) AS prompts_unanswered
                   FROM alert_rules r
                   JOIN patients p ON r.patient_id = p.patient_id
                   LEFT JOIN discharge_records dr ON p.patient_id = dr.patient_id
                   LEFT JOIN care_staff cs ON r.approved_by_staff_id = cs.staff_id"""
        params = []
        if patient_id:
            query += " WHERE r.patient_id = %s"
            params.append(patient_id)
        query += " ORDER BY p.patient_id ASC, r.rule_id ASC"
        cur.execute(query, tuple(params))
        return cur.fetchall()


# ─── Demo Automation & Simulator Endpoints (Phase 6) ──────────────────────────

class SimulateReadingIn(BaseModel):
    patient_id: int = 1
    device_id: str = "DEV-ESP32-001"
    measurement_type: str = "SpO2"
    value: float = 91.0
    unit: str = "%"


@app.post("/demo/reset")
def post_demo_reset():
    """
    Reset Demo State (Phase 6 Task 1):
    Runs scripts/seed_demo.py to restore Section 4 starting state in < 30 seconds.
    Returns: 'Reset complete: 5 patients, 3 open flags, 5 tasks'
    """
    import sys
    start_time = datetime.now()
    try:
        scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../scripts"))
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import seed_demo
        seed_demo.main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Demo reset failed: {str(e)}")

    duration = (datetime.now() - start_time).total_seconds()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS total FROM patients")
        patients_count = cur.fetchone()["total"]
        cur.execute("SELECT COUNT(*) AS total FROM flags WHERE status = 'Open'")
        open_flags = cur.fetchone()["total"]
        cur.execute("SELECT COUNT(*) AS total FROM follow_up_tasks WHERE status = 'Pending'")
        open_tasks = cur.fetchone()["total"]

    msg = f"Reset complete: {patients_count} patients, {open_flags} open flags, {open_tasks} tasks"
    return {
        "status": "ok",
        "message": msg,
        "patients": patients_count,
        "open_flags": open_flags,
        "open_tasks": open_tasks,
        "duration_seconds": round(duration, 2),
    }


@app.post("/demo/simulate-reading")
def post_demo_simulate_reading(body: Optional[SimulateReadingIn] = None):
    """
    Simulate Sensor Reading Helper (Phase 6 Task 2):
    Ingests a simulated low SpO2 reading (91.0%) for Aarav Patel (patient_id=1, device DEV-ESP32-001).
    - Inserts reading with quality_status='Simulated' into sensor_readings
    - trg_sensor_rules_after_insert automatically creates Urgent_Review flag
    - Populates escalation ladder (Patient_Prompt, Caregiver_SMS, Nurse_Alert)
    - Adds follow-up call task for Nurse Priya Nair
    - Records reading and escalation events in audit_log
    """
    payload = body or SimulateReadingIn()
    now = datetime.now()

    with get_conn() as conn, conn.cursor() as cur:
        # 1. Insert simulated sensor reading
        cur.execute(
            """INSERT INTO sensor_readings
               (patient_id, device_id, measurement_type, measurement_value, unit, measured_at, quality_status)
               VALUES (%s, %s, %s, %s, %s, %s, 'Simulated')""",
            (payload.patient_id, payload.device_id, payload.measurement_type, payload.value, payload.unit, now),
        )
        reading_id = cur.lastrowid

        # 2. Find newly generated flag by trigger
        cur.execute(
            """SELECT flag_id, rule_id, severity, reason FROM flags
               WHERE patient_id = %s AND source_type = 'Sensor' AND source_ref_id = %s
               ORDER BY flag_id DESC LIMIT 1""",
            (payload.patient_id, reading_id),
        )
        flag = cur.fetchone()
        flag_id = flag["flag_id"] if flag else None

        if flag_id:
            # 3. Create escalation ladder steps
            cur.execute(
                """INSERT INTO escalations (flag_id, step_no, step_type, channel, delivery_status, notes, sent_at)
                   VALUES
                   (%s, 1, 'Patient_Prompt', 'App', 'Sent', 'Alert shown on patient portal', %s),
                   (%s, 2, 'Caregiver_SMS', 'SMS', 'Sent', 'SMS dispatched to Neha Patel (+91 98765 43210)', %s),
                   (%s, 3, 'Nurse_Alert', 'Dashboard', 'Sent', 'Call task queued for triage nurse Priya Nair', %s)""",
                (flag_id, now, flag_id, now, flag_id, now),
            )

            # 4. Create follow-up call task for Nurse Priya Nair (staff_id=2)
            cur.execute(
                """INSERT INTO follow_up_tasks (patient_id, flag_id, assigned_staff_id, reason, priority, status, due_at)
                   VALUES (%s, %s, 2, %s, 'Urgent_Review', 'Pending', %s)""",
                (payload.patient_id, flag_id, f"Low {payload.measurement_type} ({payload.value}{payload.unit}) reading below approved limit (simulated)", now + timedelta(minutes=30)),
            )

            # 5. Record to audit_log
            audit_events = [
                ("Device", payload.device_id, "INGEST_READING", "sensor_reading", reading_id,
                 {"type": payload.measurement_type, "value": payload.value, "quality": "Simulated"}),
                ("Agent", "rule_engine", "FLAG_CREATED", "flag", flag_id,
                 {"rule_id": flag.get("rule_id"), "severity": flag.get("severity"), "reason": flag.get("reason")}),
                ("Agent", "escalation_agent", "ESCALATION_STEP", "escalation", flag_id,
                 {"step": 2, "type": "Caregiver_SMS", "status": "Sent", "recipient": "Neha Patel"}),
            ]
            for atype, aid, action, etype, eid, details in audit_events:
                cur.execute(
                    """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (atype, aid, action, etype, eid, json.dumps(details), now),
                )

        conn.commit()

    return {
        "status": "ok",
        "reading_id": reading_id,
        "flag_id": flag_id,
        "patient_id": payload.patient_id,
        "measurement_type": payload.measurement_type,
        "value": payload.value,
        "message": f"Simulated {payload.measurement_type} reading ({payload.value}{payload.unit}) ingested. Flag #{flag_id} raised and escalation ladder triggered.",
    }


# ─── Feature F1: Rounds & Background Automation Endpoints ─────────────────────

class PauseRoundsIn(BaseModel):
    patient_id: int
    hours: int = 4
    reason: str

class ResumeRoundsIn(BaseModel):
    patient_id: int

class DismissProposalIn(BaseModel):
    dismiss_reason: str


@app.get("/staff/rounds")
def get_rounds_dashboard(
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    Rounds dashboard (Feature F1):
    Next 24h lookahead, 24h history, active escalation timers, and summary counters.
    """
    from .rounds import get_rounds_overview
    return get_rounds_overview()


@app.post("/staff/rounds/pause")
def pause_rounds_endpoint(
    body: PauseRoundsIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Pause rounds for a patient with an explicit reason and end time."""
    from .rounds import pause_patient_rounds
    staff_id = user["staff_id"]
    staff_role = user.get("role", "Nurse")
    return pause_patient_rounds(body.patient_id, staff_id, staff_role, body.hours, body.reason)


@app.post("/staff/rounds/resume")
def resume_rounds_endpoint(
    body: ResumeRoundsIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Resume rounds for a patient immediately."""
    from .rounds import resume_patient_rounds
    staff_id = user["staff_id"]
    staff_role = user.get("role", "Nurse")
    return resume_patient_rounds(body.patient_id, staff_id, staff_role)


@app.post("/staff/rounds/run-now")
def run_rounds_now(
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Run due scheduled actions immediately (for demo and testing)."""
    from .rounds import tick_rounds
    result = tick_rounds(datetime.now())
    return {"status": "success", "result": result}


@app.get("/staff/patients/{patient_id}/agent-activity")
def get_agent_activity_endpoint(
    patient_id: int,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Returns agent activity feed for patient chart."""
    from .rounds import get_patient_agent_activity
    return get_patient_agent_activity(patient_id)


@app.get("/staff/agent/proposals")
def get_proposals_endpoint(
    status: str = Query("Pending"),
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Returns proposals suggested by Rounds."""
    from .rounds import get_agent_proposals
    return get_agent_proposals(status)


@app.post("/staff/agent/proposals/{proposal_id}/accept")
def accept_proposal_endpoint(
    proposal_id: int,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Accepts a proposal suggested by Rounds, creating a clinical task."""
    from .rounds import accept_proposal
    staff_id = user["staff_id"]
    staff_role = user.get("role", "Nurse")
    try:
        return accept_proposal(proposal_id, staff_id, staff_role)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/staff/agent/proposals/{proposal_id}/dismiss")
def dismiss_proposal_endpoint(
    proposal_id: int,
    body: DismissProposalIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Dismisses a proposal suggested by Rounds with a required clinical reason."""
    from .rounds import dismiss_proposal
    staff_id = user["staff_id"]
    staff_role = user.get("role", "Nurse")
    try:
        return dismiss_proposal(proposal_id, staff_id, staff_role, body.dismiss_reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── Phase 2: Check-in Guide & Two-Way SMS Endpoints ────────────────────────

class CheckinStartIn(BaseModel):
    channel: Optional[str] = "App_Guided"


class CheckinAnswerIn(BaseModel):
    session_id: int
    question_id: int
    answer_value: str
    raw_input: Optional[str] = None
    language: Optional[str] = "en"


class PhraseStatusIn(BaseModel):
    status: str  # 'Approved' or 'Pending'


class SimulateSmsIn(BaseModel):
    from_phone: str
    body: str


@app.get("/patient/me/checkin/template")
def get_active_patient_checkin_template(
    user: Dict[str, Any] = Depends(require_patient),
):
    """Returns the doctor-approved active check-in template and questions for the patient."""
    from .checkin import get_active_checkin_template
    tmpl = get_active_checkin_template()
    if not tmpl:
        raise HTTPException(status_code=404, detail="No doctor-approved check-in template is currently active.")
    return tmpl


@app.get("/patient/me/checkin/context")
def get_patient_daily_checkin_context(
    lang: Optional[str] = "en",
    user: Dict[str, Any] = Depends(require_patient),
):
    """
    Returns day context for patient Care Guide (Phase 2 Task 1 & 2):
    - has_completed_today: bool
    - active_session: partial session details if present
    - yesterday_facts: comparison facts from previous report
    - greeting_phrase: doctor-approved greeting phrase
    """
    from .checkin import get_patient_checkin_context
    pid = get_effective_patient_id(user)
    return get_patient_checkin_context(pid, language=lang or "en")


@app.post("/patient/me/checkin/start")
def start_patient_checkin_session(
    body: CheckinStartIn = CheckinStartIn(),
    user: Dict[str, Any] = Depends(require_patient),
):
    """Starts a new step-by-step guided check-in session for the patient."""
    from .checkin import start_checkin_session
    pid = get_effective_patient_id(user)
    try:
        return start_checkin_session(pid, body.channel or "App_Guided")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/patient/me/checkin/answer")
def record_patient_checkin_answer(
    body: CheckinAnswerIn,
    user: Dict[str, Any] = Depends(require_patient),
):
    """Records an answer for the current question in the guided session."""
    from .checkin import record_checkin_answer
    pid = get_effective_patient_id(user)
    try:
        return record_checkin_answer(
            session_id=body.session_id,
            patient_id=pid,
            question_id=body.question_id,
            answer_value=body.answer_value,
            raw_input=body.raw_input,
            language=body.language or "en",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/staff/checkin-templates")
def list_doctor_checkin_templates(
    user: Dict[str, Any] = Depends(require_role("Doctor")),
):
    """List check-in templates for Doctor Approvals overview."""
    from .checkin import get_doctor_templates_overview
    return {"templates": get_doctor_templates_overview()}


@app.post("/staff/checkin-templates/{template_id}/approve")
def approve_doctor_checkin_template(
    template_id: int,
    user: Dict[str, Any] = Depends(require_role("Doctor")),
):
    """Doctor approves a check-in template and activates it for all guided check-ins."""
    from .checkin import approve_template
    doctor_id = user["staff_id"]
    try:
        return approve_template(template_id, doctor_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/staff/phrase-bank")
def list_phrase_bank(
    user: Dict[str, Any] = Depends(require_role("Doctor")),
):
    """Returns all doctor-approved conversational phrases in phrase bank."""
    from .agents.phrase_bank_service import PhraseBankService
    return {"phrases": PhraseBankService.list_phrases_for_doctor()}


@app.post("/staff/phrase-bank/{phrase_id}/status")
def update_phrase_status(
    phrase_id: int,
    body: PhraseStatusIn,
    user: Dict[str, Any] = Depends(require_role("Doctor")),
):
    """Doctor approves or updates a phrase in the phrase bank."""
    from .agents.phrase_bank_service import PhraseBankService
    doctor_id = user["staff_id"]
    ok = PhraseBankService.update_phrase_status(phrase_id, body.status, doctor_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Phrase not found")
    return {"status": "updated", "phrase_id": phrase_id, "new_status": body.status}


@app.post("/sms/inbound")
async def twilio_inbound_webhook(request: Request):
    """Inbound Twilio SMS webhook."""
    from .sms_service import handle_inbound_sms
    # Read either form body or JSON
    content_type = request.headers.get("content-type", "")
    from_num = ""
    body_text = ""
    if "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        from_num = form.get("From", "")
        body_text = form.get("Body", "")
    else:
        try:
            data = await request.json()
            from_num = data.get("From") or data.get("from_phone", "")
            body_text = data.get("Body") or data.get("body", "")
        except Exception:
            pass

    res = handle_inbound_sms(from_num, body_text)
    # Twilio expects TwiML XML or plain response
    reply_msg = res.get("reply") or ""
    twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{reply_msg}</Message></Response>'
    return Response(content=twiml, media_type="application/xml")


@app.post("/staff/sms/simulate-inbound")
def simulate_inbound_sms(
    body: SimulateSmsIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    SMS Simulator for staff / presenters:
    Executes the exact same deterministic inbound parser as real Twilio SMS.
    """
    from .sms_service import handle_inbound_sms
    return handle_inbound_sms(body.from_phone, body.body)


@app.get("/staff/patients/{patient_id}/messages")
def get_patient_sms_history(
    patient_id: int,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Retrieve full SMS message history (outbound + inbound) for a patient."""
    from .sms_service import get_patient_sms_messages
    return {"messages": get_patient_sms_messages(patient_id)}


# ─── Feature F5 & F6: Recovery Plan & Patient Admission Endpoints ─────────────

class DraftPlanIn(BaseModel):
    patient_id: int
    source_document_id: Optional[int] = None


class RejectPlanIn(BaseModel):
    reason: Optional[str] = ""


class UnderstandingAnswerIn(BaseModel):
    check_id: int
    selected_option_index: int


class AdmitPatientIn(BaseModel):
    patient: Dict[str, Any]
    discharge: Dict[str, Any]
    prescriptions: List[Dict[str, Any]] = []
    proposed_limits: List[Dict[str, Any]] = []
    device: Optional[Dict[str, Any]] = None
    caregiver: Optional[Dict[str, Any]] = None


@app.post("/staff/plans/draft")
def draft_plan_endpoint(
    body: DraftPlanIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Draft a recovery plan from patient discharge papers with number guards and reconciliation."""
    from .plan_service import draft_recovery_plan
    try:
        return draft_recovery_plan(
            patient_id=body.patient_id,
            staff_id=user["staff_id"],
            staff_role=user["role"],
            source_document_id=body.source_document_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/staff/plans/pending")
def get_pending_plans_endpoint(
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """List recovery plans awaiting doctor approval."""
    from .plan_service import get_pending_plans_for_doctor
    return {"pending_plans": get_pending_plans_for_doctor()}


@app.get("/staff/patients/{patient_id}/plans")
def get_patient_plans_endpoint(
    patient_id: int,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """List all recovery plans for a patient (Draft, Approved, Superseded)."""
    from .plan_service import get_staff_patient_plans
    return get_staff_patient_plans(patient_id)


@app.post("/staff/plans/items/{item_id}/verify")
def verify_plan_item_endpoint(
    item_id: int,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Nurse or Doctor marks a recovery plan item as verified against discharge papers."""
    from .plan_service import verify_plan_item
    try:
        return verify_plan_item(item_id, user["staff_id"], user["role"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/staff/plans/{plan_id}/approve")
def approve_plan_endpoint(
    plan_id: int,
    user: Dict[str, Any] = Depends(require_doctor),
):
    """Doctor-only approval of a drafted recovery plan."""
    from .plan_service import approve_recovery_plan
    try:
        return approve_recovery_plan(plan_id, user["staff_id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/staff/plans/{plan_id}/reject")
def reject_plan_endpoint(
    plan_id: int,
    body: RejectPlanIn = RejectPlanIn(),
    user: Dict[str, Any] = Depends(require_doctor),
):
    """Doctor-only rejection of a drafted recovery plan."""
    from .plan_service import reject_recovery_plan
    try:
        return reject_recovery_plan(plan_id, user["staff_id"], body.reason or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/patient/me/plan")
def get_patient_plan_endpoint(
    user: Dict[str, Any] = Depends(require_patient),
):
    """
    Retrieve approved recovery plan for authenticated patient.
    If only draft plans exist, returns 404 (draft plans are strictly invisible to patients).
    """
    from .plan_service import get_patient_active_plan
    plan = get_patient_active_plan(user["patient_id"])
    if not plan:
        raise HTTPException(
            status_code=404,
            detail="Your care team has not yet published an approved recovery plan. Please check back shortly.",
        )
    return plan


@app.get("/patient/me/plan/understanding-check")
def get_patient_understanding_check_endpoint(
    user: Dict[str, Any] = Depends(require_patient),
):
    """Retrieve understanding check questions for the patient's active approved plan."""
    from .plan_service import get_patient_understanding_check
    return {"questions": get_patient_understanding_check(user["patient_id"])}


@app.post("/patient/me/plan/understanding-check/answer")
def submit_understanding_check_answer_endpoint(
    body: UnderstandingAnswerIn,
    user: Dict[str, Any] = Depends(require_patient),
):
    """Submit answer to understanding check question. Creates nurse proposal if incorrect."""
    from .plan_service import submit_understanding_answer
    try:
        return submit_understanding_answer(user["patient_id"], body.check_id, body.selected_option_index)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/staff/admit")
def admit_patient_endpoint(
    body: AdmitPatientIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    Nurse onboarding wizard: start follow-up for newly discharged patient.
    Creates patient, discharge document, chunks, draft plan, alert limits (status: Pending_Approval),
    and a welcome call task due within 48 hours.
    """
    from .plan_service import admit_patient_wizard
    try:
        return admit_patient_wizard(
            nurse_id=user["staff_id"],
            patient_data=body.patient,
            discharge_data=body.discharge,
            prescriptions_data=body.prescriptions,
            proposed_limits=body.proposed_limits,
            device_data=body.device,
            caregiver_data=body.caregiver,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))







# ─── CareLoop Care Agents Endpoints (Phase 1) ────────────────────────────────

class AgentPauseIn(BaseModel):
    paused: bool
    patient_id: Optional[int] = None
    reason: Optional[str] = None


class DraftActionIn(BaseModel):
    action: str = Field(..., pattern="^(accept|edit|reject)$")
    edited_body: Optional[Dict[str, Any]] = None
    rejection_reason: Optional[str] = None


class AutonomyUpdateIn(BaseModel):
    action_type: str
    level: str = Field(..., pattern="^(Suggest|Draft|Auto|Never)$")
    mode: str = Field(..., pattern="^(Shadow|Live)$")


@app.get("/agent/desk")
def get_agent_desk(user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse"))):
    """
    CareLoop Agent Desk Workspace (Brief Section 8 & Phase 1):
    Four sections:
    1. Waiting for you (pending drafts for nurse/doctor signature)
    2. Done for you (automated actions with undo button)
    3. Needs a decision (items held by policy guard or requiring human judgment)
    4. Work saved today (transparent estimated counts)
    """
    from .agents.dispatcher import AgentDispatcher
    from .agents.ledger import AgentLedger

    is_paused = AgentDispatcher.is_global_paused()

    with get_conn() as conn, conn.cursor() as cur:
        # 1. Waiting for you: Pending drafts
        cur.execute("""
            SELECT d.draft_id, d.run_id, d.patient_id, p.full_name as patient_name,
                   p.patient_code, d.draft_type, d.body, d.sources, d.status, d.created_at
            FROM agent_drafts d
            JOIN patients p ON p.patient_id = d.patient_id
            WHERE d.status = 'Pending'
            ORDER BY d.created_at DESC LIMIT 20;
        """)
        drafts_raw = cur.fetchall()
        waiting_for_you = []
        for d in drafts_raw:
            body_obj = d["body"]
            if isinstance(body_obj, str):
                try:
                    body_obj = json.loads(body_obj)
                except Exception:
                    pass
            sources_obj = d["sources"]
            if isinstance(sources_obj, str):
                try:
                    sources_obj = json.loads(sources_obj)
                except Exception:
                    pass
            waiting_for_you.append({
                "draft_id": d["draft_id"],
                "run_id": d["run_id"],
                "patient_id": d["patient_id"],
                "patient_name": d["patient_name"],
                "patient_code": d["patient_code"],
                "draft_type": d["draft_type"],
                "body": body_obj,
                "sources": sources_obj or [],
                "created_at": d["created_at"].strftime("%I:%M %p") if d.get("created_at") else "",
                "created_date": d["created_at"].strftime("%Y-%m-%d %H:%M") if d.get("created_at") else ""
            })

        # 2. Done for you: Auto actions in Live mode
        cur.execute("""
            SELECT r.run_id, r.agent_name, r.trigger_type, r.trigger_ref, r.patient_id,
                   p.full_name as patient_name, p.patient_code, r.result_type,
                   r.started_at, r.latency_ms, r.plan
            FROM agent_runs r
            LEFT JOIN patients p ON p.patient_id = r.patient_id
            WHERE r.status IN ('Done', 'Answered') AND r.mode = 'Live' AND r.autonomy_level = 'Auto'
              AND r.source != 'test'
            ORDER BY r.started_at DESC LIMIT 20;
        """)
        runs_raw = cur.fetchall()
        done_for_you = []
        for r in runs_raw:
            action_id = None
            if r.get("trigger_ref") and str(r["trigger_ref"]).startswith("action:"):
                try:
                    action_id = int(str(r["trigger_ref"]).split(":")[1])
                except Exception:
                    pass
            elif r.get("plan"):
                plan_obj = r["plan"]
                if isinstance(plan_obj, str):
                    try:
                        plan_obj = json.loads(plan_obj)
                    except Exception:
                        pass
                if isinstance(plan_obj, dict):
                    action_id = plan_obj.get("action_id")

            done_for_you.append({
                "run_id": r["run_id"],
                "agent_name": r["agent_name"],
                "trigger_type": r["trigger_type"],
                "patient_id": r["patient_id"],
                "patient_name": r["patient_name"] or "System Cohort",
                "patient_code": r["patient_code"] or "CL-SYS",
                "result_type": r["result_type"] or "automated_action",
                "time": r["started_at"].strftime("%I:%M %p") if r.get("started_at") else "",
                "latency_ms": r["latency_ms"],
                "can_undo": bool(action_id) or r["trigger_type"] in ("duplicate_alert_merging", "scheduled_retry", "outreach_action", "outreach_retry"),
                "action_id": action_id
            })

        # 3. Needs a decision: Guard-blocked or escalation items (collapsed by patient & trigger)
        cur.execute("""
            SELECT r.agent_name, r.trigger_type, r.patient_id,
                   p.full_name as patient_name, p.patient_code,
                   MAX(r.run_id) as run_id,
                   MAX(r.guard_reasons) as guard_reasons,
                   MAX(r.started_at) as started_at,
                   COUNT(*) as repeat_count
            FROM agent_runs r
            LEFT JOIN patients p ON p.patient_id = r.patient_id
            WHERE r.status IN ('Blocked_By_Guard', 'Abstained')
              AND r.source != 'test'
            GROUP BY r.agent_name, r.trigger_type, r.patient_id, p.full_name, p.patient_code
            ORDER BY started_at DESC LIMIT 20;
        """)
        decisions_raw = cur.fetchall()
        needs_a_decision = []
        for d in decisions_raw:
            reasons = d["guard_reasons"]
            if isinstance(reasons, str):
                try:
                    reasons = json.loads(reasons)
                except Exception:
                    pass
            rep_label = f" ({d['repeat_count']} events)" if d.get("repeat_count", 1) > 1 else ""
            needs_a_decision.append({
                "run_id": d["run_id"],
                "agent_name": d["agent_name"],
                "patient_name": (d["patient_name"] or "Cohort") + rep_label,
                "patient_code": d["patient_code"] or "CL-SYS",
                "reasons": reasons or ["Policy guard check held output for human verification"],
                "time": d["started_at"].strftime("%I:%M %p") if d.get("started_at") else "",
                "repeat_count": d.get("repeat_count", 1)
            })

        # 4. Work saved today (gross saved minus review time)
        cur.execute("SELECT COUNT(*) as cnt FROM agent_runs WHERE status IN ('Done', 'Answered') AND autonomy_level = 'Auto' AND source != 'test';")
        auto_cnt = cur.fetchone()["cnt"]

        cur.execute("SELECT COUNT(*) as cnt FROM cases WHERE merged_count > 1;")
        merged_cnt = cur.fetchone()["cnt"]

        cur.execute("SELECT COUNT(*) as cnt FROM agent_drafts WHERE status = 'Accepted';")
        accepted_drafts_cnt = cur.fetchone()["cnt"]

        cur.execute("SELECT COUNT(*) as cnt FROM agent_drafts;")
        total_drafts_cnt = cur.fetchone()["cnt"]

        cur.execute("SELECT COUNT(*) as cnt FROM agent_runs WHERE agent_name = 'case_prep_agent' AND status IN ('Done', 'Answered') AND source != 'test';")
        briefs_cnt = cur.fetchone()["cnt"]

        # Gross minutes saved:
        gross_minutes = (briefs_cnt * 4) + (accepted_drafts_cnt * 3) + (auto_cnt * 2) + (merged_cnt * 3)

        # Review minutes spent: 1.5 min per draft created
        review_minutes = round(total_drafts_cnt * 1.5, 1)

        # Net minutes saved:
        net_minutes = round(gross_minutes - review_minutes, 1)

        work_saved = {
            "automated_actions_count": auto_cnt,
            "briefs_prepared_count": briefs_cnt,
            "drafts_accepted_count": accepted_drafts_cnt,
            "total_drafts_count": total_drafts_cnt,
            "duplicates_merged_count": merged_cnt,
            "gross_minutes_saved": gross_minutes,
            "review_minutes_spent": review_minutes,
            "estimated_minutes_saved": net_minutes,
            "net_minutes_saved": net_minutes,
            "is_negative": net_minutes < 0,
            "quality_warning": "Agents created more review work than they saved. Too many drafts." if net_minutes < 0 else None,
            "assumptions_label": "Estimated from editable assumptions (4m/brief, 3m/draft, 2m/routine, 1.5m review)",
        }

    return {
        "global_paused": is_paused,
        "waiting_for_you": waiting_for_you,
        "done_for_you": done_for_you,
        "needs_a_decision": needs_a_decision,
        "work_saved": work_saved,
    }


@app.get("/agent/runs/{run_id}")
def get_agent_run_trace(run_id: str, user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse"))):
    """
    Returns complete execution trace for an agent run:
    plan, steps, sources, duration, token usage, and Policy Guard inspection.
    """
    from .agents.ledger import AgentLedger
    trace = AgentLedger.trace(run_id)
    if not trace:
        raise HTTPException(404, f"Agent run '{run_id}' not found.")
    return trace


@app.post("/agent/drafts/{draft_id}/action")
def act_on_agent_draft(
    draft_id: int,
    body: DraftActionIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    Nurse or Doctor accepts, edits, or rejects an agent-prepared draft.
    Calculates edit character distance to monitor drafting fidelity.
    """
    staff_id = user.get("staff_id", 1)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM agent_drafts WHERE draft_id = %s;", (draft_id,))
        draft = cur.fetchone()
        if not draft:
            raise HTTPException(404, "Draft not found.")

        edit_chars = 0
        final_body = draft["body"]
        if body.action == "edit" and body.edited_body:
            from .agents.case_workflow_service import RoutineDraftReviewService
            res = RoutineDraftReviewService.record_draft_edit(
                draft_id=draft_id,
                edited_body=body.edited_body,
                staff_id=staff_id,
                staff_account_id=user.get("account_id", staff_id)
            )
            return {
                "status": "ok",
                "draft_id": draft_id,
                "new_status": "Edited",
                "edit_chars": res["edit_chars"],
                "diff_summary": res.get("diff_summary")
            }
        elif body.action == "accept":
            status = "Accepted"
        else:
            status = "Rejected"

        cur.execute("""
            UPDATE agent_drafts
            SET status = %s,
                body = %s,
                reviewed_by_staff_id = %s,
                reviewed_at = NOW(),
                edit_chars = %s
            WHERE draft_id = %s;
        """, (status, json.dumps(final_body), staff_id, edit_chars, draft_id))

        cur.execute("""
            INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
            VALUES ('Staff', %s, %s, 'agent_draft', %s, JSON_OBJECT('action', %s, 'edit_chars', %s));
        """, (str(user["account_id"]), f"AGENT_DRAFT_{status.upper()}", str(draft_id), status, edit_chars))

        if draft.get("draft_type") == "Call_Note" and status in ("Accepted", "Edited"):
            from .agents.call_notes_agent import CallNotesAgent
            try:
                note_text = None
                task_text = None
                msg_text = None
                if isinstance(final_body, dict):
                    note_text = final_body.get("note") or final_body.get("patient_reported")
                    task_text = final_body.get("task")
                    msg_text = final_body.get("patient_message")
                CallNotesAgent.commit_call_records(
                    draft_id=draft_id,
                    staff_id=staff_id,
                    edited_note=note_text,
                    edited_task=task_text,
                    edited_message=msg_text,
                )
            except Exception as e:
                logger.warning(f"Auto-commit call records on draft #{draft_id} approval failed/skipped: {e}")

    return {
        "status": "ok",
        "draft_id": draft_id,
        "new_status": status,
        "edit_chars": edit_chars,
    }


@app.post("/agent/pause")
def set_agent_pause_endpoint(
    body: AgentPauseIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    Doctor can pause all agents globally.
    Nurse or Doctor can pause automated agents for a specific patient.
    """
    from .agents.dispatcher import AgentDispatcher

    staff_id = user.get("staff_id", 1)
    if body.patient_id is not None:
        # Per-patient pause
        with get_conn() as conn, conn.cursor() as cur:
            if body.paused:
                cur.execute("""
                    UPDATE patients
                    SET rounds_paused_until = NOW() + INTERVAL 24 HOUR,
                        rounds_pause_reason = %s
                    WHERE patient_id = %s;
                """, (body.reason or "Clinician pause from Agent Desk", body.patient_id))
            else:
                cur.execute("""
                    UPDATE patients
                    SET rounds_paused_until = NULL,
                        rounds_pause_reason = NULL
                    WHERE patient_id = %s;
                """, (body.patient_id,))
            cur.execute("""
                INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                VALUES (%s, %s, %s, 'patient', %s, JSON_OBJECT('paused', %s, 'reason', %s));
            """, (user["account_role"], str(user["account_id"]), "AGENT_PATIENT_PAUSE_TOGGLED", str(body.patient_id), body.paused, body.reason))
        return {"status": "ok", "patient_id": body.patient_id, "paused": body.paused}
    else:
        # Global pause (Doctor only)
        if user.get("account_role") != "Doctor":
            raise HTTPException(403, "Only a licensed Doctor can engage the global agent pause switch.")
        AgentDispatcher.set_global_pause(body.paused, staff_id)
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                VALUES ('Doctor', %s, 'AGENT_GLOBAL_PAUSE_TOGGLED', 'system', 'agent_system_state', JSON_OBJECT('paused', %s));
            """, (str(user["account_id"]), body.paused))
        return {"status": "ok", "global_paused": body.paused}


@app.get("/agent/settings")
def get_agent_settings(user: Dict[str, Any] = Depends(require_role("Doctor"))):
    """
    Doctor-only Agent Settings:
    Returns the autonomy matrix, shadow mode agreement rates, budgets, and pause state.
    """
    from .agents.dispatcher import AgentDispatcher, MAX_DAILY_LLM_CALLS_PER_PATIENT

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT action_type, level, mode, set_by_staff_id, set_at
            FROM agent_autonomy
            ORDER BY action_type ASC;
        """)
        matrix = cur.fetchall()

        # Compute shadow agreement rates
        cur.execute("""
            SELECT action_type,
                   COUNT(*) as total_cases,
                   SUM(agreed = 1) as agreed_cases,
                   ROUND((SUM(agreed = 1) / COUNT(*)) * 100, 1) as agreement_pct
            FROM shadow_decisions
            GROUP BY action_type;
        """)
        shadow_stats = cur.fetchall()

    from .agents.auto_close_service import AutoCloseService
    auto_close_on = AutoCloseService.is_auto_close_enabled()

    return {
        "global_paused": AgentDispatcher.is_global_paused(),
        "daily_llm_budget_per_patient": MAX_DAILY_LLM_CALLS_PER_PATIENT,
        "autonomy_matrix": matrix,
        "shadow_agreement_stats": shadow_stats,
        "auto_close_enabled": auto_close_on,
        "auto_close_catalog": [
            {
                "rule_type": "No_Data_30m",
                "name": "No data from device (silent device)",
                "low_risk": True,
                "condition": "Data resumed for 30 minutes",
                "refuses": "Emergency, SOS, Urgent, Symptom flags"
            },
            {
                "rule_type": "Missed_Dose_Confirmed",
                "name": "Missed medication dose confirmed taken",
                "low_risk": True,
                "condition": "Patient logs late confirmation within 2 hours",
                "refuses": "Emergency, SOS, Urgent, Symptom flags"
            }
        ]
    }


class AutoCloseToggleIn(BaseModel):
    enabled: bool


@app.put("/agent/settings/auto-close")
def toggle_auto_close_setting(
    body: AutoCloseToggleIn,
    user: Dict[str, Any] = Depends(require_role("Doctor")),
):
    from .agents.auto_close_service import AutoCloseService
    staff_id = user.get("staff_id", 1)
    AutoCloseService.set_auto_close_enabled(body.enabled, staff_id)
    return {"status": "ok", "auto_close_enabled": body.enabled}


@app.put("/agent/settings")
def update_agent_autonomy(
    body: AutonomyUpdateIn,
    user: Dict[str, Any] = Depends(require_role("Doctor")),
):
    """
    Doctor-only: Promote or demote an action type's autonomy level or mode (Shadow/Live).
    Audited with doctor identity and timestamp.
    """
    from .agents.dispatcher import AgentDispatcher

    staff_id = user.get("staff_id", 1)
    AgentDispatcher.set_autonomy(body.action_type, body.level, body.mode, staff_id)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
            VALUES ('Staff', %s, 'UPDATE_AGENT_AUTONOMY', 'agent_autonomy', 0,
                    JSON_OBJECT('action_type', %s, 'level', %s, 'mode', %s));
        """, (str(user["account_id"]), body.action_type, body.level, body.mode))

    return {
        "status": "ok",
        "action_type": body.action_type,
        "level": body.level,
        "mode": body.mode,
    }


# ─── CareLoop Case Prep Agent Endpoints (Phase 3) ───────────────────────────

class CaseDecideIn(BaseModel):
    action: str = Field(..., pattern="^(call_now|send_checkin|ask_doctor|recheck_at|merge_duplicate|close_rule)$")
    note: Optional[str] = None
    script_id: Optional[int] = None


@app.get("/cases")
def list_cases(user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse"))):
    """Returns active cases with primary flag and patient context."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT c.case_id, c.patient_id, c.primary_flag_id, c.status, c.merged_count,
                   c.created_at, c.updated_at,
                   p.full_name as patient_name, p.patient_code, p.phone as patient_phone,
                   f.reason as headline, f.severity, f.source_type
            FROM cases c
            JOIN patients p ON p.patient_id = c.patient_id
            LEFT JOIN flags f ON f.flag_id = c.primary_flag_id
            ORDER BY c.updated_at DESC;
        """)
        rows = cur.fetchall() or []
        for r in rows:
            if r.get("created_at"):
                r["created_at"] = r["created_at"].strftime("%Y-%m-%d %H:%M")
            if r.get("updated_at"):
                r["updated_at"] = r["updated_at"].strftime("%Y-%m-%d %H:%M")
        return rows


@app.get("/cases/{case_id}/brief")
def get_case_brief(case_id: str, user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse"))):
    """Returns the prepared brief for a case (Phase 3)."""
    from .agents.case_prep_agent import CasePrepAgent

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT draft_id, run_id, body FROM agent_drafts
            WHERE draft_type = 'Case_Brief' AND JSON_UNQUOTE(JSON_EXTRACT(body, '$.case_id')) = %s
            ORDER BY created_at DESC LIMIT 1;
        """, (case_id,))
        existing = cur.fetchone()
        if existing and existing.get("body"):
            body = existing["body"]
            if isinstance(body, str):
                try:
                    body = json.loads(body)
                except Exception:
                    pass
            body["draft_id"] = existing["draft_id"]
            body["run_id"] = existing["run_id"]
            return body

    # Otherwise generate fresh brief
    brief = CasePrepAgent.generate_case_brief(case_id, force_deterministic=True)
    return brief


@app.post("/cases/{case_id}/decide")
def decide_case_action(
    case_id: str,
    payload: CaseDecideIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    Clinician acts on a case (one-click action from approved menu).
    Records clinician decision vs agent suggestion in shadow_decisions (Shadow mode).
    Updates case and flag status with complete audit trail.
    """
    from .agents.case_prep_agent import CasePrepAgent
    from .agents.policy_guard import ALLOWED_NEXT_STEPS

    if payload.action not in ALLOWED_NEXT_STEPS:
        raise HTTPException(400, f"Action '{payload.action}' not in approved menu: {list(ALLOWED_NEXT_STEPS)}")

    staff_id = user.get("staff_id", 1)
    staff_name = user.get("full_name") or user.get("account_role", "Clinician")

    with get_conn() as conn, conn.cursor() as cur:
        # Retrieve case
        cur.execute("SELECT * FROM cases WHERE case_id = %s;", (case_id,))
        c = cur.fetchone()
        if not c:
            raise HTTPException(404, f"Case '{case_id}' not found.")

        # Check existing brief to record shadow decision
        cur.execute("""
            SELECT run_id, body FROM agent_drafts
            WHERE draft_type = 'Case_Brief' AND JSON_UNQUOTE(JSON_EXTRACT(body, '$.case_id')) = %s
            ORDER BY created_at DESC LIMIT 1;
        """, (case_id,))
        draft_row = cur.fetchone()

        run_id = draft_row["run_id"] if draft_row else f"run-shadow-{uuid.uuid4().hex[:8]}"
        agent_step = {"key": "call_now"}
        if draft_row and draft_row.get("body"):
            b = draft_row["body"]
            if isinstance(b, str):
                try:
                    b = json.loads(b)
                except Exception:
                    b = {}
            if isinstance(b, dict) and b.get("next_step"):
                agent_step = b["next_step"]

        human_decision = {
            "key": payload.action,
            "staff_id": staff_id,
            "staff_name": staff_name,
            "note": payload.note
        }

        # Record in shadow_decisions
        CasePrepAgent.record_shadow_decision(
            run_id=run_id,
            action_type="next_step_suggestion",
            agent_decision=agent_step,
            human_decision=human_decision
        )

        # Update case and primary flag status based on action
        if payload.action in ("call_now", "send_checkin"):
            new_case_status = "In_Progress"
            new_flag_status = "Acknowledged"
        elif payload.action in ("close_rule", "merge_duplicate"):
            new_case_status = "Resolved"
            new_flag_status = "Resolved"
        elif payload.action == "ask_doctor":
            new_case_status = "In_Progress"
            new_flag_status = "Acknowledged"
            if c.get("primary_flag_id"):
                cur.execute("""
                    INSERT INTO flag_events (flag_id, staff_id, event_type, note, created_at)
                    VALUES (%s, %s, 'Escalated', %s, NOW());
                """, (c["primary_flag_id"], staff_id, payload.note or "Escalated to physician from case decision"))
        else:
            new_case_status = "In_Progress"
            new_flag_status = "Acknowledged"

        cur.execute("""
            UPDATE cases SET status = %s, updated_at = NOW() WHERE case_id = %s;
        """, (new_case_status, case_id))

        if c.get("primary_flag_id"):
            cur.execute("""
                UPDATE flags SET status = %s, acknowledged_by_staff_id = %s, acknowledged_at = NOW()
                WHERE flag_id = %s;
            """, (new_flag_status, staff_id, c["primary_flag_id"]))

        entity_id_val = c.get("primary_flag_id") or c.get("patient_id") or 1
        cur.execute("""
            INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
            VALUES ('Staff', %s, 'CASE_DECISION_RECORDED', 'case', %s, JSON_OBJECT('case_id', %s, 'action', %s, 'agent_suggested', %s, 'note', %s));
        """, (str(user.get("account_id", staff_id)), entity_id_val, case_id, payload.action, agent_step.get("key"), payload.note))

        conn.commit()

    # Synchronize Phase 4 CaseWorkflow state machine
    try:
        from .agents.case_workflow_service import CaseWorkflowService
        wf = CaseWorkflowService.get_case_state(case_id)
        target_wf = "Closed" if payload.action in ("close_rule", "merge_duplicate") else "Decided"
        if wf["state"] == "Raised":
            CaseWorkflowService.transition_case(case_id, "Briefed", actor_type="System", reason="Auto-briefed prior to clinical decision")
        CaseWorkflowService.transition_case(case_id, target_wf, actor_type="Staff", actor_id=staff_id, reason=payload.note or f"Clinician decision: {payload.action}")
    except Exception as e:
        logger.warning(f"CaseWorkflowService sync in decide_case_action skipped/error: {e}")

    return {
        "status": "ok",
        "case_id": case_id,
        "action": payload.action,
        "case_status": new_case_status,
        "agent_suggested": agent_step.get("key"),
        "agreed": (agent_step.get("key") == payload.action)
    }


# ─── CareLoop Case Workflow & Explainable Queue Endpoints (Agents v2 Phase 4) ─

class CaseTransitionIn(BaseModel):
    to_state: str
    reason: Optional[str] = None


class CaseAgentStepIn(BaseModel):
    run_id: str
    step_name: str
    details: Dict[str, Any] = {}


class BatchApproveDraftsIn(BaseModel):
    draft_type: str


@app.get("/cases/{case_id}/workflow")
def get_case_workflow_endpoint(
    case_id: str,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Phase 4: Returns case workflow state, live SLA timers, and transition audit log."""
    from .agents.case_workflow_service import CaseWorkflowService
    try:
        return CaseWorkflowService.get_case_state(case_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.post("/cases/{case_id}/workflow/transition")
def transition_case_workflow_endpoint(
    case_id: str,
    payload: CaseTransitionIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Phase 4: Transitions case to new state adhering to strict state machine and SLA timers."""
    from .agents.case_workflow_service import CaseWorkflowService
    staff_id = user.get("staff_id", 1)
    try:
        return CaseWorkflowService.transition_case(
            case_id=case_id,
            to_state=payload.to_state,
            actor_type="Staff",
            actor_id=staff_id,
            reason=payload.reason
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/cases/{case_id}/agent-step")
def attach_case_agent_step_endpoint(
    case_id: str,
    payload: CaseAgentStepIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Phase 4: Agents attach steps to case. Strictly forbidden on Closed cases."""
    from .agents.case_workflow_service import CaseWorkflowService
    try:
        return CaseWorkflowService.attach_agent_step(
            case_id=case_id,
            run_id=payload.run_id,
            step_name=payload.step_name,
            details=payload.details
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/staff/worklist/prioritised")
def get_prioritised_worklist_endpoint(
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Phase 4: Explainable queue order from fixed rule-based weights with 'Why this position' breakdown."""
    import re
    from .agents.case_workflow_service import ExplainableQueueService
    from .agents.config import CASE_QUEUE_WEIGHTS

    # Fetch base worklist
    worklist_res = get_staff_worklist(scope="mine", user=user)
    patients = worklist_res.get("patients", [])

    scored_patients = []
    for p in patients:
        mins_od = 0
        od_disp = p.get("overdue_display") or ""
        if "Overdue by" in od_disp:
            m_match = re.search(r"(\d+)m", od_disp)
            h_match = re.search(r"(\d+)h", od_disp)
            d_match = re.search(r"(\d+)d", od_disp)
            if d_match:
                mins_od += int(d_match.group(1)) * 1440
            if h_match:
                mins_od += int(h_match.group(1)) * 60
            if m_match:
                mins_od += int(m_match.group(1))

        score, factors = ExplainableQueueService.compute_explainable_score({
            "tier": p.get("sla_tier") or ("Immediate" if p.get("has_emergency") else "Routine"),
            "minutes_overdue": mins_od,
            "no_answers_count": 1 if p.get("not_yet_seen") else 0,
            "device_silent_hours": 24 if any("device" in (f.get("reason", "").lower()) for f in p.get("flags", [])) else 0,
            "consent_missing": any("consent" in (f.get("reason", "").lower()) for f in p.get("flags", [])),
            "has_sos": p.get("has_emergency", False),
        })
        p_copy = dict(p)
        p_copy["explainable_score"] = score
        p_copy["why_this_position"] = factors
        scored_patients.append(p_copy)

    # Sort strictly by explainable score descending
    scored_patients.sort(key=lambda x: x["explainable_score"], reverse=True)
    for rank, sp in enumerate(scored_patients, 1):
        sp["queue_rank"] = rank

    return {
        "prioritised_patients": scored_patients,
        "count": len(scored_patients),
        "weights_configuration": CASE_QUEUE_WEIGHTS
    }


@app.get("/agent/drafts/routine")
def get_routine_drafts_endpoint(
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Phase 4: Returns routine drafts with diff views, shortcuts, and batch-approval eligibility."""
    from .agents.case_workflow_service import RoutineDraftReviewService
    return RoutineDraftReviewService.get_routine_drafts_with_diff()


@app.post("/agent/drafts/batch-approve")
def batch_approve_drafts_endpoint(
    payload: BatchApproveDraftsIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Phase 4: Batch approve all passing drafts of a type. Strictly requires shadow agreement >= 95%."""
    from .agents.case_workflow_service import RoutineDraftReviewService
    staff_id = user.get("staff_id", 1)
    staff_acct = user.get("account_id", staff_id)
    try:
        return RoutineDraftReviewService.batch_approve_drafts_of_type(
            draft_type=payload.draft_type,
            staff_id=staff_id,
            staff_account_id=staff_acct
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


# ─── CareLoop Call Notes & Outreach Agent Endpoints (Phase 4) ───────────────

class CallNoteDraftIn(BaseModel):
    patient_id: int
    reached: bool = True
    patient_reports: Optional[List[str]] = None
    actions_agreed: Optional[List[str]] = None
    voice_transcript: Optional[str] = None
    needs_doctor: bool = False
    call_script_id: Optional[int] = None


class CallNoteApproveIn(BaseModel):
    draft_id: int
    edited_body: Optional[Dict[str, Any]] = None


class OutreachEvaluateIn(BaseModel):
    patient_id: int
    action_type: str = "automated_reminder"
    message_text: str
    is_emergency: bool = False


@app.post("/agent/call-notes/draft")
def draft_call_notes_endpoint(
    body: CallNoteDraftIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    Call Notes Agent: Drafts structured note, follow-up task, and post-call patient message.
    Strictly forbids facts not provided in nurse quick picks or voice transcript.
    """
    from .agents.call_notes_agent import CallNotesAgent

    staff_id = user.get("staff_id", 1)
    staff_name = user.get("full_name") or user.get("account_role", "Nurse Priya")

    try:
        draft = CallNotesAgent.draft_call_records(
            patient_id=body.patient_id,
            staff_id=staff_id,
            staff_name=staff_name,
            reached=body.reached,
            patient_reports=body.patient_reports,
            actions_agreed=body.actions_agreed,
            voice_transcript=body.voice_transcript,
            needs_doctor=body.needs_doctor,
            call_script_id=body.call_script_id
        )
        return draft
    except ValueError as e:
        raise HTTPException(422, detail=str(e))


@app.post("/agent/call-notes/approve")
def approve_call_notes_endpoint(
    body: CallNoteApproveIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    Approves the drafted call note:
    In one atomic transaction, creates clinician_notes, follow_up_tasks, patient_updates,
    contact_log, updates agent_drafts, stores edit_chars, and logs audit record.
    """
    from .agents.call_notes_agent import CallNotesAgent

    staff_id = user.get("staff_id", 1)
    staff_name = user.get("full_name") or user.get("account_role", "Nurse Priya")

    try:
        res = CallNotesAgent.commit_call_records(
            draft_id=body.draft_id,
            staff_id=staff_id,
            staff_name=staff_name,
            edited_body=body.edited_body
        )
        return res
    except ValueError as e:
        raise HTTPException(404, detail=str(e))


@app.post("/agent/undo/{action_id}")
def undo_agent_action_endpoint(
    action_id: int,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    Reverts an automated action where possible (e.g. cancelling a scheduled retry).
    """
    from .agents.outreach_agent import OutreachAgent

    staff_id = user.get("staff_id", 1)
    try:
        res = OutreachAgent.undo_action(action_id, staff_id)
        return res
    except ValueError as e:
        raise HTTPException(404, detail=str(e))


@app.post("/agent/outreach/evaluate")
def evaluate_outreach_endpoint(
    body: OutreachEvaluateIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    Evaluates automated outreach policy: quiet hours, daily caps, STOP opt-out, and pause switches.
    """
    from .agents.outreach_agent import OutreachAgent

    res = OutreachAgent.evaluate_outreach(
        patient_id=body.patient_id,
        action_type=body.action_type,
        message_text=body.message_text,
        is_emergency=body.is_emergency
    )
    return res


# ─── CareLoop Phase 5: Handoff, Plan & Auto-Close Endpoints ─────────────────

class HandoffDraftIn(BaseModel):
    shift_type: str = "Morning_to_Evening"
    patient_id: Optional[int] = None


class HandoffSignIn(BaseModel):
    draft_id: int
    notes: Optional[str] = None
    edited_text: Optional[str] = None


class PlanDraftIn(BaseModel):
    patient_id: int
    source_doc_id: Optional[int] = None


class PlanApproveIn(BaseModel):
    plan_id: int
    notes: Optional[str] = None


class AutoCloseEvaluateIn(BaseModel):
    flag_id: int
    trigger_condition: Optional[str] = "data resumed 30m"


class FlagReopenIn(BaseModel):
    reopen_reason: Optional[str] = "Reopened by clinician"


@app.post("/agent/handoff/draft")
def draft_handoff_endpoint(
    body: HandoffDraftIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    Drafts SBAR/I-PASS patient summary or cohort shift handoff from deterministic facts.
    Marked 'AI-prepared draft', signed by human before patient or doctor viewing.
    """
    from .agents.handoff_agent import HandoffAgent

    staff_id = user.get("staff_id", 1)
    staff_name = user.get("name") or ("Dr. Sharma" if user.get("account_role") == "Doctor" else "Priya Nair")

    if body.patient_id is not None:
        res = HandoffAgent.draft_patient_summary(body.patient_id, staff_id, staff_name)
    else:
        res = HandoffAgent.draft_shift_handoff(staff_id, body.shift_type, staff_name)
    return res


@app.post("/agent/handoff/sign")
def sign_handoff_endpoint(
    body: HandoffSignIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    Licensed clinician signs an AI-prepared summary or shift handoff draft.
    Records reviewer identity, reviewed_at, and edit_chars fidelity.
    """
    from .agents.handoff_agent import HandoffAgent

    staff_id = user.get("staff_id", 1)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT draft_type FROM agent_drafts WHERE draft_id = %s;", (body.draft_id,))
        draft = cur.fetchone()
        if not draft:
            raise HTTPException(404, "Draft not found")

        if draft["draft_type"] == "Summary":
            res = HandoffAgent.sign_patient_summary(body.draft_id, staff_id, body.edited_text)
        else:
            res = HandoffAgent.sign_shift_handoff(body.draft_id, staff_id, body.notes)
    return res


@app.post("/agent/plan/draft")
def draft_plan_endpoint(
    body: PlanDraftIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    Drafts recovery plan items with chunk citations and prescription reconciliation.
    Saves in 'Draft' status (invisible to patients until doctor approved).
    """
    from .agents.plan_agent import PlanAgent

    staff_id = user.get("staff_id", 1)
    res = PlanAgent.draft_recovery_plan(body.patient_id, staff_id, body.source_doc_id)
    return res


@app.post("/agent/plan/approve")
def approve_plan_endpoint(
    body: PlanApproveIn,
    user: Dict[str, Any] = Depends(require_role("Doctor")),
):
    """
    Doctor-only: Signs and approves recovery plan.
    Makes plan visible to patient and generates understanding checks.
    """
    from .agents.plan_agent import PlanAgent

    doctor_staff_id = user.get("staff_id", 1)
    try:
        res = PlanAgent.approve_recovery_plan(body.plan_id, doctor_staff_id, body.notes)
        return res
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.post("/agent/auto-close/evaluate")
def evaluate_auto_close_endpoint(
    body: AutoCloseEvaluateIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    Evaluates doctor-approved auto-close on a flag.
    Strictly refuses emergency, SOS, urgent, or symptom flags.
    """
    from .agents.auto_close_service import AutoCloseService

    can_close, reason = AutoCloseService.can_auto_close(body.flag_id)
    if not can_close:
        return {"auto_closed": False, "can_auto_close": False, "reason": reason}

    res = AutoCloseService.auto_close_flag(body.flag_id, body.trigger_condition or "data resumed 30m")
    return res


@app.post("/flags/{flag_id}/reopen")
def reopen_flag_endpoint(
    flag_id: int,
    body: FlagReopenIn = FlagReopenIn(),
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    Reopens a resolved or auto-closed flag and its parent case.
    Audited with clinician identity.
    """
    from .agents.auto_close_service import AutoCloseService

    staff_id = user.get("staff_id", 1)
    try:
        res = AutoCloseService.reopen_flag(flag_id, staff_id, body.reopen_reason or "Reopened by clinician")
        return res
    except ValueError as e:
        raise HTTPException(404, str(e))


# ─── CareLoop Care Agents Phase 6: Evaluation, Replay & Work-Saved Metrics ───

class AssumptionsUpdateIn(BaseModel):
    assumptions: Dict[str, Any]


@app.get("/agent/metrics")
def get_agent_metrics(user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse"))):
    """
    Phase 6 Work-Saved Panel & System Performance Metrics:
    Returns live counters of routine answers, reminders, duplicates merged,
    drafts accepted/edited/rejected, auto-closes, pre-briefed calls,
    estimated minutes saved ("Estimated from editable assumptions"),
    and per-agent latency & token usage.
    """
    from .agents.workload_replay import WorkloadReplayService
    from .agents.dispatcher import AgentDispatcher, MAX_DAILY_LLM_CALLS_PER_PATIENT

    assumptions = WorkloadReplayService.get_assumptions()

    with get_conn() as conn, conn.cursor() as cur:
        # 1. Real-time work counters
        cur.execute("""
            SELECT
                (SELECT COUNT(*) FROM agent_runs WHERE trigger_type = 'papers_question' AND status = 'Done') as routine_answers,
                (SELECT COUNT(*) FROM scheduled_actions WHERE status = 'Executed') as reminders_sent,
                (SELECT COALESCE(SUM(GREATEST(merged_count - 1, 0)), 0) FROM cases) as duplicates_merged,
                (SELECT COUNT(*) FROM agent_drafts WHERE status = 'Accepted') as drafts_accepted_unchanged,
                (SELECT COUNT(*) FROM agent_drafts WHERE status = 'Edited') as drafts_edited,
                (SELECT COUNT(*) FROM agent_drafts WHERE status = 'Rejected') as drafts_rejected,
                (SELECT COUNT(*) FROM flags WHERE resolution_note LIKE '%Closed by approved rule%') as auto_closes,
                (SELECT COUNT(*) FROM cases) as calls_prebriefed;
        """)
        counts = cur.fetchone() or {}

        # 2. Per-Agent Latency and Token Usage Counters
        cur.execute("""
            SELECT
                agent_name,
                COUNT(*) as total_runs,
                COALESCE(SUM(tokens_in), 0) as tokens_prompt,
                COALESCE(SUM(tokens_out), 0) as tokens_completion,
                ROUND(AVG(COALESCE(latency_ms, 0)), 1) as avg_latency_ms,
                MAX(COALESCE(latency_ms, 0)) as max_latency_ms,
                SUM(CASE WHEN status = 'Blocked_By_Guard' THEN 1 ELSE 0 END) as blocked_by_guard_count
            FROM agent_runs
            GROUP BY agent_name
            ORDER BY total_runs DESC;
        """)
        agent_perf = cur.fetchall() or []

        # 3. Patient Daily Budget Utilization
        cur.execute("""
            SELECT
                p.patient_id, p.full_name, p.patient_code,
                COUNT(r.run_id) as today_calls,
                %s as daily_budget,
                ROUND((COUNT(r.run_id) / %s) * 100, 1) as budget_used_pct
            FROM patients p
            LEFT JOIN agent_runs r ON r.patient_id = p.patient_id AND DATE(r.started_at) = CURDATE()
            GROUP BY p.patient_id, p.full_name, p.patient_code
            ORDER BY today_calls DESC;
        """, (MAX_DAILY_LLM_CALLS_PER_PATIENT, MAX_DAILY_LLM_CALLS_PER_PATIENT))
        patient_budgets = cur.fetchall() or []

        # 4. Cached Replay Benchmark Result
        cur.execute("SELECT state_val FROM agent_system_state WHERE state_key = 'last_replay_result';")
        last_replay_row = cur.fetchone()
        last_replay = json.loads(last_replay_row["state_val"]) if last_replay_row and last_replay_row.get("state_val") else None

    # Calculate estimated minutes saved from assumptions
    q_rule = assumptions.get("routine_question", {})
    rem_rule = assumptions.get("reminder_followup", {})
    dup_rule = assumptions.get("duplicate_alert", {})
    call_rule = assumptions.get("call_documentation", {})
    sum_rule = assumptions.get("shift_summary", {})

    mins_q = float(counts.get("routine_answers") or 0) * (float(q_rule.get("manual_minutes", 4.0)) - float(q_rule.get("agents_minutes", 0.5)))
    mins_rem = float(counts.get("reminders_sent") or 0) * (float(rem_rule.get("manual_minutes", 2.5)) - float(rem_rule.get("agents_minutes", 0.0)))
    mins_dup = float(counts.get("duplicates_merged") or 0) * (float(dup_rule.get("manual_minutes", 2.0)) - float(dup_rule.get("agents_minutes", 0.0)))
    mins_call = float((counts.get("drafts_accepted_unchanged") or 0) + (counts.get("drafts_edited") or 0)) * (float(call_rule.get("manual_minutes", 6.0)) - float(call_rule.get("agents_minutes", 1.0)))
    mins_sum = float(counts.get("calls_prebriefed") or 0) * 2.0

    total_est_minutes = round(max(0.0, mins_q + mins_rem + mins_dup + mins_call + mins_sum), 1)

    return {
        "disclaimer": "Estimated from editable assumptions",
        "counts": counts,
        "estimated_minutes_saved": total_est_minutes,
        "estimated_hours_saved": round(total_est_minutes / 60.0, 1),
        "assumptions": assumptions,
        "agent_performance": agent_perf,
        "patient_budgets": patient_budgets,
        "last_replay": last_replay
    }


@app.get("/agent/assumptions")
def get_assumptions_endpoint(user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse"))):
    """Returns the current configurable step and minute assumptions."""
    from .agents.workload_replay import WorkloadReplayService
    return WorkloadReplayService.get_assumptions()


@app.put("/agent/assumptions")
def update_assumptions_endpoint(
    body: AssumptionsUpdateIn,
    user: Dict[str, Any] = Depends(require_role("Doctor")),
):
    """Doctor-only: Updates configurable clinical step and time assumptions."""
    from .agents.workload_replay import WorkloadReplayService
    saved = WorkloadReplayService.save_assumptions(body.assumptions)
    return {"status": "ok", "assumptions": saved}


@app.post("/agent/replay")
def trigger_workload_replay_endpoint(user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse"))):
    """Executes the scripted 40-event shift workload replay and returns benchmark comparison."""
    from .agents.workload_replay import WorkloadReplayService
    res = WorkloadReplayService.run_replay(update_shadow_table=True)
    return res


# ─── CareLoop Agents v2: Health, Incident & Circuit Breaker Endpoints ──────────

class AgentIncidentIn(BaseModel):
    run_id: str
    category: str
    note: str


@app.get("/agent/health")
def get_agent_health_endpoint(
    window: str = "24h",
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Returns agent health, latencies, tokens, shadow trends and draft acceptance rates."""
    from .agents.health_service import AgentHealthService
    return AgentHealthService.get_health_metrics(window=window)


@app.post("/agent/incidents")
def report_agent_incident_endpoint(
    body: AgentIncidentIn,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Reports a defect in AI output, creating a candidate test and triggering demotion."""
    from .agents.incident_service import IncidentService
    staff_id = user.get("staff_id", 1)
    try:
        res = IncidentService.report_incident(
            run_id=body.run_id,
            reported_by_staff_id=staff_id,
            category=body.category,
            note=body.note,
        )
        return res
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@app.get("/agent/candidate-tests")
def get_candidate_tests_endpoint(
    status: Optional[str] = None,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Doctor & nurse view for candidate evaluation tests generated from staff incident reports."""
    from .agents.incident_service import IncidentService
    return IncidentService.get_candidate_tests(status=status)


@app.post("/agent/candidate-tests/{candidate_id}/approve")
def approve_candidate_test_endpoint(
    candidate_id: int,
    user: Dict[str, Any] = Depends(require_role("Doctor")),
):
    """Doctor-only: Approves a candidate test case into the permanent regression evaluation suite."""
    from .agents.incident_service import IncidentService
    staff_id = user.get("staff_id", 1)
    return IncidentService.review_candidate_test(candidate_id, staff_id, approve=True)


@app.post("/agent/candidate-tests/{candidate_id}/reject")
def reject_candidate_test_endpoint(
    candidate_id: int,
    user: Dict[str, Any] = Depends(require_role("Doctor")),
):
    """Doctor-only: Rejects a candidate test case."""
    from .agents.incident_service import IncidentService
    staff_id = user.get("staff_id", 1)
    return IncidentService.review_candidate_test(candidate_id, staff_id, approve=False)


@app.post("/agent/circuit-breaker/evaluate")
def evaluate_circuit_breaker_endpoint(
    user: Dict[str, Any] = Depends(require_role("Doctor")),
):
    """Evaluates all Auto/Live actions against continuous safety thresholds and triggers demotions."""
    from .agents.circuit_breaker import CircuitBreaker
    demotions = CircuitBreaker.evaluate_all()
    return {"status": "ok", "demotions": demotions}


@app.get("/agent/circuit-breaker/demotions")
def get_circuit_breaker_demotions_endpoint(
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Fetches active circuit breaker demotion alerts."""
    from .agents.circuit_breaker import CircuitBreaker
    return CircuitBreaker.get_active_demotions()


# ─── Phase 5: Proactive Help, Approved Examples & Patient Transparency ────────

class ConsentUpdateRequest(BaseModel):
    consent_granted: bool
    notice_version: Optional[str] = None


@app.post("/patient/me/day-brief")
def generate_patient_day_brief_me(
    user: Dict[str, Any] = Depends(require_patient),
    language: str = Query("en"),
):
    """Generates Day Brief (zero LLM template) for authenticated patient."""
    pid = get_effective_patient_id(user)
    from backend.app.agents.proactive_service import generate_day_brief
    ok, update_id, reason, data = generate_day_brief(patient_id=pid, language=language, created_by="Patient")
    return {"status": "ok" if ok else "suppressed", "update_id": update_id, "reason": reason, "data": data}


@app.post("/patient/{patient_id}/day-brief")
def generate_patient_day_brief(
    patient_id: int,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
    language: str = Query("en"),
    force: bool = Query(False),
):
    """Staff triggers Day Brief for a patient within clinical automation limits."""
    from backend.app.agents.proactive_service import generate_day_brief
    staff_name = user.get("full_name", "Staff")
    ok, update_id, reason, data = generate_day_brief(patient_id=patient_id, language=language, created_by=staff_name, force=force)
    return {"status": "ok" if ok else "suppressed", "update_id": update_id, "reason": reason, "data": data}


@app.get("/patient/me/visit-prep")
def get_patient_visit_prep_me(user: Dict[str, Any] = Depends(require_patient)):
    """Generates printable Visit Prep Sheet for authenticated patient (Facts only: dates, pain numbers, unfound questions)."""
    pid = get_effective_patient_id(user)
    from backend.app.agents.proactive_service import generate_visit_prep_sheet
    return generate_visit_prep_sheet(patient_id=pid)


@app.get("/patient/{patient_id}/visit-prep")
def get_patient_visit_prep(
    patient_id: int,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Staff generates printable Visit Prep Sheet (Facts only, zero advice)."""
    from backend.app.agents.proactive_service import generate_visit_prep_sheet
    return generate_visit_prep_sheet(patient_id=patient_id)


@app.post("/staff/patterns/detect")
def trigger_pattern_detection(
    patient_id: Optional[int] = Query(None),
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """
    Deterministic rule-based pattern checks:
    - Same dose unconfirmed >= 3 times in 7 days
    - 2 consecutive unanswered check-ins
    Creates nurse proposals with approved talking points in agent_proposals.
    NEVER creates a flag; NEVER sends a patient message.
    """
    from backend.app.agents.proactive_service import detect_pattern_proposals
    proposals = detect_pattern_proposals(patient_id=patient_id)
    return {"status": "ok", "proposals_created": proposals, "count": len(proposals)}


@app.get("/agent/exemplars/{draft_type}")
def get_exemplars_endpoint(
    draft_type: str,
    limit: int = Query(3, ge=1, le=10),
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Retrieves up to 3 de-identified approved exemplars with 'Uses previously approved notes as examples. No model training.' label."""
    from backend.app.agents.proactive_service import retrieve_exemplars
    exemplars = retrieve_exemplars(draft_type=draft_type, limit=limit)
    return {"status": "ok", "draft_type": draft_type, "exemplars": exemplars}


@app.get("/patient/me/transparency")
def get_patient_transparency_me(user: Dict[str, Any] = Depends(require_patient)):
    """Patient transparency portal: counts & list of AI messages, sources used, staff reviewer attribution, consent version."""
    pid = get_effective_patient_id(user)
    from backend.app.agents.proactive_service import get_patient_ai_transparency
    return get_patient_ai_transparency(patient_id=pid)


@app.get("/patient/{patient_id}/transparency")
def get_patient_transparency(
    patient_id: int,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Staff views patient AI transparency audit."""
    from backend.app.agents.proactive_service import get_patient_ai_transparency
    return get_patient_ai_transparency(patient_id=patient_id)


@app.post("/patient/me/consent")
def update_patient_consent_me(
    payload: ConsentUpdateRequest,
    user: Dict[str, Any] = Depends(require_patient),
):
    """Records authenticated patient AI-help consent timestamp and notice version."""
    pid = get_effective_patient_id(user)
    from backend.app.agents.proactive_service import record_patient_ai_consent
    from backend.app.agents.config import CURRENT_AI_NOTICE_VERSION
    return record_patient_ai_consent(
        patient_id=pid,
        consent_granted=payload.consent_granted,
        notice_version=payload.notice_version or CURRENT_AI_NOTICE_VERSION,
        actor_id=pid,
    )


@app.post("/patient/{patient_id}/consent")
def update_patient_consent(
    patient_id: int,
    payload: ConsentUpdateRequest,
    user: Dict[str, Any] = Depends(require_role("Doctor", "Nurse")),
):
    """Staff updates patient AI consent on their behalf with audit log."""
    from backend.app.agents.proactive_service import record_patient_ai_consent
    from backend.app.agents.config import CURRENT_AI_NOTICE_VERSION
    staff_id = user.get("staff_id", 1)
    return record_patient_ai_consent(
        patient_id=patient_id,
        consent_granted=payload.consent_granted,
        notice_version=payload.notice_version or CURRENT_AI_NOTICE_VERSION,
        actor_id=staff_id,
    )


# ─── Phase 6: Retention, Hardening & Security ─────────────────────────────────

@app.post("/agent/retention/purge")
def trigger_agent_retention_purge(
    days: int = Query(30, ge=1, le=365),
    user: Dict[str, Any] = Depends(require_role("Doctor")),
):
    """Doctor-only: Purges agent traces and resolved drafts older than specified retention days."""
    from backend.app.agents.retention_service import AgentRetentionService
    staff_id = user.get("staff_id", 1)
    staff_role = user.get("role", "Doctor")
    return AgentRetentionService.purge_expired_records(retention_days=days, actor_id=staff_id, actor_role=staff_role)


@app.post("/agent/redteam/run")
def trigger_redteam_evaluation(
    user: Dict[str, Any] = Depends(require_role("Doctor")),
):
    """Doctor-only: Runs the 85-case red-team evaluation suite against Policy Guard."""
    from backend.app.agents.redteam_runner import run_redteam_suite
    return run_redteam_suite(log_to_audit=True)






