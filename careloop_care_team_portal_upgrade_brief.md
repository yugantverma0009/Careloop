# CareLoop Care Team Portal Upgrade: Antigravity Build Brief

**Goal:** turn the current staff pages (Who needs attention, Patient timeline, Follow-up tasks, Draft summaries) into a trustworthy daily working tool for doctors and nurses, using practices that are standard in current remote-monitoring and post-discharge care, **without changing the visual style**.
**Scope:** the staff area (`/staff`) and the backend endpoints, views and procedures it uses. Landing, login and the patient portal must stay as they are.
**Guiding rule:** *The LLM talks. Rules decide. Humans act.*

> Written from four screenshots and the earlier project files, **not from your code**. Antigravity must read the code first (Phase 0) and report where reality differs. All data is synthetic. Thresholds, timings and targets are demo values that clinicians must set. Standards and regulations change: **verify the current version of every standard mentioned (Section 4) before implementing**, and treat the compliance notes as engineering guidance, not legal advice.

---

## 0. How to use this file

1. Put this file in the project root next to `careloop_master_project_document.md`, `careloop_mysql_v2_detailed.sql` and `careloop_patient_portal_upgrade_brief.md`.
2. Paste this launcher prompt into Antigravity:

```
Read careloop_care_team_portal_upgrade_brief.md completely. Also skim careloop_master_project_document.md and careloop_mysql_v2_detailed.sql.
Work on a new git branch named care-team-portal-upgrade.
Follow the brief phase by phase (Section 14). Start with Phase 0 (read-only audit, data-integrity diagnosis and style lock) and STOP for my approval before changing any code or data.
Do not change the visual style: reuse existing components, colours, fonts, spacing, icons and the dark/light theme.
Never break the safety and clinical-governance rules in Section 2.
If the brief conflicts with the real code, tell me instead of guessing.
After every phase show real command output, screenshots, and the list of what you did NOT test.
```

---

## 1. Mission, scope and the style lock

### 1.1 In scope
- Staff pages: worklist (flags), patient detail and timeline, tasks, draft summaries, plus new pages listed in Section 6.
- Backend endpoints, SQL views and procedures used by those pages.
- Seed data repair so every page shows consistent, believable synthetic data.

### 1.2 Out of scope
- Landing, login, patient portal (they have their own brief).
- Hardware, simulator, the rule engine logic itself (except changes explicitly listed here and approved).
- New colours, fonts, icon libraries or UI kits.

### 1.3 Style lock (mandatory)
Before any code, create `docs/STYLE_LOCK_STAFF.md` listing the existing tokens and components used on the staff pages: colour variables (light/dark), font and sizes, radii, shadows, spacing, stat card, severity pill, status pill, table row, primary (dark) and secondary (outlined) buttons, filter chips, sidebar item with count badge, search bar, notification bell, theme toggle.
- New screens are composed only from those components. Missing ones (drawer, tabs, timeline row with chart, task row with SLA chip) are built from the same tokens and listed in the style lock as "new, built from existing tokens".
- Take baseline screenshots now (light and dark) of landing, login, patient portal and every staff page. After each phase compare: unchanged pages must match within 0.1% of pixels.

---

## 2. Non-negotiable safety, honesty and clinical-governance rules

1. **Patient identification first.** Every place that shows a patient shows at least **two identifiers** (full name plus age and patient code, for example "Aarav Patel · 58 y · CL-00001"). A page must never show a name that disagrees with the record behind it. Mismatches are a stop-the-line defect (see Section 3, item 1).
2. **The AI never decides.** No LLM output may create, close or change a flag, task, rule, prescription or patient-facing instruction. AI text is a **draft** that a named clinician approves.
3. **No clinical judgment words in system text.** Do not write "stable", "normal", "improving", "deteriorating", "safe", "concerning", "recovering well", "abnormal" in generated or templated text. State facts: value, unit, time, quality, and the clinician-approved rule that fired.
4. **Every alert must be actionable and explainable:** the real reason, the evidence, the rule and who approved it, the owner, the next step, the time target.
5. **Alert fatigue is a safety problem.** Deduplicate, group per patient, tier by severity, show owners and ages. Never show 40 identical rows.
6. **Closed loop.** A flag is not "done" until someone with a name resolves or dismisses it with a reason code (and a note for urgent ones). Acknowledging is not resolving.
7. **Append-only accountability.** State changes write rows to `flag_events` and `audit_log`. Notes are amended, never overwritten.
8. **Least privilege.** Staff see assigned patients by default. Looking at others requires a recorded reason ("break-glass"). Exports are logged.
9. **Honest numbers.** Every number on screen is computed from real data with a definition. No outcome claims ("reduced readmissions", "risks identified early").
10. **Data quality is visible.** Readings show quality (Good, Questionable, Invalid, Simulated). Missing data is shown as missing.
11. **Dose, diagnosis and treatment decisions stay with clinicians.** The portal records what a clinician decided; it does not recommend treatment.
12. **No names or contact details sent to the LLM.** Use patient code or "the patient". Insert names afterwards in code.

---

## 3. What the current screens show (findings)

| # | Where | Observation | Severity | Fix |
|---|---|---|---|---|
| 1 | Worklist, Tasks, Draft summaries | **Name mismatches.** A flag row for "Meera Sharma, PID #2" has text "Patient #1 (Aarav Patel)". A task for "Patient: Meera Sharma" says "Contact Sunita Rao regarding Congestive Heart Failure...". "Draft Summary #9, Patient: Aarav Patel" describes "Patient #9, Arjun Nair". A wrong-patient display is a patient-safety defect | **Critical** | Diagnose first (Section 7.1), repair seed/mapping, add automated consistency tests (D-01) |
| 2 | Worklist | Reason text is generic ("Clinical recovery threshold logged for monitoring team review.") and hides the real rule reason | High | Show `flags.reason` verbatim plus evidence and rule (D-03) |
| 3 | Worklist | 66 open flags, 53 urgent, every score is 100. Nothing is distinguishable | High | Group per patient, tiers, dedupe, explainable attention score (D-02, D-04) |
| 4 | Worklist | Identical emergency flags repeat (same patient, same second). Timeline shows two emergency flags 1 second apart | High | Dedupe window, grouping, duplicate fix (D-04, Section 7.3) |
| 5 | Worklist | Rows with "Status: Acknowledged" still show an **Acknowledge** button | High | Correct actions per state (D-03) |
| 6 | Worklist | "Raised at" shows time only (21:31:08). No date, no age, no SLA, no owner | High | Absolute date plus age plus SLA chip plus owner (D-02) |
| 7 | Worklist | "Immediate review 0" next to "Urgent review 53" with no definition of tiers | Medium | Define tiers (Section 6, D-02) |
| 8 | Sidebar | Counts 66 / 95 / 5 are all-time totals, not "mine" or "needs action" | Medium | Counts reflect the current filter and role |
| 9 | Timeline | Patient chips are "Patient #1..#10" (no names). Every row says "Patient #1 · Event log" | High | Names with identifiers, remove noise (D-05, D-06) |
| 10 | Timeline | Future doses shown as "Unconfirmed" (20:00 today when it is 11:16) | Medium | "Scheduled" until due (D-06) |
| 11 | Timeline | Test text leaks into records ("Dictated via microphone test at 1793252346.744534", "Identical submission test") | Medium | Clean seed, exclude test rows (D-23) |
| 12 | Timeline | Flat list. No filters, no day grouping, no vitals chart | High | Filters, day groups, readings chart with rule lines (D-06) |
| 13 | Tasks | 95 tasks with no actions: cannot claim, call, complete, snooze or add a note | High | Real work queue (D-07) |
| 14 | Tasks | Raw enum text "Urgent_Review", "Review_Soon". "Pending: 240.4h" with no overdue emphasis | Medium | Human labels, due time, overdue state |
| 15 | Tasks | Acknowledging a flag creates a task every time, which is why there are 95 | Medium | Make task creation a choice (Section 7.2) |
| 16 | Draft summaries | Every draft is the same template: "Continuous vitals stable", "Pain reported at 6/10", "Morning doses confirmed" for different patients. "Stable" is a judgment | High | Fact-sheet-based drafts, no judgment words, sources (D-08) |
| 17 | Draft summaries | Only Approve / Reject. No edit, no sources, no reject reason, no record of who approved what text | High | Edit, sources, reasons, versioning (D-08) |
| 18 | General | No patient detail page, no handoff, no communication log, no notes, no assignment, no rules view, no audit view, search box inactive | High | New features (Section 6) |
| 19 | General | Priority score "100" without explanation | Medium | Show factors; make tier primary |

