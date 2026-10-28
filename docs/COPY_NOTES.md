# CareLoop Copy Notes: Bugs, False Claims, and Data Strings

This document lists findings from the user-facing text audit, including database/seed data strings left untouched, potential bugs, and false claims identified in the current implementation.

---

## 1. Database & Seed Data Strings (Data to Leave Alone)

Per instruction, the following strings originate from MySQL tables (`medications`, `prescriptions`, `patients`, `discharge_records`, `flags`, `user_accounts`) and must NOT be altered in code:

| Data Type | Example Values | Reason |
| :--- | :--- | :--- |
| **Medication Names** | `Demo Medicine A`, `Demo Medicine B`, `Demo Medicine C`, `Atorvastatin 40mg`, `Metoprolol 25mg`, `Aspirin 75mg` | Stored in `medications.medicine_name` column. |
| **Prescription Instructions** | `Fictional sample instructions; not a real prescription.`, `Take 1 tablet daily at 09:00 with water after breakfast` | Stored in `prescriptions.instructions` column. |
| **Patient Demographics** | `Aarav Patel`, `Meera Joshi`, `Kabir Verma`, `Sunita Patel`, `Dr. Ananya Rao`, `Nurse Priya Sharma` | Stored in `patients.full_name`, `user_accounts.display_name`. |
| **Clinical Diagnosis in DB** | `CABG Post-Op Day 3`, `Post-CABG Day 4`, `Heart Failure Stage B` | Stored in `patients.primary_diagnosis` / `discharge_records`. |
| **DB Enum Values** | `Urgent_Review`, `Review_Soon`, `Immediate_Review`, `Routine_Review`, `Taken_Confirmed`, `Skipped_No_Consent`, `Open`, `Acknowledged` | Database ENUM definitions; altering would break SQL queries and constraints. |
| **Emergency Numbers** | `112` | Standard national emergency helpline number kept strictly intact. |

---

## 2. Identified Bugs & False Claims in Code (Report Only — Not Modified)

During the line-by-line audit, the following logic inconsistencies, false claims, and UI discrepancies were identified:

### 1. Hardcoded "Optimal Range" SpO₂ Badge Regardless of Value
* **File**: `frontend/src/components/CareLoopPatientPortal.jsx` (Line 803–806)
* **Finding**: The badge `<span className="status-pill status-pill-green">Optimal range</span>` is hardcoded directly underneath the SpO₂ measurement value.
* **Issue**: Even if a patient's SpO₂ reading drops below safe thresholds (e.g., to 88% or 91%), the UI still displays green "Optimal range", which is a clinical safety hazard.

### 2. Generic Flag Reason Overwriting Specific Sensor Details
* **File**: `frontend/src/components/CareLoopStaffPortal.jsx` (Line 809)
* **Finding**: `<div>{item.reason || item.flag_reason || 'Clinical alert flagged for review'}</div>`
* **Issue**: When an alert source fails to populate the specific physiological metric (e.g. "SpO2 88% below threshold 92%"), the fallback displays a generic "Clinical alert flagged for review", hiding the actual physiological trigger reason from the triage clinician.

### 3. Hardcoded "1 Vital Reading" in Safeguard Attention Card
* **File**: `frontend/src/components/CareLoopPatientPortal.jsx` (Line 963–968)
* **Finding**:
  ```jsx
  {hasUrgentFlag ? '1' : '0'}
  ...
  {hasUrgentFlag
    ? '1 clinical vital reading requires clinician review. Deterministic escalation ladder active.'
    : 'Zero critical deviations flagged. All continuous telemetry readings within safe discharge bounds.'}
  ```
* **Issue**: The text hardcodes the number "1" and "1 clinical vital reading" whenever `hasUrgentFlag` is true, even if there are 2 or 3 separate urgent flags active, or if the flag was triggered by a symptom check-in rather than a vital sign.

### 4. Hardcoded Single Summary Count in Export Summary Text
* **File**: `frontend/src/components/CareLoopPatientPortal.jsx` (Line 90–92)
* **Finding**: In `handleExportSummary`, `Safeguard Flags Active: ${hasUrgentFlag ? '1 (Clinician review requested)' : '0 (Clinically stable)'}`
* **Issue**: The generated summary report always reports "1" or "0", masking the actual count of active flags.

### 5. SLA Timeout Cards Disagree with Backend Escalation Scheduler
* **File**: `frontend/src/components/CareLoopStaffPortal.jsx` (Lines 586 & 632)
* **Finding**: The staff portal displays "SLA timeout: < 15 minutes" for Immediate Review and "< 2 hours" for Urgent Review.
* **Issue**: In `backend/app/escalation.py`, the actual ladder intervals configured are:
  - `LADDER_URGENT`: Step 1 (0m), Step 2 (0m), Step 3 (0m), Step 4 Caregiver SMS (10m).
  - `LADDER_REVIEW_SOON`: Step 1 (0m), Step 2 (20m), Step 3 (40m), Step 4 (90m).
  Neither schedule uses 15 minutes or 2 hours.

### 6. Filter Empty State Claims "All Patients Stable"
* **File**: `frontend/src/components/CareLoopStaffPortal.jsx` (Line 761)
* **Finding**: `No active triage flags under this filter. All patients clinically stable.`
* **Issue**: If the clinician selects the `Immediate_Review` filter tab and there are no immediate flags, the UI asserts "All patients clinically stable" even when there are multiple open `Urgent_Review` flags under the other tabs.

### 7. Hardcoded Patient Range in Staff Portal Dropdown
* **File**: `frontend/src/components/CareLoopStaffPortal.jsx` (Lines 862 & 1018)
* **Finding**:
  `[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((pid) => ...)`
* **Issue**: The seed dataset contains 12 patients (PIDs 1 through 12). Patients 11 and 12 cannot be selected from the Timeline or AI Summary review panels.
