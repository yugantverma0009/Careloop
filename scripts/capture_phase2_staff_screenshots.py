"""
scripts/capture_phase2_staff_screenshots.py

Captures high-resolution CDP screenshots for Phase 2 verification:
1. Patient Directory (Light Mode) with filters, search, adherence rates, silent devices
2. Patient Directory (Dark Mode)
3. Patient Overview Clinical Snapshot (Vitals telemetry with data quality badges, 7-day adherence, caregivers)
4. Patient Medicines & Exceptions Tab (Discharge prescriptions, self-reported adherence notes)
5. Upgraded Timeline (Event filter chips, HR telemetry trend with approved rule limit dashed lines, day groups)
6. Break-Glass Access Required Modal / Wall for unassigned patient

Output saved to docs/screenshots/phase2_staff/
"""

import os
import sys
import json
import time
import base64
import subprocess
import asyncio
import tempfile
import requests
import websockets

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../docs/screenshots/phase2_staff"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEBUG_PORT = 9234

async def send_cmd(ws, method, params=None, msg_id=1):
    msg = {"id": msg_id, "method": method, "params": params or {}}
    await ws.send(json.dumps(msg))
    while True:
        resp = await ws.recv()
        data = json.loads(resp)
        if data.get("id") == msg_id:
            return data.get("result", {})

async def capture_screenshot(ws, filename, msg_id_base):
    await asyncio.sleep(1.2)
    res = await send_cmd(ws, "Page.captureScreenshot", {"format": "png"}, msg_id=msg_id_base)
    b64_data = res.get("data", "")
    if b64_data:
        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(b64_data))
        print(f"  ✓ Saved {filename} ({len(b64_data)} bytes)")

async def evaluate_js(ws, expr, msg_id):
    return await send_cmd(ws, "Runtime.evaluate", {"expression": expr, "awaitPromise": True}, msg_id=msg_id)

async def main():
    print("Fetching auth token for Dr. Ananya Sharma...")
    doc_res = requests.post("http://127.0.0.1:8000/auth/login", json={"email": "ananya.demo@example.test", "password": "Demo@12345"}).json()
    doc_token = doc_res["access_token"]
    doc_user = json.dumps({
        "account_id": doc_res["account_id"],
        "email": "ananya.demo@example.test",
        "role": "Doctor",
        "name": "Dr. Ananya Sharma",
        "staff_id": doc_res["staff_id"],
    })

    tmp_dir = tempfile.mkdtemp()
    cmd = [
        CHROME_BIN,
        "--headless=new",
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={tmp_dir}",
        "--window-size=1440,960",
        "--disable-gpu",
        "--no-sandbox",
        "about:blank",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2.0)

    try:
        tab_info = requests.put(f"http://127.0.0.1:{DEBUG_PORT}/json/new").json()
        ws_url = tab_info["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url, max_size=50 * 1024 * 1024) as ws:
            mid = 1
            await send_cmd(ws, "Page.enable", msg_id=mid); mid += 1
            await send_cmd(ws, "Runtime.enable", msg_id=mid); mid += 1
            await send_cmd(ws, "Emulation.setDeviceMetricsOverride", {
                "width": 1440,
                "height": 960,
                "deviceScaleFactor": 1,
                "mobile": False,
            }, msg_id=mid); mid += 1

            # Navigate to staff portal with doctor credentials injected
            print("\nNavigating to Staff Portal...")
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/staff"}, msg_id=mid); mid += 1
            await asyncio.sleep(1.0)
            await evaluate_js(ws, f"""
                localStorage.setItem('careloop_token', '{doc_token}');
                localStorage.setItem('careloop_user', '{doc_user}');
                localStorage.setItem('careloop_role', 'Doctor');
                localStorage.setItem('theme', 'light');
                document.documentElement.setAttribute('data-theme', 'light');
            """, mid); mid += 1

            # Reload so React initializes with token
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/staff"}, msg_id=mid); mid += 1
            await asyncio.sleep(2.0)

            # ── 1. PATIENT DIRECTORY (LIGHT MODE) ──
            print("\n1. Capturing Patient Directory (Light Mode)...")
            await evaluate_js(ws, """
                const buttons = Array.from(document.querySelectorAll('button'));
                const dirBtn = buttons.find(b => b.textContent.includes('Patient directory'));
                if (dirBtn) dirBtn.click();
            """, mid); mid += 1
            await asyncio.sleep(1.2)
            await capture_screenshot(ws, "01_patient_directory_light.png", mid); mid += 1

            # ── 2. PATIENT DIRECTORY (DARK MODE) ──
            print("\n2. Capturing Patient Directory (Dark Mode)...")
            await evaluate_js(ws, """
                document.documentElement.setAttribute('data-theme', 'dark');
                localStorage.setItem('theme', 'dark');
            """, mid); mid += 1
            await asyncio.sleep(0.8)
            await capture_screenshot(ws, "02_patient_directory_dark.png", mid); mid += 1

            # Switch back to light mode
            await evaluate_js(ws, """
                document.documentElement.setAttribute('data-theme', 'light');
                localStorage.setItem('theme', 'light');
            """, mid); mid += 1
            await asyncio.sleep(0.5)

            # ── 3. PATIENT OVERVIEW CLINICAL SNAPSHOT (LIGHT MODE) ──
            print("\n3. Capturing Patient Overview Clinical Snapshot...")
            await evaluate_js(ws, """
                const btn1 = document.getElementById('btn-view-chart-1');
                if (btn1) btn1.click();
            """, mid); mid += 1
            await asyncio.sleep(1.8)
            await capture_screenshot(ws, "03_patient_overview_tab_light.png", mid); mid += 1

            # ── 4. PATIENT MEDICINES & ADHERENCE TAB ──
            print("\n4. Capturing Patient Medicines Tab...")
            await evaluate_js(ws, """
                const medBtn = document.getElementById('tab-medicines');
                if (medBtn) medBtn.click();
            """, mid); mid += 1
            await asyncio.sleep(1.5)
            await capture_screenshot(ws, "04_patient_medicines_tab_light.png", mid); mid += 1

            # ── 5. UPGRADED TIMELINE TAB ──
            print("\n5. Capturing Upgraded Timeline Tab...")
            await evaluate_js(ws, """
                const timeBtn = document.getElementById('tab-timeline');
                if (timeBtn) timeBtn.click();
            """, mid); mid += 1
            await asyncio.sleep(2.0)
            await capture_screenshot(ws, "05_patient_timeline_grouped_light.png", mid); mid += 1

            # ── 6. BREAK-GLASS ACCESS REQUIRED MODAL / SCREEN ──
            print("\n6. Capturing Break-Glass Access Required Screen...")
            # Navigate back to directory
            await evaluate_js(ws, """
                const backBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('← Directory'));
                if (backBtn) backBtn.click();
            """, mid); mid += 1
            await asyncio.sleep(1.2)

            # Click unassigned Patient 4 (Sunita Rao, CL-00004)
            await evaluate_js(ws, """
                const btn4 = document.getElementById('btn-view-chart-4');
                if (btn4) btn4.click();
            """, mid); mid += 1
            await asyncio.sleep(1.8)
            await capture_screenshot(ws, "06_break_glass_modal_light.png", mid); mid += 1

            print("\nAll 6 Phase 2 staff screenshots captured successfully!")

    finally:
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    asyncio.run(main())
