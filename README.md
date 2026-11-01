# CareLoop: Post-Discharge Patient Triage & Wearable Telemetry System

> [!IMPORTANT]
> **Synthetic-data prototype, not a medical device.**  
> CareLoop is an engineering demonstration platform designed to evaluate post-discharge remote patient monitoring workflows. All patient records, clinical notes, telemetry readings, wound photos, and thresholds are synthetic test data. It is not approved for clinical diagnostic use, does not establish medical diagnoses, and never replaces professional clinical judgment.

---

## 🏛️ Core Governing Principles

> **"The LLM talks. Rules decide. Humans act."**  
> **"Automate the routine. Propose the rest. Humans decide."**

* **Positioning:** CareLoop keeps the days after discharge from going quiet: it automates the routine, shows its reason for every alert, answers only from the patient's own papers, and makes sure a person closes every loop.
* **Tagline:** *After discharge, nothing should go quiet.*
* **The LLM is text-only:** Generates draft summaries, drafts recovery plans, and answers patient questions strictly from discharge document excerpts. It **never** creates, closes, or alters flags, tasks, thresholds, or prescriptions.
* **Deterministic Rules Decide:** Clinical alerts, risk rankings, and emergency detections are code-driven and rule-based. Emergency phrases (in English or Hindi) immediately trigger 112 guidance without invoking the LLM.
* **Humans Act:** Only qualified human clinicians review recovery photos, approve recovery plans, approve rule limits, triage calls, and resolve flags.

---

## 📋 Scope Boundaries: Core Scope vs Extensions

Per project architectural guidelines, capabilities are structured into committed core scope and additive extensions:

### 1. Core Scope
* **Wearable Hardware:** ESP32 DevKit V1 (30-pin), MAX30102 pulse oximeter (pulse & estimated SpO₂ via I2C SDA GPIO 21 / SCL GPIO 22), MPU-6050 motion sensor, 0.96-inch SSD1306 OLED display, momentary tactile push button for manual SOS, and Li-Po power management.
* **Device Telemetry Ingestion API:** `POST /device/readings` and `POST /device/events` authenticated via `X-Device-Key`. Plausibility filtering in MySQL triggers (impossible spikes such as 450 bpm are tagged `Invalid` and never become the headline).
* **Relational Database Engine:** MySQL 8.0+ transactional storage (InnoDB) with stored procedures, triggers, views, and strict referential integrity.
* **Rule-Based Flags:** SQL triggers evaluate doctor-approved limits (`alert_rules`) and raise prioritized flags on threshold breaches.
* **Patient & Staff Dashboards:** Dedicated responsive workstations for Doctor, Nurse, Patient, and Family Helper with BhoomiSetu design tokens and light/dark theme.
* **Audit Trail:** Immutable append-only audit logging (`audit_log`) for every clinical and administrative event.
* **Emergency Keyword Safety:** Zero-latency plain-code regex matching in English and Hindi directly triggers 112 emergency guidance.