---

## 4. What current practice looks like (and what we take from it)

| Practice or standard | What it means for this portal | Priority |
|---|---|---|
| **Two-identifier patient identification** (widely required in hospital safety programmes) | Name plus age and patient code on every row, drawer and export. Automated mismatch tests | P0 |
| **Clinical alarm and alert management** (alarm fatigue is a recognised patient-safety issue) | Tiering, grouping, deduplication, ownership, escalation, measuring alert burden | P0 |
| **Closed-loop communication and task ownership** | Owner, due time, outcome code, resolution reason, audit trail | P0 |
| **Structured handoff (SBAR, I-PASS)** | Shift handoff view with fixed sections | P1 |
| **Human-in-the-loop AI documentation** | AI drafts only, shows sources, clinician edits and approves, record of who approved what | P0 |
| **Protocol-driven remote monitoring** (condition pathways) | Pathway templates whose thresholds a doctor must fill and approve per patient | P2 |
| **Interoperability: HL7 FHIR R4 and ABDM** | In India the ABDM FHIR Implementation Guide (published by NRCeS for NHA, FHIR R4) defines the data exchange profiles; ABHA is the health ID; records move between HIPs and HIUs with patient consent through the ABDM gateway; developers integrate through the ABDM sandbox milestones. Provide a **FHIR export** (not a claim of ABDM certification) and keep an optional ABHA address field | P2 |
| **India data protection (DPDP Act 2023 and DPDP Rules 2025)** | The Rules were notified in November 2025 with phased commencement; core obligations (notices, consent, purpose limitation, retention and erasure) are due around May 2027 and consent-manager provisions earlier. Design for: clear purpose and consent records, access logging, minimum access, retention settings, export and erasure workflows, breach readiness | P1 |
| **Readmission-risk context (LACE index)** | Optional, clinician-entered, transparent calculation shown as context only. Published evidence on LACE is mixed, so it never drives alerts by itself | P2 |
| **Operational quality metrics** | Time to acknowledge, alerts per patient per day, overdue work, false-alarm dismissals. No outcome claims | P2 |
| **Security baseline** | Role-based access, assignment-based access, idle timeout, audit trail, optional MFA | P1 |
| **Regulation of clinical software** | If the system ever moves beyond a prototype, get regulatory advice (for example on software as a medical device) before real use | note |
| **Telemedicine rules** | If you add phone or video consults, check the Indian telemedicine practice guidelines for documentation requirements | note |

---

## 5. New care-team experience

### 5.1 Navigation (same sidebar style)
`Who needs attention` · `Patients` (new) · `Follow-up tasks` · `Draft summaries` · `Shift handoff` (new) · `Care rules` (new, doctors) · `Insights` (new) · `Audit log` (new)
Keep the existing "Patient timeline" as a tab inside the patient page; keep a sidebar link that opens the patient picker.
Sidebar counts: **my** open items that need action (not all-time totals).

### 5.2 Worklist (Who needs attention), wireframe

```
Who needs attention first                         [Mine | Team | Unassigned]  [Tier ▾] [Status ▾]  [Export]
Cards: Immediate 1 | Urgent 4 | Review soon 9 | Not yet seen 7 | Overdue 3

┌ ● URGENT  Aarav Patel · 58 y · CL-00001 · Post-CABG day 3          Owner: unassigned ┐
│ Emergency report ×3 · Missed doses ×2                                                │
│ First 29 Oct 08:33 · Latest 29 Oct 11:09 · Target: seen within 2 h · OVERDUE 1 h 20m│
│                                              [Acknowledge]  [Open patient]  [▾ 5]   │
└──────────────────────────────────────────────────────────────────────────────────────┘
   (expanded) each flag: reason · evidence · rule · time · [Resolve] [Dismiss] [Assign]
```

### 5.3 Patient page, wireframe

```
Aarav Patel · 58 y · CL-00001 · Post-CABG · Day 3 after discharge · Attending: Dr. Ananya Sharma
Caregiver: consent recorded ✓ · Device: Online (last seen 11:09)        [Add note] [Log call] [Create task]
Tabs: Overview | Timeline | Medicines | Check-ins | Rules | Notes & calls | Documents | Audit

Overview:
[Open flags 2]  [Latest readings with quality + time]  [Adherence, last 7 days grid]
[Pain, last 14 days]  [Device status]  [Next appointment]  [Draft summary waiting]
```

### 5.4 Principles
- One click from any flag to its patient and from any patient to their open work.
- Real names and identifiers everywhere, never "Patient #3".
- Same components and tokens as today. Dense but readable tables, keyboard shortcuts for the heavy actions.
- Every empty state says what is empty and why ("No open flags for your patients").

---

## 6. Feature specifications

Priority: **P0** must ship, **P1** should ship, **P2** if time allows.

### D-01 Patient identity integrity (P0, do first)
- Add `patients.patient_code` (synthetic, for example `CL-00001`, unique, not derived from real IDs).
- Create a shared `PatientIdentity` component: name, age, patient code, condition. Use it in the worklist, tasks, summaries, timeline, drawers and exports.
- Build `scripts/check_identity_consistency.sql` and an automated test that fails if any flag, task or summary text names a patient who is not the record's patient.
- Fix the root cause (seed generator or join), not just the display. Show the diagnosis in `docs/DATA_INTEGRITY_REPORT.md` (Section 7.1).
- Acceptance: zero mismatches across `flags`, `follow_up_tasks`, `ai_summaries`; the test runs in CI.

### D-02 Worklist rebuild (P0)
- **One row per patient** (collapsed) from `v_worklist_by_patient`: highest severity, count of distinct reasons, first and latest raised time (with date), owner, SLA chip. Expand to see individual flags.
- **Tiers** (define on screen):
  - Immediate = open Emergency-source flag (target under 15 min, configurable)
  - Urgent = `Urgent_Review` severity (target under 2 h)
  - Review soon = `Review_Soon` (target within a working day)
  - Routine = `Info`
  Targets are config values (`SLA_IMMEDIATE_MIN`, `SLA_URGENT_MIN`, `SLA_REVIEW_SOON_HOURS`) and labelled "target", never as a promise.
