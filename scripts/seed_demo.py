"""
scripts/seed_demo.py

Idempotent CareLoop Demo Seeder.
Target execution time: < 25 seconds.
Target volumes:
- Exactly 5 patients, 2 staff, 4 user logins
- Exactly 3 open flags (Meera, Rajesh, Sunita) + 2 resolved flags (Aarav, Kabir)
- Exactly 5 open tasks + 1 completed task
- Exactly 2 waiting summaries + 1 approved summary
- Exactly 6 chat messages for Aarav (with 1 refusal task, de-duplicated)
- ~30 audit events generated from genuine system actions
"""

import os
import sys
import json
from datetime import datetime, timedelta
import pymysql
from dotenv import load_dotenv

# Load backend environment
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend/.env"))
load_dotenv(env_path)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "careloop_api")
DB_PASSWORD = os.getenv("DB_PASSWORD", "careloop_dev_pass")
DB_NAME = os.getenv("DB_NAME", "careloop")


def get_connection():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def run_sql_file(conn, sql_path):
    with open(sql_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    # Strip comment lines to avoid comment-semicolon splitting issues
    sql_text = ""
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("--"):
            sql_text += line

    statements = sql_text.split(";")
    with conn.cursor() as cur:
        for stmt in statements:
            cleaned = stmt.strip()
            if cleaned:
                cur.execute(cleaned)
    conn.commit()


def main():
    print("🌱 Starting CareLoop Idempotent Demo Seeder...")
    start_time = datetime.now()

    conn = get_connection()
    try:
        # Step 1: Run reset_demo.sql from database directory
        print("  1. Running reset_demo.sql...")
        reset_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "database", "reset_demo.sql"))
        if not os.path.exists(reset_path):
            reset_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "reset_demo.sql"))
        run_sql_file(conn, reset_path)
        print("     ✓ Database reset to clean 5-patient schema.")

        with conn.cursor() as cur:
            now = datetime.now()
            today = now.date()

            # Step 2: Generate Doses using stored procedure
            print("  2. Generating medication logs...")
            # Generate doses for past days and today
            cur.execute("CALL sp_generate_daily_doses(%s)", (today - timedelta(days=2),))
            cur.execute("CALL sp_generate_daily_doses(%s)", (today - timedelta(days=1),))
            cur.execute("CALL sp_generate_daily_doses(%s)", (today,))

            # Set Aarav's past doses as Taken_Confirmed
            cur.execute(
                """UPDATE medication_logs ml
                   JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
                   SET ml.status = 'Taken_Confirmed', ml.recorded_at = ml.scheduled_for + INTERVAL 12 MINUTE, ml.recorded_by = 'Patient'
                   WHERE pr.patient_id = 1 AND ml.scheduled_for < %s""",
                (datetime.combine(today, datetime.min.time()) + timedelta(hours=8, minutes=1),)
            )

            # Set Aarav's 08:00 dose today as Taken_Confirmed
            cur.execute(
                """UPDATE medication_logs ml
                   JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
                   SET ml.status = 'Taken_Confirmed', ml.recorded_at = %s, ml.recorded_by = 'Patient'
                   WHERE pr.patient_id = 1 AND ml.scheduled_for = %s""",
                (datetime.combine(today, datetime.min.time()) + timedelta(hours=8, minutes=14),
                 datetime.combine(today, datetime.min.time()) + timedelta(hours=8))
            )

            # Set Meera's past doses as Taken_Confirmed
            cur.execute(
                """UPDATE medication_logs ml
                   JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
                   SET ml.status = 'Taken_Confirmed', ml.recorded_at = ml.scheduled_for + INTERVAL 10 MINUTE, ml.recorded_by = 'Patient'
                   WHERE pr.patient_id = 2 AND ml.scheduled_for < %s""",
                (now,)
            )

            # Set Rajesh's past doses as Taken_Confirmed
            cur.execute(
                """UPDATE medication_logs ml
                   JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
                   SET ml.status = 'Taken_Confirmed', ml.recorded_at = ml.scheduled_for + INTERVAL 8 MINUTE, ml.recorded_by = 'Patient'
                   WHERE pr.patient_id = 3 AND ml.scheduled_for < %s""",
                (now,)
            )

            # Set Kabir's past doses as Taken_Confirmed (100% adherence)
            cur.execute(
                """UPDATE medication_logs ml
                   JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
                   SET ml.status = 'Taken_Confirmed', ml.recorded_at = ml.scheduled_for + INTERVAL 5 MINUTE, ml.recorded_by = 'Patient'
                   WHERE pr.patient_id = 4 AND ml.scheduled_for < %s""",
                (now,)
            )

            # Set Sunita's past confirmed doses, leaving exactly 2 missed doses in last 48 hours for rule evaluation
            cur.execute(
                """UPDATE medication_logs ml
                   JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
                   SET ml.status = 'Taken_Confirmed', ml.recorded_at = ml.scheduled_for + INTERVAL 15 MINUTE, ml.recorded_by = 'Patient'
                   WHERE pr.patient_id = 5 AND ml.scheduled_for < %s""",
                (now,)
            )
            cur.execute(
                """UPDATE medication_logs
                   SET status = 'Missed', recorded_at = NULL, recorded_by = NULL
                   WHERE prescription_id = (SELECT prescription_id FROM prescriptions WHERE patient_id = 5 LIMIT 1)
                     AND scheduled_for < %s
                   ORDER BY scheduled_for DESC LIMIT 2""",
                (now,)
            )

            # Step 3: Insert Telemetry Readings
            print("  3. Inserting telemetry readings...")
            # Aarav: 12 valid readings over 3 days
            aarav_readings = [
                # Day -2
                (1, "DEV-ESP32-001", "Heart_Rate", 74.0, "bpm", now - timedelta(days=2, hours=4), "Good"),
                (1, "DEV-ESP32-001", "SpO2", 98.0, "%", now - timedelta(days=2, hours=4), "Good"),
                (1, "DEV-ESP32-001", "Heart_Rate", 76.0, "bpm", now - timedelta(days=2), "Good"),
                (1, "DEV-ESP32-001", "SpO2", 97.0, "%", now - timedelta(days=2), "Good"),
                # Day -1
                (1, "DEV-ESP32-001", "Heart_Rate", 75.0, "bpm", now - timedelta(days=1, hours=6), "Good"),
                (1, "DEV-ESP32-001", "SpO2", 98.0, "%", now - timedelta(days=1, hours=6), "Good"),
                (1, "DEV-ESP32-001", "Heart_Rate", 78.0, "bpm", now - timedelta(days=1), "Good"),
                (1, "DEV-ESP32-001", "SpO2", 97.0, "%", now - timedelta(days=1), "Good"),
                # Today
                (1, "DEV-ESP32-001", "Heart_Rate", 72.0, "bpm", now - timedelta(hours=3), "Good"),
                (1, "DEV-ESP32-001", "SpO2", 98.0, "%", now - timedelta(hours=3), "Good"),
                (1, "DEV-ESP32-001", "Heart_Rate", 74.0, "bpm", now - timedelta(minutes=25), "Good"),
                (1, "DEV-ESP32-001", "SpO2", 97.0, "%", now - timedelta(minutes=25), "Good"),
                # Aarav: 1 invalid spike (450 bpm) 2 hours ago to demonstrate data plausibility guard
                (1, "DEV-ESP32-001", "Heart_Rate", 450.0, "bpm", now - timedelta(hours=2), "Invalid"),
            ]
            for pid, dev_id, mtype, val, unit, mtime, qstat in aarav_readings:
                cur.execute(
                    """INSERT INTO sensor_readings (patient_id, device_id, measurement_type, measurement_value, unit, measured_at, quality_status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (pid, dev_id, mtype, val, unit, mtime, qstat)
                )

            # Rajesh: valid baseline readings 20 min ago
            cur.execute(
                """INSERT INTO sensor_readings (patient_id, device_id, measurement_type, measurement_value, unit, measured_at, quality_status) VALUES
                   (3, 'DEV-ESP32-003', 'Heart_Rate', 88.0, 'bpm', NOW() - INTERVAL 20 MINUTE, 'Simulated'),
                   (3, 'DEV-ESP32-003', 'SpO2', 95.0, '%', NOW() - INTERVAL 20 MINUTE, 'Simulated')"""
            )

            # Kabir: valid baseline readings
            cur.execute(
                """INSERT INTO sensor_readings (patient_id, device_id, measurement_type, measurement_value, unit, measured_at, quality_status) VALUES
                   (4, 'DEV-ESP32-004', 'Heart_Rate', 70.0, 'bpm', NOW() - INTERVAL 30 MINUTE, 'Simulated'),
                   (4, 'DEV-ESP32-004', 'SpO2', 99.0, '%', NOW() - INTERVAL 30 MINUTE, 'Simulated')"""
            )

            # Sunita: valid baseline readings
            cur.execute(
                """INSERT INTO sensor_readings (patient_id, device_id, measurement_type, measurement_value, unit, measured_at, quality_status) VALUES
                   (5, 'DEV-ESP32-005', 'Heart_Rate', 82.0, 'bpm', NOW() - INTERVAL 45 MINUTE, 'Simulated'),
                   (5, 'DEV-ESP32-005', 'SpO2', 96.0, '%', NOW() - INTERVAL 45 MINUTE, 'Simulated')"""
            )

            # Step 4: Fire genuine stored procedures for Rule Engine Flags
            print("  4. Running clinical rule procedures...")
            # Flag 1: Meera Sharma (No Data > 6 hours)
            cur.execute("CALL sp_evaluate_no_data_rules(%s)", (now,))
            # Flag 2: Sunita Rao (Missed Doses >= 2 in 48 hours)
            cur.execute("CALL sp_evaluate_missed_dose_rules(%s)", (now,))

            # Step 5: Insert Rajesh Verma's Emergency Symptom Check-in (fires trg_symptom_rules_after_insert)
            print("  5. Submitting Rajesh emergency symptom check-in...")
            cur.execute(
                """INSERT INTO symptom_reports (patient_id, symptom_text, pain_level, reported_at, input_method, language, emergency_keyword_hit, review_status)
                   VALUES (3, 'सीने में तेज दर्द और सांस लेने में कठिनाई', 5, NOW() - INTERVAL 20 MINUTE, 'Text', 'hi', 1, 'Follow_Up_Required')"""
            )
            # trg_symptom_rules_after_insert creates Flag 3 (Emergency, Urgent_Review)

            # Step 6: Insert 2 Historical Resolved Flags
            print("  6. Recording resolved historical flags...")
            # Aarav: Resolved early post-op tachycardia on Day 1
            cur.execute(
                """INSERT INTO flags (patient_id, rule_id, source_type, reason, severity, status, created_at, acknowledged_by_staff_id, acknowledged_at, resolved_by_staff_id, resolved_at, resolution_code, resolution_note)
                   VALUES (1, 2, 'Sensor', 'Heart_Rate reading 104.0 bpm is above the clinician-approved limit of 100.00', 'Review_Soon', 'Resolved',
                           NOW() - INTERVAL 2 DAY + INTERVAL 4 HOUR, 1, NOW() - INTERVAL 2 DAY + INTERVAL 5 HOUR, 1, NOW() - INTERVAL 2 DAY + INTERVAL 6 HOUR,
                           'Patient_Contacted', 'Expected post-surgical tachycardia. Resolved after oral hydration and rest.')"""
            )
            aarav_flag_id = cur.lastrowid
            cur.execute(
                """INSERT INTO flag_events (flag_id, event_type, staff_id, note, created_at) VALUES
                   (%s, 'Created', NULL, 'Triggered by sensor threshold', NOW() - INTERVAL 2 DAY + INTERVAL 4 HOUR),
                   (%s, 'Acknowledged', 1, 'Reviewing ECG and hydration status', NOW() - INTERVAL 2 DAY + INTERVAL 5 HOUR),
                   (%s, 'Resolved', 1, 'Expected post-surgical tachycardia resolved', NOW() - INTERVAL 2 DAY + INTERVAL 6 HOUR)""",
                (aarav_flag_id, aarav_flag_id, aarav_flag_id)
            )

            # Kabir: Resolved mild surgical site pain on Day 2
            cur.execute(
                """INSERT INTO flags (patient_id, rule_id, source_type, reason, severity, status, created_at, acknowledged_by_staff_id, acknowledged_at, resolved_by_staff_id, resolved_at, resolution_code, resolution_note)
                   VALUES (4, 12, 'Symptom', 'Pain score 5 reached the clinician-approved limit of 5.00', 'Review_Soon', 'Resolved',
                           NOW() - INTERVAL 7 DAY, 2, NOW() - INTERVAL 7 DAY + INTERVAL 30 MINUTE, 2, NOW() - INTERVAL 7 DAY + INTERVAL 2 HOUR,
                           'Patient_Contacted', 'Advised cold pack application and oral analgesic adherence.')"""
            )

            # Step 7: Record Escalations for the 3 Open Flags
            print("  7. Writing escalation ladder history...")
            # Get flag_ids for Meera, Sunita, Rajesh
            cur.execute("SELECT flag_id, patient_id FROM flags WHERE status = 'Open' ORDER BY flag_id ASC")
            open_flags = cur.fetchall()

            for f in open_flags:
                pid = f["patient_id"]
                fid = f["flag_id"]
                if pid == 2:  # Meera: silent device + caregiver consent NOT granted
                    cur.execute(
                        """INSERT INTO escalations (flag_id, step_no, step_type, channel, sent_at, delivery_status, notes) VALUES
                           (%s, 1, 'Patient_Prompt', 'App', NOW() - INTERVAL 2 HOUR, 'Sent', 'Prompted patient to check wearable connection'),
                           (%s, 2, 'Caregiver_SMS', 'SMS', NOW() - INTERVAL 90 MINUTE, 'Skipped_No_Consent', 'Caregiver has not granted consent'),
                           (%s, 3, 'Nurse_Alert', 'Dashboard', NOW() - INTERVAL 60 MINUTE, 'Sent', 'Escalated to triage nurse queue')""",
                        (fid, fid, fid)
                    )
                elif pid == 3:  # Rajesh: emergency check-in
                    cur.execute(
                        """INSERT INTO escalations (flag_id, step_no, step_type, channel, sent_at, delivery_status, notes) VALUES
                           (%s, 1, 'Nurse_Alert', 'Dashboard', NOW() - INTERVAL 20 MINUTE, 'Sent', 'Immediate safety review routed to nurse queue'),
                           (%s, 2, 'Doctor_Alert', 'SMS', NOW() - INTERVAL 15 MINUTE, 'Sent', 'Emergency check-in matched acute chest pain')""",
                        (fid, fid)
                    )
                elif pid == 5:  # Sunita: missed doses
                    cur.execute(
                        """INSERT INTO escalations (flag_id, step_no, step_type, channel, sent_at, delivery_status, notes) VALUES
                           (%s, 1, 'Patient_Prompt', 'App', NOW() - INTERVAL 3 HOUR, 'Sent', 'Medication confirmation reminder sent'),
                           (%s, 2, 'Nurse_Alert', 'Dashboard', NOW() - INTERVAL 2 HOUR, 'Sent', 'Escalated to nurse queue after 2 missed doses')""",
                        (fid, fid)
                    )

            # Step 8: Follow-up Tasks (Exactly 5 open, 1 completed)
            print("  8. Creating follow-up tasks...")
            cur.execute(
                """INSERT INTO follow_up_tasks (patient_id, flag_id, assigned_staff_id, reason, priority, status, due_at, created_at) VALUES
                   (3, (SELECT flag_id FROM flags WHERE patient_id=3 AND status='Open' LIMIT 1), 2,
                    'Immediate clinical follow-up: emergency symptom report (severe chest pain in Hindi check-in)', 'Urgent_Review', 'Pending', NOW() + INTERVAL 15 MINUTE, NOW() - INTERVAL 20 MINUTE),
                   (2, (SELECT flag_id FROM flags WHERE patient_id=2 AND status='Open' LIMIT 1), 2,
                    'Contact patient regarding silent wearable device (>6h no telemetry received)', 'Review_Soon', 'Pending', NOW() + INTERVAL 2 HOUR, NOW() - INTERVAL 60 MINUTE),
                   (5, (SELECT flag_id FROM flags WHERE patient_id=5 AND status='Open' LIMIT 1), 2,
                    'Medication adherence review: 2 unconfirmed cardiac doses in 48h', 'Review_Soon', 'Pending', NOW() + INTERVAL 1 HOUR, NOW() - INTERVAL 2 HOUR),
                   (5, NULL, 2,
                    'Review patient medication question: patient asked to stop blood pressure medicine', 'Review_Soon', 'Pending', NOW() + INTERVAL 3 HOUR, NOW() - INTERVAL 3 HOUR),
                   (1, NULL, 2,
                    'Routine Day 4 post-CABG check-in call with patient', 'Routine', 'Pending', NOW() + INTERVAL 24 HOUR, NOW() - INTERVAL 4 HOUR)"""
            )
            # 1 Completed task for Kabir Mehta
            cur.execute(
                """INSERT INTO follow_up_tasks (patient_id, flag_id, assigned_staff_id, reason, priority, status, due_at, created_at, completed_at, outcome_code, outcome_notes)
                   VALUES (4, NULL, 2, 'Post-appendectomy wound healing phone follow-up', 'Routine', 'Resolved',
                           NOW() - INTERVAL 1 DAY, NOW() - INTERVAL 2 DAY, NOW() - INTERVAL 1 DAY, 'Reached_And_Advised',
                           'Patient reached via phone. Confirmed incision is healing well with no signs of infection. Ambulation on track.')"""
            )

            # Step 9: AI Summaries (Exactly 2 waiting drafts, 1 approved)
            print("  9. Generating clinical AI summaries...")
            # Draft 1: Meera Sharma
            cur.execute(
                """INSERT INTO ai_summaries (patient_id, period_start, period_end, summary_text, model_name, status, source_snapshot)
                   VALUES (2, NOW() - INTERVAL 5 DAY, NOW(),
                           'Post-discharge Days 1 to 5 summary for Meera Sharma. Patient recovering from total knee arthroplasty. Prescribed JointEase-XR 1 tablet morning. Wearable device silent for 8 hours exceeding 6-hour approved threshold. Caregiver consent not granted. Follow-up clinic appointment scheduled in 7 days.',
                           'gemini-1.5-flash', 'Draft',
                           JSON_OBJECT('day_number', 6, 'discharge_date', DATE_FORMAT(CURDATE() - INTERVAL 5 DAY, '%d %b %Y'), 'total_medications_scheduled', 1, 'total_doses_taken', 4, 'total_doses_skipped', 0, 'total_doses_unconfirmed', 1, 'adherence', '80%', 'vitals_count', 18, 'open_flags', 1, 'silent_hours', 8))"""
            )
            # Draft 2: Rajesh Verma
            cur.execute(
                """INSERT INTO ai_summaries (patient_id, period_start, period_end, summary_text, model_name, status, source_snapshot)
                   VALUES (3, NOW() - INTERVAL 4 DAY, NOW(),
                           'Post-discharge Days 1 to 4 summary for Rajesh Verma. Patient recovering from community pneumonia. Prescribed BronchoClear-10 twice daily. Patient submitted Hindi check-in matching emergency keyword for acute chest pain (pain score 8/10). Immediate clinical review pending with attending physician.',
                           'gemini-1.5-flash', 'Draft',
                           JSON_OBJECT('day_number', 5, 'discharge_date', DATE_FORMAT(CURDATE() - INTERVAL 4 DAY, '%d %b %Y'), 'total_medications_scheduled', 1, 'total_doses_taken', 6, 'total_doses_skipped', 1, 'total_doses_unconfirmed', 1, 'adherence', '75%', 'vitals_count', 24, 'emergency_hits', 1, 'open_flags', 1))"""
            )
            # Approved 1: Kabir Mehta
            cur.execute(
                """INSERT INTO ai_summaries (patient_id, period_start, period_end, summary_text, model_name, status, reviewed_by_staff_id, reviewed_at, edited_text, source_snapshot)
                   VALUES (4, NOW() - INTERVAL 8 DAY, NOW() - INTERVAL 1 DAY,
                           'Post-discharge Days 1 to 7 recovery note. Patient recovering from uncomplicated appendectomy. Adherence to GastroShield-D confirmed. Incision pain resolved. Wearable telemetry within limits.',
                           'gemini-1.5-flash', 'Approved', 1, NOW() - INTERVAL 1 DAY,
                           'Post-discharge Days 1 to 7 recovery note for Kabir Mehta. Patient recovering from uncomplicated appendectomy. Adherence to GastroShield-D confirmed at 95%. Incision pain resolved. Wearable telemetry within limits. Approved for standard recovery progression.',
                           JSON_OBJECT('day_number', 8, 'discharge_date', DATE_FORMAT(CURDATE() - INTERVAL 8 DAY, '%d %b %Y'), 'total_medications_scheduled', 1, 'total_doses_taken', 7, 'total_doses_skipped', 0, 'total_doses_unconfirmed', 0, 'adherence', '100%', 'vitals_count', 42, 'open_flags', 0))"""
            )

            # Step 10: Aarav's Exact 6 Chat Messages (Assistant v2 Seed Contract)
            print("  10. Seeding Aarav chat messages...")
            conv_id = f"conv-aarav-{today.strftime('%Y%m%d')}"
            chat_data = [
                # 1. Next appointment (Tool-grounded via care plan)
                ("Patient", "When is my next appointment?", None, None, conv_id, None, {}),
                ("AI_Nurse", "Your next scheduled cardiology appointment is on post-discharge day 7 at 10:30 AM with Dr. Ananya Sharma at OPD Clinic Room 302.", 1, "structured", conv_id, 2, {"intent": "appointment", "tool_used": True}),
                # 2. Warning signs (Document-grounded, cites Warning Signs chunk 3, page 2)
                ("Patient", "What warning signs should I watch for?", None, None, conv_id, None, {}),
                ("AI_Nurse", "Watch for severe chest tightness, sudden shortness of breath, SpO2 dropping below 94%, or heart rate above 100 bpm. Call 112 immediately if chest pain is severe or radiating.", 1, "grounded", conv_id, 3, {"intent": "warning_signs", "source_ids": ["S1"]}),
                # 3. Refusal dose question (deterministic refusal, creates 1 task)
                ("Patient", "Can I double my dose?", None, None, conv_id, None, {}),
                ("AI_Nurse", "I cannot advise on changing or doubling your medication dose. Your discharge instructions state to take your medicines exactly as prescribed. I have alerted your care team to follow up with you directly.", 0, "refusal_dose", conv_id, None, {"intent": "refusal_dose"}),
                # 4. Diet not found (not in papers)
                ("Patient", "What should I eat?", None, None, conv_id, None, {}),
                ("AI_Nurse", "I could not find specific dietary instructions in your discharge summary. Please consult your care team or clinical dietitian for personalized nutrition guidance.", 0, "not_found", conv_id, None, {"intent": "diet", "found": False}),
                # 5. Follow-up (Document-grounded, cites Activity Guidelines chunk 4, page 3)
                ("Patient", "Understood, thank you. Is walking permitted?", None, None, conv_id, None, {}),
                ("AI_Nurse", "Yes, your discharge instructions state: walk indoors for 10-15 minutes twice daily. Avoid lifting objects heavier than 5 kg.", 1, "grounded", conv_id, 4, {"intent": "activity", "source_ids": ["S1"]}),
                # 6. Thank you (Small talk, NO source chip, name inserted by code)
                ("Patient", "Thank you for the guidance.", None, None, conv_id, None, {}),
                ("AI_Nurse", "You are welcome, Aarav. Please rest and reach out if you notice any warning signs.", 0, "not_found", conv_id, None, {"intent": "small_talk", "answer_type": "small_talk", "llm_called": False, "name_inserted_by_code": True}),
            ]
            for sender, text, is_grnd, ans_type, cid, target_chunk_id, rdebug in chat_data:
                cur.execute(
                    """INSERT INTO chat_messages (patient_id, sender, message_text, is_grounded, answer_type, conversation_id, retrieval_debug, created_at)
                       VALUES (1, %s, %s, %s, %s, %s, %s, NOW() - INTERVAL 4 HOUR + INTERVAL 5 MINUTE)""",
                    (sender, text, is_grnd, ans_type, cid, json.dumps(rdebug) if rdebug else None)
                )
                msg_id = cur.lastrowid
                if target_chunk_id:
                    cur.execute(
                        """INSERT INTO chat_message_sources (message_id, chunk_id)
                           VALUES (%s, %s)""",
                        (msg_id, target_chunk_id)
                    )

            # Step 11: Aarav's Check-in History (5 check-ins, mild pain 1-3)
            print("  11. Inserting patient check-in records...")
            checkins = [
                (1, "Feeling slightly fatigued after walking, but breathing comfortably.", 2, now - timedelta(days=2), "en"),
                (1, "Resting well. Sternal wound site has mild soreness.", 2, now - timedelta(days=1, hours=8), "en"),
                (1, "Morning check-in: no dizziness, took morning medicines with water.", 1, now - timedelta(days=1), "en"),
                (1, "Evening check-in: rested comfortably, pulse feels steady.", 1, now - timedelta(hours=14), "en"),
                (1, "Today morning check-in: mild stiffness upon waking, pain 2/10. Took morning dose.", 2, now - timedelta(hours=2), "en"),
            ]
            for pid, text, pain, rtime, lang in checkins:
                cur.execute(
                    """INSERT INTO symptom_reports (patient_id, symptom_text, pain_level, reported_at, input_method, language, emergency_keyword_hit, review_status)
                       VALUES (%s, %s, %s, %s, 'Text', %s, 0, 'Reviewed')""",
                    (pid, text, pain, rtime, lang)
                )

            # Step 12: Audit Events (~30 events from genuine actions)
            print("  12. Generating verifiable audit log entries...")
            audit_events = [
                # System Init
                ("System", "system_init", "SEED_SYSTEM_INITIALIZE", "system", 1, {"patients": 5, "staff": 2}, now - timedelta(days=10)),
                # Doctor Sharma alert rules setup
                ("Staff", "1", "ALERT_RULES_APPROVED", "patient", 1, {"rules_count": 6, "attending": "Dr. Ananya Sharma"}, now - timedelta(days=2)),
                ("Staff", "1", "ALERT_RULES_APPROVED", "patient", 2, {"rules_count": 3, "attending": "Dr. Ananya Sharma"}, now - timedelta(days=5)),
                ("Staff", "1", "ALERT_RULES_APPROVED", "patient", 3, {"rules_count": 2, "attending": "Dr. Ananya Sharma"}, now - timedelta(days=4)),
                ("Staff", "1", "ALERT_RULES_APPROVED", "patient", 4, {"rules_count": 2, "attending": "Dr. Ananya Sharma"}, now - timedelta(days=8)),
                ("Staff", "1", "ALERT_RULES_APPROVED", "patient", 5, {"rules_count": 3, "attending": "Dr. Ananya Sharma"}, now - timedelta(days=3)),
                # Doses Taken by Aarav
                ("Patient", "1", "DOSE_CONFIRMED", "medication_log", 1, {"medicine": "CardioPulse-XR", "scheduled": "08:00:00", "status": "Taken_Confirmed"}, now - timedelta(days=1, hours=15)),
                ("Patient", "1", "DOSE_CONFIRMED", "medication_log", 2, {"medicine": "VasculoNorm-5", "scheduled": "13:00:00", "status": "Taken_Confirmed"}, now - timedelta(days=1, hours=10)),
                ("Patient", "1", "DOSE_CONFIRMED", "medication_log", 3, {"medicine": "CardioPulse-XR", "scheduled": "20:00:00", "status": "Taken_Confirmed"}, now - timedelta(days=1, hours=3)),
                ("Patient", "1", "DOSE_CONFIRMED", "medication_log", 4, {"medicine": "CardioPulse-XR", "scheduled": "08:00:00", "status": "Taken_Confirmed"}, now - timedelta(minutes=16)),
                # Sensor Ingestion
                ("Device", "DEV-ESP32-001", "INGEST_READINGS", "sensor_reading", 1, {"measurement": "Heart_Rate", "value": 74.0, "quality": "Good"}, now - timedelta(minutes=25)),
                ("Device", "DEV-ESP32-001", "INGEST_READINGS", "sensor_reading", 2, {"measurement": "SpO2", "value": 97.0, "quality": "Good"}, now - timedelta(minutes=25)),
                # Meera silent device flag & escalation
                ("Agent", "rule_engine", "FLAG_CREATED", "flag", 1, {"rule": "No_Data_Hours", "patient_id": 2, "severity": "Review_Soon"}, now - timedelta(hours=2)),
                ("Agent", "escalation_agent", "ESCALATION_STEP", "escalation", 1, {"step": 1, "type": "Patient_Prompt", "status": "Sent"}, now - timedelta(hours=2)),
                ("Agent", "escalation_agent", "ESCALATION_STEP", "escalation", 2, {"step": 2, "type": "Caregiver_SMS", "status": "Skipped_No_Consent"}, now - timedelta(minutes=90)),
                ("Agent", "escalation_agent", "ESCALATION_STEP", "escalation", 3, {"step": 3, "type": "Nurse_Alert", "status": "Sent"}, now - timedelta(minutes=60)),
                # Rajesh emergency flag & escalation
                ("Patient", "3", "SUBMIT_SYMPTOM_REPORT", "symptom_report", 1, {"emergency_hit": True, "pain": 8}, now - timedelta(minutes=20)),
                ("Agent", "rule_engine", "FLAG_CREATED", "flag", 2, {"source": "Emergency", "severity": "Urgent_Review"}, now - timedelta(minutes=20)),
                ("Agent", "escalation_agent", "ESCALATION_STEP", "escalation", 4, {"step": 1, "type": "Nurse_Alert", "status": "Sent"}, now - timedelta(minutes=20)),
                ("Agent", "escalation_agent", "ESCALATION_STEP", "escalation", 5, {"step": 2, "type": "Doctor_Alert", "status": "Sent"}, now - timedelta(minutes=15)),
                # Sunita missed doses flag
                ("Agent", "rule_engine", "FLAG_CREATED", "flag", 3, {"rule": "Missed_Doses", "severity": "Review_Soon"}, now - timedelta(hours=3)),
                ("Agent", "escalation_agent", "ESCALATION_STEP", "escalation", 6, {"step": 1, "type": "Patient_Prompt", "status": "Sent"}, now - timedelta(hours=3)),
                ("Agent", "escalation_agent", "ESCALATION_STEP", "escalation", 7, {"step": 2, "type": "Nurse_Alert", "status": "Sent"}, now - timedelta(hours=2)),
                # Clinical Summaries
                ("Staff", "1", "APPROVE_AI_SUMMARY", "ai_summary", 3, {"patient_id": 4, "approver": "Dr. Ananya Sharma"}, now - timedelta(days=1)),
                ("Staff", "2", "TASK_COMPLETED", "follow_up_task", 6, {"patient_id": 4, "outcome": "Reached_And_Advised"}, now - timedelta(days=1)),
                # Chat assistant interactions
                ("Patient", "1", "CHAT_QUERY", "chat_message", 1, {"query": "When is my next appointment?"}, now - timedelta(hours=4)),
                ("Patient", "1", "CHAT_QUERY", "chat_message", 5, {"query": "Can I double my dose?", "refusal": True}, now - timedelta(hours=3, minutes=50)),
            ]
            for atype, aid, action, etype, eid, details, cat in audit_events:
                cur.execute(
                    """INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (atype, aid, action, etype, eid, json.dumps(details), cat)
                )

            # Step 13: Seed Scheduled Actions for Feature F1 Rounds (~15 upcoming, ~20 history)
            print("  13. Seeding Rounds scheduled actions...")
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            cur.execute("TRUNCATE TABLE plan_understanding_checks")
            cur.execute("TRUNCATE TABLE recovery_plan_items")
            cur.execute("TRUNCATE TABLE recovery_plans")
            cur.execute("TRUNCATE TABLE scheduled_actions")
            cur.execute("TRUNCATE TABLE agent_proposals")
            cur.execute("SET FOREIGN_KEY_CHECKS = 1")

            # 15 Upcoming Scheduled Actions (next 24 hours)
            upcoming_actions = [
                # Aarav Patel (Patient 1)
                (1, "Dose_Reminder", "SMS", now + timedelta(hours=1), "Scheduled", "Dose reminder: VasculoNorm-5 scheduled for 13:00", json.dumps({"medicine": "VasculoNorm-5", "log_id": 2}), f"seed_up_1_{now.strftime('%Y%m%d%H')}"),
                (1, "Dose_Reminder", "SMS", now + timedelta(hours=1, minutes=30), "Scheduled", "Follow-up reminder: VasculoNorm-5 (if unconfirmed)", json.dumps({"medicine": "VasculoNorm-5", "log_id": 2}), f"seed_up_2_{now.strftime('%Y%m%d%H')}"),
                (1, "Dose_Reminder", "SMS", now + timedelta(hours=7, minutes=50), "Scheduled", "Dose reminder: CardioPulse-XR scheduled for 20:00", json.dumps({"medicine": "CardioPulse-XR", "log_id": 3}), f"seed_up_3_{now.strftime('%Y%m%d%H')}"),
                (1, "Checkin_Prompt", "App", now + timedelta(hours=18), "Scheduled", "Scheduled daily post-discharge recovery check-in prompt", json.dumps({"date": str(today + timedelta(days=1))}), f"seed_up_4_{now.strftime('%Y%m%d%H')}"),
                # Meera Sharma (Patient 2)
                (2, "Dose_Reminder", "SMS", now + timedelta(hours=17, minutes=50), "Scheduled", "Dose reminder: JointEase-XR scheduled for 09:00", json.dumps({"medicine": "JointEase-XR"}), f"seed_up_5_{now.strftime('%Y%m%d%H')}"),
                (2, "Checkin_Prompt", "App", now + timedelta(hours=18), "Scheduled", "Scheduled daily post-discharge recovery check-in prompt", json.dumps({"date": str(today + timedelta(days=1))}), f"seed_up_6_{now.strftime('%Y%m%d%H')}"),
                (2, "Photo_Request", "App", now + timedelta(hours=4), "Scheduled", "Wound site visual check-in: Day 5 post-arthroplasty", json.dumps({"plan_item_id": 12}), f"seed_up_7_{now.strftime('%Y%m%d%H')}"),
                # Rajesh Verma (Patient 3)
                (3, "Dose_Reminder", "SMS", now + timedelta(hours=7, minutes=50), "Scheduled", "Dose reminder: BronchoClear-10 scheduled for 20:00", json.dumps({"medicine": "BronchoClear-10"}), f"seed_up_8_{now.strftime('%Y%m%d%H')}"),
                (3, "Checkin_Prompt", "App", now + timedelta(hours=18), "Scheduled", "Scheduled daily post-discharge recovery check-in prompt", json.dumps({"date": str(today + timedelta(days=1))}), f"seed_up_9_{now.strftime('%Y%m%d%H')}"),
                # Kabir Mehta (Patient 4)
                (4, "Dose_Reminder", "SMS", now + timedelta(hours=17, minutes=50), "Scheduled", "Dose reminder: GastroShield-D scheduled for 08:00", json.dumps({"medicine": "GastroShield-D"}), f"seed_up_10_{now.strftime('%Y%m%d%H')}"),
                (4, "Checkin_Prompt", "App", now + timedelta(hours=18), "Scheduled", "Scheduled daily post-discharge recovery check-in prompt", json.dumps({"date": str(today + timedelta(days=1))}), f"seed_up_11_{now.strftime('%Y%m%d%H')}"),
                # Sunita Rao (Patient 5)
                (5, "Dose_Reminder", "SMS", now + timedelta(hours=7, minutes=50), "Scheduled", "Dose reminder: CardioPulse-XR scheduled for 20:00", json.dumps({"medicine": "CardioPulse-XR"}), f"seed_up_12_{now.strftime('%Y%m%d%H')}"),
                (5, "Checkin_Prompt", "App", now + timedelta(hours=18), "Scheduled", "Scheduled daily post-discharge recovery check-in prompt", json.dumps({"date": str(today + timedelta(days=1))}), f"seed_up_13_{now.strftime('%Y%m%d%H')}"),
                (5, "Welcome_Call_Task", "Task", now + timedelta(hours=22), "Scheduled", "Welcome follow-up call with assigned nurse", json.dumps({"channel": "Phone"}), f"seed_up_14_{now.strftime('%Y%m%d%H')}"),
                (1, "Plan_Prompt", "App", now + timedelta(hours=8), "Scheduled", "Evening hydration & light ambulation reminder", json.dumps({"plan_item_id": 4}), f"seed_up_15_{now.strftime('%Y%m%d%H')}"),
            ]
            for pid, atype, chan, rat, stat, reas, pay, dkey in upcoming_actions:
                cur.execute(
                    """INSERT INTO scheduled_actions (patient_id, action_type, channel, run_at, status, reason, payload, dedupe_key)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (pid, atype, chan, rat, stat, reas, pay, dkey)
                )

            # 20 History Actions (past 24 hours: Done / Skipped with explicit reasons)
            history_actions = [
                # Aarav (Patient 1)
                (1, "Dose_Reminder", "SMS", now - timedelta(hours=4), now - timedelta(hours=4), "Done", "Dose reminder: CardioPulse-XR scheduled for 08:00", "Sent reminder", f"seed_hist_1_{now.strftime('%Y%m%d%H')}"),
                (1, "Checkin_Prompt", "App", now - timedelta(hours=3), now - timedelta(hours=3), "Done", "Scheduled morning recovery check-in prompt", "Prompt dispatched", f"seed_hist_2_{now.strftime('%Y%m%d%H')}"),
                (1, "Dose_Reminder", "SMS", now - timedelta(hours=14), now - timedelta(hours=14), "Done", "Dose reminder: CardioPulse-XR scheduled for 20:00", "Sent reminder", f"seed_hist_3_{now.strftime('%Y%m%d%H')}"),
                (1, "Dose_Reminder", "SMS", now - timedelta(hours=21), now - timedelta(hours=21), "Done", "Dose reminder: VasculoNorm-5 scheduled for 13:00", "Sent reminder", f"seed_hist_4_{now.strftime('%Y%m%d%H')}"),
                # Meera (Patient 2)
                (2, "Dose_Reminder", "SMS", now - timedelta(hours=3), now - timedelta(hours=3), "Done", "Dose reminder: JointEase-XR scheduled for 09:00", "Sent reminder", f"seed_hist_5_{now.strftime('%Y%m%d%H')}"),
                (2, "Checkin_Prompt", "App", now - timedelta(hours=3), now - timedelta(hours=3), "Skipped", "Scheduled daily check-in prompt", "Blocked: Caregiver sharing not granted", f"seed_hist_6_{now.strftime('%Y%m%d%H')}"),
                (2, "Dose_Reminder", "SMS", now - timedelta(hours=27), now - timedelta(hours=27), "Done", "Dose reminder: JointEase-XR scheduled for 09:00", "Sent reminder", f"seed_hist_7_{now.strftime('%Y%m%d%H')}"),
                # Rajesh (Patient 3)
                (3, "Dose_Reminder", "SMS", now - timedelta(hours=4), now - timedelta(hours=4), "Done", "Dose reminder: BronchoClear-10 scheduled for 08:00", "Sent reminder", f"seed_hist_8_{now.strftime('%Y%m%d%H')}"),
                (3, "Checkin_Prompt", "App", now - timedelta(hours=3), now - timedelta(hours=3), "Done", "Scheduled daily check-in prompt", "Prompt dispatched", f"seed_hist_9_{now.strftime('%Y%m%d%H')}"),
                (3, "Dose_Reminder", "SMS", now - timedelta(hours=14), now - timedelta(hours=14), "Done", "Dose reminder: BronchoClear-10 scheduled for 20:00", "Sent reminder", f"seed_hist_10_{now.strftime('%Y%m%d%H')}"),
                (3, "Plan_Prompt", "App", now - timedelta(hours=1), now - timedelta(hours=1), "Skipped", "Post-meal deep breathing exercise prompt", "Blocked: Patient has an active emergency flag; non-emergency automation is suppressed.", f"seed_hist_11_{now.strftime('%Y%m%d%H')}"),
                # Kabir (Patient 4)
                (4, "Dose_Reminder", "SMS", now - timedelta(hours=4), now - timedelta(hours=4), "Done", "Dose reminder: GastroShield-D scheduled for 08:00", "Sent reminder", f"seed_hist_12_{now.strftime('%Y%m%d%H')}"),
                (4, "Checkin_Prompt", "App", now - timedelta(hours=3), now - timedelta(hours=3), "Done", "Scheduled daily check-in prompt", "Prompt dispatched", f"seed_hist_13_{now.strftime('%Y%m%d%H')}"),
                (4, "Dose_Reminder", "SMS", now - timedelta(hours=28), now - timedelta(hours=28), "Done", "Dose reminder: GastroShield-D scheduled for 08:00", "Sent reminder", f"seed_hist_14_{now.strftime('%Y%m%d%H')}"),
                # Sunita (Patient 5)
                (5, "Dose_Reminder", "SMS", now - timedelta(hours=4), now - timedelta(hours=4), "Done", "Dose reminder: CardioPulse-XR scheduled for 08:00", "Sent reminder", f"seed_hist_15_{now.strftime('%Y%m%d%H')}"),
                (5, "Dose_Reminder", "SMS", now - timedelta(hours=3, minutes=30), now - timedelta(hours=3, minutes=30), "Done", "Follow-up reminder: CardioPulse-XR (dose unconfirmed)", "Sent follow-up reminder", f"seed_hist_16_{now.strftime('%Y%m%d%H')}"),
                (5, "Checkin_Prompt", "App", now - timedelta(hours=3), now - timedelta(hours=3), "Done", "Scheduled daily check-in prompt", "Prompt dispatched", f"seed_hist_17_{now.strftime('%Y%m%d%H')}"),
                (5, "Dose_Reminder", "SMS", now - timedelta(hours=14), now - timedelta(hours=14), "Done", "Dose reminder: CardioPulse-XR scheduled for 20:00", "Sent reminder", f"seed_hist_18_{now.strftime('%Y%m%d%H')}"),
                (5, "Dose_Reminder", "SMS", now - timedelta(hours=13, minutes=30), now - timedelta(hours=13, minutes=30), "Done", "Follow-up reminder: CardioPulse-XR (dose unconfirmed)", "Sent follow-up reminder", f"seed_hist_19_{now.strftime('%Y%m%d%H')}"),
                (1, "Dose_Reminder", "SMS", now - timedelta(hours=7), now - timedelta(hours=7), "Skipped", "Scheduled 01:00 nighttime dose check", "Blocked by quiet hours policy (22:00 to 07:00). Scheduled for morning.", f"seed_hist_20_{now.strftime('%Y%m%d%H')}"),
            ]
            for pid, atype, chan, rat, dat, stat, reas, res, dkey in history_actions:
                cur.execute(
                    """INSERT INTO scheduled_actions (patient_id, action_type, channel, run_at, done_at, status, reason, result, dedupe_key)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (pid, atype, chan, rat, dat, stat, reas, res, dkey)
                )

            # Step 14: Seed Agent Proposals (2 pending proposals)
            print("  14. Seeding Rounds agent proposals...")
            proposals = [
                (1, "Rounds", "Suggest_Call", "Call Aarav: 2 check-ins unanswered", json.dumps({"missed_checkins": 2, "last_completed": str(today - timedelta(days=1))})),
                (2, "Rounds", "Suggest_Photo", "Ask for a photo today: Day 5 post-arthroplasty wound check due", json.dumps({"post_op_day": 5, "condition": "Total Knee Arthroplasty"})),
            ]
            for pid, aname, ptype, reas, evid in proposals:
                cur.execute(
                    """INSERT INTO agent_proposals (patient_id, agent_name, proposal_type, reason, evidence, status, created_at)
                       VALUES (%s, %s, %s, %s, %s, 'Pending', %s)""",
                    (pid, aname, ptype, reas, evid, now - timedelta(hours=1))
                )

            # Step 15: Seed Check-in Sessions & Two-Way SMS Messages (Phase 2)
            print("  15. Seeding Check-in Sessions and Two-Way SMS Messages...")
            # 15a. Completed Check-in session for Aarav
            cur.execute(
                """INSERT INTO checkin_sessions (session_id, patient_id, template_id, channel, status, current_step, started_at, completed_at, symptom_report_id)
                   VALUES (1, 1, 1, 'App_Guided', 'Completed', 5, NOW() - INTERVAL 1 DAY, NOW() - INTERVAL 1 DAY + INTERVAL 3 MINUTE, 1)"""
            )
            answers = [
                (1, 1, "1", "Scale: 1/10"),
                (1, 2, "No", "Emergency: No"),
                (1, 3, "all", "Choice: All taken"),
                (1, 4, "fine", "Choice: Healing well"),
                (1, 5, "Morning walk went smoothly.", "Text: Morning walk went smoothly."),
            ]
            for sid, qid, val, raw in answers:
                cur.execute(
                    """INSERT INTO checkin_answers (session_id, question_id, answer_value, raw_input, created_at)
                       VALUES (%s, %s, %s, %s, NOW() - INTERVAL 1 DAY)""",
                    (sid, qid, val, raw)
                )

            # 15b. Two-Way SMS messages for Aarav & Neha
            sms_data = [
                ("Outbound", 1, None, "+91-98765-43210", "CareLoop Reminder: CardioPulse-XR scheduled at 08:00 AM. Reply 1 if taken, 2 if skipped.", "Dose_Reminder", "medication_log", 1, "Logged", now - timedelta(hours=13, minutes=10)),
                ("Inbound", 1, None, "+91-98765-43210", "1", None, "medication_log", 1, "Received", now - timedelta(hours=13, minutes=8)),
                ("Outbound", 1, None, "+91-98765-43210", "Confirmed: Your dose of CardioPulse-XR (08:00 AM) has been marked taken. Thank you.", "Dose_Confirmation", "medication_log", 1, "Logged", now - timedelta(hours=13, minutes=7)),
                ("Outbound", 1, None, "+91-98765-43210", "CareLoop: Your daily recovery check-in is ready. Open your portal or reply 1 to confirm doses.", "Checkin_Prompt", "checkin_session", 1, "Logged", now - timedelta(hours=4)),
            ]
            for direct, pid, cid, ph, body, tkey, rtype, rid, stat, cat in sms_data:
                cur.execute(
                    """INSERT INTO sms_messages (direction, patient_id, caregiver_id, phone, body, template_key, related_type, related_id, status, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (direct, pid, cid, ph, body, tkey, rtype, rid, stat, cat)
                )

            # 16. Seed Synthetic Wound Photos (Phase 3 Feature F4)
            print("  16. Seeding synthetic wound photos for Aarav and Meera...")
            from PIL import Image, ImageDraw
            import hashlib

            photos_dir = os.path.join(PROJECT_ROOT, "data", "wound_photos")
            thumbs_dir = os.path.join(photos_dir, "thumbs")
            os.makedirs(thumbs_dir, exist_ok=True)

            def make_synthetic_photo(label_text: str, filename_base: str, bg_color=(235, 230, 225)):
                img = Image.new("RGB", (800, 800), color=bg_color)
                draw = ImageDraw.Draw(img)
                # Geometric markers to ensure high sharpness/contrast
                for i in range(50, 750, 60):
                    draw.line([(i, 50), (i, 750)], fill=(210, 205, 200), width=1)
                    draw.line([(50, i), (750, i)], fill=(210, 205, 200), width=1)
                # Synthetic wound incision marker
                draw.rectangle([(390, 200), (410, 600)], fill=(180, 80, 80), outline=(140, 50, 50), width=2)
                for s in range(240, 580, 40):
                    draw.line([(370, s), (430, s)], fill=(60, 60, 60), width=2)

                draw.rectangle([(60, 60), (740, 140)], fill=(15, 23, 42))
                draw.text((80, 80), label_text, fill=(255, 255, 255))
                draw.text((80, 105), "CareLoop Sample Image · Not a Real Patient · Synthetic Telemetry", fill=(148, 163, 184))

                main_name = f"{filename_base}.jpg"
                thumb_name = f"{filename_base}_thumb.jpg"
                main_p = os.path.join(photos_dir, main_name)
                thumb_p = os.path.join(thumbs_dir, thumb_name)

                img.save(main_p, format="JPEG", quality=88)
                thumb_img = img.copy()
                thumb_img.thumbnail((320, 320))
                thumb_img.save(thumb_p, format="JPEG", quality=80)

                with open(main_p, "rb") as f:
                    sha = hashlib.sha256(f.read()).hexdigest()

                return os.path.join("data", "wound_photos", main_name), os.path.join("data", "wound_photos", "thumbs", thumb_name), sha

            # Photo 1: Aarav Baseline (Day 1 - Reviewed)
            p1_main, p1_thumb, p1_sha = make_synthetic_photo("Aarav Patel · Sternal Incision Baseline (Post-Op Day 1)", "aarav_day1_baseline")
            cur.execute(
                """INSERT INTO wound_photos (patient_id, file_path, thumb_path, sha256, quality_status, quality_details, patient_note, review_status, finding, review_note, reviewed_by_staff_id, reviewed_at, taken_at)
                   VALUES (%s, %s, %s, %s, 'Usable', %s, %s, 'Reviewed', 'No_Concern_Seen', %s, 2, %s, %s)""",
                (1, p1_main, p1_thumb, p1_sha, json.dumps({"width": 800, "height": 800, "sharpness": 1240.5, "brightness": 128.2}), "Incision site dry and intact on discharge day 1", "Clean sternal surgical incision, edges well-approximated, no exudate or erythema.", now - timedelta(days=2), now - timedelta(days=2, hours=1))
            )

            # Photo 2: Aarav Day 3 (Current - Pending Review)
            p2_main, p2_thumb, p2_sha = make_synthetic_photo("Aarav Patel · Sternal Incision Recovery (Post-Op Day 3)", "aarav_day3_check")
            cur.execute(
                """INSERT INTO wound_photos (patient_id, file_path, thumb_path, sha256, quality_status, quality_details, patient_note, review_status, finding, taken_at)
                   VALUES (%s, %s, %s, %s, 'Usable', %s, %s, 'Pending', NULL, %s)""",
                (1, p2_main, p2_thumb, p2_sha, json.dumps({"width": 800, "height": 800, "sharpness": 1180.2, "brightness": 125.0}), "Suture line healing, mild tightness near top, no fever or drainage.", now - timedelta(hours=3, minutes=30))
            )

            # Photo 3: Meera Knee Portal (Day 4 - Reviewed)
            p3_main, p3_thumb, p3_sha = make_synthetic_photo("Meera Sharma · Knee Arthroscopy Portal Check (Post-Op Day 4)", "meera_day4_knee")
            cur.execute(
                """INSERT INTO wound_photos (patient_id, file_path, thumb_path, sha256, quality_status, quality_details, patient_note, review_status, finding, review_note, reviewed_by_staff_id, reviewed_at, taken_at)
                   VALUES (%s, %s, %s, %s, 'Usable', %s, %s, 'Reviewed', 'No_Concern_Seen', %s, 2, %s, %s)""",
                (2, p3_main, p3_thumb, p3_sha, json.dumps({"width": 800, "height": 800, "sharpness": 1310.0, "brightness": 130.4}), "Portal dressing removed as instructed, light walking started.", "Arthroscopy portal healing normally, minimal expected post-op effusion, no signs of infection.", now - timedelta(days=1), now - timedelta(days=1, hours=2))
            )

            # 17. Seed Recovery Plans & Understanding Checks (Phase 4 Feature F5)
            print("  17. Seeding recovery plans and understanding checks for cohort...")

            # 17.1 Aarav Patel (Patient 1) — Plan v1 (Approved by Dr. Ananya Sharma)
            cur.execute(
                """INSERT INTO recovery_plans (plan_id, patient_id, version, status, source_document_id, drafted_by, drafted_at, approved_by_staff_id, approved_at)
                   VALUES (1, 1, 1, 'Approved', 1, 'Agent', %s, 1, %s)""",
                (now - timedelta(days=2, hours=2), now - timedelta(days=2))
            )
            aarav_items = [
                (1, 1, 'Medicine', 'CardioPulse-XR', '1 tablet morning (08:00) and evening (20:00).', '08:00 and 20:00', 1, 'Matches', 2, now - timedelta(days=2, hours=1), 1),
                (2, 1, 'Medicine', 'VasculoNorm-5', '1 tablet afternoon (13:00) with water. Do not modify or double doses without doctor review.', '13:00 with water', 1, 'Matches', 2, now - timedelta(days=2, hours=1), 2),
                (3, 1, 'Appointment', 'Cardiology OPD Follow-up', 'Your next scheduled cardiology appointment is on post-discharge day 7 at 10:30 AM with Dr. Ananya Sharma at OPD Clinic Room 302.', 'Day 7 at 10:30 AM', 2, 'Not_Applicable', 2, now - timedelta(days=2, hours=1), 3),
                (4, 1, 'Warning_Sign', 'Emergency Red Flag Signs', 'Watch for severe chest tightness, sudden shortness of breath, SpO2 dropping below 94%, or heart rate above 100 bpm. Call 112 immediately if chest pain is severe or radiating.', 'Immediate — 112', 3, 'Not_Applicable', 2, now - timedelta(days=2, hours=1), 4),
                (5, 1, 'Activity', 'Physical Mobility Guidelines', 'Walk indoors for 10-15 minutes twice daily. Avoid lifting objects heavier than 5 kg. Sleep on your back with upper torso elevated.', 'Twice daily', 4, 'Not_Applicable', 2, now - timedelta(days=2, hours=1), 5),
                (6, 1, 'Wound_Care', 'Daily Sternal Incision Care', 'Keep sternal incision dry and clean. Do not apply unauthorized ointments. Check daily for redness, warmth, or unusual drainage.', 'Daily at morning check-in', 5, 'Not_Applicable', 2, now - timedelta(days=2, hours=1), 6),
            ]
            for it in aarav_items:
                cur.execute(
                    """INSERT INTO recovery_plan_items (item_id, plan_id, item_type, title, detail, schedule_text, source_chunk_id, reconcile_status, verified_by_staff_id, verified_at, display_order)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    it
                )

            # Aarav Understanding Check (3 questions, 2 answered correctly, 1 pending)
            cur.execute(
                """INSERT INTO plan_understanding_checks (check_id, patient_id, plan_id, question_text, options, correct_option_index, selected_option_index, is_correct, answered_at)
                   VALUES (1, 1, 1, 'According to your recovery papers, when should you take CardioPulse-XR?',
                           %s, 0, 0, 1, %s)""",
                (json.dumps(["08:00 and 20:00 as instructed in your discharge plan", "Only when feeling acute pain", "Once every three days"]), now - timedelta(days=1))
            )
            cur.execute(
                """INSERT INTO plan_understanding_checks (check_id, patient_id, plan_id, question_text, options, correct_option_index, selected_option_index, is_correct, answered_at)
                   VALUES (2, 1, 1, 'If you experience severe chest pain, sudden breathlessness, or heavy bleeding, what is the correct action?',
                           %s, 0, 0, 1, %s)""",
                (json.dumps(["Call 112 or emergency services immediately and press SOS", "Wait 24 hours to see if symptoms resolve", "Take an extra sleeping pill"]), now - timedelta(days=1))
            )
            cur.execute(
                """INSERT INTO plan_understanding_checks (check_id, patient_id, plan_id, question_text, options, correct_option_index, selected_option_index, is_correct, answered_at)
                   VALUES (3, 1, 1, 'What is your recommended physical activity guidance?',
                           %s, 0, NULL, NULL, NULL)""",
                (json.dumps(["Walk indoors for 10-15 minutes twice daily; avoid lifting over 5 kg", "Heavy weightlifting and intense exercise daily", "Complete bed rest without moving"]), )
            )

            # 17.2 Kabir Mehta (Patient 4) — Plan v1 (Approved, 3 of 3 understanding check correct)
            cur.execute(
                """INSERT INTO recovery_plans (plan_id, patient_id, version, status, source_document_id, drafted_by, drafted_at, approved_by_staff_id, approved_at)
                   VALUES (2, 4, 1, 'Approved', 4, 'Agent', %s, 1, %s)""",
                (now - timedelta(days=6), now - timedelta(days=5))
            )
            cur.execute(
                """INSERT INTO recovery_plan_items (item_id, plan_id, item_type, title, detail, schedule_text, source_chunk_id, reconcile_status, verified_by_staff_id, verified_at, display_order)
                   VALUES (7, 2, 'Medicine', 'GastroShield-D', '1 capsule morning before meals.', 'Morning before meals', 10, 'Matches', 2, %s, 1)""",
                (now - timedelta(days=5),)
            )
            cur.execute(
                """INSERT INTO recovery_plan_items (item_id, plan_id, item_type, title, detail, schedule_text, source_chunk_id, reconcile_status, verified_by_staff_id, verified_at, display_order)
                   VALUES (8, 2, 'Appointment', 'Incision Clearance Visit', 'Follow-up visit scheduled in 6 days for incision clearance.', 'In 6 days', 11, 'Not_Applicable', 2, %s, 2)""",
                (now - timedelta(days=5),)
            )

            for c_id, q_text in enumerate([
                "When should you take GastroShield-D?",
                "What is the scheduled timeline for your incision clearance appointment?",
                "What should you do if sudden severe stomach distress occurs?"
            ], start=4):
                cur.execute(
                    """INSERT INTO plan_understanding_checks (check_id, patient_id, plan_id, question_text, options, correct_option_index, selected_option_index, is_correct, answered_at)
                       VALUES (%s, 4, 2, %s, %s, 0, 0, 1, %s)""",
                    (c_id, q_text, json.dumps(["Correct clinical recommendation per discharge papers", "Incorrect option A", "Incorrect option B"]), now - timedelta(days=4))
                )

            # 17.3 Meera Sharma (Patient 2) — Plan v1 (Draft waiting for doctor, contains Mismatch example)
            cur.execute(
                """INSERT INTO recovery_plans (plan_id, patient_id, version, status, source_document_id, drafted_by, drafted_at)
                   VALUES (3, 2, 1, 'Draft', 2, 'Agent', %s)""",
                (now - timedelta(hours=6),)
            )
            cur.execute(
                """INSERT INTO recovery_plan_items (item_id, plan_id, item_type, title, detail, schedule_text, source_chunk_id, reconcile_status, verified_by_staff_id, verified_at, display_order)
                   VALUES (9, 3, 'Medicine', 'JointEase-XR', '1 tablet twice daily with water.', 'Twice daily', 6, 'Mismatch', NULL, NULL, 1)"""
            )
            cur.execute(
                """INSERT INTO recovery_plan_items (item_id, plan_id, item_type, title, detail, schedule_text, source_chunk_id, reconcile_status, verified_by_staff_id, verified_at, display_order)
                   VALUES (10, 3, 'Appointment', 'Range of Motion Evaluation', 'Follow up with Dr. Ananya Sharma in 7 days for range-of-motion evaluation.', 'In 7 days', 7, 'Not_Applicable', 2, %s, 2)""",
                (now - timedelta(hours=5),)
            )

            # 17.4 Sunita Rao (Patient 5) — Plan v1 (Draft waiting for doctor)
            cur.execute(
                """INSERT INTO recovery_plans (plan_id, patient_id, version, status, source_document_id, drafted_by, drafted_at)
                   VALUES (4, 5, 1, 'Draft', 5, 'Agent', %s)""",
                (now - timedelta(hours=4),)
            )
            cur.execute(
                """INSERT INTO recovery_plan_items (item_id, plan_id, item_type, title, detail, schedule_text, source_chunk_id, reconcile_status, verified_by_staff_id, verified_at, display_order)
                   VALUES (11, 4, 'Medicine', 'CardioPulse-XR', '1 tablet twice daily with water.', 'Twice daily', 12, 'Matches', NULL, NULL, 1)"""
            )
            cur.execute(
                """INSERT INTO recovery_plan_items (item_id, plan_id, item_type, title, detail, schedule_text, source_chunk_id, reconcile_status, verified_by_staff_id, verified_at, display_order)
                   VALUES (12, 4, 'Warning_Sign', 'Adherence & Fluid Warning Signs', 'Missed doses or sudden weight gain requires immediate clinical review.', 'Immediate', 13, 'Not_Applicable', NULL, NULL, 2)"""
            )

            # Step 18: Seed Watch Events & Possible Fall Baseline Data (Phase 5 Feature F7)
            print("  18. Seeding Watch Events and Possible Fall prompt counters...")
            cur.execute("TRUNCATE TABLE device_events")

            # Aarav Patel (Patient 1, DEV-ESP32-001): 1 answered prompt yesterday (Answered OK)
            cur.execute(
                """INSERT INTO device_events
                   (event_id, device_id, patient_id, event_type, occurred_at, details, prompt_sent_at, patient_response, responded_at)
                   VALUES (1, 'DEV-ESP32-001', 1, 'Possible_Fall', %s, %s, %s, 'Ok', %s)""",
                (
                    now - timedelta(days=1, hours=2),
                    json.dumps({"peak_movement": 3.4, "stillness_seconds": 12, "battery_pct": 86}),
                    now - timedelta(days=1, hours=2),
                    now - timedelta(days=1, hours=1, minutes=59),
                )
            )

            # Meera Sharma (Patient 2, DEV-ESP32-002): 1 low battery event
            cur.execute(
                """INSERT INTO device_events
                   (event_id, device_id, patient_id, event_type, occurred_at, details)
                   VALUES (2, 'DEV-ESP32-002', 2, 'Low_Battery', %s, %s)""",
                (
                    now - timedelta(days=2),
                    json.dumps({"battery_pct": 14}),
                )
            )

            # 19. Seed Chroma vector collections from document_chunks
            print("  19. Indexing discharge document chunks into ChromaDB...")
            try:
                import chromadb
                from backend.app.rag import get_embedding_fn
                ef = get_embedding_fn()
                chroma_path = os.getenv("CHROMA_PATH", "./chroma")
                chroma_client = chromadb.PersistentClient(path=chroma_path)

                cur.execute("SELECT document_id, vector_collection FROM discharge_documents")
                docs = cur.fetchall()
                for doc in docs:
                    c_name = doc["vector_collection"]
                    try:
                        chroma_client.delete_collection(c_name)
                    except Exception:
                        pass
                    if ef:
                        col = chroma_client.create_collection(c_name, embedding_function=ef)
                    else:
                        col = chroma_client.create_collection(c_name)

                    cur.execute(
                        "SELECT chunk_id, chunk_index, chunk_text FROM document_chunks WHERE document_id = %s",
                        (doc["document_id"],)
                    )
                    c_rows = cur.fetchall()
                    if c_rows:
                        ids = [f"{doc['document_id']}-{r['chunk_index']}" for r in c_rows]
                        texts = [r["chunk_text"] for r in c_rows]
                        col.add(ids=ids, documents=texts)
            except Exception as e:
                print(f"      [Warning] Chroma collection indexing skipped: {e}")


        conn.commit()
        duration = (datetime.now() - start_time).total_seconds()
        print(f"✅ Seeding complete in {duration:.2f} seconds!")
    except Exception as e:
        conn.rollback()
        print(f"❌ Seeding failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
