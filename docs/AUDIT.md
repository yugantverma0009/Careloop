# CareLoop Upgrade — Phase 1 Code Audit (AUDIT.md)

**System:** Existing `agentic-ai-nurse` codebase  
**Date:** October 27, 2026  
**Status:** Read-only audit complete. No existing source files in `backend/`, `frontend/`, or `Hardware/` were modified.  
**Core Benchmark Principle:** *"The LLM talks. Rules decide. Humans act."*

---

## 1. Executive Summary

The existing repository (`agentic-ai-nurse`) is a hackathon-level prototype demonstrating an autonomous clinical triage concept. It uses FastAPI, MongoDB, ChromaDB, and React. However, from a DBMS, clinical safety, and architectural perspective, it has fundamental discrepancies between what is documented/claimed in `README.md` and what is actually implemented in code.

Most critically:
1. **Risk decisions are delegated entirely to the LLM:** Gemini classifies urgency and assigns a `risk_score` (1–10) and `action` (`LOG`/`FLAG`/`ALERT`), directly violating the core design rule.
2. **Device telemetry is unauthenticated and partially fabricated:** SpO₂ is generated via `Math.random()` on the frontend; heart rate is streamed via a websocket from an in-memory dictionary; `watch.py` takes `patient_id` directly in the URL without authentication.
3. **Database is MongoDB (NoSQL) with unconstrained schema:** No relational integrity, no foreign keys, no transactions, no stored procedures, and alerts are deleted outright upon acknowledgement rather than transitioned through an audit trail.

---

## 2. Module-by-Module Code Analysis

### 2.1 Backend Modules (`backend/app/`)

| Module | Purpose & Actual Implementation | Key Observations & Flaws |
|---|---|---|
| `main.py` | FastAPI application entry point, routing, auth handlers, WebSockets, background startup. | 1300 lines monolithic file. Contains endpoints for admission, auth, chat, voice, vision, reminders, alerts, dev triggers, and websockets. Lacks structured service separation. |
| `models.py` | Pydantic data schemas: `TaskType`, `PatientStatus`, `ChatRole`, `AlertAction`, `DailyTask`, `Appointment`, `CheckinState`, `PatientProfile`, `ChatEntry`, and request payloads. | Uses Pydantic v2 `model_dump()`. Maps directly to MongoDB documents via `.to_mongo()`. No relational constraints or database check constraints. |
| `agents/recovery_agent.py` | Triage pipeline orchestrator. Runs RAG query via `KnowledgeBase.ask_nurse`, invokes Gemini with `TRIAGE_SYSTEM_PROMPT` to get JSON, normalizes response, maps risk to action (`ALERT` if risk>=8, `FLAG` if risk>=4), then invokes Gemini with `NURSE_RESPONSE_PROMPT`. | **Direct LLM risk decision point.** The LLM assigns `risk_score` (1–10) and category (`CRITICAL`, `MEDICAL_QUESTION`, `ROUTINE_CHECKIN`). Fallback on JSON error uses hardcoded string. |
| `agents/prompts.py` | Contains `TRIAGE_SYSTEM_PROMPT` and `NURSE_RESPONSE_PROMPT`. | Prompts instruct the LLM to act as "Triage Intelligence" and estimate risk score. If critical, tells LLM to advise patient directly. |
| `tools/vision_tool.py` | `WoundVisionTool`: Encodes image to Base64, sends to Gemini 2.5 Flash with prompt evaluating healing status, infection signs (redness, pus), wound closure, and recommendation (`MONITOR`/`FLAG`/`ALERT`). | **Clinical diagnosis by LLM.** Diagnoses infection and wound dehiscence directly from photos. Must be disabled behind a config flag in CareLoop. |
| `tools/voice_tool.py` | `VoiceTool`: Wraps Deepgram SDK for Speech-To-Text (`nova-2`) and Text-To-Speech (`aura-asteria-en`). | Functional for audio conversion, but has no emergency keyword detection on transcripts before passing text to the LLM. |
| `knowledge/ingestion.py` | `MedicalKnowledgeBase`: Extracts text from PDF with `PyPDFLoader`, splits with `RecursiveCharacterTextSplitter`, embeds using local `all-MiniLM-L6-v2` (`HuggingFaceEmbeddings`), persists to ChromaDB per patient (`patient_{patient_id}`). | Collections are isolated per patient, which is good. However, chunk text and vector IDs are not stored in a relational database, and no citation tracking table exists. |
| `knowledge/__init__.py` | `KnowledgeBase`: Thin facade wrapping `MedicalKnowledgeBase`. | Initializes ingestion and provides `ask_nurse(query)`. |
| `utils/scheduler.py` | `BackgroundBrain`: Async polling loop (`asyncio.sleep(60)`). Runs 2 jobs: (1) Morning check-in state machine (3 attempts every 120m then family SMS escalation); (2) Task reminders (matches time ±2m, sends SMS). | Polling loop tied to FastAPI process. Escalation ladder is hardcoded and does not check patient or caregiver consent. |
| `utils/twilio_helper.py` | `TwilioManager`: Sends SMS and alerts using Twilio REST API. Gracefully handles missing credentials. | Works if credentials exist, but alert SMS messages include risk scores and reasons without medical privacy filtering. |
| `utils/firebase_helper.py` | `LogManager`: Firestore logging helper. Connects via `serviceAccountKey.json`. | Logs patient interactions to Firestore collection `patients/{id}/logs`. Redundant second database; sets `alert_triggered = risk_score >= 7`. |

