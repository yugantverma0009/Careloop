-- scripts/reset_seed.sql
-- Resets medicines, prescriptions, and today's medication logs to clean, realistic synthetic data.
-- Meets Brief Section 9.4 requirements (no real drug brand names, clean realistic daily schedule).

USE careloop;

-- 1. Update medicines with clear, synthetic, non-brand names
UPDATE medicines SET medicine_name = 'CardioPulse-XR', general_notes = 'Synthetic cardiac recovery tablet (database testing only)' WHERE medicine_id = 1;
UPDATE medicines SET medicine_name = 'VasculoNorm-5', general_notes = 'Synthetic vascular balance tablet (database testing only)' WHERE medicine_id = 2;
UPDATE medicines SET medicine_name = 'GastroShield-D', general_notes = 'Synthetic gastric protection capsule (database testing only)' WHERE medicine_id = 3;

-- 2. Deactivate duplicate test prescriptions for Patient 1
UPDATE prescriptions SET active_status = 0 WHERE prescription_id IN (11, 12);
UPDATE prescriptions SET active_status = 1, dose_instructions = 'Take 1 tablet after breakfast (08:00) and 1 tablet after dinner (20:00) with water' WHERE prescription_id = 1;
UPDATE prescriptions SET active_status = 1, dose_instructions = 'Take 1 tablet in the afternoon (13:00) with water' WHERE prescription_id = 2;

-- 3. Standardize prescription times to realistic schedule
-- Rx 1: 08:00:00 (Morning) & 20:00:00 (Evening)
-- Rx 2: 13:00:00 (Afternoon)
DELETE FROM prescription_times WHERE prescription_id IN (1, 2, 11, 12);
INSERT INTO prescription_times (prescription_id, dose_time) VALUES
(1, '08:00:00'),
(2, '13:00:00'),
(1, '20:00:00');

-- 4. Clean up test medication logs for today
DELETE FROM medication_logs
WHERE scheduled_for >= CURDATE() AND scheduled_for < CURDATE() + INTERVAL 1 DAY;

-- 5. Regenerate today's doses cleanly
CALL sp_generate_daily_doses(CURDATE());

-- 6. Set morning dose as Taken_Confirmed for realistic active day demo
UPDATE medication_logs ml
JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
SET ml.status = 'Taken_Confirmed', ml.recorded_at = TIMESTAMP(CURDATE(), '08:15:00'), ml.recorded_by = 'Patient'
WHERE pr.patient_id = 1
  AND ml.scheduled_for = TIMESTAMP(CURDATE(), '08:00:00');

