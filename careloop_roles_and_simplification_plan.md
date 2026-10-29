# CareLoop: Roles, Simplification and Judge-Ready Demo Plan (7 Phases)

**Why this file exists:** the app now has four logins (doctor, nurse, patient, family) but they **look and work almost the same**, and there is too much data to explain. This plan makes each role do a clearly different job, cuts the project down to what you need to show judges, and rebuilds the seed data so every screen tells a simple story.

**Guiding rule (keep saying it):** *The LLM talks. Rules decide. Humans act.*
**Style rule:** do **not** change the visual style (colours, fonts, spacing, cards, buttons). Differences between roles come from *content, navigation and wording*, using the accent colours the app already has.

> What I reviewed: your 19-page capture of `localhost:3000` (landing page, login, doctor worklist, doctor patient page, doctor tasks, handoff, audit log, nurse worklist, patient home, patient check-in history, family home). I did **not** see every screen (for example draft summaries, insights and the calendar page), and I have not seen your code. Antigravity must audit the rest in Phase 1 and tell you where this plan does not match reality. All data is synthetic.

---

## 0. How to use this file

1. Put it in the project root with your other CareLoop files.
2. Paste this into Antigravity:

```
Read careloop_roles_and_simplification_plan.md completely. Also skim careloop_master_project_document.md and careloop_mysql_v2_detailed.sql.
Work on a new git branch named roles-and-simplify.
Follow the 7 phases in order. Start with Phase 1 and STOP after it for my approval. Do the same after each phase.
Do not change the visual style. Reuse existing components, colours, fonts, spacing and the dark/light theme.
Never break the safety rules in Section 3. Ask me before deleting anything that is not clearly test data.
After every phase show real command output, screenshots (doctor, nurse, patient, family), and a list of what you did not test.
```

---

## 1. What I saw in your screens (honest findings)

| # | Finding | Where | Why it matters |
|---|---|---|---|
| 1 | **Nurse and doctor look identical.** Priya Nair (Triage Nurse) sees the same 8-item sidebar and the same "Who needs attention first" page as Dr. Sharma, including Draft summaries, Operational insights and Audit log viewer | Doctor page vs nurse page | Judges will ask "why two roles?" |
| 2 | **Family and patient look identical.** The family login ("Aarav's Family Caregiver") shows "Hi Aarav Patel", the same Taken/Skip buttons, Daily check-in and Ask my discharge papers | Patient page vs family page | The family has no distinct purpose and sees everything the patient sees |
| 3 | **Too much data.** About 115 open flags across 10 patients, one patient with 95 flags, 161 follow-up tasks (many are the same "Can I double my dose?" question), 18 draft summaries, 200 audit events, dozens of check-ins | Worklist, tasks, summaries, audit, check-in history | Nobody can explain this in a demo |
| 3a | Test text is visible: "Unit test flag for escalation", "Unit test open flag for assignment" | Worklist, patient page | Looks unfinished |
| 3b | Old generic reason still shows: "Patient #1 (Aarav Patel): Clinical recovery threshold logged for monitoring team review." | Worklist | Hides the real reason |
| 4 | **Handoff page shows duplicate cards** (Kabir Mehta twice, Rajesh Verma twice) and a **137-item action list** for one patient | Shift handoff | Looks broken |
| 5 | **A medical threshold is hard-coded as text** on every handoff card: "Standard escalation protocol: If SpO2 < 90% or severe chest pain, escalate to attending doctor." The project rule is that clinicians set thresholds | Shift handoff | Invented clinical protocol shown as fact |
| 6 | **Inconsistent numbers:** Aarav is "Post-discharge Day 15" on one screen and "Post-CABG Day 3" on another | Doctor page, patient page | Seed uses fixed dates, not relative dates |
| 7 | **"Pulse 450 bpm, Invalid" is shown as the latest reading** on the patient home and the doctor's vitals card | Patient home, doctor page | An impossible value should not be the headline number |
| 8 | Landing page claims: "Hardware-verified", "Aims to prevent hospital readmissions", "100% Emergency Keyword Detection", "98.2% Readings Checked for Errors" | Landing | Over-claims you cannot prove |
| 9 | Two notification bells in the staff top bar; the permanent red "Your care team has been told" banner on the patient and family pages even when nothing is wrong; "Overdue by 3181m"; raw label "Review_Soon"; a tab called "Upgraded Timeline" | Various | Polish |
| 10 | Features that are impressive but make explaining harder: LACE panel, pathway templates, operational insights, FHIR export, "Assign", "Unassigned" scope (you have one doctor and one nurse) | Doctor page, sidebar | Hide or remove (Section 5) |

**What is already good and should stay:** grouped worklist by patient with tiers and time targets, patient identity (name, age, code), the flag detail drawer, the audit log idea, the I-PASS handoff idea (once fixed), the family-consent badge, the patient's Taken/Skip checklist, the EN/HI toggle, the "Ask my discharge papers" assistant.

