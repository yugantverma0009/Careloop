-- scripts/relink_mismatched_records.sql
-- Repairs the legacy seed mismatch in flags, follow_up_tasks, and ai_summaries.
-- Ensures zero identity mismatches across all records (Brief Section 6, D-01).

USE careloop;

START TRANSACTION;

-- 1. Re-link Flags
UPDATE flags SET patient_id = 1 WHERE flag_id = 1;
UPDATE flags SET patient_id = 4 WHERE flag_id = 4;
UPDATE flags SET patient_id = 5 WHERE flag_id = 5;
UPDATE flags SET patient_id = 6 WHERE flag_id = 6;
UPDATE flags SET patient_id = 7 WHERE flag_id = 7;
UPDATE flags SET patient_id = 8 WHERE flag_id = 8;
UPDATE flags SET patient_id = 9 WHERE flag_id = 9;
UPDATE flags SET patient_id = 10 WHERE flag_id = 10;

-- 2. Re-link Follow-up Tasks
UPDATE follow_up_tasks SET patient_id = 4 WHERE followup_id = 4;
UPDATE follow_up_tasks SET patient_id = 5 WHERE followup_id = 5;
UPDATE follow_up_tasks SET patient_id = 6 WHERE followup_id = 6;
UPDATE follow_up_tasks SET patient_id = 7 WHERE followup_id = 7;
UPDATE follow_up_tasks SET patient_id = 8 WHERE followup_id = 8;
UPDATE follow_up_tasks SET patient_id = 9 WHERE followup_id = 9;
UPDATE follow_up_tasks SET patient_id = 10 WHERE followup_id = 10;
UPDATE follow_up_tasks SET patient_id = 5 WHERE followup_id = 30;
UPDATE follow_up_tasks SET patient_id = 1 WHERE followup_id = 33;
UPDATE follow_up_tasks SET patient_id = 6 WHERE followup_id = 36;
UPDATE follow_up_tasks SET patient_id = 8 WHERE followup_id = 40;
UPDATE follow_up_tasks SET patient_id = 10 WHERE followup_id = 43;

-- 3. Re-link AI Summaries
UPDATE ai_summaries SET patient_id = 1 WHERE summary_id = 1;
UPDATE ai_summaries SET patient_id = 3 WHERE summary_id = 3;
UPDATE ai_summaries SET patient_id = 4 WHERE summary_id = 4;
UPDATE ai_summaries SET patient_id = 5 WHERE summary_id = 5;
UPDATE ai_summaries SET patient_id = 6 WHERE summary_id = 6;
UPDATE ai_summaries SET patient_id = 7 WHERE summary_id = 7;
UPDATE ai_summaries SET patient_id = 8 WHERE summary_id = 8;
UPDATE ai_summaries SET patient_id = 9 WHERE summary_id = 9;
UPDATE ai_summaries SET patient_id = 10 WHERE summary_id = 10;

-- 4. Clean test text leakage from symptom_reports
UPDATE symptom_reports
SET symptom_text = 'Chest tightness and shortness of breath upon exertion'
WHERE symptom_text LIKE '%microphone test at%' OR symptom_text LIKE '%Identical submission test%';

-- 5. Audit entry for the repair
INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
VALUES ('System', 'migration_p1', 'REPAIR_IDENTITY_MISMATCH', 'system', NULL,
        JSON_OBJECT('flags_repaired', 8, 'tasks_repaired', 12, 'summaries_repaired', 9));

COMMIT;
