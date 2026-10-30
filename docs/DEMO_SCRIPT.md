# CareLoop Connected Demo Script
**Duration:** 6 to 7 minutes  
**Cast:** Exactly 1 Doctor, 1 Nurse, 5 Patients, 4 User Logins  
**Central Principle:** *"The LLM talks. Rules decide. Humans act."*

---

## 0. Preparation & Reset

Before going on stage or starting a rehearsal, run the demo reset command:

```bash
# Terminal command (completes in < 1 second):
./scripts/reset_demo.py
```
*Expected terminal output:*
`Reset complete: 5 patients, 3 open flags, 5 tasks`

*Browser tabs to open ahead of time:*
1. **Landing Page:** `http://localhost:3000/`
2. **Patient (Aarav):** `http://localhost:3000/patient` (or open via Landing Page card)
3. **Family (Neha):** `http://localhost:3000/family`
4. **Nurse (Priya):** `http://localhost:3000/nurse`
5. **Doctor (Dr. Sharma):** `http://localhost:3000/doctor`

*Sign-in Credentials (All passwords are `Demo@12345`):*
- **Doctor:** `ananya.demo@example.test`
- **Nurse:** `priya.demo@example.test`
- **Patient:** `aarav.demo@example.test`
- **Family Helper:** `caregiver1.demo@example.test`

---

## The Demo Story (Minute-by-Minute)

```
Time   | Role                  | Action                                                              | What Judges Learn
-------+-----------------------+---------------------------------------------------------------------+------------------------------------------------------
0:00   | Landing Page          | "Four people, four jobs." Point at 4 role cards                     | The system is strictly role-based
0:30   | Patient (Aarav)       | Taps Taken; sends check-in; asks papers (appointment & dose refusal)| Patient acts; AI is strictly grounded & safe
2:00   | Presenter             | Runs "Send test reading" (Aarav SpO2 91%)                           | Telemetry arrives from wearable watch
2:15   | Patient (Aarav)       | Refresh / live banner: "Your care team has been told..."            | Calm, actionable patient reassurance
2:30   | Family (Neha)         | "What you may need to do: The care team is checking on Aarav..."    | Family is informed with consent; small useful job
3:15   | Nurse (Priya)         | Aarav at top of My Call List; logs call; clicks "Ask doctor"        | Nurse works queue & escalates; explainable reasons
4:15   | Doctor (Dr. Sharma)   | Needs my decision shows Aarav; inspects ladder & resolves; approves | Doctor decides; AI is a draft; humans sign off
5:30   | Doctor → Audit        | Inspects last 20 events: reading, flag, SMS, call, escalation...    | Complete tamper-evident audit trail
6:00   | Patient → Family      | Aarav turns Sharing OFF; Neha's view immediately revokes            | Consent is real and enforced in real time
6:30   | Presenter Close       | "The LLM talks. Rules decide. Humans act."                          | Core design principle
```

---

### Step 1: Landing Page (0:00 – 0:30)
- **URL:** `http://localhost:3000/`
- **What to click:** Point cursor at the 4 distinct role cards.
- **Say:**
  > "Welcome to CareLoop. CareLoop is a post-discharge recovery prototype for four people with four genuinely different jobs:
  > - **The Doctor** decides, approves and exports.
  > - **The Nurse** calls, logs, rechecks and escalates.
  > - **The Patient** acts, checks in and asks their papers.
  > - **The Family Helper** supports, is informed with consent, and calls 112 if needed.
  >
  > Notice the numbers at the top: exactly 5 monitored patients, 2 staff members, 3 open baseline flags, and 100% doctor-approved rules. There are zero unprovable claims.
  > Let's start with our patient, Aarav Patel, recovering on Day 3 after bypass surgery."
- **Do not say:** *"prevents readmissions"*, *"clinically validated"*, *"100% accurate"*, *"hardware-verified"*, *"stable"*, *"normal"*.

---

### Step 2: Patient Portal (0:30 – 2:00)
- **Login:** `aarav.demo@example.test` / `Demo@12345`
- **URL:** `http://localhost:3000/patient`
- **Actions:**
  1. **Tab 1 (Home):**
     - Look at the Next Medicine card: **Pantoprazole 40mg**.
     - Click **Taken**. Point out the green confirmation badge: *"Taken at [Current Time]"*.
     - Point out the 5-minute undo button: *"Undo if tapped by mistake"*.
     - Point out the headline heart rate: **74 bpm (Good)**. Mention that an impossible 450 bpm watch spike was recorded earlier, but filtered out by quality guard rules.
  2. **Tab 3 (Daily check-in):**
     - Select Pain Scale **2** (Mild pain).
     - Select Energy Level **Normal / Okay**.
     - Add note: *"Mild surgical incision soreness, walking around room."*
     - Click **Submit Check-in**.
  3. **Tab 4 (Ask my papers):**
     - Type: *"When is my next appointment?"*
     - Point out the answer: *"Your next follow-up appointment is on 05 Nov 2026 at 10:30 AM with Dr. Ananya Sharma."*
     - Click the source chip: `[Discharge Summary Section 4]`.
     - Now type: *"Can I double my dose of Metoprolol if my chest hurts?"*
     - Point out the instant medical refusal: *"I cannot give advice on changing your medicine dose. Please contact your doctor or nurse."*
- **Say:**
  > "The patient portal is built for action, not passive reading. Aarav confirms his medicine, logs his mild soreness, and queries his discharge papers. The AI answers only from his verified documents with clickable source citations, and strictly refuses dose adjustments."

---

### Step 3: Presenter Sends Test Reading (2:00 – 2:15)
- **Action:**
  - Option A (Terminal): Run `./scripts/simulate_event.py`
  - Option B (UI): Open the presenter dropdown in header and click **⚡ Send 91% SpO₂**.
