"""
tests/test_automation_policy.py — Unit Tests for CareLoop Automation Policy

Verifies that can_send(patient, action) strictly enforces:
- Quiet hours (22:00 - 07:00)
- Paused rounds (rounds_paused_until)
- SMS STOP (sms_opt_out)
- Active emergency flag suppression of routine prompts
- Max 2 reminders per dose
- Max 3 daily patient prompts
- Mandatory explicit reasons
- Safety overrides for emergency/SOS/fall prompts
"""

import pytest
from datetime import datetime, timedelta
from backend.app.automation_policy import (
    can_send,
    is_in_quiet_hours,
    QUIET_HOURS_START_HOUR,
    QUIET_HOURS_END_HOUR,
    MAX_REMINDERS_PER_DOSE,
    MAX_DAILY_PATIENT_MESSAGES,
)


@pytest.fixture
def base_patient():
    return {
        "patient_id": 1,
        "full_name": "Aarav Patel",
        "rounds_paused_until": None,
        "rounds_pause_reason": None,
        "sms_opt_out": False,
        "consent_status": "Granted",
    }


@pytest.fixture
def routine_dose_action():
    return {
        "action_type": "Dose_Reminder",
        "channel": "SMS",
        "reason": "VasculoNorm-5 due at 13:00",
        "attempts": 0,
        "dose_reminder_count": 0,
    }


def test_allowed_during_normal_daytime_hours(base_patient, routine_dose_action):
    # 14:00 is daytime
    daytime = datetime(2026, 10, 30, 14, 0)
    allowed, reason = can_send(base_patient, routine_dose_action, current_time=daytime)
    assert allowed is True
    assert "Allowed" in reason


def test_missing_reason_rejected(base_patient, routine_dose_action):
    daytime = datetime(2026, 10, 30, 14, 0)
    routine_dose_action["reason"] = ""
    allowed, reason = can_send(base_patient, routine_dose_action, current_time=daytime)
    assert allowed is False
    assert "explicit reason" in reason


def test_quiet_hours_blocks_routine_dose_reminder(base_patient, routine_dose_action):
    # 23:30 is quiet hours
    night_time = datetime(2026, 10, 30, 23, 30)
    assert is_in_quiet_hours(night_time) is True
    allowed, reason = can_send(base_patient, routine_dose_action, current_time=night_time)
    assert allowed is False
    assert "quiet hours" in reason.lower()

    # 05:30 early morning is also quiet hours
    early_morning = datetime(2026, 10, 30, 5, 30)
    assert is_in_quiet_hours(early_morning) is True
    allowed, reason = can_send(base_patient, routine_dose_action, current_time=early_morning)
    assert allowed is False
    assert "quiet hours" in reason.lower()


def test_quiet_hours_allows_safety_overrides(base_patient):
    # Fall_Prompt and SOS_Repeat bypass quiet hours
    night_time = datetime(2026, 10, 30, 23, 30)
    fall_action = {
        "action_type": "Fall_Prompt",
        "channel": "App",
        "reason": "Possible fall reported by watch at 23:28",
        "attempts": 0,
    }
    allowed, reason = can_send(base_patient, fall_action, current_time=night_time)
    assert allowed is True
    assert "Allowed" in reason

    sos_action = {
        "action_type": "SOS_Repeat",
        "channel": "SMS",
        "reason": "SOS unacknowledged after 3 minutes",
        "attempts": 0,
    }
    allowed, reason = can_send(base_patient, sos_action, current_time=night_time)
    assert allowed is True
    assert "Allowed" in reason


def test_rounds_pause_stops_automation(base_patient, routine_dose_action):
    now = datetime(2026, 10, 30, 14, 0)
    base_patient["rounds_paused_until"] = now + timedelta(hours=4)
    base_patient["rounds_pause_reason"] = "Patient in medical procedure"

    allowed, reason = can_send(base_patient, routine_dose_action, current_time=now)
    assert allowed is False
    assert "paused" in reason.lower()
    assert "Patient in medical procedure" in reason


def test_expired_rounds_pause_allows_automation(base_patient, routine_dose_action):
    now = datetime(2026, 10, 30, 14, 0)
    base_patient["rounds_paused_until"] = now - timedelta(minutes=10)  # expired
    base_patient["rounds_pause_reason"] = "Past procedure"

    allowed, reason = can_send(base_patient, routine_dose_action, current_time=now)
    assert allowed is True
    assert "Allowed" in reason


def test_sms_opt_out_blocks_sms_only(base_patient, routine_dose_action):
    now = datetime(2026, 10, 30, 14, 0)
    base_patient["sms_opt_out"] = True

    # SMS channel blocked
    allowed_sms, reason_sms = can_send(base_patient, routine_dose_action, current_time=now)
    assert allowed_sms is False
    assert "opted out of SMS" in reason_sms

    # App channel allowed
    routine_dose_action["channel"] = "App"
    allowed_app, reason_app = can_send(base_patient, routine_dose_action, current_time=now)
    assert allowed_app is True
    assert "Allowed" in reason_app


def test_open_emergency_flag_blocks_routine_prompts(base_patient):
    now = datetime(2026, 10, 30, 14, 0)
    checkin_action = {
        "action_type": "Checkin_Prompt",
        "channel": "App",
        "reason": "Scheduled daily check-in prompt",
        "attempts": 0,
    }

    allowed, reason = can_send(
        base_patient,
        checkin_action,
        current_time=now,
        has_open_emergency_flag=True,
    )
    assert allowed is False
    assert "emergency flag" in reason.lower()


def test_max_dose_reminders_limit(base_patient, routine_dose_action):
    now = datetime(2026, 10, 30, 14, 0)
    routine_dose_action["dose_reminder_count"] = MAX_REMINDERS_PER_DOSE
    allowed, reason = can_send(base_patient, routine_dose_action, current_time=now)
    assert allowed is False
    assert "Max 2 reminders per dose reached" in reason


def test_max_daily_patient_messages_limit(base_patient):
    now = datetime(2026, 10, 30, 14, 0)
    checkin_prompt = {
        "action_type": "Checkin_Prompt",
        "channel": "App",
        "reason": "Daily recovery check-in requested",
        "attempts": 0,
    }
    # When already reached 3 non-dose messages
    allowed, reason = can_send(
        base_patient,
        checkin_prompt,
        current_time=now,
        daily_message_count=MAX_DAILY_PATIENT_MESSAGES,
    )
    assert allowed is False
    assert "Daily limit of 3 automated patient prompts reached" in reason


def test_retry_attempts_limit(base_patient, routine_dose_action):
    now = datetime(2026, 10, 30, 14, 0)
    routine_dose_action["attempts"] = 3
    allowed, reason = can_send(base_patient, routine_dose_action, current_time=now)
    assert allowed is False
    assert "retry attempts exceeded" in reason
