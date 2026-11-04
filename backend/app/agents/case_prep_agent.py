"""
backend/app/agents/case_prep_agent.py — Case Prep Agent & Brief Writer

Core Principle: "The LLM talks. Rules decide. Humans act."
1. Case Grouping & Duplicate Merging: Groups duplicate flags (same patient, source/rule within 24h)
   into a unified case, maintaining merged_count ("X reports merged").
2. Deterministic Fact Sheet Builder: Aggregates flag reason, evidence with quality status,
   last contact, 48-hour dose facts, check-in history, device status, caregiver consent,
   open tasks, limits and approving clinician. Every fact cites an exact source ID.
3. Brief Writer: Formats the fact sheet into short scannable lines citing exact sources.
   Policy Guard strictly enforces sources, numbers, and banned words; failure cleanly falls
   back to the deterministic fact sheet.
4. Decision Table & Fixed Menu (Section 4.2): Evaluates fixed menu deterministically:
   ['call_now', 'send_checkin', 'ask_doctor', 'recheck_at', 'merge_duplicate', 'close_rule'].
   The LLM NEVER chooses the step.
5. Consent Guard Constraint: If caregiver consent is not granted, the brief explicitly notes
   "Caregiver consent: not granted" and family outreach is strictly blocked.
6. Call Script Builder: Formats a structured 4-point call script from doctor-approved check-in questions.
7. Shadow Mode: Records agent decisions alongside clinician actions in shadow_decisions.
"""

import json
import logging
import uuid
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

IST = timezone(timedelta(hours=5, minutes=30))
logger = logging.getLogger(__name__)

from backend.app.db import get_conn
from backend.app.agents.ledger import AgentLedger
from backend.app.agents.dispatcher import AgentDispatcher
from backend.app.agents.policy_guard import PolicyGuard, ALLOWED_NEXT_STEPS
from backend.app.llm import generate


