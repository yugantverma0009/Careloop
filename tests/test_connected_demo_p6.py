"""
tests/test_connected_demo_p6.py

Phase 6 Acceptance Suite: Connected Demo Story & Landing Page
Verifies:
1. Demo reset endpoint runs in < 30s and outputs exact message
2. CLI scripts/reset_demo.py runs cleanly and outputs exact contract string
3. Simulator endpoint POST /demo/simulate-reading raises Urgent flag for Aarav
4. Patient view receives 'urgent' banner state
5. Family view receives 'The care team is checking on Aarav. Please contact him.'
6. Nurse call list shows Aarav with Urgent tier and explainable reason
7. Nurse logs call and escalates to Dr. Sharma
8. Doctor decisions view shows Aarav with escalation note and can resolve
9. Audit log contains verifiable trace of all connected events
10. Patient consent toggle immediately gates family helper access
11. Landing page contains 4 distinct role pitches and no unprovable claims
"""

import os
import sys
import json
import time
import subprocess
import pytest
from fastapi.testclient import TestClient

# Ensure root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app

client = TestClient(app)


def get_token(email: str, password: str = "Demo@12345") -> str:
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    return res.json()["access_token"]


@pytest.fixture(autouse=True)
def ensure_reset_demo():
    """Ensure demo starts in a clean Section 4 baseline."""
    res = client.post("/demo/reset")
    assert res.status_code == 200
    yield


def test_demo_reset_contract():
    """Phase 6 Task 1: Demo reset execution time < 30s and exact output contract."""
    start = time.time()
    res = client.post("/demo/reset")
    elapsed = time.time() - start

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["patients"] == 5
    assert data["open_flags"] == 3
    assert data["open_tasks"] == 5
    assert data["message"] == "Reset complete: 5 patients, 3 open flags, 5 tasks"
    assert elapsed < 30.0, f"Reset took {elapsed:.2f}s, exceeding 30s threshold"


def test_reset_demo_cli_script():
    """Phase 6 Task 1: scripts/reset_demo.py CLI script execution."""
    cmd = [os.path.abspath("scripts/reset_demo.py")]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
    assert proc.returncode == 0, f"reset_demo.py failed: {proc.stderr}"
    assert "Reset complete: 5 patients, 3 open flags, 5 tasks" in proc.stdout


