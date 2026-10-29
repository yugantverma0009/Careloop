# Phase 1: Defect Root Cause Analysis & Demo Seed Proposal

**Date:** 2026-10-30  
**Status:** Audit Complete — Awaiting User Approval to Apply Reseed  
**Governing Principle:** *"The LLM talks. Rules decide. Humans act."*

---

## 1. Root Cause Analysis of Defects (Section 1 Findings)

### Defect 1: Duplicate Handoff Cards & 137-Item Action List
- **Observed Behavior:** Shift handoff page displays duplicate cards for patients (e.g., Kabir Mehta twice, Rajesh Verma twice) and an overwhelming 137-item task list for Patient #1.
- **Root Cause in Code:**
  1. In `backend/app/main.py:3842-3865` (`get_shift_handoff`):
     ```sql
     SELECT p.patient_id, p.patient_code, p.full_name, ...
     FROM patients p
     LEFT JOIN discharge_records d ON d.patient_id = p.patient_id
     LEFT JOIN care_staff cs ON cs.staff_id = d.attending_staff_id
     LEFT JOIN care_assignments ca ON ca.patient_id = p.patient_id AND (ca.ends_at IS NULL OR ca.ends_at > NOW())
     ```
     `care_assignments` contains two active rows per patient (one for Primary Doctor, one for Nurse). Joining `care_assignments` without `DISTINCT` or `GROUP BY p.patient_id` duplicates every patient in the handoff list!
  2. For the action list: `follow_up_tasks` in `backend/app/main.py:3908` queries all uncompleted tasks for the patient. Due to repeated test runs and chat requests without de-duplication, Patient #1 accumulated 155 tasks, which were all dumped into the handoff card without grouping or capping.
- **Fix:** Add `SELECT DISTINCT p.patient_id, ...` in `get_shift_handoff`, de-duplicate follow-up tasks so each topic generates exactly one task, and limit handoff action items to at most 5 lines per patient.

---

### Defect 2: Inconsistent Day Numbers ("Day 15 vs Day 3")
- **Observed Behavior:** Aarav Patel is displayed as "Post-discharge Day 15" on the doctor worklist and "Post-CABG Day 3" on the patient overview and login cards.
- **Root Cause in Code:**
  1. In `discharge_records`, Patient 1 has `discharge_date = '2026-10-16'` and static text `condition_summary = 'Post-CABG Day 3'`.
  2. Today's date is `2026-10-30`. The backend computes `DATEDIFF(CURDATE(), d.discharge_date) + 1` = `DATEDIFF('2026-10-30', '2026-10-16') + 1` = `14 + 1 = 15`.
  3. Because fixed dates were seeded instead of relative dates, the day number drifts every single calendar day while the condition summary remains frozen at "Day 3".
- **Fix:** Use relative date calculations in `scripts/seed_demo.py` (`discharge_date = CURDATE() - INTERVAL (N - 1) DAY`). Clean condition summaries to clinical condition names only (e.g. `'Post-CABG Recovery'`, `'Total Knee Arthroplasty'`) and let the dynamic `day_number` append consistently across all screens.

---

### Defect 3: "Pulse 450 bpm, Invalid" Shown as Latest Headline Reading
- **Observed Behavior:** The patient home and doctor vitals card prominently display `Pulse 450 bpm, Invalid` as the headline reading.
- **Root Cause in Code:**
  1. The database view `v_latest_sensor_readings` in `database/careloop_mysql_v2_detailed.sql:480-490` uses:
     ```sql
     ROW_NUMBER() OVER (PARTITION BY sr.patient_id, sr.measurement_type ORDER BY sr.measured_at DESC) AS rn
     ```
     without filtering out `quality_status = 'Invalid'`.
  2. When the simulator or test script posts an out-of-bounds telemetry spike (450 bpm), the sensor plausibility trigger correctly tags it as `'Invalid'`. However, `rn = 1` still picks that row because it is the most recent timestamp.
  3. `backend/app/main.py:553` and `1610` read from `v_latest_sensor_readings` directly and send it to the frontend as the patient's primary headline vitals.
- **Fix:** Update view query logic or endpoint query to filter for valid readings (`quality_status IN ('Good', 'Simulated', 'Degraded')`) for the headline metric, while surfacing invalid readings separately in an auxiliary "Data Check" note (`"1 reading ignored: impossible value"`).

---

### Defect 4: Overdue Time Rendered as "Overdue by 3181m"
- **Observed Behavior:** Worklist SLA chip displays raw minute counters such as `Overdue by 3181m`.
- **Root Cause in Code:**
  In `backend/app/main.py:1814-1816`:
  ```python
  if tier == "Immediate" and delta_min > 15:
      is_overdue = True
      overdue_display = f"Overdue by {delta_min - 15}m"
  ```
  When an immediate flag has been open for 2 days (3,196 minutes), `delta_min - 15` outputs `3181m` instead of formatted days and hours.
