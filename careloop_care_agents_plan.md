# CareLoop Care Agents: Making Agentic RAG the Main Feature (7 Phases)

**Goal:** make **CareLoop Agents** the main highlight of the project. Agents prepare every case, draft the routine paperwork, answer routine patient questions from the patient's own papers, and run outreach, so nurses and doctors spend their time **deciding and calling**, not searching, typing and reconciling.

**Guiding rule (unchanged):** *The LLM talks. Rules decide. Humans act.*
**Agent rule:** *Agents do the routine. People make the calls.*

---

## 0. Is this the right direction? (verification)

I checked what I could. Here is the honest verdict.

| Your idea | Verdict | Why |
|---|---|---|
| Make agentic RAG the main feature | **Yes, with limits** | It is a real differentiator when "agentic" means planning, tool use, checking its own answer and abstaining, **not** free autonomy |
| Reduce nurse and doctor work | **Plausible, but you must measure it** | Savings come from routine work: preparing cases, de-duplicating, drafting notes, answering routine papers questions, outreach and retries. Claim only what you measure ("in a replay of 40 simulated cases, human steps fell from X to Y"), never "saves hours" |
| Agents that decide risk or escalate on their own | **No** | It breaks your own rule, breaks the human-oversight principle in India's ICMR guidance, and pushes the software toward regulated medical-device software (see below) |
| "Different from other projects" | **Yes** | The difference is not "more AI", it is **bounded autonomy**: levels per action, shadow mode before trust, a policy guard that checks every output, a trace of every step, an off switch, and a patient opt-out |

**What I verified from outside sources**
- **CDSCO (India) final guidance on Medical Device Software**, Doc No. CDSCO/MD/GD/MDSW/01/2026, issued in July 2026 under the Medical Devices Rules, 2017. The sources I read say software that performs medical functions (for example clinical decision support, treatment recommendation, quantification of physiological parameters, real-time monitoring) may be regulated, and that classification depends on intended use, claims and risk. **What this means for you:** keep agents on workflow and communication (preparing, drafting, routing, reminding), keep the "not a medical device, synthetic data" statement, and get regulatory advice before any real use. *I read summaries by law firms and news sites, not the full 62-page guidance. Read the official document before you make regulatory statements.*
- **ICMR Ethical Guidelines for AI in Biomedical Research and Healthcare (2023)**: ten principles, including accountability and liability, **autonomy (human oversight; patients can reject AI)**, data privacy, risk minimisation and safety, trustworthiness (explainable, valid), and accessibility (local languages). This plan maps to them in Section 12.
- India's **DPDP Rules 2025** (verified earlier): consent, purpose limitation, access logs, retention.

**What I could not verify:** your code, whether your hardware works, the Gemini model behaviour on your data, and real workload savings. Those are tested in Phases 6 and 7.

> **Before you start:** your proposal listed RAG, an LLM, ChromaDB and the escalation ladder as excluded unless your supervisor approves. Making them the main feature needs your supervisor's approval. Get it in writing.

---

## 1. How to use this file

1. Keep this file **outside** the repository (or delete it after Phase 7). The repository keeps only `README.md` and `PROJECT_GUIDE.md`; lasting details go there in Phase 7.
2. Launcher prompt for Antigravity or Gemini CLI inside the project folder:

```
Read careloop_care_agents_plan.md completely, then README.md, PROJECT_GUIDE.md and the real code.
This is an ADDITIVE upgrade on branch care-agents. Do not rebuild, rename or remove existing roles, pages, tables or features. Do not change the visual style: reuse existing components, colours, fonts, spacing and the dark/light theme. Keep MySQL and the cast (one doctor, one nurse, five patients, four logins).
Follow the 7 phases in order. Start with Phase 1 and STOP after it for my approval. Do the same after each phase.
The safety rules in Section 3 and the autonomy levels in Section 5 always apply. Ask me before adding any library, changing an existing column, or deleting anything.
After every phase show real command output, screenshots for all four logins (light and dark), and what you did not test.
```

---

## 2. What changes in how the project works

| Today | With CareLoop Agents |
|---|---|
| A flag appears; the nurse opens several screens to understand it | A **case brief** is prepared automatically: facts, sources, unknowns, last contact, consent, and the next step from a fixed menu |
| Nurse types the call note, creates the task, writes the patient message | The agent **drafts** all three from 2 to 3 quick picks or a short voice note; the nurse edits and signs |
| Repeated alerts need manual grouping and notes | Duplicates are **merged automatically** into one case with a note |
| Routine patient questions land on the nurse | The **Papers Agent** answers routine questions with sources; only "not in papers", dose-change and emergency go to people |
| Nurse retries unanswered calls by hand | Retries are scheduled automatically within limits; after the limit the agent **proposes** the next step |
| Summaries and handoff are written when someone has time | Drafts are prepared at shift change; a person signs |
| Doctor decisions start from raw alerts | Doctor cards arrive with the brief, a pre-drafted note and 2 to 3 one-click options |
| You cannot see what the AI did | **Agent Desk** and **Agent Trace** show every action, plan, source and check |
| AI is always on | Doctor controls autonomy per action; **shadow mode** proves reliability before an agent acts; **Pause all agents** switch; **patient can choose human-only follow-up** |