### 2.2 Hardware (`Hardware/watch.py`)

- **Script:** `Hardware/watch.py` (74 lines).
- **Transport:** Connects to serial Bluetooth port (`/dev/cu.AI_Nurse_Watch` at 115200 baud).
- **Protocol:** Expects CSV line: `bpm,fall` (e.g. `78,0` or `110,1`).
- **Telemetry ingestion:** Makes an HTTP POST to `http://localhost:8000/device/vitals/{PATIENT_ID}` with JSON `{"bpm": bpm, "fall_detected": fall}`.
- **Flaws:**
  - `PATIENT_ID` is passed as a CLI argument or input prompt, and embedded in the URL path.
  - Zero device authentication (no API key, header, or signature).
  - No SpO₂ sensor reading is handled or transmitted.
  - No timestamp or quality status is provided by the device (server assigns current UTC time).
  - ESP32 `.ino` firmware source file is missing from the repository (only Python bridge `watch.py` exists).

### 2.3 Frontend Modules (`frontend/src/`)

| File / Component | Purpose | Observations & Flaws |
|---|---|---|
| `App.js` | Top-level routing (`/`, `/patient`, `/nurse`, `/doctor`), theme switcher, system status indicator, header navigation. | Uses React Router v7. Includes "Load Demo Patient" button calling `/nurse/seed-demo-patient`. |
| `components/TriageDashboard.jsx` | Patient portal interface: shows daily tasks, care team, appointments, live vitals, chat window, voice recorder, wound upload modal. | **Fake SpO₂:** Hardcoded `setInterval(() => setOxygen(Math.floor(Math.random() * 3) + 96), 2000)`. Live BPM is read from WebSocket `/ws/vitals/{id}`, which returns `0` if watch is disconnected (violates "never show missing data as 0"). |
| `components/NurseDashboard.jsx` | Admission interface: upload discharge PDF (`/nurse/admit-patient`), patient list, pipeline status poller. | Functional UI for uploading PDFs. Reads list from `/nurse/patients`. |
| `components/DoctorDashboard.jsx` | Doctor alert dashboard: shows list of alerts with risk ring (score/10) and action badge (`ALERT`/`FLAG`/`LOG`). | Acknowledge button makes `DELETE /doctor/alerts/{alert_id}`, which hard-deletes the chat history row from MongoDB instead of transitioning an alert state and creating a follow-up task. |
| `components/Landingpage.jsx` | Marketing landing page detailing system capabilities. | Visual presentation. |
| `components/DevPanel.jsx` | Drawer for triggering test check-ins, simulated escalations, and setting dev parameters. | Hits `/dev/config` and `/dev/trigger`. |
| `services/api.js` | Centralized fetch wrapper. | All endpoints hardcoded or configured via `REACT_APP_API_URL`. Does not send JWT Bearer token on most patient endpoints. |
| `firebase.js` | Client-side Firebase configuration with placeholder values (`YOUR_API_KEY`). | Not actively utilized in the React components (components use `api.js` REST calls). |