---

## 2. The role design: who does what

### 2.1 One-line pitch per role (use these with the judges)

| Role | In one line | Verb |
|---|---|---|
| **Patient** | "I follow my plan and tell the team how I feel." | **Do** |
| **Family helper** | "I help, and I'm told if something is missed." | **Support** |
| **Nurse** | "I watch the queue, call people and keep every alert from being forgotten." | **Watch and call** |
| **Doctor** | "I decide what is clinically important and approve what the AI drafts." | **Decide** |
| **System** | "Rules raise flags, AI explains in plain words, humans decide." | |

### 2.2 How they work together (the chain)

```
Patient misses a dose / reports a symptom / watch sends a reading
   → Rules raise a flag (not the AI)
   → Patient is prompted
   → Family helper is told (only if the patient allowed it)
   → NURSE acknowledges, calls, logs the call
   → NURSE can resolve routine flags, or presses "Ask doctor"
   → DOCTOR decides on urgent flags, approves the AI summary, approves limit changes
   → Everything is written to the audit log
```
This matches the escalation ladder already in the project (Patient → Family → Nurse → Doctor).

### 2.3 Permissions matrix

| Action | Patient | Family | Nurse | Doctor |
|---|:-:|:-:|:-:|:-:|
| Confirm or skip their own doses | Yes | "I helped Aarav" (recorded as Family) | No | No |
| Send a daily check-in (pain, symptoms) | Yes | No | No | No |
| Ask the discharge-papers assistant | Yes | No | No | No |
| See medicines, today's doses | Yes | Yes (status only) | Yes | Yes |
| See readings | Yes | Latest valid reading and time | Yes, with quality | Yes, with quality and limits |
| See symptom text and chat history | Yes | **No** (only "check-in sent today: yes/no") | Yes | Yes |
| Turn family sharing on or off | **Yes** | No | No | No |
| See the triage queue | No | No | **Yes (their call list)** | **Yes (only items needing a decision)** |
| Acknowledge a flag | No | No | Yes | Yes |
| Log a call, add a note | No | No | Yes | Yes |
| Resolve routine and "review soon" flags | No | No | Yes | Yes |
| Resolve **urgent or immediate** flags | No | No | **No (acknowledge and "Ask doctor")** | **Yes, with a note** |
| Suggest a limit (threshold) change | No | No | Yes (proposal) | Yes |
| **Approve** a limit change | No | No | **No** | **Yes** |
| Generate an AI summary | No | No | Yes | Yes |
| **Approve or reject** an AI summary | No | No | **No** | **Yes** |
| Shift handoff (write and receive) | No | No | **Yes (writes it)** | Yes (receives it) |
| See audit log | No | No | No | **Yes (under "More")** |
| Export FHIR bundle | No | No | No | **Yes (under "More")** |

The "who resolves urgent flags" rule is a **demo policy** that is easy to explain. It is configurable and must be described as such.

### 2.4 What each role sees first (so the screens stop looking alike)

| Login | Sidebar subtitle | Page kicker and title | First screen shows | Sidebar items |
|---|---|---|---|---|
| **Doctor** (Dr. Ananya Sharma) | Doctor desk | DOCTOR DESK · **Needs my decision** | 4 numbers (needs decision now, summaries to approve, limit requests, patients in follow-up), then a short list of items waiting for a decision, then "Quiet patients: 2 (nothing open)" | Needs my decision · Patients · Approvals · Patient limits · *More* (Audit, Export) |
| **Nurse** (Priya Nair) | Nurse desk | NURSE DESK · **My call list** | A call list ordered by urgency. Each row: patient, why, time target, **Call**, **Acknowledge**, **Ask doctor**, **Done** | My call list · Patients · Handoff |
| **Patient** (Aarav Patel) | Recovery portal | MY RECOVERY · **Hi Aarav** | Next medicine with Taken/Skip, today's checklist, latest valid readings, week strip, family-sharing switch | Home · Medicines (with calendar) · Check-in · Ask my papers |
| **Family** (Neha Patel, spouse) | Family view | FAMILY VIEW · **Aarav's recovery, for family** | One "what you may need to do" card, today's dose status, next appointment, emergency card (call 112 and care team phone), "Sharing allowed by Aarav on 27 Oct" | Today · Calendar · Contacts |

**Visual differentiation without changing style:** each role gets a different **accent colour taken from the colours the app already uses** (blue, green, purple, amber are all present today) for the active sidebar item, the role chip in the top bar, and the page kicker. Different sidebar subtitle, different title, different first screen, different buttons.

---

## 3. Safety and honesty rules (unchanged, still mandatory)