- **Fix:** Add human-friendly duration formatting helper: `> 1440m` -> `f"{days}d {hours}h"`, `> 60m` -> `f"{hours}h {mins}m"`, `< 60m` -> `f"{mins}m"`.

---

### Defect 5: Raw Enum Label "Review_Soon"
- **Observed Behavior:** Clinician triage tables and task items show the raw database enum value `[Review_Soon]`.
- **Root Cause in Code:**
  1. In `frontend/src/components/CareLoopStaffPortal.jsx:1857`:
     `<span style={{ ... }}>[{fl.severity}]</span>` renders raw enum string directly.
  2. In `TaskQueue.jsx:376`:
     `Linked to Flag #{t.flag_id} {t.flag_severity ? `(${t.flag_severity})` : ''}` renders raw enum string.
  3. In `PatientOverviewTab.jsx:979` and `1220`:
     `fl.severity.replace('_', ' ')` leaves "Review Soon" in uppercase rather than clinical sentence case "Review soon".
- **Fix:** Implement centralized formatter `formatSeverity(sev)` mapping `Review_Soon` -> `"Review soon"`, `Urgent_Review` -> `"Urgent"`, `Immediate` -> `"Immediate"`, `Routine` -> `"Routine"`.

---

### Defect 6: Hard-Coded Medical Threshold "SpO2 < 90%" on Every Handoff Card
- **Observed Behavior:** Every handoff card includes identical contingency text: `"Standard escalation protocol: If SpO2 < 90% or severe chest pain, escalate to attending doctor."`
- **Root Cause in Code:**
  In `backend/app/main.py:3945`:
  ```python
  contingency_note = c_note_row["note_text"] if c_note_row else "Standard escalation protocol: If SpO2 < 90% or severe chest pain, escalate to attending doctor."
  ```
  When no clinician note exists for the patient (the case for 90% of patients), it falls back to hardcoded invented protocol text containing an unapproved clinical threshold.
- **Fix:** Replace hard-coded string fallback with patient-specific, doctor-approved limits queried from `alert_rules` (e.g. `"Escalation protocol: contact attending doctor if SpO2 falls below approved limit of 94%"`), or clinician-authored contingency notes.

---

### Defect 7: Generic Text "Patient #1 (Aarav Patel): Clinical recovery threshold logged..."
- **Observed Behavior:** Flags in triage display generic copy hiding the actual physiological or clinical reason.
- **Root Cause in Code:**
  Legacy seed script created mock flags with static string `Patient #1 (Aarav Patel): Clinical recovery threshold logged for monitoring team review.` instead of routing data through the real rule engine triggers (`trg_sensor_rules_after_insert`, `trg_symptom_rules_after_insert`).
- **Fix:** Generate all flags through the actual stored procedures, simulated sensor readings, and symptom check-in triggers, ensuring every flag reason explicitly quotes the reading and the clinician-approved limit (e.g. `"SpO2 reading 91% is below the clinician-approved limit of 94%"`).

---

## 2. Proposal for Demo Scripts