---

## 3. Safety rules (never break)

1. **Agents never create, close or change a flag, limit, plan or prescription.** Flags come only from doctor-approved rules, the emergency check and SOS (deterministic) and from humans. The only exception is a doctor-enabled **auto-close rule** (Section 5.4) that closes specific low-risk flag types when a stated condition is met, labelled "Closed by approved rule".
2. **No clinical judgment by AI.** Agents never diagnose, interpret symptoms or readings as safe or unsafe, recommend treatment, or advise on doses. Next steps come from a **fixed menu** chosen by a **deterministic decision table**; the LLM only writes readable sentences from facts.
3. **Emergency handling never waits for an LLM** (typed text, voice, SMS, check-in answers, SOS).
4. **Every statement is traceable.** Each fact in a brief, draft or answer cites its source (record id or passage). Numbers, times and dates must appear in the source. Anything unsourced is dropped.
5. **Untrusted text is data, never instructions.** Patient messages, voice transcripts, SMS and the contents of discharge papers can contain instructions ("ignore previous rules"). Agents never follow them. Tools are gated by code, with the patient id taken from the login token.
6. **No names, phone numbers or other identifiers go to the LLM** (use the patient code). Names are inserted by code afterwards.
7. **Consent and opt-out.** Family sees only what the patient allows. The patient can switch **AI help off** (human-only follow-up). Photos are never visible to family. STOP on SMS is honoured.
8. **Quiet by design:** quiet hours 22:00-07:00, max 2 reminders per dose, max 3 other automated patient messages per day, no new prompts while an emergency flag is open, duplicates suppressed. SOS, "Are you OK?" and escalation may break quiet hours.
9. **Transparency.** Messages say who they are from ("Automated message from CareLoop", "From Priya (nurse)"). AI-prepared items carry an "AI-prepared" label. Every agent action has a run id, a reason and an audit row.
10. **Graceful degradation.** If the LLM is down, slow or paused: rules, escalation, SOS, reminders, tools and fact-sheet briefs (no AI wording) keep working.
11. **No claims the project cannot prove:** never "autonomous", "AI nurse", "replaces nurses", "diagnoses", "saves hours". Workload numbers are always labelled **estimated** and tied to a measured replay.
12. Two patient identifiers (name, age, code) wherever a patient appears. Sample data only; sample images are generated placeholders.

---

## 4. The agents (the main feature)

All agents follow one contract: **event in → plan → tool calls → draft or action → Policy Guard → delivery by autonomy level → ledger and trace.**

| Agent | Trigger | Does | Main tools (read-only unless noted) | Default autonomy |
|---|---|---|---|---|
| **Papers Agent** (agentic RAG for patients) | Patient question (text, voice, SMS) | Plans retrieval across sources, grades the evidence, retries once, writes a short answer with sources, or abstains | papers search, plan items, care-record lookups, protocol FAQ | **Auto** for sourced answers; not-found creates ONE de-duplicated request |
| **Outreach Agent** | Rounds schedule, missed prompts | Picks channel and timing inside policy (app, then SMS if unread), sends reminders and check-in prompts, retries, handles replies | scheduler, SMS service (write, allowlisted templates) | **Auto** inside limits |
| **Case Prep Agent** | New or changed flag, call request, photo, assistant request | Builds the case brief; merges duplicates; suggests next step from the fixed menu; prepares call script from the approved template | care record, flags, readings, check-ins, dose logs, limits, contacts | Brief: **Auto** (internal). Next step: **Suggest** |
| **Call Notes Agent** | Nurse finishes a call | Drafts the call note, follow-up task and patient message from the nurse's quick picks or short voice note | the call form | **Draft** (nurse signs) |
| **Handoff Agent** | Shift change, daily time | Drafts patient summaries and the shift handoff from a fact sheet | fact sheet builder | **Draft** (doctor or nurse signs) |
| **Plan Agent** | Papers uploaded, admission | Drafts the recovery plan with sources and reconciliation | papers search, prescriptions | **Draft** (doctor approves) |
| **Dispatcher** (supervisor, no LLM) | Every event | Routes events to agents, enforces autonomy level, budgets, rate limits and the kill switch, writes the ledger | policy tables | n/a |

### 4.1 Agentic RAG, precisely (Papers Agent)
"Agentic" here means the agent **chooses a retrieval strategy, uses several sources, checks the evidence and can say no**. It does not mean it acts freely.

```
question -> safety gates (emergency, dose-change, small talk: plain code, no LLM)
         -> intent label (rules first; small LLM label only if unsure; must be from a fixed list)
         -> plan (choose ONE allowed plan template and fill its parameters; JSON validated)
         -> act (run the plan: tools and/or retrieval; max 4 steps, timeouts)
         -> grade (is the evidence enough and on topic? if not, rewrite the question once, e.g. Hindi -> English, and retry; still not enough -> abstain)
         -> draft (LLM writes 60-90 words from the evidence only, JSON with source ids)
         -> verify (sentence-level support check, numeric guard, banned words, language)
         -> deliver or abstain ("That is not in your discharge papers, so I will not guess.")
```
**Plan templates (examples):**
- `appointment`: tool `get_next_appointment`.
- `medicine_times`: tool `get_medicine_plan` + papers search (section medicines) -> merge -> verify.
- `warning_signs` / `activity` / `wound_care` / `diet`: papers search (section filter) -> grade -> draft.
- `reading_value`: tool `get_latest_readings` (latest valid value, time, quality only; no judgment).
- `plan_item`: tool `get_plan_items` (approved plan only).
- `contacts`: tool `get_care_team_contacts`.
- `follow_up`: rewrite using the last 6 messages, then one of the above.

