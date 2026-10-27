# CareLoop Upgrade — Gap Analysis (GAP_ANALYSIS.md)

**Baseline Source:** `careloop_master_project_document.md` (Part B: Feature Catalog F-01 to F-38, Stretch S-01 to S-07, Future F-F1 to F-F4)  
**Target Database Schema:** `careloop_mysql_v2_detailed.sql` (MySQL 8.0.16+, 25 tables, 7 views, 8 stored procedures, 3 triggers, 2 events)  
**Existing Baseline:** `agentic-ai-nurse` (MongoDB, FastAPI, React, in-memory live vitals, Gemini triage)  
**Date:** October 27, 2026  

---

## 1. Classification Categories

- **Already done:** Feature exists and meets CareLoop principles with little to no modification required.
- **Needs change:** Feature exists in concept or partial implementation, but currently uses MongoDB, lacks security/consent, or lets LLM decide risk instead of rules.
- **Missing:** Feature does not exist in the codebase and must be implemented from scratch.
- **Remove or disable:** Feature contradicts core principles (e.g. AI diagnosis, fake client-side metrics) and must be removed or disabled behind a configuration flag.

---

## 2. Feature-by-Feature Gap Analysis (Part B Catalog)

### 2.1 Patient-Facing Features

| ID | Feature | Existing Status in `agentic-ai-nurse` | CareLoop Classification | Required Action for CareLoop Upgrade |
|---|---|---|---|---|
| **F-01** | Login and roles (Patient, Caregiver, Doctor, Nurse) | Partial (Nurse login, Doctor login/register, unauthenticated Patient access). Roles checked in JWT claims loosely. | **Needs change** | Re-implement auth using MySQL `user_accounts` table (`bcrypt`, `PyJWT`). Ensure exactly 1 role per account (DB CHECK). Require credentials for Patient. Enforce `require_role()` dependency on endpoints. |
| **F-02** | Today's doses + confirm/skip | Partial in MongoDB (`daily_routine` array inside patient document). Completing task calls `/patient/task/complete`. | **Needs change** | Replace with MySQL `medication_logs` populated by `sp_generate_daily_doses`. Provide `GET /patient/me/doses` and `POST /patient/me/doses/{id}/confirm` (`Taken_Confirmed` or `Skipped`). Isolate strictly by JWT `patient_id`. |
| **F-03** | Dose reminders agent | Exists in `BackgroundBrain` (polls every 60s, sends Twilio SMS within ±2 min window). | **Needs change** | Connect reminder job in `scheduler.py` to MySQL `medication_logs`. Mark `reminder_sent_at`, write to `audit_log`, respect patient consent (`consent_status='Granted'`), format SMS without medical/diagnosis details. |
| **F-04** | Symptom check-in (text/voice, pain 0–10, language) | Chat endpoint accepts text or voice. No structured pain scale or language tracking. | **Needs change** | Implement `POST /patient/me/symptoms` with `symptom_text`, `pain_level` (0–10 checked by DB), `language` ('en'/'hi'), and `input_method`. Writes to `symptom_reports`. |
| **F-05** | Emergency keyword layer (deterministic code) | **Missing**. Emergency categorization is delegated to Gemini LLM (`TRIAGE_SYSTEM_PROMPT`). | **Missing (Critical)** | Build deterministic `safety.py` keyword scanner (English + Hindi: "chest pain", "can't breathe", "सीने में दर्द", etc.). Executes before any LLM call, returns immediate guidance, sets `emergency_keyword_hit=TRUE` triggering DB trigger `trg_symptom_rules_after_insert`. |
| **F-06** | Symptom tags | **Missing**. Tags are not stored or queried. | **Missing** | Post-check-in async agent asks LLM for 1–3 short tags, validates string format, and inserts into MySQL `symptom_report_tags` with `extracted_by='LLM'`. Fails gracefully without blocking check-in. |
| **F-07** | Hindi + English interface & guidance | **Missing**. Codebase is English only. | **Missing** | Add language toggle and Hindi/English localized strings for emergency guidance, reminders, medication actions, and dashboard badges. |
| **F-08** | Cited Q&A over discharge docs (RAG) | Partial. ChromaDB isolates collections per patient. Answers returned without citation tracking. | **Needs change** | Re-anchor RAG in `rag.py`: Store uploaded document chunks in MySQL `document_chunks`. On retrieval, insert citation mapping rows into `chat_message_sources` linking `chat_messages` to `document_chunks`. |
| **F-09** | Safe refusal for dose changes & out-of-doc queries | **Missing**. Prompt tells LLM to answer medical questions from context; does not detect dose changes deterministically. | **Missing (Critical)** | Add deterministic `is_dose_change_question()` check in `safety.py`. If triggered, safely refuse, set `is_grounded=FALSE` in `chat_messages`, and insert a task into `follow_up_tasks` for nursing staff. |
| **F-10** | Patient status page (vitals, device status, appointments) | Exists via `getPatientPersonalization` and live WebSocket vitals. | **Needs change** | Build `GET /patient/me/status` backed by MySQL views: `v_latest_sensor_readings`, `v_device_status`, and `appointments`. Clearly display "Missing Data" or "Questionable" instead of 0 or simulated values. |

