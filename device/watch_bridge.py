"""
Hardware/watch.py — AI Nurse Watch Bluetooth Bridge for CareLoop

Connects to the Bluetooth Serial port of the watch and forwards
heart rate telemetry to the CareLoop /device/readings endpoint.
"""

import serial
import time
import requests
import sys

# --- HARDWARE CONFIG ---
BLUETOOTH_PORT = '/dev/cu.AI_Nurse_Watch' 
BAUD_RATE = 115200

# --- CARELOOP CONFIG ---
API_URL = "http://localhost:8000"
DEVICE_KEY = "demo-device-key-change-me"

print("\n" + "="*40)
print(" CARELOOP WATCH - BLUETOOTH BRIDGE")
print("="*40)

if len(sys.argv) > 1:
    DEVICE_ID = sys.argv[1]
else:
    DEVICE_ID = input("Enter Device ID for this demo (default: ESP32-DEMO-01): ").strip() or "ESP32-DEMO-01"

print(f"\nTargeting Device ID: {DEVICE_ID}")
print("-" * 40)

try:
    print(f"Connecting to AI Nurse Watch on {BLUETOOTH_PORT}...")
    ser = serial.Serial(BLUETOOTH_PORT, BAUD_RATE, timeout=0.1)
    ser.flushInput()
    print("Connection Active! Forwarding vitals to CareLoop...\n")
    
    while True:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        
        if line:
            try:
                parts = line.split(',')
                if len(parts) >= 1:
                    bpm = int(parts[0])
                    fall = int(parts[1]) if len(parts) > 1 else 0
                    
                    if fall == 1:
                        print(f"ALERT: FALL DETECTED! | BPM: {bpm}")
                    else:
                        print(f"BPM: {bpm} | Status: Normal")
                    
                    now = int(time.time())
                    payload = {
                        "device_id": DEVICE_ID,
                        "measurement_type": "Heart_Rate",
                        "value": float(bpm),
                        "unit": "bpm",
                        "measured_at": now,
                        "quality": "Good" if bpm > 0 else "Questionable",
                    }
                    
                    try:
                        res = requests.post(
                            f"{API_URL}/device/readings", 
                            json=payload,
                            headers={"X-Device-Key": DEVICE_KEY},
                            timeout=1.0,
                        )
                        print(f" -> Telemetry POST status: {res.status_code} ({res.json().get('status')})")
                    except requests.exceptions.RequestException as e:
                        print(f" ⚠️ Backend offline: {e}")
            
            except ValueError:
                continue 

except Exception as e:
    print(f"Error: {e}")
finally:
    if 'ser' in locals():
        ser.close()