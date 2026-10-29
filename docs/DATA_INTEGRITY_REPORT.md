# CareLoop Care Team Portal — Data Integrity Diagnosis Report

This diagnosis investigates the **Patient Identity Mismatches** identified in Section 3 (Finding #1) and Section 7.1 of the *Care Team Portal Upgrade Brief*.

---

## 1. Executive Summary

| Table | Total Rows Checked | Mismatched Rows Found | Severity | Root Cause |
|---|---|---|---|---|
| `flags` | 110 | **8 rows** | **Critical** (Patient Safety) | Synthetic seed script populated 10 clinical scenario items while clamping `patient_id` to `{1, 2, 3}`. |
| `follow_up_tasks` | 95 | **12 rows** | **Critical** (Patient Safety) | Initial demo tasks were generated referencing Patients 4–10, but stored with `patient_id` 1, 2, or 3. |
| `ai_summaries` | 21 | **9 rows** | **Critical** (Patient Safety) | Summaries 1–10 were generated with hardcoded prompt text describing Patients 1–10, but inserted with `patient_id` 1 and 2. |

---

## 2. Diagnosis Query Results (Section 7.1)

### 2.1 Mismatched Rows in `flags`
Query:
```sql
SELECT f.flag_id, f.patient_id, p.full_name AS db_patient, f.reason
FROM flags f
JOIN patients p ON p.patient_id = f.patient_id
WHERE f.reason REGEXP 'Patient #[0-9]+' AND f.reason NOT LIKE CONCAT('%', p.full_name, '%');
```

Output:
| Flag ID | Stored `patient_id` | DB Patient Name | Reason Stored in Record | Actual Patient Described in Text |
|---|---|---|---|---|
| **1** | 2 | Meera Sharma | `Patient #1 (Aarav Patel): Clinical recovery threshold logged...` | **Patient 1 (Aarav Patel)** |
| **4** | 2 | Meera Sharma | `Patient #4 (Sunita Rao): Clinical recovery threshold logged...` | **Patient 4 (Sunita Rao)** |
| **5** | 3 | Kabir Mehta | `Patient #5 (Rajesh Verma): Clinical recovery threshold logged...` | **Patient 5 (Rajesh Verma)** |
| **6** | 3 | Kabir Mehta | `Patient #6 (Ananya Iyer): Clinical recovery threshold logged...` | **Patient 6 (Ananya Iyer)** |
| **7** | 2 | Meera Sharma | `Patient #7 (Vikram Malhotra): Clinical recovery threshold logged...` | **Patient 7 (Vikram Malhotra)** |
| **8** | 1 | Aarav Patel | `Patient #8 (Pooja Gupta): Clinical recovery threshold logged...` | **Patient 8 (Pooja Gupta)** |
| **9** | 1 | Aarav Patel | `Patient #9 (Arjun Nair): Clinical recovery threshold logged...` | **Patient 9 (Arjun Nair)** |
| **10** | 1 | Aarav Patel | `Patient #10 (Deepa Joshi): Clinical recovery threshold logged...` | **Patient 10 (Deepa Joshi)** |

*Result*: 8 flag records show a severe mismatch where a clinician reviewing Meera Sharma (PID #2) or Aarav Patel (PID #1) would see text explicitly instructing them regarding an entirely different patient!

---

### 2.2 Mismatched Rows in `follow_up_tasks`
Query:
```sql
SELECT t.followup_id, t.patient_id, p.full_name AS db_patient, t.reason
FROM follow_up_tasks t
JOIN patients p ON p.patient_id = t.patient_id
WHERE (t.reason LIKE '%Contact %' OR t.reason LIKE '%Patient #%')
  AND t.reason NOT LIKE CONCAT('%', p.full_name, '%');
```

Output:
| Task ID | Stored `patient_id` | DB Patient Name | Reason Stored in Record | Target Patient Described |
|---|---|---|---|---|
| **4** | 2 | Meera Sharma | `Contact Sunita Rao regarding Congestive Heart Failure recovery...` | **Patient 4 (Sunita Rao)** |
| **5** | 2 | Meera Sharma | `Contact Rajesh Verma regarding Community Pneumonia recovery...` | **Patient 5 (Rajesh Verma)** |
| **6** | 2 | Meera Sharma | `Contact Ananya Iyer regarding Laparoscopic Cholecystectomy recovery...` | **Patient 6 (Ananya Iyer)** |
| **7** | 3 | Kabir Mehta | `Contact Vikram Malhotra regarding Lumbar Spinal Fusion recovery...` | **Patient 7 (Vikram Malhotra)** |
| **8** | 3 | Kabir Mehta | `Contact Pooja Gupta regarding Post-DKA Stabilization recovery...` | **Patient 8 (Pooja Gupta)** |
| **9** | 1 | Aarav Patel | `Contact Arjun Nair regarding Coronary Stent (PCI) recovery...` | **Patient 9 (Arjun Nair)** |
| **10** | 1 | Aarav Patel | `Contact Deepa Joshi regarding Total Hip Arthroplasty recovery...` | **Patient 10 (Deepa Joshi)** |
| **30** | 3 | Kabir Mehta | `Patient #5 (Rajesh Verma): Clinical recovery threshold logged...` | **Patient 5 (Rajesh Verma)** |
| **33** | 2 | Meera Sharma | `Patient #1 (Aarav Patel): Clinical recovery threshold logged...` | **Patient 1 (Aarav Patel)** |
| **36** | 3 | Kabir Mehta | `Patient #6 (Ananya Iyer): Clinical recovery threshold logged...` | **Patient 6 (Ananya Iyer)** |
| **40** | 1 | Aarav Patel | `Patient #8 (Pooja Gupta): Clinical recovery threshold logged...` | **Patient 8 (Pooja Gupta)** |
| **43** | 1 | Aarav Patel | `Patient #10 (Deepa Joshi): Clinical recovery threshold logged...` | **Patient 10 (Deepa Joshi)** |

*Result*: 12 tasks in the queue show a clinician assigned to follow up on "Meera Sharma", but the actual clinical prompt directs them to call Sunita Rao or Rajesh Verma.

---

### 2.3 Mismatched Rows in `ai_summaries`
Query:
```sql
SELECT s.summary_id, s.patient_id, p.full_name AS db_patient, s.summary_text
FROM ai_summaries s
JOIN patients p ON p.patient_id = s.patient_id
WHERE s.summary_text LIKE 'DRAFT SUMMARY (Patient #%'
  AND s.summary_text NOT LIKE CONCAT('%', p.full_name, '%');
```

Output:
| Summary ID | Stored `patient_id` | DB Patient Name | Summary Header in Text | Target Patient Described |
|---|---|---|---|---|
| **1** | 2 | Meera Sharma | `DRAFT SUMMARY (Patient #1 - Aarav Patel): Post-discharge Day 1...` | **Patient 1 (Aarav Patel)** |
| **3** | 2 | Meera Sharma | `DRAFT SUMMARY (Patient #3 - Kabir Mehta): Post-discharge Day 3...` | **Patient 3 (Kabir Mehta)** |
| **4** | 2 | Meera Sharma | `DRAFT SUMMARY (Patient #4 - Sunita Rao): Post-discharge Day 4...` | **Patient 4 (Sunita Rao)** |
| **5** | 2 | Meera Sharma | `DRAFT SUMMARY (Patient #5 - Rajesh Verma): Post-discharge Day 5...` | **Patient 5 (Rajesh Verma)** |
| **6** | 1 | Aarav Patel | `DRAFT SUMMARY (Patient #6 - Ananya Iyer): Post-discharge Day 6...` | **Patient 6 (Ananya Iyer)** |
| **7** | 1 | Aarav Patel | `DRAFT SUMMARY (Patient #7 - Vikram Malhotra): Post-discharge Day 7...` | **Patient 7 (Vikram Malhotra)** |
| **8** | 1 | Aarav Patel | `DRAFT SUMMARY (Patient #8 - Pooja Gupta): Post-discharge Day 8...` | **Patient 8 (Pooja Gupta)** |
| **9** | 1 | Aarav Patel | `DRAFT SUMMARY (Patient #9 - Arjun Nair): Post-discharge Day 9...` | **Patient 9 (Arjun Nair)** |
| **10** | 1 | Aarav Patel | `DRAFT SUMMARY (Patient #10 - Deepa Joshi): Post-discharge Day 10...` | **Patient 10 (Deepa Joshi)** |

*Result*: 9 summaries (Summaries #1, #3, #4, #5, #6, #7, #8, #9, #10) contain full clinical paragraphs detailing medical conditions and recovery metrics for one patient while being permanently associated with an unrelated patient's `patient_id`.

---

## 3. Mathematical Root Cause Analysis

### Was it a wrong SQL JOIN?
**No.** The SQL query `JOIN patients p ON p.patient_id = f.patient_id` is a correct 1:1 relational join on primary keys. The problem is inside the table data itself.

### Was it a UI template bug?
**No.** The UI correctly renders `item.patient_name` (joined from `p.full_name`) and `item.reason` from the database. The database itself contains mismatched `patient_id` and `reason` text.

### How did the data get corrupted?
The root cause is a **seed script sequence defect**:
1. When `careloop_mysql_v2_detailed.sql` was initially authored, only **3 patients** (`Aarav Demo` #1, `Meera Demo` #2, `Kabir Demo` #3) were inserted into the `patients` table (lines 796–799).
2. A demo dataset script was subsequently run to create 10 sample flags, 10 sample tasks, and 10 sample summaries (covering Patient #1 to Patient #10).
3. Because foreign key constraints `fk_flags_patient`, `fk_tasks_patient`, and `fk_summaries_patient` strictly require valid `patients.patient_id` values, and **patients 4 through 10 did not exist in the database at the time of insertion**, the script assigned the records to existing patient IDs:
   - Patient #8, #9, #10 were assigned to `patient_id = 1`
   - Patient #1, #4, #5, #7 were assigned to `patient_id = 2`
   - Patient #3, #5, #6 were assigned to `patient_id = 3`
4. Later, patients 4 through 10 were created in the database, but the existing records were never updated to point to their matching patient records.

---

## 4. Phase 1 Repair Strategy (Requires User Approval Before Running)

To permanently resolve this critical defect in Phase 1 without data loss:
1. **Schema Addition (`D-01`)**: Add `patient_code` (`CL-00001` through `CL-00010`) to `patients` table.
2. **Re-link Orphaned Records**:
   - For `flags` 1 to 10: update `f.patient_id = <extracted_id>` where reason has `Patient #<extracted_id>`.
   - For `follow_up_tasks` 1 to 10 & 30–43: update `t.patient_id = <extracted_id>` where reason has `Patient #<extracted_id>` or matches the patient name in `patients.full_name`.
   - For `ai_summaries` 1 to 10: update `s.patient_id = <extracted_id>` where summary text has `Patient #<extracted_id>`.
3. **Automated Consistency Test (`scripts/check_identity_consistency.sql`)**:
   Add a verification script and automated pytest that asserts:
   ```sql
   SELECT COUNT(*) FROM flags f JOIN patients p ON p.patient_id = f.patient_id
   WHERE f.reason REGEXP 'Patient #[0-9]+' AND f.reason NOT LIKE CONCAT('%', p.full_name, '%');
   -- Must return 0
   ```
4. **Clean Seed Regeneration**: Rebuild clean, consistent synthetic seed data for all 10 patients so that real rule engine flags (missed doses, silent devices, vital triggers) generate consistent reasons naturally.

*No data will be deleted or modified until explicit user approval is granted.*