---

### 2.2 Device and Data-Quality Features

| ID | Feature | Existing Status in `agentic-ai-nurse` | CareLoop Classification | Required Action for CareLoop Upgrade |
|---|---|---|---|---|
| **F-11** | Idempotent device ingestion | **Missing**. `POST /device/vitals/{patient_id}` writes directly to an in-memory dictionary. Retries overwrite or duplicate. | **Missing** | Create `POST /device/readings` checking `X-Device-Key`. Inserts into `sensor_readings`. On MySQL Error 1062 (duplicate unique constraint `device_id, measurement_type, measured_at`), return `{"status": "duplicate_ignored"}`. |
| **F-12** | Reading plausibility guard | **Missing**. Unchecked inputs accept any integer. | **Needs change** | Managed in MySQL via `trg_sensor_plausibility` (BEFORE INSERT). Values like HR > 300 or < 20 become `Invalid` quality and never trigger clinical flags. |
| **F-13** | Quality labels (`Good`, `Questionable`, `Invalid`, `Simulated`) | **Missing**. No quality status field exists in existing telemetry payload. | **Missing** | Ingest `quality_status` in `sensor_readings` and propagate to all views and dashboard UI cards. |
| **F-14** | Device simulator (`device/simulator.py`) | **Missing**. Only `Hardware/watch.py` exists (requires physical Bluetooth connection). | **Missing** | Implement `device/simulator.py` with `--low-spo2` switch, `--interval`, and randomized plausible telemetry. |
| **F-15** | ESP32 + MAX30102 firmware | **Missing**. Only `Hardware/watch.py` is present; no `.ino` or C++ files exist. | **Missing** | Create `device/esp32_careloop/esp32_careloop.ino` using SparkFun MAX3010x library, NTP time sync, and HTTPS/HTTP POST to `/device/readings`. Keep `watch.py` as legacy compatibility bridge. |
| **F-16** | Heartbeat and missing-data detection | Partial. WebSocket defaults to 0 if watch not transmitting. | **Needs change** | Update `devices.last_seen_at` on reading ingestion. View `v_device_status` flags `Missing_Data` if inactive > 30 min. Scheduler runs `sp_evaluate_no_data_rules` to create a `Review_Soon` flag. |

---

### 2.3 Rule Engine and Flags

