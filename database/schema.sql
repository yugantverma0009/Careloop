-- database/schema.sql — CareLoop Consolidated Database Schema
-- Consolidates base schema + care team upgrade + patient portal upgrade.
-- Contains 32 base tables, 8 views, 16 stored procedures, and 3 triggers.

CREATE DATABASE IF NOT EXISTS careloop CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE careloop;

-- Ensure API user exists with necessary least-privilege permissions
CREATE USER IF NOT EXISTS 'careloop_api'@'localhost' IDENTIFIED BY 'careloop_dev_pass';
GRANT SELECT, INSERT, UPDATE, EXECUTE ON careloop.* TO 'careloop_api'@'localhost';
FLUSH PRIVILEGES;

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `ai_summaries`
--

DROP TABLE IF EXISTS `ai_summaries`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ai_summaries` (
  `summary_id` bigint NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `period_start` datetime NOT NULL,
  `period_end` datetime NOT NULL,
  `summary_text` text NOT NULL,
  `model_name` varchar(60) DEFAULT NULL,
  `generated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `reviewed_by_staff_id` int DEFAULT NULL,
  `reviewed_at` datetime DEFAULT NULL,
  `status` enum('Draft','Approved','Rejected') NOT NULL DEFAULT 'Draft',
  `edited_text` text,
  `reject_reason` varchar(255) DEFAULT NULL,
  `source_snapshot` json DEFAULT NULL,
  PRIMARY KEY (`summary_id`),
  KEY `fk_summary_patient` (`patient_id`),
  KEY `fk_summary_staff` (`reviewed_by_staff_id`),
  CONSTRAINT `fk_summary_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_summary_staff` FOREIGN KEY (`reviewed_by_staff_id`) REFERENCES `care_staff` (`staff_id`),
  CONSTRAINT `chk_summary_period` CHECK ((`period_end` > `period_start`))
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `alert_rules`
--

DROP TABLE IF EXISTS `alert_rules`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `alert_rules` (
  `rule_id` int NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `rule_type` enum('Reading_Above','Reading_Below','Pain_At_Least','Missed_Doses','No_Data_Hours','Possible_Fall','Missed_Checkins') NOT NULL,
  `measurement_type` enum('Heart_Rate','SpO2') DEFAULT NULL,
  `threshold_value` decimal(7,2) NOT NULL,
  `window_hours` smallint DEFAULT NULL,
  `severity` enum('Review_Soon','Urgent_Review') NOT NULL,
  `approved_by_staff_id` int NOT NULL,
  `approved_at` datetime NOT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`rule_id`),
  KEY `fk_rule_patient` (`patient_id`),
  KEY `fk_rule_staff` (`approved_by_staff_id`),
  CONSTRAINT `fk_rule_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_rule_staff` FOREIGN KEY (`approved_by_staff_id`) REFERENCES `care_staff` (`staff_id`),
  CONSTRAINT `chk_rule_measure` CHECK (((`rule_type` not in (_utf8mb4'Reading_Above',_utf8mb4'Reading_Below')) or (`measurement_type` is not null))),
  CONSTRAINT `chk_rule_window` CHECK (((`rule_type` <> _utf8mb4'Missed_Doses') or (`window_hours` is not null)))
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `alert_rules_history`
--

