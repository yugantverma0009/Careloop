# CareLoop Role & Permission Contract

**Document Version:** 1.0 (Phase 2)  
**Governing Principle:** *"The LLM talks. Rules decide. Humans act."*

---

## 1. Overview & Personas

CareLoop operates with four distinct roles. Each role exists to perform a genuine, non-overlapping clinical or support responsibility:

| Role | Persona in Demo | Verb | Core Duty | Visual Accent | Entry Route | Sidebar Subtitle |
|---|---|---|---|---|---|---|
| **Doctor** | Dr. Ananya Sharma | **Decide** | Clinically decides on urgent alerts, approves AI summaries and threshold changes, reviews audit logs. | Purple (`#7c3aed`) | `/doctor` | Doctor desk |
| **Nurse** | Priya Nair | **Watch & Call** | Works the call list, contacts patients, resolves routine alerts, escalates urgent concerns to the doctor, conducts shift handoff. | Blue (`#0284c7`) | `/nurse` | Nurse desk |
| **Patient** | Aarav Patel | **Do** | Takes medicines, logs daily recovery status, reviews discharge papers with grounded assistant, controls family sharing consent. | Teal (`#0d9488`) | `/patient` | Recovery portal |
| **Family helper** | Neha Patel | **Support** | Views allowed daily status, confirms doses helped, accesses emergency contacts and calendar. Operates strictly under patient consent. | Amber (`#d97706`) | `/family` | Family view |

---

## 2. Definitive Permissions Matrix

| Action | Patient | Family Helper | Nurse | Doctor | Enforced By |
|---|:---:|:---:|:---:|:---:|---|
| **Confirm / skip own doses** | **Yes** | No | No | No | `require_patient` |
| **Confirm dose as family ("I helped")** | No | **Yes** (`Family` actor) | No | No | `require_family` |
| **Daily check-in (pain, symptoms)** | **Yes** | No (403) | No | No | `require_patient` |
| **Discharge-papers RAG chat** | **Yes** | No (403) | No | No | `require_patient` |
| **View medicines & today's doses** | **Yes** | **Yes** (status only) | **Yes** | **Yes** | `require_patient` / `require_family` / `require_staff` |
| **View sensor readings** | **Yes** (latest valid) | **Yes** (latest valid + time) | **Yes** (with quality flags) | **Yes** (with quality & limits) | Role-specific views |
| **View raw symptom text & chat history** | **Yes** | **No** (only check-in status: yes/no) | **Yes** | **Yes** | Redacted in `/family` endpoints |
| **Turn family sharing ON / OFF** | **Yes** | No | No | No | `require_patient` (`POST /patient/me/sharing`) |
| **Family access when sharing turned OFF** | N/A | **Blocked immediately (403)** | N/A | N/A | `require_family` (checks `caregivers.consent_granted`) |
| **View triage queue / call list** | No | No | **Yes** (Call list) | **Yes** (Items needing decision) | `require_staff` |
| **Acknowledge a flag** | No | No | **Yes** | **Yes** | `require_staff` |
| **Log a call / note on flag** | No | No | **Yes** | **Yes** | `require_staff` |
| **Resolve routine / review-soon flag** | No | No | **Yes** | **Yes** | `can_resolve_flag` policy |
| **Resolve urgent or immediate flag** | No | No | **No (403)** | **Yes (requires note)** | `can_resolve_flag` policy |
| **Escalate flag to doctor ("Ask doctor")** | No | No | **Yes** | **Yes** | `POST /staff/flags/{id}/escalate-doctor` |
| **Suggest a limit change (proposal)** | No | No | **Yes** | **Yes** | `POST /staff/rules/propose-limit` |
| **Approve a limit change** | No | No | **No (403)** | **Yes** | `require_doctor` |
| **Generate draft AI clinical summary** | No | No | **Yes** | **Yes** | `require_staff` |
| **Approve or reject AI summary** | No | No | **No (403)** | **Yes** | `require_doctor` |
| **Shift handoff creation & receipt** | No | No | **Yes** (writes/receives) | **Yes** (receives) | `require_staff` |
| **View audit log** | No | No | **No (403)** | **Yes** | `require_doctor` |
| **Export FHIR bundle** | No | No | **No (403)** | **Yes** | `require_doctor` |

---

## 3. Enforcement Mechanisms

### 3.1 Backend Server-Side Checks (`backend/app/permissions.py`)

- **Role Identity:** Every JWT token includes `role`, `account_id`, `patient_id`, `caregiver_id`, and `staff_id`.
- **Identity Theft / IDOR Protection:** Patients cannot query any other patient's records. All `/patient/me/...` endpoints derive `patient_id` directly from the validated token.
- **Strict Role Gating:**
  - `require_doctor`: Enforces `user.role == "Doctor"`.
  - `require_nurse`: Enforces `user.role == "Nurse"`.
  - `require_staff`: Enforces `user.role in ("Doctor", "Nurse")`.
  - `require_patient`: Enforces `user.role == "Patient"`. Caregivers calling `/patient/...` receive `403 Forbidden`.
  - `require_family`: Enforces `user.role == "Caregiver"` AND verifies in real-time that `caregivers.consent_granted = 1`. If consent is revoked, returns `403 Forbidden` (`{"detail": "Sharing turned off by patient", "sharing_enabled": false}`).
- **Flag Resolution Authority Rule (`FLAG_AUTHORITY_POLICY`):**
  - Flags with severity `Info` (Routine) or `Review_Soon`: Resolvable by either Nurse or Doctor.
  - Flags with severity `Urgent_Review` or `Immediate`: Resolvable **only by Doctor**, with mandatory `resolution_note` (minimum 5 characters).
  - Attempting to resolve an urgent flag as a Nurse returns `403 Forbidden`: *"Nurse cannot resolve urgent or immediate flags. Please escalate to doctor."*
  - Nurse uses `POST /staff/flags/{id}/escalate-doctor` to record an `Escalated` event in `flag_events` and pass the item to the doctor desk.

### 3.2 Client-Side Route & Component Guards

- **Route Redirection:**
  - `/doctor` → Allowed for Doctor. Nurse visiting `/doctor` gets a polite redirection / notice.
  - `/nurse` → Allowed for Nurse.
  - `/patient` → Allowed only for Patient.
  - `/family` → Allowed only for Family Helper (Caregiver).
- **Navigation Customization:**
  - Doctor sidebar: `Needs my decision`, `Patients`, `Approvals`, `Patient limits`, `More (Audit, Export)`.
  - Nurse sidebar: `My call list`, `Patients`, `Handoff`.
  - Patient sidebar / tabs: `Home`, `Medicines`, `Check-in`, `Ask my papers`.
  - Family tabs: `Today`, `Calendar`, `Contacts`.
- **Accent Color Hierarchy:**
  - Role Chip and Page Kicker reflect the role accent color (`--role-doctor`, `--role-nurse`, `--role-patient`, `--role-family`).

