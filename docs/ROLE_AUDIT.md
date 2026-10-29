# CareLoop — Comprehensive Role & Access Audit

**Audit Date:** 2026-10-30  
**Audit Target:** CareLoop multi-role clinical post-discharge platform  
**Governing Principle:** *"The LLM talks. Rules decide. Humans act."*

---

## 1. Executive Summary

This audit assesses the current state of role separation, navigation boundaries, page exposure, API endpoint mappings, and backend authorization across all four intended user logins:
1. **Attending Doctor** (`Dr. Ananya Sharma`)
2. **Triage Nurse** (`Priya Nair`)
3. **Recovering Patient** (`Aarav Patel`)
4. **Family Helper / Caregiver** (`Neha Patel`)

### Key Vulnerabilities & Overlaps Identified

| # | Role Pair | Current State | Issue & Violation |
|---|---|---|---|
| **1** | **Doctor vs. Nurse** | Both route to `<CareLoopStaffPortal />`. Both see identical 8 sidebar items. | No distinction between clinical decision-maker and triage/call nurse. Nurse can approve AI summaries, change rules, and view audit logs. |
| **2** | **Patient vs. Family** | Both route to `<CareLoopPatientPortal />`. Both see identical 5 tabs and greeting ("Hi Aarav Patel"). | Family helper has full access to patient chat, discharge records, and clinical check-in logs without any functional difference. |
| **3** | **Backend Authorization** | Endpoints are grouped strictly into two coarse buckets: `require_role("Doctor", "Nurse")` and `require_role("Patient", "Caregiver")`. | Zero server-side enforcement distinguishing Doctor from Nurse, or Patient from Family Helper. |
| **4** | **Data Clutter** | Database holds 10 patients, 190 flags (84 open), 179 tasks, 53 summaries, and 1,943 audit logs. | Synthetic seed is bloated with outdated mock scripts, duplicate tasks, and conflicting demo days. |

---

## 2. Detailed Role Mapping: Current vs. Target

### 2.1 Doctor Login (`Dr. Ananya Sharma` · `ananya.demo@example.test`)

* **Current Greeting / Subtitle:** "Care team hub" · "Who needs attention"
* **Target Kicker & Title:** `DOCTOR DESK` · **Needs my decision**
* **Role Verb:** **Decide** (decide clinical escalations, approve AI summaries, approve threshold limits)
* **Accent Token:** Purple (`#7c3aed`, Soft: `#f5f3ff`, Dark: `rgba(124, 58, 237, 0.15)`)

#### Current Sidebar & Views:
1. `triage` — "Who needs attention" (Grouped worklist of all patients)
2. `patients` — "Patient directory"
3. `timeline` — "Patient timeline"
4. `tasks` — "Follow-up tasks" (Queue of 179 tasks)
5. `summaries` — "Draft summaries" (Review & approve AI summaries)
6. `handoff` — "Shift handoff" (I-PASS handoff cards)
7. `insights` — "Operational insights" (Cohort metrics)
8. `audit` — "Audit log viewer"

#### Target Sidebar & Views (Phase 3):
1. **Needs my decision** (Home) — 4 decision KPIs (*Needs decision now*, *Summaries to approve*, *Limit change requests*, *Patients in follow-up*), short decision queue (Rajesh emergency, nurse-escalated items), "Quiet patients: 2 (nothing open)" indicator.
2. **Patients** — Merged Patient Directory + Overview + Timeline + Notes + Limits tabs.
3. **Approvals** — Unified review station for AI summaries (with deterministic Fact Sheet sources) and limit change proposals.
4. **Patient limits** — Doctor-approved thresholds per patient (`alert_rules`).
5. **More (Dropdown/Section)** — Simplified Audit Log (last 20 events) and FHIR R4 JSON Export.
*(Hidden: Standalone LACE panel, Pathway templates, Standalone Operational insights page, redundant second notification bell).*