---

## 3. Data Models and Storage Audit

### 3.1 Active Database: MongoDB (`nurse_agent_db`)
The current system stores data across 5 MongoDB collections:
1. `patients`: Stores `PatientProfile` documents with embedded arrays (`daily_routine`, `care_team`, `appointments`) and nested objects (`checkin_state`).
2. `chat_history`: Stores `ChatEntry` documents (`patient_id`, `role`, `content`, `risk_score`, `action`, `timestamp`).
3. `hospitals`: Stores registered hospital info and nurse password hashes.
4. `doctors`: Stores doctor accounts and password hashes.
5. `alerts`: Partially used in `seed-demo-patient`; active alerts are actually queried directly from `chat_history` where `risk_score >= 4`.

### 3.2 Vector Database: ChromaDB (`./chroma_db`)
- Created per patient collection `patient_{patient_id}`.
- Chunks stored locally in Chroma, but chunk text and vector IDs are not cross-referenced in any database table.

### 3.3 Firebase Firestore
- `serviceAccountKey.json` initialized in `firebase_helper.py`, writing to collection `patients/{id}/logs`.

---

## 4. API Endpoints Inventory

| Method | Endpoint | Auth Required | Identity Extraction | Vulnerabilities / Issues |
|---|---|---|---|---|
| `POST` | `/hospital/purchase` | None | Body | Generates plain nurse password returned in response. |
| `POST` | `/auth/nurse/login` | None | Body | Returns JWT (`role: nurse`). |
| `POST` | `/auth/patient/access` | None | Body (`patient_id`) | **No password required.** Anyone with a patient ID gets a patient token. |
| `POST` | `/auth/doctor/register` | None | Body | Auto-assigns patients via regex on doctor's last name. |
| `POST` | `/auth/doctor/login` | None | Body | Returns JWT (`role: doctor`). |
| `POST` | `/nurse/admit-patient` | None | Multipart File | Generates `p_<hex>`, parses PDF with Gemini, builds Chroma KB. |
| `GET` | `/nurse/patients` | None | None | Public endpoint returning all patient IDs and statuses. |
| `POST` | `/nurse/seed-demo-patient`| None | None | Overwrites Eleanor Vance demo record. |
| `GET` | `/nurse/patient/{patient_id}/status` | None | URL parameter | Unauthenticated access to pipeline status. |
| `POST` | `/chat` | None | Body (`patient_id`) | **Patient ID taken from body, not JWT.** LLM decides risk score. |
| `POST` | `/chat/voice` | None | Form (`patient_id`) | **Patient ID taken from form.** Deepgram STT -> LLM. |
| `POST` | `/chat/upload-image` | None | Form (`patient_id`) | **Patient ID taken from form.** Gemini vision gives diagnostic action. |
| `POST` | `/trigger-reminder` | None | Body (`patient_id`, `task_id`) | Sends SMS reminder via Twilio. |
| `POST` | `/twilio/webhook` | None | Twilio Form | Updates task completion on SMS keyword. |
| `POST` | `/patient-reply` | None | Body | Marks task complete. |
| `POST` | `/patient/task/complete` | None | Body (`patient_id`) | Marks task complete without auth check. |
| `GET` | `/patient/{patient_id}/personalization` | None | URL parameter | **IDOR vulnerability:** Any caller can read full patient profile. |
| `GET` | `/chat_history/{patient_id}` | None | URL parameter | **IDOR vulnerability:** Any caller can read all chat logs. |
| `GET` | `/doctor/alerts` | Optional Bearer | Header Bearer token | Falls back to returning all ward alerts if doctor has no patients. |
| `DELETE`| `/doctor/alerts/{alert_id}` | Bearer (`role: doctor`) | Header Bearer token | **Destructive hard delete:** Deletes chat message from MongoDB. |
| `GET` | `/dev/config` | None | None | Dev endpoint exposing internal scheduler variables. |
| `POST` | `/dev/config` | None | Body | Mutates scheduler global variables at runtime. |
| `POST` | `/dev/trigger` | None | Body | Manually triggers check-in, escalation, or reminders. |
| `POST` | `/device/vitals/{patient_id}`| None | URL parameter | **Unauthenticated IoT ingestion.** RAM cached; triggers alert on `fall==1`. |
| `WS` | `/ws/vitals/{patient_id}` | None | URL parameter | Streams live BPM from RAM cache or defaults to 0. |

