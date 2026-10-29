"""
scripts/capture_google_calendar_cdp.py
Captures CDP screenshots verifying the Google Calendar button and links in the Patient Portal.
"""
import os
import json
import base64
import subprocess
import asyncio
import tempfile
import requests
import websockets

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../docs/screenshots/google_calendar"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEBUG_PORT = 9238

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
        print(f"  ✓ Saved {filename} ({len(b64_data)} b64 bytes)")

async def evaluate_js(ws, expr, msg_id):
    return await send_cmd(ws, "Runtime.evaluate", {"expression": expr, "awaitPromise": True}, msg_id=msg_id)

async def main():
    print("Authenticating as Patient Aarav Patel...")
    pat_res = requests.post(
        "http://127.0.0.1:8000/auth/login",
        json={"email": "aarav.demo@example.test", "password": "Demo@12345"},
    ).json()
    pat_token = pat_res["access_token"]
    pat_user = json.dumps({
        "account_id": pat_res["account_id"],
        "email": "aarav.demo@example.test",
        "full_name": "Aarav Patel",
        "role": "Patient",
        "patient_id": pat_res["patient_id"],
    })

    print("Launching headless Chrome for Google Calendar CDP captures...")
    user_data_dir = tempfile.mkdtemp()
    proc = subprocess.Popen([
        CHROME_BIN,
        "--headless=new",
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={user_data_dir}",
        "--window-size=1440,960",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
    ])

    try:
        await asyncio.sleep(2.0)
        new_tab = requests.put(f"http://127.0.0.1:{DEBUG_PORT}/json/new").json()
        ws_url = new_tab.get("webSocketDebuggerUrl")

        async with websockets.connect(ws_url, max_size=25*1024*1024) as ws:
            mid = 1
            await send_cmd(ws, "Page.enable", msg_id=mid); mid += 1
            await send_cmd(ws, "Runtime.enable", msg_id=mid); mid += 1

            # Navigate to patient portal
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/patient"}, msg_id=mid); mid += 1
            await asyncio.sleep(2.0)

            # Set localStorage tokens
            js_login = f"""
                localStorage.setItem('careloop_token', '{pat_token}');
                localStorage.setItem('careloop_user', JSON.stringify({pat_user}));
                localStorage.setItem('careloop_theme', 'light');
                window.location.reload();
            """
            await evaluate_js(ws, js_login, mid); mid += 1
            await asyncio.sleep(2.5)

            # 1. Capture Recovery Overview showing KPI Card with Google Calendar Button
            print("1. Capturing Recovery Overview with Google Calendar button...")
            await capture_screenshot(ws, "google_calendar_recovery_kpi.png", mid); mid += 1

            # 2. Scroll to Recovery Checklist
            print("2. Scrolling to Recovery Checklist...")
            await evaluate_js(ws, "window.scrollTo({ top: 900, behavior: 'instant' });", mid); mid += 1
            await asyncio.sleep(1.0)
            await capture_screenshot(ws, "google_calendar_recovery_checklist.png", mid); mid += 1

            # 3. Navigate to Calendar Tab
            print("3. Navigating to Calendar Tab...")
            js_calendar_tab = """
                const calBtn = Array.from(document.querySelectorAll('button, a, div[role="button"]')).find(b => b.innerText && b.innerText.toLowerCase().includes('calendar'));
                if (calBtn) calBtn.click();
            """
            await evaluate_js(ws, js_calendar_tab, mid); mid += 1
            await asyncio.sleep(2.0)

            print("4. Capturing Calendar Tab view with Google Calendar links...")
            await capture_screenshot(ws, "google_calendar_tab_view.png", mid); mid += 1

            # 4. Toggle Dark Mode
            print("5. Toggling Dark Mode...")
            js_dark_mode = """
                const themeBtn = document.querySelector('button[title*="theme" i], button[aria-label*="theme" i]') || Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('Dark') || b.innerText.includes('🌙') || b.innerText.includes('☀️'));
                if (themeBtn) themeBtn.click();
            """
            await evaluate_js(ws, js_dark_mode, mid); mid += 1
            await asyncio.sleep(1.5)

            print("6. Capturing Calendar Tab in Dark Mode...")
            await capture_screenshot(ws, "google_calendar_tab_dark.png", mid); mid += 1

            print("All Google Calendar CDP captures completed successfully!")

    finally:
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    asyncio.run(main())