1. Rules create flags. The LLM never creates, closes or changes flags, tasks, limits or prescriptions.
2. Emergency words (English and Hindi) are detected by plain code and show guidance at once.
3. The assistant never diagnoses, never says a reading is safe or unsafe, never advises on doses.
4. No clinical judgment words in system text ("stable", "normal", "improving", "optimal").
5. **No medical thresholds written into the interface or seed text.** Limits live in `alert_rules`, approved by the doctor, and screens show them as "approved limit".
6. Two identifiers (name, age, patient code) wherever a patient appears. A name must never disagree with its record.
7. Every state change writes `flag_events` and `audit_log`.
8. The family sees only what the patient allowed. Turning sharing off removes the family's access and the caregiver SMS step becomes "Skipped: no consent".
9. Missing, invalid or questionable data is labelled. **The headline "latest reading" is the latest *valid* one.** Invalid readings appear only in a small "data check" note.
10. Do not claim outcomes ("prevents readmissions", "100% detection", "hardware-verified"). Say what the prototype does.

---

## 4. The final cast (one doctor, one nurse, five patients, four logins)

### 4.1 Staff and logins
| Person | Role | Login |
|---|---|---|
| Dr. Ananya Sharma | Doctor (attending for all patients) | yes |
| Priya Nair | Nurse (assigned to all patients) | yes |
| Aarav Patel | Patient | yes |
| Neha Patel (spouse of Aarav) | Family helper | yes |
| Other patients' family members | exist as **data rows only** (to show consent), no login | no |

Remove the second doctor (Dr. Rohan Mehta). Everyone is Dr. Sharma's patient and Priya's patient.

### 4.2 Five patients, each tells **one** story
Use **relative dates** (discharge date = today minus N days) so "Day N" is always consistent after every reset.

| # | Patient | Condition | Day | Story for the judges | State at demo start |
|---|---|---|---|---|---|
| 1 | **Aarav Patel**, CL-00001, 41 y | Post-CABG | Day 3 | **The live demo patient.** Used for the full chain: watch reading, flag, family alert, nurse, doctor, AI summary, assistant | **Calm start:** no open flags. Doses mostly taken. Family consent on. One old resolved flag in history |
| 2 | **Meera Sharma**, CL-00002, 54 y | Total knee replacement | Day 6 | **Silent device + consent gate.** The watch has sent nothing for over 6 hours. Her caregiver has **not** consented | 1 open "Review soon" flag (no data). Escalation shows caregiver step "Skipped: no consent". Draft summary waiting |
| 3 | **Rajesh Verma**, CL-00003, 47 y | Community pneumonia | Day 5 | **Emergency path.** A Hindi check-in matched an emergency keyword | 1 open **Immediate** flag, unacknowledged for about 20 minutes. Draft summary waiting |
| 4 | **Kabir Mehta**, CL-00004, 34 y | Appendectomy convalescence | Day 9 | **Quiet patient.** Everything on track, nothing open. Shows the system stays silent when nothing is wrong | 0 flags. 1 approved summary. 1 completed task |
| 5 | **Sunita Rao**, CL-00005, 63 y | Congestive heart failure | Day 4 | **Dose-change question + missed doses.** She asked "Can I stop my blood-pressure medicine?" | 1 open "Review soon" flag (2 missed doses in 48 h), 1 nurse task from the refused question |

Remove the other five patients (Vikram Malhotra, Arjun Nair, Pooja Gupta, Ananya Iyer, Deepa Joshi). Five is enough to show every feature.

### 4.3 Target data volumes (everything must be explainable by pointing at the screen)

| Data | Target at demo start | Old |
|---|---|---|
| Patients | 5 | 10 |
| Staff | 1 doctor, 1 nurse | 2 doctors, 1 nurse |
| Logins | 4 | 4 plus others |
| Open flags | **3** (Meera, Rajesh, Sunita). 2 resolved ones in history | about 115 |
| Follow-up tasks | **5** open, 1 completed | 161 |
| Draft summaries | **2** waiting (Meera, Rajesh), 1 approved (Kabir) | 18 |
| Audit events | about **30**, all produced by real actions | 200 |
| Aarav's check-ins | 5 to 7 (one a day, pain 1 to 3) | dozens, many emergencies |
| Other patients' check-ins | 1 to 2 each | dozens |
| Aarav's readings | about 12 valid points over 3 days, plus 1 invalid (450 bpm) kept as a data-quality example | many |
| Aarav's chat | 6 messages (see below) | many repeats |
| Medicines | Aarav 3 doses a day (2 medicines). Others 1 to 2 doses a day | |
| Appointments | 1 per patient | |
| LACE, pathway templates | none (hidden feature) | |

