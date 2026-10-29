-- database/patient_portal_upgrade.sql
-- CareLoop Patient Portal Upgrade: Phase 4 Schema Additions (Brief Section 9.2)

ALTER TABLE document_chunks
  ADD COLUMN section_title VARCHAR(120) NULL,
  ADD COLUMN section_type ENUM('medications','follow_up','warning_signs','activity','diet','wound_care','general')
      NOT NULL DEFAULT 'general',
  ADD COLUMN page_no SMALLINT NULL;

ALTER TABLE chat_messages
  ADD COLUMN answer_type ENUM('grounded','structured','refusal_dose','refusal_medical','emergency','not_found','unavailable') NULL,
  ADD COLUMN conversation_id VARCHAR(40) NULL,
  ADD COLUMN retrieval_debug JSON NULL;

CREATE TABLE IF NOT EXISTS chat_feedback (
  feedback_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  message_id  BIGINT NOT NULL,
  rating      TINYINT NOT NULL,
  comment     VARCHAR(255),
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_feedback_message (message_id),
  CONSTRAINT fk_feedback_message FOREIGN KEY (message_id) REFERENCES chat_messages(message_id) ON DELETE CASCADE,
  CONSTRAINT chk_feedback_rating CHECK (rating IN (-1, 1))
);
