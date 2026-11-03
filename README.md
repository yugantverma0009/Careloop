# CareLoop: Post-Discharge Patient Care & Clinical Agents Platform

> [!IMPORTANT]
> **Synthetic-data prototype, not a medical device.**  
> CareLoop is an engineering demonstration platform designed to evaluate post-discharge remote patient monitoring and clinical agent workflows. All patient records, clinical notes, sensor readings, wound photos, and limits are synthetic test data. It is not approved for clinical diagnostic use, does not provide medical diagnoses, and never substitutes for professional clinical judgment.

---

## 🏛️ Governing Headline & Principle

> # **"Agents do the routine. People make the calls."**  
> *"CareLoop keeps the days after discharge from going quiet: agents prepare every case and answer from the patient's own papers, rules raise every alert with its reason, and people make every decision."*

* **The Core Rule:** *"The LLM talks. Rules decide. Humans act."*
* **Every case arrives prepared:** Clinical alarms are pre-compiled into concise briefs with grounded facts, pre-identified unknowns, and fixed administrative next steps.
* **Autonomy is earned:** Every automated action starts in Shadow Mode until agreement is proven from data; promotion to Live is strictly doctor-governed.
* **Pause with one switch:** An emergency kill switch halts all automated agents immediately without affecting rules, reminders, or escalation.
* **Patients retain control:** Patients can turn off automated assistance at any time from their home screen.

---

## 📋 Scope Boundaries: Core Scope vs Extensions

Per project architectural guidelines, capabilities are structured into committed core scope and additive extensions:

### 1. Core Scope
* **Wearable Hardware:** ESP32 DevKit V1 (30-pin), MAX30102 pulse sensor (pulse and estimated SpO₂ via I2C SDA GPIO 21 / SCL GPIO 22), MPU-6050 motion sensor, 0.96-inch SSD1306 OLED display, momentary tactile push button for manual SOS, and Li-Po power management.
* **Device Sensor Ingestion API:** `POST /device/readings` and `POST /device/events` authenticated via `X-Device-Key`. Plausibility filtering in MySQL triggers (impossible spikes such as 450 bpm are tagged `Invalid` and never become the headline).
* **Relational Database Engine:** MySQL 8.0+ transactional storage (InnoDB) with stored procedures, triggers, views, and strict referential integrity.
* **Rule-Based Flags:** SQL triggers evaluate doctor-approved limits (`alert_rules`) and raise prioritized flags on threshold breaches.
* **Patient & Staff Dashboards:** Dedicated responsive workstations for Doctor, Nurse, Patient, and Family Helper with BhoomiSetu design tokens and light/dark theme.
* **Audit Trail:** Immutable append-only audit logging (`audit_log`) for every clinical and administrative event.
* **Emergency Keyword Safety:** Zero-latency plain-code regex matching in English and Hindi directly triggers 112 emergency guidance without invoking an LLM.

### 2. Extensions: CareLoop Care Agents
* **Papers Agent (Agentic RAG):** Sourced answers to patient recovery questions using hybrid retrieval (ChromaDB multilingual embeddings + MySQL keyword search + Reciprocal Rank Fusion), section-aware chunk citations, numeric grounding verification, and plain-code safety gates.
* **Case Prep Agent:** Synthesizes incoming alerts into unified case briefs with grounded facts, pre-identified unknowns, and administrative next steps from a fixed menu. Merges duplicate alarms within 30 minutes into a single active case.
* **Call Notes Agent:** 3-click call documentation synthesizing structured clinician notes, follow-up tasks, and patient messages from quick picks and speech dictation.
* **Outreach Agent:** Manages patient check-ins and retry ladders within strict quiet hours (22:00–07:00 IST), daily caps (max 3/day), SMS STOP opt-out, and active emergency suppression.
* **Handoff Agent:** Compiles deterministic clinical fact sheets from SQL records and drafts SBAR/I-PASS shift handoffs with zero subjective judgment words.
* **Plan Agent:** Synthesizes post-discharge recovery plans from discharge documents, reconciles active prescriptions against discharge orders, and activates plans only upon doctor signature.

---

## 🤖 The Six CareLoop Care Agents