- **Scope filter:** Mine, Team, Unassigned. **Status filter:** Not yet seen (Open), Seen (Acknowledged), Closed (Resolved/Dismissed, hidden by default).
- **Sorting:** tier, then overdue-first, then oldest.
- **Attention score:** keep the number as a secondary column, but show its factors on hover or in the drawer. Make it meaningful: count each distinct *reason* once (not once per duplicate flag) and cap each factor, otherwise everything saturates at 100 (the current symptom). Weights are demo values that need clinician approval.
- Summary cards: counts by tier, not-yet-seen, overdue. They must equal what the table shows with the same filters.
- Search box (Ctrl+K) searches patient name, code, flag reason and task text.
- Acceptance: with 66 flags in the old data, the page shows about one row per affected patient; counts are consistent; no all-100 column.

### D-03 Flag detail drawer and state actions (P0)
Opens from a flag. Shows:
- **Why:** the exact reason text, severity, tier, created time, age.
- **Evidence:** the reading (value, unit, time, quality, device), or the symptom report text (pain, chips, language), or dose logs, depending on `source_type`; link to the exact timeline entry.
- **Rule:** rule type, threshold, who approved it and when (`alert_rules`). If no rule (patient-requested or emergency keyword), say so.
- **Escalation ladder** (D-10).
- **History:** `flag_events` (created, acknowledged by whom, notes, resolved).
- **Actions by state:**

| State | Primary | Others |
|---|---|---|
| Open | Acknowledge (takes ownership) | Assign to someone, Add note, Dismiss as false alarm (with reason), Open patient |
| Acknowledged | Resolve | Log call, Create task, Add note, Reassign, Reopen not allowed |
| Resolved / Dismissed | none | Reopen (doctor, with reason) |

- **Resolve** needs a reason code: No action needed, Patient contacted, Appointment arranged, Referred to emergency care, Device or data issue, Duplicate. **Urgent and Immediate flags need a note of at least 5 characters.**
- **Dismiss as false alarm** needs a reason and feeds rule-quality counts (D-13).
- Two staff acting at once: the first wins; the second gets a clear message ("Already acknowledged by Priya Nair at 11:12").
- Acceptance: acknowledged rows never show Acknowledge; every action writes `flag_events` and `audit_log`.

### D-04 Deduplication and grouping (P0)
- Group by (patient, source type, rule) inside the worklist: "Emergency report ×3, first 08:33, last 08:35".
- Stop creating duplicate emergency flags at the source (trigger change in Section 7.3, needs my approval). Staff still see every report in the timeline.
- Clean existing duplicates with a script that marks extras `Dismissed` with reason `Duplicate` and an audit note. Ask before running it.

### D-05 Patient directory and patient page (P0 overview; P1 other tabs)
- **Patients** list: name, age, code, condition, discharge date and day number, attending doctor, open flag count, device status, last check-in, adherence this week. Filters: mine, all, has open flags, device silent.
- **Overview tab (P0):** open flags, latest readings with quality and time, adherence grid for 7 days (dose by day), pain over 14 days, device status, next appointment, draft summary waiting, caregiver consent status.
- **Medicines tab (P1):** the discharge medicine list (name, schedule, start and end dates) and an adherence grid; list of Not confirmed and Skipped with reasons. Wording: "Self-reported", not "adherence outcome".
- **Check-ins tab (P1):** pain chart with notes and tags; the emergency-keyword reports highlighted.
- **Rules tab (P1):** this patient's rules, threshold, approver, date; see D-13.
- **Notes & calls tab (P1):** D-15 and D-16.
- **Documents tab (P2):** the discharge papers and sections used by the assistant.
- Break-glass for non-assigned patients (D-12).

### D-06 Timeline upgrade (P0)
- Patient picker by name and code (no "Patient #3").
- **Filter chips:** Readings, Symptoms, Doses, Flags, Calls, Notes. **Date range** and "Today / 7 days / All".
- **Grouped by day** with sticky date headers. Collapse repeated events ("Emergency flag ×2").
- **Readings chart** (heart rate and SpO₂) in the existing chart style, with quality markers (Good, Questionable, Invalid, Simulated) and the patient's approved rule lines drawn as dashed lines, labelled "approved limit".
- Future doses show **Scheduled**, not Unconfirmed. Past unconfirmed doses show **Not confirmed**.
- Remove the repeated "Patient #1 · Event log" text. Show the actor ("Patient", "System rule", "Dr. Sharma").
- Pagination or infinite scroll with a cursor; 200 rows per request maximum.
- Acceptance: the Timeline for one patient loads in under 1 s with 5,000 events.

### D-07 Follow-up tasks as a real queue (P0)
- Columns: Task, Patient (identity), Priority (human labels: Urgent, Review soon, Routine), **Due** (and overdue state), Owner, Status, Source (linked flag), Age.
- Filters: My tasks, Team, Unassigned, Overdue, Status.
- Actions: Claim, Assign, **Log call** (opens D-15 form), Set appointment (opens simple scheduler), **Complete with outcome** (Reached and advised, Appointment set, No answer, Escalated to doctor, No action needed), Snooze with reason and new due time.
- No auto-created duplicates (Section 7.2). A task always has an owner or sits in Unassigned with a visible age.
- Due time defaults from priority via config; clinicians can change it.
- Acceptance: "Pending: 240.4h" becomes an overdue chip with the date it was due; completing a task requires an outcome and writes audit.

### D-08 Draft summaries rebuilt (P0)
Pipeline (build in this order):
1. **Deterministic fact sheet** from SQL (like `sp_daily_report`): discharge date and day number, condition (clinician-entered text), medicines and counts (taken, skipped, not confirmed), latest readings with time and quality, device last seen, check-ins with pain and tags, open flags with reasons, appointments. No names.
2. **LLM rewrite** into a fixed structure (SBAR) using the prompt in Section 10.2.
3. **Guard:** every number, date and time in the draft must appear in the fact sheet; no banned judgment words; every section non-empty. On failure, show the plain fact sheet instead of the AI text.
4. **Store:** `ai_summaries` with `status = Draft`, the `source_snapshot` JSON (the fact sheet), model name and time.
UI:
- Header with patient identity, period covered, model, generated time, "AI draft, not reviewed".
- **Sources panel:** the facts the draft was built from, each linkable to its timeline entry.
- **Edit** in place. **Approve** records approver, time and the final text (`edited_text`), keeping the original. **Reject** needs a reason.
- Approved summaries show "Approved by Dr. X, 29 Oct 14:20" and become read-only (amend through a new version).
- **Generate drafts for my patients** button with progress; never create two drafts for the same patient and period.
- Acceptance: no "stable", no copy-pasted pain value across patients, numbers match the source snapshot, a mismatching name is impossible (name is inserted by code from `patient_id`).

### D-09 Shift handoff (P1)
A page that produces a per-shift handoff for my patients using I-PASS style sections, built from data (not AI):
- **Illness/attention tier** (from flags only: Immediate, Urgent, Review soon, Routine; no "stable/unstable").
- **Patient summary:** condition, day number, key facts.
- **Action list:** open tasks with owners and due times.
- **Situation awareness and contingency:** open flags, silent devices, upcoming appointments, "if X happens call Y" text entered by the outgoing clinician.
- **Synthesis by receiver:** the incoming clinician ticks "Received" per patient (recorded with time).
- Print or PDF export (logged). Optional AI wording is a draft and never replaces the data.

