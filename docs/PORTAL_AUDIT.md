# CareLoop Patient Portal Audit (Phase 0)

> **Document Purpose:** Complete read-only audit of the CareLoop Patient Portal as of October 2026. This document captures how patient pages, backend endpoints, state handling, i18n, and RAG/chat currently work in real code, maps all data shapes, and identifies every gap against `careloop_patient_portal_upgrade_brief.md`.

---

## 1. Executive Summary

The existing CareLoop patient portal is a functional single-page React application (`CareLoopPatientPortal.jsx`) communicating with a FastAPI backend (`backend/app/main.py`) powered by a MySQL 8.0 database (`careloop_mysql_v2_detailed.sql`) and a Chroma vector store (`backend/app/rag.py`).

While the core safety invariants (deterministic emergency guidance, dose change refusal, JWT-based patient isolation, audit logging) are implemented and passing unit tests, the patient experience suffers from major usability and clinical honesty issues:
1. **Misleading Per-Dose Percentage Bars:** Each single dose displays a `100%` or `0%` progress bar, which is clinically illogical.
2. **Permanent Red Emergency Banner:** The top alert banner renders red whenever any flag exists, causing alarm fatigue even for routine review items.
3. **No Distinction Between Patient-Skipped and System-Missed Doses:** System "Missed" doses appear identical to voluntary patient skips, and patients cannot undo mis-taps.
4. **Weak RAG Assistant:** Chat attempts to answer deterministic database questions (e.g., "When is my next appointment?") from unstructured text chunks instead of structured SQL queries, frequently triggering "Not found" fallbacks. Answers lack source inspection and citation chips.
5. **No Calendar View:** Patients have no visual overview of past dose adherence or future scheduled visits.
6. **Crude Symptom Check-in:** The check-in form consists only of an HTML range slider (0–10) and a plain textarea without quick symptom chips, pain location tags, or history charts.

---

## 2. Current Architecture & Implementation

### 2.1 Frontend Structure (`CareLoopPatientPortal.jsx`)
- **Technology:** React (Create React App), inline JSX styles, CSS variables from `frontend/src/index.css`.
- **State Management:**
  - `statusData`: Vitals, device status, active clinical flags, next appointment.
  - `doses`: Array of today's scheduled doses.
  - `chatMessages`: Array of chat turns (`{ role, content, grounded, timestamp }`).
  - `activeNav`: Active navigation tab (`'recovery'`, `'prescriptions'`, `'checkin'`, `'chat'`).
  - `lang`: Language state (`'en'` | `'hi'`).
  - Polling: Auto-refreshes via `setInterval(loadAll, 10000)` (every 10 seconds).
- **Navigation Tabs:**
  - `recovery`: Overview dashboard containing 4 KPI stat cards, progress meters, safeguard attention card, and dose register table.
  - `prescriptions`: Duplicates the same dose table as the overview.
  - `checkin`: 0–10 pain slider + textarea.
  - `chat`: Basic chat box with AI Nurse.
  - *Missing:* `My calendar` tab does not exist.

### 2.2 Backend Endpoints & Current Data Shapes

#### 1. `GET /patient/me/status`
- **Authentication:** JWT Bearer token (`get_effective_patient_id(user)`).
- **Current Response Shape:**
```json
{
  "readings": [
    {
      "measurement_type": "Heart_Rate",
      "measurement_value": 72.0,
      "unit": "bpm",
      "measured_at": "2026-10-20 09:15:00",
      "quality_status": "Valid"
    }
  ],
  "devices": [
    {
      "device_id": "DEV-001",
      "device_type": "Smartwatch",
      "connectivity_status": "Online",
      "last_seen_at": "2026-10-20 09:15:00"
    }
  ],
  "next_appointment": {
    "appointment_id": 1,
    "appointment_date": "2026-10-23 10:00:00",
    "appointment_type": "Cardiology_FollowUp",
    "status": "Scheduled",
    "doctor_name": "Dr. Ananya Sharma"
  },
  "active_flags": [
    {
      "flag_id": 101,
      "severity": "Urgent_Review",
      "source_type": "Emergency",
      "reason": "Patient report matched emergency keyword",
      "created_at": "2026-10-20 09:20:00"
    }
  ]
}
```

