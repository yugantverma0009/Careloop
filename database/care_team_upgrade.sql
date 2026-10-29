-- database/care_team_upgrade.sql
-- CareLoop Care Team Portal Upgrade: Schema Additions & Upgrades (Brief Section 7)

USE careloop;

-- ─── 1. PATIENT IDENTITY (D-01) ─────────────────────────────────────────────
-- Add synthetic patient_code (e.g. CL-00001)
SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = 'careloop' AND TABLE_NAME = 'patients' AND COLUMN_NAME = 'patient_code');
SET @sql = IF(@col_exists = 0, 'ALTER TABLE patients ADD COLUMN patient_code VARCHAR(20) NULL', 'SELECT "patient_code column already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

UPDATE patients SET patient_code = CONCAT('CL-', LPAD(patient_id, 5, '0')) WHERE patient_code IS NULL;

-- Ensure UNIQUE index
SET @idx_exists = (SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = 'careloop' AND TABLE_NAME = 'patients' AND INDEX_NAME = 'uq_patient_code');
SET @sql = IF(@idx_exists = 0, 'ALTER TABLE patients MODIFY patient_code VARCHAR(20) NOT NULL, ADD UNIQUE KEY uq_patient_code (patient_code)', 'SELECT "uq_patient_code index already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;


-- ─── 2. FLAG OWNERSHIP AND RESOLUTION (D-03) ────────────────────────────────
SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = 'careloop' AND TABLE_NAME = 'flags' AND COLUMN_NAME = 'owner_staff_id');
SET @sql = IF(@col_exists = 0, 'ALTER TABLE flags
  ADD COLUMN owner_staff_id INT NULL,
  ADD COLUMN resolved_at DATETIME NULL,
  ADD COLUMN resolved_by_staff_id INT NULL,
  ADD COLUMN resolution_code ENUM(\'No_Action_Needed\',\'Patient_Contacted\',\'Appointment_Arranged\',
        \'Referred_To_Emergency\',\'Device_Or_Data_Issue\',\'Duplicate\',\'False_Alarm\') NULL,
  ADD COLUMN resolution_note VARCHAR(500) NULL,
  ADD CONSTRAINT fk_flag_owner    FOREIGN KEY (owner_staff_id) REFERENCES care_staff(staff_id),
  ADD CONSTRAINT fk_flag_resolver FOREIGN KEY (resolved_by_staff_id) REFERENCES care_staff(staff_id)',
  'SELECT "flags resolution columns already exist"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

CREATE TABLE IF NOT EXISTS flag_events (
  flag_event_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  flag_id       BIGINT NOT NULL,
  event_type    ENUM('Created','Acknowledged','Assigned','Note','Escalated','Resolved','Dismissed','Reopened') NOT NULL,
  staff_id      INT NULL,
  note          VARCHAR(500) NULL,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_flagevent_flag  FOREIGN KEY (flag_id)  REFERENCES flags(flag_id) ON DELETE CASCADE,
  CONSTRAINT fk_flagevent_staff FOREIGN KEY (staff_id) REFERENCES care_staff(staff_id),
  INDEX idx_flagevent_flag_time (flag_id, created_at)
);


-- ─── 3. TASKS EXTENSION (D-07) ──────────────────────────────────────────────
SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = 'careloop' AND TABLE_NAME = 'follow_up_tasks' AND COLUMN_NAME = 'due_at');
SET @sql = IF(@col_exists = 0, 'ALTER TABLE follow_up_tasks
  ADD COLUMN due_at DATETIME NULL,
  ADD COLUMN completed_at DATETIME NULL,
  ADD COLUMN outcome_code ENUM(\'Reached_And_Advised\',\'Appointment_Set\',\'No_Answer\',
        \'Escalated_To_Doctor\',\'No_Action_Needed\') NULL,
  ADD INDEX idx_task_due (status, due_at)',
  'SELECT "follow_up_tasks due_at already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;


-- ─── 4. SUMMARIES EXTENSION (D-08) ──────────────────────────────────────────
SET @col_exists = (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = 'careloop' AND TABLE_NAME = 'ai_summaries' AND COLUMN_NAME = 'status');
SET @sql = IF(@col_exists = 0, 'ALTER TABLE ai_summaries
  ADD COLUMN status ENUM(\'Draft\',\'Approved\',\'Rejected\') NOT NULL DEFAULT \'Draft\',
  ADD COLUMN edited_text TEXT NULL,
  ADD COLUMN reject_reason VARCHAR(255) NULL,
  ADD COLUMN source_snapshot JSON NULL',
  'SELECT "ai_summaries status already exists"');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;


-- ─── 5. CARE ASSIGNMENTS (D-12) ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS care_assignments (
  assignment_id   INT AUTO_INCREMENT PRIMARY KEY,
  patient_id      INT NOT NULL,
  staff_id        INT NOT NULL,
  assignment_role ENUM('Primary_Doctor','Nurse','Backup') NOT NULL,
  starts_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ends_at         DATETIME NULL,
  CONSTRAINT fk_assign_patient FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
  CONSTRAINT fk_assign_staff   FOREIGN KEY (staff_id)   REFERENCES care_staff(staff_id),
  CONSTRAINT chk_assign_dates  CHECK (ends_at IS NULL OR ends_at > starts_at),
  INDEX idx_assign_staff_active (staff_id, ends_at)
);


-- ─── 6. CONTACT LOG & NOTES (D-15, D-16) ────────────────────────────────────
CREATE TABLE IF NOT EXISTS contact_log (
  contact_id   BIGINT AUTO_INCREMENT PRIMARY KEY,
  patient_id   INT NOT NULL,
  staff_id     INT NOT NULL,
  flag_id      BIGINT NULL,
  task_id      BIGINT NULL,
  channel      ENUM('Phone','SMS','In_Person','Video') NOT NULL,
  outcome      ENUM('Reached','No_Answer','Left_Message','Wrong_Number','Declined') NOT NULL,
  summary      VARCHAR(500) NULL,
  contacted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_contact_patient FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
  CONSTRAINT fk_contact_staff   FOREIGN KEY (staff_id)   REFERENCES care_staff(staff_id),
  CONSTRAINT fk_contact_flag    FOREIGN KEY (flag_id)    REFERENCES flags(flag_id) ON DELETE SET NULL,
  CONSTRAINT fk_contact_task    FOREIGN KEY (task_id)    REFERENCES follow_up_tasks(followup_id) ON DELETE SET NULL,
  INDEX idx_contact_patient_time (patient_id, contacted_at)
);

CREATE TABLE IF NOT EXISTS clinician_notes (
  note_id        BIGINT AUTO_INCREMENT PRIMARY KEY,
  patient_id     INT NOT NULL,
  staff_id       INT NOT NULL,
  note_type      ENUM('Review','Call','Plan_Change','General') NOT NULL DEFAULT 'General',
  note_text      TEXT NOT NULL,
  amends_note_id BIGINT NULL,
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_note_patient FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
  CONSTRAINT fk_note_staff   FOREIGN KEY (staff_id)   REFERENCES care_staff(staff_id),
  CONSTRAINT fk_note_amends  FOREIGN KEY (amends_note_id) REFERENCES clinician_notes(note_id),
  INDEX idx_note_patient_time (patient_id, created_at)
);

CREATE TABLE IF NOT EXISTS alert_rules_history (
  history_id   BIGINT AUTO_INCREMENT PRIMARY KEY,
  rule_id      INT NOT NULL,
  changed_by_staff_id INT NOT NULL,
  change_reason VARCHAR(255) NOT NULL,
  old_values   JSON NOT NULL,
  new_values   JSON NOT NULL,
  changed_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_rulehist_rule  FOREIGN KEY (rule_id) REFERENCES alert_rules(rule_id) ON DELETE CASCADE,
  CONSTRAINT fk_rulehist_staff FOREIGN KEY (changed_by_staff_id) REFERENCES care_staff(staff_id)
);

CREATE TABLE IF NOT EXISTS risk_context (
  risk_context_id     INT AUTO_INCREMENT PRIMARY KEY,
  patient_id          INT NOT NULL,
  entered_by_staff_id INT NOT NULL,
  length_of_stay_days SMALLINT NOT NULL,
  acute_admission     BOOLEAN NOT NULL,
  charlson_index      TINYINT NOT NULL,
  ed_visits_6m        TINYINT NOT NULL,
  entered_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_riskctx_patient FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
  CONSTRAINT fk_riskctx_staff   FOREIGN KEY (entered_by_staff_id) REFERENCES care_staff(staff_id),
  CONSTRAINT chk_riskctx_values CHECK (length_of_stay_days >= 0 AND charlson_index >= 0 AND ed_visits_6m >= 0)
);


-- ─── 7. GROUPED WORKLIST VIEW (D-02) ────────────────────────────────────────
CREATE OR REPLACE VIEW v_worklist_by_patient AS
SELECT p.patient_id, p.patient_code, p.full_name,
       TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age_years,
       COUNT(*) AS open_flag_count,
       COUNT(DISTINCT CONCAT(f.source_type, ':', COALESCE(f.rule_id, 0))) AS distinct_reasons,
       MAX(CASE f.severity WHEN 'Urgent_Review' THEN 3 WHEN 'Review_Soon' THEN 2 ELSE 1 END) AS top_severity_rank,
       MAX(f.source_type = 'Emergency') AS has_emergency,
       SUM(f.status = 'Open') AS not_yet_seen,
       MIN(f.created_at) AS first_flag_at,
       MAX(f.created_at) AS latest_flag_at,
       MAX(f.owner_staff_id) AS owner_staff_id
FROM flags f
JOIN patients p ON p.patient_id = f.patient_id
WHERE f.status IN ('Open','Acknowledged')
GROUP BY p.patient_id, p.patient_code, p.full_name, p.date_of_birth;


-- ─── 8. STORED PROCEDURES ───────────────────────────────────────────────────
DROP PROCEDURE IF EXISTS sp_acknowledge_flag;
DELIMITER $$
CREATE PROCEDURE sp_acknowledge_flag(
    IN p_flag_id BIGINT,
    IN p_staff_id INT,
    IN p_note VARCHAR(255),
    IN p_create_task BOOLEAN
)
BEGIN
    DECLARE v_patient  INT DEFAULT NULL;
    DECLARE v_severity VARCHAR(20) DEFAULT NULL;
    DECLARE v_reason   VARCHAR(255) DEFAULT NULL;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;

    START TRANSACTION;
    SELECT patient_id, severity, reason INTO v_patient, v_severity, v_reason
    FROM flags WHERE flag_id = p_flag_id AND status = 'Open' FOR UPDATE;
    
    IF v_patient IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Flag not found or already acknowledged';
    END IF;

    UPDATE flags
    SET status = 'Acknowledged',
        owner_staff_id = p_staff_id,
        acknowledged_by_staff_id = p_staff_id,
        acknowledged_at = NOW()
    WHERE flag_id = p_flag_id;

    UPDATE escalations
    SET delivery_status = 'Acknowledged', responded_at = NOW()
    WHERE flag_id = p_flag_id AND delivery_status IN ('Queued','Sent');

    INSERT INTO flag_events (flag_id, event_type, staff_id, note)
    VALUES (p_flag_id, 'Acknowledged', p_staff_id, p_note);

    IF p_create_task THEN
        INSERT INTO follow_up_tasks (patient_id, flag_id, assigned_staff_id, reason, priority, due_at)
        VALUES (v_patient, p_flag_id, p_staff_id, v_reason,
                CASE v_severity WHEN 'Urgent_Review' THEN 'Urgent_Review' WHEN 'Review_Soon' THEN 'Review_Soon' ELSE 'Routine' END,
                NOW() + INTERVAL CASE v_severity WHEN 'Urgent_Review' THEN 2 WHEN 'Review_Soon' THEN 24 ELSE 72 END HOUR);
    END IF;

    INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
    VALUES ('Staff', CAST(p_staff_id AS CHAR), 'ACK_FLAG', 'flag', p_flag_id,
            JSON_OBJECT('note', p_note, 'task', p_create_task));
    COMMIT;
END$$

DROP PROCEDURE IF EXISTS sp_resolve_flag$$
CREATE PROCEDURE sp_resolve_flag(
    IN p_flag_id BIGINT,
    IN p_staff_id INT,
    IN p_code VARCHAR(30),
    IN p_note VARCHAR(500),
    IN p_dismiss BOOLEAN
)
BEGIN
    DECLARE v_status VARCHAR(20) DEFAULT NULL;
    DECLARE v_sev    VARCHAR(20) DEFAULT NULL;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;

    START TRANSACTION;
    SELECT status, severity INTO v_status, v_sev FROM flags WHERE flag_id = p_flag_id FOR UPDATE;
    IF v_status IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Flag not found';
    END IF;
    IF v_status IN ('Resolved','Dismissed') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Flag is already closed';
    END IF;
    IF v_sev = 'Urgent_Review' AND (p_note IS NULL OR CHAR_LENGTH(TRIM(p_note)) < 5) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A note of at least 5 characters is required to close an urgent flag';
    END IF;

    UPDATE flags
    SET status = IF(p_dismiss, 'Dismissed', 'Resolved'),
        resolved_at = NOW(),
        resolved_by_staff_id = p_staff_id,
        resolution_code = p_code,
        resolution_note = p_note
    WHERE flag_id = p_flag_id;

    INSERT INTO flag_events (flag_id, event_type, staff_id, note)
    VALUES (p_flag_id, IF(p_dismiss, 'Dismissed', 'Resolved'), p_staff_id, p_note);

    INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
    VALUES ('Staff', CAST(p_staff_id AS CHAR), IF(p_dismiss, 'DISMISS_FLAG', 'RESOLVE_FLAG'), 'flag', p_flag_id,
            JSON_OBJECT('code', p_code, 'note', p_note));
    COMMIT;
END$$

DROP PROCEDURE IF EXISTS sp_assign_flag$$
CREATE PROCEDURE sp_assign_flag(
    IN p_flag_id BIGINT,
    IN p_assigned_by_staff_id INT,
    IN p_target_staff_id INT,
    IN p_note VARCHAR(255)
)
BEGIN
    DECLARE v_status VARCHAR(20) DEFAULT NULL;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;

    START TRANSACTION;
    SELECT status INTO v_status FROM flags WHERE flag_id = p_flag_id FOR UPDATE;
    IF v_status IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Flag not found';
    END IF;

    UPDATE flags SET owner_staff_id = p_target_staff_id WHERE flag_id = p_flag_id;

    INSERT INTO flag_events (flag_id, event_type, staff_id, note)
    VALUES (p_flag_id, 'Assigned', p_target_staff_id, p_note);

    INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
    VALUES ('Staff', CAST(p_assigned_by_staff_id AS CHAR), 'ASSIGN_FLAG', 'flag', p_flag_id,
            JSON_OBJECT('target_staff_id', p_target_staff_id, 'note', p_note));
    COMMIT;
END$$

-- ─── 9. EMERGENCY DUPLICATE SUPPRESSION TRIGGER (Section 7.3) ───────────────
DROP TRIGGER IF EXISTS trg_symptom_rules_after_insert$$
CREATE TRIGGER trg_symptom_rules_after_insert
AFTER INSERT ON symptom_reports
FOR EACH ROW
BEGIN
    IF NEW.emergency_keyword_hit = TRUE THEN
        INSERT INTO flags (patient_id, rule_id, source_type, source_ref_id, reason, severity)
        SELECT NEW.patient_id, NULL, 'Emergency', NEW.symptom_report_id,
               'Patient report matched an emergency keyword. Emergency guidance was shown to the patient immediately. Clinician review required.',
               'Urgent_Review'
        FROM DUAL
        WHERE NOT EXISTS (SELECT 1 FROM flags f
                          WHERE f.patient_id = NEW.patient_id AND f.source_type = 'Emergency'
                            AND f.status IN ('Open','Acknowledged')
                            AND f.created_at >= NOW() - INTERVAL 60 MINUTE);
    END IF;

    IF NEW.pain_level IS NOT NULL THEN
        INSERT INTO flags (patient_id, rule_id, source_type, source_ref_id, reason, severity)
        SELECT NEW.patient_id, r.rule_id, 'Symptom', NEW.symptom_report_id,
               CONCAT('Pain score ', NEW.pain_level, ' reached the clinician-approved limit of ', r.threshold_value),
               r.severity
        FROM alert_rules r
        WHERE r.patient_id = NEW.patient_id AND r.rule_type = 'Pain_At_Least' AND r.is_active = TRUE
          AND NEW.pain_level >= r.threshold_value
          AND NOT EXISTS (SELECT 1 FROM flags f WHERE f.rule_id = r.rule_id AND f.status IN ('Open','Acknowledged'));
    END IF;
END$$
DELIMITER ;