### D-10 Escalation visibility (P0)
Per flag, show the ladder as a timeline: Patient prompt, Caregiver SMS (or "Skipped: no consent"), Nurse alert, Doctor alert, with status, time, and a countdown to the next step. Acknowledging stops the ladder and says so. "Escalate now" button (confirmation required) writes an escalation row and audit entry.

### D-11 Notifications (P1)
- The bell lists items needing action for me: new urgent or immediate flags, flags escalated to me, tasks due within the hour, tasks overdue.
- Urgent items get a distinct, non-dismissable-by-accident style; routine items do not interrupt.
- Optional browser notifications for Immediate and Urgent only, with a plain permission prompt. No promise of background delivery.
- Snooze is allowed for Routine only.

### D-12 Assignment and access control (P1)
- New `care_assignments` table (doctor, nurse, backup). The worklist defaults to **Mine**.
- Doctors see patients they attend; nurses see their assigned patients. Others require **break-glass**: a reason is typed, the access is logged (`audit_log`, action `BREAK_GLASS_VIEW`), and the page shows a banner "Viewing outside your assignment".
- Only doctors can approve summaries and rules.
- Idle timeout (15 minutes, config) with return to login; confirm password to approve a summary or rule (P2: optional MFA).

### D-13 Care rules and pathway templates (P1 view, P2 templates)
- **Rules tab:** each rule with type, threshold, window, severity, approver, approved time, active flag, fired count (last 30 days), dismissed-as-false count.
- **Propose a change:** nurses can propose; doctors approve. Changes are versioned in `alert_rules_history` (old value, new value, who, when, reason). Rules are never edited in place without history.
- **Pathway templates (P2):** named templates (for example post-cardiac procedure, post joint replacement, pneumonia, post-DKA) listing rule *types* with **blank thresholds**. A template can only be applied after a doctor fills every threshold and approves. The system ships **no default medical thresholds**.

### D-14 Operational insights (P2)
Page with plain tables and the existing chart style, date range filter, CSV export (logged). Metrics with definitions:

| Metric | Definition |
|---|---|
| Median time to acknowledge | `acknowledged_at - created_at` for flags in range, by tier |
| Within target | % of flags acknowledged within their tier target |
| Open flags by age | counts in buckets (under 1 h, 1-4 h, 4-24 h, over 24 h) |
| Alerts per patient per day | distinct flags per monitored patient per day |
| Duplicate rate | flags marked `Duplicate` / all flags |
| False-alarm dismissals | `Dismissed` with reason `False_Alarm` / all closed, by rule |
| Self-reported dose confirmation | taken / (taken + skipped + not confirmed) from `medication_logs` |
| Device uptime | % of expected readings received |
| Overdue tasks | tasks past `due_at` and not completed |
Do not show outcome metrics (readmissions, recovery rate). No benchmarks against other hospitals.

### D-15 Communication log (P1)
- "Log call" or "Log message" from the flag drawer, task row or patient page: channel (Phone, SMS, In person, Video), outcome (Reached, No answer, Left message, Wrong number, Declined), short summary, links to flag or task. Saved in `contact_log` and `audit_log`.
- Phone numbers open as `tel:` links on devices that support it.
- SMS templates for staff: short, no diagnosis details. Preview before sending. In demo mode SMS is logged, not sent.

### D-16 Clinical notes (P1)
Per patient: type (Review, Call, Plan change, General), text, author, time. **Append-only:** corrections are new notes with `amends_note_id`. Notes appear in the timeline.

### D-17 Audit log viewer (P1)
Filter by patient, staff, action, date. Shows who viewed (break-glass), exported, acknowledged, resolved, approved, changed a rule. Read-only; export is itself logged.

### D-18 Data-quality indicators (P0)
On the patient overview and flag evidence: a small label for Questionable, Invalid and Simulated readings; a "No reading since 09:15" notice from `v_device_status`; "Caregiver has not consented" where relevant.

### D-19 FHIR export (P2)
`GET /staff/patients/{id}/fhir` returns a FHIR R4 JSON bundle for follow-up data. Suggested mapping (verify against the current ABDM implementation guide and FHIR R4 before relying on it):

| CareLoop | FHIR R4 resource | Notes |
|---|---|---|
| patient | Patient | identifier slot for patient code; optional ABHA address only with consent |
| heart rate reading | Observation (vital-signs) | LOINC 8867-4 |
| SpO₂ reading | Observation (vital-signs) | LOINC 59408-5 (pulse oximetry) or 2708-6; quality noted in `Observation.note` or an extension |
| prescription | MedicationRequest | dose text copied verbatim |
| dose confirmation | MedicationAdministration or MedicationStatement | self-reported flag |
| symptom report | Observation or QuestionnaireResponse | patient-reported |
| flag | Flag | with reason text |
| follow-up task | Task | owner, due, outcome |
| appointment | Appointment | |
| staff message | Communication | |
| approved summary | Composition | only approved ones |
Do **not** claim ABDM certification. ABDM integration requires registration and the sandbox milestones (ABHA, HIP, HIU) and the patient's consent through the gateway. Export is logged. P2 only.

### D-20 LACE context (P2, optional)
- Clinician-entered inputs stored in `risk_context`: length of stay (days), acute admission (yes/no), Charlson comorbidity index, ED visits in the previous 6 months.
- Score is computed by the published rule (0 to 19): length of stay <1 day 0, 1 day 1, 2 days 2, 3 days 3, 4-6 days 4, 7-13 days 5, 14 or more 7; acute admission +3; Charlson 0/1/2/3 as 0/1/2/3 and 4 or more 5; ED visits 0-3 as the count and 4 or more 4. **Verify against a primary source before shipping.**
- Display "LACE 12 (clinician-entered, context only)". It is **never** used to create flags unless a doctor approves a specific rule, and the screen says that published evidence on LACE is mixed.

### D-21 Search and keyboard use (P1)
Ctrl+K works: patients by name or code, flags, tasks, notes. Keyboard: `j/k` move, `a` acknowledge, `r` resolve, `o` open patient, `?` shows shortcuts. All actions also work with the mouse.

### D-22 Accessibility and layout (P0)
Contrast at least WCAG AA in light and dark; color is never the only signal (tier text and icon); focus ring in the existing style; tables usable with keyboard and screen readers; drawers trap focus and close with Esc; works from 1280 px width up (desktop first; tablets nice to have).

### D-23 Seed and data hygiene (P0)
- Rebuild a believable synthetic cohort of 10 patients with consistent names, ages, conditions, discharge dates, caregivers (some without consent), devices (one silent), medicines (invented names; ask me before choosing), appointments.
- Observed names and conditions from the current screens (verify against the database): Aarav Patel (post-CABG), Meera Sharma (total knee replacement), Arjun Nair (coronary stent, PCI), Deepa Joshi (total hip arthroplasty), Pooja Gupta (post-DKA), Ananya Iyer (laparoscopic cholecystectomy), Vikram Malhotra (lumbar spinal fusion), Sunita Rao (congestive heart failure), Rajesh Verma (community pneumonia).
- Flags must come from the **real mechanisms** (triggers, procedures, simulated readings and check-ins), not hand-written rows with generic text.
- Remove test strings ("microphone test at 17932...", "Identical submission test") from visible data after my approval.
- Provide `scripts/reset_seed.sql` and `scripts/seed_demo.py`, idempotent, with a validation step that runs the consistency test.

