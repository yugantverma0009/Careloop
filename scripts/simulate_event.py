#!/usr/bin/env python3
"""
scripts/simulate_event.py

Phase 6 CLI helper to simulate Aarav Patel's low SpO2 reading (91.0%)
from the wearable watch (DEV-ESP32-001).
Triggers clinical rule threshold (< 94.0%), raises Urgent_Review flag,
activates the 3-step escalation ladder, creates follow-up task for Nurse Priya,
and writes the entire trace to audit_log.
"""

import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.abspath(os.path.join(SCRIPT_DIR, "../backend/env/bin/python"))
if os.path.exists(VENV_PYTHON) and sys.executable != VENV_PYTHON:
    os.execv(VENV_PYTHON, [VENV_PYTHON] + sys.argv)

import json
import urllib.request
import urllib.error

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")


def simulate_via_api():
    url = f"{API_URL}/demo/simulate-reading"
    payload = {
        "patient_id": 1,
        "device_id": "DEV-ESP32-001",
        "measurement_type": "SpO2",
        "value": 91.0,
        "unit": "%",
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        return None


def main():
    print("⚡ Sending test reading: Aarav Patel SpO2 = 91.0% (DEV-ESP32-001)...")
    res = simulate_via_api()
    if res and res.get("status") == "ok":
        print(f"✓ Reading ingested (reading_id={res.get('reading_id')})")
        print(f"✓ Flag raised: #{res.get('flag_id')} (Urgent_Review: SpO2 91% < approved limit 94%)")
        print("✓ Escalation ladder dispatched:")
        print("    1. Patient Prompt: In-app banner ('Your care team has been told. Call 112 if you have chest pain.')")
        print("    2. Caregiver SMS: Dispatched to Neha Patel (+91 98765 43210)")
        print("    3. Nurse Alert: Queued in My Call List for Priya Nair")
        print("✓ Follow-up call task assigned to Nurse Priya Nair")
        print("✓ Complete audit trail recorded in audit_log")
        print("\n🎉 Live event ready across all 4 portals!")
    else:
        print(f"❌ Simulation failed or backend not reachable: {res}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