def test_connected_demo_story_flow():
    """
    Phase 6 Acceptance: Full 6-minute live event story flow
    1 reading -> patient banner -> family update -> nurse call -> doctor decision -> audit log.
    """
    # 1. Aarav logs morning dose
    p_tok = get_token("aarav.demo@example.test")
    p_today_init = client.get("/patient/me/today", headers={"Authorization": f"Bearer {p_tok}"}).json()
    assert p_today_init["banner"]["state"] == "none", "Aarav should have no open flags initially"

    # 2. Ingest simulated low SpO2 reading (91.0%)
    sim_res = client.post(
        "/demo/simulate-reading",
        json={
            "patient_id": 1,
            "device_id": "DEV-ESP32-001",
            "measurement_type": "SpO2",
            "value": 91.0,
            "unit": "%",
        },
    )
    assert sim_res.status_code == 200
    sim_data = sim_res.json()
    flag_id = sim_data["flag_id"]
    assert flag_id is not None, "Trigger should have raised a flag"

    # 3. Patient view receives urgent banner
    p_today_after = client.get("/patient/me/today", headers={"Authorization": f"Bearer {p_tok}"}).json()
    assert p_today_after["banner"]["state"] == "urgent"
    assert p_today_after["banner"]["message_key"] == "urgent_alert"

    # 4. Family view receives 'What you may need to do' guidance
    f_tok = get_token("caregiver1.demo@example.test")
    f_today = client.get("/family/today", headers={"Authorization": f"Bearer {f_tok}"}).json()
    assert f_today["what_you_may_need_to_do"]["severity"] == "urgent"
    assert "The care team is checking on Aarav. Please contact him." in f_today["what_you_may_need_to_do"]["text"]

    # 5. Nurse My Call List shows Aarav at top of queue
    n_tok = get_token("priya.demo@example.test")
    n_list = client.get("/staff/nurse/call-list", headers={"Authorization": f"Bearer {n_tok}"}).json()
    aarav_call = next((it for it in n_list["call_items"] if it["patient_id"] == 1), None)
    assert aarav_call is not None, "Aarav must appear on nurse call list"
    assert aarav_call["tier"] == "Urgent"
    assert "91.00 %" in aarav_call["reason"]
    assert "94.00" in aarav_call["reason"]

    # 6. Nurse logs call and escalates to Dr. Sharma
    call_log_res = client.post(
        "/staff/contacts/log",
        headers={"Authorization": f"Bearer {n_tok}"},
        json={
            "patient_id": 1,
            "flag_id": flag_id,
            "channel": "Phone",
            "outcome": "Reached",
            "summary": "Reached Aarav by phone; instructed deep breathing; SpO2 recheck pending.",
        },
    )
    assert call_log_res.status_code == 200

    escalate_res = client.post(
        f"/staff/flags/{flag_id}/escalate",
        headers={"Authorization": f"Bearer {n_tok}"},
        json={"note": "Oxygen at 91% on watch. Patient instructed to sit upright; requesting physician review."},
    )
    assert escalate_res.status_code == 200

    # 7. Doctor desk displays Aarav in 'Needs my decision'
    d_tok = get_token("ananya.demo@example.test")
    d_dec = client.get("/staff/doctor/decisions", headers={"Authorization": f"Bearer {d_tok}"}).json()
    aarav_dec = next((it for it in d_dec["items"] if it["patient_id"] == 1), None)
    assert aarav_dec is not None, "Aarav must appear on Doctor decision list after escalation"
    assert aarav_dec["escalated_by"] == "Priya Nair"

    # 8. Doctor resolves flag
    resolve_res = client.post(
        f"/staff/flags/{flag_id}/resolve",
        headers={"Authorization": f"Bearer {d_tok}"},
        json={
            "resolution_code": "Patient_Contacted",
            "resolution_note": "Reviewed telemetry. Repeat SpO2 confirmed at 95%. Continue current plan.",
        },
    )
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"].lower() == "resolved"

    # 9. Audit log contains full trail
    audit_res = client.get("/staff/audit-log", headers={"Authorization": f"Bearer {d_tok}"}).json()
    actions = [a["action"] for a in audit_res["logs"]]
    assert "INGEST_READING" in actions
    assert "FLAG_CREATED" in actions
    assert "ESCALATION_STEP" in actions
    assert "RESOLVE_FLAG" in actions


def test_consent_gating_live():
    """Phase 6 Acceptance: Patient flips sharing OFF -> Family portal immediately 403s."""
    p_tok = get_token("aarav.demo@example.test")
    f_tok = get_token("caregiver1.demo@example.test")

    # Verify initial sharing OK
    res_ok = client.get("/family/today", headers={"Authorization": f"Bearer {f_tok}"})
    assert res_ok.status_code == 200

    # Patient revokes consent
    revoke_res = client.post(
        "/patient/me/sharing",
        headers={"Authorization": f"Bearer {p_tok}"},
        json={"enabled": False},
    )
    assert revoke_res.status_code == 200

    # Family view must immediately be blocked
    res_blocked = client.get("/family/today", headers={"Authorization": f"Bearer {f_tok}"})
    assert res_blocked.status_code == 403
    assert "turned sharing off" in res_blocked.json()["detail"].lower()

    # Restore consent
    restore_res = client.post(
        "/patient/me/sharing",
        headers={"Authorization": f"Bearer {p_tok}"},
        json={"enabled": True},
    )
    assert restore_res.status_code == 200

    res_restored = client.get("/family/today", headers={"Authorization": f"Bearer {f_tok}"})
    assert res_restored.status_code == 200


def test_landing_page_claims_clean():
    """Phase 6 Acceptance: Landing page has no unprovable claims or banned words."""
    landing_path = os.path.abspath("frontend/src/components/Landingpage.jsx")
    with open(landing_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Banned unprovable claims
    banned_claims = [
        "prevents readmissions",
        "clinically validated",
        "100% accurate",
        "hardware-verified",
        "optimal",
    ]
    for claim in banned_claims:
        assert claim.lower() not in content.lower(), f"Banned claim found on landing page: '{claim}'"

    # Required safety phrase in footer
    assert "Sample data. Not medical advice. Synthetic-data prototype, not a medical device." in content

    # Exactly four role pitches present
    assert "The doctor decides, approves and exports." in content
    assert "The nurse calls, logs, rechecks and escalates." in content
    assert "The patient acts, checks in and asks their papers." in content
    assert "The family helper supports, is informed with consent, and calls 112 if needed." in content