---

## 7. Database changes

### 7.1 Diagnose the identity mismatch first (read-only queries)
```sql
-- 1. What patient does each record point to?
SELECT f.flag_id, f.patient_id, p.full_name, LEFT(f.reason, 90) AS reason
FROM flags f JOIN patients p ON p.patient_id = f.patient_id ORDER BY f.flag_id DESC LIMIT 50;

SELECT t.followup_id, t.patient_id, p.full_name, LEFT(t.reason, 90) AS reason
FROM follow_up_tasks t JOIN patients p ON p.patient_id = t.patient_id ORDER BY t.followup_id DESC LIMIT 50;

SELECT s.summary_id, s.patient_id, p.full_name, LEFT(s.summary_text, 90) AS text_start
FROM ai_summaries s JOIN patients p ON p.patient_id = s.patient_id ORDER BY s.summary_id DESC LIMIT 50;

-- 2. Rows whose text names a different patient than patient_id (adapt the pattern to the real text format)
SELECT 'flag' AS kind, f.flag_id AS id, p.full_name, f.reason
FROM flags f JOIN patients p ON p.patient_id = f.patient_id
WHERE f.reason REGEXP 'Patient #[0-9]+' AND f.reason NOT LIKE CONCAT('%', p.full_name, '%');
```
Report: how many rows, which tables, and the cause (seed script wrong, join wrong, or UI template wrong). Do not delete anything before I approve.

### 7.2 Additive schema changes (add to `database/care_team_upgrade.sql`; do not edit the original silently)
```sql
-- Identity
ALTER TABLE patients ADD COLUMN patient_code VARCHAR(20) NULL;
UPDATE patients SET patient_code = CONCAT('CL-', LPAD(patient_id, 5, '0')) WHERE patient_code IS NULL;
ALTER TABLE patients MODIFY patient_code VARCHAR(20) NOT NULL, ADD UNIQUE KEY uq_patient_code (patient_code);

-- Flag ownership and closure
ALTER TABLE flags
  ADD COLUMN owner_staff_id INT NULL,
  ADD COLUMN resolved_at DATETIME NULL,
  ADD COLUMN resolved_by_staff_id INT NULL,
  ADD COLUMN resolution_code ENUM('No_Action_Needed','Patient_Contacted','Appointment_Arranged',
        'Referred_To_Emergency','Device_Or_Data_Issue','Duplicate','False_Alarm') NULL,
  ADD COLUMN resolution_note VARCHAR(500) NULL,
  ADD CONSTRAINT fk_flag_owner    FOREIGN KEY (owner_staff_id) REFERENCES care_staff(staff_id),
  ADD CONSTRAINT fk_flag_resolver FOREIGN KEY (resolved_by_staff_id) REFERENCES care_staff(staff_id);

CREATE TABLE flag_events (
  flag_event_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  flag_id       BIGINT NOT NULL,
  event_type    ENUM('Created','Acknowledged','Assigned','Note','Escalated','Resolved','Dismissed','Reopened') NOT NULL,
  staff_id      INT NULL,
  note          VARCHAR(500) NULL,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_flagevent_flag  FOREIGN KEY (flag_id)  REFERENCES flags(flag_id) ON DELETE CASCADE,
  CONSTRAINT fk_flagevent_staff FOREIGN KEY (staff_id) REFERENCES care_staff(staff_id),
  INDEX idx_flagevent_flag_time (flag_id, created_at)
);

-- Tasks
ALTER TABLE follow_up_tasks
  ADD COLUMN due_at DATETIME NULL,
  ADD COLUMN completed_at DATETIME NULL,
  ADD COLUMN outcome_code ENUM('Reached_And_Advised','Appointment_Set','No_Answer',
        'Escalated_To_Doctor','No_Action_Needed') NULL,
  ADD INDEX idx_task_due (status, due_at);

-- Summaries
ALTER TABLE ai_summaries
  ADD COLUMN status ENUM('Draft','Approved','Rejected') NOT NULL DEFAULT 'Draft',
  ADD COLUMN edited_text TEXT NULL,
  ADD COLUMN reject_reason VARCHAR(255) NULL,
  ADD COLUMN source_snapshot JSON NULL;

-- Assignment
CREATE TABLE care_assignments (
  assignment_id   INT AUTO_INCREMENT PRIMARY KEY,
  patient_id      INT NOT NULL,
  staff_id        INT NOT NULL,
  assignment_role ENUM('Primary_Doctor','Nurse','Backup') NOT NULL,
  starts_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ends_at         DATETIME NULL,
  CONSTRAINT fk_assign_patient FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
  CONSTRAINT fk_assign_staff   FOREIGN KEY (staff_id)   REFERENCES care_staff(staff_id),
  CONSTRAINT chk_assign_dates  CHECK (ends_at IS NULL OR ends_at > starts_at),
  INDEX idx_assign_staff_active (staff_id, ends_at)
);

-- Communication and notes
CREATE TABLE contact_log (
  contact_id   BIGINT AUTO_INCREMENT PRIMARY KEY,
  patient_id   INT NOT NULL,
  staff_id     INT NOT NULL,
  flag_id      BIGINT NULL,
  task_id      BIGINT NULL,
  channel      ENUM('Phone','SMS','In_Person','Video') NOT NULL,
  outcome      ENUM('Reached','No_Answer','Left_Message','Wrong_Number','Declined') NOT NULL,
  summary      VARCHAR(500) NULL,
  contacted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_contact_patient FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
  CONSTRAINT fk_contact_staff   FOREIGN KEY (staff_id)   REFERENCES care_staff(staff_id),
  CONSTRAINT fk_contact_flag    FOREIGN KEY (flag_id)    REFERENCES flags(flag_id) ON DELETE SET NULL,
  CONSTRAINT fk_contact_task    FOREIGN KEY (task_id)    REFERENCES follow_up_tasks(followup_id) ON DELETE SET NULL,
  INDEX idx_contact_patient_time (patient_id, contacted_at)
);

CREATE TABLE clinician_notes (
  note_id        BIGINT AUTO_INCREMENT PRIMARY KEY,
  patient_id     INT NOT NULL,
  staff_id       INT NOT NULL,
  note_type      ENUM('Review','Call','Plan_Change','General') NOT NULL DEFAULT 'General',
  note_text      TEXT NOT NULL,
  amends_note_id BIGINT NULL,
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_note_patient FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
  CONSTRAINT fk_note_staff   FOREIGN KEY (staff_id)   REFERENCES care_staff(staff_id),
  CONSTRAINT fk_note_amends  FOREIGN KEY (amends_note_id) REFERENCES clinician_notes(note_id),
  INDEX idx_note_patient_time (patient_id, created_at)
);

-- Rule history (never edit rules without a trace)
CREATE TABLE alert_rules_history (
  history_id   BIGINT AUTO_INCREMENT PRIMARY KEY,
  rule_id      INT NOT NULL,
  changed_by_staff_id INT NOT NULL,
  change_reason VARCHAR(255) NOT NULL,
  old_values   JSON NOT NULL,
  new_values   JSON NOT NULL,
  changed_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_rulehist_rule  FOREIGN KEY (rule_id) REFERENCES alert_rules(rule_id) ON DELETE CASCADE,
  CONSTRAINT fk_rulehist_staff FOREIGN KEY (changed_by_staff_id) REFERENCES care_staff(staff_id)
);

-- Optional LACE inputs (D-20)
CREATE TABLE risk_context (
  risk_context_id     INT AUTO_INCREMENT PRIMARY KEY,
  patient_id          INT NOT NULL,
  entered_by_staff_id INT NOT NULL,
  length_of_stay_days SMALLINT NOT NULL,
  acute_admission     BOOLEAN NOT NULL,
  charlson_index      TINYINT NOT NULL,
  ed_visits_6m        TINYINT NOT NULL,
  entered_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_riskctx_patient FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE,
  CONSTRAINT fk_riskctx_staff   FOREIGN KEY (entered_by_staff_id) REFERENCES care_staff(staff_id),
  CONSTRAINT chk_riskctx_values CHECK (length_of_stay_days >= 0 AND charlson_index >= 0 AND ed_visits_6m >= 0)
);
```
Tell me the exact error if any statement fails (the database was not run against these statements here).