**Aarav's chat (6 messages):**
1. "When is my next appointment?" → grounded answer with source
2. "What warning signs should I watch for?" → grounded answer with source
3. "Can I double my dose?" → refusal, **one** nurse task
4. "What should I eat?" (not in his papers) → "not found", Ask care team button
5. A short follow-up to message 2
6. A "thank you"

### 4.4 Rules for the seed
- Flags must come from the **real mechanisms** (rules, triggers, procedures, simulated readings, check-ins). No hand-typed flags with generic text.
- Remove every "Unit test…", "microphone test…" and "Identical submission test" string.
- One reason text per flag, the real one (for example "SpO₂ reading 91% is below the clinician-approved limit of 94"). No "Patient #N (Name):" prefix.
- A refused question creates **one** task per patient per topic (de-duplicate), not one per message.
- Medicine names are invented (keep CardioPulse-XR, VasculoNorm-5 if they are not real brands; Antigravity should check). Dose text is neutral sample text.
- Approved limits for the demo are **fictional demo values** entered under the doctor's name. Never display them as protocol text.

---

## 5. What to remove, hide, simplify or keep

| Item | Decision | Reason |
|---|---|---|
| About 100 extra flags, 150 extra tasks, 15 extra summaries, 170 audit rows | **Remove** (reseed) | Unexplainable |
| Test strings, duplicate handoff cards, generic "Clinical recovery threshold logged…" text | **Remove / fix** | Looks unfinished |
| Hard-coded "If SpO2 < 90%…" escalation protocol text | **Remove** | Invented clinical protocol |
| 5 of the 10 patients, second doctor | **Remove** | You asked for one doctor, one nurse |
| LACE panel | **Hide** (keep code, no menu entry; doctor "More" only if time) | Adds a topic you must defend |
| Pathway templates | **Hide** | Not needed for the story |
| Operational insights page | **Replace** with a 4-number strip on the doctor home | Simpler |
| FHIR export | **Keep as one button** under doctor "More" | Good one-sentence interoperability answer |
| Audit log | **Keep, simplified** (last 20 events, filters hidden) under doctor "More" | "Everything is logged" is a strong point |
| "Assign" button, "Unassigned" scope | **Remove** | Only two staff |
| "Patient timeline" as its own sidebar page | **Merge** into the patient page as a tab | Fewer pages |
| "Patient directory" and "Patients" | **Merge** into one "Patients" | Fewer pages |
| Second bell icon | **Remove** | Duplicate |
| Patient "My calendar" page | **Merge** into Medicines (tab) and the home week strip | Fewer pages |
| Google Calendar link | **Keep only the .ics download** | One path |
| Hindi on staff screens | **Not needed** (staff English only). Keep EN/HI for patient and family | Less to translate |
| Landing claims (hardware-verified, prevents readmissions, 100%, 98.2%) | **Remove or reword** | Cannot be proven |
| Permanent red banner | **Only when a real urgent flag exists** | Banner must mean something |

---

## 6. The seven phases

Order matters: data first, then roles, then one role at a time, then the story, then proof.

| Phase | Name | Result |
|---|---|---|
| 1 | Audit, freeze and clean the data | A small, consistent, explainable database |
| 2 | Role and permission model | Server-enforced rules; each role has its own entry points |
| 3 | Doctor desk | A decision-focused home, approvals, limits |
| 4 | Nurse desk | A call-list workflow and handoff |
| 5 | Patient app and family view | Four patient pages and a genuinely different family view |
| 6 | The one connected demo story and landing page | A 6 to 7 minute script that crosses all four logins; reset button |
| 7 | Quality, claims audit and judge rehearsal | Tests, screenshots, Q&A, backup video |

---

### PHASE 1: Audit, freeze and clean the data

**Goal:** one small, believable dataset that never contradicts itself, and a written map of what exists.

