"""
scripts/capture_phase5_screens.py

Captures Phase 5 screenshots (Light and Dark) of:
1. Patient Home (/patient - Aarav Patel, Post-CABG Day 3, Next dose, Vitals 74 bpm, Data-check note, Family sharing switch)
2. Patient Medicines - Today's Doses (/patient - Grouped schedule, Taken/Skip status pills)
3. Patient Medicines - Calendar (/patient - Month grid & day detail)
4. Patient Daily Check-in (/patient - Pain scale 0-10, symptom chips, emergency keyword notice)
5. Patient Ask My Papers (/patient - Grounded Q&A, source chips, dose refusal, ask care team)
6. Family Today (/family - Neha Patel, calm 'What you may need to do', status-only doses, 'I helped Aarav take it')
7. Family Calendar (/family - 7-day dose history strip + appointments with .ics download)
8. Family Contacts (/family - Call 112, care team phone numbers, emergency guidance)
9. Family Sharing Blocked (/family - 'Aarav has turned sharing off' state when consent revoked)
10. All four logins first screens comparison (Doctor, Nurse, Patient, Family)

Saves to: docs/screenshots/phase5/
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

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../docs/screenshots/phase5"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEBUG_PORT = 9242


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
        const btn = document.querySelector('button[aria-label="Toggle theme"]');
        if (btn) btn.click();
    }})()
    """
    await evaluate_js(ws, expr, mid)
    await asyncio.sleep(0.5)