#### Endpoints Called & Server Checks:
- `GET /staff/worklist` → `require_role("Doctor", "Nurse")`
- `GET /staff/patients` → `require_role("Doctor", "Nurse")`
- `GET /staff/patients/{id}/timeline` → `require_role("Doctor", "Nurse")`
- `GET /staff/follow-ups` → `require_role("Doctor", "Nurse")`
- `POST /staff/follow-ups/{id}/resolve` → `require_role("Doctor", "Nurse")`
- `GET /staff/summaries/pending` → `require_role("Doctor", "Nurse")`
- `POST /staff/summaries/{id}/approve` → `require_role("Doctor", "Nurse")` *(Target: Doctor only)*
- `POST /staff/summaries/{id}/reject` → `require_role("Doctor", "Nurse")` *(Target: Doctor only)*
- `GET /staff/audit-log` → `require_role("Doctor", "Nurse")` *(Target: Doctor only)*
- `POST /governance/fhir/export` → `require_role("Doctor", "Nurse")` *(Target: Doctor only)*
- `PUT /governance/rules/{id}` → `require_role("Doctor", "Nurse")` *(Target: Doctor only)*

---

### 2.2 Nurse Login (`Priya Nair` · `priya.demo@example.test`)

* **Current Greeting / Subtitle:** "Care team hub" · "Who needs attention" *(Identical to Doctor)*
* **Target Kicker & Title:** `NURSE DESK` · **My call list**
* **Role Verb:** **Watch and call** (work queue, acknowledge, log calls, resolve routine items, escalate to doctor)
* **Accent Token:** Blue (`#0284c7`, Soft: `#eff6ff`, Dark: `rgba(56, 189, 248, 0.15)`)

#### Current Sidebar & Views:
* Exactly identical to Doctor (all 8 items shown above).

#### Target Sidebar & Views (Phase 4):
1. **My call list** (Home) — Queue ordered by urgency and age. Actions per row: **Call** (log dialog), **Acknowledge**, **Ask doctor** (escalate), **Done**. Clear indicator: "Needs doctor to resolve" for urgent/immediate flags. Includes "Calls due today" strip.
2. **Patients** — Patient directory and overview (read-only limits, no audit log, no approvals).
3. **Handoff** — Simplified I-PASS shift handoff report authored by Nurse; at most 5 lines per patient, no invented thresholds.
*(Removed from Nurse: Draft summaries, Operational insights, Audit log viewer, Follow-up tasks page).*

#### Endpoints Called & Server Checks:
- Currently shares all Doctor endpoints without restriction.
- Target Server-side Permissions:
  * May call: `GET /nurse/call-list`, `POST /flags/{id}/acknowledge`, `POST /flags/{id}/escalate-doctor`, `POST /staff/calls/log`, `POST /staff/handoff`, `POST /rules/propose-limit`.
  * **Forbidden (403):** `approve summary`, `approve limit`, `audit log`, `export FHIR`.
  * **Flag resolution rule:** Nurse can resolve routine/review-soon flags; cannot resolve urgent/immediate flags without Doctor.

---

### 2.3 Patient Login (`Aarav Patel` · `aarav.demo@example.test`)

* **Current Greeting / Subtitle:** "Recovery portal" · "Hi Aarav Patel"
* **Target Kicker & Title:** `MY RECOVERY` · **Hi Aarav**
* **Role Verb:** **Do** (take medicines, report check-ins, review schedule, consult discharge assistant)
* **Accent Token:** Teal (`#0d9488`, Soft: `#ecfdf5`, Dark: `rgba(20, 184, 166, 0.15)`)

#### Current Tabs & Views:
1. `recovery` — Today's Regimen, Telemetry card, Care Team contacts.
2. `prescriptions` — Full list of prescriptions and doses.
3. `calendar` — Interactive month grid, Day Sheet drawer, .ics / Google Calendar links.
4. `checkin` — 0-10 numeric pain slider, symptom chips, location chips, trend picker, audio input.
5. `chat` — Grounded RAG discharge assistant with source pill chips.

#### Target Tabs & Views (Phase 5):
1. **Home** — Next medicine with **Taken / Skip**, today's checklist, latest **valid** readings (impossible values filtered), week strip, next appointment (.ics download), and **Family sharing toggle switch** ("Neha can see your medicine status and appointments: On/Off"). Red emergency banner appears **only** when a real open urgent flag exists.
2. **Medicines** — Today's doses grouped by time of day + **Calendar tab** (month grid and day detail). Not confirmed vs Skipped distinct states. 5-minute undo toast.
3. **Check-in** — Pain 0-10, symptom chips, note, submit. Emergency keywords instantly display life-safety guidance without LLM delay.
4. **Ask my papers** — Grounded assistant with source drawer, right-aligned user messages, left-aligned assistant messages, and "Ask my care team" button for ungrounded queries.

