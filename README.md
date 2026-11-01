# CareLoop: Post-Discharge Telemetry & Triage Platform

> [!IMPORTANT]
> **Synthetic-data prototype, not a medical device.**
> CareLoop is an engineering demonstration platform designed to evaluate post-discharge remote patient monitoring workflows. All patient records, clinical notes, telemetry readings, and thresholds are synthetic test data. It is not approved for clinical diagnostic use, does not establish medical diagnoses, and never replaces professional clinical judgment.

---

## 🏛️ Core Governing Principle

> **"The LLM talks. Rules decide. Humans act."**

* **The LLM is text-only:** Generates draft summaries and answers patient questions strictly from discharge document excerpts. It **never** creates, closes, or alters flags, tasks, thresholds, or prescriptions.
* **Deterministic Rules Decide:** Clinical alerts, risk rankings, and emergency detections are code-driven and rule-based. Emergency phrases (in English or Hindi) immediately trigger 112 guidance without invoking the LLM.
* **Humans Act:** Only qualified human clinicians review summaries, approve rule limits, triage calls, and resolve flags.

---

## 👥 The Four Distinct Roles

| Role | User & Login | Section 2.1 One-Liner | What to Look at First | Accent |
| :--- | :--- | :--- | :--- | :--- |
| **Doctor** | **Dr. Ananya Sharma**<br>`ananya.demo@example.test` | *"The doctor decides, approves and exports."* | **Needs My Decision** queue (`/staff/doctor/decisions`), SBAR summary approvals, and HL7 FHIR R4 JSON export. | Slate / Navy (`#0284c7`) |
| **Nurse** | **Priya Nair**<br>`priya.demo@example.test` | *"The nurse calls, logs, rechecks and escalates."* | **My Call List** queue (`/staff/nurse/call-list`), structured call logging modal, and shift handoff. | Amber / Orange (`#d97706`) |
| **Patient** | **Aarav Patel**<br>`aarav.demo@example.test` | *"The patient acts, checks in and asks their papers."* | **Today's Regimen** (`/patient`), 1-tap dose taken with 5-min undo, check-in, and cited discharge assistant. | Emerald / Teal (`#059669`) |
| **Family Helper** | **Aarav's Family Helper**<br>`caregiver1.demo@example.test` | *"The family helper supports, is informed with consent, and calls 112 if needed."* | **Today's Support View** (`/family`), helped-dose button, and live consent toggle verification. | Violet / Purple (`#7c3aed`) |

*Password for all demo accounts:* **`Demo@12345`**

---

## 🛠️ Technology Stack

| Component | Technology | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Frontend** | React SPA, React Router, Tailwind CSS | React 18.2.0, Tailwind 3.4.17 | Responsive role portals, dark/light theme, design tokens |
| **Backend API** | FastAPI, Uvicorn | FastAPI 0.128.0 | REST endpoints, JWT authorization, safety guards |
| **Database** | MySQL (InnoDB) via PyMySQL | MySQL 8.0+, PyMySQL 1.1.1 | 32 tables, 8 views, 16 stored procedures, 3 triggers |
| **Grounded AI** | Google GenAI (Gemini) & ChromaDB | google-genai 0.1.1, Chroma 0.5.23 | Strict RAG discharge assistant & SBAR fact-sheet summaries |
| **IoT / Hardware** | ESP32 Arduino Core / Python Simulator | C++ / Python 3.12 | MAX30102 pulse oximeter firmware and telemetry simulator |

---

## 📁 Repository Structure

```
CareLoop/
├── README.md               # Quickstart guide, demo credentials, and disclaimer
├── PROJECT_GUIDE.md        # Comprehensive clinical and technical architecture guide
├── .gitignore              # Ignores env, dependencies, caches, and local databases
├── .env.example            # Environment template (no secrets)
├── backend/                # FastAPI application, auth, permissions, RAG pipeline, and eval
├── database/               # Consolidated schema.sql and idempotent reset_demo.sql
├── device/                 # IoT sensor simulator, Bluetooth bridge, and ESP32 firmware
├── frontend/               # React single-page application and public static assets
├── scripts/                # Operational CLI tools: reset_demo, validate_demo, simulate_event
└── tests/                  # 51 safety-critical pytest acceptance tests across all 4 roles
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

# Seed clean 5-patient demo dataset (< 0.25 seconds)
python3 scripts/reset_demo.py
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

### 5. Running the Telemetry Simulator & Live Event
```bash
# Continuous physiological telemetry streaming
python3 device/simulator.py --interval 10

# Trigger live SpO2 drop (91% < 94%) for Aarav Patel (demonstrates clinical escalation)
python3 scripts/simulate_event.py

# Validate complete 12-check demo contract
./backend/env/bin/python3 scripts/validate_demo.py
```

---

## 🧪 Acceptance Test Suite

Run the 51 safety-critical acceptance tests:
```bash
PYTHONPATH=. ./backend/env/bin/pytest tests/ -v
```

---

## 👥 Credits & Attribution
CareLoop Post-Discharge Telemetry & Triage Platform.
Synthetic-data prototype, not a medical device.
All code, database procedures, design tokens, and wearable hardware architecture preserved.
For complete architectural details, see [PROJECT_GUIDE.md](PROJECT_GUIDE.md).
