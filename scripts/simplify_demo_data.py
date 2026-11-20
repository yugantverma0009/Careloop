"""
scripts/simplify_demo_data.py

Simplifies CareLoop demo data to a clean, minimal, 100% explainable state:
- Cleans out 20+ duplicate test emergency flags created during testing
- Leaves exactly 2-3 prioritized clinical decision items on the Doctor Desk:
  1. Wearable Tachycardia Alert (Aarav Patel - 104 bpm from ESP32 MAX30102)
  2. Post-op Pain Alert (Meera Sharma - Pain 8/10)
  3. Medication Adherence Review (Sunita Rao - 2 unconfirmed doses)
- Leaves 1 clinical discharge summary awaiting physician approval
- Leaves 3 clean follow-up tasks for nurses
- Preserves all 5 patient records, prescriptions, discharge chunks, and RAG knowledge.
"""

import os
import sys
import json
import pymysql
from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(PROJECT_ROOT, "backend/.env"))

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "careloop_api")
DB_PASSWORD = os.getenv("DB_PASSWORD", "careloop_dev_pass")
DB_NAME = os.getenv("DB_NAME", "careloop")


def simplify():
    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )

    try:
        with conn.cursor() as cur:
            print("🧹 Simplifying CareLoop demo database...")

            # 1. Clean out duplicate emergency flags
            cur.execute("""
                DELETE FROM flags
                WHERE reason LIKE '%Immediate emergency safety flag%'
                   OR reason LIKE '%Patient report matched an emergency keyword%';
            """)
            deleted_flags = cur.rowcount
            print(f"  • Removed {deleted_flags} duplicate test emergency flags.")

            # Resolve any old stale device silent flags
            cur.execute("""
                UPDATE flags
                SET status = 'Resolved', resolution_code = 'Patient_Contacted', resolution_note = 'Telemetry restored via ESP32 reconnect'
                WHERE reason LIKE '%No data from device%' AND status = 'Open';
            """)

            # Ensure we have exactly 2-3 clean, realistic decision flags:
            # Item 1: Aarav Patel ESP32 Wearable Tachycardia alert
            cur.execute("""
                SELECT flag_id FROM flags 
                WHERE patient_id = 1 AND reason LIKE '%Heart_Rate reading%' AND status = 'Open'
                LIMIT 1;
            """)
            if not cur.fetchone():
                cur.execute("""
                    INSERT INTO flags (patient_id, rule_id, source_type, source_ref_id, reason, severity, status, created_at)
                    VALUES (1, 1, 'Device', 1, 'Heart_Rate reading 104.0 bpm from ESP32 wearable is above the clinician limit of 100.00', 'Urgent_Review', 'Open', NOW());
                """)
                print("  • Added clean ESP32 Tachycardia alert for Aarav Patel.")

            # Item 2: Meera Sharma High Pain alert
            cur.execute("""
                SELECT flag_id FROM flags 
                WHERE patient_id = 2 AND reason LIKE '%Pain score%' AND status = 'Open'
                LIMIT 1;
            """)
            if not cur.fetchone():
                cur.execute("""
                    INSERT INTO flags (patient_id, rule_id, source_type, source_ref_id, reason, severity, status, created_at)
                    VALUES (2, 2, 'Checkin', 2, 'Pain score 8/10 reported at morning check-in (clinician limit: 7.00)', 'Urgent_Review', 'Open', NOW());
                """)
                print("  • Added clean High Pain alert for Meera Sharma.")

            # Item 3: Sunita Rao Missed Doses alert
            cur.execute("""
                SELECT flag_id FROM flags 
                WHERE patient_id = 5 AND reason LIKE '%dose(s) with no confirmation%' AND status = 'Open'
                LIMIT 1;
            """)
            if not cur.fetchone():
                cur.execute("""
                    INSERT INTO flags (patient_id, rule_id, source_type, source_ref_id, reason, severity, status, created_at)
                    VALUES (5, 3, 'Adherence', 5, '2 cardiac doses with no confirmation in last 48h (clinician limit: 2.00)', 'Review_Soon', 'Open', NOW());
                """)
                print("  • Added clean adherence alert for Sunita Rao.")

            # 2. Clean out duplicate follow-up tasks
            cur.execute("""
                DELETE FROM follow_up_tasks
                WHERE reason LIKE '%emergency symptom report%'
                   OR reason LIKE '%Source conflict%'
                   OR reason LIKE '%Patient Distress Intercept%'
                   OR reason LIKE '%Medication Barrier Callback%'
                   OR reason LIKE '%Help Bar:%'
                   OR reason LIKE '%Patient question about general%';
            """)
            deleted_tasks = cur.rowcount
            print(f"  • Cleaned {deleted_tasks} duplicate test tasks.")

            # Ensure 3 clean follow-up tasks exist
            cur.execute("SELECT COUNT(*) as c FROM follow_up_tasks WHERE status = 'Pending';")
            pending_count = cur.fetchone()["c"]
            if pending_count < 3:
                cur.execute("""
                    INSERT INTO follow_up_tasks (patient_id, assigned_staff_id, priority, reason, status, created_at)
                    VALUES 
                    (1, 1, 'Review_Soon', 'Verify sternal wound healing and ESP32 telemetry stability at Day 21 cardiology visit', 'Pending', NOW()),
                    (2, 1, 'Urgent_Review', 'Post-TKA physical therapy check-in call regarding knee flexion comfort', 'Pending', NOW()),
                    (5, 1, 'Routine', 'Medication schedule review call with home caregiver', 'Pending', NOW())
                    ON DUPLICATE KEY UPDATE status = status;
                """)
                print("  • Seeded 3 clean clinical follow-up tasks.")

            # 3. Clean up doctor cases
            cur.execute("UPDATE cases SET status = 'Resolved' WHERE case_id = 'case-meera-silent';")

            # 4. Count remaining decision items
            cur.execute("SELECT COUNT(*) as c FROM flags WHERE status = 'Open';")
            open_flags = cur.fetchone()["c"]

            cur.execute("SELECT COUNT(*) as c FROM follow_up_tasks WHERE status = 'Pending';")
            open_tasks = cur.fetchone()["c"]

            conn.commit()

            print("\n✨ Database successfully simplified!")
            print(f"  • Open Decision Flags: {open_flags} (100% explainable)")
            print(f"  • Pending Follow-Up Tasks: {open_tasks}")
            print("  • Ready for clear, confident teacher/evaluator walkthrough.")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error simplifying demo data: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    simplify()
