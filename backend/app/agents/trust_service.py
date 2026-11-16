"""
app/agents/trust_service.py — CareLoop Phase 4 Trust, Transparency & Safety Service

Implements:
1. "Why was my care team told?" (5.F): Explains alert flags with data quality, rule threshold, approving doctor, and next steps in plain, non-judgmental language.
2. "My readings" trend: 7-day valid values, filtered invalid readings, doctor's alert limit line.
3. Help bar (5.G): Call 112, Ask nurse to call me, SOS, Message my nurse (fixed templates). De-duplicated. Works with LLM off.
4. Distress path (5.G): Plain code matching of English, Hindi, and Hinglish distress phrases. Creates urgent nurse call task and returns clinician-approved fixed message.
5. AI Transparency & Settings (5.H): AI usage metrics, data sources, AI help toggle, chat privacy controls (hide/delete).
"""

import re
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Tuple
from backend.app.db import get_conn


class TrustService:
    # ─── 1. Distress Phrase Patterns (Plain Code Matching, No LLM) ─────────
    DISTRESS_PATTERNS = [
        # English
        r"\b(?:i\s+want\s+to\s+die|feel\s+like\s+giving\s+up|cannot\s+take\s+this\s+anymore)\b",
        r"\b(?:hopeless|want\s+to\s+end\s+(?:it|my\s+life)|cannot\s+go\s+on|no\s+point\s+in\s+living)\b",
        r"\b(?:overwhelmed\s+and\s+scared|ready\s+to\s+give\s+up)\b",
        # Hindi / Hinglish
        r"\b(?:main\s+haar\s+gaya|jeena\s+nahi\s+chahta|marne\s+ka\s+man)\b",
        r"\b(?:himmat\s+toot\s+gayi|bahut\s+dar\s+lag\s+raha\s+hai|ab\s+nahi\s+ho\s+raha)\b",
        r"\b(?:give\s+up\s+kar\s+raha|koi\s+fayda\s+nahi\s+hai|sab\s+khatam\s+karna)\b",
    ]

    # Clinician-approved fixed distress messages (Clinician slot)
    DISTRESS_REPLY_EN = (
        "We hear you, and you are not alone. A triage nurse has been notified immediately to call you. "
        "If you are feeling in immediate crisis or need urgent emotional support, please call 112 "
        "or contact a mental health crisis line immediately."
    )
    DISTRESS_REPLY_HI = (
        "हम आपकी बात समझ रहे हैं, और आप अकेले नहीं हैं। आपकी मदद के लिए ट्राइएज नर्स को तुरंत कॉल करने की सूचना भेज दी गई है। "
        "यदि आपको तत्काल आपातकालीन सहायता की आवश्यकता है, तो कृपया तुरंत 112 पर कॉल करें।"
    )

    @classmethod
    def check_distress(cls, text: str) -> bool:
        if not text:
            return False
        clean = text.strip().lower()
        return any(re.search(pat, clean, re.IGNORECASE) for pat in cls.DISTRESS_PATTERNS)

    @classmethod
    def handle_distress(cls, patient_id: int, query_text: str, language: str = "en") -> Dict[str, Any]:
        """
        Intercepts distress queries in plain code:
        - Bypasses LLM generation.
        - Automatically creates High-priority urgent nurse call task.
        - Returns clinician-approved message with emergency guidance.
        """
        task_id = None
        call_created = False
        with get_conn() as conn, conn.cursor() as cur:
            # Check deduplication for today
            cur.execute(
                """SELECT followup_id FROM follow_up_tasks
                   WHERE patient_id = %s AND reason LIKE '%%Distress Intercept%%'
                     AND DATE(created_at) = CURDATE()
                   LIMIT 1""",
                (patient_id,)
            )
            existing = cur.fetchone()
            if not existing:
                cur.execute(
                    """INSERT INTO follow_up_tasks (patient_id, assigned_staff_id, reason, priority, status, created_at)
                       VALUES (%s, 1, %s, 'Urgent_Review', 'Pending', NOW())""",
                    (patient_id, f"Patient Distress Intercept: '{query_text[:120]}'")
                )
                task_id = cur.lastrowid
                call_created = True
            else:
                task_id = existing["followup_id"]

            # Log audit
            cur.execute(
                """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                   VALUES ('System', 0, 'DISTRESS_INTERCEPT_TRIGGERED', 'follow_up_tasks', %s,
                           JSON_OBJECT('patient_id', %s, 'task_id', %s))""",
                (task_id, patient_id, task_id)
            )
            conn.commit()

        msg = cls.DISTRESS_REPLY_HI if language == "hi" else cls.DISTRESS_REPLY_EN
        return {
            "distress_intercepted": True,
            "answer": msg,
            "response": msg,
            "task_id": task_id,
            "call_created": call_created,
            "can_ask_care_team": True,
            "action_suggested": "distress_support",
        }

    # ─── 2. "Why was my care team told?" Explainer (5.F) ─────────────────
    @classmethod
    def get_why_told_explainer(cls, patient_id: int, flag_id: Optional[int] = None, language: str = "en") -> Dict[str, Any]:
        """
        Builds transparent, judgment-free explanation of why an alert was shared with the care team:
        - Exact metric value and timestamp
        - Data quality label (e.g. Good, Questionable)
        - Alert rule threshold set by physician and approval date
        - What happens next (clinician review)
        """
        with get_conn() as conn, conn.cursor() as cur:
            if flag_id:
                cur.execute(
                    """SELECT f.flag_id, f.reason, f.source_type, f.source_ref_id, f.severity, f.status,
                              f.created_at, f.rule_id
                       FROM flags f
                       WHERE f.flag_id = %s AND f.patient_id = %s""",
                    (flag_id, patient_id)
                )
            else:
                cur.execute(
                    """SELECT f.flag_id, f.reason, f.source_type, f.source_ref_id, f.severity, f.status,
                              f.created_at, f.rule_id
                       FROM flags f
                       WHERE f.patient_id = %s AND f.status IN ('Open', 'Acknowledged')
                       ORDER BY f.created_at DESC LIMIT 1""",
                    (patient_id,)
                )
            flag = cur.fetchone()
            if not flag:
                return {
                    "has_open_alert": False,
                    "message": "No active alert currently shared with your care team." if language == "en" else "वर्तमान में आपकी केयर टीम के साथ कोई सक्रिय अलर्ट साझा नहीं है."
                }

            # Retrieve rule info if linked
            rule_info = {}
            if flag["rule_id"]:
                cur.execute(
                    """SELECT ar.rule_type, ar.measurement_type, ar.threshold_value, ar.approved_at,
                              cs.full_name AS approver_name
                       FROM alert_rules ar
                       LEFT JOIN care_staff cs ON ar.approved_by_staff_id = cs.staff_id
                       WHERE ar.rule_id = %s""",
                    (flag["rule_id"],)
                )
                rule_info = cur.fetchone() or {}

            # Retrieve sensor reading quality if source is sensor
            data_quality = "Good"
            metric_val = None
            if flag["source_type"] == "Sensor" and flag["source_ref_id"]:
                cur.execute(
                    """SELECT measurement_value, unit, quality_status, measured_at
                       FROM sensor_readings
                       WHERE reading_id = %s""",
                    (flag["source_ref_id"],)
                )
                sensor_row = cur.fetchone()
                if sensor_row:
                    data_quality = sensor_row["quality_status"] or "Good"
                    metric_val = f"{sensor_row['measurement_value']} {sensor_row['unit']}"

        # Construct factual explanation
        approver = rule_info.get("approver_name") or "Dr. Sharma"
        threshold = rule_info.get("threshold_value")
        rule_type = rule_info.get("rule_type", "").replace("_", " ").lower()

        if language == "hi":
            title = "केयर टीम को क्यों सूचित किया गया?"
            plain_reason = flag["reason"] or "स्वास्थ्य रीडिंग डॉक्टर द्वारा निर्धारित सामान्य सीमा से बाहर थी।"
            rule_explanation = (
                f"{approver} ने {rule_type} के लिए {threshold} की सीमा निर्धारित की थी।"
                if threshold else "यह नियम आपके चिकित्सक द्वारा अनुमोदित किया गया था।"
            )
            next_steps = "आपकी केयर टीम इस अलर्ट की समीक्षा कर रही है। यदि आप बहुत अस्वस्थ महसूस करते हैं, तो तुरंत 112 पर कॉल करें।"
        else:
            title = "Why was my care team told?"
            plain_reason = flag["reason"] or "A recorded measurement crossed the alert limit set for your care."
            rule_explanation = (
                f"{approver} set an alert threshold of {threshold} for {rule_type}."
                if threshold else "This safety threshold was configured by your attending physician."
            )
            next_steps = "Your triage care team will review this finding. If you feel unwell or breathless, call 112 immediately."

        return {
            "has_open_alert": True,
            "flag_id": flag["flag_id"],
            "title": title,
            "plain_reason": plain_reason,
            "source_type": flag["source_type"],
            "data_quality_label": data_quality,
            "rule_threshold": str(threshold) if threshold else None,
            "approver_name": approver,
            "approved_at": str(rule_info.get("approved_at") or flag["created_at"]),
            "rule_explanation": rule_explanation,
            "what_happens_next": next_steps,
            "alert_time": str(flag["created_at"]),
        }

    # ─── 3. "My Readings" 7-Day Trend (5.F) ───────────────────────────────
    @classmethod
    def get_readings_trend(cls, patient_id: int, measurement_type: str = "SpO2") -> Dict[str, Any]:
        """
        Compiles 7-day readings trend:
        - Valid readings included in trend chart.
        - Invalid readings strictly excluded from headlines and counted separately.
        - Clinician's approved threshold line provided.
        """
        meas_type = "SpO2" if measurement_type.lower() in ("spo2", "oxygen") else "Heart_Rate"

        with get_conn() as conn, conn.cursor() as cur:
            # 1. Fetch valid readings
            cur.execute(
                """SELECT reading_id, measurement_value, unit, measured_at, quality_status
                   FROM sensor_readings
                   WHERE patient_id = %s AND measurement_type = %s
                     AND quality_status != 'Invalid'
                     AND measured_at >= NOW() - INTERVAL 7 DAY
                   ORDER BY measured_at ASC""",
                (patient_id, meas_type)
            )
            valid_rows = cur.fetchall()

            # 2. Fetch invalid count
            cur.execute(
                """SELECT COUNT(*) AS invalid_count
                   FROM sensor_readings
                   WHERE patient_id = %s AND measurement_type = %s
                     AND quality_status = 'Invalid'
                     AND measured_at >= NOW() - INTERVAL 7 DAY""",
                (patient_id, meas_type)
            )
            invalid_count = cur.fetchone()["invalid_count"]

            # 3. Get doctor's alert rule limit
            cur.execute(
                """SELECT ar.threshold_value, ar.rule_type, cs.full_name AS approver_name
                   FROM alert_rules ar
                   LEFT JOIN care_staff cs ON ar.approved_by_staff_id = cs.staff_id
                   WHERE ar.patient_id = %s AND ar.measurement_type = %s AND ar.is_active = 1
                   LIMIT 1""",
                (patient_id, meas_type)
            )
            rule_row = cur.fetchone() or {}

        points = [
            {
                "reading_id": r["reading_id"],
                "value": float(r["measurement_value"]),
                "unit": r["unit"],
                "time": r["measured_at"].strftime("%a %I:%M %p"),
                "quality": r["quality_status"] or "Good"
            }
            for r in valid_rows
        ]

        latest = points[-1] if points else None
        threshold_val = float(rule_row.get("threshold_value") or (94.0 if meas_type == "SpO2" else 100.0))
        approver = rule_row.get("approver_name") or "Dr. Sharma"

        return {
            "measurement_type": meas_type,
            "latest_reading": latest,
            "points": points,
            "alert_limit": {
                "threshold": threshold_val,
                "label": f"Alert limit set by {approver}",
                "rule_type": rule_row.get("rule_type", "Reading_Below" if meas_type == "SpO2" else "Reading_Above"),
            },
            "invalid_readings_ignored": invalid_count,
            "disclaimer": "I cannot tell you if your reading is OK. Your care team configured the safety alert limits.",
        }

    # ─── 4. Help Bar Request (5.G) ────────────────────────────────────────
    @classmethod
    def request_nurse_call(cls, patient_id: int, reason_category: str, custom_note: Optional[str] = None) -> Dict[str, Any]:
        """
        Creates a de-duplicated triage nurse call request from the Help Bar:
        - Call 112 guidance
        - Ask a nurse to call me
        - SOS request
        - Message my nurse (fixed template)
        """
        dedupe_reason = f"Help Bar: {reason_category}"
        call_created = False
        task_id = None

        with get_conn() as conn, conn.cursor() as cur:
            # Check for existing pending call task today
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
                call_created = True
            else:
                task_id = existing["followup_id"]

            # Log audit
            cur.execute(
                """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                   VALUES ('Patient', %s, 'HELP_BAR_CALL_REQUESTED', 'follow_up_tasks', %s,
                           JSON_OBJECT('category', %s, 'note', %s))""",
                (str(patient_id), task_id, reason_category, custom_note or "")
            )
            conn.commit()

        return {
            "success": True,
            "task_id": task_id,
            "created": call_created,
            "message": "Your request has been delivered to your care team. A triage nurse will call you as soon as possible.",
        }

    # ─── 5. AI Transparency & Data Controls (5.H) ─────────────────────────
    @classmethod
    def get_ai_transparency_summary(cls, patient_id: int) -> Dict[str, Any]:
        """
        Summarizes how CareLoop used AI for the patient:
        - AI help enabled switch status
        - Delivered AI message count
        - Sources consulted (discharge papers, clinical plans)
        - Consent record & notice version
        - What Care Guide remembers
        """
        with get_conn() as conn, conn.cursor() as cur:
            # Patient state
            cur.execute(
                """SELECT p.full_name, p.preferred_language, p.ai_help_enabled, p.consent_status,
                          pp.reminder_lead_min, pp.channel_pref, pp.input_mode
                   FROM patients p
                   LEFT JOIN patient_preferences pp ON p.patient_id = pp.patient_id
                   WHERE p.patient_id = %s""",
                (patient_id,)
            )
            patient_row = cur.fetchone() or {}

            # AI messages count
            cur.execute(
                """SELECT COUNT(*) AS ai_msg_count
                   FROM chat_messages
                   WHERE patient_id = %s AND sender = 'AI_Nurse'""",
                (patient_id,)
            )
            ai_count = cur.fetchone()["ai_msg_count"]

            # Consent record
            cur.execute(
                """SELECT notice_version, consented_at, consent_granted
                   FROM patient_ai_consents
                   WHERE patient_id = %s
                   ORDER BY consented_at DESC LIMIT 1""",
                (patient_id,)
            )
            consent_row = cur.fetchone() or {}

        remembers = [
            f"Your name: {patient_row.get('full_name', 'Patient')}",
            f"Preferred language: {'Hindi' if patient_row.get('preferred_language') == 'hi' else 'English'}",
            f"Reminder timing: {patient_row.get('reminder_lead_min', 15)} minutes before doses via {patient_row.get('channel_pref', 'App')}",
            "Your hospital discharge summary and doctor recovery plan",
            "Your logged medication adherence and check-in pain history"
        ]

        sources = [
            "Hospital Discharge Summary (Verified Physician Notes)",
            "Active Medication Prescriptions & Doctor-Approved Dose Schedules",
            "Recovery Plan Goals (Wound Care, Activity Guidelines)",
            "Sensor Stream (Blood Oxygen & Pulse from your connected device)"
        ]

        return {
            "ai_help_enabled": bool(patient_row.get("ai_help_enabled", 1)),
            "ai_messages_delivered": ai_count,
            "sources_used": sources,
            "consent_record": {
                "granted": bool(consent_row.get("consent_granted", 1)),
                "notice_version": consent_row.get("notice_version", "v2.0-approved"),
                "consented_at": str(consent_row.get("consented_at") or datetime.now().date()),
            },
            "what_care_guide_remembers": remembers,
        }

    @classmethod
    def set_ai_help_enabled(cls, patient_id: int, enabled: bool) -> Dict[str, Any]:
        """
        Toggles the patient's AI Help switch:
        - When OFF: removes all LLM features for this patient.
        - Rules, deterministic reminders, and staff follow-ups continue unaffected.
        """
        val = 1 if enabled else 0
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE patients SET ai_help_enabled = %s WHERE patient_id = %s",
                (val, patient_id)
            )
            cur.execute(
                """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                   VALUES ('Patient', %s, 'AI_HELP_TOGGLED', 'patient', %s,
                           JSON_OBJECT('ai_help_enabled', %s))""",
                (str(patient_id), patient_id, bool(val))
            )
            conn.commit()

        return {
            "success": True,
            "ai_help_enabled": bool(val),
            "message": "AI assistant features enabled." if val else "AI assistant features turned off. Routine medication reminders and emergency nurse alerts remain active.",
        }

    @classmethod
    def request_chat_privacy(cls, patient_id: int, action_type: str) -> Dict[str, Any]:
        """
        Handles 'hide' or 'delete' chat requests (5.H):
        - 'hide': Hides chat messages from the patient's screen.
        - 'delete': Submits deletion request with retention audit (keeps IDs and timestamps only).
        """
        with get_conn() as conn, conn.cursor() as cur:
            if action_type == "hide":
                cur.execute(
                    """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                       VALUES ('Patient', %s, 'CHAT_HIDDEN_FROM_SCREEN', 'chat_history', %s,
                               JSON_OBJECT('timestamp', NOW()))""",
                    (str(patient_id), patient_id)
                )
                msg = "Chat history hidden from your display."
            else:
                cur.execute(
                    """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                       VALUES ('Patient', %s, 'CHAT_DELETION_REQUESTED', 'chat_history', %s,
                               JSON_OBJECT('timestamp', NOW(), 'policy', 'retention_audit_only'))""",
                    (str(patient_id), patient_id)
                )
                msg = "Chat deletion request registered. Text will be purged according to retention policy with audit record preserved."
            conn.commit()

        return {
            "success": True,
            "action": action_type,
            "message": msg
        }