#### Endpoints Called & Server Checks:
- `GET /patient/me/today` → `require_role("Patient", "Caregiver")`
- `POST /patient/me/doses/{id}/taken` → `require_role("Patient", "Caregiver")`
- `POST /patient/me/doses/{id}/skip` → `require_role("Patient", "Caregiver")`
- `POST /patient/me/doses/{id}/undo` → `require_role("Patient", "Caregiver")`
- `POST /patient/me/checkin` → `require_role("Patient", "Caregiver")`
- `POST /patient/me/chat` → `require_role("Patient", "Caregiver")`
- `PUT /patient/me/sharing` → *(To be added: updates `caregivers.consent_granted`)*

---

### 2.4 Family Helper Login (`Neha Patel` · `caregiver1.demo@example.test`)

* **Current Greeting / Subtitle:** "Recovery portal" · "Hi Aarav Patel" *(Identical to Patient)*
* **Target Kicker & Title:** `FAMILY VIEW` · **Aarav's recovery, for family**
* **Role Verb:** **Support** (assist with doses, stay informed of safety escalations, check appointments, access emergency contacts)
* **Accent Token:** Amber (`#d97706`, Soft: `#fffbeb`, Dark: `rgba(251, 191, 36, 0.15)`)

#### Current Tabs & Views:
* Exactly identical to Patient (all 5 tabs, full chat history, symptom forms, and discharge papers accessible).

#### Target Tabs & Views (Phase 5):
1. **Today** (Home):
   - **"What you may need to do"** card: if an escalation reached family, shows clear non-diagnostic prompt ("The care team is checking on Aarav. Please contact him."). Otherwise "Nothing needed right now."
   - Today's doses status only (Taken, Not yet, Not confirmed).
   - Button: **"I helped Aarav take it"** (records dose as confirmed by `Family`).
   - Latest valid reading with timestamp (no clinical jargon).
   - Check-in status: "Check-in sent today: Yes/No" (no private text or pain details).
   - Consent badge: "Sharing allowed by Aarav on 27 Oct". If sharing turned off: "Aarav has turned sharing off" (all other cards hidden).
2. **Calendar**:
   - Upcoming appointments + simple dose history strip.
3. **Contacts**:
   - Prominent **Call 112** emergency card, attending care team phone, and emergency symptom guidance.
*(Strictly Prohibited for Family: Chat assistant, symptom check-in submission, viewing raw symptom text, viewing clinical flags or notes).*

#### Endpoints Called & Server Checks:
- Currently shares all Patient endpoints.
- Target Server-side Permissions:
  * Dedicated family endpoints: `GET /family/today`, `POST /family/doses/{id}/helped`, `GET /family/calendar`, `GET /family/contacts`.
  * **Forbidden (403):** Any `/patient/...` endpoint, `/patient/me/chat`, `/patient/me/checkin`.
  * **Consent Gate:** If `caregivers.consent_granted = FALSE`, returns 403 / "Sharing turned off".

---

## 3. Shared vs. Dedicated Pages Matrix

```
                     DOCTOR          NURSE          PATIENT          FAMILY
                 (Dr. Sharma)    (Priya Nair)    (Aarav Patel)    (Neha Patel)
                 ────────────    ────────────    ─────────────    ────────────
Current Pages:   [  Shared Staff Portal  ]       [  Shared Patient Portal   ]
Target Pages:    • Needs Decis.  • Call List     • Recovery Home  • Family Today
                 • Approvals     • Handoff       • Medicines      • Calendar
                 • Limits        • Patients      • Check-in       • Contacts
                 • Patients (w/  (read-only)     • Ask Papers
                   Limits/Audit)
```