### 7.3 Views and procedures
```sql
-- One row per patient for the worklist
CREATE OR REPLACE VIEW v_worklist_by_patient AS
SELECT p.patient_id, p.patient_code, p.full_name,
       TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age_years,
       COUNT(*) AS open_flag_count,
       COUNT(DISTINCT CONCAT(f.source_type, ':', COALESCE(f.rule_id, 0))) AS distinct_reasons,
       MAX(CASE f.severity WHEN 'Urgent_Review' THEN 3 WHEN 'Review_Soon' THEN 2 ELSE 1 END) AS top_severity_rank,
       MAX(f.source_type = 'Emergency') AS has_emergency,
       SUM(f.status = 'Open') AS not_yet_seen,
       MIN(f.created_at) AS first_flag_at,
       MAX(f.created_at) AS latest_flag_at
FROM flags f
JOIN patients p ON p.patient_id = f.patient_id
WHERE f.status IN ('Open','Acknowledged')
GROUP BY p.patient_id, p.patient_code, p.full_name, p.date_of_birth;

-- Optional LACE score view (verify the point table before use)
CREATE OR REPLACE VIEW v_lace AS
SELECT rc.*,
       ( CASE WHEN length_of_stay_days < 1 THEN 0 WHEN length_of_stay_days = 1 THEN 1
              WHEN length_of_stay_days = 2 THEN 2 WHEN length_of_stay_days = 3 THEN 3
              WHEN length_of_stay_days BETWEEN 4 AND 6 THEN 4
              WHEN length_of_stay_days BETWEEN 7 AND 13 THEN 5 ELSE 7 END
         + IF(acute_admission, 3, 0)
         + CASE WHEN charlson_index >= 4 THEN 5 ELSE charlson_index END
         + LEAST(ed_visits_6m, 4) ) AS lace_score
FROM risk_context rc;
```
Replace `sp_acknowledge_flag` (new signature adds `p_create_task`; update the backend call):
```sql
DROP PROCEDURE IF EXISTS sp_acknowledge_flag;
DELIMITER $$
CREATE PROCEDURE sp_acknowledge_flag(IN p_flag_id BIGINT, IN p_staff_id INT, IN p_note VARCHAR(255), IN p_create_task BOOLEAN)
BEGIN
    DECLARE v_patient  INT DEFAULT NULL;
    DECLARE v_severity VARCHAR(20) DEFAULT NULL;
    DECLARE v_reason   VARCHAR(255) DEFAULT NULL;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;

    START TRANSACTION;
    SELECT patient_id, severity, reason INTO v_patient, v_severity, v_reason
    FROM flags WHERE flag_id = p_flag_id AND status = 'Open' FOR UPDATE;
    IF v_patient IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Flag not found or already acknowledged';
    END IF;

    UPDATE flags SET status = 'Acknowledged', owner_staff_id = p_staff_id,
           acknowledged_by_staff_id = p_staff_id, acknowledged_at = NOW()
    WHERE flag_id = p_flag_id;

    UPDATE escalations SET delivery_status = 'Acknowledged', responded_at = NOW()
    WHERE flag_id = p_flag_id AND delivery_status IN ('Queued','Sent');

    INSERT INTO flag_events (flag_id, event_type, staff_id, note) VALUES (p_flag_id, 'Acknowledged', p_staff_id, p_note);

    IF p_create_task THEN
        INSERT INTO follow_up_tasks (patient_id, flag_id, assigned_staff_id, reason, priority, due_at)
        VALUES (v_patient, p_flag_id, p_staff_id, v_reason,
                CASE v_severity WHEN 'Urgent_Review' THEN 'Urgent_Review' WHEN 'Review_Soon' THEN 'Review_Soon' ELSE 'Routine' END,
                NOW() + INTERVAL CASE v_severity WHEN 'Urgent_Review' THEN 2 WHEN 'Review_Soon' THEN 24 ELSE 72 END HOUR);
    END IF;

    INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
    VALUES ('Staff', CAST(p_staff_id AS CHAR), 'ACK_FLAG', 'flag', p_flag_id, JSON_OBJECT('note', p_note, 'task', p_create_task));
    COMMIT;
END$$

CREATE PROCEDURE sp_resolve_flag(IN p_flag_id BIGINT, IN p_staff_id INT, IN p_code VARCHAR(30), IN p_note VARCHAR(500), IN p_dismiss BOOLEAN)
BEGIN
    DECLARE v_status VARCHAR(20) DEFAULT NULL;
    DECLARE v_sev    VARCHAR(20) DEFAULT NULL;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;

    START TRANSACTION;
    SELECT status, severity INTO v_status, v_sev FROM flags WHERE flag_id = p_flag_id FOR UPDATE;
    IF v_status IS NULL THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Flag not found'; END IF;
    IF v_status IN ('Resolved','Dismissed') THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Flag is already closed'; END IF;
    IF v_sev = 'Urgent_Review' AND (p_note IS NULL OR CHAR_LENGTH(TRIM(p_note)) < 5) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'A note is required to close an urgent flag';
    END IF;

    UPDATE flags
    SET status = IF(p_dismiss, 'Dismissed', 'Resolved'), resolved_at = NOW(),
        resolved_by_staff_id = p_staff_id, resolution_code = p_code, resolution_note = p_note
    WHERE flag_id = p_flag_id;

    INSERT INTO flag_events (flag_id, event_type, staff_id, note)
    VALUES (p_flag_id, IF(p_dismiss, 'Dismissed', 'Resolved'), p_staff_id, p_note);
    INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
    VALUES ('Staff', CAST(p_staff_id AS CHAR), IF(p_dismiss, 'DISMISS_FLAG', 'RESOLVE_FLAG'), 'flag', p_flag_id,
            JSON_OBJECT('code', p_code));
    COMMIT;
END$$
DELIMITER ;
```
Also write (same transaction-and-audit style) `sp_assign_flag`, `sp_complete_task` (needs outcome code, sets `completed_at`, status `Resolved`), `sp_approve_summary` (doctor only, stores `edited_text`, approver, time, status `Approved`) and `sp_reject_summary` (needs reason). Backend checks the caller's role before calling; the procedures check state.

### 7.4 Emergency duplicate fix (needs my approval)
Apply the trigger change from the patient-portal brief (section 9.3): no new Emergency flag when the patient already has an Open or Acknowledged Emergency flag created in the last 60 minutes. Staff still see every report.

