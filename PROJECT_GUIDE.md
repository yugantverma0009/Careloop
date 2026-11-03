# CareLoop Technical & Clinical Architecture Guide

> [!IMPORTANT]
> **Synthetic-data prototype, not a medical device.**  
> CareLoop is an engineering demonstration platform designed to evaluate post-discharge remote patient monitoring workflows. All patient records, clinical notes, telemetry readings, wound photos, and thresholds are synthetic test data. It is not approved for clinical diagnostic use, does not establish medical diagnoses, and never replaces professional clinical judgment.

---

## Table of Contents
1. [Overview, Positioning & Scope Boundaries](#1-overview-positioning--scope-boundaries)
2. [What CareLoop Adds: Comparison Table](#2-what-careloop-adds-comparison-table)
3. [Architecture Diagram and End-to-End Data Flow](#3-architecture-diagram-and-end-to-end-data-flow)
4. [Technology Stack](#4-technology-stack)
5. [Repository Folder Structure](#5-repository-folder-structure)
6. [Core Services & Capabilities](#6-core-services--capabilities)
   - [6.1 Rounds & Automation Policy](#61-rounds--automation-policy)
   - [6.2 Two-Way SMS & Guided Check-in](#62-two-way-sms--guided-check-in)
   - [6.3 Wound Photo Quality Check & Review](#63-wound-photo-quality-check--review)
   - [6.4 Recovery Plan Drafter & Admission](#64-recovery-plan-drafter--admission)
   - [6.5 Watch Events & Possible Fall Service](#65-watch-events--possible-fall-service)
   - [6.6 Grounded RAG Assistant & Safety Gates](#66-grounded-rag-assistant--safety-gates)
7. [Database Schema, Views, Procedures & Triggers](#7-database-schema-views-procedures--triggers)
8. [Roles, Permissions & Security Matrix](#8-roles-permissions--security-matrix)
9. [Safety Principles & Honesty Boundaries](#9-safety-principles--honesty-boundaries)
10. [Synthetic Demo Cohort & 8-Minute Demo Story](#10-synthetic-demo-cohort--8-minute-demo-story)
11. [Hardware Specifications & IoT Simulator](#11-hardware-specifications--iot-simulator)
12. [Testing Strategy & Test Suites (99 Tests)](#12-testing-strategy--test-suites-99-tests)
13. [Troubleshooting & Verification](#13-troubleshooting--verification)

---

## 1. Overview, Positioning & Scope Boundaries

CareLoop is a post-discharge patient triage and wearable telemetry system designed to prevent the days after hospital discharge from going quiet.

### Governing Philosophies
> **"The LLM talks. Rules decide. Humans act."**  
> **"Automate the routine. Propose the rest. Humans decide."**

* **Positioning:** CareLoop keeps the days after discharge from going quiet: it automates the routine, shows its reason for every alert, answers only from the patient's own papers, and makes sure a person closes every loop.
* **Tagline:** *After discharge, nothing should go quiet.*

### Scope Separation: Core Scope vs Extensions

Per committed project requirements:

* **Core Scope (Committed Baseline):**
  - **Wearable Hardware:** ESP32 DevKit V1, MAX30102 pulse & estimated SpO₂ sensor (I2C SDA 21, SCL 22), MPU-6050 accelerometer/gyroscope, 0.96-inch SSD1306 OLED, tactile push button for SOS, Li-Po battery and charging module.
  - **Device API:** `POST /device/readings` and `POST /device/events` over Wi-Fi with device key authentication.
  - **Relational Storage:** MySQL 8.0+ transactional database (InnoDB) with stored procedures, triggers, views, and integrity constraints.
  - **Rule-Based Triage:** Deterministic SQL triggers evaluate doctor-approved thresholds (`alert_rules`) and raise prioritized flags on breach.
  - **Dashboards & Workstations:** Four role-specialized workstations (Doctor, Nurse, Patient, Family Helper) using BhoomiSetu design tokens and dark/light themes.
  - **Immutable Audit Trail:** Append-only log (`audit_log`) capturing every administrative, clinical, and patient action.
  - **Emergency Keyword Bypass:** Zero-latency plain-code regex matching (English and Hindi) providing direct 112 guidance.

* **Extensions (Additive Capabilities):**
  *(Note: Extensions are built as modular additive capabilities; pending supervisor confirmation before calling extensions formally approved.)*
  - **Ask My Papers Assistant:** Hybrid RAG pipeline (ChromaDB dense vectors + MySQL keyword search) with cited source chips and strict dose modification refusal.
  - **Automated Rounds & Automation Policy:** Background engine executing a transparent 24-hour lookahead for routine actions (quiet hours 22:00–07:00, daily message limits, patient pause, and clinician proposals).
  - **Two-Way SMS Service:** Twilio integration behind `SMS_ENABLED` (logged to database when disabled) supporting patient commands: `1` (dose confirmed), `2` (status check), `3` (urgent callback request), and `STOP`/`START` compliance.
  - **Guided Health Check-in:** Step-by-step check-in wizard with text-to-speech audio guidance, speech-to-text voice input, and instant emergency keyword detection.
  - **Recovery & Wound Photo Quality Check:** Client and server-side deterministic quality evaluation (Laplacian sharpness variance, mean brightness, resolution), EXIF metadata stripping, and nurse side-by-side comparative review.
  - **Recovery Plan Drafter & Patient Admission:** Discharge paper parsing, strict number grounding guard, reconciliation mismatch detection, doctor approval lifecycle, and 7-step nurse patient admission wizard.
  - **Watch Events & Possible Fall Prompts:** Bounded motion event evaluation (*"No text says detected"*), 2-minute patient inquiry prompt (*"Are you OK?"*), and 3 deterministic outcomes (A: I'm OK, B: Need Help, C: Wait time expired $\rightarrow$ Immediate flag).

---

## 2. What CareLoop Adds: Comparison Table

Each row is implemented and verified directly in codebase tests:

| Capability Area | First-Generation "AI Nurse" Concept | CareLoop Post-Discharge Architecture | Proven In Code |
| :--- | :--- | :--- | :--- |
| **Clinical Decision Authority** | LLM evaluates vitals and decides whether to alert doctor or change care plan. | **The LLM never flags.** Deterministic SQL triggers evaluate doctor-approved thresholds. LLM only formats text or drafts notes. | [`database/schema.sql`](file:///Users/yugantverma/Desktop/CareLoop/database/schema.sql), `test_doctor_desk_p3.py` |
| **Image & Wound Inspection** | AI diagnostic model claims to diagnose wound infection or healing stages. | **No AI diagnosis of images.** Deterministic quality check only (blur, brightness, resolution); licensed nurse reviews side-by-side. | [`backend/app/photo_service.py`](file:///Users/yugantverma/Desktop/CareLoop/backend/app/photo_service.py), `test_photo_check.py` |
| **Care Plan Generation** | AI hallucinates recovery guidelines from generic medical training data. | **Grounded strictly in patient papers.** Extracted from patient's own discharge summary with cited passages, number grounding guard, and doctor sign-off. | [`backend/app/plan_service.py`](file:///Users/yugantverma/Desktop/CareLoop/backend/app/plan_service.py), `test_plan_and_admission.py` |
| **Background Automation** | Unmonitored background agents execute unverified actions and messages. | **Transparent Rounds with Safety Policy.** 24-hour visible lookahead, quiet hours (22:00–07:00), daily caps, patient pause, and clinician proposals. | [`backend/app/automation_policy.py`](file:///Users/yugantverma/Desktop/CareLoop/backend/app/automation_policy.py), [`backend/app/rounds.py`](file:///Users/yugantverma/Desktop/CareLoop/backend/app/rounds.py), `test_automation_policy.py` |
| **Fall Handling** | Black-box algorithm makes diagnostic claims without clinical validation. | **Bounded Possible Fall Inquiry.** Watch reports motion shock; asks *"Are you OK?"* with 2-min timer; no unvalidated diagnostic claims. | [`backend/app/device_event_service.py`](file:///Users/yugantverma/Desktop/CareLoop/backend/app/device_event_service.py), `test_watch_events_p5.py` |
| **Telemetry Quality** | Raw sensor readings are displayed blindly, confusing patients with artifacts. | **Headline Quality Filtering.** Plausibility trigger flags impossible spikes (450 bpm) as `Invalid`; only verified readings become headlines. | `trg_sensor_plausibility`, `test_watch_events_p5.py` |
| **Emergency Safety** | Emergency words wait for LLM completion token generation. | **Zero-Latency Bypass.** Plain regex catches emergency keywords (English and Hindi) immediately, giving direct 112 guidance. | [`backend/app/safety.py`](file:///Users/yugantverma/Desktop/CareLoop/backend/app/safety.py), `test_checkin_guide.py` |
| **Patient Privacy & Family** | Family members see sensitive medical details without explicit consent. | **Immediate Consent Cutoff.** When patient flips sharing off, caregiver portal immediately returns HTTP 403. Zero clinical note leakage. | [`backend/app/permissions.py`](file:///Users/yugantverma/Desktop/CareLoop/backend/app/permissions.py), `test_patient_family_p5.py` |

---

## 3. Architecture Diagram and End-to-End Data Flow

```mermaid
flowchart TD
    subgraph EdgeWearable["1. Wearable Watch & Ingestion"]
        ESP32["ESP32 DevKit V1 (MAX30102 + MPU6050)"] -->|POST /device/readings| ReadingAPI["Readings Ingestion"]
        ESP32 -->|POST /device/events| EventAPI["Watch Event Ingestion"]
        ReadingAPI -->|Plausibility Trigger| SensorDB[("sensor_readings")]
        EventAPI -->|Rule Check| FallService["device_event_service"]
    end

    subgraph RelationalEngine["2. MySQL 8.0 Relational Engine & Rules"]
        SensorDB -->|AFTER INSERT| RuleTrigger["trg_sensor_rules_after_insert"]
        RuleTrigger -->|Limit Check| AlertRules[("alert_rules")]
        AlertRules -->|Breach| FlagsDB[("flags (Open)")]
        FlagsDB -->|Escalation Engine| Ladder["4-Tier Escalation Ladder"]
        Ladder --> TaskDB[("follow_up_tasks")]
    end

    subgraph AutomationRounds["3. Background Automation & Policy"]
        Policy["automation_policy (Quiet hours, Caps, Pause)"] --> Rounds["rounds engine (24h lookahead)"]
        Rounds --> ActionsDB[("scheduled_actions")]
        Rounds --> SMS["sms_service (Two-way SMS 1, 2, 3)"]
        Rounds --> ProposalsDB[("rounds_proposals")]
    end

    subgraph ClinicalWorkstations["4. Four Role Workspaces"]
        PatientApp["Patient Portal (/patient)"] <-->|Doses, Guided Check-in, My Plan| API["FastAPI Backend"]
        FamilyApp["Family View (/family)"] <-->|Helped Dose, Consent-gated| API
        NurseDesk["Nurse Workstation (/nurse)"] <-->|Call List, Rounds, Photo Review, Admit| API
        DoctorDesk["Doctor Desk (/doctor)"] <-->|Decisions, Plan Approvals, Limit Approvals| API
    end

    subgraph GroundedIntelligence["5. Grounded RAG & Document Services"]
        DischargeDocs[("discharge_documents")] --> Chunks[("document_chunks + ChromaDB")]
        PatientApp -->|Chat Question| RAG["Hybrid RAG Pipeline"]
        RAG --> Citations["Cited Passage Chips"]
        NurseDesk -->|Draft Plan| PlanService["plan_service"]
        PlanService --> NumberGuard["Number Grounding Guard"]
        NumberGuard --> RecoveryPlans[("recovery_plans")]
        RecoveryPlans -->|Doctor Approval| PatientPlan["Active My Plan"]
    end
```

---

## 4. Technology Stack

| Layer | Component | Version / Library | Purpose in CareLoop |
| :--- | :--- | :--- | :--- |
| **Frontend Framework** | React SPA | `18.2.0` (`react-scripts 5.0.1`) | Responsive web applications for all four roles |
| **Frontend Routing** | React Router | `7.11.0` | Client-side routing with role-based navigation guards |
| **Frontend UI & Tokens** | Tailwind CSS & Icons | `tailwindcss 3.4.17`, `lucide-react 0.562.0` | BhoomiSetu design token styling, dark/light theme |
| **Backend Framework** | FastAPI | `0.128.0` (Starlette TestClient) | REST API endpoints, JWT role enforcement, CORS |
| **ASGI Server** | Uvicorn | `0.34.0` | Asynchronous HTTP server |
| **Database** | MySQL | `8.0.16+` (InnoDB) | Relational store, 35 tables, stored procedures, triggers, views |
| **Database Driver** | PyMySQL | `1.1.1` (DictCursor) | Pure-Python transactional client with session time zone |
| **Vector Store** | ChromaDB | `0.5.23` | Embeddings and dense document chunk retrieval |
| **LLM Provider** | Google GenAI | `google-genai 0.1.1` | Gemini model access with strict offline fallbacks |
| **Two-Way SMS** | Twilio REST API | `twilio 9.0.0+` | Outbound alerts and inbound SMS command handler |
| **Image Processing** | Pillow (PIL) | `Pillow 11.0.0+` | Image resolution verification, EXIF stripping, Laplacian sharpness |
| **Auth & Security** | PyJWT & Bcrypt | `python-jose 3.5.0`, `bcrypt 5.0.0` | HS256 token encoding, secure demo password hashing |
| **IoT Wearable** | ESP32 Arduino C++ | Arduino Core 2.0+ | MAX30102 pulse oximeter & MPU6050 accelerometer firmware |

---

## 5. Repository Folder Structure

```
CareLoop/
├── README.md                           # Quickstart guide, demo credentials, scope, and disclaimer
├── PROJECT_GUIDE.md                    # Single authoritative clinical and technical guide
├── .gitignore                          # Excludes env, dependencies, caches, and local databases
├── .env.example                        # Template environment variables (no secrets)
├── backend/
│   ├── requirements.txt                # Python runtime dependencies
│   ├── uploads/photos/                 # Secure wound photo storage (outside web root)
│   └── app/
│       ├── __init__.py
│       ├── main.py                     # FastAPI application, route mounting, and middleware
│       ├── auth.py                     # JWT token issuance, verification, password hashing
│       ├── db.py                       # PyMySQL connection pool and session context manager
│       ├── permissions.py              # Role dependencies (require_doctor, require_nurse, etc.)
│       ├── automation_policy.py        # Safety gate for automated actions (quiet hours, limits, pause)
│       ├── rounds.py                   # Automated Rounds engine, 24h lookahead, proposal generator
│       ├── sms_service.py              # Outbound SMS dispatcher and inbound command parser (1, 2, 3)
│       ├── checkin_guide.py            # Guided check-in engine, templates, and Hindi voice support
│       ├── photo_service.py            # Image quality evaluator, EXIF stripper, and audit logger
│       ├── plan_service.py             # Recovery plan drafter, number grounding guard, reconciliation
│       ├── admit_service.py            # 7-step nurse patient admission workflow
│       ├── device_event_service.py     # Watch event ingestion, Possible_Fall rule and timeout handler
│       ├── clinical_summaries.py       # SBAR fact-sheet builder, AI drafting, and safety guard
│       ├── escalation.py               # 4-tier escalation ladder state machine
│       ├── governance_interop.py       # HL7 FHIR R4 JSON export and LACE risk calculation
│       ├── llm.py                      # Single resilient Gemini API wrapper with offline fallback
│       ├── rag.py                      # Core RAG functions, emergency terms, dose refusals
│       ├── rag_config.py               # Assistant prompts, refusal templates, intent taxonomy
│       ├── rag_pipeline.py             # Advanced RAG: hybrid search, numeric/citation guards
│       ├── rag_tools.py                # Read-only SQL tools for discharge assistant
│       └── safety.py                   # Plain-code emergency detection and dose check logic
├── database/
│   ├── schema.sql                      # Unified MySQL DDL (35 tables, views, procedures, triggers)
│   └── reset_demo.sql                  # Idempotent demo dataset reset SQL script
├── device/
│   ├── simulator.py                    # Sensor simulator streaming Heart Rate, SpO2, and Fall events
│   ├── watch_bridge.py                 # Serial forwarder to /device/readings
│   └── esp32_careloop/
│       └── esp32_careloop.ino          # ESP32 MAX30102/MPU6050 hardware firmware
├── frontend/
│   ├── package.json                    # Node dependencies and build scripts
│   ├── tailwind.config.js              # Tailwind styling definitions
│   ├── public/
│   │   ├── index.html                  # HTML entry point with web fonts
│   │   └── careloop_logo.jpg           # CareLoop branding logo
│   └── src/
│       ├── index.js                    # React root renderer
│       ├── index.css                   # Global CSS variables, BhoomiSetu tokens, reset rules
│       ├── App.js                      # React router configuration and RoleRouteGuard
│       ├── ThemeContext.js             # Dark and light theme state provider
│       ├── components/                 # Role workspaces and clinical components
│       │   ├── CareLoopLogin.jsx       # Glassmorphism login portal with 1-click role buttons
│       │   ├── CareLoopPatientPortal.jsx # Patient recovery home, check-in, and assistant
│       │   ├── CareLoopStaffPortal.jsx # Staff workstation shell housing Doctor and Nurse views
│       │   ├── PatientOverviewTab.jsx  # Comprehensive clinical chart, Device Health, and timeline
│       │   ├── RoundsView.jsx          # Automated Rounds 24h lookahead and proposals view
│       │   ├── CheckinGuide.jsx        # Step-by-step guided check-in with audio & speech input
│       │   ├── WoundPhotoUpload.jsx    # Patient photo upload modal with quality checker
│       │   ├── PatientMyPlanView.jsx   # Patient active recovery plan view with cited sources
│       │   ├── DoctorLimitsView.jsx    # Doctor limit approvals and Possible Fall counters
│       │   ├── NurseCallListView.jsx   # Nurse priority triage call queue
│       │   ├── FamilyPortal.jsx        # Consent-gated family helper view
│       │   ├── FlagDrawer.jsx          # Clinical flag detail drawer with escalation history
│       │   ├── AuditLogViewer.jsx      # Doctor-only audit log inspection drawer
│       │   ├── Landingpage.jsx         # Public landing page with 4 role cards and real counts
│       │   └── Icons.jsx               # SVG icon primitives
│       └── services/
│           └── api.js                  # Axios/fetch HTTP client with JWT interceptors
├── scripts/
│   ├── reset_demo.py                   # Sub-second reset command runner (< 0.35s)
│   ├── seed_demo.py                    # Synthetic data seeder (18 idempotent steps)
│   ├── validate_demo.py                # 21-check validation suite
│   ├── simulate_event.py               # Live SpO2 91% event simulator
│   └── index_document.py               # Discharge PDF/text chunker and Chroma indexer
└── tests/                              # Complete 99-test pytest acceptance test suite
```

---

## 6. Core Services & Capabilities

### 6.1 Rounds & Automation Policy
* **Engine:** [`backend/app/rounds.py`](file:///Users/yugantverma/Desktop/CareLoop/backend/app/rounds.py) & [`backend/app/automation_policy.py`](file:///Users/yugantverma/Desktop/CareLoop/backend/app/automation_policy.py).
* **Guiding Principle:** *"Automate the routine. Propose the rest. Humans decide."*
* **Safety Gates:**
  1. *Quiet Hours:* 22:00 to 07:00 IST. Routine dose reminders and check-in prompts are silenced; only emergency escalations and possible fall safety inquiries may bypass.
  2. *Message Limits:* At most 2 reminders per scheduled dose. At most 3 automated patient messages per calendar day outside dose reminders.
  3. *Emergency Freeze:* Automated prompts are suspended for any patient with an active open emergency/urgent flag.
  4. *Patient Pause:* Staff can pause automation for a designated patient (`rounds_paused_until` timestamp) with a mandatory clinical reason.
  5. *Patient STOP:* Honored when `sms_opt_out = 1` for SMS transmissions.
  6. *Explicit Reason Required:* Every entry in `scheduled_actions` must carry an explainable reason.
* **Clinician Proposals:** Ambiguous situations (e.g. repeated missed doses, unclear symptom trends, incorrect plan understanding) generate non-self-executing entries in `rounds_proposals` for doctor or nurse review.

### 6.2 Two-Way SMS & Guided Check-in
* **Engine:** [`backend/app/sms_service.py`](file:///Users/yugantverma/Desktop/CareLoop/backend/app/sms_service.py) & [`backend/app/checkin_guide.py`](file:///Users/yugantverma/Desktop/CareLoop/backend/app/checkin_guide.py).
* **Inbound Command Parser:**
  - `1`: Confirms dose taken (matches next scheduled dose within 2 hours; cancels pending reminders; records helped dose if sent by caregiver). If an active fall prompt is awaiting response, confirms *"I'm OK"*.
  - `2`: Returns current regimen status and next scheduled medicine.
  - `3`: Requests urgent callback from Nurse Priya; creates an immediate nurse callback task in `follow_up_tasks`. If an active fall prompt is awaiting response, raises an Immediate flag.
  - `STOP`: Sets `sms_opt_out = 1`, blocking outbound SMS without cutting off app or voice channels.
  - `START`: Re-enables SMS communications.
* **Guided Check-in:** Step-by-step interactive questionnaire (pain rating, symptom chips, trend). Features browser SpeechSynthesis for TTS read-aloud and SpeechRecognition for voice input in English and Hindi. Emergency keywords trigger instant 112 guidance.

### 6.3 Wound Photo Quality Check & Review
* **Engine:** [`backend/app/photo_service.py`](file:///Users/yugantverma/Desktop/CareLoop/backend/app/photo_service.py).
* **Deterministic Quality Gates (No AI Diagnosis):**
  - Resolution: Minimum $480 \times 480$ pixels.
  - Sharpness: Laplacian variance $\ge 65.0$ (blurry images flagged).
  - Brightness: Mean luminance $\ge 40.0$ and $\le 235.0$ (too dark or overexposed images flagged).
  - Clean Metadata: EXIF and GPS tags stripped prior to saving in `uploads/photos/` outside the web root.
* **Nurse Comparative Review:** Priya reviews the photo side-by-side with previous photos, recording structured findings (`No_Concern_Seen`, `Needs_Monitoring`, `Escalated_To_Doctor`).

### 6.4 Recovery Plan Drafter & Admission
* **Engine:** [`backend/app/plan_service.py`](file:///Users/yugantverma/Desktop/CareLoop/backend/app/plan_service.py) & [`backend/app/admit_service.py`](file:///Users/yugantverma/Desktop/CareLoop/backend/app/admit_service.py).
* **Grounding & Reconciliation Guard:**
  - Extracts medication, follow-up, and activity instructions from discharge records.
  - *Number Grounding Guard:* Strict regex check ensures every number (dosages, frequencies, days) is grounded in the source text.
  - *Reconciliation Check:* Compares discharge prescriptions against admission orders; flags mismatches prominently for doctor review.
* **Doctor Approval Lifecycle:** Draft plans (`Draft`) are completely invisible to the patient until Dr. Sharma reviews, verifies cited passages, and clicks **Approve** (`Approved`), automatically superseding previous versions.
* **7-Step Admission Wizard:** Nurse flow for admitting post-discharge patients: Demographics $\rightarrow$ Discharge Document Indexing $\rightarrow$ Prescriptions $\rightarrow$ Alert Rules Setup $\rightarrow$ Device Linking $\rightarrow$ Family Consent $\rightarrow$ Review & Finalize.

### 6.5 Watch Events & Possible Fall Service
* **Engine:** [`backend/app/device_event_service.py`](file:///Users/yugantverma/Desktop/CareLoop/backend/app/device_event_service.py).
* **Honest, Bounded Workflow (*"No text says detected"*):**
  - Evaluates motion spikes ($\ge 2.8g$) followed by prolonged stillness.
  - *Rule Off (Default for Cohort):* Device event is recorded in `device_events` and logged in `audit_log` only; no prompt sent, no flag created.
  - *Rule On (Sunita Rao, Pt 5):* Sends patient inquiry banner and SMS: *"CareLoop check: We noticed sudden movement from your watch. Are you OK?"* with a 2-minute countdown timer.
  - *Outcome A ("✓ I'm OK"):* Event closed, prompt OK counter incremented, timeout action cancelled, no flag.
  - *Outcome B ("🚨 I need help"):* Creates Immediate flag (`source_type = 'Fall'`), initiates 4-tier escalation, opens urgent nurse callback task.
  - *Outcome C (Wait time expired):* Rounds timeout fires, creating Immediate flag: *"Watch reported a possible fall at 14:02. No reply within 2 minutes."*

### 6.6 Grounded Clinical Assistant v2 & Safety Gates
* **Engine:** [`backend/app/rag_pipeline.py`](file:///Users/yugantverma/Desktop/CareLoop/backend/app/rag_pipeline.py), [`backend/app/assistant_router.py`](file:///Users/yugantverma/Desktop/CareLoop/backend/app/assistant_router.py), [`backend/app/patient_updates.py`](file:///Users/yugantverma/Desktop/CareLoop/backend/app/patient_updates.py), & [`backend/app/safety.py`](file:///Users/yugantverma/Desktop/CareLoop/backend/app/safety.py).
* **Guiding Principle:** *"The LLM talks. Rules decide. Humans act."* The LLM produces natural language and proposes actions; deterministic code enforces safety boundaries and only the patient's explicit confirmation triggers actions.

```mermaid
sequenceDiagram
    autonumber
    actor Patient
    participant UI as Patient Portal (React)
    participant Router as Intent Router (Rules-First)
    participant Tools as Read-Only Tools (SQL)
    participant RAG as Hybrid Retrieval (ChromaDB + BM25)
    participant LLM as Google Gemini (12s Timeout)
    participant Staff as Care Team (Nurse & Doctor)

    Patient->>UI: Speaks or types query (EN / HI)
    Note over UI: Emergency keywords checked in interim transcript
    UI->>Router: POST /patient/me/chat
    alt Emergency Intent
        Router-->>UI: Deterministic 112 guidance + Call 112 button (0 LLM calls, 0 sources)
    else Small Talk Intent
        Router-->>UI: Friendly reply with patient name inserted by code (0 LLM calls, 0 sources)
    else Dose Modification Attempt
        Router-->>UI: Refusal + "Ask Care Team" button (0 LLM calls, 0 sources)
    else Tool Query (Medicines, Appointments, Contacts)
        Router->>Tools: Fetch deterministic patient record
        Tools-->>UI: Structured card + "From your care plan" chip
    else Document Question
        Router->>RAG: Hybrid dense vector + keyword search + RRF
        alt Below 0.62 threshold
            RAG-->>UI: "Not in your discharge papers" + Ask Care Team card
        else Above threshold
            RAG->>LLM: JSON prompt with retrieved passages (Patient identity redacted)
            LLM-->>RAG: Structured JSON {found, answer, bullets, source_ids, actions}
            Note over RAG: Numeric guard validates numbers; filters actions to allowlist
            RAG-->>UI: Grounded answer + Section source chips + Action cards
        end
    end
    opt Patient clicks Action Card
        Patient->>UI: Confirms action (e.g. Ask Care Team / Start Checkin)
        UI->>Staff: Dispatches task to Nurse Call List & records audit log
    end
```

* **Core Architectural Components:**
  1. **Rules-First Intent Router:** Evaluates user input deterministically before invoking an LLM.
     - *Emergency Detection:* Evaluates bilingual regex (English and Hindi) across interim speech and final text, presenting emergency guidance and 112 dialing.
     - *Small Talk:* Returns polite greeting/acknowledgment with the patient's first name inserted by application code; zero source chips.
     - *Dose Modification Refusal:* Requests to modify doses or schedules are refused deterministically with an *Ask Care Team* action card (limited to one follow-up task per topic per day).
     - *Read-Only Tools:* Queries regarding daily doses, appointments, medicine plans, latest valid sensor values, and care contacts bypass document chunks and pull directly from SQL endpoints.
  2. **Section-Aware Ingestion & Hybrid RAG:**
     - Discharge summaries are split into section-aware chunks recording `section_title`, `section_type`, and `page_no`.
     - Dense semantic retrieval via ChromaDB multilingual embeddings combined with BM25 keyword matching via Reciprocal Rank Fusion (RRF).
     - 0.62 score threshold downgrades out-of-scope questions to *"That is not in your discharge papers, so I will not guess."*
  3. **Structured Generation & Deterministic Guards:**
     - Strict JSON-only response schema with a 12-second timeout and graceful extractive fallback.
     - *Numeric Grounding Guard:* Verifies that every number, dosage, and date in the response text originates from the cited chunk or tool payload.
     - *Allowlisted Action Cards:* Filters suggested actions to an approved allowlist (`Start_Checkin`, `Add_Photo`, `Request_Call`, `Ask_Care_Team`, `Open_Plan_Item`, `Open_Medicines`, `Add_Appointment_To_Calendar`, `Call_112`, `Open_SOS`).
  4. **Voice Interaction & Privacy Boundary:**
     - Web Speech API integration supporting English (`en-IN`) and Hindi (`hi-IN`).
     - Review-before-send default preview (*"Heard: ..."*) with an optional Hands-Free auto-send toggle.
     - Audio playback via browser `speechSynthesis` with patient preference stored in `patients.voice_autoplay`.
     - Privacy boundary: CareLoop stores only text transcripts; audio streams are never saved or sent to the backend.
  5. **Proactive Updates Inbox (`patient_updates`):**
     - Two-tab Assistant view: *Ask* (chat) and *Updates* (proactive inbox with bell notification indicator).
     - Governed by clinical automation limits: quiet hours (22:00–07:00 IST), emergency flag suppression, maximum 2 reminders per dose, maximum 3 automated messages per day, and audit logging of suppressed notifications.
  6. **Care Team Loop & Audit:**
     - *Nurse Call List:* Dedicated *Patient Assistant Questions* queue with quick clinical reply templates.
     - *Doctor Review:* Dedicated *Assistant Review* audit tab in Clinical Summaries.
     - Full audit logging on every offered and executed action (`ASSISTANT_ACTION_OFFERED`, `ASSISTANT_ACTION_USED`).

---

## 7. Database Schema, Views, Procedures & Triggers

### Relational Entities (37 Tables)
1. **Core Identity & Cohort:** `patients`, `care_staff`, `caregivers`, `user_accounts`, `care_assignments`.
2. **Clinical Records & Prescriptions:** `discharge_records`, `discharge_documents`, `document_chunks`, `prescriptions`, `prescription_times`, `medicines`.
3. **Telemetry & Sensoring:** `devices`, `sensor_readings`, `device_events`.
4. **Safety, Rules & Escalation:** `alert_rules`, `alert_rules_history`, `flags`, `flag_events`, `escalations`.
5. **Execution & Workflows:** `medication_logs`, `symptom_reports`, `symptom_report_tags`, `follow_up_tasks`, `contact_log`, `clinician_notes`, `appointments`.
6. **Automation & Rounds:** `scheduled_actions`, `rounds_proposals`, `sms_messages`, `checkin_templates`, `checkin_sessions`, `checkin_answers`, `patient_updates`.
7. **Photos & Plans:** `wound_photos`, `recovery_plans`, `recovery_plan_items`.
8. **AI & Audit:** `ai_summaries`, `chat_messages`, `chat_message_sources`, `chat_feedback`, `chat_actions`, `risk_context`, `risk_snapshots`, `audit_log`.

### Views (8)
* `v_device_status`: Connectivity status, minutes since last seen, and silence status.
* `v_latest_risk`: Cached composite clinical risk score per patient.
* `v_latest_sensor_readings`: Latest valid physiological readings per metric (ignoring invalid noise).
* `v_medication_adherence`: 7-day adherence percentages across confirmed doses.
* `v_patient_timeline`: Merged chronological stream of vitals, doses, notes, photos, and alerts.
* `v_pending_followups`: Unresolved staff follow-up tasks with priority.
* `v_triage_board`: Open clinical flags sorted by severity and elapsed time.
* `v_worklist_by_patient`: Patient-aggregated worklist with SLA rankings.

### Stored Procedures (16) & Triggers (3)
* `trg_sensor_plausibility`: Marks readings outside physiological limits (HR > 300 bpm or SpO₂ > 100%) as `Invalid`.
* `trg_sensor_rules_after_insert`: Evaluates active rules on valid readings and raises `flags` on threshold breach.
* `trg_symptom_rules_after_insert`: Raises flags for severe pain ($\ge 7$) or emergency terms with 60-min deduplication.
* Standard stored procedures manage atomic transactions for flag acknowledgment, resolution, task completion, daily dose generation, risk snapshot computation, and summary review.

---

## 8. Roles, Permissions & Security Matrix

| Feature / Endpoint | Doctor (Dr. Ananya Sharma) | Nurse (Priya Nair) | Patient (Aarav Patel) | Family Helper (Neha Patel) |
| :--- | :---: | :---: | :---: | :---: |
| **Landing Workspace** | `/staff/doctor/decisions` | `/staff/nurse/call-list` | `/patient` | `/family` |
| **Needs My Decision Queue** | **Yes** | No (HTTP 403) | No | No |
| **My Call List & Triage** | Yes | **Yes** | No | No |
| **Automated Rounds View** | Yes | **Yes** | No | No |
| **Start Follow-Up (Admission)** | Yes | **Yes** | No | No |
| **Resolve Routine Flags** | Yes | Yes | No | No |
| **Resolve Urgent / Fall Flags** | **Yes** | No (Escalates to Doctor) | No | No |
| **Approve / Reject Recovery Plans** | **Yes** | No (HTTP 403) | No | No |
| **Approve / Reject AI Summaries** | **Yes** | No (HTTP 403) | No | No |
| **Approve Alert Limits** | **Yes** | No (Can Propose only) | No | No |
| **Audit Log Inspection** | **Yes** | No (HTTP 403) | No | No |
| **HL7 FHIR R4 Bundle Export** | **Yes** | No (HTTP 403) | No | No |
| **Mark Dose Taken / 5-min Undo** | No | No | **Yes** | Yes (Helped dose) |
| **Guided Check-in (Voice/TTS)** | No | No | **Yes** | No |
| **Wound Photo Upload** | No | No | **Yes** | No (HTTP 403) |
| **Wound Photo Review** | Yes | **Yes** | No | No |
| **Ask My Papers Assistant** | No | No | **Yes** | No (HTTP 403) |
| **Toggle Family Consent** | No | No | **Yes (Live switch)** | No |
| **See Clinical Notes / Free-Text** | Yes | Yes | Yes | **No (Zero leakage)** |

---

## 9. Safety Principles & Honesty Boundaries

1. **No Medical Thresholds in Code:** Alert limits come only from doctor-approved records in `alert_rules`.
2. **Valid Readings as Headline:** The headline reading in the patient and staff portals is always the latest `Valid` reading. Spurious telemetry (e.g. 450 bpm) is tagged `Invalid` and surfaced as a clean data check note.
3. **Emergency Bypass:** Detection of life-threatening symptoms never waits for LLM responses. Plain regex pattern matching routes patients directly to emergency guidance.
4. **Immediate Consent Cutoff:** When a patient toggles family sharing off, caregiver access is revoked immediately across all queries.
5. **No Unprovable Claims:** Interface and documentation completely prohibit unprovable marketing claims (*"guarantees recovery"*, *"100% accurate"*, *"hardware-verified"*, *"AI detected"*).
6. **No Automated Prescribing:** The system never alters medication dosages or clinical plans without human clinician sign-off.

---

## 10. Synthetic Demo Cohort & 8-Minute Demo Story

### The 5 Synthetic Demo Patients
1. **Aarav Patel (Day 3 Post-CABG):** Baseline candidate. Valid headline vitals (74 bpm, 98% SpO₂), invalid 450 bpm spike ignored, family sharing active. Target of live SpO₂ event simulation.
2. **Meera Sharma (Day 6 Heart Failure):** Open `Review_Soon` flag: silent telemetry device (>24h without data). Family consent revoked by patient.
3. **Rajesh Verma (Day 5 Acute MI):** Open `Urgent_Review` flag: acute emergency symptom check-in (chest pressure) with nurse call task.
4. **Kabir Mehta (Day 9 Valve Replacement):** Historical candidate: resolved flag with full audit history, approved summary ready.
5. **Sunita Rao (Day 4 Post-PCI Stenting):** Open `Review_Soon` flag: two consecutive missed medication doses with pending nurse call task. Possible Fall rule enabled.

### The 8-Minute Connected Demo Script

| Time | Persona | Action & Demonstration Steps | Key Message to Judges |
| :--- | :--- | :--- | :--- |
| **0:00** | **Landing Page** | Show the 4 role cards with distinct accents and positioning: *"CareLoop keeps the days after discharge from going quiet."* | Role-based separation of concerns. |
| **0:30** | **Nurse $\rightarrow$ Rounds** | Opens Rounds: inspects 24-hour lookahead table (*"What CareLoop will do next, and why"*). Shows due reminders and silence checks. | Automation you can see; every action has a reason. |
| **1:15** | **Patient (Aarav)** | Reviews **My Plan** with cited discharge passages $\rightarrow$ starts Guided Check-in with TTS read-aloud and voice $\rightarrow$ uploads recovery photo with quality check. | Papers-first recovery, voice access, and image quality gates. |
| **2:30** | **SMS Simulator** | Demonstrates basic-phone interaction: sends inbound SMS `1` (dose confirmed) and `3` (urgent callback). | Accessible to patients without smartphones. |
| **3:00** | **Nurse (Priya)** | My Call List displays callback request $\rightarrow$ Photos to Review shows photo side-by-side with baseline $\rightarrow$ records *"No concern seen"*. | Human clinicians review images; no AI diagnosis. |
| **3:45** | **Presenter** | Triggers simulated low SpO₂ reading (91% < 94%) for Aarav. | Wearable telemetry streams into the SQL rules engine. |
| **4:00** | **Patient & Family** | Aarav receives calm guidance banner; Neha receives SMS notice with Aarav's explicit consent. | Calm patient guidance; family helper informed with consent. |
| **4:30** | **Nurse $\rightarrow$ Doctor** | Priya logs call, clicks **Ask Doctor** $\rightarrow$ Dr. Sharma inspects escalation evidence and resolves flag. | Clinicians close the loop; full human oversight. |
| **5:15** | **Doctor (Dr. Sharma)** | Opens Approvals $\rightarrow$ reviews drafted recovery plan with reconciliation mismatch warning $\rightarrow$ **Approves** $\rightarrow$ signs clinical summary. | AI drafts from papers; doctor reviews and approves. |
| **6:15** | **Presenter** | Simulates possible fall for Sunita (Pt 5) $\rightarrow$ patient prompt appears $\rightarrow$ timer expires $\rightarrow$ Immediate flag and escalation ladder start. | Bounded fall prompt; no unvalidated detection claims. |
| **7:00** | **Nurse $\rightarrow$ Admit** | Walks through 7-step admission wizard: document indexed, doctor limits configured, welcome call scheduled. | Onboarding is a structured clinical flow. |
| **7:30** | **Doctor $\rightarrow$ Audit** | Inspects append-only audit trail verifying every automated and human action with timestamps and reasons. | Complete verifiable accountability. |
| **7:50** | **Conclusion** | Recite core principle: *"Automates the routine. Proposes the rest. Humans decide."* | Engineering rigor and safety boundaries. |

---

## 11. Hardware Specifications & IoT Simulator

### Hardware Specifications
* **Microcontroller:** ESP32 DevKit V1 (30-pin, dual-core Tensilica Xtensa 32-bit LX6).
* **Sensors:**
  - MAX30102 via $I^2C$ (SDA: GPIO 21, SCL: GPIO 22) measuring optical PPG for Heart Rate (bpm) and estimated SpO₂ (%).
  - MPU-6050 Accelerometer/Gyroscope for motion spike analysis ($\sqrt{x^2+y^2+z^2} \ge 2.8g$).
* **Local Display:** SSD1306 0.96" OLED ($I^2C$ address `0x3C`).
* **Hardware SOS:** Tactile momentary push button pulling GPIO down to GND.
* **Firmware:** Located in `device/esp32_careloop/esp32_careloop.ino`.

### Software Telemetry Simulator
The Python simulator (`device/simulator.py`) generates physiological telemetry and event shock profiles:
```bash
# Continuous physiological telemetry streaming every 10 seconds
python3 device/simulator.py --interval 10

# Single low SpO2 breach cycle (89-91%) for alert testing
python3 device/simulator.py --low-spo2 --once

# Simulate motion spike followed by stillness (Possible Fall event)
python3 device/simulator.py --device DEV-ESP32-005 --fall
```

---

## 12. Testing Strategy & Test Suites (99 Tests)

CareLoop enforces regression prevention through 11 test suites comprising 99 safety-critical tests:

```bash
PYTHONPATH=. ./backend/env/bin/pytest tests/ -v
```

1. **`test_automation_policy.py` (11 tests):** Quiet hours enforcement (22:00–07:00), daily patient message caps, dose reminder limits, patient pause honor, open emergency freeze, and mandatory explicit reasons.
2. **`test_checkin_guide.py` (5 tests):** Active template loading, nurse approval prohibition (doctor-only), instant emergency keyword trigger during check-in, routine completion, and template approval lifecycle.
3. **`test_two_way_sms.py` (7 tests):** Inbound SMS commands (`1` dose confirmed, `3` urgent callback), `STOP`/`START` opt-out lifecycle, emergency keyword interception, unknown phone number handling, and Twilio webhook integration.
4. **`test_photo_check.py` (7 tests):** Four deterministic quality cases (good, dark, blurry, low resolution), EXIF metadata removal, caregiver HTTP 403 access denial, patient cross-identity isolation, view audit logging, and nurse review workflow.
5. **`test_plan_and_admission.py` (9 tests):** Section detection, number grounding guard (rejection of invented dosages), reconciliation mismatch detection, patient draft invisibility, doctor approval lifecycle, understanding check feedback proposal, and 7-step nurse admission flow.
6. **`test_watch_events_p5.py` (9 tests):** Device key authentication, Rule OFF audit logging only, Rule ON prompt dispatch and 2-min countdown timer, Outcome A (I'm OK), Outcome B (Need Help $\rightarrow$ Immediate flag), Outcome C (Timeout $\rightarrow$ Immediate flag), inbound SMS fall prompt resolution, device health reporting, and zero "detected" wording leakage.
7. **`test_role_permissions_p2.py` (14 tests):** Role boundary HTTP 403 enforcement, token IDOR binding, family consent toggle cutoff, and nurse vs doctor flag authority.
8. **`test_doctor_desk_p3.py` (7 tests):** Doctor decision queue, AI summary approval/rejection, limit proposals, and HL7 FHIR R4 JSON export.
9. **`test_nurse_desk_p4.py` (7 tests):** Nurse call list queue, contact call logging, task completion with outcome codes, and shift handoffs.
10. **`test_patient_family_p5.py` (9 tests):** Patient daily regimen, 5-minute undo, check-in emergency detection, grounded RAG citations, and family zero-leakage view.
11. **`test_connected_demo_p6.py` (5 tests):** Sub-second database reset contract, live SpO₂ drop event simulation, and landing page claims clean audit.
12. **`test_phase7_acceptance.py` (9 tests):** Offline LLM resilience (deterministic tool fallbacks, extractive chunk grounding, SBAR draft fallback), English/Hindi 112 emergency bypass, and headline vital filtering (ignoring 450 bpm).

---

## 13. Troubleshooting & Verification

| Problem | Root Cause | Resolution |
| :--- | :--- | :--- |
| Database connection error (`1045 Access Denied`) | Credentials mismatch in `.env` | Ensure `.env` has `DB_USER=careloop_api` and `DB_PASSWORD=careloop_dev_pass`. |
| Flag count mismatch after testing | Transactional tests modified flags | Run `./backend/env/bin/python scripts/reset_demo.py` (< 0.35s) to restore clean baseline. |
| AI Assistant returns fallback note | LLM API key missing or unreachable | Verify `GOOGLE_API_KEY` in `.env`. System operates safely in deterministic extractive fallback mode when offline. |
| Port 8000 or 3000 already in use | Stale background process | Kill process: `lsof -ti:8000,3000 \| xargs kill -9`. |
| Device event returns 401 | Missing or incorrect device key | Include `X-Device-Key: demo-device-key-change-me` in request headers. |