```mermaid
flowchart TD
    subgraph Inputs["Clinical Inputs & Triggers"]
        Sensors["Watch Sensor Readings & SOS"]
        Papers["Discharge Documents (PDF)"]
        PatientMsg["Patient Questions (Text/Voice/SMS)"]
        NurseCall["Nurse Phone Calls & Dictation"]
    end

    subgraph Agents["CareLoop Care Agents Tier"]
        PapersAg["Papers Agent<br/>(Agentic RAG)"]
        CasePrepAg["Case Prep Agent<br/>(Brief Synthesizer)"]
        CallNotesAg["Call Notes Agent<br/>(3-Click Documentation)"]
        OutreachAg["Outreach Agent<br/>(Adaptive Follow-Up)"]
        HandoffAg["Handoff Agent<br/>(Shift Synthesis)"]
        PlanAg["Plan Agent<br/>(Recovery Plans)"]
    end

    subgraph Safety["Deterministic Safety Tier"]
        Dispatcher["Dispatcher<br/>(Budgets & Kill Switch)"]
        PolicyGuard["Policy Guard<br/>(10 Safety Checks)"]
        SQLRules["SQL Alert Rules<br/>(Limits & Thresholds)"]
    end

    subgraph Clinicians["Human-in-the-Loop Decisions"]
        NurseDesk["Nurse Agent Desk<br/>(Review & Sign Drafts)"]
        DoctorDesk["Doctor Decisions & Settings<br/>(Promote Autonomy / Approve Plans)"]
        PatientUI["Patient Portal<br/>(Grounded Answers & AI Toggle)"]
    end

    PatientMsg --> Dispatcher --> PapersAg --> PolicyGuard --> PatientUI
    Sensors --> SQLRules --> CasePrepAg --> PolicyGuard --> NurseDesk
    NurseCall --> CallNotesAg --> PolicyGuard --> NurseDesk
    Papers --> PlanAg --> PolicyGuard --> DoctorDesk
    HandoffAg --> PolicyGuard --> NurseDesk
    OutreachAg --> PolicyGuard --> PatientUI
```

| Agent | What it does | Autonomy Default | Safety Gate | Human Role |
| :--- | :--- | :--- | :--- | :--- |
| **Papers Agent** | Answers routine questions strictly from discharge papers | **Auto** (Live) | Blocks dose changes, diagnosis requests, injections | Reads cited chips; asks team if unsure |
| **Case Prep Agent** | Prepares case briefs from flags; merges duplicates within 30m | **Auto** (Live) | Facts cite source IDs; unknowns explicit; fixed menu | Reviews brief; selects action |
| **Call Notes Agent** | Drafts note, follow-up task, and patient update in 3 clicks | **Draft** (Live) | 0 invented symptoms/numbers beyond nurse input | Edits or signs draft in one action |
| **Outreach Agent** | Sends check-in reminders and manages call retries | **Auto** (Live) | Quiet hours (22:00–07:00), daily caps, consent check | Undoes scheduled outreach; reviews escalations |
| **Handoff Agent** | Compiles fact sheets and drafts shift handoffs | **Draft** (Live) | Zero clinical judgment words (unsubstantiated condition labels) | Reviews and signs shift handoff |
| **Plan Agent** | Drafts recovery plan from discharge papers with reconciliation | **Draft** (Live) | Item citations; reconciliation tags (*Matches/Mismatch*) | Doctor approves to activate plan |

---

## 🔒 Policy Guard: 10 Deterministic Safety Checks

Every agent output is intercepted by `PolicyGuard.inspect()` before storage or delivery:
1. **Allowlist:** Only approved tools and actions for that agent and autonomy level.
2. **Identity Verification:** Context patient ID matches payload patient ID; zero patient name leakage to LLMs.
3. **Sources:** Every factual sentence must cite an existing document chunk or SQL record ID.
4. **Numeric Grounding:** Every number, dosage, and date must be present in cited source text.
5. **Fixed Menu:** Next steps restricted to the 7-item administrative menu (`call_now`, `send_checkin`, `request_photo`, `ask_doctor`, `recheck_at`, `merge_duplicate`, `close_rule`).
6. **Language:** Output language matches patient preference (en/hi).
7. **Banned Words:** Zero subjective clinical judgment words (unsubstantiated condition labels) and zero diagnosis advice.
8. **Caregiver Consent:** Family outreach blocked if patient has not granted consent.
9. **Automation Limits:** Enforces quiet hours (22:00–07:00 IST), daily caps (max 3/day), pause switch, and active emergency suppression.
10. **Schema & Red-Team Gate:** Valid JSON schema; input length capped at 1200 chars; 100% of prompt injections, jailbreaks, and cross-patient requests blocked.

---

## ⏱️ Workload Replay Benchmark (Empirical Results)

Replay of a 40-event scripted synthetic shift (14 routine questions, 10 reminder follow-ups, 6 duplicate alerts, 5 call documentations, 3 shift summaries, 2 urgent cases) across the cohort:

| Shift Workload Metric | Manual (Agents OFF) | Agents Active (CareLoop) | Impact |
| :--- | :---: | :---: | :---: |
| **Human Steps** | **155 steps** | **36 steps** | **-76.8% reduction** |
| **Clinician Time** | **157.0 minutes** | **22.5 minutes** | **134.5 min saved (~2.2 hrs)** |
| **Assumptions Label** | *"Estimated from editable assumptions"* | Configurable via `PUT /agent/assumptions` | Shown on screen |

### Dynamically Computed Shadow Agreement:
* **Sourced Answers (`papers_question_sourced`):** **95.0% agreement** over 40 cases (38 agreed).
* **Call Notes Drafts (`call_notes_draft`):** **88.0% accepted without edits** over 25 cases (22 agreed).

---

## 👥 The Four Distinct Roles