async def main():
    print("Capturing Phase 5 Patient App & Family Helper Screenshots...")

    # Authenticate all 4 logins
    accounts = {
        "nurse": ("priya.demo@example.test", "Demo@12345", "/nurse"),
        "doctor": ("ananya.demo@example.test", "Demo@12345", "/doctor"),
        "patient": ("aarav.demo@example.test", "Demo@12345", "/patient"),
        "family": ("caregiver1.demo@example.test", "Demo@12345", "/family"),
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
                "deviceScaleFactor": 2,
                "mobile": False,
            }, msg_id=mid); mid += 1

            # Helper to login and navigate
            async def navigate_as(role):
                nonlocal mid
                r_json = auth_data[role]["resp"]
                token = r_json["access_token"]
                user_obj = {
                    "account_id": r_json["account_id"],
                    "email": accounts[role][0],
                    "role": r_json["role"],
                    "name": r_json.get("name"),
                    "staff_id": r_json.get("staff_id"),
                    "patient_id": r_json.get("patient_id"),
                    "caregiver_id": r_json.get("caregiver_id"),
                }

                await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/"}, msg_id=mid); mid += 1
                await asyncio.sleep(0.5)

                set_auth_script = f"""
                (() => {{
                    localStorage.setItem('careloop_token', '{token}');
                    localStorage.setItem('careloop_user', JSON.stringify({json.dumps(user_obj)}));
                }})()
                """
                await evaluate_js(ws, set_auth_script, mid); mid += 1

                target_url = f"http://localhost:3000{auth_data[role]['route']}"
                await send_cmd(ws, "Page.navigate", {"url": target_url}, msg_id=mid); mid += 1
                await asyncio.sleep(2.0)

            # ── 1. PATIENT PORTAL SCREENS ──────────────────────────────────────
            print("\nCapturing Patient App screens...")
            await navigate_as("patient")

            # 1a. Patient Home (Light & Dark)
            for theme in ["light", "dark"]:
                await set_theme(ws, theme, mid); mid += 1
                await capture_screenshot(ws, f"patient_home_{theme}.png", mid); mid += 1

            # 1b. Patient Medicines - Today's Doses Tab
            click_meds_js = """
            (() => {
                const btns = Array.from(document.querySelectorAll('aside button'));
                const medsBtn = btns.find(b => b.textContent && (b.textContent.includes('Medicines') || b.textContent.includes('दवाइयाँ')));
                if (medsBtn) medsBtn.click();
            })()
            """
            await evaluate_js(ws, click_meds_js, mid); mid += 1
            await asyncio.sleep(1.0)

            for theme in ["light", "dark"]:
                await set_theme(ws, theme, mid); mid += 1
                await capture_screenshot(ws, f"patient_medicines_doses_{theme}.png", mid); mid += 1

            # 1c. Patient Medicines - Calendar Tab
            click_cal_subtab_js = """
            (() => {
                const btns = Array.from(document.querySelectorAll('button'));
                const calBtn = btns.find(b => b.textContent && b.textContent.includes('Calendar & Appointments'));
                if (calBtn) calBtn.click();
            })()
            """
            await evaluate_js(ws, click_cal_subtab_js, mid); mid += 1
            await asyncio.sleep(1.0)

            for theme in ["light", "dark"]:
                await set_theme(ws, theme, mid); mid += 1
                await capture_screenshot(ws, f"patient_medicines_calendar_{theme}.png", mid); mid += 1

            # 1d. Patient Daily Check-in
            click_checkin_js = """
            (() => {
                const btns = Array.from(document.querySelectorAll('aside button'));
                const cBtn = btns.find(b => b.textContent && (b.textContent.includes('Daily check-in') || b.textContent.includes('दैनिक चेक-इन')));
                if (cBtn) cBtn.click();
            })()
            """
            await evaluate_js(ws, click_checkin_js, mid); mid += 1
            await asyncio.sleep(1.0)

            # Trigger emergency keyword chip for screenshot illustration
            click_chest_pain_js = """
            (() => {
                const chips = Array.from(document.querySelectorAll('button'));
                const cpChip = chips.find(b => b.textContent && b.textContent.includes('Chest pain'));
                if (cpChip) cpChip.click();
            })()
            """
            await evaluate_js(ws, click_chest_pain_js, mid); mid += 1
            await asyncio.sleep(0.5)

            for theme in ["light", "dark"]:
                await set_theme(ws, theme, mid); mid += 1
                await capture_screenshot(ws, f"patient_checkin_{theme}.png", mid); mid += 1

            # 1e. Patient Ask My Papers (Chat)
            click_chat_js = """
            (() => {
                const btns = Array.from(document.querySelectorAll('aside button'));
                const chatBtn = btns.find(b => b.textContent && (b.textContent.includes('Ask my papers') || b.textContent.includes('मेरे कागजात')));
                if (chatBtn) chatBtn.click();
            })()
            """
            await evaluate_js(ws, click_chat_js, mid); mid += 1
            await asyncio.sleep(1.5)

            for theme in ["light", "dark"]:
                await set_theme(ws, theme, mid); mid += 1
                await capture_screenshot(ws, f"patient_ask_papers_{theme}.png", mid); mid += 1

            # ── 2. FAMILY HELPER PORTAL SCREENS ─────────────────────────────────
            print("\nCapturing Family Helper screens...")
            await navigate_as("family")

            # 2a. Family Today (Light & Dark)
            for theme in ["light", "dark"]:
                await set_theme(ws, theme, mid); mid += 1
                await capture_screenshot(ws, f"family_today_{theme}.png", mid); mid += 1

            # 2b. Family Calendar (with 7-Day Dose Strip)
            click_f_cal_js = """
            (() => {
                const btns = Array.from(document.querySelectorAll('aside button'));
                const calBtn = btns.find(b => b.textContent && (b.textContent.includes('Calendar') || b.textContent.includes('कैलेंडर')));
                if (calBtn) calBtn.click();
            })()
            """
            await evaluate_js(ws, click_f_cal_js, mid); mid += 1
            await asyncio.sleep(1.0)

            for theme in ["light", "dark"]:
                await set_theme(ws, theme, mid); mid += 1
                await capture_screenshot(ws, f"family_calendar_{theme}.png", mid); mid += 1

            # 2c. Family Contacts
            click_f_contacts_js = """
            (() => {
                const btns = Array.from(document.querySelectorAll('aside button'));
                const conBtn = btns.find(b => b.textContent && (b.textContent.includes('Contacts') || b.textContent.includes('संपर्क')));
                if (conBtn) conBtn.click();
            })()
            """
            await evaluate_js(ws, click_f_contacts_js, mid); mid += 1
            await asyncio.sleep(1.0)

            for theme in ["light", "dark"]:
                await set_theme(ws, theme, mid); mid += 1
                await capture_screenshot(ws, f"family_contacts_{theme}.png", mid); mid += 1

            # 2d. Family Sharing Blocked (Revoked Consent State)
            print("\nCapturing Family Sharing Off state...")
            p_tok = auth_data["patient"]["resp"]["access_token"]
            requests.post("http://127.0.0.1:8000/patient/me/sharing", json={"enabled": False}, headers={"Authorization": f"Bearer {p_tok}"})

            # Reload family portal
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/family"}, msg_id=mid); mid += 1
            await asyncio.sleep(2.0)

            for theme in ["light", "dark"]:
                await set_theme(ws, theme, mid); mid += 1
                await capture_screenshot(ws, f"family_sharing_off_{theme}.png", mid); mid += 1

            # Restore sharing
            requests.post("http://127.0.0.1:8000/patient/me/sharing", json={"enabled": True}, headers={"Authorization": f"Bearer {p_tok}"})

            # ── 3. FOUR ROLES FIRST SCREENS COMPARISON ─────────────────────────
            print("\nCapturing All Four Logins First Screen Comparison...")
            for role in ["doctor", "nurse", "patient", "family"]:
                await navigate_as(role)
                for theme in ["light", "dark"]:
                    await set_theme(ws, theme, mid); mid += 1
                    await capture_screenshot(ws, f"{role}_first_screen_{theme}.png", mid); mid += 1

        print("\n✅ All Phase 5 screenshots captured successfully in docs/screenshots/phase5/!")

    finally:
        chrome_proc.terminate()
        try:
            chrome_proc.wait(timeout=3)
        except Exception:
            chrome_proc.kill()


if __name__ == "__main__":
    asyncio.run(main())
