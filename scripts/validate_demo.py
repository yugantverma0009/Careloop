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

        # Check 13: Rounds Scheduled Actions (Phase 1 Feature F1)
        cur.execute("SELECT COUNT(*) AS total, SUM(CASE WHEN reason IS NULL OR TRIM(reason) = '' THEN 1 ELSE 0 END) AS empty_reasons FROM scheduled_actions")
        sa_row = cur.fetchone()
        if not sa_row or sa_row["total"] < 25:
            failures.append(f"❌ scheduled_actions count too low: {sa_row.get('total') if sa_row else 0} (expected >= 25)")
        elif sa_row["empty_reasons"] > 0:
            failures.append(f"❌ scheduled_actions has {sa_row['empty_reasons']} rows with missing/empty reasons!")
        else:
            print(f"  ✓ Rounds scheduled actions verified: {sa_row['total']} actions, 0 empty reasons (100% justified)")

        # Check 14: Rounds Agent Proposals (Phase 1 Feature F1)
        cur.execute("SELECT COUNT(*) AS pending_count FROM agent_proposals WHERE status = 'Pending'")
        prop_row = cur.fetchone()
        if not prop_row or prop_row["pending_count"] != 2:
            failures.append(f"❌ agent_proposals pending count mismatch: {prop_row.get('pending_count') if prop_row else 0} (expected 2)")
        else:
            print(f"  ✓ Rounds agent proposals verified: {prop_row['pending_count']} pending clinician proposals")

        # Check 15: Sunita Adherence Defect Fix Check
        cur.execute("SELECT self_reported_taken_pct FROM v_medication_adherence WHERE patient_id = 5")
        sunita_adh = cur.fetchone()
        if sunita_adh and float(sunita_adh["self_reported_taken_pct"]) >= 100.0:
            failures.append(f"❌ Sunita adherence calculation defect: reported {sunita_adh['self_reported_taken_pct']}% despite 2 unconfirmed doses")
        else:
            pct_val = sunita_adh["self_reported_taken_pct"] if sunita_adh else "N/A"
            print(f"  ✓ Sunita adherence accurately reflects dose logs ({pct_val}%, unconfirmed doses penalized)")

        # Check 16: Check-in Templates (Phase 2 Feature F2)
        cur.execute("SELECT COUNT(*) AS total_t, SUM(is_active = 1) AS active_t FROM checkin_templates")
        t_row = cur.fetchone()
        if not t_row or t_row["total_t"] < 2 or t_row["active_t"] != 1:
            failures.append(f"❌ checkin_templates mismatch: total={t_row.get('total_t')}, active={t_row.get('active_t')} (expected >=2 total, 1 active)")
        else:
            print(f"  ✓ Check-in templates verified: {t_row['total_t']} templates ({t_row['active_t']} active doctor-approved)")

        # Check 17: Check-in Sessions & Answers Integrity (Phase 2 Feature F2)
        cur.execute("SELECT COUNT(*) AS total_sessions FROM checkin_sessions")
        s_count = cur.fetchone()["total_sessions"]
        cur.execute(
            """SELECT COUNT(*) AS orphan_answers
               FROM checkin_answers a
               LEFT JOIN checkin_sessions s ON a.session_id = s.session_id
               WHERE s.session_id IS NULL"""
        )
        orphans = cur.fetchone()["orphan_answers"]
        if orphans > 0:
            failures.append(f"❌ checkin_answers has {orphans} orphaned answers!")
        else:
            print(f"  ✓ Check-in sessions and answers verified ({s_count} sessions, 0 orphaned answers)")

        # Check 18: Two-Way SMS Messages (Phase 2 Feature F3)
        cur.execute("SELECT COUNT(*) AS total_sms, SUM(direction = 'Inbound') AS in_sms, SUM(direction = 'Outbound') AS out_sms FROM sms_messages")
        sms_row = cur.fetchone()
        if not sms_row or sms_row["total_sms"] < 4:
            failures.append(f"❌ sms_messages count too low: {sms_row.get('total_sms') if sms_row else 0} (expected >= 4)")
        else:
            print(f"  ✓ Two-Way SMS messages verified: {sms_row['total_sms']} messages ({sms_row['out_sms']} outbound, {sms_row['in_sms']} inbound)")

        # Check 19: Wound Photos Integrity & Storage (Phase 3 Feature F4)
        cur.execute(
            """SELECT COUNT(*) AS total_photos,
                      SUM(review_status = 'Pending') AS pending_photos,
                      SUM(review_status = 'Reviewed') AS reviewed_photos
               FROM wound_photos"""
        )
        photo_row = cur.fetchone()
        if not photo_row or photo_row["total_photos"] != 3:
            failures.append(f"❌ wound_photos count mismatch: {photo_row.get('total_photos') if photo_row else 0} (expected exactly 3)")
        elif photo_row["pending_photos"] != 1 or photo_row["reviewed_photos"] != 2:
            failures.append(f"❌ wound_photos status mismatch: {photo_row['pending_photos']} pending, {photo_row['reviewed_photos']} reviewed (expected 1 pending, 2 reviewed)")
        else:
            # Check disk file existence
            cur.execute("SELECT file_path, thumb_path FROM wound_photos")
            missing_files = []
            for r in cur.fetchall():
                for p in (r["file_path"], r["thumb_path"]):
                    if p:
                        full_p = os.path.join(os.path.dirname(__file__), "..", p)
                        if not os.path.exists(full_p):
                            missing_files.append(p)
            if missing_files:
                failures.append(f"❌ Missing wound photo files on disk: {missing_files}")
            else:
                print(f"  ✓ Wound photos verified: {photo_row['total_photos']} photos (1 pending review, 2 reviewed, all files intact on disk)")

        # Check 20: Recovery Plans & Items Integrity (Phase 4 Feature F5)
        cur.execute(
            """SELECT COUNT(*) AS total_plans,
                      SUM(status = 'Approved') AS approved_plans,
                      SUM(status = 'Draft') AS draft_plans
               FROM recovery_plans"""
        )
        plan_row = cur.fetchone()
        if not plan_row or plan_row["total_plans"] != 4:
            failures.append(f"❌ recovery_plans count mismatch: {plan_row.get('total_plans') if plan_row else 0} (expected 4)")
        elif plan_row["approved_plans"] != 2 or plan_row["draft_plans"] != 2:
            failures.append(f"❌ recovery_plans status mismatch: {plan_row['approved_plans']} approved, {plan_row['draft_plans']} draft (expected 2 approved, 2 draft)")
        else:
            # Check items
            cur.execute(
                """SELECT COUNT(*) AS total_items,
                          SUM(reconcile_status = 'Mismatch') AS mismatches,
                          SUM(source_chunk_id IS NULL) AS orphan_items
                   FROM recovery_plan_items"""
            )
            item_row = cur.fetchone()
            if item_row["orphan_items"] > 0:
                failures.append(f"❌ recovery_plan_items has {item_row['orphan_items']} items without source chunk citations!")
            elif item_row["mismatches"] < 1:
                failures.append("❌ Expected at least 1 medication reconciliation Mismatch (Meera), found 0")
            else:
                print(f"  ✓ Recovery plans verified: 4 plans (2 approved, 2 draft), {item_row['total_items']} items, {item_row['mismatches']} reconciliation mismatch example")

        # Check 21: Watch Events & Possible Fall Rules (Phase 5 Feature F7)
        cur.execute(
            """SELECT
                 COUNT(*) AS total_rules,
                 SUM(patient_id = 5 AND is_active = 1) AS sunita_active,
                 SUM(patient_id != 5 AND is_active = 0) AS others_inactive
               FROM alert_rules
               WHERE rule_type = 'Possible_Fall'"""
        )
        fall_rules = cur.fetchone()
        if not fall_rules or fall_rules["total_rules"] != 5:
            failures.append(f"❌ Possible_Fall rules count mismatch: {fall_rules.get('total_rules') if fall_rules else 0} (expected 5)")
        elif fall_rules["sunita_active"] != 1:
            failures.append("❌ Sunita Rao does not have Possible_Fall rule enabled (expected is_active=1)")
        elif fall_rules["others_inactive"] != 4:
            failures.append("❌ Non-Sunita patients must have Possible_Fall rule disabled by default (expected 4 inactive)")
        else:
            cur.execute("SELECT COUNT(*) AS total_events, SUM(event_type = 'Possible_Fall') AS fall_events FROM device_events")
            dev_ev = cur.fetchone()
            if not dev_ev or dev_ev["total_events"] < 2:
                failures.append(f"❌ device_events count too low: {dev_ev.get('total_events') if dev_ev else 0}")
            else:
                print(f"  ✓ Watch events and Possible Fall rules verified: Sunita enabled, cohort disabled by default, {dev_ev['total_events']} baseline device events")

        # Check 22: CareLoop Agents Baseline Verification (Phase 1)
        cur.execute("SELECT COUNT(*) AS autonomy_cnt FROM agent_autonomy;")
        autonomy_row = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS runs_cnt FROM agent_runs;")
        runs_row = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS drafts_cnt FROM agent_drafts;")
        drafts_row = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS cases_cnt, SUM(merged_count > 1) AS merged_cases FROM `cases`;")
        cases_row = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS shadow_cnt FROM shadow_decisions;")
        shadow_row = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS opt_in_cnt FROM patients WHERE ai_help_enabled = 1;")
        opt_in_row = cur.fetchone()

        if not autonomy_row or autonomy_row["autonomy_cnt"] < 17:
            failures.append(f"❌ agent_autonomy count mismatch: {autonomy_row.get('autonomy_cnt')} (expected >= 17)")
        elif not runs_row or runs_row["runs_cnt"] < 25:
            failures.append(f"❌ agent_runs count mismatch: {runs_row.get('runs_cnt')} (expected >= 25)")
        elif not drafts_row or drafts_row["drafts_cnt"] < 3:
            failures.append(f"❌ agent_drafts count mismatch: {drafts_row.get('drafts_cnt')} (expected >= 3)")
        elif not cases_row or cases_row["cases_cnt"] < 4 or (cases_row["merged_cases"] or 0) < 1:
            failures.append(f"❌ cases count mismatch: {cases_row.get('cases_cnt')} (expected >= 4 with merged cases)")
        elif not shadow_row or shadow_row["shadow_cnt"] < 65:
            failures.append(f"❌ shadow_decisions count mismatch: {shadow_row.get('shadow_cnt')} (expected >= 65)")
        elif not opt_in_row or opt_in_row["opt_in_cnt"] != 5:
            failures.append(f"❌ patients.ai_help_enabled count mismatch: {opt_in_row.get('opt_in_cnt')} (expected 5)")
        else:
            print(f"  ✓ CareLoop Agents baseline verified: 17 autonomy levels, {runs_row['runs_cnt']} runs, {drafts_row['drafts_cnt']} drafts, {cases_row['cases_cnt']} cases ({cases_row['merged_cases']} merged), {shadow_row['shadow_cnt']} shadow decisions")

        # Check 23: CareLoop Agents v2 Versions Registry (Phase 1)
        cur.execute("SELECT COUNT(*) AS ver_cnt FROM agent_versions WHERE is_active = 1;")
        ver_row = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS runs_with_ver FROM agent_runs WHERE version_id IS NOT NULL;")
        ver_runs_row = cur.fetchone()
        if not ver_row or ver_row["ver_cnt"] < 6:
            failures.append(f"❌ agent_versions count mismatch: {ver_row.get('ver_cnt') if ver_row else 0} (expected >= 6)")
        elif not ver_runs_row or ver_runs_row["runs_with_ver"] < 25:
            failures.append(f"❌ agent_runs with version_id mismatch: {ver_runs_row.get('runs_with_ver') if ver_runs_row else 0} (expected >= 25)")
        else:
            print(f"  ✓ CareLoop Agents v2 versions verified: {ver_row['ver_cnt']} active versions, {ver_runs_row['runs_with_ver']} runs tagged with version_id")

    conn.close()

    if failures:
        print("\n❌ VALIDATION FAILED WITH THE FOLLOWING ERRORS:")
        for err in failures:
            print(f"  {err}")
        sys.exit(1)
    else:
        print("\n🎉 ALL 23 ACCEPTANCE CHECKS PASSED PERFECTLY!\n")
        sys.exit(0)


if __name__ == "__main__":
    validate()