| Role | User & Login | Section 2.1 One-Liner | What to Look at First | Accent |
| :--- | :--- | :--- | :--- | :--- |
| **Doctor** | **Dr. Ananya Sharma**<br>`ananya.demo@example.test` | *"The doctor approves recovery plans, decides escalated alerts, and sets limits."* | **Needs My Decision** (`/staff/doctor/decisions`), Agent Settings (Autonomy Matrix & Kill Switch), Work Saved Panel. | Slate / Navy (`#0284c7`) |
| **Nurse** | **Priya Nair**<br>`priya.demo@example.test` | *"The nurse runs Rounds, reviews recovery photos, calls patients, and starts follow-ups."* | **Agent Desk** (`/staff/desk`), My Call List with Case Briefs, 3-Click Call Documentation, Shift Handoff. | Amber / Orange (`#d97706`) |
| **Patient** | **Aarav Patel**<br>`aarav.demo@example.test` | *"The patient follows My Plan, completes voice or SMS check-ins, and asks their papers."* | **My Plan** (`/patient`), Sourced Discharge Assistant with Citations, Guided Check-in, AI Help Switch. | Emerald / Teal (`#059669`) |
| **Family Helper** | **Neha Patel**<br>`caregiver1.demo@example.test` | *"The family helper supports with consent, sees calm updates, and calls 112 if needed."* | **Today's Support View** (`/family`), helped-dose confirmation, and live patient consent toggle verification. | Violet / Purple (`#7c3aed`) |

*Password for all demo accounts:* **`password123`** (or `Demo@12345`)

---

## 📊 Comparison: CareLoop vs First-Generation Healthcare Bot Concepts

| First-Generation Healthcare Bot Concept | How CareLoop Solves It in Code | Proven In Code |
| :--- | :--- | :--- |
| LLM decides whether patient is deteriorating | Deterministic SQL triggers evaluate doctor limits; LLM has zero authority to alert | `backend/app/agents/policy_guard.py:30` |
| AI gives open-ended medical diagnosis advice | Safety gate intercepts dose changes and diagnosis; returns 112 guidance or care team task | `backend/app/safety.py:12` |
| AI acts autonomously without human review | Four autonomy tiers; paperwork requires human sign-off; shadow mode first | `backend/app/agents/dispatcher.py:80` |
| Clinician overwhelmed by paperwork after call | 3-click workflow synthesizes note, task, and patient update from quick picks and dictation | `backend/app/agents/call_notes_agent.py:120` |
| Patient cannot opt out of automated AI | Single-toggle "AI help" switch on patient home screen disables agent responses | `backend/app/agents/dispatcher.py:140` |
| Untrusted text from patient or PDF jailbreaks AI | Deterministic red-team gate blocks 100% of injections and cross-patient snooping | `backend/app/agents/policy_guard.py:279` |
| Hospital cannot shut off runaway AI | Global emergency kill switch pauses all agent operations in one click | `backend/app/agents/dispatcher.py:110` |

---

## 🚀 Quickstart from Fresh Clone

### Prerequisites
* Python 3.12+
* Node.js 18+ and npm
* MySQL 8.0+ server running on port 3306

### 1. Database Initialization
```bash
# Set database credentials in backend/.env
# DB_USER=careloop_api, DB_PASSWORD=careloop_dev_pass, DB_NAME=careloop

# Run the idempotent demo seeder (resets and validates in under 3 seconds)
PYTHONPATH=. ./backend/env/bin/python scripts/seed_demo.py
PYTHONPATH=. ./backend/env/bin/python scripts/validate_demo.py
```

### 2. Run the Full Test Suite (46 Tests)
```bash
PYTHONPATH=. ./backend/env/bin/pytest tests/ -v
```

### 3. Run the Workload Replay Benchmark
```bash
PYTHONPATH=. ./backend/env/bin/python scripts/replay_workload.py
```

### 4. Start the Application
```bash
# Terminal 1: Backend API
./backend/env/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Frontend SPA
npm --prefix frontend start
```
Open `http://127.0.0.1:3000` in your browser.

---

## 📜 Regulatory and Ethics Disclosures

### 1. ICMR 2023 Ethical Guidelines for Biomedical Research Involving AI
* **Autonomy & Human Oversight:** Every clinical decision and prescription alteration requires explicit licensed clinician action. Patients can disable AI help at any time.
* **Accountability:** Every agent execution records full steps, source citations, and Policy Guard inspection results in `agent_runs` and `agent_steps`.
* **Data Minimization:** No patient names or phone numbers are transmitted in stored LLM requests.

### 2. CDSCO Medical Device Software (MDSW) Guidance (July 2026)
* *Notice:* CareLoop is a research and engineering demonstration platform with synthetic data. It is not approved as a medical device under the Medical Devices Rules (MDR 2017).
* Clinical agents perform administrative drafting, document retrieval, and workflow facilitation only. Next steps are restricted to a fixed administrative menu. Rule-based vital-sign alerts could still be considered a monitoring function in a real deployment; seek official regulatory counsel before any clinical use.
