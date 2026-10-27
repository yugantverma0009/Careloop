# CareLoop (Agentic Post-Discharge Care System)
*Autonomous Clinical Post-Discharge Triage & Wearable Telemetry Platform*

CareLoop is an **agentic post-discharge care management system** engineered to support patients in the vulnerable days following hospital discharge. It combines wearable physiological telemetry, deterministic clinical rule safety guards, an autonomous multi-step escalation ladder, and grounded AI retrieval.

---

## 🏛️ Core Governing Principle

> **"The LLM talks. Rules decide. Humans act."**

* **LLM output is text only**: It never creates clinical flags, never changes prescriptions, never gives medical diagnoses, and never advises on dose modifications.
* **Flags come only from clinician-approved rules** (`alert_rules`), database triggers and stored procedures (`trg_sensor_rules_after_insert`, `sp_evaluate_patient_rules`), and a deterministic emergency keyword check in plain code.
* **Emergency guidance never waits for an LLM call**: Emergency phrases in English or Hindi immediately surface life-safety emergency guidance and alert clinical staff.
* **All demonstration data is synthetic**: Prototype threshold values only, not clinically validated.

---

## ⚙️ Architectural Highlights & Milestones

### 1. Database (Milestone M0)
* **Single Source of Truth**: Local MySQL 8.0.16+ with 25 relational tables, 7 real-time views, 8 stored procedures, 3 automated triggers, and 2 scheduled events.
* **Least-Privilege Security**: `careloop_api` database account with `SELECT, INSERT, UPDATE, EXECUTE` on `careloop.*` (no DDL/DELETE permissions).
* **Guaranteed Auditability**: Append-only `audit_log` records every medication confirmation, clinical alert, escalation step, and review action.

### 2. Multi-Role Authentication & Isolation (Milestone M1)
* **JWT Authentication**: HS256 JWT tokens with 8-hour expiration.
* **Strict Role Segregation**: 4 distinct roles (`Patient`, `Caregiver`, `Doctor`, `Nurse`).
* **IDOR Protection**: Patient routes strictly bind to `patient_id` from the authenticated token claim, completely preventing horizontal privilege escalation.

### 3. Device Telemetry & Ingestion (Milestone M2)
* **Idempotent Ingestion**: `POST /device/readings` rejects or ignores duplicated device packets (`duplicate_ignored`).
* **Plausibility Guard**: Sensor trigger marks non-physiological values (e.g., > 300 bpm) as `Invalid` with 0 false-positive flags.
* **ESP32 Firmware & Hardware Simulator**: Firmware in `device/esp32_careloop/` and Python telemetry simulator (`device/simulator.py`) supporting live SpO₂ and heart-rate streaming.

### 4. Patient Flows & Deterministic Safety Engine (Milestone M3)
* **Medication Adherence**: `GET /patient/me/doses` and `POST /patient/me/doses/{log_id}/confirm` (Taken/Skipped) with audit logging.
* **Bilingual Emergency Detection**: Deterministic keyword engine in English and Hindi (e.g., "chest pain", "सीने में दर्द").
* **Transparent Patient Status**: Shows actual telemetry, quality badges, and explicit `"Missing data"` (never 0 or blank).

### 5. Escalation Agent & Clinical Workflow (Milestone M4)
* **Autonomous Escalation Ladder**: `Review_Soon` and `Urgent_Review` ladders progressing through Patient Prompt, Caregiver SMS, Nurse Alert, and Doctor Alert.
* **Privacy by Design (Consent Gate)**: If caregiver consent is not granted, the caregiver step is logged as `Skipped_No_Consent`.
* **Atomic Flag Acknowledgment**: Transactional `sp_acknowledge_flag` marks flags and escalations `Acknowledged`, creates follow-up tasks, and prevents double-acknowledgment.

### 6. Grounded AI Layer (Milestone M5)
* **One Single LLM Wrapper**: `backend/app/llm.py` wrapping Gemini API with failure resilience.
* **Document Chunking & Vector Search**: `scripts/index_document.py` indexing synthetic discharge summaries into ChromaDB collections.
* **Grounded RAG with Citations**: `POST /patient/me/chat` answers strictly from discharge excerpts, links citations to `chat_message_sources`, and deterministically refuses dose modifications (`is_grounded = FALSE`).
* **Factual Daily AI Summaries**: Synthesizes `sp_daily_report` data into factual notes marked with **"AI draft, not reviewed"** until clinician review.

### 7. Modern Web Portals (Milestone M6)
* **CareLoop Login**: Modern responsive glassmorphism portal with quick demo buttons for all 4 roles.
* **Patient Recovery Portal**: Today's medications, live telemetry, bilingual symptom check-in, and grounded discharge assistant.
* **Clinical Triage Hub**: Real-time triage board with priority score, severity color, reason text, patient timeline, and AI summary approval.

---

## 🚀 Quickstart Guide

### 1. Database Setup
```bash
mysql -u root -p < careloop_mysql_v2_detailed.sql
python3 scripts/set_demo_passwords.py
```

### 2. Backend Setup
```bash
cd backend
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 3. Frontend Setup
```bash
cd frontend
npm install
npm start
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

### 4. Run Telemetry Simulator
```bash
# Send normal readings every 3 seconds
python3 device/simulator.py --interval 3

# Trigger low SpO2 alert
python3 device/simulator.py --low-spo2 --once
```

### 5. Hardware Integration
The ESP32 wearable streams physiological data via `device/esp32_careloop/esp32_careloop.ino`.
* **MAX30102** → Heart rate & SpO₂ monitoring
* **MPU6050** → Motion detection
* **OLED Display** → Real-time local feedback

---

## 🧪 Comprehensive Test Suites

Run individual milestone tests or the complete regression suite:
```bash
# Milestone M1: Auth & Isolation
PYTHONPATH=. ./backend/env/bin/python3 tests/test_m1_auth.py

# Milestone M2: Device Telemetry & Ingestion
PYTHONPATH=. ./backend/env/bin/python3 tests/test_m2_device.py

# Milestone M3: Patient Flows & Emergency Detection
PYTHONPATH=. ./backend/env/bin/python3 tests/test_m3_patient_flows.py

# Milestone M4: Escalation Ladder & Clinical Workflow
PYTHONPATH=. ./backend/env/bin/python3 tests/test_m4_escalation.py

# Milestone M5: Grounded RAG, Safety Boundaries & Summaries
PYTHONPATH=. ./backend/env/bin/python3 tests/test_m5_ai.py
```

---

## 🔒 Safety & Reliability Guardrails
* **Human-in-the-Loop**: All clinical decisions, dose adjustments, and escalated alerts require human clinician review.
* **Zero AI Diagnostic Hallucinations**: Image/audio diagnostic analysis is disabled/restricted in accordance with clinical safety principles.
* **Graceful Degradation**: If LLM or SMS provider APIs experience outages, rules continue evaluating and staff alerts remain fully functional.

---

## 👥 Credits & Attribution
Autonomous Clinical Post-Discharge Triage & Wearable Telemetry Platform.
Original team credits, design assets, and wearable hardware architecture preserved.