**Sources the agent may use:** (1) the patient's own discharge papers (hybrid search, section-aware), (2) the approved plan, (3) read-only care-record tools, (4) an optional **clinic protocol and FAQ library**: short documents written and approved by the doctor (for the sample: neutral administrative content such as "who to call", "how the watch works", "what the app can and cannot do". Do **not** invent medical protocols). No general medical knowledge from the model.

### 4.2 Case Prep Agent: the case brief
The brief is built from a **deterministic fact sheet first**; the LLM only rewrites it into readable lines (and the guard rejects anything not in the fact sheet).

```
{
 "case_id": "...", "patient_code": "CL-00001",
 "headline": "SpO2 reading 91.00 % is below the clinician-approved limit of 94.00 (simulated reading)",   // the flag's real reason
 "what_happened": [{"fact": "...", "source": "flag#6"}, {"fact": "...", "source": "reading#20"}],
 "context": [{"fact": "Last check-in 1 h 20 min ago, pain 2/10", "source": "checkin#31"},
             {"fact": "3 of 3 doses taken yesterday", "source": "doses 2026-10-29"},
             {"fact": "Caregiver consent: granted", "source": "caregiver#1"}],
 "unknowns": ["No reading since 14:38", "Patient has not answered today's prompt"],
 "next_step": {"key": "call_now", "why": ["Immediate or urgent tier", "No contact since 13:28"]},   // from the fixed menu via the decision table
 "options": ["call_now", "send_checkin", "request_photo", "ask_doctor", "recheck_at"],
 "prefilled": {"call_script_id": 17, "note_draft": "..."},
 "guard": {"passed": true}
}
```
**Fixed menu of next steps:** Call the patient now · Send a check-in prompt · Ask for a photo · Ask the doctor · Re-check at a set time · Merge as duplicate · Close with a reason code (only where the rule allows and a person presses it). **Decision table (deterministic):** keyed by flag source, tier, consent, device status, time since last contact and number of no-answers. The LLM never picks the step; it only explains it using the listed facts.

### 4.3 Call Notes Agent
Nurse taps quick picks (reached or not; patient reports; actions agreed) and optionally dictates 1 to 2 sentences. The agent drafts: (a) the call note, (b) the follow-up task with a due time, (c) a short patient message (SMS or app), (d) a "needs doctor" line if the nurse ticked it. **It may not add any fact the nurse did not provide.** The nurse edits and signs; edit distance is stored to measure draft quality.

### 4.4 Outreach Agent (adaptive but bounded)
- Chooses the channel inside policy: app notification first, SMS if unread after a set time; Hindi or English by patient preference.
- Retries unanswered check-ins once; no-answer calls: reschedule up to 2 retries, then **propose** the family step (only with consent) or doctor review.
- Learns nothing outside policy: it cannot send new kinds of messages or change timing rules; doctors change those in Agent settings.

---

## 5. Autonomy, shadow mode and trust

### 5.1 Autonomy levels
| Level | Meaning | Example |
|---|---|---|
| **Suggest** | Agent shows an idea; nothing is prepared | "Suggested next step: call now" |
| **Draft** | Agent prepares the full item; a person approves, edits or rejects | Call note, summary, plan |
| **Auto** | Agent acts alone inside limits; each action is logged and undoable where possible | Reminders, sourced routine answers, duplicate merging |
| **Never** | Not available to any agent | Create or close flags (except approved auto-close), change limits, plans or prescriptions, contact family outside the ladder, dose advice, diagnosis |

### 5.2 Default autonomy per action type (editable by the doctor only)
| Action | Default |
|---|---|
| Dose reminder, check-in prompt, photo request (when the approved plan says so) | Auto |
| Sourced answer to a routine papers question | Auto |
| Not-found or dose-change request to the care team | Auto (ONE per topic per day) |
| Duplicate alert merging | Auto |
| Case brief | Auto (internal only) |
| Next-step suggestion | Suggest |
| Call script, call note, post-call patient message | Draft |
| Daily summary, shift handoff | Draft |
| Recovery plan | Draft (doctor approves) |
| No-answer retry scheduling | Auto (max 2) |
| Auto-close of approved flag types | **Off** until the doctor turns it on |
| Flags, limits, prescriptions, dose advice, diagnosis | Never |

### 5.3 Shadow mode (earn the right to act)
Every action type has a mode: **Shadow** or **Live**. In Shadow, the agent records what it *would* do next to what the human actually did (`shadow_decisions`), without acting. The **Agent settings** page shows agreement over the last N cases (for example 96% over 40). The doctor can promote an action to Live or demote it, each change audited. Defaults for the sample build: low-risk actions (reminders, sourced answers, merging) start Live; everything else starts Shadow or Draft.

