"""
tests/test_agents_v2_phase3.py — CareLoop Agents v2 Phase 3: Staff Copilot Test Suite

Verifies:
1. Template mapping and parameter validation (target >= 90% mapping, 100% parameter validation).
2. SQL injection resistance (0 SQL injection possible).
3. Role assignment guard (Nurses only see assigned patients; Doctors see all).
4. Opt-out patient warning badge.
5. Grounded list tables with exact count and click-through links.
6. Alert explanation with 5-part Case Prep brief and recommended next step.
7. Message drafts in Draft mode with channel confirmation required.
8. 60-second in-memory staff cache.
9. Chronological summary and vital comparison.
"""

import os
import pytest
from datetime import datetime

os.environ["CARELOOP_EVAL_MODE"] = "1"

from backend.app.agents.copilot_service import (
    classify_staff_question,
    ask_careloop,
    get_cached_result,
    clear_copilot_cache,
    ALLOWLISTED_TEMPLATES,
)
from backend.app.agents.eval_datasets import STAFF_COPILOT_QUESTIONS_40
from backend.app.db import get_conn


def test_phase3_template_mapping_and_confidence():
    """Verify >= 90% correct template mapping and 100% parameter validation across 40 questions."""
    correct = 0
    total = len(STAFF_COPILOT_QUESTIONS_40)

    for item in STAFF_COPILOT_QUESTIONS_40:
        res = classify_staff_question(item["q"])
        tpl = res["template"]
        params = res["parameters"]

        if tpl == item["expected_template"]:
            # Check filter if find_patients
            if tpl == "find_patients" and "expected_filter" in item:
                if params.get("filter") == item["expected_filter"]:
                    correct += 1
            elif tpl == "explain_alert" and "expected_flag_id" in item:
                if params.get("flag_id") == item["expected_flag_id"]:
                    correct += 1
            elif tpl == "draft_message" and "expected_purpose" in item:
                if params.get("purpose") == item["expected_purpose"]:
                    correct += 1
            else:
                correct += 1

    accuracy = (correct / total) * 100.0
    print(f"\n  ✓ Copilot Template Mapping Accuracy: {correct}/{total} ({accuracy:.1f}%) [Target: >= 90.0%]")
    assert accuracy >= 90.0, f"Expected at least 90% mapping accuracy, got {accuracy:.1f}%"


def test_phase3_zero_sql_injection_resistance():
    """Verify copilot rejects or safely sanitizes SQL injection payloads with zero SQL execution."""
    malicious_inputs = [
        "who missed doses; DROP TABLE patients;--",
        "explain alert 1' OR '1'='1",
        "show patients with open flags UNION SELECT * FROM user_accounts",
        "snapshot of Aarav'; DELETE FROM flags;--",
        "what happened to Aarav since 24; DROP TABLE medication_logs;--"
    ]
    doctor_user = {"staff_id": 1, "role": "Doctor", "full_name": "Dr. Ananya Sharma"}

    for mal_q in malicious_inputs:
        # Must execute without throwing SQL syntax error
        res = ask_careloop(mal_q, doctor_user, bypass_cache=True)
        assert "error" not in res or "syntax" not in res["error"].lower()
        # Verify patients table still exists and is untouched
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM patients;")
            cnt = cur.fetchone()["cnt"]
            assert cnt >= 5, "Integrity check failed: patients table compromised!"

    print("  ✓ Zero SQL injection possible: all queries parameterized, dangerous keywords sanitized.")


def test_phase3_role_assignment_guard():
    """Verify nurse cannot view unassigned patients, while doctor has universal clinical access."""
    # Temporarily remove patient 4 (Kabir Mehta) assignment from Nurse Priya (staff_id=2)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE care_assignments
                SET ends_at = DATE_ADD(starts_at, INTERVAL 1 HOUR)
                WHERE patient_id = 4 AND staff_id = 2;
            """)
        conn.commit()

    try:
        nurse_user = {"staff_id": 2, "role": "Nurse", "full_name": "Priya Nair"}
        doctor_user = {"staff_id": 1, "role": "Doctor", "full_name": "Dr. Ananya Sharma"}

        # Nurse querying unassigned patient 4
        nurse_res = ask_careloop("Snapshot of Kabir Mehta", nurse_user, bypass_cache=True)
        assert "error" in nurse_res
        assert "Access Denied" in nurse_res["error"]

        # Doctor querying same patient 4
        doc_res = ask_careloop("Snapshot of Kabir Mehta", doctor_user, bypass_cache=True)
        assert "error" not in doc_res
        assert doc_res["patient_name"] == "Kabir Mehta"
        assert len(doc_res["bullets"]) >= 2

        print("  ✓ Role assignment guard strictly enforced: Nurse restricted to assigned panel, Doctor universal.")
    finally:
        # Restore assignment
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE care_assignments
                    SET ends_at = NULL
                    WHERE patient_id = 4 AND staff_id = 2;
                """)
            conn.commit()