| ID | Feature | Existing Status in `agentic-ai-nurse` | CareLoop Classification | Required Action for CareLoop Upgrade |
|---|---|---|---|---|
| **F-17** | Clinician-approved alert rules | **Missing**. No alert rules table or concept in MongoDB. | **Missing** | Backed by MySQL `alert_rules` table where doctors set per-patient thresholds (`Heart_Rate`, `SpO2`, `Pain_Level`, `Missed_Dose_Count`, `No_Data_Hours`). |
| **F-18** | Sensor reading rule evaluation | **Missing** (LLM decides alert). | **Needs change** | Enforced by MySQL trigger `trg_sensor_rules_after_insert`. When reading violates approved limit, creates one `Urgent_Review` or `Review_Soon` row in `flags` with plain-text clinical explanation. |
| **F-19** | Pain rule evaluation | **Missing**. | **Missing** | Enforced by MySQL trigger `trg_symptom_rules_after_insert`. Evaluates `pain_level` against approved threshold in `alert_rules`. |
| **F-20** | Missed-dose rule evaluation | **Missing**. | **Missing** | Scheduler runs `sp_evaluate_missed_dose_rules()` every cycle. Checks unconfirmed doses against rule thresholds. |
| **F-21** | No-data rule evaluation | **Missing**. | **Missing** | Scheduler runs `sp_evaluate_no_data_rules()`. Raises flag if device has been silent past rule limit. |
| **F-22** | Flags with reason, severity, status | Partial. MongoDB `chat_history` stores `risk_score` and `action`. | **Needs change** | Managed in MySQL `flags` table with statuses: `Open`, `Acknowledged`, `Resolved`, `Dismissed`. Every flag contains human-readable `reason_text` and `source_type`. |
| **F-23** | Duplicate-flag protection | **Missing**. Cooldown of 60s hardcoded for fall alerts in RAM; other alerts duplicate freely. | **Needs change** | DB triggers/procedures enforce `NOT EXISTS (SELECT 1 FROM flags WHERE patient_id=... AND rule_id=... AND status IN ('Open','Acknowledged'))`. |

---

### 2.4 Escalation and Clinician Workflow

| ID | Feature | Existing Status in `agentic-ai-nurse` | CareLoop Classification | Required Action for CareLoop Upgrade |
|---|---|---|---|---|
| **F-24** | Escalation ladder with timeouts | Exists in rudimentary form in `BackgroundBrain` (3 check-in attempts then family SMS). | **Needs change** | Implement standard CareLoop ladder in `escalation.py`: `LADDER_REVIEW_SOON` and `LADDER_URGENT`. Steps logged in `escalations` table. |
| **F-25** | Consent-gated caregiver step | **Missing**. Family contact is messaged regardless of consent. | **Missing (Critical)** | Query `caregivers` for `consent_granted=TRUE`. If consent is missing, skip SMS and record `delivery_status='Skipped_No_Consent'` in `escalations` and log in `audit_log`. |
| **F-26** | Triage board | Exists in `DoctorDashboard.jsx` (fetches `/doctor/alerts` filtering `risk_score >= 4`). | **Needs change** | Point to `GET /staff/triage` querying view `v_triage_board`. Display severity, reason text, minutes open, and priority score. |
| **F-27** | Atomic acknowledge | Broken in current app (`DELETE /doctor/alerts/{id}` deletes MongoDB record). | **Needs change (Critical)** | Implement `POST /staff/flags/{id}/acknowledge` executing `sp_acknowledge_flag` (MySQL transaction: locks row, marks flag Acknowledged, sets escalations Acknowledged, creates follow-up task, writes audit log). |
| **F-28** | Follow-up tasks | **Missing**. | **Missing** | Stored in MySQL `follow_up_tasks`. Surfaced via view `v_pending_followups`. |
| **F-29** | Appointments | Read from MongoDB patient profile. | **Needs change** | Read from MySQL `appointments` table. |
| **F-30** | Patient timeline | Separate chat history and vitals logs. | **Needs change** | Expose `GET /staff/patients/{id}/timeline` reading unified `v_patient_timeline` view. |
| **F-31** | Daily report | **Missing**. | **Missing** | Callable via MySQL procedure `sp_daily_report(patient_id, date)`. |
| **F-32** | Adherence overview | Hardcoded calculation in React. | **Needs change** | Read from MySQL view `v_medication_adherence`. |

---

### 2.5 Intelligence, Trust and Governance