### 2.1 `scripts/reset_demo.sql`
- **Execution Time:** < 5 seconds.
- **Operations:**
  1. Truncates all transactional tables: `sensor_readings`, `flags`, `escalations`, `follow_up_tasks`, `ai_summaries`, `audit_log`, `contact_log`, `clinician_notes`, `flag_events`, `symptom_reports`, `symptom_report_tags`, `chat_messages`, `chat_message_sources`, `chat_feedback`, `medication_logs`, `appointments`, `care_assignments`, `alert_rules_history`, `risk_context`, `risk_snapshots`.
  2. Seeds exactly 5 patients with relative discharge dates:
     - Patient 1: `Aarav Patel` (CL-00001, 41y, Post-CABG Recovery, `CURDATE() - INTERVAL 2 DAY` -> Day 3)
     - Patient 2: `Meera Sharma` (CL-00002, 54y, Total Knee Arthroplasty, `CURDATE() - INTERVAL 5 DAY` -> Day 6)
     - Patient 3: `Rajesh Verma` (CL-00003, 47y, Community Pneumonia, `CURDATE() - INTERVAL 4 DAY` -> Day 5)
     - Patient 4: `Kabir Mehta` (CL-00004, 34y, Appendectomy Convalescence, `CURDATE() - INTERVAL 8 DAY` -> Day 9)
     - Patient 5: `Sunita Rao` (CL-00005, 63y, Congestive Heart Failure, `CURDATE() - INTERVAL 3 DAY` -> Day 4)
  3. Seeds exactly 2 staff members:
     - `Dr. Ananya Sharma` (Attending Doctor, staff_id: 1)
     - `Priya Nair` (Triage Nurse, staff_id: 2)
  4. Seeds exactly 4 user login accounts (`Demo@12345`):
     - `ananya.demo@example.test` (Doctor)
     - `priya.demo@example.test` (Nurse)
     - `aarav.demo@example.test` (Patient)
     - `caregiver1.demo@example.test` (Family Helper - Neha Patel, spouse)
  5. Seeds caregivers with consent states:
     - `Neha Patel` (Aarav's spouse, `consent_granted = TRUE`)
     - Meera Sharma's caregiver (`consent_granted = FALSE` for consent gate demo)
  6. Seeds devices:
     - Aarav: Active ESP32 wearable (`last_seen_at = NOW()`)
     - Meera: Silent wearable (`last_seen_at = NOW() - INTERVAL 8 HOUR`)
  7. Seeds clinician-approved alert rules per patient under Dr. Sharma's name (`alert_rules`).
  8. Seeds clean, non-brand synthetic medicines (`CardioPulse-XR`, `VasculoNorm-5`, `GastroShield-D`) with standard schedules.

---

### 2.2 `scripts/seed_demo.py`
- **Execution Time:** < 25 seconds.
- **Operations:**
  1. Executes `reset_demo.sql`.
  2. Generates daily dose events via `sp_generate_daily_doses(CURDATE())` and marks morning doses for Aarav as `Taken_Confirmed`.
  3. Inserts Aarav's 12 valid physiological telemetry points over 3 days, plus 1 invalid reading (450 bpm, tagged `Invalid` by trigger) to demonstrate data plausibility guarding.
  4. Fires genuine database triggers and procedures:
     - Calls `sp_evaluate_no_data_rules(NOW())` to create Meera's Review_Soon silent device flag.
     - Inserts Rajesh's Hindi emergency check-in (`"सीने में तेज दर्द"`) with `emergency_keyword_hit = TRUE` -> trigger creates Immediate flag.
     - Calls `sp_evaluate_missed_dose_rules(NOW())` to create Sunita's Review_Soon missed doses flag.
  5. Simulates escalation progression:
     - Meera's caregiver escalation logs `Skipped_No_Consent`.
     - Rajesh's escalation logs `Doctor_Alert` sent 20 minutes ago.
  6. Inserts Aarav's exact 6 chat messages:
     - Q1: "When is my next appointment?" -> Grounded answer with source.
     - Q2: "What warning signs should I watch for?" -> Grounded answer with source.
     - Q3: "Can I double my dose?" -> Safe refusal with 1 follow-up task.
     - Q4: "What should I eat?" -> "Information not in discharge papers" with Ask Care Team button.
     - Q5: Follow-up clarification.
     - Q6: "Thank you".
  7. Inserts 2 waiting draft AI summaries (Meera, Rajesh) and 1 approved summary (Kabir).

---

### 2.3 `scripts/validate_demo.py`
- **Execution Time:** < 3 seconds.
- **Automated Validation Checks:**
  1. `assert patients_count == 5`
  2. `assert care_staff_count == 2`
  3. `assert user_accounts_count == 4`
  4. `assert open_flags_count == 3` (Meera, Rajesh, Sunita)
  5. `assert open_tasks_count == 5`
  6. `assert completed_tasks_count == 1`
  7. `assert pending_summaries_count == 2`
  8. `assert approved_summaries_count == 1`
  9. `assert audit_events_count >= 25 and audit_events_count <= 40`
  10. `assert no_test_strings_leak`: zero occurrences of "Unit test", "microphone test", "Identical submission test", or "Patient #[0-9]+" in flags, tasks, or summaries.
  11. `assert identity_consistency`: patient name in text matches `patients.full_name`.
  12. `assert day_number_consistency`: computed day matches across all endpoints.
  13. `assert latest_reading_valid`: headline reading is not `quality_status = 'Invalid'`.
  14. `assert handoff_no_duplicates`: handoff returns exactly 5 unique patient cards.
  15. `assert no_hardcoded_protocols`: zero instances of `"SpO2 < 90%"` in handoff contingency.

---

## 3. Next Steps & Approval Gate

Antigravity is completely paused and awaiting your explicit approval:
- **No data has been deleted or rewritten.**
- **No stored procedures or database schemas have been altered.**
- Once approved, Antigravity will proceed to execute the seed rebuild and verify it with `validate_demo.py`.
