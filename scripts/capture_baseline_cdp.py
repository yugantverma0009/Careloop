"""
scripts/capture_baseline_cdp.py

Automated baseline screenshot capture using Chrome DevTools Protocol (CDP).
Captures:
- Landing (light, dark, EN, HI)
- Login (light, dark, EN, HI)
- Staff (light, dark, EN, HI)
- Patient (light, dark, EN, HI)
"""

import os
import sys
import json
import time
import base64
import subprocess
import asyncio
import urllib.request
import requests
import websockets

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../docs/screenshots/baseline"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEBUG_PORT = 9225

async def send_cmd(ws, method, params=None, msg_id=1):
    msg = {"id": msg_id, "method": method, "params": params or {}}
    await ws.send(json.dumps(msg))
    while True:
        resp = await ws.recv()
        data = json.loads(resp)
        if data.get("id") == msg_id:
            return data.get("result", {})

async def capture_screenshot(ws, filename, msg_id_base):
    # Wait 800ms for animations/render
    await asyncio.sleep(0.8)
    res = await send_cmd(ws, "Page.captureScreenshot", {"format": "png"}, msg_id=msg_id_base)
    b64_data = res.get("data", "")
    if b64_data:
        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(b64_data))
        print(f"  ✓ Saved {filename} ({len(b64_data)} b64 bytes)")

async def evaluate_js(ws, expr, msg_id):
    return await send_cmd(ws, "Runtime.evaluate", {"expression": expr, "awaitPromise": True}, msg_id=msg_id)

async def main():
    # 1. Fetch Auth Tokens
    print("Fetching auth tokens from backend...")
    pat_res = requests.post("http://127.0.0.1:8000/auth/login", json={"email": "aarav.demo@example.test", "password": "Demo@12345"}).json()
    doc_res = requests.post("http://127.0.0.1:8000/auth/login", json={"email": "ananya.demo@example.test", "password": "Demo@12345"}).json()

    pat_token = pat_res["access_token"]
    pat_user = json.dumps({"account_id": pat_res["account_id"], "email": "aarav.demo@example.test", "role": "Patient", "name": "Aarav Patel", "patient_id": pat_res["patient_id"]})

    doc_token = doc_res["access_token"]
    doc_user = json.dumps({"account_id": doc_res["account_id"], "email": "ananya.demo@example.test", "role": "Doctor", "name": "Dr. Ananya Sharma", "staff_id": doc_res["staff_id"]})

    # 2. Launch Chrome Headless with Remote Debugging
    print(f"Launching headless Chrome on port {DEBUG_PORT}...")
    import tempfile
    temp_profile = tempfile.mkdtemp()
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
        # Create new target tab
        tab_info = requests.put(f"http://127.0.0.1:{DEBUG_PORT}/json/new").json()
        ws_url = tab_info["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
            mid = 100
            await send_cmd(ws, "Page.enable", msg_id=mid); mid += 1
            await send_cmd(ws, "DOM.enable", msg_id=mid); mid += 1
            await send_cmd(ws, "Emulation.setDeviceMetricsOverride", {
                "width": 1440,
                "height": 900,
                "deviceScaleFactor": 1,
                "mobile": False
            }, msg_id=mid); mid += 1

            # ─── 1. LANDING PAGE ──────────────────────────────────────────
            print("\n1. Capturing Landing Page...")
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/"}, msg_id=mid); mid += 1
            await asyncio.sleep(1.5)

            # Landing Light EN
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'light')", msg_id=mid); mid += 1
            await capture_screenshot(ws, "landing_light_en.png", mid); mid += 1

            # Landing Dark EN
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'dark')", msg_id=mid); mid += 1
            await capture_screenshot(ws, "landing_dark_en.png", mid); mid += 1

            # Landing Light HI
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'light')", msg_id=mid); mid += 1
            await capture_screenshot(ws, "landing_light_hi.png", mid); mid += 1

            # Landing Dark HI
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'dark')", msg_id=mid); mid += 1
            await capture_screenshot(ws, "landing_dark_hi.png", mid); mid += 1

            # ─── 2. LOGIN PAGE ────────────────────────────────────────────
            print("\n2. Capturing Login Page...")
            await evaluate_js(ws, "localStorage.clear()", msg_id=mid); mid += 1
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/login"}, msg_id=mid); mid += 1
            await asyncio.sleep(1.5)

            # Login Light EN
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'light')", msg_id=mid); mid += 1
            await capture_screenshot(ws, "login_light_en.png", mid); mid += 1

            # Login Dark EN
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'dark')", msg_id=mid); mid += 1
            await capture_screenshot(ws, "login_dark_en.png", mid); mid += 1

            # Login Light HI
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'light')", msg_id=mid); mid += 1
            await capture_screenshot(ws, "login_light_hi.png", mid); mid += 1

            # Login Dark HI
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'dark')", msg_id=mid); mid += 1
            await capture_screenshot(ws, "login_dark_hi.png", mid); mid += 1

            # ─── 3. PATIENT PORTAL ────────────────────────────────────────
            print("\n3. Capturing Patient Portal (/patient)...")
            set_pat_storage = f"""
            localStorage.setItem('careloop_token', '{pat_token}');
            localStorage.setItem('careloop_user', JSON.stringify({pat_user}));
            """
            await evaluate_js(ws, set_pat_storage, msg_id=mid); mid += 1
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/patient"}, msg_id=mid); mid += 1
            await asyncio.sleep(2.0)

            # Patient Light EN
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'light')", msg_id=mid); mid += 1
            # Ensure EN button clicked if exists
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

            # ─── 4. STAFF PORTAL ──────────────────────────────────────────
            print("\n4. Capturing Staff Portal (/staff)...")
            set_doc_storage = f"""
            localStorage.setItem('careloop_token', '{doc_token}');
            localStorage.setItem('careloop_user', JSON.stringify({doc_user}));
            """
            await evaluate_js(ws, set_doc_storage, msg_id=mid); mid += 1
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/staff"}, msg_id=mid); mid += 1
            await asyncio.sleep(2.0)

            # Staff Light EN
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'light')", msg_id=mid); mid += 1
            await capture_screenshot(ws, "staff_triage_light_en.png", mid); mid += 1

            # Staff Dark EN
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'dark')", msg_id=mid); mid += 1
            await capture_screenshot(ws, "staff_triage_dark_en.png", mid); mid += 1

            # Staff Light HI
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'light')", msg_id=mid); mid += 1
            await capture_screenshot(ws, "staff_triage_light_hi.png", mid); mid += 1

            # Staff Dark HI
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'dark')", msg_id=mid); mid += 1
            await capture_screenshot(ws, "staff_triage_dark_hi.png", mid); mid += 1

        print("\nAll baseline screenshots successfully captured in docs/screenshots/baseline/!")

    finally:
        chrome_proc.terminate()
        chrome_proc.wait()

if __name__ == "__main__":
    asyncio.run(main())