**Tasks**
1. **Read-only audit.** Write `docs/ROLE_AUDIT.md`: for each of the four logins list the sidebar items, pages, API endpoints they call, and which backend checks exist. Mark which pages are shared between roles and which screens I did not see (draft summaries, insights, calendar, medicines) so I know the gaps.
2. **Style lock.** `docs/STYLE_LOCK.md` with the existing tokens and the accent colours available per role. Baseline screenshots (light and dark) of landing, login, and the first screen of each login.
3. **Decide the final cast** exactly as in Section 4 and ask me to confirm before deleting anything that is not obvious test data.
4. **Write `scripts/reset_demo.sql` and `scripts/seed_demo.py`** (idempotent, runs in under 30 seconds) that:
   - recreates the five patients, doctor, nurse, four logins, caregivers (Aarav's and Meera's with different consent), devices (Meera's silent), medicines, prescriptions and dose times, appointments, approved limits;
   - uses **relative dates** (today minus N days);
   - generates doses with `sp_generate_daily_doses`, readings with the simulator logic, check-ins and chat messages through the **normal API or SQL paths** so triggers and rules create flags, escalations and audit rows;
   - creates the exact starting state in Section 4.2 and the volumes in Section 4.3.
5. **Consistency checks.** Add `scripts/validate_demo.py` that fails if: a text names a patient who is not the record's patient; the day number differs between pages; a flag lacks a real reason; a task is duplicated; counts are outside the targets; the latest reading shown for a patient is Invalid.
6. **Fix data-display defects found in Section 1:** duplicate handoff cards (find the cause), "Day 15 vs Day 3", "450 bpm" as latest reading (show the latest valid reading and a small "1 reading ignored: impossible value" note), minutes shown as "3181m" (show "2 d 5 h"), raw "Review_Soon" label (show "Review soon").
7. Remove the hard-coded "SpO2 < 90%" protocol text.

**Acceptance checks**
- Running the reset twice gives the same result.
- `validate_demo.py` passes.
- Counts match Section 4.3 (3 open flags, 5 open tasks, etc.).
- No "Unit test", "microphone test" or "Patient #N (" text anywhere on screen.
- Every page shows the same "Day N" for the same patient.

**Show me:** the audit file, the validation output, before/after counts, screenshots of doctor and nurse worklists with the new small data.
**Ask me before:** deleting any real-looking data, changing a stored procedure, adding a table.

---

### PHASE 2: Role and permission model

**Goal:** each role has its own entry point and the server enforces what it may do.

**Tasks**
1. **Single role contract.** Create `docs/ROLE_CONTRACT.md` and a code module (for example `permissions`) that holds the matrix from Section 2.3. The UI and the API both read from it.
2. **Server-side checks.** Every endpoint checks the role and, for patients and family, the patient id **from the login token**:
   - Patient endpoints return only the patient's own data.
   - **Family endpoints are separate** (for example `/family/today`, `/family/doses/{id}/helped`, `/family/calendar`, `/family/contacts`). They return a reduced set and refuse chat, symptom text and notes.
   - Nurse endpoints cannot approve summaries or limits, cannot resolve urgent or immediate flags, cannot open the audit log.
   - Doctor endpoints add approvals, resolving urgent/immediate flags, limits, audit, export.
3. **Family consent.** Family access requires `caregivers.consent_granted = TRUE`. When the patient turns sharing off, family endpoints return a clear "Sharing is turned off" response and the escalation step shows "Skipped: no consent".
4. **Separate entry routes and navigation.** After login each role lands on its own home (Section 2.4). Direct URL access to a page the role may not use shows a polite "This page is for doctors" and is logged.
5. **Role chip and accent.** Top bar shows the role chip ("Doctor", "Nurse", "Patient", "Family helper") with the role's accent token. Sidebar subtitle per role.
6. **Flag authority rule.** Implement "nurse can acknowledge and resolve routine and review-soon flags; urgent and immediate need the doctor" as a **config value**, with the doctor's resolve requiring a note. Nurse gets an **Ask doctor** action that records a `flag_events` row ("Escalated to doctor") and makes the flag appear on the doctor home.
7. Remove "Assign" and the "Unassigned" scope. Keep "Mine" and "All".

**Acceptance checks (automated tests)**
- A nurse calling `approve summary`, `approve limit`, `audit`, `export` gets 403.
- A family token calling any `/patient/...` or chat endpoint gets 403.
- Changing a patient id in a URL does not leak another patient's data.
- Turning family sharing off blocks family data immediately.
- A nurse cannot resolve an urgent flag; the doctor can, but only with a note.

**Show me:** the role contract file, the test output, a table of "login → first page → sidebar items".

---

### PHASE 3: Doctor desk ("Needs my decision")

**Goal:** the doctor's screen answers one question: "What needs **me**?"

**Tasks**
1. **Doctor home** (page kicker "DOCTOR DESK", title "Needs my decision"):
   - Four number cards: *Needs decision now*, *Summaries to approve*, *Limit change requests*, *Patients in follow-up*.
   - A short list of decision items, each with patient identity (name, age, code), what is being asked, how long it has waited, and two buttons: **Decide** and **Open patient**. Sources of items: immediate/urgent flags (including those the nurse escalated), AI summaries waiting, limit proposals, dose-change questions the nurse passed up.
   - A one-line "Quiet patients: 2. Nothing open." row to show the system stays silent when nothing is wrong.
2. **Flag drawer (keep, simplify):** reason, evidence, rule and who approved it, escalation ladder, history. Doctor actions: **Resolve** (reason code plus note), **Dismiss as false alarm**, **Add note**. No "Assign".
3. **Approvals page** (summaries and limit proposals together):
   - **AI summary:** shows patient identity, period, "AI draft, not reviewed", a **Sources** panel listing the facts it was built from, an editable text box, **Approve** (records approver, time, final text) and **Reject** (needs a reason). No judgment words. Name inserted by code from the record.
   - **Limit proposals:** old value, new value, who proposed, why; **Approve** or **Reject** (history stored).
4. **Patient limits page:** the doctor's own limits per patient (heart rate above, SpO₂ below, pain at or above, missed doses, silent device hours) with approver and date. This is where **"approved limit"** comes from. Values are fictional demo values; no medical protocol text elsewhere.
5. **Patients page** (merge directory and timeline): list with open flag count and device status; patient page tabs: **Overview, Medicines, Check-ins, Limits, Notes**. The timeline becomes a section in Overview with filter chips (Readings, Symptoms, Doses, Flags). Rename "Upgraded Timeline" and "Trigger Rules & Limits" to "Timeline" and "Limits".
6. **More** menu (doctor only): **Audit log** (last 20 events, filters hidden), **Export FHIR bundle**. Hide LACE, pathway templates and the insights page.
7. Remove the second bell, the "Assign" button and the cohort-wide "115 open flags" language.

**Acceptance checks**
- With the Section 4 data, the doctor home shows: 1 immediate item (Rajesh), 2 summaries to approve (Meera, Rajesh), 0 limit requests at start, 5 patients, "Quiet patients: 2".
- Approving a summary writes the approver, time and the final text; rejecting requires a reason.
- The doctor home does **not** show routine items (Sunita's missed doses, Meera's silent device) unless the nurse escalated them.

**Show me:** doctor home screenshot, an approved summary with its sources, the limits page, audit "More".

---

### PHASE 4: Nurse desk ("My call list")

**Goal:** the nurse's day is a **call list** that gets emptied and handed off, not a dashboard.

**Tasks**
1. **Nurse home** (kicker "NURSE DESK", title "My call list"):
   - Rows ordered by tier then age. Each row: patient identity, **why** (the real reason), tier chip with target timer ("Target: seen within 15 min · overdue 1 h 5 min"), and buttons **Call**, **Acknowledge**, **Ask doctor**, **Done**.
   - Immediate and urgent rows show "Needs doctor to resolve", so the nurse knows to acknowledge and escalate.
   - A "Calls due today" strip (tasks due today).
2. **Call logging** (small dialog): channel (Phone, SMS), outcome (Reached, No answer, Left message), one-line summary. Saved to the call log and audit. In demo mode SMS is logged, not sent.
3. **Task completion** with outcome codes (Reached and advised, Appointment set, No answer, Escalated to doctor, No action needed). One task per topic, no repeated tasks.
4. **Suggest a limit change:** nurse can propose; it appears in the doctor's Approvals. Nurse cannot approve.
5. **Handoff (simplified, nurse-owned):** one card per patient, **at most 5 lines each**: attention tier, one-line summary, open items, "if X happens call Y" text typed by the nurse (no pre-filled medical thresholds), **Mark received** by the doctor. Fix the duplicate cards and the 137-line list.
6. **Patients** list (same page as the doctor, but without Limits editing, Approvals, Audit or Export).
7. Remove from the nurse's sidebar: Draft summaries, Operational insights, Audit log, Follow-up tasks as a separate page (tasks live inside "My call list").

**Acceptance checks**
- Nurse sees exactly three sidebar items: My call list, Patients, Handoff.
- A nurse cannot see Approvals, Audit or Export (and gets a polite message if they type the URL).
- After the nurse presses **Ask doctor** on Rajesh's flag, the doctor home shows it with the nurse's name and time.
- The handoff shows each patient once, with at most 5 lines.

**Show me:** nurse home next to doctor home (they must look clearly different), a call log entry, a handoff card.

---

### PHASE 5: Patient app and family view

**Goal:** the patient does; the family supports. Different pages, different words.

**Patient (4 pages)**
1. **Home:** "Hi Aarav", next medicine with **Taken / Skip**, today's checklist, latest **valid** readings with time and quality, a week strip, next appointment with **.ics** download, and the **Family sharing** switch ("Neha can see your medicine status and appointments: On"). The red banner appears only when a real urgent flag exists; otherwise a calm info line or nothing.
2. **Medicines:** today's doses grouped by time of day, plus a **Calendar tab** (month grid, day detail). Not confirmed and Skipped are shown as different states. Undo for 5 minutes.
3. **Check-in:** pain 0 to 10 buttons, symptom chips, optional note or voice, send. Short history (7 days). Emergency words or chips show guidance first.
4. **Ask my papers:** assistant with source chips; patient messages right-aligned and assistant left-aligned; "Ask my care team" button for not-found answers; one task per topic.

**Family helper (3 pages) with a genuinely different view**
1. **Today** (kicker "FAMILY VIEW", title "Aarav's recovery, for family"):
   - **"What you may need to do"** card: if an escalation reached the family, show a plain message such as "The care team is checking on Aarav. Please contact him." (no diagnosis details). Otherwise "Nothing needed right now."
   - Today's doses: status only (Taken, Not yet, Not confirmed). Button **"I helped Aarav take it"** records the dose as confirmed by Family (not by the patient).
   - Latest valid reading with time (no clinical wording), "Check-in sent today: Yes/No" (no text), next appointment with Add to calendar.
   - Badge: "Sharing allowed by Aarav on 27 Oct". If sharing is off: "Aarav has turned sharing off", and nothing else is shown.
2. **Calendar:** appointments and a simple dose history strip.
3. **Contacts:** a clear **Call 112** card, the care team phone (from staff data), and what to do if the patient is confused or has chest pain (only the 112 line already used in the app).
- The family **cannot**: see check-in text, pain details, the chat, notes, limits, or flags; submit a check-in; ask the assistant.

**Acceptance checks**
- Patient and family home pages are visibly different (title, cards, buttons, sidebar).
- Family confirming a dose is recorded as "Family" in the dose log and the audit log.
- Turning sharing off on the patient side instantly changes the family page.
- Pulse "450 bpm Invalid" no longer appears as the headline reading.
- Hindi toggle works on patient and family pages.

**Show me:** patient home and family home side by side, the sharing switch before and after, a dose confirmed by family in the audit log.

---

### PHASE 6: The one connected demo story and the landing page

**Goal:** a 6 to 7 minute story where **one event** travels through all four logins.

**Tasks**
1. **Add a "Reset demo" command** (CLI and, optionally, a small button hidden in the doctor "More" menu): restores the Section 4 starting state in under 30 seconds. Print "Reset complete: 5 patients, 3 open flags, 5 tasks".
2. **Add a "Send test reading" helper** (simulator command or a small hidden control) that sends Aarav's low SpO₂ reading so the live event is repeatable.
3. **Write `docs/DEMO_SCRIPT.md`** using the script in Section 7, with the exact logins, passwords, URLs and what to click.
4. **Landing page simplification:**
   - Keep: hero, four role cards, a "How a day works" strip with 5 steps, safety and privacy cards, footer note "Sample data. Not medical advice."
   - Make each **role card say the one-line pitch** from Section 2.1 and show its own accent colour.
   - Replace the "Clinical Follow-Up Targets" block and the claim-style numbers (98.2%, 83.6%, 100%, "aims to prevent readmissions", "hardware-verified") with **real counts read from the database** or remove them.
   - Keep the sign-in details visible on the role cards for the judges.
5. **Judge cheat-sheet** (`docs/JUDGE_CHEATSHEET.md`): the 30-second pitch, the four one-liners, the demo steps with timings, the numbers on screen, and the "do not say" list (Section 8).

**Acceptance checks**
- A teammate can run the whole demo from `DEMO_SCRIPT.md` without help, twice in a row after resets.
- The live event (low reading) produces: a patient banner, a family message, a nurse call-list row, a doctor decision item, an audit trail.
- Landing page has no claim that the app cannot prove.

**Show me:** a screen recording or screenshots of each step, plus the output of two resets.

---

### PHASE 7: Quality, claims audit and judge rehearsal

**Goal:** nothing breaks on stage and every statement is true.

**Tasks**
1. **Tests:** run the full suite. Add or keep tests for: role permissions (Phase 2), family consent, seed validation, dose actions and undo, flag lifecycle, escalation ladder with consent, emergency keyword path (EN and HI), AI summary guard (no banned words, numbers must match facts), assistant refusal for dose-change, assistant source chips.
2. **Visual check:** screenshots of every page for all four logins in light and dark; confirm no style drift compared with the Phase 1 baseline. Confirm the four first screens look clearly different.
3. **Claims audit:** search the whole interface and README for banned wording: "stable", "normal", "optimal", "improving", "prevents", "validated", "hardware-verified", "100%", "AI detected", any hard-coded medical threshold. List every hit and fix it.
4. **Data audit:** run `validate_demo.py` again, then click through every page as every login and note anything that looks odd (duplicate rows, raw enum words, minutes instead of hours, missing names).
5. **Performance and reliability:** pages load in under 1 second with the small data; the demo works with the LLM turned off (drafts fall back to the plain fact sheet; assistant says it is unavailable; emergency path still works).
6. **Backup plan:** a 3-minute screen recording of the full story, a printed or PDF copy of the demo script, and a spare browser profile per login.
7. **Rehearsal:** run the story three times with a timer. Prepare answers for the questions in Section 9.
8. **README:** what each role does, how to reset the demo, the four logins, and the sentence "Synthetic-data prototype, not a medical device."

**Acceptance checks:** all tests pass; claims audit empty; two clean resets and runs; the recording exists.

---

## 7. The demo story (6 to 7 minutes, one event, four logins)

| Time | Who | What happens | What the judges learn |
|---|---|---|---|
| 0:00 | Landing page | "Four people, four jobs." Point at the four role cards | The system is role-based |
| 0:30 | **Patient (Aarav)** | Home shows next medicine, taps **Taken**. Opens Check-in, sends a mild pain 2 note. Asks "When is my next appointment?" and sees the answer with its **source chip**. Asks "Can I double my dose?" and gets the **refusal** | Patient does; AI answers only from papers and refuses dose advice |
| 2:00 | **Presenter** | Runs "Send test reading" (low SpO₂ for Aarav) | A reading arrives from the watch (simulated) |
| 2:15 | **Patient** | Banner appears: "Your care team has been told. Call 112 if you have chest pain." | The patient is told, calmly, with an action |
| 2:30 | **Family (Neha)** | Refresh: "What you may need to do: The care team is checking on Aarav. Please contact him." She taps **I helped Aarav take it** on a dose | The family is informed (no medical details) and has a small, useful job |
| 3:15 | **Nurse (Priya)** | My call list shows Aarav on top with a timer and the real reason ("SpO₂ reading 91% is below the approved limit of 94"). She presses **Call**, logs "Reached, advised to rest and recheck", then **Ask doctor** | The nurse works the queue and escalates; the reason is explainable |
| 4:15 | **Doctor (Dr. Sharma)** | Needs my decision shows Aarav (nurse's note) and Rajesh's emergency item. Opens the flag drawer: evidence, **who approved the limit**, ladder. **Resolve** with a note. Opens Approvals, reads the AI summary with **Sources**, edits one line, **Approves** | The doctor decides; AI is a draft; humans approve |
| 5:30 | **Doctor → More → Audit** | Last 20 events: reading, flag, family message, call, escalation, resolve, approval | Everything is logged |
| 6:00 | **Patient Home** | Switch **Family sharing: Off**. Switch to the family login: "Aarav has turned sharing off." | Consent is real |
| 6:30 | Close | "The LLM talks. Rules decide. Humans act." | The principle |

---

## 8. Say and do not say

**Say:** "Prototype with sample data." "Rules raise flags, the AI explains." "The nurse can resolve routine flags; urgent ones need the doctor." "Every action is logged." "The family only sees what the patient allows." "Limits are set and approved by the doctor."

**Do not say:** "prevents readmissions", "clinically validated", "100% accurate", "AI detects problems", "hardware-verified", "stable", "normal", "safe". Do not read out any medical threshold as a protocol.

---

## 9. Likely judge questions and short answers

| Question | Answer |
|---|---|
| Why four roles? | Patients act, families help and get informed with consent, nurses work the queue, doctors decide and approve. Different jobs, different screens, different permissions |
| Does the AI make medical decisions? | No. Rules raise flags. The AI only answers from the patient's own papers with sources and writes drafts that a doctor must approve |
| What if the watch gives a wrong value? | Impossible values are stored as Invalid and never raise a flag. Silence is flagged as missing data, not treated as normal |
| What if nobody responds? | The escalation ladder moves from patient to family (if consent) to nurse to doctor, with timers, and every step is logged |
| How do you protect privacy? | Role-based access, family sees only allowed items, patient can turn sharing off, every access and action is in the audit log, data is synthetic |
| Is the data real? | No. Synthetic people, invented medicine names, demo limits |
| Why not just a normal reminder app? | It closes the loop: alerts have owners, reasons, time targets, escalation and a record |
| How would you scale it? | Same design; add assignments, more staff, real device onboarding, hospital integration through standard formats (FHIR export exists as a first step) |
| What are the limits? | Prototype, sample data, demo thresholds, simulated watch, not a medical device, needs clinical validation and regulatory review before real use |

---

## 10. Final checklist before the demo

- [ ] Four logins land on four clearly different first screens.
- [ ] Nurse cannot open Approvals, Audit or Export. Family cannot see chat, symptom text or notes.
- [ ] Reset gives 5 patients, 3 open flags, 5 open tasks, 3 summaries, about 30 audit events.
- [ ] No test strings, duplicate rows, "450 bpm" headline, hard-coded medical thresholds or unprovable claims.
- [ ] The live event works three times in a row.
- [ ] The backup recording and printed script exist.
- [ ] Each teammate can say the four one-liners without notes.

---

## 11. What I want from Antigravity after each phase
1. Plain-language summary of what changed and why (files listed).
2. Real command output for tests, resets and validation.
3. Screenshots for **all four logins** (light and dark) of every changed screen.
4. Anything that looked like a bug, a data problem or a false claim that you did not fix.
5. What you did not test and every assumption you made.
6. The next phase's plan, then wait for my approval.

**Ask me before:** deleting data that is not clearly test data, changing a stored procedure, adding a table, adding a library, or changing who may resolve which flags.
