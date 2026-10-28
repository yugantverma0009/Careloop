"""
scripts/capture_phase1_screenshots.py

Captures Phase 1 upgraded patient portal screens:
- patient_overview_light_en.png
- patient_overview_dark_en.png
- patient_overview_light_hi.png
- patient_overview_dark_hi.png
- landing_light_en.png (verification)
- login_light_en.png (verification)
- staff_triage_light_en.png (verification)

Saved to docs/screenshots/phase1/
"""

import os
import json
import time
import base64
import subprocess
import asyncio
import tempfile
import requests
import websockets

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../docs/screenshots/phase1"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEBUG_PORT = 9228

async def send_cmd(ws, method, params=None, msg_id=1):
    msg = {"id": msg_id, "method": method, "params": params or {}}
    await ws.send(json.dumps(msg))
    while True:
        resp = await ws.recv()
        data = json.loads(resp)
        if data.get("id") == msg_id:
            return data.get("result", {})

async def capture_screenshot(ws, filename, msg_id_base):
    await asyncio.sleep(1.0)
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

    temp_profile = tempfile.mkdtemp()
    print(f"Launching headless Chrome on port {DEBUG_PORT}...")
    chrome_proc = subprocess.Popen([
        CHROME_BIN,
        "--headless=new",
        "--disable-gpu",
        f"--user-data-dir={temp_profile}",
        f"--remote-debugging-port={DEBUG_PORT}",
        "--window-size=1440,900",
        "--hide-scrollbars",
        "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    time.sleep(1.8)

    try:
        tab_info = requests.put(f"http://127.0.0.1:{DEBUG_PORT}/json/new").json()
        ws_url = tab_info["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
            mid = 200
            await send_cmd(ws, "Page.enable", msg_id=mid); mid += 1
            await send_cmd(ws, "DOM.enable", msg_id=mid); mid += 1
            await send_cmd(ws, "Emulation.setDeviceMetricsOverride", {
                "width": 1440,
                "height": 900,
                "deviceScaleFactor": 1,
                "mobile": False
            }, msg_id=mid); mid += 1

            # ─── 1. PATIENT PORTAL (PHASE 1 CHANGED SCREEN) ───────────
            print("\n1. Capturing Patient Portal Upgraded Overview (/patient)...")
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/login"}, msg_id=mid); mid += 1
            await asyncio.sleep(1.0)

            set_pat_storage = f"""
            localStorage.setItem('careloop_token', '{pat_token}');
            localStorage.setItem('careloop_user', JSON.stringify({pat_user}));
            """
            await evaluate_js(ws, set_pat_storage, msg_id=mid); mid += 1
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/patient"}, msg_id=mid); mid += 1
            await asyncio.sleep(2.5)

            # Patient Light EN
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'light')", msg_id=mid); mid += 1
            await evaluate_js(ws, "(() => { const btns = Array.from(document.querySelectorAll('button')); const b = btns.find(x => x.textContent.trim() === 'EN'); if (b) b.click(); })()", msg_id=mid); mid += 1
            await asyncio.sleep(0.5)
            await capture_screenshot(ws, "patient_overview_light_en.png", mid); mid += 1

            # Patient Dark EN
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'dark')", msg_id=mid); mid += 1
            await asyncio.sleep(0.5)
            await capture_screenshot(ws, "patient_overview_dark_en.png", mid); mid += 1

            # Patient Dark HI
            await evaluate_js(ws, "(() => { const btns = Array.from(document.querySelectorAll('button')); const b = btns.find(x => x.textContent.trim() === 'HI'); if (b) b.click(); })()", msg_id=mid); mid += 1
            await asyncio.sleep(0.5)
            await capture_screenshot(ws, "patient_overview_dark_hi.png", mid); mid += 1

            # Patient Light HI
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'light')", msg_id=mid); mid += 1
            await asyncio.sleep(0.5)
            await capture_screenshot(ws, "patient_overview_light_hi.png", mid); mid += 1

            # ─── 2. LANDING & LOGIN & STAFF REGRESSION CHECKS ────────
            print("\n2. Capturing Baseline Verification Screens...")
            # Landing Light EN
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/"}, msg_id=mid); mid += 1
            await asyncio.sleep(1.5)
            await capture_screenshot(ws, "landing_light_en_check.png", mid); mid += 1

            # Login Light EN
            await evaluate_js(ws, "localStorage.clear()", msg_id=mid); mid += 1
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/login"}, msg_id=mid); mid += 1
            await asyncio.sleep(1.5)
            await capture_screenshot(ws, "login_light_en_check.png", mid); mid += 1

            # Staff Light EN
            set_doc_storage = f"""
            localStorage.setItem('careloop_token', '{doc_token}');
            localStorage.setItem('careloop_user', JSON.stringify({doc_user}));
            """
            await evaluate_js(ws, set_doc_storage, msg_id=mid); mid += 1
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/staff"}, msg_id=mid); mid += 1
            await asyncio.sleep(2.0)
            await capture_screenshot(ws, "staff_triage_light_en_check.png", mid); mid += 1

        print("\n✅ Phase 1 screenshots successfully captured in docs/screenshots/phase1/!")

    finally:
        chrome_proc.terminate()
        chrome_proc.wait()

if __name__ == "__main__":
    asyncio.run(main())