### 5.4 Approved auto-close rules (optional, P1)
Doctor-enabled per rule type and per patient, **off by default**, for low-risk types only (for example "No data from device" closes when valid readings resume for 30 minutes). Never for Emergency, SOS, Urgent, Symptom or Photo flags. The closure is labelled "Closed by approved rule (data resumed 14:52)", shows who enabled the rule, and can be reopened.

### 5.5 Controls
- **Pause all agents** (doctor): human-only mode, effective within one tick.
- **Pause for this patient** (nurse or doctor, with reason).
- **Patient opt-out:** "AI help: On/Off" on patient Home next to Family sharing. Off: no LLM features for this patient; reminders and rules still run; the assistant page becomes a plain "Ask my care team" form.
- Budgets: max LLM calls per patient per day and per agent run (config).

---

## 6. Policy Guard (deterministic, applied to every agent output)

| Check | Rule |
|---|---|
| Allowlist | Only tools and actions allowed for that agent and autonomy level |
| Identity | Patient id from the token or the case; names and codes consistent across the output |
| Sources | Every fact and sentence has a source id that exists; unsourced items dropped |
| Numbers | Every number, date and time appears in the cited source |
| Menu | Next steps and options only from the fixed menu |
| Language | Output language matches the patient preference; emergency text from fixed templates |
| Banned words | No clinical judgment words (stable, normal, safe, improving, concerning, ...) and no dose or treatment advice patterns |
| Consent | Family or photo content never goes where consent is missing |
| Limits | Quiet hours, daily caps, duplicates, pause, STOP, open emergency |
| Length and format | JSON schema valid; length caps; no instructions copied from untrusted text |
On failure: drop the item, fall back to the plain fact sheet or an abstain message, and log the reason in the run.

---

## 7. Data and API (sketch; adapt to the real schema; ask before changing existing columns)

```
agent_runs      (run_id, agent_name, trigger_type, trigger_ref, patient_id, case_id NULL, started_at, finished_at,
                 status [Done, Abstained, Failed, Blocked_By_Guard, Paused], autonomy_level, mode [Shadow, Live],
                 plan JSON, result_type, llm_calls, tokens_in, tokens_out, latency_ms)
agent_steps     (step_id, run_id, seq, step_type [Gate, Plan, Retrieve, Tool, Grade, Draft, Verify, Guard, Deliver, Abstain],
                 summary, ids JSON, ok, ms)
agent_drafts    (draft_id, run_id, patient_id, draft_type [Case_Brief, Call_Script, Call_Note, Patient_Message, Summary,
                 Handoff, Plan, Reply], body TEXT/JSON, sources JSON, status [Pending, Accepted, Edited, Rejected, Auto_Sent, Expired],
                 reviewed_by_staff_id, reviewed_at, edit_chars INT NULL, created_at)
agent_autonomy  (action_type PK, level [Suggest, Draft, Auto], mode [Shadow, Live], set_by_staff_id, set_at)
shadow_decisions(shadow_id, run_id, action_type, agent_decision JSON, human_decision JSON, agreed BOOLEAN, created_at)
cases           (case_id, patient_id, primary_flag_id, status, created_at, merged_count)  -- groups duplicate flags; may reuse existing grouping if present
case_flags      (case_id, flag_id)
protocol_docs   (reuse discharge_documents with doc_type 'Protocol', approved_by_staff_id, approved_at)  -- optional library
patients        + ai_help_enabled BOOLEAN DEFAULT TRUE
```
Existing items to reuse: `scheduled_actions`, `agent_proposals`, `audit_log`, `chat_messages`, `document_chunks`, `follow_up_tasks`, `flags`, `escalations`, `sms_messages`. If some do not exist yet, the audit in Phase 1 says so.

| Endpoint (sketch) | Roles | Purpose |
|---|---|---|
| `GET /agent/desk` | Nurse, Doctor | Waiting for you, Done for you (with undo), Needs a decision, work saved (estimate) |
| `GET /agent/runs/{id}` | Nurse, Doctor | Trace: plan, steps, sources, guard results |
| `GET /cases/{id}/brief` | Nurse, Doctor | Case brief |
| `POST /agent/drafts/{id}/accept|edit|reject` | Nurse, Doctor (summaries and plans: doctor) | Draft handling |
| `POST /agent/undo/{action_id}` | Nurse, Doctor | Undo an Auto action where possible |
| `GET/PUT /agent/settings` | **Doctor** | Autonomy matrix, shadow results, promote or demote, budgets |
| `POST /agent/pause` | Doctor (all); Nurse (one patient) | Pause switch |
| `PATCH /patient/me/settings` (`ai_help_enabled`) | Patient | Opt-out |
| `GET /insights/work-saved` and `POST /insights/replay` | Doctor | Measured workload replay (dev tool) |

---

## 8. Screens (built from existing components; no new style)

**Nurse**
- **My call list** cards gain: "Brief ready" chip, 3 to 5 fact lines with sources, "Unknowns", the suggested next step with its reasons, and buttons **Call** (opens the call form with the prepared script), **Ask doctor**, **Done**. Duplicates show "5 reports merged".
- **Agent desk** (new sidebar item): four sections: *Waiting for you* (drafts), *Done for you* (auto actions with Undo), *Needs a decision* (items the guard held back or the doctor must decide), *Work saved today (estimate)*.
- **Call form:** quick picks, optional **voice note** (browser speech recognition, transcript shown and editable), then the drafted note, task and patient message; **Approve** sends all three after edits.
- Handoff and summaries arrive as drafts at shift start.