---

## 5. Where the LLM Decides Risk (Violations of Core Rule)

The benchmark rule states: *"The LLM talks. Rules decide. Humans act. LLM output is text only. It must never create flags, change prescriptions, give diagnoses, or advise on doses."*

In the existing codebase, this rule is violated in multiple places:
1. **`backend/app/agents/recovery_agent.py` (lines 96–140):**
   ```python
   # The LLM is prompted with TRIAGE_SYSTEM_PROMPT to output JSON with risk_score (1-10) and category:
   triage_response = (triage_prompt | self.llm).invoke(...)
   # Risk score and category from LLM directly trigger alerts:
   if triage_risk >= 8 or triage_category == "CRITICAL":
       action = "ALERT"
   elif triage_risk >= 4 or triage_category == "MEDICAL_QUESTION":
       action = "FLAG"
   ```
2. **`backend/app/agents/prompts.py` (lines 2–17):**
   The prompt instructs the model: *"You are the Triage Intelligence... Output: category, reasoning, risk_score: 1-10"*.
3. **`backend/app/main.py` (`/doctor/alerts` endpoint, lines 1047–1064):**
   The doctor triage board displays chat rows where `risk_score >= 4`. Thus, which patients the doctor sees as at-risk is decided solely by the LLM output.
4. **`backend/app/tools/vision_tool.py` (lines 20–35 & 87–90):**
   Gemini vision diagnoses whether a surgical wound is healing or infected and recommends `ALERT`, `FLAG`, or `MONITOR`. In `main.py` line 897, `risk` is assigned as 7 (ALERT) or 4 (FLAG) directly from this vision evaluation.

---

## 6. Claimed vs. Actual Feature Verification

