"""
scripts/capture_phase4_screenshots.py

Captures Phase 4 Grounded RAG & Assistant screenshots:
- chat_empty_starter_chips_light_en.png
- chat_answered_source_chips_light_en.png
- chat_source_drawer_light_en.png
- chat_refusal_ask_care_team_light_en.png
- chat_dark_en.png
- chat_answered_light_hi.png
- landing_light_en.png (verification)
- login_light_en.png (verification)

Saved to docs/screenshots/phase4/
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

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../docs/screenshots/phase4"))
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

async def main():
    print("Fetching auth tokens from backend...")
    pat_res = requests.post("http://127.0.0.1:8000/auth/login", json={"email": "aarav.demo@example.test", "password": "Demo@12345"}).json()
    pat_token = pat_res["access_token"]
    pat_user = json.dumps({"account_id": pat_res["account_id"], "email": "aarav.demo@example.test", "role": "Patient", "name": "Aarav Patel", "patient_id": pat_res["patient_id"]})

    tmp_dir = tempfile.mkdtemp()
    cmd = [
        CHROME_BIN,
        "--headless=new",
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={tmp_dir}",
        "--window-size=1280,900",
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
                "width": 1280,
                "height": 900,
                "deviceScaleFactor": 1,
                "mobile": False,
            }, msg_id=mid); mid += 1

            # ─── 1. Landing Page Verification ───
            print("\nCapturing Landing Page (Verification)...")
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/"}, msg_id=mid); mid += 1
            await asyncio.sleep(2.0)
            await capture_screenshot(ws, "landing_light_en.png", mid); mid += 1

            # ─── 2. Login Page Verification ───
            print("\nCapturing Login Page (Verification)...")
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/login"}, msg_id=mid); mid += 1
            await asyncio.sleep(2.0)
            await capture_screenshot(ws, "login_light_en.png", mid); mid += 1

            # ─── 3. Patient Portal Setup ───
            print("\nNavigating to Patient Portal...")
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/patient"}, msg_id=mid); mid += 1
            await asyncio.sleep(1.5)

            # Set Auth token
            await evaluate_js(ws, f"""
                localStorage.setItem('careloop_token', '{pat_token}');
                localStorage.setItem('careloop_user', '{pat_user}');
                localStorage.setItem('careloop_theme', 'light');
                document.documentElement.setAttribute('data-theme', 'light');
            """, mid); mid += 1

            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/patient"}, msg_id=mid); mid += 1
            await asyncio.sleep(2.5)

            # Navigate to Chat tab
            print("Switching to Chat tab...")
            await evaluate_js(ws, """
                const chatBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Chat') || b.textContent.includes('Assistant') || b.textContent.includes('चैट'));
                if (chatBtn) chatBtn.click();
            """, mid); mid += 1
            await asyncio.sleep(1.0)

            # Click New Chat to ensure clean starter chips state
            await evaluate_js(ws, """
                const newChatBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('New chat') || b.textContent.includes('नया संवाद'));
                if (newChatBtn) newChatBtn.click();
            """, mid); mid += 1
            await asyncio.sleep(1.0)

            # ─── 4. Empty State with Starter Chips ───
            print("Capturing Chat Empty State with 4 Starter Chips...")
            await capture_screenshot(ws, "chat_empty_starter_chips_light_en.png", mid); mid += 1

            # ─── 5. Ask Grounded Query (Click Starter Chip) ───
            print("Clicking 'When is my next visit?' starter chip...")
            await evaluate_js(ws, """
                const starter = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('When is my next visit?'));
                if (starter) starter.click();
            """, mid); mid += 1
            await asyncio.sleep(4.5)

            # Capture Answered state with source pills
            print("Capturing Chat Answered State with Grounded Source Chips...")
            await capture_screenshot(ws, "chat_answered_source_chips_light_en.png", mid); mid += 1

            # ─── 6. Open Source Inspection Modal Drawer ───
            print("Clicking Source Pill to open Inspection Drawer...")
            await evaluate_js(ws, """
                const sourcePill = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Appointments') || b.textContent.includes('Discharge summary'));
                if (sourcePill) sourcePill.click();
            """, mid); mid += 1
            await asyncio.sleep(1.5)

            print("Capturing Source Inspection Drawer...")
            await capture_screenshot(ws, "chat_source_drawer_light_en.png", mid); mid += 1

            # Close drawer
            await evaluate_js(ws, """
                const closeBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Close') || b.textContent.includes('बंद'));
                if (closeBtn) closeBtn.click();
            """, mid); mid += 1
            await asyncio.sleep(1.0)

            # ─── 7. Refusal Query & Ask Care Team ───
            print("Sending dose change question...")
            await evaluate_js(ws, """
                const input = document.querySelector('input[type="text"]');
                if (input) {
                    input.value = "Can I double my dose to get better faster?";
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                    const form = input.closest('form');
                    if (form) form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
                }
            """, mid); mid += 1
            await asyncio.sleep(3.5)

            print("Capturing Dose Refusal & Ask My Care Team Button...")
            await capture_screenshot(ws, "chat_refusal_ask_care_team_light_en.png", mid); mid += 1

            # ─── 8. Dark Mode ───
            print("Switching to Dark Mode...")
            await evaluate_js(ws, """
                const themeBtn = Array.from(document.querySelectorAll('button')).find(b => b.title && b.title.includes('dark') || b.getAttribute('aria-label')?.includes('theme'));
                if (themeBtn) themeBtn.click();
                document.documentElement.setAttribute('data-theme', 'dark');
            """, mid); mid += 1
            await asyncio.sleep(1.5)

            print("Capturing Chat Assistant in Dark Mode...")
            await capture_screenshot(ws, "chat_dark_en.png", mid); mid += 1

            # Reset back to light
            await evaluate_js(ws, """
                document.documentElement.setAttribute('data-theme', 'light');
            """, mid); mid += 1

            # ─── 9. Hindi Mode ───
            print("Switching to Hindi Mode...")
            await evaluate_js(ws, """
                const hiBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'HI' || b.textContent.trim() === 'हिन्दी');
                if (hiBtn) hiBtn.click();
            """, mid); mid += 1
            await asyncio.sleep(2.0)

            print("Capturing Chat Assistant in Hindi Mode...")
            await capture_screenshot(ws, "chat_answered_light_hi.png", mid); mid += 1

        print("\nAll Phase 4 screenshots successfully captured in docs/screenshots/phase4/!")

    finally:
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    asyncio.run(main())