### 7.5 Indexes to confirm
`flags (patient_id, status)`, `flags (status, severity, created_at)` (exists), `follow_up_tasks (status, due_at)`, `symptom_reports (patient_id, reported_at)` (exists), `sensor_readings (patient_id, measurement_type, measured_at)` (exists). Check with `EXPLAIN`. Target: worklist and timeline p95 under 300 ms with 5,000 flags and 100,000 readings.

---

## 8. API contract (staff, role-checked on every call)

| Endpoint | Roles | Purpose |
|---|---|---|
| `GET /staff/worklist?scope=mine|team|unassigned&tier=&status=&q=&cursor=` | Doctor, Nurse | Grouped worklist with counts for the same filters |
| `GET /staff/flags/{id}` | assigned or break-glass | Detail: reason, evidence, rule, ladder, history |
| `POST /staff/flags/{id}/acknowledge` `{note, create_task}` | Doctor, Nurse | Calls `sp_acknowledge_flag` |
| `POST /staff/flags/{id}/resolve` `{code, note}` | Doctor, Nurse | `sp_resolve_flag` (dismiss = false) |
| `POST /staff/flags/{id}/dismiss` `{code, note}` | Doctor, Nurse | `sp_resolve_flag` (dismiss = true) |
| `POST /staff/flags/{id}/assign` `{staff_id}` | Doctor, Nurse | Reassign owner, writes `flag_events` |
| `POST /staff/flags/{id}/escalate-now` | Doctor, Nurse | Escalation row plus audit |
| `GET /staff/patients?scope=&q=` | Doctor, Nurse | Directory |
| `GET /staff/patients/{id}/overview` | assigned or break-glass | Overview tab data |
| `GET /staff/patients/{id}/timeline?types=&from=&to=&cursor=` | assigned or break-glass | Timeline |
| `GET /staff/patients/{id}/readings?type=&from=&to=` | assigned or break-glass | Chart data with quality and rule lines |
| `GET /staff/tasks?scope=&status=&overdue=` | Doctor, Nurse | Queue |
| `POST /staff/tasks/{id}/claim|assign|complete|snooze` | Doctor, Nurse | Task actions (complete needs outcome) |
| `POST /staff/patients/{id}/contacts` | Doctor, Nurse | Communication log |
| `POST /staff/patients/{id}/notes` | Doctor, Nurse | Append-only notes |
| `GET /staff/summaries?status=draft` | Doctor, Nurse | Drafts list |
| `POST /staff/summaries/generate` `{patient_id, period}` | Doctor, Nurse | Fact sheet, LLM draft, guard, store |
| `POST /staff/summaries/{id}/approve` `{edited_text?}` | **Doctor** | Approve with final text |
| `POST /staff/summaries/{id}/reject` `{reason}` | **Doctor** | Reject |
| `GET /staff/handoff?shift=` | Doctor, Nurse | Handoff data |
| `GET/POST /staff/patients/{id}/rules`, `POST /staff/rules/{id}/approve` | read: both; approve: **Doctor** | Rules and history |
| `GET /staff/insights?from=&to=` | Doctor, Nurse | Metrics |
| `GET /staff/audit?...` | Doctor | Audit viewer |
| `GET /staff/patients/{id}/fhir` | Doctor | FHIR export (logged) |
| `POST /staff/access/break-glass` `{patient_id, reason}` | Doctor, Nurse | Records the reason, returns a short-lived grant |

Rules for every endpoint: role and assignment checks on the server; input validation; consistent error body `{ "error": "code", "message": "plain text" }`; cursor pagination; times in IST; every state change writes `audit_log`; exports are logged.

---

## 9. UI copy (EN; use the existing i18n keys; no jargon)

| Place | Text |
|---|---|
| Worklist title | Who needs attention first |
| Worklist helper | Grouped by patient. Every flag shows why it was raised. |
| Tiers | Immediate · Urgent · Review soon · Routine |
| SLA chip | Target: seen within 2 h · Overdue by 1 h 20 m |
| Status | Not yet seen · Seen by Priya Nair · Closed |
| Actions | Acknowledge · Resolve · Dismiss as false alarm · Assign · Log call · Add note · Open patient |
| Resolve dialog | How was this handled? (reason) · Add a short note (needed for urgent flags) |
| Already taken | Already acknowledged by {name} at {time} |
| Empty worklist | No open flags for your patients. |
| Timeline future dose | Scheduled |
| Timeline past dose | Not confirmed |
| Reading quality | Good · Questionable · Invalid · Sample |
| Device silent | No reading since {time}. Check the device. |
| Draft header | AI draft, not reviewed |
| Approved | Approved by {name}, {date time} |
| Break-glass | You are viewing a patient outside your assignment. This access is recorded. |
| Handoff received | Received by {name} at {time} |
Avoid: "stable", "normal", "optimal", "improving", "risk identified early", "validated", "AI detected".

---

## 10. AI behaviour for summaries

### 10.1 What the AI may do
Rewrite a deterministic fact sheet into a short, structured note. Nothing else. It cannot add, calculate, interpret or recommend.

### 10.2 Prompt (store in a config file)
```
You rewrite a FACT SHEET into a short handoff note for a clinician. You are not a clinician.

RULES
1. Use only the facts in FACT SHEET. Do not add, infer, calculate, round or compare.
2. Copy every number, date, time, unit and name of medicine exactly.
3. Do not use judgment words such as stable, normal, abnormal, improving, worsening, safe, concerning, healthy, or recovering well.
4. Do not recommend any action, test, treatment or dose change.
5. If a fact is missing, write "not available". Never fill gaps.
6. Refer to the person only as "the patient".
7. Maximum 120 words.

FORMAT (JSON only):
{"situation": "...", "background": "...", "assessment_facts": ["..."], "items_for_review": ["..."]}
"items_for_review" may only repeat open flag reasons and open tasks from the fact sheet.

FACT SHEET:
{fact_sheet_json}
```

### 10.3 Guard (mandatory)
```python
BANNED = ["stable","normal","abnormal","improving","worsening","deteriorating","safe","concerning","healthy","recovering well","optimal"]

def check_summary(draft, fact_sheet):
    text = " ".join([draft["situation"], draft["background"], *draft["assessment_facts"], *draft["items_for_review"]]).lower()
    if any(w in text for w in BANNED):
        return False, "banned_word"
    allowed = numbers_in(json.dumps(fact_sheet))
    if not numbers_in(text) <= allowed:
        return False, "number_not_in_facts"
    review_ok = all(item in fact_sheet["open_flag_reasons"] + fact_sheet["open_task_texts"] for item in draft["items_for_review"])
    return review_ok, None if review_ok else "review_item_not_from_facts"
```
If the check fails, store the plain fact sheet as the draft with the label "Generated without AI wording" and log the reason. The patient's name is added by code from `patient_id` when displaying.

---

## 11. Compliance and security engineering notes (not legal advice)