### 2. Extensions (Additive Capabilities)
*(Note: Extensions are modular capabilities added to enhance post-discharge safety; pending supervisor confirmation before calling extensions formally approved.)*
* **"Ask My Papers" Assistant:** Hybrid RAG pipeline (ChromaDB dense vectors + MySQL keyword search) with cited source chips and strict dose modification refusal.
* **Automated Rounds & Automation Policy:** Background scheduler executing a transparent 24-hour lookahead for routine actions (quiet hours 22:00–07:00, daily message limits, patient pause, and clinician proposals).
* **Two-Way SMS Service:** Twilio integration behind `SMS_ENABLED` (logged to database when disabled) supporting patient commands: `1` (dose confirmed), `2` (status check), `3` (urgent callback request), and `STOP`/`START` compliance.
* **Guided Health Check-in:** Step-by-step check-in wizard with text-to-speech audio guidance, speech-to-text voice input, and instant emergency keyword detection.
* **Recovery & Wound Photo Quality Check:** Client and server-side deterministic quality evaluation (Laplacian sharpness variance, mean brightness, resolution), EXIF metadata stripping, and nurse side-by-side comparative review.
* **Recovery Plan Drafter & Patient Admission:** Discharge paper parsing, strict number grounding guard, reconciliation mismatch detection, doctor approval lifecycle, and 7-step nurse patient admission wizard.
* **Watch Events & Possible Fall Prompts:** Bounded motion event evaluation (*"No text says detected"*), 2-minute patient inquiry prompt (*"Are you OK?"*), and 3 deterministic outcomes (A: I'm OK, B: Need Help, C: Wait time expired $\rightarrow$ Immediate flag).

---

## 👥 The Four Distinct Roles

| Role | User & Login | Section 2.1 One-Liner | What to Look at First | Accent |
| :--- | :--- | :--- | :--- | :--- |
| **Doctor** | **Dr. Ananya Sharma**<br>`ananya.demo@example.test` | *"The doctor approves recovery plans, decides escalated alerts, and sets limits."* | **Needs My Decision** queue (`/staff/doctor/decisions`), Plan Approvals, Summary Approvals, and HL7 FHIR R4 JSON export. | Slate / Navy (`#0284c7`) |
| **Nurse** | **Priya Nair**<br>`priya.demo@example.test` | *"The nurse runs Rounds, reviews recovery photos, calls patients, and starts follow-ups."* | **Rounds** (`/staff/rounds`), **My Call List** queue, Photo Review, and **Start Follow-up** admission wizard. | Amber / Orange (`#d97706`) |
| **Patient** | **Aarav Patel**<br>`aarav.demo@example.test` | *"The patient follows My Plan, completes voice or SMS check-ins, and asks their papers."* | **My Plan** (`/patient`), Guided Check-in with voice/listen, photo upload, and cited discharge assistant. | Emerald / Teal (`#059669`) |
| **Family Helper** | **Neha Patel**<br>`caregiver1.demo@example.test` | *"The family helper supports with consent, sees calm updates, and calls 112 if needed."* | **Today's Support View** (`/family`), helped-dose confirmation, and live patient consent toggle verification. | Violet / Purple (`#7c3aed`) |

*Password for all demo accounts:* **`Demo@12345`**

---

## 🛠️ Technology Stack

| Component | Technology | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Frontend** | React SPA, React Router, Tailwind CSS | React 18.2.0, Tailwind 3.4.17 | Responsive role portals, dark/light theme, design tokens |
| **Backend API** | FastAPI, Uvicorn | FastAPI 0.128.0 | REST endpoints, JWT authorization, safety guards |
| **Database** | MySQL (InnoDB) via PyMySQL | MySQL 8.0+, PyMySQL 1.1.1 | 35 tables, 8 views, 16 stored procedures, 3 triggers |
| **Grounded AI** | Google GenAI (Gemini) & ChromaDB | google-genai 0.1.1, Chroma 0.5.23 | Strict RAG discharge assistant, plan drafter & SBAR summaries |
| **Two-Way SMS** | Twilio REST API & Inbound Webhook | twilio 9.0.0+ | Outbound reminders and inbound SMS command parser |
| **IoT / Hardware** | ESP32 Arduino Core / Python Simulator | C++ / Python 3.12 | MAX30102 / MPU-6050 firmware and event simulator |

---

## 📁 Repository Structure

```
CareLoop/
├── README.md               # Quickstart guide, demo credentials, scope, and disclaimer
├── PROJECT_GUIDE.md        # Comprehensive clinical and technical architecture guide
├── .gitignore              # Ignores env, dependencies, caches, and local databases
├── .env.example            # Environment template (no secrets)
├── backend/                # FastAPI application, auth, permissions, RAG pipeline, and eval
├── database/               # Consolidated schema.sql and idempotent reset_demo.sql
├── device/                 # IoT sensor simulator, Bluetooth bridge, and ESP32 firmware
├── frontend/               # React single-page application and public static assets
├── scripts/                # Operational CLI tools: reset_demo, validate_demo, simulate_event
└── tests/                  # 99 safety-critical pytest acceptance tests across all 4 roles
```

---

## 🚀 Quickstart from a Fresh Clone

### Prerequisites
* Python 3.12+
* Node.js 18+ and npm
* Local MySQL 8.0+ server running on port 3306

### 1. Database Initialization
```bash
# Create schema and initialize careloop database
mysql -u root -p < database/schema.sql

# Seed clean 5-patient demo dataset (< 0.35 seconds)
./backend/env/bin/python scripts/reset_demo.py
```

### 2. Environment Configuration
```bash
cp .env.example backend/.env
# Edit backend/.env to set your DB_PASSWORD and optional LLM_API_KEY
```

### 3. Backend Setup
```bash
cd backend
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 4. Frontend Setup
```bash
cd frontend
npm install
npm start
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

### 5. Running the Telemetry Simulator & Watch Events
```bash
# Continuous physiological telemetry streaming
python3 device/simulator.py --interval 10

# Simulate sudden motion spike and stillness (Possible Fall event)
python3 device/simulator.py --device DEV-ESP32-005 --fall

# Trigger live low SpO2 breach (91% < 94%) for Aarav Patel
python3 scripts/simulate_event.py

# Validate complete 21-check demo contract
./backend/env/bin/python scripts/validate_demo.py
```

---

## 🧪 Acceptance Test Suite

Run the complete 99-test acceptance suite:
```bash
PYTHONPATH=. ./backend/env/bin/pytest tests/ -v
```

All 99 tests pass covering automation policy, Rounds, guided check-ins, two-way SMS, photo privacy, recovery plans, admission wizard, watch events, role permissions, and offline resilience.

---

## 👥 Credits & Attribution
CareLoop Post-Discharge Patient Triage & Wearable Telemetry System.  
Synthetic-data prototype, not a medical device.  
All code, database procedures, design tokens, and wearable hardware architecture preserved.  
For complete architectural details, see [PROJECT_GUIDE.md](PROJECT_GUIDE.md).
