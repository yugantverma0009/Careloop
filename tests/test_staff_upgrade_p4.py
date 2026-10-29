"""
tests/test_staff_upgrade_p4.py

Tests for Care Team Portal Phase 4:
- D-09 Shift handoff with I-PASS sections built from data (NO stable/unstable)
- D-09 Handoff receive synthesis, contingency note, and export logging
- D-10 Escalation ladder timeline and stopped state on acknowledgment
- D-11 Notification feed with action items and snooze restriction (Routine only)
- D-15 Communication log (call & SMS recording, outcome tracking, audit trail)
- D-16 Clinical notes append-only versioning with amends pointer
"""

import pytest
import json
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import get_conn
from backend.app.auth import make_token

client = TestClient(app)

doctor_token = make_token({
    "account_id": 3,
    "email": "ananya.demo@example.test",
    "account_role": "Doctor",
    "patient_id": None,
    "caregiver_id": None,
    "staff_id": 1,
})
nurse_token = make_token({
    "account_id": 4,
    "email": "priya.demo@example.test",
    "account_role": "Nurse",
    "patient_id": None,
    "caregiver_id": None,
    "staff_id": 3,
})
doc_headers = {"Authorization": f"Bearer {doctor_token}"}
nurse_headers = {"Authorization": f"Bearer {nurse_token}"}


def test_d09_shift_handoff_ipass_structure():
    """D-09: Shift handoff produces structured I-PASS cards built from data without judgment words."""
    resp = client.get("/staff/handoff?scope=all", headers=nurse_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "shift_name" in data
    assert "date" in data
    assert "patients" in data
    assert len(data["patients"]) > 0

    first = data["patients"][0]
    assert "patient_code" in first
    assert first["patient_code"].startswith("CL-")
    assert "full_name" in first
    assert "illness_tier" in first
    # Illness tier must be one of the 4 strict tiers; never 'stable' or 'unstable'
    assert first["illness_tier"] in ["Immediate", "Urgent", "Review soon", "Routine"]
    assert "patient_summary" in first
    assert "condition" in first["patient_summary"]
    assert "action_list" in first
    assert "situation_awareness" in first
    assert "open_flags" in first["situation_awareness"]
    assert "silent_devices" in first["situation_awareness"]
    assert "contingency_note" in first
    assert "is_received" in first


def test_d09_shift_handoff_actions():
    """D-09: Test receive check, contingency note update, and export logging."""
    # 1. Update contingency note
    c_resp = client.post(
        "/staff/handoff/1/contingency",
        json={"contingency_note": "If systolic BP > 160 mmHg, call Dr. Sharma immediately."},
        headers=doc_headers,
    )
    assert c_resp.status_code == 200
    assert c_resp.json()["status"] == "updated"

    # 2. Mark received by incoming nurse
    r_resp = client.post("/staff/handoff/1/receive", headers=nurse_headers)
    assert r_resp.status_code == 200
    assert r_resp.json()["status"] == "received"

    # 3. Log export
    e_resp = client.post(
        "/staff/handoff/export-log",
        json={"export_format": "PDF"},
        headers=nurse_headers,
    )
    assert e_resp.status_code == 200
    assert e_resp.json()["status"] == "logged"

    # Verify audit log recorded receipt
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT action, entity_type, entity_id
               FROM audit_log
               WHERE entity_type = 'handoff' AND entity_id = 1 AND action = 'HANDOFF_RECEIVED'
               ORDER BY log_id DESC LIMIT 1"""
        )
        row = cur.fetchone()
        assert row is not None


def test_d10_escalation_ladder_visibility():
    """D-10: Flag escalation ladder timeline and stopping upon acknowledgment."""
    # Fetch first flag
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT flag_id, status FROM flags ORDER BY flag_id ASC LIMIT 1")
        f_row = cur.fetchone()
        flag_id = f_row["flag_id"]

    resp = client.get(f"/staff/flags/{flag_id}/escalations", headers=nurse_headers)
    assert resp.status_code == 200
    ladder = resp.json()
    assert "flag_id" in ladder
    assert "steps" in ladder
    assert len(ladder["steps"]) == 4

    step_types = [s["step_type"] for s in ladder["steps"]]
    assert step_types == ["Patient_Prompt", "Caregiver_SMS", "Nurse_Alert", "Doctor_Alert"]

    if ladder["status"] in ("Acknowledged", "Resolved"):
        assert ladder["is_stopped"] is True
        assert "Ladder stopped" in ladder["stopped_banner"]


def test_d11_notifications_feed_and_snooze_rules():
    """D-11: Notifications feed with urgent vs routine snooze rules."""
    resp = client.get("/staff/notifications", headers=doc_headers)
    assert resp.status_code == 200
    feed = resp.json()
    assert "count" in feed
    assert "notifications" in feed

    for item in feed["notifications"]:
        assert "id" in item
        assert "tier" in item
        assert "title" in item
        # Strict rule: Urgent or Immediate items cannot be snoozed
        if item["tier"] in ("Immediate", "Urgent"):
            assert item["can_snooze"] is False
        elif item["tier"] == "Routine":
            assert item["can_snooze"] is True


def test_d15_communication_log_and_history():
    """D-15: Log call or message with channel and outcome, verify history."""
    # 1. Invalid channel rejected
    bad_resp = client.post(
        "/staff/contacts/log",
        json={
            "patient_id": 1,
            "channel": "CarrierPigeon",
            "outcome": "Reached",
            "summary": "test",
        },
        headers=nurse_headers,
    )
    assert bad_resp.status_code == 400

    # 2. Valid call log
    good_resp = client.post(
        "/staff/contacts/log",
        json={
            "patient_id": 1,
            "channel": "Phone",
            "outcome": "Reached",
            "summary": "Spoke with patient regarding morning dizziness; vitals re-checked and stable.",
        },
        headers=nurse_headers,
    )
    assert good_resp.status_code == 200
    data = good_resp.json()
    assert data["status"] == "logged"
    contact_id = data["contact_id"]

    # 3. Retrieve contacts history
    hist_resp = client.get("/staff/patients/1/contacts", headers=nurse_headers)
    assert hist_resp.status_code == 200
    logs = hist_resp.json()
    assert any(c["contact_id"] == contact_id for c in logs)


def test_d16_clinical_notes_append_only():
    """D-16: Append-only clinical notes and amendment chaining."""
    # 1. Create original note
    n1 = client.post(
        "/staff/patients/1/notes",
        json={"note_type": "Review", "note_text": "Post-op wound check completed; no erythema."},
        headers=doc_headers,
    )
    assert n1.status_code == 200
    note_id_1 = n1.json()["note_id"]

    # 2. Amend note
    n2 = client.post(
        "/staff/patients/1/notes",
        json={
            "note_type": "Review",
            "note_text": "Amended: slight serous discharge noted at lower edge, swab collected.",
            "amends_note_id": note_id_1,
        },
        headers=doc_headers,
    )
    assert n2.status_code == 200
    note_id_2 = n2.json()["note_id"]

    # 3. Retrieve notes history
    h_resp = client.get("/staff/patients/1/notes", headers=doc_headers)
    assert h_resp.status_code == 200
    notes = h_resp.json()
    amended = next((n for n in notes if n["note_id"] == note_id_2), None)
    assert amended is not None
    assert amended["amends_note_id"] == note_id_1


def test_d12_assignment_scope_and_break_glass():
    """D-12: Worklist default to mine scope, and break-glass access logging."""
    # 1. Doctor worklist defaults to mine (scope=mine)
    doc_wl = client.get("/staff/worklist", headers=doc_headers)
    assert doc_wl.status_code == 200
    wl_data = doc_wl.json()
    assert "patients" in wl_data
    # Every patient returned under mine must have is_mine = True
    for p in wl_data["patients"]:
        assert p["is_mine"] is True

    # 2. Break-glass view for non-assigned patient
    bg_resp = client.post(
        "/staff/patients/6/break-glass",
        json={"reason": "Emergency cover during clinician break"},
        headers=doc_headers,
    )
    assert bg_resp.status_code == 200
    assert bg_resp.json()["status"] == "access_granted"

    # Verify audit entry for break-glass
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT action, actor_id, entity_type, entity_id
               FROM audit_log
               WHERE action = 'BREAK_GLASS_VIEW' AND entity_id = 6
               ORDER BY log_id DESC LIMIT 1"""
        )
        row = cur.fetchone()
        assert row is not None
        assert row["action"] == "BREAK_GLASS_VIEW"