#### 2. `GET /patient/me/doses`
- **Functionality:** Calls `sp_generate_daily_doses(CURDATE())` and queries `medication_logs` for `CURDATE()`.
- **Current Response Shape:**
```json
[
  {
    "medication_log_id": 12,
    "medicine_name": "Demo Medicine A",
    "dose_instructions": "Take with water after breakfast",
    "scheduled_for": "2026-10-20 08:00:00",
    "status": "Unconfirmed",
    "reminder_sent_at": null,
    "recorded_at": null,
    "patient_note": null
  }
]
```

#### 3. `POST /patient/me/doses/{log_id}/confirm`
- **Request Body:** `{ "status": "Taken_Confirmed" | "Skipped", "patient_note": "..." }`
- **Current Deficiencies:**
  - No 60-minute early restriction (allows confirming doses hours or days before scheduled time).
  - No 5-minute undo mechanism.
  - No reason taxonomy for skips (only optional freeform text note).
  - Does not distinguish between user "Skipped" and system "Missed".

#### 4. `POST /patient/me/symptoms`
- **Request Body:** `{ "text": "...", "pain_level": 2, "input_method": "Text", "language": "en" }`
- **Current Response Shape:**
```json
{
  "status": "recorded",
  "report_id": 45,
  "emergency": false,
  "guidance": null
}
```
- **Current Deficiencies:**
  - Lacks symptom chips, anatomical location chips (`site:*`), and trend tags (`trend:*`).
  - Lacks duplicate submission protection within 60 seconds.
  - Lacks microphone / Web Speech API integration.

#### 5. `POST /patient/me/chat` & `GET /patient/me/chat/history`
- **Request Body:** `{ "message": "...", "language": "en" }`
- **Current Response Shape:**
```json
{
  "response": "From your discharge summary: Follow-up visit with Dr. Ananya Sharma is due on 23 October 2026.",
  "is_grounded": true,
  "citations": ["chroma-1-0"]
}
```
- **Current Deficiencies:**
  - Flat response without structured bullets, source chip metadata (section, page), or follow-up suggestions.
  - Vector search returns fixed raw strings without section headings or page numbers.
  - No tool execution for structured facts (appointments, prescriptions).
  - No numeric verification guard (`numbers_in` post-check).
  - No user feedback endpoint (👍/👎).

### 2.3 Internationalization (i18n) Status
- Currently, i18n is handled entirely through ad-hoc ternary expressions inside JSX (e.g., `lang === 'hi' ? 'हाँ' : 'Yes'`).
- There are no centralized dictionary files (`en.json` / `hi.json`) or structured translation keys.
- Several error messages and button labels are hardcoded in English.

---

## 3. Gap Analysis: Code Reality vs. Upgrade Brief