DROP TABLE IF EXISTS `alert_rules_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `alert_rules_history` (
  `history_id` bigint NOT NULL AUTO_INCREMENT,
  `rule_id` int NOT NULL,
  `changed_by_staff_id` int NOT NULL,
  `change_reason` varchar(255) NOT NULL,
  `old_values` json NOT NULL,
  `new_values` json NOT NULL,
  `changed_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`history_id`),
  KEY `fk_rulehist_rule` (`rule_id`),
  KEY `fk_rulehist_staff` (`changed_by_staff_id`),
  CONSTRAINT `fk_rulehist_rule` FOREIGN KEY (`rule_id`) REFERENCES `alert_rules` (`rule_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_rulehist_staff` FOREIGN KEY (`changed_by_staff_id`) REFERENCES `care_staff` (`staff_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `appointments`
--

DROP TABLE IF EXISTS `appointments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `appointments` (
  `appointment_id` int NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `staff_id` int NOT NULL,
  `appointment_date` datetime NOT NULL,
  `appointment_type` varchar(80) NOT NULL DEFAULT 'Post-discharge follow-up',
  `status` enum('Scheduled','Completed','Cancelled','No_Show') NOT NULL DEFAULT 'Scheduled',
  `notes` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`appointment_id`),
  KEY `fk_appt_patient` (`patient_id`),
  KEY `fk_appt_staff` (`staff_id`),
  KEY `idx_appt_date_status` (`appointment_date`,`status`),
  CONSTRAINT `fk_appt_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_appt_staff` FOREIGN KEY (`staff_id`) REFERENCES `care_staff` (`staff_id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `audit_log`
--

DROP TABLE IF EXISTS `audit_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `audit_log` (
  `log_id` bigint NOT NULL AUTO_INCREMENT,
  `actor_type` enum('Patient','Caregiver','Staff','Agent','Device','System') NOT NULL,
  `actor_id` varchar(60) DEFAULT NULL,
  `action` varchar(80) NOT NULL,
  `entity_type` varchar(40) DEFAULT NULL,
  `entity_id` bigint DEFAULT NULL,
  `details` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`log_id`),
  KEY `idx_audit_entity` (`entity_type`,`entity_id`),
  KEY `idx_audit_time` (`created_at`)
) ENGINE=InnoDB AUTO_INCREMENT=50 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `care_assignments`
--

DROP TABLE IF EXISTS `care_assignments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `care_assignments` (
  `assignment_id` int NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `staff_id` int NOT NULL,
  `assignment_role` enum('Primary_Doctor','Nurse','Backup') NOT NULL,
  `starts_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `ends_at` datetime DEFAULT NULL,
  PRIMARY KEY (`assignment_id`),
  KEY `fk_assign_patient` (`patient_id`),
  KEY `idx_assign_staff_active` (`staff_id`,`ends_at`),
  CONSTRAINT `fk_assign_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_assign_staff` FOREIGN KEY (`staff_id`) REFERENCES `care_staff` (`staff_id`),
  CONSTRAINT `chk_assign_dates` CHECK (((`ends_at` is null) or (`ends_at` > `starts_at`)))
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `care_staff`
--

DROP TABLE IF EXISTS `care_staff`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `care_staff` (
  `staff_id` int NOT NULL AUTO_INCREMENT,
  `full_name` varchar(100) NOT NULL,
  `staff_role` enum('Doctor','Nurse') NOT NULL,
  `specialization` varchar(100) DEFAULT NULL,
  `phone` varchar(20) DEFAULT NULL,
  `email` varchar(120) NOT NULL,
  PRIMARY KEY (`staff_id`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `caregivers`
--

DROP TABLE IF EXISTS `caregivers`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `caregivers` (
  `caregiver_id` int NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `full_name` varchar(100) NOT NULL,
  `phone` varchar(20) NOT NULL,
  `relationship` varchar(40) DEFAULT NULL,
  `consent_granted` tinyint(1) NOT NULL DEFAULT '0',
  `is_primary` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`caregiver_id`),
  KEY `fk_caregiver_patient` (`patient_id`),
  CONSTRAINT `fk_caregiver_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `chat_feedback`
--

DROP TABLE IF EXISTS `chat_feedback`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chat_feedback` (
  `feedback_id` bigint NOT NULL AUTO_INCREMENT,
  `message_id` bigint NOT NULL,
  `rating` tinyint NOT NULL,
  `comment` varchar(255) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`feedback_id`),
  UNIQUE KEY `uk_feedback_message` (`message_id`),
  CONSTRAINT `fk_feedback_message` FOREIGN KEY (`message_id`) REFERENCES `chat_messages` (`message_id`) ON DELETE CASCADE,
  CONSTRAINT `chk_feedback_rating` CHECK ((`rating` in (-(1),1)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `chat_message_sources`
--

DROP TABLE IF EXISTS `chat_message_sources`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chat_message_sources` (
  `message_id` bigint NOT NULL,
  `chunk_id` bigint NOT NULL,
  PRIMARY KEY (`message_id`,`chunk_id`),
  KEY `fk_src_chunk` (`chunk_id`),
  CONSTRAINT `fk_src_chunk` FOREIGN KEY (`chunk_id`) REFERENCES `document_chunks` (`chunk_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_src_message` FOREIGN KEY (`message_id`) REFERENCES `chat_messages` (`message_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `chat_messages`
--

DROP TABLE IF EXISTS `chat_messages`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chat_messages` (
  `message_id` bigint NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `sender` enum('Patient','AI_Nurse') NOT NULL,
  `message_text` text NOT NULL,
  `is_grounded` tinyint(1) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `answer_type` enum('grounded','structured','refusal_dose','refusal_medical','emergency','not_found','unavailable') DEFAULT NULL,
  `conversation_id` varchar(40) DEFAULT NULL,
  `retrieval_debug` json DEFAULT NULL,
  PRIMARY KEY (`message_id`),
  KEY `idx_chat_patient_time` (`patient_id`,`created_at`),
  CONSTRAINT `fk_chat_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `clinician_notes`
--

DROP TABLE IF EXISTS `clinician_notes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `clinician_notes` (
  `note_id` bigint NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `staff_id` int NOT NULL,
  `note_type` enum('Review','Call','Plan_Change','General') NOT NULL DEFAULT 'General',
  `note_text` text NOT NULL,
  `amends_note_id` bigint DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`note_id`),
  KEY `fk_note_staff` (`staff_id`),
  KEY `fk_note_amends` (`amends_note_id`),
  KEY `idx_note_patient_time` (`patient_id`,`created_at`),
  CONSTRAINT `fk_note_amends` FOREIGN KEY (`amends_note_id`) REFERENCES `clinician_notes` (`note_id`),
  CONSTRAINT `fk_note_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_note_staff` FOREIGN KEY (`staff_id`) REFERENCES `care_staff` (`staff_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `contact_log`
--

DROP TABLE IF EXISTS `contact_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `contact_log` (
  `contact_id` bigint NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `staff_id` int NOT NULL,
  `flag_id` bigint DEFAULT NULL,
  `task_id` bigint DEFAULT NULL,
  `channel` enum('Phone','SMS','In_Person','Video') NOT NULL,
  `outcome` enum('Reached','No_Answer','Left_Message','Wrong_Number','Declined') NOT NULL,
  `summary` varchar(500) DEFAULT NULL,
  `contacted_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`contact_id`),
  KEY `fk_contact_staff` (`staff_id`),
  KEY `fk_contact_flag` (`flag_id`),
  KEY `fk_contact_task` (`task_id`),
  KEY `idx_contact_patient_time` (`patient_id`,`contacted_at`),
  CONSTRAINT `fk_contact_flag` FOREIGN KEY (`flag_id`) REFERENCES `flags` (`flag_id`) ON DELETE SET NULL,
  CONSTRAINT `fk_contact_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_contact_staff` FOREIGN KEY (`staff_id`) REFERENCES `care_staff` (`staff_id`),
  CONSTRAINT `fk_contact_task` FOREIGN KEY (`task_id`) REFERENCES `follow_up_tasks` (`followup_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `devices`
--

DROP TABLE IF EXISTS `devices`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `devices` (
  `device_id` varchar(60) NOT NULL,
  `patient_id` int NOT NULL,
  `device_type` enum('ESP32_Watch','Simulator') NOT NULL,
  `registered_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `last_seen_at` datetime DEFAULT NULL,
  `expected_interval_minutes` int NOT NULL DEFAULT '60',
  `api_key_hash` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`device_id`),
  UNIQUE KEY `uq_device_patient` (`device_id`,`patient_id`),
  KEY `fk_device_patient` (`patient_id`),
  CONSTRAINT `fk_device_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `discharge_documents`
--

DROP TABLE IF EXISTS `discharge_documents`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `discharge_documents` (
  `document_id` int NOT NULL AUTO_INCREMENT,
  `discharge_id` int NOT NULL,
  `file_name` varchar(200) NOT NULL,
  `uploaded_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `indexing_status` enum('Pending','Indexed','Failed') NOT NULL DEFAULT 'Pending',
  `vector_collection` varchar(100) DEFAULT NULL,
  PRIMARY KEY (`document_id`),
  KEY `fk_document_discharge` (`discharge_id`),
  CONSTRAINT `fk_document_discharge` FOREIGN KEY (`discharge_id`) REFERENCES `discharge_records` (`discharge_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `discharge_records`
--

DROP TABLE IF EXISTS `discharge_records`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `discharge_records` (
  `discharge_id` int NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `attending_staff_id` int NOT NULL,
  `discharge_date` date NOT NULL,
  `condition_summary` varchar(255) DEFAULT NULL,
  `instructions` text,
  `follow_up_due` date DEFAULT NULL,
  PRIMARY KEY (`discharge_id`),
  KEY `fk_discharge_patient` (`patient_id`),
  KEY `fk_discharge_staff` (`attending_staff_id`),
  CONSTRAINT `fk_discharge_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_discharge_staff` FOREIGN KEY (`attending_staff_id`) REFERENCES `care_staff` (`staff_id`),
  CONSTRAINT `chk_followup_after_discharge` CHECK (((`follow_up_due` is null) or (`follow_up_due` >= `discharge_date`)))
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `document_chunks`
--

DROP TABLE IF EXISTS `document_chunks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `document_chunks` (
  `chunk_id` bigint NOT NULL AUTO_INCREMENT,
  `document_id` int NOT NULL,
  `chunk_index` int NOT NULL,
  `chunk_text` text NOT NULL,
  `vector_id` varchar(100) DEFAULT NULL,
  `section_title` varchar(120) DEFAULT NULL,
  `section_type` enum('medications','follow_up','warning_signs','activity','diet','wound_care','general') NOT NULL DEFAULT 'general',
  `page_no` smallint DEFAULT NULL,
  PRIMARY KEY (`chunk_id`),
  UNIQUE KEY `uq_document_chunk` (`document_id`,`chunk_index`),
  CONSTRAINT `fk_chunk_document` FOREIGN KEY (`document_id`) REFERENCES `discharge_documents` (`document_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `escalations`
--

DROP TABLE IF EXISTS `escalations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `escalations` (
  `escalation_id` bigint NOT NULL AUTO_INCREMENT,
  `flag_id` bigint NOT NULL,
  `step_no` tinyint NOT NULL,
  `step_type` enum('Patient_Prompt','Caregiver_SMS','Nurse_Alert','Doctor_Alert') NOT NULL,
  `channel` enum('App','SMS','Dashboard') NOT NULL,
  `sent_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `delivery_status` enum('Queued','Sent','Failed','Acknowledged','Skipped_No_Consent') NOT NULL DEFAULT 'Queued',
  `responded_at` datetime DEFAULT NULL,
  `notes` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`escalation_id`),
  UNIQUE KEY `uq_flag_step` (`flag_id`,`step_no`),
  CONSTRAINT `fk_escalation_flag` FOREIGN KEY (`flag_id`) REFERENCES `flags` (`flag_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `flag_events`
--

DROP TABLE IF EXISTS `flag_events`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `flag_events` (
  `flag_event_id` bigint NOT NULL AUTO_INCREMENT,
  `flag_id` bigint NOT NULL,
  `event_type` enum('Created','Acknowledged','Assigned','Note','Escalated','Resolved','Dismissed','Reopened') NOT NULL,
  `staff_id` int DEFAULT NULL,
  `note` varchar(500) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`flag_event_id`),
  KEY `fk_flagevent_staff` (`staff_id`),
  KEY `idx_flagevent_flag_time` (`flag_id`,`created_at`),
  CONSTRAINT `fk_flagevent_flag` FOREIGN KEY (`flag_id`) REFERENCES `flags` (`flag_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_flagevent_staff` FOREIGN KEY (`staff_id`) REFERENCES `care_staff` (`staff_id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `flags`
--

DROP TABLE IF EXISTS `flags`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `flags` (
  `flag_id` bigint NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `rule_id` int DEFAULT NULL,
  `source_type` enum('Sensor','Symptom','Medication','Device','Emergency','Photo','Fall','Checkin','SOS') NOT NULL,
  `source_ref_id` bigint DEFAULT NULL,
  `reason` varchar(255) NOT NULL,
  `severity` enum('Info','Review_Soon','Urgent_Review') NOT NULL DEFAULT 'Review_Soon',
  `status` enum('Open','Acknowledged','Resolved','Dismissed') NOT NULL DEFAULT 'Open',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `acknowledged_by_staff_id` int DEFAULT NULL,
  `acknowledged_at` datetime DEFAULT NULL,
  `owner_staff_id` int DEFAULT NULL,
  `resolved_at` datetime DEFAULT NULL,
  `resolved_by_staff_id` int DEFAULT NULL,
  `resolution_code` enum('No_Action_Needed','Patient_Contacted','Appointment_Arranged','Referred_To_Emergency','Device_Or_Data_Issue','Duplicate','False_Alarm') DEFAULT NULL,
  `resolution_note` varchar(500) DEFAULT NULL,
  PRIMARY KEY (`flag_id`),
  KEY `fk_flag_rule` (`rule_id`),
  KEY `fk_flag_staff` (`acknowledged_by_staff_id`),
  KEY `idx_flag_status_sev` (`status`,`severity`,`created_at`),
  KEY `idx_flag_patient_time` (`patient_id`,`created_at`),
  KEY `fk_flag_owner` (`owner_staff_id`),
  KEY `fk_flag_resolver` (`resolved_by_staff_id`),
  CONSTRAINT `fk_flag_owner` FOREIGN KEY (`owner_staff_id`) REFERENCES `care_staff` (`staff_id`),
  CONSTRAINT `fk_flag_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_flag_resolver` FOREIGN KEY (`resolved_by_staff_id`) REFERENCES `care_staff` (`staff_id`),
  CONSTRAINT `fk_flag_rule` FOREIGN KEY (`rule_id`) REFERENCES `alert_rules` (`rule_id`) ON DELETE SET NULL,
  CONSTRAINT `fk_flag_staff` FOREIGN KEY (`acknowledged_by_staff_id`) REFERENCES `care_staff` (`staff_id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `follow_up_tasks`
--

DROP TABLE IF EXISTS `follow_up_tasks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `follow_up_tasks` (
  `followup_id` bigint NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `flag_id` bigint DEFAULT NULL,
  `assigned_staff_id` int NOT NULL,
  `reason` varchar(255) NOT NULL,
  `priority` enum('Routine','Review_Soon','Urgent_Review') NOT NULL DEFAULT 'Routine',
  `status` enum('Pending','Contacted','Appointment_Set','Resolved') NOT NULL DEFAULT 'Pending',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `contacted_at` datetime DEFAULT NULL,
  `outcome_notes` text,
  `due_at` datetime DEFAULT NULL,
  `completed_at` datetime DEFAULT NULL,
  `outcome_code` enum('Reached_And_Advised','Appointment_Set','No_Answer','Escalated_To_Doctor','No_Action_Needed') DEFAULT NULL,
  PRIMARY KEY (`followup_id`),
  KEY `fk_task_patient` (`patient_id`),
  KEY `fk_task_flag` (`flag_id`),
  KEY `fk_task_staff` (`assigned_staff_id`),
  KEY `idx_task_status_priority` (`status`,`priority`,`created_at`),
  KEY `idx_task_due` (`status`,`due_at`),
  CONSTRAINT `fk_task_flag` FOREIGN KEY (`flag_id`) REFERENCES `flags` (`flag_id`) ON DELETE SET NULL,
  CONSTRAINT `fk_task_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_task_staff` FOREIGN KEY (`assigned_staff_id`) REFERENCES `care_staff` (`staff_id`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `scheduled_actions`
--

DROP TABLE IF EXISTS `scheduled_actions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `scheduled_actions` (
  `action_id` bigint NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `action_type` enum('Dose_Reminder','Checkin_Prompt','Photo_Request','Fall_Prompt','Plan_Prompt','Welcome_Call_Task','SOS_Repeat') NOT NULL,
  `channel` enum('App','SMS','Voice','Task') NOT NULL DEFAULT 'App',
  `run_at` datetime NOT NULL,
  `status` enum('Scheduled','Done','Skipped','Cancelled','Failed') NOT NULL DEFAULT 'Scheduled',
  `reason` varchar(255) NOT NULL,
  `payload` json DEFAULT NULL,
  `attempts` tinyint NOT NULL DEFAULT '0',
  `done_at` datetime DEFAULT NULL,
  `result` varchar(255) DEFAULT NULL,
  `dedupe_key` varchar(120) NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`action_id`),
  UNIQUE KEY `uq_sched_dedupe` (`dedupe_key`),
  KEY `idx_sched_due` (`status`,`run_at`),
  KEY `fk_sched_patient` (`patient_id`),
  CONSTRAINT `fk_sched_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `agent_proposals`
--

DROP TABLE IF EXISTS `agent_proposals`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `agent_proposals` (
  `proposal_id` bigint NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `agent_name` varchar(40) NOT NULL DEFAULT 'Rounds',
  `proposal_type` enum('Suggest_Call','Suggest_Photo','Suggest_Plan_Review') NOT NULL,
  `reason` varchar(255) NOT NULL,
  `evidence` json DEFAULT NULL,
  `status` enum('Pending','Accepted','Dismissed') NOT NULL DEFAULT 'Pending',
  `decided_by_staff_id` int DEFAULT NULL,
  `decided_at` datetime DEFAULT NULL,
  `dismiss_reason` varchar(255) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`proposal_id`),
  KEY `idx_prop_status` (`status`,`created_at`),
  KEY `fk_prop_patient` (`patient_id`),
  KEY `fk_prop_staff` (`decided_by_staff_id`),
  CONSTRAINT `fk_prop_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_prop_staff` FOREIGN KEY (`decided_by_staff_id`) REFERENCES `care_staff` (`staff_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `checkin_templates`
--

DROP TABLE IF EXISTS `checkin_templates`;
CREATE TABLE `checkin_templates` (
  `template_id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(80) NOT NULL,
  `version` smallint NOT NULL DEFAULT '1',
  `status` enum('Draft','Approved','Archived') NOT NULL DEFAULT 'Draft',
  `approved_by_staff_id` int DEFAULT NULL,
  `approved_at` datetime DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL DEFAULT '0',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`template_id`),
  KEY `fk_template_staff` (`approved_by_staff_id`),
  CONSTRAINT `fk_template_staff` FOREIGN KEY (`approved_by_staff_id`) REFERENCES `care_staff` (`staff_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `checkin_questions`
--

DROP TABLE IF EXISTS `checkin_questions`;
CREATE TABLE `checkin_questions` (
  `question_id` int NOT NULL AUTO_INCREMENT,
  `template_id` int NOT NULL,
  `step_order` smallint NOT NULL,
  `question_key` varchar(40) NOT NULL,
  `text_en` varchar(255) NOT NULL,
  `text_hi` varchar(255) NOT NULL,
  `response_type` enum('Scale_0_10','Yes_No','Choice','Text') NOT NULL,
  `choices` json DEFAULT NULL,
  `is_emergency_trigger` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`question_id`),
  KEY `fk_question_template` (`template_id`),
  CONSTRAINT `fk_question_template` FOREIGN KEY (`template_id`) REFERENCES `checkin_templates` (`template_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `checkin_sessions`
--

DROP TABLE IF EXISTS `checkin_sessions`;
CREATE TABLE `checkin_sessions` (
  `session_id` bigint NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `template_id` int NOT NULL,
  `channel` enum('App_Guided','SMS','Voice') NOT NULL DEFAULT 'App_Guided',
  `status` enum('In_Progress','Completed','Abandoned','Missed') NOT NULL DEFAULT 'In_Progress',
  `current_step` smallint NOT NULL DEFAULT '1',
  `started_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `completed_at` datetime DEFAULT NULL,
  `symptom_report_id` bigint DEFAULT NULL,
  PRIMARY KEY (`session_id`),
  KEY `fk_checkin_patient` (`patient_id`),
  KEY `fk_checkin_template` (`template_id`),
  KEY `fk_checkin_report` (`symptom_report_id`),
  CONSTRAINT `fk_checkin_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_checkin_report` FOREIGN KEY (`symptom_report_id`) REFERENCES `symptom_reports` (`symptom_report_id`) ON DELETE SET NULL,
  CONSTRAINT `fk_checkin_template` FOREIGN KEY (`template_id`) REFERENCES `checkin_templates` (`template_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `checkin_answers`
--

DROP TABLE IF EXISTS `checkin_answers`;
CREATE TABLE `checkin_answers` (
  `answer_id` bigint NOT NULL AUTO_INCREMENT,
  `session_id` bigint NOT NULL,
  `question_id` int NOT NULL,
  `answer_value` varchar(255) NOT NULL,
  `raw_input` varchar(500) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`answer_id`),
  KEY `fk_answer_session` (`session_id`),
  KEY `fk_answer_question` (`question_id`),
  CONSTRAINT `fk_answer_question` FOREIGN KEY (`question_id`) REFERENCES `checkin_questions` (`question_id`),
  CONSTRAINT `fk_answer_session` FOREIGN KEY (`session_id`) REFERENCES `checkin_sessions` (`session_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Table structure for table `sms_messages`
--

DROP TABLE IF EXISTS `sms_messages`;
CREATE TABLE `sms_messages` (
  `sms_id` bigint NOT NULL AUTO_INCREMENT,
  `direction` enum('Outbound','Inbound') NOT NULL,
  `patient_id` int DEFAULT NULL,
  `caregiver_id` int DEFAULT NULL,
  `phone` varchar(20) NOT NULL,
  `body` varchar(480) NOT NULL,
  `template_key` varchar(60) DEFAULT NULL,
  `related_type` varchar(30) DEFAULT NULL,
  `related_id` bigint DEFAULT NULL,
  `status` enum('Logged','Sent','Delivered','Failed','Received') NOT NULL,
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`sms_id`),
  KEY `idx_sms_patient_time` (`patient_id`,`created_at`),
  KEY `fk_sms_caregiver` (`caregiver_id`),
  CONSTRAINT `fk_sms_caregiver` FOREIGN KEY (`caregiver_id`) REFERENCES `caregivers` (`caregiver_id`) ON DELETE SET NULL,
  CONSTRAINT `fk_sms_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `wound_photos`
--

DROP TABLE IF EXISTS `wound_photos`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `wound_photos` (
  `photo_id` bigint NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `session_id` bigint DEFAULT NULL,
  `taken_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `file_path` varchar(255) NOT NULL,
  `thumb_path` varchar(255) DEFAULT NULL,
  `sha256` char(64) NOT NULL,
  `quality_status` enum('Usable','Too_Dark','Blurry','Too_Small','Used_Anyway') NOT NULL,
  `quality_details` json DEFAULT NULL,
  `patient_note` varchar(255) DEFAULT NULL,
  `review_status` enum('Pending','Reviewed','Needs_Doctor') NOT NULL DEFAULT 'Pending',
  `finding` enum('No_Concern_Seen','Concern_Noted','Retake_Needed') DEFAULT NULL,
  `review_note` varchar(500) DEFAULT NULL,
  `reviewed_by_staff_id` int DEFAULT NULL,
  `reviewed_at` datetime DEFAULT NULL,
  `flag_id` bigint DEFAULT NULL,
  PRIMARY KEY (`photo_id`),
  KEY `fk_photo_patient` (`patient_id`),
  KEY `fk_photo_staff` (`reviewed_by_staff_id`),
  KEY `fk_photo_flag` (`flag_id`),
  KEY `idx_photo_review` (`review_status`,`taken_at`),
  CONSTRAINT `fk_photo_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_photo_staff` FOREIGN KEY (`reviewed_by_staff_id`) REFERENCES `care_staff` (`staff_id`) ON DELETE SET NULL,
  CONSTRAINT `fk_photo_flag` FOREIGN KEY (`flag_id`) REFERENCES `flags` (`flag_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `medication_logs`
--

DROP TABLE IF EXISTS `medication_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `medication_logs` (
  `medication_log_id` bigint NOT NULL AUTO_INCREMENT,
  `prescription_id` int NOT NULL,
  `scheduled_for` datetime NOT NULL,
  `status` enum('Taken_Confirmed','Missed','Skipped','Unconfirmed') NOT NULL DEFAULT 'Unconfirmed',
  `reminder_sent_at` datetime DEFAULT NULL,
  `recorded_at` datetime DEFAULT NULL,
  `recorded_by` enum('Patient','Caregiver','System') DEFAULT NULL,
  `patient_note` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`medication_log_id`),
  UNIQUE KEY `uq_rx_schedule` (`prescription_id`,`scheduled_for`),
  KEY `idx_medlog_status_time` (`status`,`scheduled_for`),
  CONSTRAINT `fk_medlog_rx` FOREIGN KEY (`prescription_id`) REFERENCES `prescriptions` (`prescription_id`) ON DELETE CASCADE,
  CONSTRAINT `chk_confirmed_has_time` CHECK (((`status` not in (_utf8mb4'Taken_Confirmed',_utf8mb4'Skipped')) or (`recorded_at` is not null)))
) ENGINE=InnoDB AUTO_INCREMENT=71 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `medicines`
--

DROP TABLE IF EXISTS `medicines`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `medicines` (
  `medicine_id` int NOT NULL AUTO_INCREMENT,
  `medicine_name` varchar(120) NOT NULL,
  `general_notes` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`medicine_id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `patients`
--

DROP TABLE IF EXISTS `patients`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `patients` (
  `patient_id` int NOT NULL AUTO_INCREMENT,
  `full_name` varchar(100) NOT NULL,
  `phone` varchar(20) DEFAULT NULL,
  `date_of_birth` date DEFAULT NULL,
  `preferred_language` enum('en','hi') NOT NULL DEFAULT 'en',
  `consent_status` enum('Granted','Pending','Withdrawn') NOT NULL DEFAULT 'Pending',
  `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `patient_code` varchar(20) NOT NULL,
  `rounds_paused_until` datetime DEFAULT NULL,
  `rounds_pause_reason` varchar(120) DEFAULT NULL,
  `sms_opt_out` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`patient_id`),
  UNIQUE KEY `uq_patient_code` (`patient_code`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `prescription_times`
--

DROP TABLE IF EXISTS `prescription_times`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `prescription_times` (
  `prescription_time_id` int NOT NULL AUTO_INCREMENT,
  `prescription_id` int NOT NULL,
  `dose_time` time NOT NULL,
  PRIMARY KEY (`prescription_time_id`),
  UNIQUE KEY `uq_rx_time` (`prescription_id`,`dose_time`),
  CONSTRAINT `fk_rxtime_rx` FOREIGN KEY (`prescription_id`) REFERENCES `prescriptions` (`prescription_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `prescriptions`
--

DROP TABLE IF EXISTS `prescriptions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `prescriptions` (
  `prescription_id` int NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `medicine_id` int NOT NULL,
  `dose_instructions` varchar(255) NOT NULL,
  `start_date` date NOT NULL,
  `end_date` date DEFAULT NULL,
  `active_status` tinyint(1) NOT NULL DEFAULT '1',
  `prescribed_by_staff_id` int NOT NULL,
  PRIMARY KEY (`prescription_id`),
  KEY `fk_rx_patient` (`patient_id`),
  KEY `fk_rx_medicine` (`medicine_id`),
  KEY `fk_rx_staff` (`prescribed_by_staff_id`),
  CONSTRAINT `fk_rx_medicine` FOREIGN KEY (`medicine_id`) REFERENCES `medicines` (`medicine_id`),
  CONSTRAINT `fk_rx_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_rx_staff` FOREIGN KEY (`prescribed_by_staff_id`) REFERENCES `care_staff` (`staff_id`),
  CONSTRAINT `chk_rx_dates` CHECK (((`end_date` is null) or (`end_date` >= `start_date`)))
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `risk_context`
--

DROP TABLE IF EXISTS `risk_context`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `risk_context` (
  `risk_context_id` int NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `entered_by_staff_id` int NOT NULL,
  `length_of_stay_days` smallint NOT NULL,
  `acute_admission` tinyint(1) NOT NULL,
  `charlson_index` tinyint NOT NULL,
  `ed_visits_6m` tinyint NOT NULL,
  `entered_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`risk_context_id`),
  KEY `fk_riskctx_patient` (`patient_id`),
  KEY `fk_riskctx_staff` (`entered_by_staff_id`),
  CONSTRAINT `fk_riskctx_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_riskctx_staff` FOREIGN KEY (`entered_by_staff_id`) REFERENCES `care_staff` (`staff_id`),
  CONSTRAINT `chk_riskctx_values` CHECK (((`length_of_stay_days` >= 0) and (`charlson_index` >= 0) and (`ed_visits_6m` >= 0)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `risk_snapshots`
--

DROP TABLE IF EXISTS `risk_snapshots`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `risk_snapshots` (
  `snapshot_id` bigint NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `computed_at` datetime NOT NULL,
  `risk_score` tinyint unsigned NOT NULL,
  `contributing_factors` json DEFAULT NULL,
  PRIMARY KEY (`snapshot_id`),
  KEY `idx_risk_patient_time` (`patient_id`,`computed_at`),
  CONSTRAINT `fk_risk_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `chk_risk_score` CHECK ((`risk_score` between 0 and 100))
) ENGINE=InnoDB AUTO_INCREMENT=126 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `sensor_readings`
--

DROP TABLE IF EXISTS `sensor_readings`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sensor_readings` (
  `reading_id` bigint NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `device_id` varchar(60) NOT NULL,
  `measurement_type` enum('Heart_Rate','SpO2') NOT NULL,
  `measurement_value` decimal(7,2) NOT NULL,
  `unit` varchar(20) NOT NULL,
  `measured_at` datetime NOT NULL,
  `quality_status` enum('Good','Questionable','Invalid','Simulated') NOT NULL DEFAULT 'Simulated',
  PRIMARY KEY (`reading_id`),
  UNIQUE KEY `uq_device_measure_time` (`device_id`,`measurement_type`,`measured_at`),
  KEY `fk_reading_device_patient` (`device_id`,`patient_id`),
  KEY `idx_reading_patient_type_time` (`patient_id`,`measurement_type`,`measured_at`),
  CONSTRAINT `fk_reading_device_patient` FOREIGN KEY (`device_id`, `patient_id`) REFERENCES `devices` (`device_id`, `patient_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=20 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `trg_sensor_plausibility` BEFORE INSERT ON `sensor_readings` FOR EACH ROW BEGIN
    IF (NEW.measurement_type = 'Heart_Rate' AND (NEW.measurement_value < 20 OR NEW.measurement_value > 250))
       OR (NEW.measurement_type = 'SpO2' AND (NEW.measurement_value < 50 OR NEW.measurement_value > 100)) THEN
        SET NEW.quality_status = 'Invalid';
    END IF;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `trg_sensor_rules_after_insert` AFTER INSERT ON `sensor_readings` FOR EACH ROW BEGIN
    IF NEW.quality_status IN ('Good','Simulated') THEN
        INSERT INTO flags (patient_id, rule_id, source_type, source_ref_id, reason, severity)
        SELECT NEW.patient_id, r.rule_id, 'Sensor', NEW.reading_id,
               CONCAT(NEW.measurement_type, ' reading ', NEW.measurement_value, ' ', NEW.unit,
                      IF(r.rule_type = 'Reading_Above', ' is above ', ' is below '),
                      'the clinician-approved limit of ', r.threshold_value,
                      IF(NEW.quality_status = 'Simulated', ' (simulated reading)', '')),
               r.severity
        FROM alert_rules r
        WHERE r.patient_id = NEW.patient_id
          AND r.is_active = TRUE
          AND r.measurement_type = NEW.measurement_type
          AND ((r.rule_type = 'Reading_Above' AND NEW.measurement_value > r.threshold_value)
            OR (r.rule_type = 'Reading_Below' AND NEW.measurement_value < r.threshold_value))
          AND NOT EXISTS (SELECT 1 FROM flags f
                          WHERE f.rule_id = r.rule_id AND f.status IN ('Open','Acknowledged'));
    END IF;

    UPDATE devices
    SET last_seen_at = GREATEST(COALESCE(last_seen_at, NEW.measured_at), NEW.measured_at)
    WHERE device_id = NEW.device_id;
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;

--
-- Table structure for table `symptom_report_tags`
--

DROP TABLE IF EXISTS `symptom_report_tags`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `symptom_report_tags` (
  `tag_id` bigint NOT NULL AUTO_INCREMENT,
  `symptom_report_id` bigint NOT NULL,
  `tag` varchar(40) NOT NULL,
  `extracted_by` enum('Patient_Form','Keyword_Rule','LLM') NOT NULL,
  PRIMARY KEY (`tag_id`),
  UNIQUE KEY `uq_report_tag` (`symptom_report_id`,`tag`),
  CONSTRAINT `fk_tag_report` FOREIGN KEY (`symptom_report_id`) REFERENCES `symptom_reports` (`symptom_report_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `symptom_reports`
--

DROP TABLE IF EXISTS `symptom_reports`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `symptom_reports` (
  `symptom_report_id` bigint NOT NULL AUTO_INCREMENT,
  `patient_id` int NOT NULL,
  `symptom_text` text NOT NULL,
  `pain_level` tinyint DEFAULT NULL,
  `reported_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `input_method` enum('Text','Voice_Transcript','Caregiver') NOT NULL DEFAULT 'Text',
  `language` enum('en','hi') NOT NULL DEFAULT 'en',
  `emergency_keyword_hit` tinyint(1) NOT NULL DEFAULT '0',
  `review_status` enum('Pending','Reviewed','Follow_Up_Required','Closed') NOT NULL DEFAULT 'Pending',
  PRIMARY KEY (`symptom_report_id`),
  KEY `idx_symptom_patient_time` (`patient_id`,`reported_at`),
  CONSTRAINT `fk_symptom_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`) ON DELETE CASCADE,
  CONSTRAINT `chk_pain_level` CHECK (((`pain_level` is null) or (`pain_level` between 0 and 10)))
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE*/ /*!50017 DEFINER=`root`@`localhost`*/ /*!50003 TRIGGER `trg_symptom_rules_after_insert` AFTER INSERT ON `symptom_reports` FOR EACH ROW BEGIN
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
END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;

--
-- Table structure for table `user_accounts`
--

DROP TABLE IF EXISTS `user_accounts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `user_accounts` (
  `account_id` int NOT NULL AUTO_INCREMENT,
  `email` varchar(120) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `account_role` enum('Patient','Caregiver','Doctor','Nurse') NOT NULL,
  `patient_id` int DEFAULT NULL,
  `caregiver_id` int DEFAULT NULL,
  `staff_id` int DEFAULT NULL,
  PRIMARY KEY (`account_id`),
  UNIQUE KEY `email` (`email`),
  KEY `fk_account_patient` (`patient_id`),
  KEY `fk_account_caregiver` (`caregiver_id`),
  KEY `fk_account_staff` (`staff_id`),
  CONSTRAINT `fk_account_caregiver` FOREIGN KEY (`caregiver_id`) REFERENCES `caregivers` (`caregiver_id`),
  CONSTRAINT `fk_account_patient` FOREIGN KEY (`patient_id`) REFERENCES `patients` (`patient_id`),
  CONSTRAINT `fk_account_staff` FOREIGN KEY (`staff_id`) REFERENCES `care_staff` (`staff_id`),
  CONSTRAINT `chk_account_identity` CHECK ((((`account_role` = _utf8mb4'Patient') and (`patient_id` is not null) and (`caregiver_id` is null) and (`staff_id` is null)) or ((`account_role` = _utf8mb4'Caregiver') and (`caregiver_id` is not null) and (`patient_id` is null) and (`staff_id` is null)) or ((`account_role` in (_utf8mb4'Doctor',_utf8mb4'Nurse')) and (`staff_id` is not null) and (`patient_id` is null) and (`caregiver_id` is null))))
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Temporary view structure for view `v_device_status`
--

DROP TABLE IF EXISTS `v_device_status`;
/*!50001 DROP VIEW IF EXISTS `v_device_status`*/;
SET @saved_cs_client     = @@character_set_client;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50001 CREATE VIEW `v_device_status` AS SELECT 
 1 AS `device_id`,
 1 AS `patient_id`,
 1 AS `patient_name`,
 1 AS `device_type`,
 1 AS `last_seen_at`,
 1 AS `expected_interval_minutes`,
 1 AS `minutes_since_last_seen`,
 1 AS `connectivity_status`*/;
SET character_set_client = @saved_cs_client;

--
-- Temporary view structure for view `v_latest_risk`
--

DROP TABLE IF EXISTS `v_latest_risk`;
/*!50001 DROP VIEW IF EXISTS `v_latest_risk`*/;
SET @saved_cs_client     = @@character_set_client;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50001 CREATE VIEW `v_latest_risk` AS SELECT 
 1 AS `patient_id`,
 1 AS `computed_at`,
 1 AS `risk_score`,
 1 AS `risk_level`,
 1 AS `contributing_factors`*/;
SET character_set_client = @saved_cs_client;

--
-- Temporary view structure for view `v_latest_sensor_readings`
--

DROP TABLE IF EXISTS `v_latest_sensor_readings`;
/*!50001 DROP VIEW IF EXISTS `v_latest_sensor_readings`*/;
SET @saved_cs_client     = @@character_set_client;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50001 CREATE VIEW `v_latest_sensor_readings` AS SELECT 
 1 AS `patient_id`,
 1 AS `patient_name`,
 1 AS `measurement_type`,
 1 AS `measurement_value`,
 1 AS `unit`,
 1 AS `measured_at`,
 1 AS `quality_status`,
 1 AS `device_id`*/;
SET character_set_client = @saved_cs_client;

--
-- Temporary view structure for view `v_medication_adherence`
--

DROP TABLE IF EXISTS `v_medication_adherence`;
/*!50001 DROP VIEW IF EXISTS `v_medication_adherence`*/;
SET @saved_cs_client     = @@character_set_client;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50001 CREATE VIEW `v_medication_adherence` AS SELECT 
 1 AS `patient_id`,
 1 AS `patient_name`,
 1 AS `scheduled_events`,
 1 AS `taken_confirmed`,
 1 AS `marked_skipped`,
 1 AS `no_confirmation_missed`,
 1 AS `still_pending`,
 1 AS `self_reported_taken_pct`*/;
SET character_set_client = @saved_cs_client;

--
-- Temporary view structure for view `v_patient_timeline`
--

DROP TABLE IF EXISTS `v_patient_timeline`;
/*!50001 DROP VIEW IF EXISTS `v_patient_timeline`*/;
SET @saved_cs_client     = @@character_set_client;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50001 CREATE VIEW `v_patient_timeline` AS SELECT 
 1 AS `patient_id`,
 1 AS `event_time`,
 1 AS `event_type`,
 1 AS `summary`*/;
SET character_set_client = @saved_cs_client;

--
-- Temporary view structure for view `v_pending_followups`
--

DROP TABLE IF EXISTS `v_pending_followups`;
/*!50001 DROP VIEW IF EXISTS `v_pending_followups`*/;
SET @saved_cs_client     = @@character_set_client;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50001 CREATE VIEW `v_pending_followups` AS SELECT 
 1 AS `followup_id`,
 1 AS `patient_id`,
 1 AS `patient_name`,
 1 AS `assigned_to`,
 1 AS `reason`,
 1 AS `priority`,
 1 AS `status`,
 1 AS `created_at`*/;
SET character_set_client = @saved_cs_client;

--
-- Temporary view structure for view `v_triage_board`
--

DROP TABLE IF EXISTS `v_triage_board`;
/*!50001 DROP VIEW IF EXISTS `v_triage_board`*/;
SET @saved_cs_client     = @@character_set_client;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50001 CREATE VIEW `v_triage_board` AS SELECT 
 1 AS `patient_id`,
 1 AS `patient_name`,
 1 AS `flag_id`,
 1 AS `severity`,
 1 AS `source_type`,
 1 AS `reason`,
 1 AS `status`,
 1 AS `flagged_at`,
 1 AS `minutes_open`,
 1 AS `risk_score`,
 1 AS `risk_level`*/;
SET character_set_client = @saved_cs_client;

--
-- Temporary view structure for view `v_worklist_by_patient`
--

DROP TABLE IF EXISTS `v_worklist_by_patient`;
/*!50001 DROP VIEW IF EXISTS `v_worklist_by_patient`*/;
SET @saved_cs_client     = @@character_set_client;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50001 CREATE VIEW `v_worklist_by_patient` AS SELECT 
 1 AS `patient_id`,
 1 AS `patient_code`,
 1 AS `full_name`,
 1 AS `age_years`,
 1 AS `open_flag_count`,
 1 AS `distinct_reasons`,
 1 AS `top_severity_rank`,
 1 AS `has_emergency`,
 1 AS `not_yet_seen`,
 1 AS `first_flag_at`,
 1 AS `latest_flag_at`,
 1 AS `owner_staff_id`*/;
SET character_set_client = @saved_cs_client;

--
-- Dumping routines for database 'careloop'
--
/*!50003 DROP PROCEDURE IF EXISTS `sp_acknowledge_flag` */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_acknowledge_flag`(
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
END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 DROP PROCEDURE IF EXISTS `sp_approve_summary` */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_approve_summary`(
    IN p_summary_id BIGINT,
    IN p_doctor_staff_id INT,
    IN p_edited_text MEDIUMTEXT
)
BEGIN
    DECLARE v_status VARCHAR(20) DEFAULT NULL;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;

    START TRANSACTION;
    SELECT status INTO v_status FROM ai_summaries WHERE summary_id = p_summary_id FOR UPDATE;
    IF v_status IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Summary not found';
    END IF;

    UPDATE ai_summaries
    SET status = 'Approved',
        reviewed_by_staff_id = p_doctor_staff_id,
        reviewed_at = NOW(),
        edited_text = p_edited_text
    WHERE summary_id = p_summary_id;

    INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
    VALUES ('Staff', CAST(p_doctor_staff_id AS CHAR), 'APPROVE_SUMMARY', 'summary', p_summary_id,
            JSON_OBJECT('edited', p_edited_text IS NOT NULL));
    COMMIT;
END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 DROP PROCEDURE IF EXISTS `sp_assign_flag` */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_assign_flag`(
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
END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 DROP PROCEDURE IF EXISTS `sp_assign_task` */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_assign_task`(
    IN p_task_id BIGINT,
    IN p_staff_id INT,
    IN p_target_staff_id INT,
    IN p_note VARCHAR(255)
)
BEGIN
    DECLARE v_status VARCHAR(20) DEFAULT NULL;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;

    START TRANSACTION;
    SELECT status INTO v_status FROM follow_up_tasks WHERE followup_id = p_task_id FOR UPDATE;
    IF v_status IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Task not found';
    END IF;

    UPDATE follow_up_tasks
    SET assigned_staff_id = p_target_staff_id
    WHERE followup_id = p_task_id;

    INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
    VALUES ('Staff', CAST(p_staff_id AS CHAR), 'ASSIGN_TASK', 'task', p_task_id,
            JSON_OBJECT('target_staff_id', p_target_staff_id, 'note', p_note));
    COMMIT;
END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 DROP PROCEDURE IF EXISTS `sp_claim_task` */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_claim_task`(
    IN p_task_id BIGINT,
    IN p_staff_id INT
)
BEGIN
    DECLARE v_status VARCHAR(20) DEFAULT NULL;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;

    START TRANSACTION;
    SELECT status INTO v_status FROM follow_up_tasks WHERE followup_id = p_task_id FOR UPDATE;
    IF v_status IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Task not found';
    END IF;

    UPDATE follow_up_tasks
    SET assigned_staff_id = p_staff_id
    WHERE followup_id = p_task_id;

    INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
    VALUES ('Staff', CAST(p_staff_id AS CHAR), 'CLAIM_TASK', 'task', p_task_id, JSON_OBJECT('assigned_staff_id', p_staff_id));
    COMMIT;
END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 DROP PROCEDURE IF EXISTS `sp_complete_task` */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_complete_task`(
    IN p_task_id BIGINT,
    IN p_staff_id INT,
    IN p_outcome_code VARCHAR(50),
    IN p_outcome_notes VARCHAR(500)
)
BEGIN
    DECLARE v_status VARCHAR(20) DEFAULT NULL;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;

    START TRANSACTION;
    SELECT status INTO v_status FROM follow_up_tasks WHERE followup_id = p_task_id FOR UPDATE;
    IF v_status IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Task not found';
    END IF;
    IF v_status = 'Resolved' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Task is already resolved';
    END IF;

    UPDATE follow_up_tasks
    SET status = 'Resolved',
        completed_at = NOW(),
        outcome_code = p_outcome_code,
        outcome_notes = p_outcome_notes
    WHERE followup_id = p_task_id;

    INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
    VALUES ('Staff', CAST(p_staff_id AS CHAR), 'COMPLETE_TASK', 'task', p_task_id,
            JSON_OBJECT('outcome_code', p_outcome_code, 'notes', p_outcome_notes));
    COMMIT;
END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 DROP PROCEDURE IF EXISTS `sp_compute_all_risk_snapshots` */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_compute_all_risk_snapshots`(IN p_now DATETIME)
BEGIN
    DECLARE v_done INT DEFAULT 0;
    DECLARE v_pid  INT;
    DECLARE cur CURSOR FOR SELECT patient_id FROM patients WHERE consent_status = 'Granted';
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = 1;

    OPEN cur;
    read_loop: LOOP
        FETCH cur INTO v_pid;
        IF v_done = 1 THEN
            LEAVE read_loop;
        END IF;
        CALL sp_compute_risk_snapshot(v_pid, p_now);
    END LOOP;
    CLOSE cur;
END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 DROP PROCEDURE IF EXISTS `sp_compute_risk_snapshot` */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_compute_risk_snapshot`(IN p_patient_id INT, IN p_now DATETIME)
BEGIN
    DECLARE v_urgent INT DEFAULT 0;
    DECLARE v_soon   INT DEFAULT 0;
    DECLARE v_missed INT DEFAULT 0;
    DECLARE v_pain   INT DEFAULT 0;
    DECLARE v_score  INT DEFAULT 0;

    SELECT COALESCE(SUM(severity = 'Urgent_Review'), 0), COALESCE(SUM(severity = 'Review_Soon'), 0)
      INTO v_urgent, v_soon
    FROM flags
    WHERE patient_id = p_patient_id AND status IN ('Open','Acknowledged');

    SELECT COUNT(*) INTO v_missed
    FROM medication_logs ml
    JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
    WHERE pr.patient_id = p_patient_id AND ml.status = 'Missed'
      AND ml.scheduled_for >= p_now - INTERVAL 72 HOUR;

    SELECT COALESCE(MAX(pain_level), 0) INTO v_pain
    FROM symptom_reports
    WHERE patient_id = p_patient_id AND reported_at >= p_now - INTERVAL 72 HOUR;

    SET v_score = LEAST(100, v_urgent * 40 + v_soon * 20 + LEAST(v_missed * 10, 30) + IF(v_pain >= 7, 15, 0));

    INSERT INTO risk_snapshots (patient_id, computed_at, risk_score, contributing_factors)
    VALUES (p_patient_id, p_now, v_score,
            JSON_OBJECT('open_urgent_flags', v_urgent, 'open_review_soon_flags', v_soon,
                        'missed_doses_72h', v_missed, 'max_pain_72h', v_pain));
END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 DROP PROCEDURE IF EXISTS `sp_daily_report` */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_daily_report`(IN p_patient_id INT, IN p_day DATE)
BEGIN
    SELECT p.patient_id, p.full_name, p_day AS report_date
    FROM patients p WHERE p.patient_id = p_patient_id;

    SELECT m.medicine_name, ml.scheduled_for, ml.status, ml.recorded_at
    FROM medication_logs ml
    JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
    JOIN medicines m ON m.medicine_id = pr.medicine_id
    WHERE pr.patient_id = p_patient_id
      AND ml.scheduled_for >= p_day AND ml.scheduled_for < p_day + INTERVAL 1 DAY
    ORDER BY ml.scheduled_for;

    SELECT sr.measurement_type, COUNT(*) AS readings_used,
           MIN(sr.measurement_value) AS min_value, MAX(sr.measurement_value) AS max_value,
           ROUND(AVG(sr.measurement_value), 1) AS avg_value
    FROM sensor_readings sr
    WHERE sr.patient_id = p_patient_id
      AND sr.quality_status IN ('Good','Simulated')
      AND sr.measured_at >= p_day AND sr.measured_at < p_day + INTERVAL 1 DAY
    GROUP BY sr.measurement_type;

    SELECT s.reported_at, s.pain_level, s.input_method, s.language, s.symptom_text
    FROM symptom_reports s
    WHERE s.patient_id = p_patient_id
      AND s.reported_at >= p_day AND s.reported_at < p_day + INTERVAL 1 DAY
    ORDER BY s.reported_at;

    SELECT f.created_at, f.severity, f.source_type, f.reason, f.status
    FROM flags f
    WHERE f.patient_id = p_patient_id
      AND f.created_at >= p_day AND f.created_at < p_day + INTERVAL 1 DAY
    ORDER BY f.created_at;
END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 DROP PROCEDURE IF EXISTS `sp_evaluate_missed_dose_rules` */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_evaluate_missed_dose_rules`(IN p_now DATETIME)
BEGIN
    INSERT INTO flags (patient_id, rule_id, source_type, reason, severity)
    SELECT r.patient_id, r.rule_id, 'Medication',
           CONCAT(r.missed, ' dose(s) with no confirmation in the last ', r.window_hours,
                  ' hours (clinician-approved limit: ', r.threshold_value, ')'),
           r.severity
    FROM (
        SELECT r2.rule_id, r2.patient_id, r2.severity, r2.window_hours, r2.threshold_value,
               (SELECT COUNT(*)
                FROM medication_logs ml
                JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
                WHERE pr.patient_id = r2.patient_id
                  AND ml.status = 'Missed'
                  AND ml.scheduled_for >= p_now - INTERVAL r2.window_hours HOUR) AS missed
        FROM alert_rules r2
        WHERE r2.rule_type = 'Missed_Doses' AND r2.is_active = TRUE
    ) r
    WHERE r.missed >= r.threshold_value
      AND NOT EXISTS (SELECT 1 FROM flags f
                      WHERE f.rule_id = r.rule_id AND f.status IN ('Open','Acknowledged'));
END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 DROP PROCEDURE IF EXISTS `sp_evaluate_no_data_rules` */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_evaluate_no_data_rules`(IN p_now DATETIME)
BEGIN
    INSERT INTO flags (patient_id, rule_id, source_type, reason, severity)
    SELECT r.patient_id, r.rule_id, 'Device',
           CONCAT('No data from device ', d.device_id, ' for more than ', r.threshold_value,
                  ' hour(s). Missing data is not a normal reading.'),
           r.severity
    FROM alert_rules r
    JOIN devices d ON d.patient_id = r.patient_id
    WHERE r.rule_type = 'No_Data_Hours' AND r.is_active = TRUE
      AND (d.last_seen_at IS NULL OR d.last_seen_at < p_now - INTERVAL r.threshold_value HOUR)
      AND NOT EXISTS (SELECT 1 FROM flags f
                      WHERE f.rule_id = r.rule_id AND f.status IN ('Open','Acknowledged'));
END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 DROP PROCEDURE IF EXISTS `sp_generate_daily_doses` */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_generate_daily_doses`(IN p_date DATE)
BEGIN
    INSERT IGNORE INTO medication_logs (prescription_id, scheduled_for)
    SELECT pr.prescription_id, TIMESTAMP(p_date, pt.dose_time)
    FROM prescriptions pr
    JOIN prescription_times pt ON pt.prescription_id = pr.prescription_id
    WHERE pr.active_status = TRUE
      AND p_date >= pr.start_date
      AND (pr.end_date IS NULL OR p_date <= pr.end_date);
END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 DROP PROCEDURE IF EXISTS `sp_mark_overdue_doses_missed` */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_mark_overdue_doses_missed`(IN p_now DATETIME, IN p_grace_minutes INT)
BEGIN
    UPDATE medication_logs
    SET status = 'Missed', recorded_by = 'System'
    WHERE status = 'Unconfirmed'
      AND scheduled_for < p_now - INTERVAL p_grace_minutes MINUTE;
END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 DROP PROCEDURE IF EXISTS `sp_reject_summary` */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_reject_summary`(
    IN p_summary_id BIGINT,
    IN p_doctor_staff_id INT,
    IN p_reason VARCHAR(255)
)
BEGIN
    DECLARE v_status VARCHAR(20) DEFAULT NULL;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;

    START TRANSACTION;
    SELECT status INTO v_status FROM ai_summaries WHERE summary_id = p_summary_id FOR UPDATE;
    IF v_status IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Summary not found';
    END IF;

    IF p_reason IS NULL OR CHAR_LENGTH(TRIM(p_reason)) < 3 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A reason of at least 3 characters is required to reject a summary';
    END IF;

    UPDATE ai_summaries
    SET status = 'Rejected',
        reviewed_by_staff_id = p_doctor_staff_id,
        reviewed_at = NOW(),
        reject_reason = p_reason
    WHERE summary_id = p_summary_id;

    INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
    VALUES ('Staff', CAST(p_doctor_staff_id AS CHAR), 'REJECT_SUMMARY', 'summary', p_summary_id,
            JSON_OBJECT('reason', p_reason));
    COMMIT;
END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 DROP PROCEDURE IF EXISTS `sp_resolve_flag` */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_resolve_flag`(
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
END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 DROP PROCEDURE IF EXISTS `sp_snooze_task` */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_0900_ai_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE DEFINER=`root`@`localhost` PROCEDURE `sp_snooze_task`(
    IN p_task_id BIGINT,
    IN p_staff_id INT,
    IN p_hours INT,
    IN p_reason VARCHAR(255)
)
BEGIN
    DECLARE v_status VARCHAR(20) DEFAULT NULL;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;

    START TRANSACTION;
    SELECT status INTO v_status FROM follow_up_tasks WHERE followup_id = p_task_id FOR UPDATE;
    IF v_status IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Task not found';
    END IF;

    UPDATE follow_up_tasks
    SET due_at = NOW() + INTERVAL p_hours HOUR
    WHERE followup_id = p_task_id;

    INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
    VALUES ('Staff', CAST(p_staff_id AS CHAR), 'SNOOZE_TASK', 'task', p_task_id,
            JSON_OBJECT('hours', p_hours, 'reason', p_reason));
    COMMIT;
END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;

--
-- Final view structure for view `v_device_status`
--

/*!50001 DROP VIEW IF EXISTS `v_device_status`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_0900_ai_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `v_device_status` AS select `d`.`device_id` AS `device_id`,`d`.`patient_id` AS `patient_id`,`p`.`full_name` AS `patient_name`,`d`.`device_type` AS `device_type`,`d`.`last_seen_at` AS `last_seen_at`,`d`.`expected_interval_minutes` AS `expected_interval_minutes`,timestampdiff(MINUTE,`d`.`last_seen_at`,now()) AS `minutes_since_last_seen`,(case when (`d`.`last_seen_at` is null) then 'Never_Connected' when (timestampdiff(MINUTE,`d`.`last_seen_at`,now()) > (2 * `d`.`expected_interval_minutes`)) then 'Missing_Data' else 'Online' end) AS `connectivity_status` from (`devices` `d` join `patients` `p` on((`p`.`patient_id` = `d`.`patient_id`))) */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;

--
-- Final view structure for view `v_latest_risk`
--

/*!50001 DROP VIEW IF EXISTS `v_latest_risk`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_0900_ai_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `v_latest_risk` AS select `x`.`patient_id` AS `patient_id`,`x`.`computed_at` AS `computed_at`,`x`.`risk_score` AS `risk_score`,(case when (`x`.`risk_score` >= 60) then 'High' when (`x`.`risk_score` >= 30) then 'Moderate' else 'Low' end) AS `risk_level`,`x`.`contributing_factors` AS `contributing_factors` from (select `rs`.`patient_id` AS `patient_id`,`rs`.`computed_at` AS `computed_at`,`rs`.`risk_score` AS `risk_score`,`rs`.`contributing_factors` AS `contributing_factors`,row_number() OVER (PARTITION BY `rs`.`patient_id` ORDER BY `rs`.`computed_at` desc,`rs`.`snapshot_id` desc )  AS `rn` from `risk_snapshots` `rs`) `x` where (`x`.`rn` = 1) */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;

--
-- Final view structure for view `v_latest_sensor_readings`
--

/*!50001 DROP VIEW IF EXISTS `v_latest_sensor_readings`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_0900_ai_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `v_latest_sensor_readings` AS select `x`.`patient_id` AS `patient_id`,`p`.`full_name` AS `patient_name`,`x`.`measurement_type` AS `measurement_type`,`x`.`measurement_value` AS `measurement_value`,`x`.`unit` AS `unit`,`x`.`measured_at` AS `measured_at`,`x`.`quality_status` AS `quality_status`,`x`.`device_id` AS `device_id` from ((select `sr`.`reading_id` AS `reading_id`,`sr`.`patient_id` AS `patient_id`,`sr`.`device_id` AS `device_id`,`sr`.`measurement_type` AS `measurement_type`,`sr`.`measurement_value` AS `measurement_value`,`sr`.`unit` AS `unit`,`sr`.`measured_at` AS `measured_at`,`sr`.`quality_status` AS `quality_status`,row_number() OVER (PARTITION BY `sr`.`patient_id`,`sr`.`measurement_type` ORDER BY `sr`.`measured_at` desc )  AS `rn` from `sensor_readings` `sr`) `x` join `patients` `p` on((`p`.`patient_id` = `x`.`patient_id`))) where (`x`.`rn` = 1) */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;

--
-- Final view structure for view `v_medication_adherence`
--

/*!50001 DROP VIEW IF EXISTS `v_medication_adherence`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_0900_ai_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `v_medication_adherence` AS select `p`.`patient_id` AS `patient_id`,`p`.`full_name` AS `patient_name`,count(`ml`.`medication_log_id`) AS `scheduled_events`,coalesce(sum((`ml`.`status` = 'Taken_Confirmed')),0) AS `taken_confirmed`,coalesce(sum((`ml`.`status` = 'Skipped')),0) AS `marked_skipped`,coalesce(sum((`ml`.`status` = 'Missed')),0) AS `no_confirmation_missed`,coalesce(sum((`ml`.`status` = 'Unconfirmed')),0) AS `still_pending`,round(((100 * sum((`ml`.`status` = 'Taken_Confirmed'))) / nullif(count(`ml`.`medication_log_id`),0)),1) AS `self_reported_taken_pct` from ((`patients` `p` join `prescriptions` `pr` on((`pr`.`patient_id` = `p`.`patient_id`))) left join `medication_logs` `ml` on((`ml`.`prescription_id` = `pr`.`prescription_id`))) group by `p`.`patient_id`,`p`.`full_name` */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;

--
-- Final view structure for view `v_patient_timeline`
--

/*!50001 DROP VIEW IF EXISTS `v_patient_timeline`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_0900_ai_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `v_patient_timeline` AS select `sr`.`patient_id` AS `patient_id`,`sr`.`measured_at` AS `event_time`,'Reading' AS `event_type`,concat(`sr`.`measurement_type`,' ',`sr`.`measurement_value`,' ',`sr`.`unit`,' [',`sr`.`quality_status`,']') AS `summary` from `sensor_readings` `sr` union all select `s`.`patient_id` AS `patient_id`,`s`.`reported_at` AS `reported_at`,'Symptom' AS `Symptom`,concat('Pain ',coalesce(`s`.`pain_level`,'n/a'),': ',left(`s`.`symptom_text`,120)) AS `Name_exp_8` from `symptom_reports` `s` union all select `pr`.`patient_id` AS `patient_id`,`ml`.`scheduled_for` AS `scheduled_for`,'Dose' AS `Dose`,concat(`m`.`medicine_name`,' - ',`ml`.`status`) AS `CONCAT(m.medicine_name, ' - ', ml.status)` from ((`medication_logs` `ml` join `prescriptions` `pr` on((`pr`.`prescription_id` = `ml`.`prescription_id`))) join `medicines` `m` on((`m`.`medicine_id` = `pr`.`medicine_id`))) union all select `f`.`patient_id` AS `patient_id`,`f`.`created_at` AS `created_at`,'Flag' AS `Flag`,concat(`f`.`severity`,': ',`f`.`reason`) AS `CONCAT(f.severity, ': ', f.reason)` from `flags` `f` */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;

--
-- Final view structure for view `v_pending_followups`
--

/*!50001 DROP VIEW IF EXISTS `v_pending_followups`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_0900_ai_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `v_pending_followups` AS select `t`.`followup_id` AS `followup_id`,`p`.`patient_id` AS `patient_id`,`p`.`full_name` AS `patient_name`,`s`.`full_name` AS `assigned_to`,`t`.`reason` AS `reason`,`t`.`priority` AS `priority`,`t`.`status` AS `status`,`t`.`created_at` AS `created_at` from ((`follow_up_tasks` `t` join `patients` `p` on((`p`.`patient_id` = `t`.`patient_id`))) join `care_staff` `s` on((`s`.`staff_id` = `t`.`assigned_staff_id`))) where (`t`.`status` = 'Pending') */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;

--
-- Final view structure for view `v_triage_board`
--

/*!50001 DROP VIEW IF EXISTS `v_triage_board`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_0900_ai_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `v_triage_board` AS select `p`.`patient_id` AS `patient_id`,`p`.`full_name` AS `patient_name`,`f`.`flag_id` AS `flag_id`,`f`.`severity` AS `severity`,`f`.`source_type` AS `source_type`,`f`.`reason` AS `reason`,`f`.`status` AS `status`,`f`.`created_at` AS `flagged_at`,timestampdiff(MINUTE,`f`.`created_at`,now()) AS `minutes_open`,`lr`.`risk_score` AS `risk_score`,`lr`.`risk_level` AS `risk_level` from ((`flags` `f` join `patients` `p` on((`p`.`patient_id` = `f`.`patient_id`))) left join `v_latest_risk` `lr` on((`lr`.`patient_id` = `p`.`patient_id`))) where (`f`.`status` in ('Open','Acknowledged')) */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;

--
-- Final view structure for view `v_worklist_by_patient`
--

/*!50001 DROP VIEW IF EXISTS `v_worklist_by_patient`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_0900_ai_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`root`@`localhost` SQL SECURITY DEFINER */
/*!50001 VIEW `v_worklist_by_patient` AS select `p`.`patient_id` AS `patient_id`,`p`.`patient_code` AS `patient_code`,`p`.`full_name` AS `full_name`,timestampdiff(YEAR,`p`.`date_of_birth`,curdate()) AS `age_years`,count(0) AS `open_flag_count`,count(distinct concat(`f`.`source_type`,':',coalesce(`f`.`rule_id`,0))) AS `distinct_reasons`,max((case `f`.`severity` when 'Urgent_Review' then 3 when 'Review_Soon' then 2 else 1 end)) AS `top_severity_rank`,max((`f`.`source_type` = 'Emergency')) AS `has_emergency`,sum((`f`.`status` = 'Open')) AS `not_yet_seen`,min(`f`.`created_at`) AS `first_flag_at`,max(`f`.`created_at`) AS `latest_flag_at`,max(`f`.`owner_staff_id`) AS `owner_staff_id` from (`flags` `f` join `patients` `p` on((`p`.`patient_id` = `f`.`patient_id`))) where (`f`.`status` in ('Open','Acknowledged')) group by `p`.`patient_id`,`p`.`patient_code`,`p`.`full_name`,`p`.`date_of_birth` */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-10-30 13:10:27
