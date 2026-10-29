"""
tests/test_m2_device.py — Milestone M2 Tests

Tests:
1. Authentication: Rejection of invalid X-Device-Key (HTTP 401)
2. Validation: Rejection of unknown device_id (HTTP 404)
3. Ingestion: Successful storage of valid Heart_Rate and SpO2 telemetry
4. Idempotency: Retried upload with identical timestamp returns 'duplicate_ignored'
5. Rule & Flag: Simulator low SpO2 creates exactly ONE flag with clinical reason
6. Deduplication: Subsequent low SpO2 while flag is open creates no duplicate flag
7. Plausibility Guard: Impossible sensor value (450 bpm) becomes 'Invalid' and raises no flag
"""

import time
import random
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import get_conn

client = TestClient(app)
VALID_KEY = "demo-device-key-change-me"


def test_auth_and_device_validation():
    # Bad device key
    res = client.post(
        "/device/readings",
        json={
            "device_id": "ESP32-DEMO-01",
            "measurement_type": "Heart_Rate",
            "value": 75.0,
            "unit": "bpm",
            "measured_at": int(time.time()),
            "quality": "Good",
        },
        headers={"X-Device-Key": "wrong-key"},
    )
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    print("✅ Invalid device key rejected with HTTP 401")

    # Unknown device ID
    res = client.post(
        "/device/readings",
        json={
            "device_id": "UNKNOWN-DEVICE-999",
            "measurement_type": "Heart_Rate",
            "value": 75.0,
            "unit": "bpm",
            "measured_at": int(time.time()),
            "quality": "Good",
        },
        headers={"X-Device-Key": VALID_KEY},
    )
    assert res.status_code == 404, f"Expected 404, got {res.status_code}"
    print("✅ Unknown device ID rejected with HTTP 404")


def test_idempotent_ingestion():
    timestamp = int(time.time()) - random.randint(100000, 999999)
    payload = {
        "device_id": "ESP32-DEMO-01",
        "measurement_type": "Heart_Rate",
        "value": 76.0,
        "unit": "bpm",
        "measured_at": timestamp,
        "quality": "Good",
    }

    # First send -> stored
    res1 = client.post("/device/readings", json=payload, headers={"X-Device-Key": VALID_KEY})
    assert res1.status_code == 200, res1.text
    assert res1.json()["status"] == "stored"
    print("✅ Initial reading upload stored successfully")

    # Duplicate send with same timestamp -> duplicate_ignored
    res2 = client.post("/device/readings", json=payload, headers={"X-Device-Key": VALID_KEY})
    assert res2.status_code == 200, res2.text
    assert res2.json()["status"] == "duplicate_ignored"
    print("✅ Retried upload with duplicate key returned 'duplicate_ignored' (Idempotent)")


def test_low_spo2_creates_flag_and_deduplicates():
    # Patient 2 (Meera Demo) owns ESP32-DEMO-02; her approved SpO2 limit is 94.00
    # Clean up any existing open flags for patient 2 by marking them Resolved
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE flags SET status='Resolved' WHERE patient_id=2 AND source_type='Sensor'")
    
    t1 = int(time.time()) - 200
    payload_low = {
        "device_id": "ESP32-DEMO-02",
        "measurement_type": "SpO2",
        "value": 90.0,
        "unit": "%",
        "measured_at": t1,
        "quality": "Simulated",
    }

    # Ingest low SpO2 reading
    res = client.post("/device/readings", json=payload_low, headers={"X-Device-Key": VALID_KEY})
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "stored"

    # Check that database trigger created exactly one flag
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM flags WHERE patient_id=2 AND source_type='Sensor' AND status='Open'")
        flags = cur.fetchall()
        assert len(flags) == 1, f"Expected 1 flag, got {len(flags)}"
        flag = flags[0]
        assert flag["severity"] == "Urgent_Review"
        assert "below the clinician-approved limit of 94.00" in flag["reason"]
        flag_id = flag["flag_id"]
        print(f"✅ Low SpO2 reading raised exactly ONE Urgent_Review flag #{flag_id}: '{flag['reason']}'")

    # Second low reading arrives at a newer timestamp while the first flag is still Open
    t2 = int(time.time()) - 100
    payload_low_2 = {
        "device_id": "ESP32-DEMO-02",
        "measurement_type": "SpO2",
        "value": 89.0,
        "unit": "%",
        "measured_at": t2,
        "quality": "Simulated",
    }
    res2 = client.post("/device/readings", json=payload_low_2, headers={"X-Device-Key": VALID_KEY})
    assert res2.status_code == 200
    assert res2.json()["status"] == "stored"

    # Verify that NO duplicate open flag was created
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM flags WHERE patient_id=2 AND source_type='Sensor' AND status='Open'")
        flags_after = cur.fetchall()
        assert len(flags_after) == 1, f"Duplicate flag detected! Count: {len(flags_after)}"
        print("✅ Duplicate flag protection verified: 2nd low SpO2 reading did not create a redundant flag")


def test_plausibility_guard():
    t_impossible = int(time.time()) - 50
    payload_bad = {
        "device_id": "ESP32-DEMO-01",
        "measurement_type": "Heart_Rate",
        "value": 450.0,
        "unit": "bpm",
        "measured_at": t_impossible,
        "quality": "Good",
    }
    res = client.post("/device/readings", json=payload_bad, headers={"X-Device-Key": VALID_KEY})
    assert res.status_code == 200
    assert res.json()["status"] == "stored"

    # Verify trigger converted quality to 'Invalid' and raised no flag
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT quality_status FROM sensor_readings WHERE device_id='ESP32-DEMO-01' AND measurement_value=450.0")
        row = cur.fetchone()
        assert row["quality_status"] == "Invalid", f"Expected Invalid, got {row['quality_status']}"

        cur.execute("SELECT COUNT(*) AS c FROM flags WHERE reason LIKE '%450%'")
        assert cur.fetchone()["c"] == 0
        print("✅ Impossible reading (450 bpm) stored as 'Invalid'; zero clinical flags raised")


if __name__ == "__main__":
    test_auth_and_device_validation()
    test_idempotent_ingestion()
    test_low_spo2_creates_flag_and_deduplicates()
    test_plausibility_guard()
    print("\n🎉 ALL MILESTONE M2 DEVICE TELEMETRY TESTS PASSED!")