| ID | Feature | Existing Status in `agentic-ai-nurse` | CareLoop Classification | Required Action for CareLoop Upgrade |
|---|---|---|---|---|
| **F-33** | Explainable priority score | **Missing**. Uses arbitrary LLM `risk_score` (1–10). | **Needs change** | Compute deterministic additive score (0–100) via `sp_compute_risk_snapshot()` storing contributing factors in JSON (`urgent_flags`, `missed_doses`, `pain`). Display on triage board. |
| **F-34** | AI daily draft summary | **Missing**. | **Missing** | Background summary agent generates factual summary from `sp_daily_report`, inserts into `ai_summaries` marked "AI draft, not reviewed". |
| **F-35** | Audit log | **Missing**. | **Missing (Critical)** | Every automated agent step, SMS dispatch, flag creation, and staff acknowledge writes an immutable row in `audit_log`. |
| **F-36** | Consent gating of monitoring | **Missing**. All admitted patients are actively monitored. | **Missing** | Respect `patients.consent_status` in periodic scoring and reminder jobs. |
| **F-37** | Least-privilege DB account | MongoDB runs without restricted app users. | **Needs change** | Create `careloop_api` MySQL user with `SELECT, INSERT, UPDATE, EXECUTE` on `careloop.*` (no `DELETE` or `DDL`). |
| **F-38** | Record-level authorization | Insecure (patient endpoints accept `patient_id` in URL or body). | **Needs change (Critical)** | Patient endpoints must extract `patient_id` solely from verified JWT payload (`user["patient_id"]`). Prevent IDOR completely. |

---

### 2.6 Stretch & Legacy Features

| ID | Feature | Existing Status | CareLoop Classification | Required Action |
|---|---|---|---|---|
| **S-01** | Wound-photo upload for clinician viewing | Exists in `vision_tool.py` as an AI diagnostic tool. | **Remove or disable (diagnostic AI)** / **Re-purpose as Stretch (clinician viewer)** | Disable LLM diagnostic inference behind config flag `ENABLE_WOUND_AI_DIAGNOSIS=false`. If uploaded, store for clinician visual inspection only. |
| **S-02** | Per-device hashed API keys | Ingestion uses single global key `DEVICE_API_KEY`. | **Stretch** | Hash device keys against `devices.api_key_hash`. |
| **S-03** | Staff-to-patient assignment filtering | Regex match on doctor last name. | **Stretch** | Use `discharge_records.attending_staff_id`. |
| **S-04** | WhatsApp channel | Not present. | **Future** | Keep out of scope. |
| **S-05** | BLE via phone | `watch.py` connects via desktop Bluetooth. | **Stretch** | Document as limitation. |
| **S-06** | Caregiver view | Not present. | **Stretch** | Provide caregiver login with read-only access. |
| **S-07** | PDF/CSV report export | Not present. | **Stretch** | Future scope. |
| **F-F1** | Fall detection / Temperature | Fall detection in `watch.py` is dummy binary flag. | **Future** | Explicitly state as simulated/demo feature; do not claim clinical validation. |
| **—** | Audio analysis (Librosa) | Claimed in README, non-existent in code. | **Remove** | Remove inaccurate claims from documentation. |
| **—** | OpenCV preprocessing | Claimed in README, non-existent in code. | **Remove** | Remove inaccurate claims from documentation. |
| **—** | Client-side fake SpO₂ generator | Hardcoded in `TriageDashboard.jsx`. | **Remove immediately** | Delete `setInterval` random SpO₂; show real readings or explicit "Missing Data" label. |

---

## 3. Migration Action Plan Summary

1. **Database:** Initialize MySQL schema `careloop_mysql_v2_detailed.sql` and verify object counts (25 tables, 7 views, 8 procedures, 3 triggers, 2 events).
2. **Backend:** Replace MongoDB/Firestore data layer with raw SQL via PyMySQL (`db.py`).
3. **Safety Engine:** Create `safety.py` containing deterministic keyword checks and dose-change refusal logic.
4. **Auth & Security:** Implement strict JWT token authentication with role-based checks and patient ID isolation.
5. **Telemetry & Hardware:** Build idempotent `POST /device/readings` and `device/simulator.py`. Keep `watch.py` mapped to the new endpoint structure.
6. **AI Layer:** Refactor `rag.py` to store chunk citations in MySQL and strip all triage/risk scoring responsibilities from LLM prompts.
7. **Frontend:** Update dashboard components to consume CareLoop REST API endpoints and views (`v_triage_board`, `v_patient_timeline`).