| Feature in `README.md` | Status in Code | Actual Reality in Repository |
|---|---|---|
| **Heart rate from wearable** | **Partial** | `watch.py` connects to serial Bluetooth and sends `bpm` to `/device/vitals/{patient_id}`. Ingested into in-memory dictionary `live_vitals`. |
| **SpO₂ (Blood Oxygen)** | **Missing / Fabricated** | Neither `watch.py` nor `main.py` processes SpO₂. In `frontend/src/components/TriageDashboard.jsx` (line 149), SpO₂ is generated with `setInterval(() => setOxygen(Math.floor(Math.random() * 3) + 96), 2000)`. |
| **Fall detection** | **Simulated / Barebones** | `watch.py` reads a 0 or 1 integer from serial Bluetooth. `main.py` sets a 60-second cooldown and logs an emergency chat entry with `risk_score = 10`. No sensor fusion or MPU650 algorithm in code. |
| **Wound image analysis** | **Exists (Over-claim)** | Calls Gemini vision to evaluate wound infection. Over-claims diagnostic capability without clinical validation. |
| **Librosa (audio analysis)** | **Claimed, Not Present** | Mentioned in README tech stack. `grep` reveals zero imports in project code. Deepgram REST API is used instead. |
| **OpenCV (image preprocessing)** | **Claimed, Not Present** | Mentioned in README tech stack. Zero imports in project code. Raw files are uploaded directly to Gemini. |
| **LangChain / LangGraph** | **Partial** | Basic `PromptTemplate` and `ChatGoogleGenerativeAI` from LangChain used. No LangGraph state machine used. |
| **ChromaDB Vector Database** | **Exists** | Used in `ingestion.py` for per-patient collection storage. |
| **Twilio SMS Alerts** | **Exists** | Used in `twilio_helper.py` and `scheduler.py`. |
| **ESP32 Firmware (.ino)** | **Missing** | `README.md` mentions custom ESP32 smartwatch with MAX30102, MPU650, and OLED display. Only `watch.py` (desktop serial bridge) is in the repo. |
| **Hindi / Multilingual Support**| **Missing** | Entire existing codebase is English-only. |
| **Clinician Alert Rules** | **Missing** | No `alert_rules` concept exists. No doctor-approved limits. |
| **Consent-gated Escalation** | **Missing** | Escalation SMS is sent directly to `family_contact` without checking consent. |
| **Audit Log** | **Missing** | No immutable audit table. Alert deletion actually erases clinical history. |

---

## 7. Security, Privacy, and Safety Risk Analysis

1. **Active Secret in `.env`:**
   `backend/.env` line 1 contains an active `GOOGLE_API_KEY` (`AQ.Ab8RN6Kuxk9SqkZ...`). This must be moved out of any committed code and replaced with `.env.example`.
2. **Predictable / Hardcoded JWT Secret:**
   `JWT_SECRET` defaults to `"nurseai-dev-secret-change-in-prod"`.
3. **No Patient Authentication:**
   `POST /auth/patient/access` accepts any `patient_id` string and immediately signs a JWT token with no secret or PIN verification.
4. **Severe IDOR (Insecure Direct Object References):**
   Endpoints such as `GET /patient/{patient_id}/personalization`, `GET /chat_history/{patient_id}`, and `POST /chat` extract `patient_id` from the URL or request body rather than verifying against the authenticated JWT caller claims.
5. **No Input Sanitization / Deterministic Emergency Interception:**
   Patient messages like "severe chest pain" or "I cannot breathe" are forwarded to the LLM to decide triage rather than being intercepted instantly by deterministic emergency keyword rules.
6. **Destructive Acknowledge Workflow:**
   Clicking "Acknowledge" on the doctor dashboard issues a `DELETE` request that purges the record from the database, eliminating the clinical audit trail.
7. **Silence / Disconnection Treated as Normal or Zero:**
   When the wearable disconnects, the frontend displays `BPM: 0` or keeps running with fake oxygen values. Disconnection is not surfaced as a "Missing Data" clinical flag.

---

## 8. Summary of Findings

The existing project has a polished frontend UI and demonstrates the multi-agent vision, but its data tier (MongoDB + in-memory state) and AI logic (LLM deciding medical risk) must be completely restructured to adhere to the CareLoop requirements.

The MySQL database schema in `careloop_mysql_v2_detailed.sql` provides the exact remedy needed:
- 25 normalized tables with strict CHECK constraints, composite foreign keys, and unique keys.
- Triggers and stored procedures that evaluate readings deterministically against clinician-approved `alert_rules`.
- A transaction-backed `sp_acknowledge_flag` that preserves the audit trail.
- True consent gating for caregivers.
- Fully isolated RAG citations stored in `chat_message_sources` and `document_chunks`.

This concludes the Phase 1 Read-Only Audit.
