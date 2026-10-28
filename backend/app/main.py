"""
backend/app/main.py — CareLoop API

Core Rule: "The LLM talks. Rules decide. Humans act."
All patient endpoints strictly extract patient_id from the authenticated JWT token.
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Header, HTTPException, Depends, Request
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


# ─── Patient Medication Doses (Milestone M3) ─────────────────────────────────

class DoseConfirmIn(BaseModel):
    status: str = Field(pattern="^(Taken_Confirmed|Skipped)$")
    patient_note: Optional[str] = None


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


# ─── Symptom Check-in & Emergency Layer (Milestone M3) ───────────────────────

class SymptomIn(BaseModel):
    text: str
    pain_level: int = Field(default=0, ge=0, le=10)
    input_method: str = Field(default="Text", pattern="^(Text|Voice_Transcript|Caregiver)$")
    language: str = Field(default="en", pattern="^(en|hi)$")


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


@app.post("/patient/me/symptoms")
def submit_symptom_checkin(body: SymptomIn, user: Dict[str, Any] = Depends(require_role("Patient", "Caregiver"))):
    """
    Symptom Check-in Endpoint:
    - Runs deterministic emergency keyword check (English + Hindi) instantly.
    - Inserts into symptom_reports table.
    - Database AFTER INSERT trigger trg_symptom_rules_after_insert creates Urgent_Review
      flag (for emergency hit) or Review_Soon flag (if pain_level >= clinician threshold).
    - Writes to audit_log.
    - Emergency guidance is returned immediately without waiting for any LLM call!
    - Tags extracted asynchronously/inline via LLM.
    """
    pid = get_effective_patient_id(user)
    emergency = has_emergency_term(body.text)
    guidance = EMERGENCY_GUIDANCE.get(body.language, EMERGENCY_GUIDANCE["en"]) if emergency else None

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO symptom_reports
               (patient_id, symptom_text, pain_level, input_method, language, emergency_keyword_hit)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (pid, body.text, body.pain_level, body.input_method, body.language, emergency),
        )
        report_id = cur.lastrowid

        # Write audit log
        cur.execute(
            """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
               VALUES ('Patient', %s, 'SUBMIT_SYMPTOM', 'symptom_report', %s,
                       JSON_OBJECT('emergency_hit', %s, 'pain_level', %s, 'lang', %s))""",
            (str(user["account_id"]), report_id, emergency, body.pain_level, body.language),
        )

    # Extract tags via LLM
    extract_and_save_symptom_tags(report_id, body.text)

    return {
        "status": "recorded",
        "report_id": report_id,
        "emergency": emergency,
        "guidance": guidance,
    }


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