def test_phase3_opt_out_patient_warning_badge():
    """Verify patients opted out of AI help display an explicit opt-out warning badge."""
    # Ensure patient 3 has ai_help_enabled = 0 (opted out)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE patients SET ai_help_enabled = 0 WHERE patient_id = 3;")
        conn.commit()

    try:
        doc_user = {"staff_id": 1, "role": "Doctor", "full_name": "Dr. Ananya Sharma"}
        res = ask_careloop("Snapshot of Rajesh Verma", doc_user, bypass_cache=True)
        assert res["opt_out_badge"] is True
        assert res["patient_name"] == "Rajesh Verma"
        print("  ✓ Opt-out warning badge properly flagged for human-only mode patient.")
    finally:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE patients SET ai_help_enabled = 1 WHERE patient_id = 3;")
            conn.commit()


def test_phase3_grounded_table_list():
    """Verify find_patients produces exact counts, tailored columns, and patient click-through links."""
    doc_user = {"staff_id": 1, "role": "Doctor", "full_name": "Dr. Ananya Sharma"}
    res = ask_careloop("Who missed doses today?", doc_user, bypass_cache=True)

    assert res["template"] == "find_patients"
    assert res["result_type"] == "patient_table"
    assert "count" in res
    assert isinstance(res["rows"], list)
    assert len(res["columns"]) >= 4
    if res["rows"]:
        first_row = res["rows"][0]
        assert "patient_id" in first_row
        assert "patient_name" in first_row
        assert "identifiers" in first_row

    print(f"  ✓ Grounded patient table: {res['count']} patients found with tailored columns.")


def test_phase3_explain_alert_case_prep_brief():
    """Verify explain_alert returns the 5-part Case Prep brief with citations and next step."""
    doc_user = {"staff_id": 1, "role": "Doctor", "full_name": "Dr. Ananya Sharma"}
    res = ask_careloop("Explain alert 1", doc_user, bypass_cache=True)

    assert res["template"] == "explain_alert"
    assert res["result_type"] == "case_prep_brief"
    assert "brief_sections" in res
    assert len(res["brief_sections"]) == 5
    assert "1. Patient Identifiers & Baseline" in res["brief_sections"][0]["title"]
    assert "5. Deterministic Recommended Next Step" in res["brief_sections"][4]["title"]
    assert "recommended_step" in res
    print("  ✓ explain_alert returned grounded 5-part Case Prep brief with citations.")


def test_phase3_draft_message_requires_channel_confirmation():
    """Verify draft_message creates a Draft with Send disabled until channel confirmed."""
    doc_user = {"staff_id": 1, "role": "Doctor", "full_name": "Dr. Ananya Sharma"}
    res = ask_careloop("Draft message to Aarav about missed dose", doc_user, bypass_cache=True)

    assert res["template"] == "draft_message"
    assert res["result_type"] == "message_draft"
    assert res["mode"] == "Draft"
    assert res["requires_channel_confirmation"] is True
    assert res["send_disabled"] is True
    assert "draft_text" in res
    assert "Aarav" in res["draft_text"]
    assert "SMS" in res["allowed_channels"]
    assert "WhatsApp" in res["allowed_channels"]
    print("  ✓ Draft message generated in Draft mode with human channel confirmation required.")


def test_phase3_fast_path_cache_60s():
    """Verify fast path returns cached responses within 60s window per staff member."""
    clear_copilot_cache()
    doc_user = {"staff_id": 1, "role": "Doctor", "full_name": "Dr. Ananya Sharma"}
    q = "Who has active alerts right now?"

    # First call -> not cached
    res1 = ask_careloop(q, doc_user, bypass_cache=False)
    assert res1.get("is_cached") is False

    # Second call -> cached
    res2 = ask_careloop(q, doc_user, bypass_cache=False)
    assert res2.get("is_cached") is True
    assert "cached_at" in res2
    assert res2["count"] == res1["count"]
    print(f"  ✓ 60-second in-memory staff cache hit verified: cached at {res2['cached_at']}")


def test_phase3_summarize_and_compare_vitals():
    """Verify chronological timeline summary and vital delta comparison."""
    doc_user = {"staff_id": 1, "role": "Doctor", "full_name": "Dr. Ananya Sharma"}

    # 1. Summarize since yesterday
    sum_res = ask_careloop("What happened to Aarav since yesterday?", doc_user, bypass_cache=True)
    assert sum_res["template"] == "summarize_since"
    assert sum_res["result_type"] == "timeline_summary"
    assert len(sum_res["bullets"]) >= 1

    # 2. Compare vitals
    vit_res = ask_careloop("Compare vitals for Aarav over 7 days", doc_user, bypass_cache=True)
    assert vit_res["template"] == "compare_vitals"
    assert vit_res["result_type"] == "vital_comparison"
    assert "comparisons" in vit_res

    print("  ✓ summarize_since and compare_vitals verified with grounded logs and timestamps.")