- **India DPDP Act 2023 and DPDP Rules 2025** (notified November 2025; phased commencement, with core obligations around May 2027): design now for a clear purpose, recorded consent and withdrawal, minimum necessary access, retention and erasure, and breach readiness. Items to build or leave hooks for: consent status per patient and caregiver (exists), access logs (D-17), break-glass (D-12), export logging, retention settings, "erase or anonymise a patient" procedure that keeps audit integrity.
- **ABDM:** if you later connect to the national health records system, you need the sandbox milestones and the patient's consent flows. Keep patient identifiers separable so an ABHA address can be stored with consent.
- **Do not store or display real identity numbers** in this prototype.
- **Security baseline:** server-side role and assignment checks; passwords hashed; JWT with short expiry; idle timeout; no secrets in the repository; HTTPS and secure cookies if deployed; rate limiting on login and exports.
- **Prototype honesty:** a small footer on staff pages is not needed, but the repository README must say that this is a synthetic-data prototype and not a medical device.

---

## 12. Testing and evaluation

| Level | What | Notes |
|---|---|---|
| Data integrity | no flag, task or summary text names a different patient than its `patient_id`; seed validation script passes | runs in CI (D-01) |
| Unit | tier mapping, SLA calculation, grouping/dedupe, guard for summaries, LACE score table, permission checks | pytest |
| API | state machine (Open to Acknowledged to Resolved), double acknowledge returns 409 and names the first person, urgent resolve needs a note, role limits (nurse cannot approve summaries), break-glass logging, pagination | pytest with test DB |
| Concurrency | two staff acknowledge the same flag at once: exactly one wins | script with threads |
| SQL | procedures roll back on error; `flag_events` and `audit_log` rows exist for each action | SQL tests |
| UI | worklist grouping and filters, drawer actions per state, timeline filters and chart, task queue actions, draft edit/approve/reject, handoff, dark mode | Playwright |
| Visual | baseline pages unchanged; new pages follow the style lock | Playwright screenshots |
| Accessibility | automated audit plus keyboard-only walkthrough | axe via Playwright |
| Performance | 5,000 flags, 100,000 readings, p95 under 300 ms for worklist and timeline first page | load script |
| Safety | AI summary cannot contain banned words or unknown numbers; no names sent to the LLM; no AI text can change a flag or rule | pytest |
| Manual | a 10-minute "morning shift" run: triage, resolve, call log, handoff | checklist |

---

## 13. Observability and operations
- Structured logs for every state change with request id and staff id.
- A `scripts/print_recent_audit.py` to show the last 50 audit rows.
- Health endpoint reporting database, scheduler and LLM availability; the UI shows a small status chip for the LLM ("AI drafting unavailable") without blocking any clinical action.
- Backup and restore note in the README (how to restore the seeded demo state).

---

## 14. Delivery phases with gates

**Phase 0: read-only audit and diagnosis (no code or data changes)**
Deliver `docs/STAFF_PORTAL_AUDIT.md` (how staff pages, endpoints, views and state work today), `docs/DATA_INTEGRITY_REPORT.md` (Section 7.1 results with cause), `docs/STYLE_LOCK_STAFF.md`, baseline screenshots (light and dark), and a plan for Phase 1 with files you will touch. **Stop for my approval.**

**Phase 1: integrity, worklist, flag drawer (D-01, D-02, D-03, D-04, D-10, D-18, D-23)**
Gate: zero identity mismatches; grouped worklist with correct counts and no all-100 column; drawer actions correct per state; acknowledged rows never show Acknowledge; duplicate fix applied (after approval); seed rebuilt; consistency test green.

**Phase 2: patient page and timeline (D-05 overview and Medicines, D-06)**
Gate: patient names everywhere; timeline filters, day groups, chart with quality and rule lines; future doses show Scheduled.

**Phase 3: tasks and summaries (D-07, D-08)**
Gate: task queue with owner, due, outcome; summaries from fact sheets with sources, edit, approve, reject; guard tests pass; no banned words.

**Phase 4: workflow tools (D-09, D-11, D-12, D-15, D-16, D-17, D-21)**
Gate: handoff page, notifications, assignment and break-glass, call log, notes, audit viewer, Ctrl+K.

**Phase 5: governance and interoperability (D-13, D-14, D-19, D-20)**
Gate: rules tab with history, pathway templates with blank thresholds, insights page with definitions, FHIR export validated against the FHIR R4 spec, optional LACE context.

**Phase 6: polish and handover**
Accessibility report, performance report, README section, 5-minute doctor-portal demo script, list of known gaps.

At the end of each phase: commit, summarise, show test output and screenshots (light and dark), list what you did **not** test, and wait for my go-ahead.

**Ask me before:** deleting or rewriting seed data, applying the trigger change, changing a procedure signature, choosing medicine names, adding any rule that creates flags, or adding a new library.

---

## 15. Definition of done

- [ ] Style lock respected; baseline pages unchanged.
- [ ] No patient-name mismatches anywhere; automated test in place.
- [ ] Worklist grouped per patient, tiered, deduplicated, with SLA chips and owners; counts match filters.
- [ ] Every flag shows its real reason, evidence, rule, approver and escalation ladder.
- [ ] Flag lifecycle (acknowledge, resolve, dismiss with reasons) works with audit and `flag_events`.
- [ ] Timeline has filters, day grouping, readings chart with quality and rule lines; future doses show Scheduled.
- [ ] Tasks are a real queue (owner, due, outcome, overdue).
- [ ] Draft summaries come from fact sheets, show sources, can be edited, approved or rejected by a doctor, and contain no judgment words.
- [ ] Handoff, notifications, assignment with break-glass, call log, notes, audit viewer working (Phases 4).
- [ ] Rules view with history; insights with definitions; FHIR export; optional LACE (Phase 5), or listed as not done.
- [ ] No claims the system cannot back with data anywhere on screen.
- [ ] All tests pass; accessibility and performance reports attached; list of untested items provided.

---

## 16. What I want from Antigravity after each phase
1. Plain-language summary of what changed and why (files listed).
2. Real command output for tests, builds and SQL checks.
3. Screenshots (light and dark) of every changed screen.
4. Anything that looked like a bug, a data problem or a false claim that you did **not** fix.
5. What you did not test, and every assumption you made.
6. The next phase's plan, then wait for my approval.

---

## Appendix A. Definitions

| Term | Meaning here |
|---|---|
| Flag | A system-generated reason for a person to review a patient. Not a diagnosis |
| Tier | Immediate, Urgent, Review soon, Routine, derived from flag source and severity |
| Acknowledge | A named person takes ownership and stops escalation. Not the same as resolve |
| Resolve / Dismiss | Close with a reason code (and a note for urgent flags) |
| Break-glass | Access outside assignment with a typed reason, logged |
| Fact sheet | Deterministic data summary used as the only source for an AI draft |
| Closed loop | Alert, owner, action, outcome, all recorded |
| SBAR / I-PASS | Structured handoff formats (Situation-Background-Assessment-Recommendation; Illness severity-Patient summary-Action list-Situation awareness-Synthesis by receiver) |
| LACE | Readmission-risk index from length of stay, acuity, comorbidity and ED visits; context only here |
| HIP / HIU / ABHA | ABDM terms: information provider, information user, health ID |

## Appendix B. Quick wins to do first (about two hours of work)
1. Diagnose and report the identity mismatch (Section 7.1).
2. Replace raw `Urgent_Review` / `Review_Soon` with human labels on the Tasks page.
3. Show date and age (not only time) in "Raised at".
4. Hide the Acknowledge button on acknowledged rows.
5. Replace "Patient #N" chips with names plus codes.
6. Show future doses as Scheduled.
7. Remove "Event log" repetition and the word "stable" from templated summary text.
