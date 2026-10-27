"""
device/simulator.py — CareLoop IoT Device Simulator

Simulates wearable sensor telemetry for CareLoop.
Posts Heart_Rate (bpm) and SpO2 (%) to POST /device/readings.
Supports --low-spo2 to trigger clinical alert rules during demos and testing.
"""

import time
import random
import argparse
import requests


def main():
    parser = argparse.ArgumentParser(description="CareLoop IoT Sensor Simulator")
    parser.add_argument("--api", default="http://localhost:8000", help="CareLoop API base URL")
    parser.add_argument("--device", default="ESP32-DEMO-02", help="Registered device ID (default: ESP32-DEMO-02)")
    parser.add_argument("--key", default="demo-device-key-change-me", help="Device API authentication key")
    parser.add_argument("--interval", type=int, default=10, help="Seconds between reading cycles")
    parser.add_argument("--low-spo2", action="store_true", help="Simulate SpO2 below clinician-approved limit (e.g. 89-91%)")
    parser.add_argument("--once", action="store_true", help="Send a single cycle and exit (useful for testing)")
    args = parser.parse_args()

    print("=" * 60)
    print(" CareLoop Sensor Simulator Active")
    print(f" Target API: {args.api}/device/readings")
    print(f" Device ID:  {args.device}")
    print(f" Low SpO2:   {'ENABLED (89-91%)' if args.low_spo2 else 'DISABLED (Normal 95-98%)'}")
    print(f" Interval:   {args.interval}s {'(Running once)' if args.once else '(Continuous loop)'}")
    print("=" * 60)

    cycle_count = 0
    while True:
        cycle_count += 1
        now = int(time.time())
        hr = random.randint(72, 92)
        spo2 = random.randint(89, 91) if args.low_spo2 else random.randint(95, 98)

        print(f"\n[Cycle #{cycle_count} | Epoch {now}] Generating readings...")
        for mtype, val, unit in (("Heart_Rate", hr, "bpm"), ("SpO2", spo2, "%")):
            payload = {
                "device_id": args.device,
                "measurement_type": mtype,
                "value": float(val),
                "unit": unit,
                "measured_at": now,
                "quality": "Simulated",
            }
            try:
                res = requests.post(
                    f"{args.api}/device/readings",
                    json=payload,
                    headers={"X-Device-Key": args.key},
                    timeout=5,
                )
                print(f"  -> {mtype:10}: {val} {unit:4} | HTTP {res.status_code} | {res.json()}")
            except requests.exceptions.RequestException as e:
                print(f"  -> {mtype:10}: {val} {unit:4} | Connection Error: {e}")

        if args.once:
            print("\nSingle cycle complete. Exiting.")
            break

        time.sleep(args.interval)


if __name__ == "__main__":
    main()
