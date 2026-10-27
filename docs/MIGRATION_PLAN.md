# CareLoop Upgrade — Migration Plan (MIGRATION_PLAN.md)

**Branch:** `careloop-upgrade`  
**Target Architecture:** CareLoop (MySQL 8.0.16+, FastAPI, PyMySQL raw SQL, ChromaDB citations, Rule-based Escalation)  
**Core Rule:** *"The LLM talks. Rules decide. Humans act."*

---

## 1. Migration Strategy & Principles

1. **Non-destructive Migration:** All existing routes and functionality will be preserved or kept backwards-compatible until their replacements are tested and verified.
2. **Feature Flags for Heavy / Diagnostic AI:**
   - `ENABLE_WOUND_AI_DIAGNOSIS=false`: Wound-image analysis will not give clinical infection diagnoses; images can be uploaded and stored for human clinician viewing only.
   - `ENABLE_AUDIO_ANALYSIS=false`: Voice input will use browser speech recognition or Deepgram purely for Speech-to-Text transcription. The raw transcript is passed directly through deterministic emergency keyword checks before any LLM interaction.
3. **No Secrets in Code:** Create `backend/.env.example`. Replace any committed API keys in `.env` with environment variable loading. Ensure `.env`, `.venv/`, `chroma/`, and `__pycache__/` are ignored in `.gitignore`.
4. **Single Timezone:** Set and enforce `Asia/Kolkata` (IST, `+05:30`) globally across MySQL, Python backend, and IoT timestamps.
5. **Database as Single Source of Truth:** Replace MongoDB queries with raw SQL transactions and procedures via PyMySQL.

---

## 2. Milestone Execution Plan

### Milestone M0: Database Provisioning & Validation
- **Actions:**
  1. Verify MySQL 8.0.16+ availability (detected MySQL 9.7.1).
  2. Execute `careloop_mysql_v2_detailed.sql` to instantiate the `careloop` schema.
  3. Create dedicated application user `careloop_api` with `SELECT, INSERT, UPDATE, EXECUTE` (no `DELETE` or `DDL`).
  4. Run validation queries:
     - **Q19:** Verify exact object counts (25 tables, 7 views, 8 procedures, 3 triggers, 2 events).
     - **Q2:** Triage board view.
     - **Q6:** `trg_sensor_rules_after_insert` low SpO₂ trigger.
     - **Q7:** `trg_sensor_plausibility` impossible value guard.
     - **Q8:** `trg_symptom_rules_after_insert` emergency hit trigger.
  5. Document any SQL syntax adjustments or character set requirements.

### Milestone M1: Backend Foundation & Multi-Role Auth
- **Files to create/modify:**
  - `backend/app/db.py`: Context manager for PyMySQL with dictionary cursor, IST timezone setting, and transactional commit/rollback.
  - `backend/app/auth.py`: Bcrypt password verification, HS256 JWT generation and validation, and `require_role("Patient", "Caregiver", "Doctor", "Nurse")` dependencies.
  - `scripts/set_demo_passwords.py`: Script to seed bcrypt password hashes for seed accounts in `user_accounts`.
  - `backend/.env.example`: Safe template without credentials.
  - `backend/app/main.py`: Refactored to expose `/auth/login`, health checks, and role-guarded routes.
- **Verification:** Swagger docs at `http://localhost:8000/docs`, login for all 4 roles, verifying Patient routes reject URL-based IDs and strictly extract `patient_id` from the JWT token.

### Milestone M2: Device Data Ingestion & Simulator
- **Files to create/modify:**
  - `device/simulator.py`: Python device simulator with `--low-spo2`, `--device`, `--interval`, and `--key` flags.
  - `device/esp32_careloop/esp32_careloop.ino`: Arduino sketch for ESP32 + MAX30102 with UTC NTP time sync and HTTP POST.
  - `Hardware/watch.py`: Update legacy serial bridge to send authenticated readings to `/device/readings`.
  - `backend/app/main.py`: `POST /device/readings` endpoint (idempotent, returns `duplicate_ignored` on duplicate insert).
- **Verification:** Post duplicate reading (assert `duplicate_ignored`), post low SpO₂ (assert exactly 1 flag in `flags` table with clinical reason).

### Milestone M3: Patient Flows & Deterministic Safety Layer
- **Files to create/modify:**
  - `backend/app/safety.py`: Deterministic emergency keyword dictionary (English + Hindi) and dose-change refusal patterns.
  - `backend/app/main.py`: `GET /patient/me/doses`, `POST /patient/me/doses/{id}/confirm`, `POST /patient/me/symptoms`, and `GET /patient/me/status`.
  - `backend/app/scheduler.py`: Dose reminder background job updating `medication_logs.reminder_sent_at`.
- **Verification:** Submit symptom check-in with "chest pain" or "सीने में दर्द" (assert instant emergency guidance returned without LLM delay and Urgent flag raised in DB).

### Milestone M4: Consent-Gated Escalation & Clinical Workflow
- **Files to create/modify:**
  - `backend/app/escalation.py`: Review-soon and Urgent escalation ladders, caregiver consent check (`caregivers.consent_granted`), Twilio wrapper with `SMS_ENABLED=false` fallback.
  - `backend/app/scheduler.py`: Background scheduler running rule cycle (`sp_mark_overdue_doses_missed`, `sp_evaluate_missed_dose_rules`, `sp_evaluate_no_data_rules`, `sp_compute_all_risk_snapshots`) and escalation loop.
  - `backend/app/main.py`: `GET /staff/triage` and `POST /staff/flags/{id}/acknowledge` (calling `sp_acknowledge_flag`).
- **Verification:** Kabir's missing caregiver consent logs `Skipped_No_Consent`. Acknowledging a flag creates a follow-up task and audit row. Double acknowledge returns HTTP 409 conflict.

### Milestone M5: AI Layer with Strict Boundaries
- **Files to create/modify:**
  - `backend/app/llm.py`: Single wrapper for hosted LLM generating text only.
  - `backend/app/rag.py`: Grounded Q&A against patient discharge documents. Queries ChromaDB, fetches matching chunks from MySQL `document_chunks`, records citations in `chat_message_sources`.
  - `scripts/index_document.py`: PDF indexer extracting text, generating chunks, and populating MySQL `discharge_documents` + `document_chunks` + ChromaDB collection.
- **Verification:** Ask "What is my follow-up appointment?" (assert grounded reply with citations); ask "Can I double my dose?" (assert refusal and creation of nursing follow-up task).

### Milestone M6: Frontend Integration, Hindi Localization & Demo Verification
- **Files to create/modify:**
  - Frontend components (`TriageDashboard`, `DoctorDashboard`, `NurseDashboard`) refactored to consume MySQL views via CareLoop REST API.
  - Remove fake client-side random oxygen generator.
  - Add Hindi language toggle and labels.
  - Run end-to-end 5-minute demo script (Section A10) and verify test checklist (Section C13).
