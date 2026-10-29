"""
scripts/capture_phase3_screenshots.py

Captures Phase 3 upgraded patient portal screens with full resolution:
- patient_checkin_form_light_en.png
- patient_checkin_form_dark_en.png
- patient_checkin_form_light_hi.png
- patient_checkin_chips_selected.png
- patient_checkin_confirmation_emergency.png
- patient_checkin_history_expanded.png
- landing_light_en_check.png (visual lock verification)
- login_light_en_check.png (visual lock verification)

Saved to docs/screenshots/phase3/
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

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../docs/screenshots/phase3"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEBUG_PORT = 9230

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
    await asyncio.sleep(1.2)
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
        mid += 1
        res = await evaluate_js(ws, f"Boolean(document.querySelector('{selector}'))", mid)
        if res.get("result", {}).get("value") is True:
            return mid
        await asyncio.sleep(0.3)
    return mid

async def main():
    # 1. Login via backend API to get fresh tokens
    print("1. Authenticating as Aarav via API...")
    pat_res = requests.post(
        "http://127.0.0.1:8000/auth/login",
        json={"email": "aarav.demo@example.test", "password": "Demo@12345"}
    ).json()
    pat_token = pat_res["access_token"]
    pat_user = json.dumps({"account_id": pat_res["account_id"], "email": "aarav.demo@example.test", "role": "Patient", "name": "Aarav Patel", "patient_id": pat_res["patient_id"]})

    temp_profile = tempfile.mkdtemp(prefix="chrome_cdp_p3_")
    chrome_proc = subprocess.Popen([
        CHROME_BIN,
        "--headless=new",
        "--disable-gpu",
        f"--user-data-dir={temp_profile}",
        f"--remote-debugging-port={DEBUG_PORT}",
        "--window-size=1280,1000",
        "--hide-scrollbars",
        "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    time.sleep(2.0)

    try:
        tab_info = requests.put(f"http://127.0.0.1:{DEBUG_PORT}/json/new").json()
        ws_url = tab_info["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url, max_size=25 * 1024 * 1024) as ws:
            mid = 500
            await send_cmd(ws, "Page.enable", msg_id=mid); mid += 1
            await send_cmd(ws, "DOM.enable", msg_id=mid); mid += 1
            await send_cmd(ws, "Emulation.setDeviceMetricsOverride", {
                "width": 1280,
                "height": 1000,
                "deviceScaleFactor": 1,
                "mobile": False
            }, msg_id=mid); mid += 1

            # A. Verification: Landing Page
            print("\nA. Capturing Landing Page verification...")
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/"}, msg_id=mid); mid += 1
            mid = await wait_for_selector(ws, "nav", mid)
            await asyncio.sleep(1.5)
            await capture_screenshot(ws, "landing_light_en_check.png", mid); mid += 1

            # B. Verification: Login Page
            print("\nB. Capturing Login Page verification...")
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/login"}, msg_id=mid); mid += 1
            mid = await wait_for_selector(ws, "form", mid)
            await asyncio.sleep(1.5)
            await capture_screenshot(ws, "login_light_en_check.png", mid); mid += 1

            # Set localStorage for patient session
            set_pat_storage = f"""
            localStorage.setItem('careloop_token', '{pat_token}');
            localStorage.setItem('careloop_user', JSON.stringify({pat_user}));
            """
            await evaluate_js(ws, set_pat_storage, msg_id=mid); mid += 1

            # C. Navigate to Patient Portal
            print("\nC. Navigating to Patient Portal...")
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/patient"}, msg_id=mid); mid += 1
            mid = await wait_for_selector(ws, "header", mid)
            await asyncio.sleep(2.0)

            # Switch to Check-in tab
            print("Switching to Check-in tab...")
            await evaluate_js(ws, """
                (() => {
                    const buttons = Array.from(document.querySelectorAll('aside button'));
                    const chkBtn = buttons.find(b => b.textContent.includes('Daily check-in') || b.textContent.includes('चेक-इन'));
                    if (chkBtn) chkBtn.click();
                })()
            """, mid); mid += 1
            await asyncio.sleep(1.5)

            # 1. Check-in Form Light EN
            print("1. Capturing Check-in Form Light EN...")
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'light')", msg_id=mid); mid += 1
            await evaluate_js(ws, "(() => { const btns = Array.from(document.querySelectorAll('button')); const b = btns.find(x => x.textContent.trim() === 'EN'); if (b) b.click(); })()", msg_id=mid); mid += 1
            await asyncio.sleep(0.8)
            await capture_screenshot(ws, "patient_checkin_form_light_en.png", mid); mid += 1

            # 2. Check-in Form Dark EN
            print("2. Capturing Check-in Form Dark EN...")
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'dark')", msg_id=mid); mid += 1
            await asyncio.sleep(0.8)
            await capture_screenshot(ws, "patient_checkin_form_dark_en.png", mid); mid += 1

            # 3. Check-in Form Light HI
            print("3. Capturing Check-in Form Light HI...")
            await evaluate_js(ws, "document.documentElement.setAttribute('data-theme', 'light')", msg_id=mid); mid += 1
            await evaluate_js(ws, "(() => { const btns = Array.from(document.querySelectorAll('button')); const b = btns.find(x => x.textContent.trim() === 'HI'); if (b) b.click(); })()", msg_id=mid); mid += 1
            await asyncio.sleep(0.8)
            await capture_screenshot(ws, "patient_checkin_form_light_hi.png", mid); mid += 1

            # Switch back to English
            await evaluate_js(ws, "(() => { const btns = Array.from(document.querySelectorAll('button')); const b = btns.find(x => x.textContent.trim() === 'EN'); if (b) b.click(); })()", msg_id=mid); mid += 1
            await asyncio.sleep(0.5)

            # 4. Chips and Pain Score 3 Selected
            print("4. Selecting Pain Score 3, Symptoms, Location, Trend...")
            await evaluate_js(ws, """
                (() => {
                    // Tap pain button 3
                    const painBtns = Array.from(document.querySelectorAll('button[aria-label^="Pain score"]'));
                    const btn3 = painBtns.find(b => b.textContent.trim() === '3');
                    if (btn3) btn3.click();

                    // Tap symptom chips
                    const chipBtns = Array.from(document.querySelectorAll('button'));
                    const tiredChip = chipBtns.find(b => b.textContent.includes('Tired'));
                    if (tiredChip) tiredChip.click();

                    const woundChip = chipBtns.find(b => b.textContent.includes('Wound pain'));
                    if (woundChip) woundChip.click();

                    const siteWound = chipBtns.find(b => b.textContent.includes('Wound site'));
                    if (siteWound) siteWound.click();

                    const trendSame = chipBtns.find(b => b.textContent.includes('Same'));
                    if (trendSame) trendSame.click();

                    const ta = document.querySelector('textarea');
                    if (ta) {
                        ta.value = 'Walking around the living room felt okay. Dressing is dry and intact.';
                        ta.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                })()
            """, mid); mid += 1
            await asyncio.sleep(0.8)
            await capture_screenshot(ws, "patient_checkin_chips_selected.png", mid); mid += 1

            # 5. Expand 14-day history item
            print("5. Expanding History item...")
            await evaluate_js(ws, """
                (() => {
                    const detailsBtns = Array.from(document.querySelectorAll('span')).filter(s => s.textContent.includes('Details') || s.textContent.includes('विवरण'));
                    if (detailsBtns.length > 0) detailsBtns[0].click();
                })()
            """, mid); mid += 1
            await asyncio.sleep(0.8)
            await capture_screenshot(ws, "patient_checkin_history_expanded.png", mid); mid += 1

            # 6. Submit Emergency Check-in
            print("6. Submitting Emergency checkin to display emergency guidance...")
            await evaluate_js(ws, """
                (() => {
                    // Select emergency chip
                    const chipBtns = Array.from(document.querySelectorAll('button'));
                    const chestChip = chipBtns.find(b => b.textContent.includes('Chest pain'));
                    if (chestChip) chestChip.click();

                    // Submit form
                    const sendBtn = chipBtns.find(b => b.textContent.includes('Send to my care team') || b.textContent.includes('केयर टीम को भेजें'));
                    if (sendBtn) sendBtn.click();
                })()
            """, mid); mid += 1
            await asyncio.sleep(2.5)
            await capture_screenshot(ws, "patient_checkin_confirmation_emergency.png", mid); mid += 1

            print("\n✓ All Phase 3 screenshots captured successfully in docs/screenshots/phase3/")

    finally:
        chrome_proc.terminate()
        chrome_proc.wait()

if __name__ == "__main__":
    asyncio.run(main())
