"""
scripts/capture_baseline_staff.py

Captures baseline screenshots of:
- Landing (light, dark)
- Login (light, dark)
- Patient Portal (light, dark)
- Staff Portal Triage (light, dark)
- Staff Portal Timeline (light, dark)
- Staff Portal Tasks (light, dark)
- Staff Portal Summaries (light, dark)

Saved to docs/screenshots/baseline_staff/
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

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../docs/screenshots/baseline_staff"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEBUG_PORT = 9231

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
    print("Fetching auth tokens from backend...")
    pat_res = requests.post("http://127.0.0.1:8000/auth/login", json={"email": "aarav.demo@example.test", "password": "Demo@12345"}).json()
    doc_res = requests.post("http://127.0.0.1:8000/auth/login", json={"email": "ananya.demo@example.test", "password": "Demo@12345"}).json()

    pat_token = pat_res["access_token"]
    pat_user = json.dumps({"account_id": pat_res["account_id"], "email": "aarav.demo@example.test", "role": "Patient", "name": "Aarav Patel", "patient_id": pat_res["patient_id"]})

    doc_token = doc_res["access_token"]
    doc_user = json.dumps({"account_id": doc_res["account_id"], "email": "ananya.demo@example.test", "role": "Doctor", "name": "Dr. Ananya Sharma", "staff_id": doc_res["staff_id"]})

    tmp_dir = tempfile.mkdtemp()
    cmd = [
        CHROME_BIN,
        "--headless=new",
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={tmp_dir}",
        "--window-size=1440,900",
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
                "height": 900,
                "deviceScaleFactor": 1,
                "mobile": False,
            }, msg_id=mid); mid += 1

            # 1. Landing Light & Dark
            print("\nCapturing Landing Page (Light & Dark)...")
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/"}, msg_id=mid); mid += 1
            await asyncio.sleep(2.0)
            await capture_screenshot(ws, "landing_light.png", mid); mid += 1

            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'dark'); localStorage.setItem('careloop_theme', 'dark');", mid); mid += 1
            await capture_screenshot(ws, "landing_dark.png", mid); mid += 1

            # 2. Login Light & Dark
            print("\nCapturing Login Page (Light & Dark)...")
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/login"}, msg_id=mid); mid += 1
            await asyncio.sleep(2.0)
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'light'); localStorage.setItem('careloop_theme', 'light');", mid); mid += 1
            await capture_screenshot(ws, "login_light.png", mid); mid += 1

            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'dark'); localStorage.setItem('careloop_theme', 'dark');", mid); mid += 1
            await capture_screenshot(ws, "login_dark.png", mid); mid += 1

            # 3. Patient Portal Light & Dark
            print("\nCapturing Patient Portal (Light & Dark)...")
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/patient"}, msg_id=mid); mid += 1
            await asyncio.sleep(1.0)
            await evaluate_js(ws, f"""
                localStorage.setItem('careloop_token', '{pat_token}');
                localStorage.setItem('careloop_user', '{pat_user}');
                localStorage.setItem('careloop_theme', 'light');
                document.documentElement.setAttribute('data-theme', 'light');
            """, mid); mid += 1
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/patient"}, msg_id=mid); mid += 1
            await asyncio.sleep(2.5)
            await capture_screenshot(ws, "patient_overview_light.png", mid); mid += 1

            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'dark'); localStorage.setItem('careloop_theme', 'dark');", mid); mid += 1
            await capture_screenshot(ws, "patient_overview_dark.png", mid); mid += 1

            # 4. Staff Portal Setup
            print("\nSetting Staff Doctor Credentials...")
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/staff"}, msg_id=mid); mid += 1
            await asyncio.sleep(1.0)
            await evaluate_js(ws, f"""
                localStorage.setItem('careloop_token', '{doc_token}');
                localStorage.setItem('careloop_user', '{doc_user}');
                localStorage.setItem('careloop_theme', 'light');
                document.documentElement.setAttribute('data-theme', 'light');
            """, mid); mid += 1
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/staff"}, msg_id=mid); mid += 1
            await asyncio.sleep(2.5)

            # Tab 1: Triage (Who needs attention)
            print("Capturing Staff Triage Tab...")
            await capture_screenshot(ws, "staff_triage_light.png", mid); mid += 1
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'dark'); localStorage.setItem('careloop_theme', 'dark');", mid); mid += 1
            await capture_screenshot(ws, "staff_triage_dark.png", mid); mid += 1
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'light'); localStorage.setItem('careloop_theme', 'light');", mid); mid += 1

            # Tab 2: Timeline
            print("Capturing Staff Timeline Tab...")
            await evaluate_js(ws, """
                const btns = Array.from(document.querySelectorAll('button'));
                const timelineBtn = btns.find(b => b.textContent.includes('Patient timeline'));
                if (timelineBtn) timelineBtn.click();
            """, mid); mid += 1
            await asyncio.sleep(2.0)
            await capture_screenshot(ws, "staff_timeline_light.png", mid); mid += 1
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'dark'); localStorage.setItem('careloop_theme', 'dark');", mid); mid += 1
            await capture_screenshot(ws, "staff_timeline_dark.png", mid); mid += 1
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'light'); localStorage.setItem('careloop_theme', 'light');", mid); mid += 1

            # Tab 3: Tasks
            print("Capturing Staff Tasks Tab...")
            await evaluate_js(ws, """
                const btns = Array.from(document.querySelectorAll('button'));
                const tasksBtn = btns.find(b => b.textContent.includes('Follow-up tasks'));
                if (tasksBtn) tasksBtn.click();
            """, mid); mid += 1
            await asyncio.sleep(2.0)
            await capture_screenshot(ws, "staff_tasks_light.png", mid); mid += 1
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'dark'); localStorage.setItem('careloop_theme', 'dark');", mid); mid += 1
            await capture_screenshot(ws, "staff_tasks_dark.png", mid); mid += 1
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'light'); localStorage.setItem('careloop_theme', 'light');", mid); mid += 1

            # Tab 4: Summaries
            print("Capturing Staff Summaries Tab...")
            await evaluate_js(ws, """
                const btns = Array.from(document.querySelectorAll('button'));
                const summariesBtn = btns.find(b => b.textContent.includes('Draft summaries'));
                if (summariesBtn) summariesBtn.click();
            """, mid); mid += 1
            await asyncio.sleep(2.0)
            await capture_screenshot(ws, "staff_summaries_light.png", mid); mid += 1
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'dark'); localStorage.setItem('careloop_theme', 'dark');", mid); mid += 1
            await capture_screenshot(ws, "staff_summaries_dark.png", mid); mid += 1

            print("\nAll baseline staff screenshots captured in docs/screenshots/baseline_staff/!")

    finally:
        proc.terminate()

if __name__ == "__main__":
    asyncio.run(main())
