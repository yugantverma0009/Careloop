# CareLoop: Post-Discharge Telemetry & Triage Platform

> [!IMPORTANT]
> **Synthetic-data prototype, not a medical device.**
> CareLoop is an engineering demonstration platform designed to evaluate post-discharge remote patient monitoring workflows. All patient records, clinical notes, telemetry readings, and thresholds are synthetic test data. It is not approved for clinical diagnostic use, does not establish medical diagnoses, and never replaces professional clinical judgment.

---

## 🏛️ Core Governing Principle

> **"The LLM talks. Rules decide. Humans act."**

* **The LLM is text-only**: The language model generates conversational drafts and answers questions strictly from discharge document excerpts. It **never** creates, closes, or modifies flags, tasks, thresholds, or prescriptions.
* **Deterministic Rules Decide**: Clinical flags are generated exclusively by doctor-approved rule procedures, database triggers, and deterministic keyword matching in plain code. Emergency words in English and Hindi bypass the LLM entirely and immediately route to local emergency services (**112**).
* **Humans Act**: Only clinicians (doctors and nurses) resolve flags, adjust thresholds, and contact patients.

---

## 👥 The Four Genuinely Distinct Roles

CareLoop provides four purpose-built workspaces with role-specific permissions, dedicated navigation, and distinct visual accent colors:

| Role | User & Login | Section 2.1 One-Liner | Distinct Scope & Accent |
| :--- | :--- | :--- | :--- |
| **Doctor** | **Dr. Ananya Sharma**<br>`ananya.demo@example.test` | *"The doctor decides, approves and exports."* | **Decisions & Governance**: Approves nurse-proposed telemetry limits, reviews/signs clinical AI summaries, manages medical escalations, and exports standard HL7 FHIR R4 JSON bundles. Routine flags are omitted until escalated.<br>*(Accent: Slate / Navy `#0284c7`)* |
| **Nurse** | **Priya Nair**<br>`priya.demo@example.test` | *"The nurse calls, logs, rechecks and escalates."* | **Execution & Care Coordination**: Triage call list, structured contact logging, patient check-in follow-ups, vital rechecks, and clinical escalation to the doctor. Proposes limit adjustments to doctor (cannot approve directly). Forbidden from approvals, audit log, and FHIR export.<br>*(Accent: Amber / Orange `#d97706`)* |
| **Patient** | **Aarav Patel**<br>`aarav.demo@example.test` | *"The patient acts, checks in and asks their papers."* | **Action & Self-Care**: Daily medication schedule with 1-tap confirmation, 5-minute undo, and structured skip reasons; rapid bilingual symptom check-in; grounded discharge assistant answering strictly with cited document chips; immediate 112 emergency routing.<br>*(Accent: Emerald / Teal `#059669`)* |
| **Family Helper** | **Aarav's Family Helper**<br>`caregiver1.demo@example.test` | *"The family helper supports, is informed with consent, and calls 112 if needed."* | **Consent-Gated Support**: High-contrast read-only care schedule, helped-dose confirmation, and emergency contacts. Zero access to private clinical chat, clinician notes, or free-text symptoms. Completely cut off if patient revokes sharing consent.<br>*(Accent: Violet / Purple `#7c3aed`)* |

*Password for all demo accounts:* **`Demo@12345`**

---

## ⚡ 1-Second Demo Reset & Event Simulator

Reset the demonstration database to the clean 5-patient baseline in under 0.25 seconds:

```bash
# 1. Reset database to clean 5-patient cast (< 0.25s)
python3 scripts/reset_demo.py

# 2. Simulate live SpO2 drop (91% < 94%) for Aarav Patel
python3 scripts/simulate_event.py

# 3. Validate complete 12-check acceptance contract
./backend/env/bin/python3 scripts/validate_demo.py
```

*In the browser:* Click the **"Switch Demo Workspace"** pill in the top navigation bar to switch between all 4 logins with 1 click or trigger an instant database reset directly from the interface.

---

## 🧑‍🤝‍🧑 The 5 Synthetic Demo Patients

| Patient | Discharge Diagnosis | Recovery Day | Demo Scenario & Flag Status |
| :--- | :--- | :--- | :--- |
| **Aarav Patel** | Post-CABG recovery | **Day 3** | Baseline candidate: valid headline vitals (74 bpm, 98% SpO₂), invalid 450 bpm spike ignored, family sharing active. Target of live SpO₂ event simulation. |
| **Meera Joshi** | Heart Failure | **Day 6** | Open `Review_Soon` flag: silent telemetry device (>24 hours without readings). Caregiver consent revoked by patient (family access blocked). |
| **Rajesh Kumar** | Acute MI | **Day 5** | Open `Urgent_Review` flag: emergency symptom check-in (chest pressure) with immediate nurse call task. |
| **Kabir Mehta** | Valve Replacement | **Day 9** | Historical candidate: resolved flag with full clinical audit trail, approved summary ready for review. |
| **Sunita Rao** | Post-PCI Stenting | **Day 4** | Open `Review_Soon` flag: two consecutive missed medication doses with pending nurse call task. |

---

## 🚀 Quickstart Guide

### 1. Database Setup
```bash
mysql -u root -p < careloop_mysql_v2_detailed.sql
python3 scripts/reset_demo.py
```

### 2. Backend Setup
```bash
cd backend
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 3. Frontend Setup
```bash
cd frontend
npm install
npm start
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 🧪 Automated Test Suites

All 51 acceptance tests across Phases 2 through 7 run with 100% pass rate:

```bash
# Run all Phase 2-7 acceptance tests
PYTHONPATH=. ./backend/env/bin/pytest \
  tests/test_role_permissions_p2.py \
  tests/test_doctor_desk_p3.py \
  tests/test_nurse_desk_p4.py \
  tests/test_patient_family_p5.py \
  tests/test_connected_demo_p6.py \
  tests/test_phase7_acceptance.py -v
```

---

## 🔒 Safety & Reliability Highlights

1. **Grounded RAG with Citations**: Patient chat answers come strictly from discharge document excerpts indexed in ChromaDB collections. Refuses medical diagnosis and dose modification requests deterministically.
2. **Offline LLM Resilience**: If the language model provider is unreachable or raises an error, CareLoop never crashes:
   - Structured queries (appointments, medication times) are answered deterministically from MySQL.
   - Discharge document queries fall back to verbatim extractive sentences.
   - Summaries fall back to deterministic SBAR fact sheets with zero judgment words.
3. **Emergency Bypass**: Deterministic keyword matching in English and Hindi ("chest pain", "सीने में दर्द") immediately displays 112 guidance without invoking the LLM.
4. **Headline Vital Quality Filtering**: Telemetry spikes (e.g. 450 bpm) are flagged as `Invalid` by database triggers and omitted from headline vitals, displaying explicit data check notes instead.
5. **HL7 FHIR R4 Interoperability**: Doctor desk exports clinical observations, conditions, and medication statements as standard-compliant FHIR R4 JSON bundles.

---

## 📚 Technical Documentation & Rehearsal Guides
* [Visual Style Lock Specification](docs/STYLE_LOCK.md)
* [Role & Permission Audit](docs/ROLE_AUDIT.md)
* [Connected 6:30 Minute Demo Script](docs/DEMO_SCRIPT.md)
* [Judge Rehearsal Cheatsheet](docs/JUDGE_CHEATSHEET.md)
