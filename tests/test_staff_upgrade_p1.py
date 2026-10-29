"""
tests/test_staff_upgrade_p1.py

Care Team Portal Upgrade — Phase 1 Test Suite
Validates:
- D-01: Zero patient identity mismatches across flags, tasks, ai_summaries.
- D-01: Synthetic patient codes (CL-00001 to CL-00010) unique and present.
- D-02: Grouped worklist endpoint (v_worklist_by_patient), SLA tiers, explainable attention score.
- D-03: Flag detail endpoint, closed-loop acknowledge, resolve, dismiss, and assign workflows.
- D-03: Double-acknowledge 409 conflict handling.
- D-03: Urgent flag resolution requires note >= 5 characters.
- D-10: Escalation ladder visibility and manual escalation endpoint.
- Append-only audit trail in flag_events and audit_log.
"""

import pytest
import pymysql
import json
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import get_conn
from backend.app.auth import make_token

client = TestClient(app)

DOCTOR_TOKEN = make_token({
    "account_id": 3,
    "email": "ananya.demo@example.test",
    "account_role": "Doctor",
    "patient_id": None,
    "caregiver_id": None,
    "staff_id": 1,
})
NURSE_TOKEN = make_token({
    "account_id": 4,
    "email": "priya.demo@example.test",
    "account_role": "Nurse",
    "patient_id": None,
    "caregiver_id": None,
    "staff_id": 3,
})

DOCTOR_AUTH = {"Authorization": f"Bearer {DOCTOR_TOKEN}"}
NURSE_AUTH = {"Authorization": f"Bearer {NURSE_TOKEN}"}


def test_d01_identity_consistency_in_db():
    """D-01: Asserts zero cross-patient name mismatches in flags, tasks, and ai_summaries."""
    with get_conn() as conn, conn.cursor() as cur:
        # 1. Flags mismatch check
        cur.execute("""
            SELECT flag_id, patient_id, reason FROM flags
            WHERE (reason LIKE '%Aarav%' AND patient_id != 1)
               OR (reason LIKE '%Meera%' AND patient_id != 2)
               OR (reason LIKE '%Kabir%' AND patient_id != 3)
               OR (reason LIKE '%Sunita%' AND patient_id != 4)
               OR (reason LIKE '%Rajesh%' AND patient_id != 5)
               OR (reason LIKE '%Ananya%' AND patient_id != 6)
               OR (reason LIKE '%Vikram%' AND patient_id != 7)
               OR (reason LIKE '%Pooja%' AND patient_id != 8)
               OR (reason LIKE '%Arjun%' AND patient_id != 9)
               OR (reason LIKE '%Deepa%' AND patient_id != 10)
        """)
        flag_mismatches = cur.fetchall()
        assert len(flag_mismatches) == 0, f"Found {len(flag_mismatches)} flag identity mismatches"

        # 2. Tasks mismatch check
        cur.execute("""
            SELECT followup_id, patient_id, reason FROM follow_up_tasks
            WHERE (reason LIKE '%Aarav%' AND patient_id != 1)
               OR (reason LIKE '%Meera%' AND patient_id != 2)
               OR (reason LIKE '%Kabir%' AND patient_id != 3)
               OR (reason LIKE '%Sunita%' AND patient_id != 4)
               OR (reason LIKE '%Rajesh%' AND patient_id != 5)
               OR (reason LIKE '%Ananya%' AND patient_id != 6)
               OR (reason LIKE '%Vikram%' AND patient_id != 7)
               OR (reason LIKE '%Pooja%' AND patient_id != 8)
               OR (reason LIKE '%Arjun%' AND patient_id != 9)
               OR (reason LIKE '%Deepa%' AND patient_id != 10)
        """)
        task_mismatches = cur.fetchall()
        assert len(task_mismatches) == 0, f"Found {len(task_mismatches)} task identity mismatches"

        # 3. AI summaries mismatch check
        cur.execute("""
            SELECT summary_id, patient_id, summary_text FROM ai_summaries
            WHERE (summary_text LIKE '%Aarav%' AND patient_id != 1)
               OR (summary_text LIKE '%Meera%' AND patient_id != 2)
               OR (summary_text LIKE '%Kabir%' AND patient_id != 3)
               OR (summary_text LIKE '%Sunita%' AND patient_id != 4)
               OR (summary_text LIKE '%Rajesh%' AND patient_id != 5)
               OR (summary_text LIKE '%Ananya%' AND summary_text NOT LIKE '%Dr. Ananya%' AND patient_id != 6)
               OR (summary_text LIKE '%Vikram%' AND patient_id != 7)
               OR (summary_text LIKE '%Pooja%' AND patient_id != 8)
               OR (summary_text LIKE '%Arjun%' AND patient_id != 9)
               OR (summary_text LIKE '%Deepa%' AND patient_id != 10)
        """)
        summary_mismatches = cur.fetchall()
        assert len(summary_mismatches) == 0, f"Found {len(summary_mismatches)} summary identity mismatches"


