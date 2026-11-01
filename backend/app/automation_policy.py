"""
backend/app/automation_policy.py — CareLoop Automation Policy & Safety Gate

Governs what the background automation / Rounds may perform autonomously:
- Rule: "Automate the routine. Propose the rest. Humans decide."
- Quiet hours: 22:00 - 07:00 (only SOS, emergency escalations, and 'Are you OK?' fall prompts may bypass).
- Dose reminder limits: At most 2 reminders per scheduled dose.
- Daily patient prompt limits: At most 3 automated patient messages per day outside dose reminders.
- Emergency freeze: No new automated prompts while a patient has an open emergency/urgent flag.
- Patient pause: Honored when rounds_paused_until > current_time.
- Patient STOP: Honored when sms_opt_out is True and channel is SMS.
- Every automated action requires an explicit clinical or operational reason.
"""

from datetime import datetime, time
from typing import Dict, Any, Optional, Tuple, Union

# Configurable policy constants (demo defaults)
QUIET_HOURS_START_HOUR = 22  # 10:00 PM
QUIET_HOURS_END_HOUR = 7     # 07:00 AM
MAX_REMINDERS_PER_DOSE = 2
MAX_DAILY_PATIENT_MESSAGES = 3

# Action types that are routine vs urgent/safety overrides
ROUTINE_ACTION_TYPES = {
    "Dose_Reminder",
    "Checkin_Prompt",
    "Photo_Request",
    "Plan_Prompt",
    "Welcome_Call_Task",
}

SAFETY_OVERRIDE_ACTION_TYPES = {
    "SOS_Repeat",
    "Fall_Prompt",
    "Escalation_Step",
}


def is_in_quiet_hours(current_time: datetime) -> bool:
    """Returns True if current_time falls between 22:00 and 07:00."""
    hour = current_time.hour
    return hour >= QUIET_HOURS_START_HOUR or hour < QUIET_HOURS_END_HOUR


def can_send(
    patient: Dict[str, Any],
    action: Dict[str, Any],
    current_time: Optional[datetime] = None,
    daily_message_count: int = 0,
    has_open_emergency_flag: bool = False,
) -> Tuple[bool, str]:
    """
    Evaluates whether an automated action can be executed for the given patient.
    
    Args:
        patient: Patient dict containing keys:
            - rounds_paused_until (Optional[datetime or str])
            - rounds_pause_reason (Optional[str])
            - sms_opt_out (bool)
            - consent_status (Optional[str])
        action: Action dict containing keys:
            - action_type (str: Dose_Reminder, Checkin_Prompt, Photo_Request, Fall_Prompt, etc.)
            - channel (str: App, SMS, Voice, Task)
            - reason (str: required non-empty explanation)
            - attempts (int: current attempt count)
            - dose_reminder_count (int: optional, number of reminders already sent for this dose)
        current_time: Evaluation timestamp (defaults to datetime.now())
        daily_message_count: Number of non-dose automated messages already sent to this patient today.
        has_open_emergency_flag: True if patient currently has an active emergency flag.

    Returns:
        (allowed: bool, reason: str)
    """
    now = current_time or datetime.now()
    action_type = action.get("action_type", "")
    channel = action.get("channel", "App")
    action_reason = (action.get("reason") or "").strip()

    # 1. Mandatory audit reason check
    if not action_reason:
        return False, "Rejected: Every automated action must specify an explicit reason."

    # 2. Check patient rounds pause status
    paused_until = patient.get("rounds_paused_until")
    if paused_until:
        if isinstance(paused_until, str):
            try:
                paused_until = datetime.fromisoformat(paused_until.replace("Z", ""))
            except ValueError:
                paused_until = None
        if paused_until and paused_until > now:
            pause_reason = patient.get("rounds_pause_reason") or "Clinician paused"
            return False, f"Rounds paused for patient until {paused_until.strftime('%H:%M')}: {pause_reason}"

    # 3. Check SMS opt-out (STOP)
    if channel == "SMS" and patient.get("sms_opt_out"):
        return False, "Blocked: Patient has opted out of SMS messages (STOP)."

    # 4. Check open emergency flag
    # If patient has an open emergency flag, routine prompts must not disturb them
    if has_open_emergency_flag and action_type in ROUTINE_ACTION_TYPES:
        return False, "Blocked: Patient has an active emergency flag; non-emergency automation is suppressed."

    # 5. Check quiet hours (22:00 - 07:00)
    # Safety overrides (SOS, Fall prompt, Escalation) are exempt from quiet hours
    if is_in_quiet_hours(now) and action_type not in SAFETY_OVERRIDE_ACTION_TYPES:
        return False, "Blocked by quiet hours policy (22:00 to 07:00). Scheduled for morning."

    # 6. Check dose reminder limit (max 2 per dose)
    if action_type == "Dose_Reminder":
        reminder_count = action.get("dose_reminder_count", 0)
        attempts = action.get("attempts", 0)
        if reminder_count >= MAX_REMINDERS_PER_DOSE:
            return False, f"Max {MAX_REMINDERS_PER_DOSE} reminders per dose reached."
        if attempts >= 3:
            return False, "Max 3 execution retry attempts exceeded."

    # 7. Check daily automated patient message limit (max 3 non-dose messages/day)
    if action_type in {"Checkin_Prompt", "Photo_Request", "Plan_Prompt"}:
        if daily_message_count >= MAX_DAILY_PATIENT_MESSAGES:
            return False, f"Daily limit of {MAX_DAILY_PATIENT_MESSAGES} automated patient prompts reached for today."

    return True, "Allowed by automation policy"