- **Say:**
  > "Now, Aarav is resting at home wearing his continuous pulse oximeter watch. Let's simulate a genuine telemetry event: Aarav's blood oxygen drops to 91%, breaching Dr. Sharma's approved threshold of 94%."

---

### Step 4: Patient Status Banner (2:15 – 2:30)
- **URL:** `http://localhost:3000/patient`
- **Action:** Reload or observe live status banner.
- **Visual:** Red status banner appears at the top of Home:
  > **Your care team has been told**  
  > *If you have chest pain or severe trouble breathing, call 112 now.*
- **Say:**
  > "Notice how the patient is informed immediately, calmly, with a clear emergency fallback. The app does not diagnose, does not say 'you are hypoxic', but reassures the patient that their care team has been alerted."

---

### Step 5: Family Helper Portal (2:30 – 3:15)
- **Login:** `caregiver1.demo@example.test` / `Demo@12345`
- **URL:** `http://localhost:3000/family`
- **Actions:**
  1. Point out the top card **What you may need to do**:
     > *"The care team is checking on Aarav. Please contact him."*
     Point out that Neha does *not* see internal medical diagnoses, symptom free-text, or chat transcripts.
  2. Point out the scheduled medicine Metoprolol 25mg.
  3. Click **I helped Aarav take it**.
     Notice the status updates to *"Confirmed with family helper support"*.
- **Say:**
  > "Neha Patel has a specific role: support with consent. She received an automated SMS because Aarav consented to family alerts. Her screen gives her one clear task: check in on Aarav. She can also confirm she handed Aarav his midday medicine."

---

### Step 6: Nurse Desk (3:15 – 4:15)
- **Login:** `priya.demo@example.test` / `Demo@12345`
- **URL:** `http://localhost:3000/nurse`
- **Actions:**
  1. First screen is **My call list**.
  2. Aarav Patel appears in the Urgent tier:
     - Tier: **Urgent** (Target: 30m response)
     - Reason: **SpO₂ reading 91.00 % is below the clinician-approved limit of 94.00**
     - Notice: Nurse cannot resolve Urgent flags on her own (it shows *"Needs doctor to resolve"*).
  3. Click **Call**:
     - Modal opens with Aarav's phone `+91 98765 43210`.
     - Log note: *"Reached Aarav by phone; instructed deep breathing and sitting upright; SpO2 recheck pending."*
     - Click **Save Call Log**.
  4. Click **Ask doctor**:
     - Status updates to: *"⚡ Escalated to Dr. Sharma by Priya Nair"*.
- **Say:**
  > "Nurse Priya works the queue. The reason is transparent and explainable: reading 91% below approved limit of 94%. Priya makes the call, logs her clinical assessment, and escalates to Dr. Sharma because an urgent oxygen desaturation requires physician review."

---

### Step 7: Doctor Desk (4:15 – 5:30)
- **Login:** `ananya.demo@example.test` / `Demo@12345`
- **URL:** `http://localhost:3000/doctor`
- **Actions:**
  1. First screen is **Needs my decision**.
  2. Aarav Patel is at the top with Priya's escalation note:
     - *"Escalated by Priya Nair: Reached Aarav by phone; instructed deep breathing and sitting upright..."*
  3. Click **Decide** to open Flag Drawer:
     - Point out the **Approved Rule**: SpO₂ < 94%, approved by Dr. Ananya Sharma on 28 Oct.
     - Point out the **Escalation Ladder**: Step 1 Patient Prompt (Sent) → Step 2 Caregiver SMS (Sent to Neha) → Step 3 Nurse Call (Contacted) → Step 4 Doctor Alert (Active).
     - Enter resolution note: *"Reviewed telemetry. Recheck reading confirmed at 95%. Continue current ACE-inhibitor and schedule telemetry check in 2h."*
     - Click **Resolve Flag**.
  4. Click **Approvals** on sidebar:
     - Open Meera Rao's draft AI discharge summary.
     - Point out cited sources and fact sheet.
     - Edit one line in the draft.
     - Click **Approve Summary**.
- **Say:**
  > "Dr. Sharma decides. The doctor sees who set the limit, who was called, and what the nurse found. The AI draft summary is reviewed, edited by hand, and signed off. The AI never approves itself."

---

### Step 8: Audit Log Viewer (5:30 – 6:00)
- **Navigation:** Doctor Desk sidebar → **Audit log viewer** (`/staff/doctor` -> audit tab)
- **Visual:**
  - Ingest reading DEV-ESP32-001 (SpO₂ 91.0%)
  - Flag #6 created by rule engine (SpO₂ < 94%)
  - SMS dispatched to Neha Patel
  - Call logged by Nurse Priya Nair
  - Flag escalated to Dr. Ananya Sharma
  - Flag resolved by Dr. Ananya Sharma
- **Say:**
  > "Every action across the entire loop is recorded in a tamper-evident audit log with exact timestamps, actors and entity IDs."

---

### Step 9: Consent Control Verification (6:00 – 6:30)
- **Actions:**
  1. Switch to Patient Portal (`/patient`).
  2. On Home, toggle **Family sharing: OFF**.
  3. Switch to Family Portal (`/family`).
  4. Reload screen. The entire portal locks immediately:
     > **Aarav has turned sharing off.**  
     > *Aarav has paused data sharing with family helpers. When he turns sharing back on, his progress will appear here.*
- **Say:**
  > "Consent is genuine and instant. The moment Aarav turns sharing off, Neha's access is revoked completely."

---

### Step 10: Closing Statement (6:30 – 7:00)
- **Say:**
  > "CareLoop proves that in post-discharge care, artificial intelligence has a clear, safe place:
  > **The LLM talks. Rules decide. Humans act.**
  > Thank you. We are ready for your questions."