**Doctor**
- **Needs my decision** cards gain the brief, a pre-drafted note and 2 to 3 one-click options.
- **Agent settings** (new sidebar item): autonomy matrix (level and Shadow/Live per action type), shadow agreement table, kill switch, budgets, auto-close rules, protocol library upload and approval.
- **Agent trace:** "Why did the agent say this?" link on any AI-prepared item opens the run (plan, sources, checks).

**Patient**
- Assistant (Papers Agent): sources on every answer, "From your papers", small talk with no source, action cards, Listen and voice (see the Assistant v2 work if present).
- **AI help: On/Off** switch on Home.
- Automated messages are labelled "Automated message from CareLoop".

**Family:** unchanged (status only).

**Landing page:** add a **Care Agents** section (Phase 7) with provable statements only.

---

## 9. Seed data (small, explainable)

- Agents: the five agent rows with autonomy levels per Section 5.2; shadow results for two actions (for example sourced answers 96% over 40 cases; call-note drafts 88% accepted without edits). These are **computed from the replay run in Phase 6, not typed in**.
- Aarav: 6 chat messages with runs and traces; one open case (SpO2) with brief and call script; one completed call with an accepted draft.
- Meera: case (silent device) with brief, "No consent for family step" shown in the facts; one draft summary pending.
- Rajesh: case from a Hindi emergency report with a brief; a dose-question request answered by the nurse using the agent's draft reply.
- Kabir: quiet; one auto-answered routine question.
- Sunita: case merged from 3 duplicate missed-dose reports; one no-answer retry scheduled.
- About 25 agent runs in the last 24 hours across agents (Done, Abstained, Blocked_By_Guard examples), 3 pending drafts, 1 rejected draft.
- Reset in under 30 seconds; the validation script must also check: every draft has sources, every run has steps, no brief mentions a fact absent from the fact sheet, no patient name appears in any stored LLM request.

---

## 10. The seven phases

| Phase | Name | Result |
|---|---|---|
| 1 | Agent foundation | Dispatcher, Policy Guard, ledger, traces, autonomy matrix, shadow mode, pause switch, patient opt-out, Agent desk skeleton |
| 2 | Papers Agent (agentic RAG) | Planner, hybrid retrieval, tools, grading, verification, abstain, traces, evaluation set |
| 3 | Case Prep Agent | Case briefs, duplicate merging, next-step menu, doctor decision cards |
| 4 | Outreach and Call Notes Agents | Adaptive outreach, retries, call form with voice note, drafted note, task and message |
| 5 | Handoff, Plan and auto-close | Drafted summaries and handoff at shift change, Plan Agent hookup, approved auto-close rules, Agent settings page |
| 6 | Evaluation and measurement | Golden sets, red-team and injection tests, workload replay, work-saved panel, shadow results |
| 7 | Wording, documents, final proof | Care Agents as the headline of the whole product, README and PROJECT_GUIDE updated, rehearsed demo |

---

### PHASE 1: Agent foundation

**Goal:** one safe place where every agent runs, is checked, is logged and can be switched off.

**Tasks**
1. **Audit (chat only):** how chat, RAG, Rounds, reminders, escalation, SMS, drafts, summaries, handoff and permissions work today; which earlier features exist (Rounds, Check-in Guide, Photo check, My plan, SOS, Assistant v2); where this plan does not match the code. Style lock list and baseline screenshots.
2. **Schema** for the tables in Section 7 (reuse what exists).
3. **Dispatcher:** event intake, routing table, budgets, rate limits, kill switch, per-patient pause, opt-out check, autonomy lookup. No LLM inside.
4. **Policy Guard** (Section 6) as one module with unit tests for each check, used by every agent.
5. **Run recorder:** every agent run writes `agent_runs` and `agent_steps`; a helper `trace(run_id)`.
6. **Autonomy and shadow:** `agent_autonomy`, `shadow_decisions`, the logic "Shadow records, Live acts". Seed defaults from Section 5.2.
7. **Agent desk skeleton** for nurse and doctor (the four sections, empty states), **AI help** switch for the patient, **Pause all agents** for the doctor.
8. **Degradation test:** with the LLM disabled, rules, reminders, escalation and tools still work and briefs fall back to the plain fact sheet.

**Acceptance checks**
- A blocked output is never delivered and the reason is stored.
- Shadow mode never acts; Live acts only inside limits.
- Pause stops all agent actions within one tick; opt-out stops LLM features for that patient.
- No patient names in any stored LLM request (test).
- Existing screens look and behave as before.

**Show me:** audit summary, Agent desk screenshots (nurse and doctor), guard test output, a run trace, the degradation test result.
**Ask me before:** adding a library, changing any existing column.

---

### PHASE 2: Papers Agent (agentic RAG)

**Goal:** a patient assistant that plans, retrieves from the right source, checks itself and abstains when unsure.

