# CareLoop Care Team Portal — Phase 0 Read-Only Audit Report

This audit documents the current state of the CareLoop Care Team Portal (`/staff`), its frontend architecture, backend endpoints, database views and stored procedures, and evaluates them finding-by-finding against the **Care Team Portal Upgrade Brief**.

---

## 1. Architectural Overview of Current System

### 1.1 Frontend Structure
- **Component**: `frontend/src/components/CareLoopStaffPortal.jsx` (1,110 lines of React code).
- **Navigation State (`activeNav`)**: Switches between 4 views:
  1. `triage`: "Who needs attention" (flat table of open flags from `/staff/triage`).
  2. `timeline`: "Patient timeline" (events list from `/staff/patients/{pid}/timeline`).
  3. `tasks`: "Follow-up tasks" (pending task list from `/staff/follow-ups`).
  4. `summaries`: "Draft summaries" (AI summaries from `/staff/summaries/pending`).
- **State Management**: Local React state (`useState`, `useEffect`) polling `/staff/triage`, `/staff/follow-ups`, `/staff/summaries/pending` every 12 seconds via `setInterval`.

### 1.2 Backend REST Endpoints (`backend/app/main.py`)
All endpoints enforce JWT authentication with role authorization (`require_role("Doctor", "Nurse")`):

| Endpoint | HTTP Method | Handler Function | Current SQL Query / Procedure | Role Allowed |
|---|---|---|---|---|
| `/staff/triage` | `GET` | `get_triage_board` | Queries `v_triage_board` | Doctor, Nurse |
| `/staff/flags/{id}/acknowledge` | `POST` | `acknowledge_flag` | Calls `sp_acknowledge_flag(flag_id, staff_id, note)` | Doctor, Nurse |
| `/staff/follow-ups` | `GET` | `get_pending_follow_ups` | Queries `v_pending_followups` | Doctor, Nurse |
| `/staff/patients/{pid}/timeline`| `GET` | `get_patient_timeline` | Queries `v_patient_timeline` | Doctor, Nurse |
| `/staff/summaries/pending` | `GET` | `get_pending_summaries` | Queries `ai_summaries` where `reviewed_by_staff_id IS NULL` | Doctor, Nurse |
| `/staff/summaries/generate`| `POST` | `generate_ai_summary` | Calls LLM to generate draft, writes `ai_summaries` | Doctor, Nurse |
| `/staff/summaries/{id}/review`| `POST` | `review_summary` | Updates `reviewed_by_staff_id`, `reviewed_at` | Doctor only |

### 1.3 Database Views & Procedures (`careloop_mysql_v2_detailed.sql`)
1. **`v_triage_board`**:
   `SELECT p.patient_id, p.full_name AS patient_name, f.flag_id, f.severity, f.source_type, f.reason, f.status, f.created_at AS flagged_at, TIMESTAMPDIFF(MINUTE, f.created_at, NOW()) AS minutes_open, lr.risk_score, lr.risk_level FROM flags f JOIN patients p ON p.patient_id = f.patient_id LEFT JOIN v_latest_risk lr ON lr.patient_id = p.patient_id WHERE f.status IN ('Open','Acknowledged');`
2. **`v_pending_followups`**:
   `SELECT t.followup_id, p.patient_id, p.full_name AS patient_name, s.full_name AS assigned_to, t.reason, t.priority, t.status, t.created_at FROM follow_up_tasks t JOIN patients p ON p.patient_id = t.patient_id JOIN care_staff s ON s.staff_id = t.assigned_staff_id WHERE t.status = 'Pending';`
3. **`v_patient_timeline`**:
   `UNION ALL` of `sensor_readings`, `symptom_reports`, `medication_logs`, and `flags`.
4. **`sp_acknowledge_flag`**:
   Takes `(p_flag_id, p_staff_id, p_note)`. In an atomic transaction, updates `flags.status = 'Acknowledged'`, updates escalations, inserts a `follow_up_tasks` row, and writes an `audit_log` row.

---

## 2. Finding-by-Finding Gap Analysis (Brief Section 3)