| Specification Area | Upgrade Brief Requirement | Current Code Implementation | Gap Severity |
|---|---|---|---|
| **Overview Single Call** (Sec 8.1) | Single aggregated endpoint `GET /patient/me/today` | Front-end fires 3 separate endpoints (`/status`, `/doses`, `/chat/history`) | High (P0) |
| **Dose Grouping** (Sec 6.2) | Group doses by Morning (<12:00), Afternoon (12-17), Evening (17-21), Night (>=21) | Flat unsorted table ordered strictly by timestamp | High (P0) |
| **Dose Progress Meter** (Sec 6.1) | Single day summary "N of M taken" with dot indicators; remove single-dose % bars | Each single dose has a `100%` or `0%` progress bar | High (P0) |
| **Dose Action Controls** (Sec 6.2) | One-tap Taken; 5-min Undo; Skip sheet with reasons; block >60 min early | "Mark Taken" button only; no Undo; no Skip modal; no early-window check | High (P0) |
| **Calendar Tab** (Sec 6.3) | New `My calendar` page with month grid, markers, day sheet, `.ics` export | Completely missing from portal | High (P0) |
| **Status Banner** (Sec 6.5) | 4 real states: `none`, `review`, `urgent`, `seen` | Statically shows red urgent banner if any flag exists | High (P0) |
| **Check-in Form** (Sec 6.4) | 0–10 number buttons, quick symptom chips, location chips, trend, mic voice, 14-day chart | 0–10 slider + textarea only; no chips, no voice, no history | High (P0) |
| **RAG Tool Routing** (Sec 7.4) | Intent routing to read-only SQL tools for appointments, today's doses, plan, vitals | All questions routed to Chroma vector search; fails on appointment queries | High (P0) |
| **RAG Ingestion** (Sec 7.3) | Chunks store `section_title`, `section_type`, `page_no`; multilingual embeddings | Chunks are raw synthetic text in SQL without metadata | High (P0) |
| **RAG Numeric Guard** (Sec 7.8) | Mandatory post-generation regex guard verifying all numbers exist in context | Completely missing; relies solely on prompt instruction | Critical (Safety) |
| **Chat UI & Citations** (Sec 7.10) | Interactive source chips opening source inspection panel; 👍/👎 feedback | Plain chat bubble without clickable sources or feedback | High (P0) |
| **Evaluation Harness** (Sec 7.11) | `rag_eval/` with `golden.jsonl` (40-60 items) + automated evaluation script | Missing | High (P0) |
| **Database Additions** (Sec 9.2) | Columns on `document_chunks`, `chat_messages`, new `chat_feedback` table | Missing columns and table | Medium (P1) |
| **Emergency Duplicates** (Sec 9.3) | Trigger deduplicating emergency flags within 60-min window | Creates a new flag on every emergency report | Pending Approval |

---

## 4. Plan Checklist & Milestones Mapping

To systematically close every gap without violating the style lock or breaking existing staff/login functionality, the work is partitioned into 5 strictly gated phases:

- **Phase 0 (Current):** Read-only Audit (`PORTAL_AUDIT.md`), Style Lock (`STYLE_LOCK.md`), Baseline Screenshots, Phase 1 Plan.
- **Phase 1: Overview, Doses, Banner & Error States (Sections 6.1, 6.2, 6.5, 6.9, 8.1, 8.2)**
  - Implement `GET /patient/me/today` returning aggregated day state, grouped doses, relative times ("In 1 hr", "Due now"), and dynamic banner state.
  - Implement `POST /patient/me/doses/{id}/taken`, `/skip`, `/undo` with 60-min early guard, 5-min undo, and audit logging.
  - Update Overview UI: single "Today: 2 of 6 taken" card, Next Medicine card, remove per-dose percentage bars.
- **Phase 2: Calendar & Plan Checklist (Sections 6.3, 6.6, 6.8, 8.3, 8.5)**
  - Implement `GET /patient/me/calendar?month=YYYY-MM`, `GET /patient/me/day`, and `GET /patient/me/appointments/{id}.ics`.
  - Add `My calendar` tab with month grid, day sheet drawer, and `.ics` download.
  - Add factual Plan Checklist card to Overview.
- **Phase 3: Pain & Daily Check-in Upgrade (Sections 6.4, 8.4, 9.3)**
  - Rebuild Check-in: 0–10 number buttons, symptom chips, location chips, trend chips, optional Web Speech API mic.
  - 14-day history chart/list.
  - Duplicate check-in protection within 60s.
  - Apply emergency duplicate trigger fix (upon user approval).
- **Phase 4: Grounded RAG Assistant Upgrade (Section 7, 8.6, 9.2)**
  - Apply additive database migrations (`document_chunks` columns, `chat_feedback` table).
  - Implement intent router & read-only SQL tools (`get_next_appointment`, `get_today_doses`, `get_medicine_plan`, `get_latest_readings`).
  - Implement multilingual hybrid retrieval, structured answer generator, numeric/citation guard.
  - Chat UI with source chips, drawer preview, and feedback.
  - Build `rag_eval/` golden test set and runner.
- **Phase 5: Polish & Handover (Sections 10, 11, 13)**
  - Full Hindi verification, keyboard accessibility (WCAG AA), demo walkthrough, documentation.