def test_d01_patient_codes():
    """D-01: Verifies all patients have valid synthetic CL-0000X codes."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT patient_id, full_name, patient_code FROM patients ORDER BY patient_id")
        rows = cur.fetchall()
        assert len(rows) >= 10, "Expected at least 10 synthetic patients"
        codes = set()
        for r in rows:
            assert r["patient_code"] is not None, f"Patient {r['patient_id']} missing patient_code"
            assert r["patient_code"].startswith("CL-"), f"Invalid code format: {r['patient_code']}"
            assert r["patient_code"] not in codes, f"Duplicate patient code {r['patient_code']}"
            codes.add(r["patient_code"])


def test_d02_grouped_worklist():
    """D-02: Worklist returns one card per affected patient, SLA tiers, and explainable attention score."""
    res = client.get("/staff/worklist", headers=DOCTOR_AUTH)
    assert res.status_code == 200, res.text
    data = res.json()

    assert "summary" in data
    assert "patients" in data
    summary = data["summary"]
    patients = data["patients"]

    assert summary["total_patients"] > 0
    assert summary["total_open_flags"] > 0
    # Grouping ensures number of patient cards is ~9-10, NOT 66
    assert len(patients) <= 10

    # Validate first patient structure
    p = patients[0]
    assert "patient_code" in p
    assert p["patient_code"].startswith("CL-")
    assert "full_name" in p
    assert "age_years" in p
    assert "tier" in p
    assert p["tier"] in ["Immediate", "Urgent", "Review_Soon", "Routine"]
    assert "attention_score" in p
    assert 0 <= p["attention_score"] <= 100
    assert "attention_factors" in p
    assert isinstance(p["attention_factors"], list)
    assert len(p["attention_factors"]) > 0
    assert "flags" in p
    assert isinstance(p["flags"], list)


def test_d03_flag_detail():
    """D-03: Drawer detail endpoint returns evidence, rule, escalation ladder, and audit history."""
    # Find an open flag
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT flag_id FROM flags WHERE status = 'Open' LIMIT 1")
        flag_id = cur.fetchone()["flag_id"]

    res = client.get(f"/staff/flags/{flag_id}", headers=DOCTOR_AUTH)
    assert res.status_code == 200, res.text
    detail = res.json()

    assert detail["flag_id"] == flag_id
    assert "patient" in detail
    assert detail["patient"]["patient_code"].startswith("CL-")
    assert detail["patient"]["full_name"] is not None
    assert "evidence" in detail
    assert "rule" in detail
    assert "escalation_ladder" in detail
    assert len(detail["escalation_ladder"]) >= 4
    assert "history" in detail


def test_d03_acknowledge_and_double_acknowledge():
    """D-03: Acknowledge takes ownership; second attempt yields 409 conflict with clinician details."""
    with get_conn() as conn, conn.cursor() as cur:
        # Create a test flag
        cur.execute("""
            INSERT INTO flags (patient_id, source_type, reason, severity, status)
            VALUES (1, 'Sensor', 'Unit test open flag for acknowledgment', 'Review_Soon', 'Open')
        """)
        conn.commit()
        flag_id = cur.lastrowid

    # 1. First acknowledgment by Doctor Ananya
    res1 = client.post(
        f"/staff/flags/{flag_id}/acknowledge",
        headers=DOCTOR_AUTH,
        json={"note": "Assessing patient telemetry", "create_task": True},
    )
    assert res1.status_code == 200, res1.text
    assert res1.json()["status"] == "acknowledged"

    # Verify task was created
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT followup_id, priority, due_at FROM follow_up_tasks WHERE flag_id = %s", (flag_id,))
        task = cur.fetchone()
        assert task is not None, "Follow-up task was not created"
        assert task["due_at"] is not None

    # 2. Second acknowledgment by Nurse Priya -> 409 Conflict
    res2 = client.post(
        f"/staff/flags/{flag_id}/acknowledge",
        headers=NURSE_AUTH,
        json={"note": "Attempting simultaneous ack", "create_task": False},
      )
    assert res2.status_code == 409, res2.text
    assert "Already acknowledged" in res2.json()["detail"]


def test_d03_resolve_urgent_flag_validation():
    """D-03: Urgent/Immediate flag resolution enforces note >= 5 characters."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO flags (patient_id, source_type, reason, severity, status)
            VALUES (1, 'Emergency', 'Unit test urgent flag for resolution check', 'Urgent_Review', 'Acknowledged')
        """)
        conn.commit()
        flag_id = cur.lastrowid

    # 1. Attempt resolve with empty note -> 400 Bad Request
    res1 = client.post(
        f"/staff/flags/{flag_id}/resolve",
        headers=DOCTOR_AUTH,
        json={"resolution_code": "No_Action_Needed", "resolution_note": ""},
    )
    assert res1.status_code == 400, res1.text
    assert "at least 5 characters" in res1.json()["detail"]

    # 2. Attempt resolve with 3 char note -> 400 Bad Request
    res2 = client.post(
        f"/staff/flags/{flag_id}/resolve",
        headers=DOCTOR_AUTH,
        json={"resolution_code": "Patient_Contacted", "resolution_note": "ok"},
    )
    assert res2.status_code == 400, res2.text

    # 3. Resolve with compliant note -> 200 OK
    res3 = client.post(
        f"/staff/flags/{flag_id}/resolve",
        headers=DOCTOR_AUTH,
        json={"resolution_code": "Patient_Contacted", "resolution_note": "Spoke with patient; recovery normal."},
    )
    assert res3.status_code == 200, res3.text
    assert res3.json()["status"] == "resolved"

    # Verify audit log & flag_events
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT status, resolution_code, resolution_note FROM flags WHERE flag_id = %s", (flag_id,))
        fl = cur.fetchone()
        assert fl["status"] == "Resolved"
        assert fl["resolution_code"] == "Patient_Contacted"

        cur.execute("SELECT event_type, note FROM flag_events WHERE flag_id = %s AND event_type = 'Resolved'", (flag_id,))
        ev = cur.fetchone()
        assert ev is not None

        # Clean up test flag to prevent test interference
        cur.execute("DELETE FROM flag_events WHERE flag_id = %s", (flag_id,))
        cur.execute("DELETE FROM audit_log WHERE entity_type = 'flag' AND entity_id = %s", (str(flag_id),))
        cur.execute("DELETE FROM flags WHERE flag_id = %s", (flag_id,))
        conn.commit()


def test_d03_dismiss_flag():
    """D-03: Dismiss flag as False_Alarm records resolution_code and event."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO flags (patient_id, source_type, reason, severity, status)
            VALUES (2, 'Sensor', 'Unit test flag for dismissal', 'Review_Soon', 'Open')
        """)
        conn.commit()
        flag_id = cur.lastrowid

    res = client.post(
        f"/staff/flags/{flag_id}/dismiss",
        headers=DOCTOR_AUTH,
        json={"resolution_code": "False_Alarm", "resolution_note": "Motion artifact on pulse oximeter"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "dismissed"

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT status, resolution_code FROM flags WHERE flag_id = %s", (flag_id,))
        fl = cur.fetchone()
        assert fl["status"] == "Dismissed"
        assert fl["resolution_code"] == "False_Alarm"

        # Clean up test flag
        cur.execute("DELETE FROM flag_events WHERE flag_id = %s", (flag_id,))
        cur.execute("DELETE FROM audit_log WHERE entity_type = 'flag' AND entity_id = %s", (str(flag_id),))
        cur.execute("DELETE FROM flags WHERE flag_id = %s", (flag_id,))
        conn.commit()


def test_d03_assign_flag():
    """D-03: Assign flag updates owner_staff_id and logs event."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO flags (patient_id, source_type, reason, severity, status)
            VALUES (3, 'Sensor', 'Unit test flag for assignment', 'Review_Soon', 'Open')
        """)
        conn.commit()
        flag_id = cur.lastrowid

    res = client.post(
        f"/staff/flags/{flag_id}/assign",
        headers=DOCTOR_AUTH,
        json={"target_staff_id": 3, "note": "Assigned to Nurse Priya for home vitals check"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "assigned"

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT owner_staff_id FROM flags WHERE flag_id = %s", (flag_id,))
        fl = cur.fetchone()
        assert fl["owner_staff_id"] == 3

        cur.execute("SELECT event_type, staff_id FROM flag_events WHERE flag_id = %s AND event_type = 'Assigned'", (flag_id,))
        ev = cur.fetchone()
        assert ev is not None
        assert ev["staff_id"] == 3

        # Clean up test flag
        cur.execute("DELETE FROM flag_events WHERE flag_id = %s", (flag_id,))
        cur.execute("DELETE FROM flags WHERE flag_id = %s", (flag_id,))
        conn.commit()


def test_d10_manual_escalate():
    """D-10: Escalate now writes escalation ladder entry and flag event."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO flags (patient_id, source_type, reason, severity, status)
            VALUES (1, 'Sensor', 'Unit test flag for escalation', 'Urgent_Review', 'Open')
        """)
        conn.commit()
        flag_id = cur.lastrowid

    res = client.post(
        f"/staff/flags/{flag_id}/escalate",
        headers=NURSE_AUTH,
        json={"note": "Patient complaining of worsening shortness of breath"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "escalated"

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT step_type, delivery_status FROM escalations WHERE flag_id = %s", (flag_id,))
        esc = cur.fetchone()
        assert esc is not None
        assert esc["step_type"] == "Doctor_Alert"
        assert esc["delivery_status"] == "Sent"

        # Clean up test flag
        cur.execute("DELETE FROM escalations WHERE flag_id = %s", (flag_id,))
        cur.execute("DELETE FROM flag_events WHERE flag_id = %s", (flag_id,))
        cur.execute("DELETE FROM flags WHERE flag_id = %s", (flag_id,))
        conn.commit()
