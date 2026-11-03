"""
backend/app/migrate_phase1.py — Idempotent migration for Phase 1 CareLoop Agents.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.db import get_conn


def run_migration():
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 1. Check if ai_help_enabled exists in patients
            cur.execute("""
                SELECT COUNT(*) as cnt 
                FROM information_schema.columns 
                WHERE table_schema = DATABASE() 
                  AND table_name = 'patients' 
                  AND column_name = 'ai_help_enabled';
            """)
            if cur.fetchone()["cnt"] == 0:
                cur.execute("ALTER TABLE patients ADD COLUMN ai_help_enabled BOOLEAN NOT NULL DEFAULT TRUE;")
                print("✓ Added ai_help_enabled to patients")
            else:
                print("✓ ai_help_enabled already exists in patients")

            # 2. agent_system_state
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_system_state (
                    state_key VARCHAR(64) PRIMARY KEY,
                    state_val VARCHAR(255) NOT NULL,
                    updated_by_staff_id INT NULL,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)
            cur.execute("""
                INSERT INTO agent_system_state (state_key, state_val) VALUES ('pause_all_agents', 'false')
                ON DUPLICATE KEY UPDATE state_val = state_val;
            """)
            print("✓ agent_system_state table verified")

            # 3. agent_autonomy
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_autonomy (
                    action_type VARCHAR(64) PRIMARY KEY,
                    level ENUM('Suggest', 'Draft', 'Auto', 'Never') NOT NULL DEFAULT 'Suggest',
                    mode ENUM('Shadow', 'Live') NOT NULL DEFAULT 'Shadow',
                    set_by_staff_id INT NULL,
                    set_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)

            defaults = [
                ('dose_reminder', 'Auto', 'Live', 1),
                ('checkin_prompt', 'Auto', 'Live', 1),
                ('photo_request', 'Auto', 'Live', 1),
                ('papers_question_sourced', 'Auto', 'Live', 1),
                ('not_found_care_team_request', 'Auto', 'Live', 1),
                ('dose_change_care_team_request', 'Auto', 'Live', 1),
                ('duplicate_alert_merging', 'Auto', 'Live', 1),
                ('case_brief', 'Auto', 'Live', 1),
                ('next_step_suggestion', 'Suggest', 'Shadow', 1),
                ('call_script', 'Draft', 'Shadow', 1),
                ('call_note', 'Draft', 'Shadow', 1),
                ('post_call_patient_message', 'Draft', 'Shadow', 1),
                ('daily_summary', 'Draft', 'Shadow', 1),
                ('shift_handoff', 'Draft', 'Shadow', 1),
                ('recovery_plan', 'Draft', 'Shadow', 1),
                ('no_answer_retry_scheduling', 'Auto', 'Live', 1),
                ('approved_flag_auto_close', 'Draft', 'Shadow', 1)
            ]
            for action_type, level, mode, staff_id in defaults:
                cur.execute("""
                    INSERT INTO agent_autonomy (action_type, level, mode, set_by_staff_id)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE level = VALUES(level), mode = VALUES(mode);
                """, (action_type, level, mode, staff_id))
            print("✓ agent_autonomy table and default seeds verified")

            # 4. cases and case_flags
            cur.execute("""
                CREATE TABLE IF NOT EXISTS `cases` (
                    case_id VARCHAR(64) PRIMARY KEY,
                    patient_id INT NOT NULL,
                    primary_flag_id INT NULL,
                    status ENUM('Open', 'In_Progress', 'Resolved', 'Merged') NOT NULL DEFAULT 'Open',
                    merged_count INT NOT NULL DEFAULT 1,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_cases_patient (patient_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS case_flags (
                    case_id VARCHAR(64) NOT NULL,
                    flag_id INT NOT NULL,
                    added_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (case_id, flag_id),
                    INDEX idx_cf_flag (flag_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)
            print("✓ cases and case_flags tables verified")

            # 5. agent_runs
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_runs (
                    run_id VARCHAR(64) PRIMARY KEY,
                    agent_name VARCHAR(64) NOT NULL,
                    trigger_type VARCHAR(64) NOT NULL,
                    trigger_ref VARCHAR(128) NULL,
                    patient_id INT NULL,
                    case_id VARCHAR(64) NULL,
                    started_at DATETIME NOT NULL,
                    finished_at DATETIME NULL,
                    status ENUM('Done', 'Abstained', 'Failed', 'Blocked_By_Guard', 'Paused') NOT NULL DEFAULT 'Done',
                    autonomy_level ENUM('Suggest', 'Draft', 'Auto', 'Never') NOT NULL DEFAULT 'Suggest',
                    mode ENUM('Shadow', 'Live') NOT NULL DEFAULT 'Shadow',
                    plan JSON NULL,
                    result_type VARCHAR(64) NULL,
                    llm_calls INT NOT NULL DEFAULT 0,
                    tokens_in INT NOT NULL DEFAULT 0,
                    tokens_out INT NOT NULL DEFAULT 0,
                    latency_ms INT NOT NULL DEFAULT 0,
                    guard_reasons JSON NULL,
                    INDEX idx_agent_runs_patient (patient_id),
                    INDEX idx_agent_runs_created (started_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)
            print("✓ agent_runs table verified")

            # 6. agent_steps
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_steps (
                    step_id INT AUTO_INCREMENT PRIMARY KEY,
                    run_id VARCHAR(64) NOT NULL,
                    seq INT NOT NULL,
                    step_type ENUM('Gate', 'Plan', 'Retrieve', 'Tool', 'Grade', 'Draft', 'Verify', 'Guard', 'Deliver', 'Abstain') NOT NULL,
                    summary VARCHAR(255) NOT NULL,
                    ids JSON NULL,
                    ok BOOLEAN NOT NULL DEFAULT TRUE,
                    ms INT NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_steps_run (run_id),
                    CONSTRAINT fk_steps_run FOREIGN KEY (run_id) REFERENCES agent_runs (run_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)
            print("✓ agent_steps table verified")

            # 7. agent_drafts
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_drafts (
                    draft_id INT AUTO_INCREMENT PRIMARY KEY,
                    run_id VARCHAR(64) NULL,
                    patient_id INT NOT NULL,
                    draft_type ENUM('Case_Brief', 'Call_Script', 'Call_Note', 'Patient_Message', 'Summary', 'Handoff', 'Plan', 'Reply') NOT NULL,
                    body JSON NOT NULL,
                    sources JSON NULL,
                    status ENUM('Pending', 'Accepted', 'Edited', 'Rejected', 'Auto_Sent', 'Expired') NOT NULL DEFAULT 'Pending',
                    reviewed_by_staff_id INT NULL,
                    reviewed_at DATETIME NULL,
                    edit_chars INT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_drafts_patient (patient_id),
                    INDEX idx_drafts_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)
            print("✓ agent_drafts table verified")

            # 8. shadow_decisions
            cur.execute("""
                CREATE TABLE IF NOT EXISTS shadow_decisions (
                    shadow_id INT AUTO_INCREMENT PRIMARY KEY,
                    run_id VARCHAR(64) NULL,
                    action_type VARCHAR(64) NOT NULL,
                    agent_decision JSON NOT NULL,
                    human_decision JSON NULL,
                    agreed BOOLEAN NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_shadow_action (action_type)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)
            print("✓ shadow_decisions table verified")

        conn.commit()
    print("✅ All Phase 1 database schema additions successfully migrated.")


if __name__ == "__main__":
    run_migration()
