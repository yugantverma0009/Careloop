"""
scripts/validate_demo.py

Comprehensive Validation Suite for CareLoop Demo Dataset (Phase 1).
Exits with code 0 on complete pass; exits with code 1 with actionable failure message.
"""

import os
import sys
import pymysql
from dotenv import load_dotenv

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
        autocommit=True,
    )


def validate():
    print("🔍 Running CareLoop Demo Dataset Validation Suite...")
    conn = get_connection()
    failures = []

    with conn.cursor() as cur:
        # Check 1: Patients Count == 5
        cur.execute("SELECT COUNT(*) AS cnt FROM patients")
        p_cnt = cur.fetchone()["cnt"]
        if p_cnt != 5:
            failures.append(f"❌ Patients count mismatch: expected 5, got {p_cnt}")
        else:
            print("  ✓ Patients count is exactly 5")

        # Check 2: Care Staff Count == 2
        cur.execute("SELECT COUNT(*) AS cnt, GROUP_CONCAT(full_name) as names FROM care_staff")
        staff_row = cur.fetchone()
        s_cnt = staff_row["cnt"]
        if s_cnt != 2:
            failures.append(f"❌ Care staff count mismatch: expected 2, got {s_cnt} ({staff_row['names']})")
        else:
            print(f"  ✓ Care staff count is exactly 2 ({staff_row['names']})")

        # Check 3: User Accounts Count == 4
        cur.execute("SELECT COUNT(*) AS cnt FROM user_accounts")
        u_cnt = cur.fetchone()["cnt"]
        if u_cnt != 4:
            failures.append(f"❌ User accounts count mismatch: expected 4, got {u_cnt}")
        else:
            print("  ✓ User accounts count is exactly 4")

        # Check 4: Open Flags == 3, Resolved Flags == 2
        cur.execute("SELECT status, COUNT(*) AS cnt FROM flags GROUP BY status")
        flag_status = {r["status"]: r["cnt"] for r in cur.fetchall()}
        open_flags = flag_status.get("Open", 0)
        resolved_flags = flag_status.get("Resolved", 0)
        if open_flags != 3:
            failures.append(f"❌ Open flags mismatch: expected 3, got {open_flags}")
        else:
            print("  ✓ Exactly 3 open flags (Meera silent device, Rajesh emergency, Sunita missed doses)")

        if resolved_flags != 2:
            failures.append(f"❌ Resolved flags mismatch: expected 2, got {resolved_flags}")
        else:
            print("  ✓ Exactly 2 historical resolved flags (Aarav, Kabir)")

        # Check 5: Follow-up Tasks (5 Open, 1 Resolved)
        cur.execute("SELECT status, COUNT(*) AS cnt FROM follow_up_tasks GROUP BY status")
        task_status = {r["status"]: r["cnt"] for r in cur.fetchall()}
        open_tasks = task_status.get("Pending", 0)
        resolved_tasks = task_status.get("Resolved", 0)
        if open_tasks != 5:
            failures.append(f"❌ Open follow-up tasks mismatch: expected 5, got {open_tasks}")
        else:
            print("  ✓ Exactly 5 open follow-up tasks")

        if resolved_tasks != 1:
            failures.append(f"❌ Resolved follow-up tasks mismatch: expected 1, got {resolved_tasks}")
        else:
            print("  ✓ Exactly 1 completed follow-up task (Kabir post-op follow-up)")

        # Check 6: AI Summaries (2 Drafts, 1 Approved)
        cur.execute("SELECT status, COUNT(*) AS cnt FROM ai_summaries GROUP BY status")
        summ_status = {r["status"]: r["cnt"] for r in cur.fetchall()}
        draft_summ = summ_status.get("Draft", 0)
        appr_summ = summ_status.get("Approved", 0)
        if draft_summ != 2:
            failures.append(f"❌ Draft summaries mismatch: expected 2, got {draft_summ}")
        else:
            print("  ✓ Exactly 2 draft summaries waiting (Meera, Rajesh)")

        if appr_summ != 1:
            failures.append(f"❌ Approved summaries mismatch: expected 1, got {appr_summ}")
        else:
            print("  ✓ Exactly 1 approved summary (Kabir)")

        # Check 7: Audit Log Volume (~25-45 events)
        cur.execute("SELECT COUNT(*) AS cnt FROM audit_log")
        a_cnt = cur.fetchone()["cnt"]
        if a_cnt < 20 or a_cnt > 50:
            failures.append(f"❌ Audit log count outside target range [20, 50]: got {a_cnt}")
        else:
            print(f"  ✓ Audit log volume is clean: {a_cnt} entries")

        # Check 8: No Test Strings Leakage
        test_pattern = "%Unit test%"
        mic_pattern = "%microphone test%"
        subm_pattern = "%Identical submission test%"
        cur.execute(
            """SELECT 'flags' as tbl, COUNT(*) as cnt FROM flags WHERE reason LIKE %s
               UNION ALL SELECT 'follow_up_tasks', COUNT(*) FROM follow_up_tasks WHERE reason LIKE %s
               UNION ALL SELECT 'symptom_reports', COUNT(*) FROM symptom_reports WHERE symptom_text LIKE %s OR symptom_text LIKE %s
               UNION ALL SELECT 'ai_summaries', COUNT(*) FROM ai_summaries WHERE summary_text LIKE %s""",
            (test_pattern, test_pattern, mic_pattern, subm_pattern, test_pattern)
        )
        for r in cur.fetchall():
            if r["cnt"] > 0:
                failures.append(f"❌ Test string leakage detected in {r['tbl']}: {r['cnt']} rows found")
        print("  ✓ Zero test string leakage in flags, tasks, symptoms, or summaries")

        # Check 9: Identity Consistency (No 'Patient #N (Name)' copy mismatch)
        cur.execute(
            """SELECT f.flag_id, f.patient_id, p.full_name, f.reason
               FROM flags f
               JOIN patients p ON p.patient_id = f.patient_id
               WHERE f.reason REGEXP 'Patient #[0-9]+' AND f.reason NOT LIKE CONCAT('%', p.full_name, '%')"""
        )
        mismatched_flags = cur.fetchall()
        if mismatched_flags:
            failures.append(f"❌ Identity mismatch in flags: {len(mismatched_flags)} rows found")
        else:
            print("  ✓ Zero identity mismatches across all flags")

        # Check 10: Relative Day Consistency across all patients
        expected_days = {
            1: 3,  # Aarav: Day 3
            2: 6,  # Meera: Day 6
            3: 5,  # Rajesh: Day 5
            4: 9,  # Kabir: Day 9
            5: 4,  # Sunita: Day 4
        }
        cur.execute(
            """SELECT patient_id, DATEDIFF(CURDATE(), discharge_date) + 1 AS day_number
               FROM discharge_records
               ORDER BY patient_id ASC"""
        )
        for r in cur.fetchall():
            pid = r["patient_id"]
            calc_day = r["day_number"]
            exp_day = expected_days.get(pid)
            if calc_day != exp_day:
                failures.append(f"❌ Inconsistent day number for patient {pid}: expected Day {exp_day}, calculated Day {calc_day}")
        print("  ✓ Relative day numbers are consistent: Aarav (Day 3), Meera (Day 6), Rajesh (Day 5), Kabir (Day 9), Sunita (Day 4)")

        # Check 11: Headline Reading Valid (Never Invalid)
        cur.execute(
            """SELECT sr.patient_id, sr.measurement_type, sr.measurement_value, sr.quality_status
               FROM sensor_readings sr
               JOIN (
                   SELECT patient_id, measurement_type, MAX(measured_at) as max_at
                   FROM sensor_readings
                   WHERE quality_status != 'Invalid'
                   GROUP BY patient_id, measurement_type
               ) latest ON latest.patient_id = sr.patient_id AND latest.measurement_type = sr.measurement_type AND latest.max_at = sr.measured_at
               WHERE sr.patient_id = 1 AND sr.measurement_type = 'Heart_Rate'"""
        )
        vitals_row = cur.fetchone()
        if not vitals_row or vitals_row["quality_status"] == "Invalid" or float(vitals_row["measurement_value"]) > 200:
            failures.append(f"❌ Aarav latest valid heart rate reading check failed: {vitals_row}")
        else:
            print(f"  ✓ Aarav latest valid headline heart rate is {vitals_row['measurement_value']} bpm ({vitals_row['quality_status']}), filtering out invalid 450 bpm reading")

        # Check 12: Caregiver Consent States
        cur.execute("SELECT patient_id, full_name, consent_granted FROM caregivers WHERE patient_id IN (1, 2) ORDER BY patient_id")
        cg_rows = {r["patient_id"]: r for r in cur.fetchall()}
        if not cg_rows.get(1, {}).get("consent_granted"):
            failures.append("❌ Aarav caregiver Neha Patel must have consent_granted = 1")
        if cg_rows.get(2, {}).get("consent_granted"):
            failures.append("❌ Meera caregiver must have consent_granted = 0 (consent gate demo)")
        print("  ✓ Caregiver consent states verified: Aarav (Consent=True), Meera (Consent=False)")

    conn.close()

    if failures:
        print("\n❌ VALIDATION FAILED WITH THE FOLLOWING ERRORS:")
        for err in failures:
            print(f"  {err}")
        sys.exit(1)
    else:
        print("\n🎉 ALL 12 ACCEPTANCE CHECKS PASSED PERFECTLY!\n")
        sys.exit(0)


if __name__ == "__main__":
    validate()

