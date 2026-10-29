"""
scripts/capture_phase1_baseline.py

Captures Phase 1 baseline screenshots (Light and Dark) of:
1. Landing Page (/)
2. Login Page (/login)
3. First Screen of Doctor (Dr. Ananya Sharma) (/staff)
4. First Screen of Nurse (Priya Nair) (/staff)
5. First Screen of Patient (Aarav Patel) (/patient)
6. First Screen of Family Helper (Caregiver Neha Patel) (/patient)

Saves to: docs/screenshots/phase1_baseline/
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

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../docs/screenshots/phase1_baseline"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEBUG_PORT = 9229

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

async def set_theme(ws, theme, mid):
    expr = f"""
    (() => {{
        localStorage.setItem('careloop_theme', '{theme}');
        document.documentElement.setAttribute('data-theme', '{theme}');
    }})()
    """
    await evaluate_js(ws, expr, mid)
    await asyncio.sleep(0.5)

async def main():
    print("Capturing Phase 1 Baseline Screenshots...")

    # Fetch login tokens
    accounts = {
        "doctor": ("ananya.demo@example.test", "Demo@12345", "/staff"),
        "nurse": ("priya.demo@example.test", "Demo@12345", "/staff"),
        "patient": ("aarav.demo@example.test", "Demo@12345", "/patient"),
        "family": ("caregiver1.demo@example.test", "Demo@12345", "/patient"),
    }
    
    auth_data = {}
    for role, (email, pw, route) in accounts.items():
        resp = requests.post("http://127.0.0.1:8000/auth/login", json={"email": email, "password": pw})
        if resp.status_code == 200:
            auth_data[role] = {
                "resp": resp.json(),
                "route": route,
            }
        else:
            print(f"Failed to authenticate {role}: {resp.status_code}")
            return

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
        tab_info = requests.put(f"http://127.0.0.1:{DEBUG_PORT}/json/new").json()
        ws_url = tab_info["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url, max_size=25 * 1024 * 1024) as ws:
            mid = 100
            await send_cmd(ws, "Page.enable", msg_id=mid); mid += 1
            await send_cmd(ws, "DOM.enable", msg_id=mid); mid += 1
            await send_cmd(ws, "Emulation.setDeviceMetricsOverride", {
                "width": 1440,
                "height": 900,
                "deviceScaleFactor": 1,
                "mobile": False
            }, msg_id=mid); mid += 1

            # 1. Landing Page
            print("\n1. Landing Page...")
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/"}, msg_id=mid); mid += 1
            await asyncio.sleep(1.5)
            await set_theme(ws, "light", mid); mid += 1
            await capture_screenshot(ws, "landing_light.png", mid); mid += 1

            await set_theme(ws, "dark", mid); mid += 1
            await capture_screenshot(ws, "landing_dark.png", mid); mid += 1

            # 2. Login Page
            print("\n2. Login Page...")
            # clear localStorage auth
            await evaluate_js(ws, "(() => { localStorage.clear(); })()", mid); mid += 1
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/login"}, msg_id=mid); mid += 1
            await asyncio.sleep(1.5)
            await set_theme(ws, "light", mid); mid += 1
            await capture_screenshot(ws, "login_light.png", mid); mid += 1

            await set_theme(ws, "dark", mid); mid += 1
            await capture_screenshot(ws, "login_dark.png", mid); mid += 1

            # Helper for role screens
            for role_name in ["doctor", "nurse", "patient", "family"]:
                print(f"\n3. {role_name.capitalize()} First Screen...")
                dat = auth_data[role_name]
                r_json = dat["resp"]
                user_obj = {
                    "account_id": r_json["account_id"],
                    "email": accounts[role_name][0],
                    "role": r_json["role"],
                    "name": r_json.get("name"),
                    "patient_id": r_json.get("patient_id"),
                    "caregiver_id": r_json.get("caregiver_id"),
                    "staff_id": r_json.get("staff_id"),
                }
                token = r_json["access_token"]
                route = dat["route"]

                # Navigate to blank first, set auth in localStorage, then navigate to route
                await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/"}, msg_id=mid); mid += 1
                await asyncio.sleep(0.5)

                set_auth_expr = f"""
                (() => {{
                    localStorage.setItem('careloop_token', '{token}');
                    localStorage.setItem('careloop_user', JSON.stringify({json.dumps(user_obj)}));
                }})()
                """
                await evaluate_js(ws, set_auth_expr, mid); mid += 1

                # Navigate to target route
                await send_cmd(ws, "Page.navigate", {"url": f"http://localhost:3000{route}"}, msg_id=mid); mid += 1
                await asyncio.sleep(2.0)

                # Light mode
                await set_theme(ws, "light", mid); mid += 1
                await capture_screenshot(ws, f"{role_name}_first_screen_light.png", mid); mid += 1

                # Dark mode
                await set_theme(ws, "dark", mid); mid += 1
                await capture_screenshot(ws, f"{role_name}_first_screen_dark.png", mid); mid += 1

        print("\nAll baseline screenshots captured successfully!")
    finally:
        chrome_proc.terminate()
        chrome_proc.wait()

if __name__ == "__main__":
    asyncio.run(main())
