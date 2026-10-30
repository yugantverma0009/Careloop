"""
scripts/capture_phase6_screens.py

Captures Phase 6 screenshots (Light and Dark) of:
1. Landing Page Hero & Metrics (01_landing_page)
2. Landing Page Four Role Cards with pitches & visible logins (02_landing_four_roles)
3. Landing Page 5-Step 'How a day works' strip & safety cards (03_landing_how_a_day_works)
4. Patient Home initial state (04_patient_home_initial)
5. Presenter Controls dropdown open (05_presenter_controls_open)
6. Patient Home with live SpO2 91% urgent banner (06_patient_urgent_banner)
7. Family Today with 'The care team is checking on Aarav' & dose help (07_family_checking_on_aarav)
8. Nurse Call List with Aarav in Urgent tier (08_nurse_call_list_aarav_urgent)
9. Nurse Call List escalated to Dr. Sharma (09_nurse_escalated_to_doctor)
10. Doctor Desk 'Needs my decision' with Aarav escalation (10_doctor_needs_decision_aarav)
11. Doctor Flag Drawer with evidence ladder and approved limit (11_doctor_flag_drawer_evidence)
12. Doctor Audit Log showing complete event trace (12_doctor_audit_log_trace)
13. Family Helper view when Aarav turns sharing off (13_family_sharing_turned_off)

Saves to: docs/screenshots/phase6/
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

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../docs/screenshots/phase6"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEBUG_PORT = 9245


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
    print("Capturing Phase 6 Connected Demo & Landing Page Screenshots...")

    # 1. Reset demo to clean baseline
    requests.post("http://127.0.0.1:8000/demo/reset")
    time.sleep(1)

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
            auth_data[role] = {"resp": resp.json(), "route": route}
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

    time.sleep(2.0)

    try:
        tab_info = requests.put(f"http://127.0.0.1:{DEBUG_PORT}/json/new").json()
        ws_url = tab_info["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url, max_size=30 * 1024 * 1024) as ws:
            mid = 100
            await send_cmd(ws, "Page.enable", msg_id=mid); mid += 1
            await send_cmd(ws, "DOM.enable", msg_id=mid); mid += 1
            await send_cmd(ws, "Emulation.setDeviceMetricsOverride", {
                "width": 1440,
                "height": 900,
                "deviceScaleFactor": 2,
                "mobile": False,
            }, msg_id=mid); mid += 1

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

            # ── 1. LANDING PAGE HERO ───────────────────────────────────────────
            print("\nCapturing Landing Page Hero...")
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/"}, msg_id=mid); mid += 1
            await asyncio.sleep(2.0)
            for theme in ["light", "dark"]:
                await set_theme(ws, theme, mid); mid += 1
                await evaluate_js(ws, "window.scrollTo(0, 0);", mid); mid += 1
                await capture_screenshot(ws, f"01_landing_page_{theme}.png", mid); mid += 1

            # ── 2. LANDING FOUR ROLE CARDS ─────────────────────────────────────
            print("Capturing Landing Four Role Cards...")
            for theme in ["light", "dark"]:
                await set_theme(ws, theme, mid); mid += 1
                await evaluate_js(ws, "const el = document.getElementById('roles'); if (el) el.scrollIntoView();", mid); mid += 1
                await capture_screenshot(ws, f"02_landing_four_roles_{theme}.png", mid); mid += 1

            # ── 3. LANDING HOW A DAY WORKS (5 STEPS) ───────────────────────────
            print("Capturing Landing How A Day Works...")
            for theme in ["light", "dark"]:
                await set_theme(ws, theme, mid); mid += 1
                await evaluate_js(ws, "const el = document.getElementById('day-in-the-life'); if (el) el.scrollIntoView();", mid); mid += 1
                await capture_screenshot(ws, f"03_landing_how_a_day_works_{theme}.png", mid); mid += 1

            # ── 4. PATIENT HOME INITIAL STATE ──────────────────────────────────
            print("\nCapturing Patient Home Initial State...")
            await navigate_as("patient")
            for theme in ["light", "dark"]:
                await set_theme(ws, theme, mid); mid += 1
                await capture_screenshot(ws, f"04_patient_home_initial_{theme}.png", mid); mid += 1

            # ── 5. PRESENTER CONTROLS OPEN ────────────────────────────────────
            print("\nCapturing Presenter Controls Open on Staff Portal...")
            await navigate_as("doctor")
            for theme in ["light", "dark"]:
                await set_theme(ws, theme, mid); mid += 1
                await evaluate_js(ws, """
                (() => {
                    const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent && (b.textContent.includes('Dr. Ananya') || b.textContent.includes('Attending Physician')));
                    if (btn) btn.click();
                })()
                """, mid); mid += 1
                await asyncio.sleep(0.8)
                await capture_screenshot(ws, f"05_presenter_controls_open_{theme}.png", mid); mid += 1

            # ── TRIGGER LIVE EVENT (Aarav SpO2 91%) ───────────────────────────
            print("\n⚡ Triggering simulated event: Aarav Patel low SpO2 (91.0%)...")
            sim_res = requests.post("http://127.0.0.1:8000/demo/simulate-reading", json={
                "patient_id": 1,
                "device_id": "DEV-ESP32-001",
                "measurement_type": "SpO2",
                "value": 91.0,
                "unit": "%",
            })
            flag_id = sim_res.json().get("flag_id", 6)
            time.sleep(1.0)

            # ── 6. PATIENT URGENT BANNER ──────────────────────────────────────
            print("Capturing Patient Urgent Banner...")
            await navigate_as("patient")
            for theme in ["light", "dark"]:
                await set_theme(ws, theme, mid); mid += 1
                await capture_screenshot(ws, f"06_patient_urgent_banner_{theme}.png", mid); mid += 1

            # ── 7. FAMILY CHECKING ON AARAV ────────────────────────────────────
            print("Capturing Family Checking On Aarav Guidance...")
            await navigate_as("family")
            for theme in ["light", "dark"]:
                await set_theme(ws, theme, mid); mid += 1
                await capture_screenshot(ws, f"07_family_checking_on_aarav_{theme}.png", mid); mid += 1

            # ── 8. NURSE CALL LIST (Aarav in Urgent Tier) ──────────────────────
            print("Capturing Nurse Call List...")
            await navigate_as("nurse")
            for theme in ["light", "dark"]:
                await set_theme(ws, theme, mid); mid += 1
                await capture_screenshot(ws, f"08_nurse_call_list_aarav_urgent_{theme}.png", mid); mid += 1

            # Nurse logs call and escalates to Dr. Sharma
            nurse_headers = {"Authorization": f"Bearer {auth_data['nurse']['resp']['access_token']}"}
            requests.post("http://127.0.0.1:8000/staff/contacts/log", headers=nurse_headers, json={
                "patient_id": 1,
                "flag_id": flag_id,
                "channel": "Phone",
                "outcome": "Reached",
                "summary": "Reached Aarav by phone; instructed deep breathing; SpO2 recheck pending.",
            })
            requests.post(f"http://127.0.0.1:8000/staff/flags/{flag_id}/escalate", headers=nurse_headers, json={
                "note": "SpO2 91% on watch. Reached patient by phone. Patient instructed to sit upright; requesting physician review."
            })
            time.sleep(1.0)

            # ── 9. NURSE CALL LIST ESCALATED TO DOCTOR ─────────────────────────
            print("Capturing Nurse Call List Escalated...")
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/nurse"}, msg_id=mid); mid += 1
            await asyncio.sleep(2.0)
            for theme in ["light", "dark"]:
                await set_theme(ws, theme, mid); mid += 1
                await capture_screenshot(ws, f"09_nurse_escalated_to_doctor_{theme}.png", mid); mid += 1

            # ── 10. DOCTOR NEEDS DECISION AARAV ───────────────────────────────
            print("Capturing Doctor Needs Decision...")
            await navigate_as("doctor")
            for theme in ["light", "dark"]:
                await set_theme(ws, theme, mid); mid += 1
                await capture_screenshot(ws, f"10_doctor_needs_decision_aarav_{theme}.png", mid); mid += 1

            # ── 11. DOCTOR FLAG DRAWER EVIDENCE ────────────────────────────────
            print("Capturing Doctor Flag Drawer...")
            for theme in ["light", "dark"]:
                await set_theme(ws, theme, mid); mid += 1
                await evaluate_js(ws, """
                (() => {
                    const btns = Array.from(document.querySelectorAll('button'));
                    const decideBtn = btns.find(b => b.textContent && b.textContent.trim() === 'Decide');
                    if (decideBtn) decideBtn.click();
                })()
                """, mid); mid += 1
                await asyncio.sleep(1.2)
                await capture_screenshot(ws, f"11_doctor_flag_drawer_evidence_{theme}.png", mid); mid += 1

            # ── 12. DOCTOR AUDIT LOG TRACE ─────────────────────────────────────
            print("Capturing Doctor Audit Log Trace...")
            for theme in ["light", "dark"]:
                await set_theme(ws, theme, mid); mid += 1
                # Close drawer if open
                await evaluate_js(ws, """
                (() => {
                    const closeBtn = document.querySelector('button[aria-label="Close"]') || Array.from(document.querySelectorAll('button')).find(b => b.textContent === '✕');
                    if (closeBtn) closeBtn.click();
                })()
                """, mid); mid += 1
                await asyncio.sleep(0.5)
                # Click Audit log viewer
                await evaluate_js(ws, """
                (() => {
                    const btns = Array.from(document.querySelectorAll('aside button, nav button'));
                    const auditBtn = btns.find(b => b.textContent && b.textContent.includes('Audit log viewer'));
                    if (auditBtn) auditBtn.click();
                })()
                """, mid); mid += 1
                await asyncio.sleep(1.8)
                await capture_screenshot(ws, f"12_doctor_audit_log_trace_{theme}.png", mid); mid += 1

            # ── 13. FAMILY SHARING TURNED OFF ──────────────────────────────────
            print("\n🔒 Revoking Aarav family sharing consent...")
            p_tok = auth_data["patient"]["resp"]["access_token"]
            requests.post("http://127.0.0.1:8000/patient/me/sharing", json={"enabled": False}, headers={"Authorization": f"Bearer {p_tok}"})
            time.sleep(0.5)

            await navigate_as("family")
            for theme in ["light", "dark"]:
                await set_theme(ws, theme, mid); mid += 1
                await capture_screenshot(ws, f"13_family_sharing_turned_off_{theme}.png", mid); mid += 1

            # Clean restore
            requests.post("http://127.0.0.1:8000/patient/me/sharing", json={"enabled": True}, headers={"Authorization": f"Bearer {p_tok}"})
            requests.post("http://127.0.0.1:8000/demo/reset")
            print("\n🎉 Phase 6 screenshot capture complete!")

    finally:
        chrome_proc.terminate()
        try:
            chrome_proc.wait(timeout=3)
        except Exception:
            chrome_proc.kill()


if __name__ == "__main__":
    asyncio.run(main())