| Page / Component | Doctor | Nurse | Patient | Family | Status |
|---|:---:|:---:|:---:|:---:|---|
| **Landing Page (`/`)** | View | View | View | View | Public Shared |
| **Login Page (`/login`)** | Login | Login | Login | Login | Public Shared |
| **Doctor Desk (`/doctor` or `/staff/decision`)** | **Primary** | Forbidden | Forbidden | Forbidden | **Dedicated (Phase 3)** |
| **Nurse Desk (`/nurse` or `/staff/call-list`)** | View | **Primary** | Forbidden | Forbidden | **Dedicated (Phase 4)** |
| **Patient Directory (`/staff/patients`)** | Full (Edit) | View (Read) | Forbidden | Forbidden | Role-scoped |
| **Approvals & Limits (`/staff/approvals`)** | **Full** | Forbidden | Forbidden | Forbidden | **Dedicated Doctor** |
| **Audit Log & FHIR Export** | **Full** | Forbidden | Forbidden | Forbidden | **Dedicated Doctor** |
| **Shift Handoff (`/staff/handoff`)** | Receive/View | **Author/Edit** | Forbidden | Forbidden | Role-scoped |
| **Patient Recovery Home (`/patient`)** | Forbidden | Forbidden | **Primary** | Forbidden | **Dedicated (Phase 5)** |
| **Patient Medicines & Calendar** | Forbidden | Forbidden | **Full** | Forbidden | **Dedicated Patient** |
| **Patient Check-in Form** | Forbidden | Forbidden | **Full** | Forbidden | **Dedicated Patient** |
| **Discharge RAG Assistant** | Forbidden | Forbidden | **Full** | Forbidden | **Dedicated Patient** |
| **Family Today & Contacts (`/family`)** | Forbidden | Forbidden | Forbidden | **Primary** | **Dedicated (Phase 5)** |

---

## 4. Inspection Gaps & Audit Coverage

The reviewer noted they did not see every screen in their initial 19-page capture. Here is the verified audit of those uninspected screens:

1. **Draft Summaries (`ClinicalSummaries.jsx`)**:
   - *Inspected:* Reads `GET /staff/summaries/pending`. Generates drafts with LLM wrapper. Doctor and Nurse both currently have access to approve (`sp_approve_summary`) or reject (`sp_reject_summary`). Contains fact sheets, but currently lacks an explicit source citations panel.
2. **Operational Insights (`OperationalInsights.jsx`)**:
   - *Inspected:* Renders 9 cohort-level operational metrics (median SLA acknowledge time, overdue tasks count, medication adherence, alert rules distribution). Over-complex for a 5-patient demo. *Plan recommends replacing with a 4-number KPI strip on Doctor Desk.*
3. **Patient Calendar Page (`CareLoopPatientPortal.jsx` lines 1800-2400)**:
   - *Inspected:* Interactive month grid with colored dose status dots and appointments. Day Sheet drawer correctly fetches `GET /patient/me/day?date=YYYY-MM-DD`. `.ics` download works; Google Calendar URL generation exists. *Plan recommends integrating into Medicines tab.*
4. **Patient Medicines Detail Page**:
   - *Inspected:* Grouped morning/afternoon/evening schedule with 60-minute active window validation, skip dose reason modal, and 5-minute undo toast.
5. **Break-Glass Emergency Modal**:
   - *Inspected:* In `PatientOverviewTab.jsx`, unlocks unassigned patients by recording `BREAK_GLASS_ACCESS` to `audit_log`. Not needed in demo because all 5 patients are assigned to Dr. Sharma and Nurse Priya.
6. **Command Palette (`Ctrl+K`)**:
   - *Inspected:* In `CareLoopStaffPortal.jsx`, searches patients, flags, and tasks. Clean implementation; should be preserved.
7. **Pathway Templates Modal**:
   - *Inspected:* 4 clinical templates (Post-CABG, Total Joint, Congestive Heart Failure, Community Pneumonia) in `governance_interop.py`. *Plan recommends hiding from main sidebar to simplify demo explanation.*
8. **FHIR R4 JSON Export**:
   - *Inspected:* Endpoint `/governance/fhir/patient/{id}` generates valid HL7 FHIR R4 JSON collection bundle. *Plan recommends preserving as single button under Doctor "More".*

---

## 5. Security & Safety Checklist

- [x] **No LLM Medical Decision Making**: LLM never sets rules, triggers flags, alters prescriptions, or diagnoses.
- [x] **Deterministic Keyword Engine**: Plain Python regex triggers emergency paths without calling the Gemini API.
- [x] **Consent Enforcement**: Caregiver notification skips when `caregivers.consent_granted = FALSE`.
- [!] **Authorization Enforcement**: Must split endpoints so Nurse cannot approve summaries or edit rules, and Family cannot access chat or check-in text (scheduled for Phase 2).
- [!] **Data Hygiene**: Must clean up test text strings, duplicate tasks, and impossible headline readings (scheduled for Phase 1 Seed Proposal).