**Tasks**
1. **Safety gates first (plain code):** emergency (English and Hindi, text and voice transcripts), dose-change, small talk (fixed replies, no sources, name added by code).
2. **Intent label and plan templates** (Section 4.1): rules first; a small LLM label only if unsure; output validated against the fixed list; plan JSON validated; max 4 steps; timeouts.
3. **Ingestion upgrade:** section-aware chunks (heading detection; `section_title`, `section_type`, `page_no`), a multilingual embedding model or translate-to-English fallback so Hindi works; hybrid retrieval (embeddings plus keyword); optional clinic protocol and FAQ library with doctor approval.
4. **Read-only tools:** appointment, today's doses, medicine plan, approved plan items, latest valid readings (value, time, quality only), care team contacts. Patient from the token.
5. **Grade and correct:** judge evidence sufficiency; one query rewrite; then abstain.
6. **Draft and verify:** JSON answer with source ids; sentence-level support check (each sentence cites a source; token overlap with that source above a threshold), numeric guard, banned words, language; fail means abstain.
7. **Source chips and passage drawer** with real section and page; "Not in your papers" card creating ONE care-team request per topic per day, only claiming it when it exists.
8. **Trace:** every answer stores its run; staff can open "Why did the agent say this?".
9. **Evaluation set (in the repo's test folder, not a document):** 50 questions from the real discharge PDF in English and Hindi across all plan templates, plus 10 injection attempts and 10 out-of-scope questions.

**Acceptance checks (report honestly)**
- Retrieval hit at 3 at least 90% (Hindi at least 80%); abstain correctly on not-in-papers at least 95%; hallucinated numbers reaching a patient: 0; emergency and dose-change handled correctly 100%; ungrounded answers shown as grounded: 0.
- Tool answers match the Medicines, Calendar and Plan pages exactly.
- Injection attempts (in questions and inside a test PDF passage) never change behaviour.

**Show me:** evaluation report, three traces (answered, abstained, blocked), a Hindi voice question end to end.

---

### PHASE 3: Case Prep Agent

**Goal:** every alert arrives as a prepared case.

**Tasks**
1. **Cases:** group duplicate flags into a case (same patient, source and rule within a window), keep `merged_count`, show "5 reports merged".
2. **Fact sheet builder** for a case (flag reason, evidence with quality, last contact, dose facts for 48 hours, check-ins, device status, consent, open tasks, limits and who approved them).
3. **Brief writer:** LLM rewrites the fact sheet into short lines; guard enforces sources, numbers and banned words; failure falls back to the fact sheet.
4. **Decision table and fixed menu** (Section 4.2) with unit tests per row; the LLM never chooses the step.
5. **Call script** from the doctor-approved check-in template (no invented questions).
6. **UI:** nurse call-list cards (Brief ready, facts with sources, unknowns, suggested step with reasons); doctor decision cards (brief, pre-drafted note, 2 to 3 one-click options); Agent trace link.
7. **Shadow:** record the agent's suggested step beside the nurse's actual action.

**Acceptance checks**
- Brief faithfulness 100%: every line maps to a source row (automatic test over all seed cases).
- The suggested step is always from the menu and matches the decision table.
- A brief for a patient with no caregiver consent says so and never suggests the family step.
- Duplicates merge; the nurse sees one card.

**Show me:** briefs for Aarav, Meera and Rajesh; the decision-table tests; a merged-case example.

---

### PHASE 4: Outreach Agent and Call Notes Agent

**Goal:** the routine contact work and the paperwork after calls are prepared for the nurse.

**Tasks**
1. **Outreach:** channel choice inside policy (app first, SMS if unread after a set time), language, retries (check-ins once; no-answer calls up to 2), reply handling (SMS 1/2/3/STOP, existing parser), "Suggested by Rounds" proposals after the limit (family step only with consent).
2. **Call form (nurse):** quick picks, optional voice note (browser speech recognition, editable transcript, no audio stored), "needs doctor" tick.
3. **Call Notes Agent:** drafts note, follow-up task with due time, and the patient message; **no facts beyond the nurse's input**; guard checks; nurse edits and signs; `edit_chars` stored.
4. **Papers Agent link:** when a patient's question was not found or concerned a dose change, the nurse sees the question, the draft reply (facts only from the papers and care record, or "needs your answer"), and sends or edits it. Replies appear to the patient as "Message from Priya (nurse)".
5. **Agent desk:** Waiting for you (drafts), Done for you (outreach actions, undo where possible), counts.
6. **Shadow:** compare drafted notes and tasks with what the nurse finally saved.

**Acceptance checks**
- A draft that adds an unprovided fact is blocked.
- Quiet hours, daily caps, STOP and pause are respected by outreach (tests with a fake clock).
- Approving a call draft creates the note, task and message in one action, with audit rows and the run id.
- The nurse can complete a call record in 3 clicks plus an optional voice note (measure and report).

**Show me:** a full call: brief, call, voice note, drafts, approval; a retry chain; an undo.

---

### PHASE 5: Handoff, Plan and approved auto-close

**Goal:** the periodic paperwork writes itself; the doctor keeps control.

**Tasks**
1. **Handoff Agent:** at shift start and a set daily time, draft per-patient summaries and the shift handoff from the fact sheet (I-PASS or SBAR style, facts only, no judgment words), marked "AI-prepared draft". A person signs; the doctor receives.
2. **Plan Agent hookup:** drafting from papers with sources, reconciliation and doctor approval (reuse My plan work if present).
3. **Approved auto-close rules (P1):** doctor toggles per rule type and patient, off by default, low-risk types only, labelled closures, reopen allowed, audit rows.
4. **Agent settings page** (Section 8): autonomy matrix, Shadow/Live per action, agreement table, promote or demote with audit, budgets, protocol library approval, kill switch.
5. **Undo** for Auto actions that can be undone (messages cannot be unsent; tasks and merges can be reverted).

**Acceptance checks**
- A signed summary records signer and time; an unsigned draft is never shown to a patient.
- Auto-close refuses Emergency, SOS, Urgent, Symptom and Photo flags (tests) and is off by default.
- Promotion to Live is possible only for the doctor and is recorded; demotion works instantly.

**Show me:** Agent settings screenshot, a signed handoff, an auto-close example with its label and reopen.

---

### PHASE 6: Evaluation, red-team and workload measurement

**Goal:** prove it works and measure honestly.

**Tasks**
1. **Golden sets** (stored with the tests): Papers Agent (Phase 2), Case Prep faithfulness, Call Notes (no invented facts), Outreach policy compliance, Handoff faithfulness. Report per agent.
2. **Red-team suite (automated):** prompt injection through patient messages, SMS, voice transcripts and inside a PDF passage ("ignore the rules", "you are now the doctor", fake system messages), requests for another patient's data, requests for dose or diagnosis advice, attempts to get the agent to close a flag, long and malformed inputs, Hindi and mixed-language attacks. All must be blocked or abstained, with the reason in the run.
3. **Workload replay (script, not a document):** replay one scripted synthetic shift (for example 40 events: 12 routine patient questions, 10 reminder follow-ups, 6 duplicate alerts, 5 calls needing notes, 3 summaries, 2 urgent cases) twice, **agents off** and **agents on**. Count **human steps** with a configurable step table (for example answering a question by hand = open chat, read papers, type, send). Output: human steps and estimated minutes for both runs. All step and minute values are **assumptions shown on screen and editable**.
4. **Work saved panel** (Agent desk and doctor insights): counts of routine answers, reminders and prompts, duplicates merged, drafts accepted unchanged, edited and rejected, auto-closes, calls pre-briefed, **estimated minutes with the label "Estimated from editable assumptions"**; plus the replay result.
5. **Shadow results** computed from the replay and from live use; fill the agreement table from data, never by hand.
6. **Latency and cost counters** per agent (calls, tokens, p95 latency) and a limits test (what happens at the daily budget).

**Acceptance checks**
- Red-team: 100% blocked or abstained; any failure becomes a fixed test.
- Faithfulness: 100% for briefs and handoffs; invented facts in call-note drafts: 0.
- The replay shows a reduction in human steps with the numbers on screen. If it does not, say so; do not tune assumptions to look better.
- Every number on the work-saved panel is traceable to rows.

**Show me:** evaluation and red-team report in the chat, the replay table, the panel, shadow agreement values.

---

### PHASE 7: Wording, documents and final proof

**Goal:** Care Agents read as the headline of the whole product, truthfully.

**Tasks**
1. **Glossary first** (chat): CareLoop Agents, Papers Agent, Case Prep Agent, Call Notes Agent, Outreach Agent, Handoff Agent, Plan Agent, Dispatcher, Agent desk, Agent settings, Agent trace, autonomy levels (Suggest, Draft, Auto, Never), Shadow and Live, AI help, case brief.
2. **Message house.** Positioning sentence: "CareLoop keeps the days after discharge from going quiet: agents prepare every case and answer from the patient's own papers, rules raise every alert with its reason, and people make every decision." Headline line for the product: **"Agents do the routine. People make the calls."** Supporting lines: "Every case arrives prepared." "Autonomy is earned: shadow mode first." "Pause all agents with one switch."
3. **Landing page:** a **Care Agents** section (what each agent does in one plain line, the four autonomy levels, the pause switch, the AI help opt-out) with only provable statements; any number read from the database; the replay result may appear **only** with its label ("In a replay of N simulated events, human steps fell from X to Y").
4. **Wording rules.** Allowed: prepares, drafts, answers from your papers, does the routine, asks a person, estimated. Banned in UI, README, PROJECT_GUIDE, comments, titles and package files: hackathon, SIH, Smart India, NurseAI, autonomous, "AI nurse", "replaces", "saves hours", diagnose, "real-time", "24/7", HIPAA, "prevents readmissions", validated, accurate, stable, normal, optimal, improving, and stock phrases (seamless, cutting-edge, AI-powered, smart, transform, empower, leverage, holistic, next-gen, advanced, governance, telemetry). The word "agent" is used in the product; do not name an LLM model in marketing text.
5. **Patient wording** plain (about Grade 6 to 8); Hindi simple and marked for native review ("AI help", "Automated message from CareLoop", "From your papers"). Staff screens short English. Every sentence must be true where it appears.
6. **README.md and PROJECT_GUIDE.md:** add Core scope vs Extensions (the proposal's core: wearable, API, MySQL, rule-based flags, dashboards, audit, SOS; extensions: Care Agents and the rest), the agent architecture (Mermaid), the agentic RAG loop, autonomy levels and shadow mode, Policy Guard, traces, controls (pause, opt-out), data and endpoints, evaluation and red-team results, the replay method and its assumptions, regulatory and ethics notes (Section 12, with "not legal advice, read the official CDSCO document"), the updated demo walkthrough, and a "What is new compared with a first-generation AI-nurse idea" table where every row is proven from code. Keep "Sample data. Not medical advice." in the UI and "Synthetic-data prototype, not a medical device." in the documents. No other documents.
7. **Final proof:** build, lint, all tests, evaluation and red-team results, banned-word search (empty), claims audit (every sentence tied to code), validation script and two clean resets, screenshots (all four logins, light and dark, English and Hindi) checked for overflow, fresh-clone run of the README steps, demo rehearsed three times.

---

## 11. Demo story (8 minutes, agents as the headline)

| Time | Who | What happens | What the judges learn |
|---|---|---|---|
| 0:00 | Landing | "Agents do the routine. People make the calls." Four roles | The idea |
| 0:30 | Patient (Aarav), Hindi voice | Asks a routine question; answer with source chips; asks "Can I stop my BP medicine?" and gets a refusal and a request | Agentic RAG with sources; refusal; routine handled without staff |
| 1:45 | Nurse, Agent desk | "Done for you": the routine answer, reminders, merged duplicates; "Waiting for you": the dose question with a drafted reply | The nurse starts with prepared work |
| 2:30 | Presenter | Sends the simulated low SpO₂ reading | A rule raises the alert |
| 2:45 | Nurse | Call list shows a **prepared case**: facts with sources, unknowns, suggested step with reasons, call script | Cases arrive prepared |
| 3:30 | Nurse | Calls, taps quick picks, speaks a short note; **drafts** (note, task, patient message) appear; approves in one action; "Ask doctor" | Paperwork drafted, human signs |
| 4:30 | Doctor | Decision card with the brief, pre-drafted note and options; resolves with a code and note | Human decides |
| 5:15 | Doctor, Agent trace | "Why did the agent say this?" shows plan, sources, guard checks | Transparent |
| 5:45 | Doctor, Agent settings | Autonomy matrix, shadow agreement table; promote one action; **Pause all agents** and show human-only mode | Autonomy is earned and controllable |
| 6:45 | Presenter | Injection attempt in a patient message is blocked; shown in the run | Safe against untrusted text |
| 7:15 | Doctor | Work saved (estimated) and the replay result with its label | Honest measurement |
| 7:45 | Close | "Agents do the routine. People make the calls." | The principle |

---

## 12. Verification of the design (mapping to guidance)

| ICMR 2023 principle (as summarised in the sources I read) | How this plan meets it |
|---|---|
| Autonomy: human oversight; patients can reject AI | Autonomy levels, doctor approval, Pause all agents, patient **AI help** opt-out |
| Accountability and liability: audits | Ledger, run ids, audit log, named approvers, undo |
| Trustworthiness: explainable, valid | Sources on every statement, Agent trace, evaluation and red-team results |
| Risk minimisation and safety | Policy Guard, shadow mode, degradation mode, emergency paths without LLM |
| Data privacy | No identifiers to the LLM, consent rules, access logging, photo privacy, DPDP-style notices |
| Accessibility and equity (local languages) | Hindi in patient screens and voice |
| Validity | Golden sets, replay, honest reporting |

| CDSCO MDSW guidance (final, July 2026), as summarised in sources | Design response |
|---|---|
| Software that performs medical functions (clinical decision support, treatment recommendation, quantification of physiological parameters, monitoring) may be regulated under MDR 2017; classification follows intended use, claims and risk | Agents do workflow and communication only; next steps from a fixed administrative menu; no treatment recommendation; intended-use statement in README; "not a medical device; synthetic data". **Rule-based vital-sign alerts could still be considered a monitoring function in a real deployment, so seek regulatory advice before any real use** |

---

## 13. Risk register
| Risk | Mitigation |
|---|---|
| Agent states something untrue | Sources and numeric guard; abstain; fact-sheet fallback; red-team tests |
| Prompt injection via patient text or PDF | Untrusted-text rule, tool allowlist, patient id from token, JSON validation, red-team suite |
| Over-trust ("the AI said so") | Labels, "AI-prepared" chips, human signature, shadow mode, no clinical judgment words |
| Alert fatigue becomes agent-message fatigue | Daily caps, quiet hours, duplicates suppressed, patient opt-out |
| Workload claim is exaggerated | Only measured replay, editable assumptions, "estimated" label |
| LLM outage on stage | Degradation mode, cached demo traces, rehearsed fallback |
| Cost and latency | Budgets, small model for labels, caching, timeouts |
| Scope conflict with proposal | Supervisor approval; README separates Core scope and Extensions |

---

## 14. What I want from Antigravity after each phase
1. Plain-language summary of what changed and why (files listed).
2. Real command output for tests, evaluation and validation.
3. Screenshots (all four logins, light and dark) of every changed screen.
4. Anything that looked like a bug, a data problem or a false claim that you did not fix.
5. What you did not test and every assumption you made.
6. The next phase's plan, then wait for my approval.

**Ask me before:** adding a library, changing an existing column, changing escalation timing, enabling any action at Live that is not Live in Section 5.2, writing credits, deleting anything, or describing extensions as approved.