| # | Brief Finding | Reality in Current Code | Severity | Brief Solution Required |
|---|---|---|---|---|
| **1** | **Patient identity mismatches** across flags, tasks, summaries. | **Confirmed Critical Defect**: 8 flags, 12 tasks, and 9 summaries store text describing a different patient than `patient_id` (see [docs/DATA_INTEGRITY_REPORT.md](file:///Users/yugantverma/Desktop/CareLoop/docs/DATA_INTEGRITY_REPORT.md)). | **Critical** | Add `patient_code`, re-link orphaned records, build `scripts/check_identity_consistency.sql` test (D-01). |
| **2** | **Reason text hides the rule reason**. | Flag table renders raw string `item.reason`, which in legacy seed rows is generic: `"Clinical recovery threshold logged for monitoring team review."` | High | Render verbatim reason plus evidence and rule trigger details (D-03). |
| **3** | **Un-grouped worklist with 66+ flags & all-100 scores**. | Flags are listed flat, row-by-row. Every row has `risk_score = 100` from `v_latest_risk` because risk snapshots saturate without reason deduplication. | High | Group per patient via `v_worklist_by_patient`; show explainable attention factors (D-02). |
| **4** | **Repeating identical emergency flags**. | Every emergency check-in submission creates an emergency flag row without deduplication. | High | Implement 60-minute duplicate suppression window in trigger (Section 7.3) and group on screen. |
| **5** | **Acknowledged rows show Acknowledge button**. | `CareLoopStaffPortal.jsx` line 837 renders `<button onClick={() => handleAcknowledge(item.flag_id)}>Acknowledge</button>` on EVERY row, even when `item.status === 'Acknowledged'`! Clicking it triggers 409 error. | High | Hide Acknowledge on acknowledged rows; show Resolve instead (D-03). |
| **6** | **Raised at shows time only**. | Table column renders `(item.flagged_at || item.created_at)?.slice(11, 19)`, completely omitting date, elapsed age, SLA target, and owner. | High | Display full date, elapsed age, SLA chip, and owner (D-02). |
| **7** | **Undefined review tiers**. | Immediate vs. Urgent vs. Routine are arbitrary without explicit SLA definitions. | Medium | Define tiers on screen: Immediate (<15m), Urgent (<2h), Review soon (<24h) (D-02). |
| **8** | **Sidebar counts are all-time totals**. | Sidebar shows total counts (`triageItems.length`, `followUps.length`, `summaries.length`), regardless of logged-in user or active filters. | Medium | Filter sidebar counts to active user's assigned/open workload (D-12). |
| **9** | **Timeline patient chips have no names**. | Timeline header renders raw loop `[1..10].map(pid => <button>Patient #{pid}</button>)`. Rows repeat `"Patient #1 · Event log"`. | High | Render `PatientIdentity` component with name, age, code, condition; remove event log repetition (D-05, D-06). |
| **10**| **Future doses shown as Unconfirmed**. | Doses scheduled for 20:00 today show `Unconfirmed` at 11:00 AM, looking like a failure. | Medium | Display "Scheduled" until dose time passes (D-06). |
| **11**| **Test text leaks into timeline**. | Test submissions like `"Dictated via microphone test at 17932..."` appear directly in the clinical timeline. | Medium | Clean seed data and filter test text (D-23). |
| **12**| **Flat timeline with no filters or charts**. | Timeline is an un-filtered list without date grouping, vitals chart, or quality indicators. | High | Add filter chips (Readings/Symptoms/Doses/Flags), day groups, and readings SVG chart with rule threshold lines (D-06). |
| **13**| **95 tasks with no actions**. | Tasks tab is a read-only list. Staff cannot claim, assign, log calls, snooze, or complete tasks with outcome codes. | High | Rebuild as an interactive queue with action modal and outcome codes (D-07). |
| **14**| **Raw enum text & no overdue emphasis**. | Displays raw string `Urgent_Review`, `Pending: 240.4h` without overdue styling. | Medium | Human-friendly labels ("Urgent", "Review soon") and overdue badge with due date. |
| **15**| **Auto-creating tasks on acknowledge**. | `sp_acknowledge_flag` always inserts into `follow_up_tasks`, generating 95+ unmanaged tasks. | Medium | Update `sp_acknowledge_flag` with `p_create_task` parameter so task creation is intentional (Section 7.3). |
| **16**| **Templated AI summaries with banned judgment words**. | Summaries use hardcoded templates repeating `"Continuous vitals stable"`. "Stable" is a judgment word that violates Section 2. | High | Fact-sheet-driven SBAR drafts without judgment words, with strict numeric and source guards (D-08). |
| **17**| **Summaries lack in-place edit & source tracking**. | Only has basic Approve/Reject. No text editing, no sources panel, no rejection reasons, no approver audit. | High | In-place editor, fact-sheet sources panel, rejection reason dialog, and versioned approval (D-08). |
| **18**| **Missing clinical workflow tools**. | No Patient Directory page, no Shift Handoff, no Care Rules view, no Call Log, no Audit Viewer. | High | Implement missing workflow views across Phases 2, 4, 5. |

---

## 3. Baseline Screenshots Verification

Baseline screenshots have been captured using Chrome DevTools Protocol and saved to [`docs/screenshots/baseline_staff/`](file:///Users/yugantverma/Desktop/CareLoop/docs/screenshots/baseline_staff/):

1. **Staff Triage (Who needs attention)**:
   - Light Mode: [staff_triage_light.png](file:///Users/yugantverma/Desktop/CareLoop/docs/screenshots/baseline_staff/staff_triage_light.png)
   - Dark Mode: [staff_triage_dark.png](file:///Users/yugantverma/Desktop/CareLoop/docs/screenshots/baseline_staff/staff_triage_dark.png)
2. **Staff Timeline**:
   - Light Mode: [staff_timeline_light.png](file:///Users/yugantverma/Desktop/CareLoop/docs/screenshots/baseline_staff/staff_timeline_light.png)
   - Dark Mode: [staff_timeline_dark.png](file:///Users/yugantverma/Desktop/CareLoop/docs/screenshots/baseline_staff/staff_timeline_dark.png)
3. **Staff Tasks**:
   - Light Mode: [staff_tasks_light.png](file:///Users/yugantverma/Desktop/CareLoop/docs/screenshots/baseline_staff/staff_tasks_light.png)
   - Dark Mode: [staff_tasks_dark.png](file:///Users/yugantverma/Desktop/CareLoop/docs/screenshots/baseline_staff/staff_tasks_dark.png)
4. **Staff Summaries**:
   - Light Mode: [staff_summaries_light.png](file:///Users/yugantverma/Desktop/CareLoop/docs/screenshots/baseline_staff/staff_summaries_light.png)
   - Dark Mode: [staff_summaries_dark.png](file:///Users/yugantverma/Desktop/CareLoop/docs/screenshots/baseline_staff/staff_summaries_dark.png)
5. **Landing, Login & Patient Pages (Visual Lock Verification)**:
   - Landing: [landing_light.png](file:///Users/yugantverma/Desktop/CareLoop/docs/screenshots/baseline_staff/landing_light.png), [landing_dark.png](file:///Users/yugantverma/Desktop/CareLoop/docs/screenshots/baseline_staff/landing_dark.png)
   - Login: [login_light.png](file:///Users/yugantverma/Desktop/CareLoop/docs/screenshots/baseline_staff/login_light.png), [login_dark.png](file:///Users/yugantverma/Desktop/CareLoop/docs/screenshots/baseline_staff/login_dark.png)
   - Patient Overview: [patient_overview_light.png](file:///Users/yugantverma/Desktop/CareLoop/docs/screenshots/baseline_staff/patient_overview_light.png), [patient_overview_dark.png](file:///Users/yugantverma/Desktop/CareLoop/docs/screenshots/baseline_staff/patient_overview_dark.png)

---

## 4. Phase 1 Implementation Plan

Upon receiving user approval, **Phase 1** will address:
- **D-01 (Identity Integrity)**: Add `patients.patient_code` (`CL-00001` - `CL-00010`), create shared `PatientIdentity` component, re-link mismatched seed records, and establish `scripts/check_identity_consistency.sql`.
- **D-02 (Worklist Rebuild)**: Create `v_worklist_by_patient` view; group rows by patient; display SLA chips, owners, tier definitions, and explainable attention score factors.
- **D-03 (Flag Detail Drawer & Lifecycle)**: Create `flag_events` table; implement slide-in Flag Detail Drawer; add `sp_resolve_flag` with reason codes and mandatory urgent notes; fix Acknowledge button display.
- **D-04 (Deduplication & Emergency Suppression)**: Group duplicate flags in UI and prepare the 60-minute emergency suppression trigger update.
- **D-10 (Escalation Visibility)**: Display multi-step escalation ladder timeline inside the flag drawer.
- **D-18 (Data Quality)**: Show Good/Questionable/Invalid/Simulated badges.
- **D-23 (Clean Seed Regeneration)**: Clean test text and build consistent 10-patient synthetic cohort.

### Files to Touch in Phase 1:
1. `database/care_team_upgrade.sql` (New additive migration file)
2. `scripts/check_identity_consistency.sql` (Automated data integrity test)
3. `scripts/relink_mismatched_records.sql` (Safe data repair script)
4. `backend/app/main.py` (Add `/staff/worklist`, `/staff/flags/{id}`, `/staff/flags/{id}/resolve`, `/staff/flags/{id}/dismiss` endpoints)
5. `frontend/src/services/api.js` (Add staff worklist and flag lifecycle API calls)
6. `frontend/src/components/PatientIdentity.jsx` (New shared two-identifier component)
7. `frontend/src/components/FlagDrawer.jsx` (New flag detail drawer component)
8. `frontend/src/components/CareLoopStaffPortal.jsx` (Upgrade triage table to grouped worklist with drawer)
9. `tests/test_staff_upgrade_p1.py` (Automated test suite)

### Questions for the User:
1. **Approval to Add `patient_code`**: May we add `patient_code VARCHAR(20) NOT NULL UNIQUE` (e.g. `CL-00001` to `CL-00010`) to the `patients` table via `database/care_team_upgrade.sql`?
2. **Approval to Re-link Mismatched Records**: May we run the safe UPDATE statements to re-link flags 1–10, tasks 1–10, and summaries 1–10 to their true `patient_id` as diagnosed in `docs/DATA_INTEGRITY_REPORT.md`?
3. **Approval for `sp_acknowledge_flag` Signature Change**: The brief specifies adding `p_create_task BOOLEAN` to `sp_acknowledge_flag` so acknowledging a flag does not uncontrollably spawn 95+ follow-up tasks. May we update the stored procedure and backend caller accordingly?
4. **Emergency Duplicate Trigger Approval**: May we apply the 60-minute emergency flag deduplication trigger (`trg_symptom_rules_after_insert`)?
