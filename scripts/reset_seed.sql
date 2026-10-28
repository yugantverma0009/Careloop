-- scripts/reset_seed.sql
-- Resets medicines, prescriptions, and today's medication logs to clean, realistic synthetic data.

USE careloop;

-- 1. Update medicines with clear, synthetic, non-brand names
UPDATE medicines SET medicine_name = 'CardioPulse-XR', general_notes = 'Synthetic cardiac recovery tablet (database testing only)' WHERE medicine_id = 1;
UPDATE medicines SET medicine_name = 'VasculoNorm-5', general_notes = 'Synthetic vascular balance tablet (database testing only)' WHERE medicine_id = 2;
UPDATE medicines SET medicine_name = 'GastroShield-D', general_notes = 'Synthetic gastric protection capsule (database testing only)' WHERE medicine_id = 3;

-- 2. Update prescription instructions
UPDATE prescriptions SET dose_instructions = 'Take 1 tablet with water after breakfast' WHERE prescription_id = 1;
UPDATE prescriptions SET dose_instructions = 'Take 1 tablet with water after dinner' WHERE prescription_id = 2;
UPDATE prescriptions SET dose_instructions = 'Take 1 capsule in the afternoon' WHERE prescription_id = 3;
UPDATE prescriptions SET dose_instructions = 'Take 1 tablet at bedtime' WHERE prescription_id = 4;

-- 3. Standardize prescription times to realistic schedule
-- Rx 1: 08:00:00 (Morning)
-- Rx 2: 13:00:00 (Afternoon)
-- Rx 3: 18:30:00 (Evening)
-- Rx 4: 21:30:00 (Night)
DELETE FROM prescription_times WHERE prescription_id IN (1, 2, 3, 4);
INSERT INTO prescription_times (prescription_id, dose_time) VALUES
(1, '08:00:00'),
(2, '13:00:00'),
(3, '18:30:00'),
(4, '21:30:00');

-- 4. Clean up extraneous medication logs for today (keep only 1 per prescription schedule)
DELETE FROM medication_logs
WHERE scheduled_for >= CURDATE() AND scheduled_for < CURDATE() + INTERVAL 1 DAY;

-- Regenerate today's doses cleanly
CALL sp_generate_daily_doses(CURDATE());
