"""
scripts/capture_phase2_screenshots.py

Captures Phase 2 upgraded patient portal screens:
- patient_overview_plan_checklist_light_en.png
- patient_overview_plan_checklist_dark_en.png
- patient_calendar_light_en.png
- patient_calendar_dark_en.png
- patient_calendar_light_hi.png
- patient_calendar_dark_hi.png
- patient_reminders_open.png
- patient_calendar_day_sheet.png
- landing_light_en_check.png (verification)
- login_light_en_check.png (verification)

Saved to docs/screenshots/phase2/
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

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../docs/screenshots/phase2"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEBUG_PORT = 9228

async def send_cmd(ws, method, params=None, msg_id=1):
    msg = {"id": msg_id, "method": method}
    if params:
        msg["params"] = params
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
    else:
        print(f"  ✗ Warning: No data for {filename}")

async def evaluate_js(ws, expr, msg_id):
    return await send_cmd(ws, "Runtime.evaluate", {"expression": expr, "awaitPromise": True}, msg_id=msg_id)

async def wait_for_selector(ws, selector, msg_id_base, timeout=10.0):
    start = time.time()
    mid = msg_id_base
    while time.time() - start < timeout:
        res = await evaluate_js(ws, f"Boolean(document.querySelector('{selector}'))", msg_id=mid)
        mid += 1
        if res.get("result", {}).get("value") is True:
            return mid
        await asyncio.sleep(0.3)
    return mid

async def main():
    print("Fetching auth tokens from backend...")
    pat_res = requests.post("http://127.0.0.1:8000/auth/login", json={"email": "aarav.demo@example.test", "password": "Demo@12345"}).json()
    pat_token = pat_res["access_token"]
    pat_user = json.dumps({"account_id": pat_res["account_id"], "email": "aarav.demo@example.test", "role": "Patient", "name": "Aarav Patel", "patient_id": pat_res["patient_id"]})

    temp_profile = tempfile.mkdtemp()
    chrome_proc = subprocess.Popen([
        CHROME_BIN,
        "--headless=new",
        "--disable-gpu",
        f"--user-data-dir={temp_profile}",
        f"--remote-debugging-port={DEBUG_PORT}",
        "--window-size=1440,960",
        "--hide-scrollbars",
        "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    time.sleep(2.0)

    try:
        tab_info = requests.put(f"http://127.0.0.1:{DEBUG_PORT}/json/new").json()
        ws_url = tab_info["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
            mid = 300
            await send_cmd(ws, "Page.enable", msg_id=mid); mid += 1
            await send_cmd(ws, "DOM.enable", msg_id=mid); mid += 1
            await send_cmd(ws, "Emulation.setDeviceMetricsOverride", {
                "width": 1440,
                "height": 960,
                "deviceScaleFactor": 1,
                "mobile": False
            }, msg_id=mid); mid += 1

            # 1. Verification of Landing Page
            print("\n1. Capturing Landing Page...")
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/"}, msg_id=mid); mid += 1
            mid = await wait_for_selector(ws, "nav", mid)
            await asyncio.sleep(1.0)
            await capture_screenshot(ws, "landing_light_en_check.png", mid); mid += 1

            # 2. Verification of Login Page
            print("\n2. Capturing Login Page...")
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/login"}, msg_id=mid); mid += 1
            mid = await wait_for_selector(ws, "form", mid)
            await asyncio.sleep(1.0)
            await capture_screenshot(ws, "login_light_en_check.png", mid); mid += 1

            # Seed localStorage with Patient session while on /login
            set_pat_storage = f"""
            localStorage.setItem('careloop_token', '{pat_token}');
            localStorage.setItem('careloop_user', JSON.stringify({pat_user}));
            """
            await evaluate_js(ws, set_pat_storage, msg_id=mid); mid += 1

            # 3. Patient Overview with Plan Checklist (Light EN)
            print("\n3. Capturing Patient Overview with Plan Checklist (Light EN)...")
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/patient"}, msg_id=mid); mid += 1
            mid = await wait_for_selector(ws, "header", mid)
            await asyncio.sleep(2.0)
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'light')", msg_id=mid); mid += 1
            await evaluate_js(ws, "(() => { const btns = Array.from(document.querySelectorAll('button')); const b = btns.find(x => x.textContent.trim() === 'EN'); if (b) b.click(); })()", msg_id=mid); mid += 1
            await asyncio.sleep(0.5)
            await capture_screenshot(ws, "patient_overview_plan_checklist_light_en.png", mid); mid += 1

            # 4. Patient Overview with Plan Checklist (Dark EN)
            print("\n4. Capturing Patient Overview with Plan Checklist (Dark EN)...")
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'dark')", msg_id=mid); mid += 1
            await asyncio.sleep(0.5)
            await capture_screenshot(ws, "patient_overview_plan_checklist_dark_en.png", mid); mid += 1

            # 5. In-App Reminders Popover Open
            print("\n5. Capturing Reminders Popover Open...")
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'light')", msg_id=mid); mid += 1
            await evaluate_js(ws, """
                const btn = document.querySelector('button[aria-label="In-app reminders"]');
                if (btn) btn.click();
            """, msg_id=mid); mid += 1
            await asyncio.sleep(0.6)
            await capture_screenshot(ws, "patient_reminders_open.png", mid); mid += 1

            # Close reminders popover
            await evaluate_js(ws, """
                const btn = document.querySelector('button[aria-label="In-app reminders"]');
                if (btn) btn.click();
            """, msg_id=mid); mid += 1
            await asyncio.sleep(0.3)

            # 6. Switch to Calendar Tab (Light EN)
            print("\n6. Capturing My Calendar Tab (Light EN)...")
            await evaluate_js(ws, """
                const calBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('My calendar') || b.textContent.includes('मेरा कैलेंडर'));
                if (calBtn) calBtn.click();
            """, msg_id=mid); mid += 1
            await asyncio.sleep(2.0)
            await capture_screenshot(ws, "patient_calendar_light_en.png", mid); mid += 1

            # 7. Calendar Tab (Dark EN)
            print("\n7. Capturing My Calendar Tab (Dark EN)...")
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'dark')", msg_id=mid); mid += 1
            await asyncio.sleep(0.5)
            await capture_screenshot(ws, "patient_calendar_dark_en.png", mid); mid += 1

            # 8. Switch to Hindi (Light HI)
            print("\n8. Capturing My Calendar Tab (Light HI)...")
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'light')", msg_id=mid); mid += 1
            await evaluate_js(ws, """
                const hiBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'HI');
                if (hiBtn) hiBtn.click();
            """, msg_id=mid); mid += 1
            await asyncio.sleep(1.0)
            await capture_screenshot(ws, "patient_calendar_light_hi.png", mid); mid += 1

            # 9. Calendar Tab (Dark HI)
            print("\n9. Capturing My Calendar Tab (Dark HI)...")
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'dark')", msg_id=mid); mid += 1
            await asyncio.sleep(0.5)
            await capture_screenshot(ws, "patient_calendar_dark_hi.png", mid); mid += 1

            # 10. Day Sheet Inspection Drawer for Oct 29
            print("\n10. Capturing Day Sheet Inspection Drawer for Oct 29...")
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'light')", msg_id=mid); mid += 1
            await evaluate_js(ws, """
                const enBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'EN');
                if (enBtn) enBtn.click();
            """, msg_id=mid); mid += 1
            await asyncio.sleep(0.5)
            await evaluate_js(ws, """
                const day29Btn = document.querySelector('button[aria-label*="2026-10-29"]');
                if (day29Btn) day29Btn.click();
            """, msg_id=mid); mid += 1
            await asyncio.sleep(1.0)
            await capture_screenshot(ws, "patient_calendar_day_sheet.png", mid); mid += 1

        print("\nAll Phase 2 screenshots successfully captured in docs/screenshots/phase2/!")

    finally:
        chrome_proc.terminate()
        chrome_proc.wait()

if __name__ == "__main__":
    asyncio.run(main())