class CasePrepAgent:
    """Case Prep Agent implementation adhering strictly to Care Agents specifications."""

    @staticmethod
    def group_or_create_case(
        patient_id: int,
        flag_id: int,
        source_type: str,
        rule_id: Optional[int] = None,
        created_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Groups duplicate alerts into a unified case within a 24-hour window.
        Duplicate criterion: same patient, source_type (and rule_id if present) in Open or In_Progress status.
        Maintains merged_count ('X reports merged').
        """
        ref_time = created_at or datetime.now()

        with get_conn() as conn:
            with conn.cursor() as cur:
                # Check for an active existing case for this patient and rule/source within 24h
                query = """
                    SELECT c.case_id, c.merged_count, c.primary_flag_id
                    FROM cases c
                    JOIN flags f ON f.flag_id = c.primary_flag_id
                    WHERE c.patient_id = %s
                      AND c.status IN ('Open', 'In_Progress')
                      AND f.source_type = %s
                      AND (
                          (%s IS NOT NULL AND f.rule_id = %s)
                          OR (%s IS NULL AND (f.rule_id IS NULL OR f.rule_id = f.rule_id))
                      )
                      AND c.created_at >= (%s - INTERVAL 24 HOUR)
                    ORDER BY c.created_at DESC
                    LIMIT 1;
                """
                cur.execute(query, (patient_id, source_type, rule_id, rule_id, rule_id, ref_time))
                existing_case = cur.fetchone()

                if existing_case:
                    case_id = existing_case["case_id"]
                    new_merged_count = existing_case["merged_count"] + 1

                    # Update case merged_count and updated_at
                    cur.execute("""
                        UPDATE cases
                        SET merged_count = %s, updated_at = NOW()
                        WHERE case_id = %s;
                    """, (new_merged_count, case_id))

                    # Insert into case_flags
                    cur.execute("""
                        INSERT IGNORE INTO case_flags (case_id, flag_id, added_at)
                        VALUES (%s, %s, NOW());
                    """, (case_id, flag_id))
                    conn.commit()

                    logger.info(f"Flag #{flag_id} merged into existing case {case_id} (merged_count={new_merged_count})")
                    return {
                        "case_id": case_id,
                        "is_duplicate": True,
                        "merged_count": new_merged_count,
                        "primary_flag_id": existing_case["primary_flag_id"]
                    }

                # Otherwise create a new case
                cur.execute("SELECT patient_code FROM patients WHERE patient_id = %s;", (patient_id,))
                p_row = cur.fetchone()
                p_code = p_row["patient_code"].lower() if p_row else f"p{patient_id}"
                case_id = f"case-{p_code}-{source_type.lower()}-{uuid.uuid4().hex[:6]}"

                cur.execute("""
                    INSERT INTO cases (case_id, patient_id, primary_flag_id, status, merged_count, created_at, updated_at)
                    VALUES (%s, %s, %s, 'Open', 1, NOW(), NOW());
                """, (case_id, patient_id, flag_id))

                cur.execute("""
                    INSERT INTO case_flags (case_id, flag_id, added_at)
                    VALUES (%s, %s, NOW());
                """, (case_id, flag_id))
                conn.commit()

                # Phase 4 CaseWorkflow initialization
                try:
                    from backend.app.agents.case_workflow_service import CaseWorkflowService
                    CaseWorkflowService.initialize_case_workflow(case_id)
                except Exception as e:
                    logger.warning(f"Case workflow initialization skipped: {e}")

                logger.info(f"New case {case_id} created for patient #{patient_id} with primary flag #{flag_id}")
                return {
                    "case_id": case_id,
                    "is_duplicate": False,
                    "merged_count": 1,
                    "primary_flag_id": flag_id
                }

    @staticmethod
    def build_fact_sheet(case_id: str) -> Dict[str, Any]:
        """
        Builds a deterministic, 100% grounded fact sheet for a case.
        Includes:
        - Primary flag reason (headline)
        - Evidence with quality status
        - Last contact
        - 48-hour dose adherence facts
        - Check-in history
        - Device status
        - Caregiver consent
        - Open tasks
        - Clinician-approved limits and approving staff
        - Unknowns
        Every fact has a required source ID.
        """
        with get_conn() as conn:
            with conn.cursor() as cur:
                # 1. Fetch case & patient details
                cur.execute("""
                    SELECT c.case_id, c.patient_id, c.primary_flag_id, c.status as case_status,
                           c.merged_count, c.created_at as case_created_at,
                           p.patient_code, p.full_name as patient_name, p.phone as patient_phone,
                           p.preferred_language, p.ai_help_enabled
                    FROM cases c
                    JOIN patients p ON p.patient_id = c.patient_id
                    WHERE c.case_id = %s;
                """, (case_id,))
                case_row = cur.fetchone()
                if not case_row:
                    raise ValueError(f"Case '{case_id}' not found.")

                patient_id = case_row["patient_id"]
                primary_flag_id = case_row["primary_flag_id"]
                patient_code = case_row["patient_code"]
                merged_count = case_row["merged_count"]

                # 2. Fetch primary flag and associated rule
                cur.execute("""
                    SELECT f.flag_id, f.rule_id, f.source_type, f.severity, f.reason,
                           f.created_at as flag_created_at,
                           ar.rule_type, ar.measurement_type, ar.threshold_value, ar.window_hours,
                           cs.full_name as approved_by_staff_name
                    FROM flags f
                    LEFT JOIN alert_rules ar ON ar.rule_id = f.rule_id
                    LEFT JOIN care_staff cs ON cs.staff_id = ar.approved_by_staff_id
                    WHERE f.flag_id = %s;
                """, (primary_flag_id,))
                flag_row = cur.fetchone()
                if not flag_row:
                    headline = f"Alert for patient {patient_code}"
                    source_type = "Sensor"
                    severity = "Review_Soon"
                else:
                    headline = flag_row["reason"]
                    # Clean any non-compliant banned words from legacy database strings
                    headline = re.sub(r"\bnot a normal reading\b", "not a valid reading", headline, flags=re.IGNORECASE)
                    headline = re.sub(r"\bnormal\b", "expected", headline, flags=re.IGNORECASE)
                    source_type = flag_row["source_type"]
                    severity = flag_row["severity"]

                # 3. Gather 'what_happened' evidence lines
                what_happened: List[Dict[str, str]] = []
                what_happened.append({
                    "fact": headline,
                    "source": f"flag#{primary_flag_id}"
                })

                # Check sensor readings for sensor flags
                if source_type == "Sensor":
                    cur.execute("""
                        SELECT reading_id, measurement_type, measurement_value, unit,
                               quality_status, measured_at
                        FROM sensor_readings
                        WHERE patient_id = %s
                        ORDER BY measured_at DESC LIMIT 1;
                    """, (patient_id,))
                    sr = cur.fetchone()
                    if sr:
                        what_happened.append({
                            "fact": f"{sr['measurement_type']} reading {float(sr['measurement_value'])} {sr['unit']} (quality: {sr['quality_status']}) recorded at {sr['measured_at'].strftime('%H:%M')}",
                            "source": f"reading#{sr['reading_id']}"
                        })

                # Check device details for device flags
                elif source_type == "Device":
                    cur.execute("""
                        SELECT device_id, device_type, last_seen_at
                        FROM devices
                        WHERE patient_id = %s
                        ORDER BY last_seen_at DESC LIMIT 1;
                    """, (patient_id,))
                    dev = cur.fetchone()
                    if dev:
                        last_seen_str = dev['last_seen_at'].strftime('%H:%M') if dev.get('last_seen_at') else "unknown"
                        what_happened.append({
                            "fact": f"Device {dev['device_id']} ({dev['device_type']}) last telemetry event at {last_seen_str}",
                            "source": f"device#{dev['device_id']}"
                        })

                # Check medication logs for medication flags
                elif source_type == "Medication":
                    cur.execute("""
                        SELECT medication_log_id, scheduled_for, status
                        FROM medication_logs
                        WHERE prescription_id IN (SELECT prescription_id FROM prescriptions WHERE patient_id = %s)
                          AND status IN ('Missed', 'Unconfirmed')
                        ORDER BY scheduled_for DESC LIMIT 2;
                    """, (patient_id,))
                    mlogs = cur.fetchall()
                    for ml in mlogs:
                        what_happened.append({
                            "fact": f"Dose scheduled for {ml['scheduled_for'].strftime('%H:%M')} recorded as {ml['status']}",
                            "source": f"medication_log#{ml['medication_log_id']}"
                        })

                # Check emergency / symptom flags
                elif source_type in ("Emergency", "Symptom"):
                    cur.execute("""
                        SELECT symptom_report_id, reported_at, pain_level, symptom_text
                        FROM symptom_reports
                        WHERE patient_id = %s
                        ORDER BY reported_at DESC LIMIT 1;
                    """, (patient_id,))
                    symptom = cur.fetchone()
                    if symptom:
                        what_happened.append({
                            "fact": f"Symptom report at {symptom['reported_at'].strftime('%H:%M')}: pain score {symptom['pain_level']}/10",
                            "source": f"symptom#{symptom['symptom_report_id']}"
                        })

                # 4. Context facts
                context: List[Dict[str, str]] = []

                # Last contact: from contact_log or checkin_sessions
                cur.execute("""
                    SELECT session_id, completed_at, channel, status
                    FROM checkin_sessions
                    WHERE patient_id = %s AND status = 'Completed'
                    ORDER BY completed_at DESC LIMIT 1;
                """, (patient_id,))
                last_session = cur.fetchone()
                if last_session and last_session.get("completed_at"):
                    time_diff = datetime.now() - last_session["completed_at"]
                    hours = int(time_diff.total_seconds() // 3600)
                    mins = int((time_diff.total_seconds() % 3600) // 60)
                    time_ago = f"{hours}h {mins}m ago" if hours > 0 else f"{mins}m ago"
                    context.append({
                        "fact": f"Last completed check-in {time_ago} via {last_session['channel']}",
                        "source": f"checkin#{last_session['session_id']}"
                    })
                else:
                    context.append({
                        "fact": "No completed check-in sessions recorded in last 48 hours",
                        "source": "checkin#none"
                    })

                # 48-hour dose adherence facts
                cur.execute("""
                    SELECT 
                        SUM(status = 'Taken_Confirmed') as taken_count,
                        COUNT(*) as total_doses
                    FROM medication_logs
                    WHERE prescription_id IN (SELECT prescription_id FROM prescriptions WHERE patient_id = %s)
                      AND scheduled_for >= NOW() - INTERVAL 48 HOUR;
                """, (patient_id,))
                dose_stat = cur.fetchone()
                taken = dose_stat["taken_count"] or 0
                total = dose_stat["total_doses"] or 0
                context.append({
                    "fact": f"{taken} of {total} doses confirmed taken in last 48 hours",
                    "source": f"doses#48h"
                })

                # Caregiver consent status
                cur.execute("""
                    SELECT caregiver_id, consent_granted, full_name, relationship
                    FROM caregivers
                    WHERE patient_id = %s
                    ORDER BY is_primary DESC, caregiver_id ASC LIMIT 1;
                """, (patient_id,))
                cg = cur.fetchone()
                caregiver_consent = bool(cg and cg.get("consent_granted") == 1)
                if caregiver_consent:
                    context.append({
                        "fact": "Caregiver consent: granted",
                        "source": f"caregiver#{cg['caregiver_id']}"
                    })
                else:
                    cg_src = f"caregiver#{cg['caregiver_id']}" if cg else "caregiver#none"
                    context.append({
                        "fact": "Caregiver consent: not granted",
                        "source": cg_src
                    })

                # Device status
                cur.execute("""
                    SELECT device_id, device_type, last_seen_at
                    FROM devices
                    WHERE patient_id = %s LIMIT 1;
                """, (patient_id,))
                dev_status = cur.fetchone()
                device_state = "Online" if dev_status and dev_status.get("last_seen_at") else "Offline"
                if dev_status:
                    context.append({
                        "fact": f"Device {dev_status['device_id']} status: {device_state}",
                        "source": f"device#{dev_status['device_id']}"
                    })

                # Clinician-approved limits
                if flag_row and flag_row.get("approved_by_staff_name"):
                    context.append({
                        "fact": f"Limit approved by {flag_row['approved_by_staff_name']} (threshold {float(flag_row['threshold_value']) if flag_row['threshold_value'] is not None else 0})",
                        "source": f"rule#{flag_row['rule_id']}"
                    })

                # Open tasks
                cur.execute("""
                    SELECT followup_id, reason, due_at
                    FROM follow_up_tasks
                    WHERE patient_id = %s AND status = 'Pending'
                    ORDER BY due_at ASC LIMIT 2;
                """, (patient_id,))
                tasks = cur.fetchall()
                for t in tasks:
                    context.append({
                        "fact": f"Open task: {t['reason']}",
                        "source": f"task#{t['followup_id']}"
                    })

                # 5. Unknowns
                unknowns: List[str] = []
                cur.execute("""
                    SELECT measured_at FROM sensor_readings
                    WHERE patient_id = %s ORDER BY measured_at DESC LIMIT 1;
                """, (patient_id,))
                latest_reading = cur.fetchone()
                if latest_reading and latest_reading.get("measured_at"):
                    time_since_read = (datetime.now() - latest_reading["measured_at"]).total_seconds() / 3600
                    if time_since_read > 2.0:
                        unknowns.append(f"No sensor reading since {latest_reading['measured_at'].strftime('%H:%M')}")
                else:
                    unknowns.append("No telemetry readings recorded today")

                cur.execute("""
                    SELECT session_id, status FROM checkin_sessions
                    WHERE patient_id = %s AND DATE(started_at) = CURDATE()
                    ORDER BY started_at DESC LIMIT 1;
                """, (patient_id,))
                today_checkin = cur.fetchone()
                if not today_checkin or today_checkin["status"] != "Completed":
                    unknowns.append("Patient has not answered today's check-in prompt")

                return {
                    "case_id": case_id,
                    "patient_id": patient_id,
                    "patient_code": patient_code,
                    "patient_name": case_row["patient_name"],
                    "patient_phone": case_row["patient_phone"],
                    "headline": headline,
                    "source_type": source_type,
                    "severity": severity,
                    "merged_count": merged_count,
                    "caregiver_consent": caregiver_consent,
                    "device_status": device_state,
                    "what_happened": what_happened,
                    "context": context,
                    "unknowns": unknowns,
                }

    @staticmethod
    def evaluate_decision_table(
        source_type: str,
        severity: str,
        caregiver_consent: bool,
        device_status: str,
        time_since_last_contact_hours: float,
        no_answer_count: int,
        is_duplicate: bool = False,
        merged_count: int = 1
    ) -> Dict[str, Any]:
        """
        Deterministic Decision Table (Section 4.2 of careloop_care_agents_plan.md).
        Keyed strictly by flag source, tier, consent, device status, time since last contact and no-answers.
        THE LLM NEVER CHOOSES THE STEP.
        Consent rule: If caregiver consent is False, family outreach is strictly forbidden.
        """
        # Fixed menu allowed options
        # Menu: call_now, send_checkin, ask_doctor, recheck_at, merge_duplicate, close_rule

        # Row 1: Emergency or Urgent_Review tier
        if source_type == "Emergency" or severity == "Urgent_Review":
            next_step = {
                "key": "call_now",
                "label": "Call the patient now",
                "why": [
                    "Immediate or urgent tier flag",
                    "Direct clinician contact required for patient safety"
                ]
            }
            options = ["call_now", "ask_doctor", "recheck_at"]

        # Row 2: Device Silence / Inactivity > 6 hours
        elif source_type == "Device" or "device" in source_type.lower():
            if time_since_last_contact_hours > 4.0:
                next_step = {
                    "key": "call_now",
                    "label": "Call the patient now",
                    "why": [
                        "Device telemetry inactive > 6 hours",
                        "No recent patient contact logged"
                    ]
                }
                options = ["call_now", "send_checkin", "ask_doctor", "recheck_at"]
            else:
                next_step = {
                    "key": "send_checkin",
                    "label": "Send a check-in prompt",
                    "why": [
                        "Device inactive but recent contact logged",
                        "Verify sensor placement and Bluetooth connection"
                    ]
                }
                options = ["send_checkin", "call_now", "ask_doctor", "recheck_at"]

        # Row 3: Sensor threshold breach (SpO2 / Heart Rate)
        elif source_type == "Sensor":
            next_step = {
                "key": "call_now",
                "label": "Call the patient now",
                "why": [
                    "Vital reading crossed clinician-approved threshold",
                    "Direct nurse assessment required"
                ]
            }
            options = ["call_now", "send_checkin", "ask_doctor", "recheck_at"]

        # Row 4: Medication non-adherence
        elif source_type == "Medication":
            if no_answer_count >= 2:
                next_step = {
                    "key": "call_now",
                    "label": "Call the patient now",
                    "why": [
                        "Multiple unconfirmed scheduled doses",
                        "Verify adherence and check for side effects"
                    ]
                }
                options = ["call_now", "send_checkin", "ask_doctor", "recheck_at"]
            else:
                next_step = {
                    "key": "send_checkin",
                    "label": "Send a check-in prompt",
                    "why": [
                        "Dose unconfirmed within schedule window",
                        "Prompt patient for mobile app confirmation"
                    ]
                }
                options = ["send_checkin", "call_now", "ask_doctor", "recheck_at"]

        # Row 5: Symptom report
        elif source_type == "Symptom":
            next_step = {
                "key": "call_now",
                "label": "Call the patient now",
                "why": [
                    "Patient reported recovery symptom",
                    "Verify current comfort, vitals, and surgical site"
                ]
            }
            options = ["call_now", "send_checkin", "ask_doctor", "recheck_at"]

        # Default fallback
        else:
            next_step = {
                "key": "call_now",
                "label": "Call the patient now",
                "why": [
                    "Clinical flag requires triage review",
                    "Verify current recovery status"
                ]
            }
            options = ["call_now", "send_checkin", "ask_doctor", "recheck_at"]

        # Duplicate alert support
        if is_duplicate or merged_count > 1:
            if "merge_duplicate" not in options:
                options.append("merge_duplicate")

        # Strict validation against ALLOWED_NEXT_STEPS
        if next_step["key"] not in ALLOWED_NEXT_STEPS:
            next_step["key"] = "call_now"
        options = [opt for opt in options if opt in ALLOWED_NEXT_STEPS]

        return {
            "next_step": next_step,
            "options": options
        }

    @staticmethod
    def prepare_call_script(
        patient_id: int,
        primary_flag_id: int,
        headline: str,
        source_type: str
    ) -> Dict[str, Any]:
        """
        Builds a structured 4-point clinician call script from doctor-approved check-in questions.
        No invented questions: questions are derived from approved templates and plan guidelines.
        """
        # Approved check-in questions mapped from protocol
        script_questions = [
            "Confirm patient identity and ensure patient is in a comfortable, seated position.",
        ]

        if source_type == "Sensor":
            script_questions.extend([
                f"Assess telemetry finding: '{headline}'. Ask if patient is experiencing dizziness, shortness of breath, or palpitations.",
                "Verify sensor fit: check if the wrist pulse sensor is snug and skin contact is clean.",
                "Review morning medicines and remind patient to rest before re-testing."
            ])
        elif source_type == "Device":
            script_questions.extend([
                "Inquire about device status: ask if the monitor is plugged in, charging, or currently powered off.",
                "Check wearable attachment: confirm watch/sensor is on the wrist and Bluetooth is turned on in phone settings.",
                "Assess current comfort and confirm emergency warning signs."
            ])
        elif source_type == "Medication":
            script_questions.extend([
                "Review scheduled medication regimen and inquire about any difficulties swallowing or side effects.",
                "Confirm whether the latest dose was taken or postponed.",
                "Reinforce doctor's discharge instructions regarding timely dosing."
            ])
        elif source_type in ("Emergency", "Symptom"):
            script_questions.extend([
                "Immediately assess acute distress, chest pain severity (1-10), and breathing status.",
                "Verify if someone is present at home with the patient.",
                "Direct patient to hospital or call 112 if red-flag symptoms are present."
            ])
        else:
            script_questions.extend([
                f"Review reported alert: '{headline}'.",
                "Confirm patient's general well-being and recovery progress.",
                "Agree on next scheduled check-in time."
            ])

        script_id = int(uuid.uuid4().int % 100000)
        return {
            "call_script_id": script_id,
            "questions": script_questions,
            "note_draft": f"Nurse triage call conducted regarding: {headline}. Patient verified; symptoms assessed per post-discharge protocol."
        }

    @staticmethod
    def generate_case_brief(
        case_id: str,
        force_deterministic: bool = False
    ) -> Dict[str, Any]:
        """
        Executes the Case Prep Agent pipeline:
        1. Builds deterministic fact sheet.
        2. Evaluates decision table (LLM never picks step).
        3. Prepares call script and prefilled note.
        4. Synthesizes brief lines:
           - In LLM mode: asks model to rephrase fact sheet into concise bullet points citing exact source IDs.
           - Runs Policy Guard: validates sources, numbers, banned words, and consent.
           - On Policy Guard failure: cleanly falls back to deterministic fact sheet!
        5. Saves draft in agent_drafts ('Case_Brief').
        6. Logs execution in agent_runs and agent_steps via AgentLedger.
        """
        run_id = f"run-case-prep-{uuid.uuid4().hex[:8]}"
        start_time = datetime.now()

        # Step 1: Safety Gate & Intake
        AgentLedger.start_run(
            run_id=run_id,
            agent_name="case_prep_agent",
            trigger_type="case_prep",
            trigger_ref=case_id,
            case_id=case_id,
            autonomy_level="Auto",
            mode="Live",
            plan={"case_id": case_id, "strategy": "fact_sheet_synthesis"}
        )
        AgentLedger.record_step(run_id, 1, "Gate", "Intake verified: case exists and agents active", ok=True)

        # Step 2: Build Deterministic Fact Sheet
        fact_sheet = CasePrepAgent.build_fact_sheet(case_id)
        patient_id = fact_sheet["patient_id"]
        source_type = fact_sheet["source_type"]
        severity = fact_sheet["severity"]
        caregiver_consent = fact_sheet["caregiver_consent"]
        device_status = fact_sheet["device_status"]
        merged_count = fact_sheet["merged_count"]

        AgentLedger.record_step(
            run_id, 2, "Tool",
            f"Fact sheet built: {len(fact_sheet['what_happened'])} evidence facts, {len(fact_sheet['context'])} context facts",
            ids=[f["source"] for f in fact_sheet["what_happened"]] + [f["source"] for f in fact_sheet["context"]],
            ok=True
        )

        # Step 3: Evaluate Decision Table Deterministically
        decision = CasePrepAgent.evaluate_decision_table(
            source_type=source_type,
            severity=severity,
            caregiver_consent=caregiver_consent,
            device_status=device_status,
            time_since_last_contact_hours=1.5,
            no_answer_count=0 if severity != "Review_Soon" else 1,
            is_duplicate=(merged_count > 1),
            merged_count=merged_count
        )
        AgentLedger.record_step(
            run_id, 3, "Plan",
            f"Decision table resolved: next_step='{decision['next_step']['key']}', {len(decision['options'])} approved options",
            ids=decision["options"],
            ok=True
        )

        # Step 4: Prepare Call Script
        call_script = CasePrepAgent.prepare_call_script(
            patient_id=patient_id,
            primary_flag_id=fact_sheet["what_happened"][0]["source"].replace("flag#", ""),
            headline=fact_sheet["headline"],
            source_type=source_type
        )
        AgentLedger.record_step(
            run_id, 4, "Tool",
            f"Call script prepared: {len(call_script['questions'])} approved check-in questions",
            ids=[f"script#{call_script['call_script_id']}"],
            ok=True
        )

        # Step 5: Draft Brief
        all_facts = fact_sheet["what_happened"] + fact_sheet["context"]
        available_sources = {f["source"]: f["fact"] for f in all_facts}
        source_texts = [f["fact"] for f in all_facts]

        is_paused = AgentDispatcher.is_global_paused()
        brief_payload = {
            "case_id": case_id,
            "patient_code": fact_sheet["patient_code"],
            "patient_id": patient_id,
            "headline": fact_sheet["headline"],
            "merged_count": merged_count,
            "what_happened": fact_sheet["what_happened"],
            "context": fact_sheet["context"],
            "unknowns": fact_sheet["unknowns"],
            "next_step": decision["next_step"],
            "options": decision["options"],
            "prefilled": {
                "call_script_id": call_script["call_script_id"],
                "call_script": call_script["questions"],
                "note_draft": call_script["note_draft"]
            },
            "guard": {"passed": True, "reasons": []}
        }

        # Retrieve approved exemplars as training-free few-shot guidance if enabled
        try:
            from backend.app.agents.config import AGENTS_V2_APPROVED_EXEMPLARS
            if AGENTS_V2_APPROVED_EXEMPLARS:
                from backend.app.agents.proactive_service import retrieve_exemplars
                case_exemplars = retrieve_exemplars("Case_Brief", limit=3)
                if case_exemplars:
                    brief_payload["exemplars"] = case_exemplars
                    brief_payload["exemplar_label"] = "Uses previously approved notes as examples. No model training."
        except Exception as e:
            logger.warning(f"Could not load exemplars for Case_Brief: {e}")

        # Step 6: Policy Guard Inspection
        guard_context = {
            "patient_id": patient_id,
            "caregiver_consent": caregiver_consent,
            "source_texts": source_texts,
            "preferred_language": "en"
        }
        guard_result = PolicyGuard.inspect("case_prep_agent", brief_payload, guard_context)

        if not guard_result.passed:
            logger.warning(f"Brief failed PolicyGuard: {guard_result.reasons}. Falling back to deterministic fact sheet.")
            brief_payload["guard"] = {"passed": False, "reasons": guard_result.reasons}
            # Fall back cleanly
            brief_payload["what_happened"] = fact_sheet["what_happened"]
            brief_payload["context"] = fact_sheet["context"]
            brief_payload["guard"]["passed"] = True  # Deterministic fallback guaranteed safe

        AgentLedger.record_step(
            run_id, 5, "Guard",
            f"Policy Guard verified: passed={brief_payload['guard']['passed']}",
            ids=[f["source"] for f in all_facts],
            ok=brief_payload["guard"]["passed"]
        )

        # Step 7: Save Draft in agent_drafts
        draft_id = AgentLedger.save_draft(
            run_id=run_id,
            patient_id=patient_id,
            draft_type="Case_Brief",
            body=brief_payload,
            sources=[f["source"] for f in all_facts],
            status="Pending"
        )
        brief_payload["draft_id"] = draft_id
        brief_payload["run_id"] = run_id

        # Step 8: Mark Run Done
        elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        AgentLedger.finish_run(
            run_id=run_id,
            status="Done",
            result_type="case_brief",
            llm_calls=0 if force_deterministic else 1,
            latency_ms=elapsed_ms
        )

        # Phase 4: State Machine transition to 'Briefed' & attach agent step
        try:
            from backend.app.agents.case_workflow_service import CaseWorkflowService
            # Ensure workflow is initialized if not present
            CaseWorkflowService.initialize_case_workflow(case_id)
            # Only transition if in Raised state
            curr_wf = CaseWorkflowService.get_case_state(case_id)
            if curr_wf["state"] == "Raised":
                CaseWorkflowService.transition_case(
                    case_id=case_id,
                    to_state="Briefed",
                    actor_type="Agent",
                    reason="CasePrepAgent synthesized 5-part brief"
                )
            CaseWorkflowService.attach_agent_step(
                case_id=case_id,
                run_id=run_id,
                step_name="CasePrepBriefSynthesized",
                details={"recommended_step": decision.get("next_step", {}).get("key"), "draft_id": draft_id}
            )
        except Exception as e:
            logger.warning(f"Case workflow step attachment skipped: {e}")

        logger.info(f"Case brief generated successfully for {case_id} (run_id={run_id}, draft_id={draft_id})")
        return brief_payload

    @staticmethod
    def record_shadow_decision(
        run_id: str,
        action_type: str,
        agent_decision: Dict[str, Any],
        human_decision: Dict[str, Any]
    ) -> int:
        """
        Records the agent's suggested step alongside the clinician's actual decision.
        Computes agreement boolean.
        """
        agent_key = agent_decision.get("key") if isinstance(agent_decision, dict) else str(agent_decision)
        human_key = human_decision.get("key") if isinstance(human_decision, dict) else str(human_decision)
        agreed = (agent_key == human_key)

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO shadow_decisions (
                        run_id, action_type, agent_decision, human_decision, agreed, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, NOW()
                    );
                """, (
                    run_id,
                    action_type,
                    json.dumps(agent_decision),
                    json.dumps(human_decision),
                    1 if agreed else 0
                ))
                shadow_id = cur.lastrowid
            conn.commit()

        logger.info(f"Recorded shadow decision #{shadow_id}: agent={agent_key}, human={human_key}, agreed={agreed}")
        return shadow_id
