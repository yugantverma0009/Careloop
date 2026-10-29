-- Verification script: Check identity consistency across flags, tasks, and ai_summaries.
-- Every check must return 0 rows for perfect data integrity.

SELECT 'flags mismatch' AS check_name, flag_id, patient_id, reason
FROM flags
WHERE (reason LIKE '%Aarav%' AND patient_id != 1)
   OR (reason LIKE '%Meera%' AND patient_id != 2)
   OR (reason LIKE '%Kabir%' AND patient_id != 3)
   OR (reason LIKE '%Sunita%' AND patient_id != 4)
   OR (reason LIKE '%Rajesh%' AND patient_id != 5)
   OR (reason LIKE '%Ananya%' AND patient_id != 6)
   OR (reason LIKE '%Vikram%' AND patient_id != 7)
   OR (reason LIKE '%Pooja%' AND patient_id != 8)
   OR (reason LIKE '%Arjun%' AND patient_id != 9)
   OR (reason LIKE '%Deepa%' AND patient_id != 10);

SELECT 'follow_up_tasks mismatch' AS check_name, followup_id, patient_id, reason
FROM follow_up_tasks
WHERE (reason LIKE '%Aarav%' AND patient_id != 1)
   OR (reason LIKE '%Meera%' AND patient_id != 2)
   OR (reason LIKE '%Kabir%' AND patient_id != 3)
   OR (reason LIKE '%Sunita%' AND patient_id != 4)
   OR (reason LIKE '%Rajesh%' AND patient_id != 5)
   OR (reason LIKE '%Ananya%' AND patient_id != 6)
   OR (reason LIKE '%Vikram%' AND patient_id != 7)
   OR (reason LIKE '%Pooja%' AND patient_id != 8)
   OR (reason LIKE '%Arjun%' AND patient_id != 9)
   OR (reason LIKE '%Deepa%' AND patient_id != 10);

SELECT 'ai_summaries mismatch' AS check_name, summary_id, patient_id, summary_text
FROM ai_summaries
WHERE (summary_text LIKE '%Aarav%' AND patient_id != 1)
   OR (summary_text LIKE '%Meera%' AND patient_id != 2)
   OR (summary_text LIKE '%Kabir%' AND patient_id != 3)
   OR (summary_text LIKE '%Sunita%' AND patient_id != 4)
   OR (summary_text LIKE '%Rajesh%' AND patient_id != 5)
   OR (summary_text LIKE '%Ananya%' AND patient_id != 6)
   OR (summary_text LIKE '%Vikram%' AND patient_id != 7)
   OR (summary_text LIKE '%Pooja%' AND patient_id != 8)
   OR (summary_text LIKE '%Arjun%' AND patient_id != 9)
   OR (summary_text LIKE '%Deepa%' AND patient_id != 10);