def test_d17_audit_log_viewer_and_export():
    """D-17: Audit log viewer filtering and export audit logging."""
    # 1. Query audit log
    resp = client.get("/staff/audit-log?limit=50", headers=doc_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "logs" in data
    assert "actions" in data
    assert "staff" in data
    assert len(data["logs"]) > 0

    first = data["logs"][0]
    assert "log_id" in first
    assert "actor_type" in first
    assert "action" in first
    assert "created_at" in first

    # 2. Log export event
    exp_resp = client.post(
        "/staff/audit-log/export-log",
        json={"count": 50, "filters": {"action": "BREAK_GLASS_VIEW"}},
        headers=doc_headers,
    )
    assert exp_resp.status_code == 200
    assert exp_resp.json()["status"] == "logged"

    # Verify EXPORT_AUDIT_LOG was recorded
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT action FROM audit_log
               WHERE action = 'EXPORT_AUDIT_LOG'
               ORDER BY log_id DESC LIMIT 1"""
        )
        row = cur.fetchone()
        assert row is not None


def test_d21_global_search_endpoint():
    """D-21: Global search across patients, active flags, tasks, and clinician notes."""
    resp = client.get("/staff/search?q=Aarav", headers=nurse_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "patients" in data
    assert "flags" in data
    assert "tasks" in data
    assert "notes" in data
    assert any("Aarav" in p["full_name"] for p in data["patients"])

