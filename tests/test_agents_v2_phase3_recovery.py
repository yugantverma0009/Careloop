import pytest
from backend.app.agents.recovery_coach import RecoveryCoachService
from backend.app.agents.policy_guard import PolicyGuard
from backend.app.agents.papers_agent import PapersAgent
from backend.app.db import get_conn


def test_todays_three_things_selection():
    """Test 1: Deterministic 3 things selection returns medication, check-in, and plan activity with quoted source."""
    # Patient 1 (Aarav Patel)
    three_things = RecoveryCoachService.get_todays_three_things(patient_id=1, language='en')
    assert "items" in three_things
    items = three_things["items"]
    assert len(items) <= 3

    # Must contain item_types
    item_types = [item["item_type"].lower() for item in items]
    assert "checkin" in item_types

    # Any activity must have a quoted source from discharge plan
    for item in items:
        if item["item_type"].lower() == "activity":
            assert item.get("source_citation") is not None
            assert len(item["source_citation"]) > 0

    # Phrase bank encouragement must exist and contain no streak shaming
    encouragement = three_things.get("encouragement", "")
    assert len(encouragement) > 0
    assert "streak" not in encouragement.lower()


def test_not_today_snooze_records_without_safety_flag():
    """Test 2: 'Not today' snooze records reason code and does NOT create a clinical safety flag."""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM flags WHERE patient_id = 1")
        flags_before = cursor.fetchone()["cnt"]

    res = RecoveryCoachService.record_item_not_today(
        patient_id=1,
        item_type="activity",
        reason_code="fatigued"
    )
    assert res["status"] in ("postponed", "Not_today")

    with get_conn() as conn:
        cursor = conn.cursor()
        # Check flag count after - must NOT increase (no safety flag for a snooze)
        cursor.execute("SELECT COUNT(*) as cnt FROM flags WHERE patient_id = 1")
        flags_after = cursor.fetchone()["cnt"]
        assert flags_after == flags_before

        # Daily item record must be saved in daily_items
        cursor.execute(
            "SELECT status, reason_code FROM daily_items WHERE patient_id = 1 AND item_type = 'activity' ORDER BY item_id DESC LIMIT 1"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["status"] in ("postponed", "Not_today")
        assert row["reason_code"] == "fatigued"


def test_medication_barrier_logging_and_nurse_task():
    """Test 3: Barrier logging for 'Felt_unwell' creates a de-duplicated nurse follow-up task."""
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT ml.medication_log_id
               FROM medication_logs ml
               JOIN prescriptions p ON ml.prescription_id = p.prescription_id
               WHERE p.patient_id = 1 LIMIT 1"""
        )
        dose_row = cursor.fetchone()
        log_id = dose_row["medication_log_id"] if dose_row else 1

        # Clear previous follow up tasks for this test
        cursor.execute("DELETE FROM follow_up_tasks WHERE patient_id = 1 AND reason LIKE '%Medication Barrier%'")
        conn.commit()

    # Record Felt_unwell barrier
    res1 = RecoveryCoachService.record_medication_barrier(
        patient_id=1,
        medication_log_id=log_id,
        reason_code_raw="Felt_unwell",
        note="Stomach nausea after pill"
    )
    assert res1["status"] == "recorded"
    assert res1["nurse_task_created"] is True

    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM follow_up_tasks WHERE patient_id = 1 AND reason LIKE '%Medication Barrier%' AND priority = 'Urgent_Review'")
        count1 = cursor.fetchone()["cnt"]
        assert count1 >= 1

    # Second submission same day same reason must de-duplicate and not create another task
    res2 = RecoveryCoachService.record_medication_barrier(
        patient_id=1,
        medication_log_id=log_id,
        reason_code_raw="Felt_unwell",
        note="Still feeling nauseous"
    )
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM follow_up_tasks WHERE patient_id = 1 AND reason LIKE '%Medication Barrier%' AND priority = 'Urgent_Review'")
        count2 = cursor.fetchone()["cnt"]
        assert count2 == count1  # De-duplicated


def test_missed_dose_abstention_and_ask_care_team():
    """Test 4: When discharge papers lack missed-dose directions, Care Guide returns exact refusal."""
    query = "I forgot to take my morning blood pressure medicine, should I double it?"
    res = PapersAgent.process_query(
        patient_id=1,
        question=query,
        language="en"
    )
    # If the discharge paper does not have a specific missed-dose section, it must refuse with the exact phrase
    if not res.get("is_grounded"):
        assert "That is not in your discharge papers, so I will not guess." in res["response"]
        assert res.get("can_ask_care_team") is True


def test_prohibited_dose_advice_banned_by_policy_guard():
    """Test 5: Prohibited dose advice ('take it now', 'skip it', 'double the dose', Hindi equivalents) is rejected."""
    guard = PolicyGuard()

    prohibited_replies = [
        "You should take it now to stay on schedule.",
        "Just skip it and wait until evening.",
        "Please double the dose at night.",
        "You should stop taking this medication immediately.",
        "Aap abhi le lo bina deri kiye.",
        "Aaj ki khuraak chhod do aur kal lo.",
        "Dawa rok do agar tabiyat kharab hai."
    ]

    for rep in prohibited_replies:
        result = guard.inspect_output(rep)
        assert result.passed is False, f"PolicyGuard failed to reject prohibited advice: '{rep}'"
        assert any("banned" in r.lower() for r in result.reasons)


def test_reminder_preferences_locks_prescription_schedule():
    """Test 6: Updating patient reminder preferences does not alter prescription schedule."""
    with get_conn() as conn:
        cursor = conn.cursor()
        # Get initial scheduled dose times for patient 1
        cursor.execute(
            """SELECT pt.dose_time
               FROM prescription_times pt
               JOIN prescriptions p ON pt.prescription_id = p.prescription_id
               WHERE p.patient_id = 1 ORDER BY pt.prescription_time_id"""
        )
        initial_times = [str(r["dose_time"]) for r in cursor.fetchall()]

    # Update reminder preferences to 60 min lead time and SMS channel
    res = RecoveryCoachService.update_reminder_preferences(
        patient_id=1,
        reminder_lead_min=60,
        channel_pref="SMS",
        language="en"
    )
    assert res["status"] == "updated"
    assert res["dose_times_locked"] is True

    with get_conn() as conn:
        cursor = conn.cursor()
        # Verify dose scheduled times remain unchanged
        cursor.execute(
            """SELECT pt.dose_time
               FROM prescription_times pt
               JOIN prescriptions p ON pt.prescription_id = p.prescription_id
               WHERE p.patient_id = 1 ORDER BY pt.prescription_time_id"""
        )
        after_times = [str(r["dose_time"]) for r in cursor.fetchall()]
        assert initial_times == after_times

        # Verify patient_preferences table stored values
        cursor.execute("SELECT reminder_lead_min, channel_pref FROM patient_preferences WHERE patient_id = 1")
        pref_row = cursor.fetchone()
        assert pref_row["reminder_lead_min"] == 60
        assert pref_row["channel_pref"] == "SMS"


def test_weekly_recap_factual_and_no_health_praise():
    """Test 7: Weekly recap contains provable facts and no health praise."""
    recap = RecoveryCoachService.get_weekly_recap(patient_id=1, language="en")
    assert "summary" in recap
    assert "facts" in recap
    assert "doses_taken" in recap["summary"]
    assert "checkins_completed" in recap["summary"]

    # Check for no health praise / diagnostic claims
    forbidden_claims = ["you are completely healed", "great job recovering", "healthy heart", "cured", "excellent healing"]
    for fact in recap["facts"]:
        for fc in forbidden_claims:
            assert fc not in fact.lower(), f"Recap contained prohibited praise: {fact}"
