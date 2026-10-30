"""
scripts/capture_phase4_screens.py

Captures Phase 4 screenshots (Light and Dark) of:
1. Nurse Desk Home (/nurse - My call list, 3 sidebar items, 4 KPI cards, call queue with countdown timers)
2. Doctor Desk Home (/doctor - Needs my decision, showing distinct content and accent differentiation)
3. Nurse Call Logging Modal (Phone/SMS selector, outcome, summary notes)
4. Nurse Task Complete Modal (Outcome codes: Reached and advised, Appointment set, No answer, etc.)
5. Nurse Propose Limit Modal (Target rule, proposed threshold, clinical justification for Dr. Sharma)
6. Simplified Shift Handoff (/nurse - 5-line cards per patient, illness tiers, contingency guidance, mark received)
7. Nurse Restricted View (Polite clinical governance notice when navigating to physician-only features)
8. Patient First Screen (/patient - Aarav Patel)
9. Family Helper First Screen (/family - Neha Patel)

Saves to: docs/screenshots/phase4/
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

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../docs/screenshots/phase4"))
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
    print("Capturing Phase 4 Nurse Desk & Multi-Role Screenshots...")

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
                "deviceScaleFactor": 1,
                "mobile": False
            }, msg_id=mid); mid += 1

            # ── 1. Setup Nurse Auth & Desk ──────────────────────────────────────────
            nurse_data = auth_data["nurse"]
            r_json = nurse_data["resp"]
            token = r_json["access_token"]
            user_obj = {
                "account_id": r_json["account_id"],
                "email": accounts["nurse"][0],
                "role": r_json["role"],
                "name": r_json.get("name"),
                "staff_id": r_json.get("staff_id"),
            }

            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/"}, msg_id=mid); mid += 1
            await asyncio.sleep(0.5)

            set_nurse_auth = f"""
            (() => {{
                localStorage.setItem('careloop_token', '{token}');
                localStorage.setItem('careloop_user', JSON.stringify({json.dumps(user_obj)}));
            }})()
            """
            await evaluate_js(ws, set_nurse_auth, mid); mid += 1

            # A. Nurse Desk Home (My call list)
            print("\nCapturing Nurse Desk Home (My call list)...")
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/nurse"}, msg_id=mid); mid += 1
            await asyncio.sleep(2.0)
            await set_theme(ws, "light", mid); mid += 1
            await capture_screenshot(ws, "nurse_home_calllist_light.png", mid); mid += 1
            await set_theme(ws, "dark", mid); mid += 1
            await capture_screenshot(ws, "nurse_home_calllist_dark.png", mid); mid += 1

            # B. Nurse Call Modal
            print("\nCapturing Nurse Call Logging Modal...")
            await set_theme(ws, "light", mid); mid += 1
            open_call_modal = """
            (() => {
                const buttons = Array.from(document.querySelectorAll('button'));
                const callBtn = buttons.find(b => b.textContent && b.textContent.trim() === 'Call');
                if (callBtn) callBtn.click();
            })()
            """
            await evaluate_js(ws, open_call_modal, mid); mid += 1
            await asyncio.sleep(1.0)
            await capture_screenshot(ws, "nurse_call_modal_light.png", mid); mid += 1
            await set_theme(ws, "dark", mid); mid += 1
            await capture_screenshot(ws, "nurse_call_modal_dark.png", mid); mid += 1

            # Close call modal
            close_modal = """
            (() => {
                const buttons = Array.from(document.querySelectorAll('button'));
                const cancelBtn = buttons.find(b => b.textContent && b.textContent.trim() === 'Cancel');
                if (cancelBtn) cancelBtn.click();
            })()
            """
            await evaluate_js(ws, close_modal, mid); mid += 1
            await asyncio.sleep(0.8)

            # C. Nurse Task Complete Modal
            print("\nCapturing Nurse Task Complete Modal...")
            await set_theme(ws, "light", mid); mid += 1
            open_task_modal = """
            (() => {
                const buttons = Array.from(document.querySelectorAll('button'));
                const compBtn = buttons.find(b => b.textContent && b.textContent.includes('Complete'));
                if (compBtn) compBtn.click();
            })()
            """
            await evaluate_js(ws, open_task_modal, mid); mid += 1
            await asyncio.sleep(1.0)
            await capture_screenshot(ws, "nurse_task_complete_modal_light.png", mid); mid += 1
            await set_theme(ws, "dark", mid); mid += 1
            await capture_screenshot(ws, "nurse_task_complete_modal_dark.png", mid); mid += 1

            # Close task modal
            await evaluate_js(ws, close_modal, mid); mid += 1
            await asyncio.sleep(0.8)

            # D. Nurse Propose Limit Modal
            print("\nCapturing Nurse Propose Limit Modal...")
            await set_theme(ws, "light", mid); mid += 1
            open_limit_modal = """
            (() => {
                const buttons = Array.from(document.querySelectorAll('button'));
                const propBtn = buttons.find(b => b.textContent && b.textContent.includes('Propose limit'));
                if (propBtn) propBtn.click();
            })()
            """
            await evaluate_js(ws, open_limit_modal, mid); mid += 1
            await asyncio.sleep(1.2)
            await capture_screenshot(ws, "nurse_propose_limit_modal_light.png", mid); mid += 1
            await set_theme(ws, "dark", mid); mid += 1
            await capture_screenshot(ws, "nurse_propose_limit_modal_dark.png", mid); mid += 1

            # Close limit modal
            await evaluate_js(ws, close_modal, mid); mid += 1
            await asyncio.sleep(0.8)

            # E. Shift Handoff (Simplified 5-line cards)
            print("\nCapturing Simplified Shift Handoff...")
            click_handoff = """
            (() => {
                const buttons = Array.from(document.querySelectorAll('button'));
                const btn = buttons.find(b => b.textContent && b.textContent.includes('Shift handoff'));
                if (btn) btn.click();
            })()
            """
            await evaluate_js(ws, click_handoff, mid); mid += 1
            await asyncio.sleep(1.5)
            await set_theme(ws, "light", mid); mid += 1
            await capture_screenshot(ws, "nurse_handoff_simplified_light.png", mid); mid += 1
            await set_theme(ws, "dark", mid); mid += 1
            await capture_screenshot(ws, "nurse_handoff_simplified_dark.png", mid); mid += 1

            # F. Nurse Restricted View Notice
            print("\nCapturing Nurse Restricted Notice (Clinical Governance)...")
            trigger_restricted = """
            (() => {
                window.location.hash = '#audit';
                // Trigger navigation to audit tab
                const mainComp = window;
            })()
            """
            # Direct URL to /doctor while logged in as nurse
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/doctor"}, msg_id=mid); mid += 1
            await asyncio.sleep(1.5)
            await set_theme(ws, "light", mid); mid += 1
            await capture_screenshot(ws, "nurse_restricted_notice_light.png", mid); mid += 1
            await set_theme(ws, "dark", mid); mid += 1
            await capture_screenshot(ws, "nurse_restricted_notice_dark.png", mid); mid += 1

            # ── 2. Doctor Desk Home (Needs my decision) ─────────────────────────────
            print("\nCapturing Doctor Desk Home (for side-by-side comparison with Nurse Desk)...")
            doc_data = auth_data["doctor"]
            doc_token = doc_data["resp"]["access_token"]
            doc_user_obj = {
                "account_id": doc_data["resp"]["account_id"],
                "email": accounts["doctor"][0],
                "role": doc_data["resp"]["role"],
                "name": doc_data["resp"].get("name"),
                "staff_id": doc_data["resp"].get("staff_id"),
            }
            set_doc_auth = f"""
            (() => {{
                localStorage.setItem('careloop_token', '{doc_token}');
                localStorage.setItem('careloop_user', JSON.stringify({json.dumps(doc_user_obj)}));
            }})()
            """
            await evaluate_js(ws, set_doc_auth, mid); mid += 1
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/doctor"}, msg_id=mid); mid += 1
            await asyncio.sleep(1.8)
            await set_theme(ws, "light", mid); mid += 1
            await capture_screenshot(ws, "doctor_home_decision_light.png", mid); mid += 1
            await set_theme(ws, "dark", mid); mid += 1
            await capture_screenshot(ws, "doctor_home_decision_dark.png", mid); mid += 1

            # ── 3. Patient Recovery Portal ──────────────────────────────────────────
            print("\nCapturing Patient First Screen (Aarav Patel)...")
            pat_data = auth_data["patient"]
            pat_token = pat_data["resp"]["access_token"]
            pat_user_obj = {
                "account_id": pat_data["resp"]["account_id"],
                "email": accounts["patient"][0],
                "role": pat_data["resp"]["role"],
                "name": pat_data["resp"].get("name"),
                "patient_id": pat_data["resp"].get("patient_id"),
            }
            set_pat_auth = f"""
            (() => {{
                localStorage.setItem('careloop_token', '{pat_token}');
                localStorage.setItem('careloop_user', JSON.stringify({json.dumps(pat_user_obj)}));
            }})()
            """
            await evaluate_js(ws, set_pat_auth, mid); mid += 1
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/patient"}, msg_id=mid); mid += 1
            await asyncio.sleep(1.8)
            await set_theme(ws, "light", mid); mid += 1
            await capture_screenshot(ws, "patient_phase4_light.png", mid); mid += 1
            await set_theme(ws, "dark", mid); mid += 1
            await capture_screenshot(ws, "patient_phase4_dark.png", mid); mid += 1

            # ── 4. Family Helper View ───────────────────────────────────────────────
            print("\nCapturing Family Helper First Screen (Neha Patel)...")
            fam_data = auth_data["family"]
            fam_token = fam_data["resp"]["access_token"]
            fam_user_obj = {
                "account_id": fam_data["resp"]["account_id"],
                "email": accounts["family"][0],
                "role": fam_data["resp"]["role"],
                "name": fam_data["resp"].get("name"),
                "patient_id": fam_data["resp"].get("patient_id"),
            }
            set_fam_auth = f"""
            (() => {{
                localStorage.setItem('careloop_token', '{fam_token}');
                localStorage.setItem('careloop_user', JSON.stringify({json.dumps(fam_user_obj)}));
            }})()
            """
            await evaluate_js(ws, set_fam_auth, mid); mid += 1
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/family"}, msg_id=mid); mid += 1
            await asyncio.sleep(1.8)
            await set_theme(ws, "light", mid); mid += 1
            await capture_screenshot(ws, "family_phase4_light.png", mid); mid += 1
            await set_theme(ws, "dark", mid); mid += 1
            await capture_screenshot(ws, "family_phase4_dark.png", mid); mid += 1

            print("\nAll Phase 4 screenshots captured successfully!")

    finally:
        chrome_proc.terminate()
        chrome_proc.wait()


if __name__ == "__main__":
    asyncio.run(main())
