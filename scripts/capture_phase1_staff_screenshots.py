"""
scripts/capture_phase1_staff_screenshots.py

Captures high-resolution CDP screenshots for Phase 1 verification:
- Grouped Worklist (Light & Dark mode)
- Expanded Patient Flags & Attention Score breakdown
- Flag Detail Drawer (Clinical Why, Evidence & Quality, Escalation Ladder, History)
- Filter & Search states

Output saved to docs/screenshots/phase1_staff/
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

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../docs/screenshots/phase1_staff"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEBUG_PORT = 9232

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
    print("Fetching auth token for Dr. Ananya Sharma...")
    doc_res = requests.post("http://127.0.0.1:8000/auth/login", json={"email": "ananya.demo@example.test", "password": "Demo@12345"}).json()
    doc_token = doc_res["access_token"]
    doc_user = json.dumps({
        "account_id": doc_res["account_id"],
        "email": "ananya.demo@example.test",
        "role": "Doctor",
        "name": "Dr. Ananya Sharma",
        "staff_id": doc_res["staff_id"],
    })

    tmp_dir = tempfile.mkdtemp()
    cmd = [
        CHROME_BIN,
        "--headless=new",
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={tmp_dir}",
        "--window-size=1440,960",
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
                "width": 1440,
                "height": 960,
                "deviceScaleFactor": 1,
                "mobile": False,
            }, msg_id=mid); mid += 1

            # Navigate to staff portal with doctor credentials injected
            print("\nNavigating to Staff Portal (Grouped Worklist)...")
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/staff"}, msg_id=mid); mid += 1
            await asyncio.sleep(1.0)
            await evaluate_js(ws, f"""
                localStorage.setItem('careloop_token', '{doc_token}');
                localStorage.setItem('careloop_user', '{doc_user}');
                localStorage.setItem('careloop_role', 'Doctor');
                localStorage.setItem('careloop_theme', 'light');
                document.documentElement.setAttribute('data-theme', 'light');
                window.location.reload();
            """, mid); mid += 1
            await asyncio.sleep(2.5)

            # 1. Grouped Worklist (Light)
            print("Capturing 01_worklist_grouped_light.png...")
            await capture_screenshot(ws, "01_worklist_grouped_light.png", mid); mid += 1

            # 2. Open First Flag Detail Drawer
            print("Opening Flag Detail Drawer...")
            await evaluate_js(ws, """
                const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Detail Drawer') || b.textContent.includes('Resolve Flag'));
                if (btn) btn.click();
            """, mid); mid += 1
            await asyncio.sleep(1.5)
            print("Capturing 02_flag_drawer_overview_light.png...")
            await capture_screenshot(ws, "02_flag_drawer_overview_light.png", mid); mid += 1

            # 3. Evidence Tab in Drawer
            print("Switching to Evidence & Quality Tab...")
            await evaluate_js(ws, """
                const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Evidence & Quality'));
                if (btn) btn.click();
            """, mid); mid += 1
            await asyncio.sleep(1.0)
            print("Capturing 03_flag_drawer_evidence_light.png...")
            await capture_screenshot(ws, "03_flag_drawer_evidence_light.png", mid); mid += 1

            # 4. Escalation Ladder Tab in Drawer
            print("Switching to Escalation Ladder Tab...")
            await evaluate_js(ws, """
                const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Escalation Ladder'));
                if (btn) btn.click();
            """, mid); mid += 1
            await asyncio.sleep(1.0)
            print("Capturing 04_flag_drawer_ladder_light.png...")
            await capture_screenshot(ws, "04_flag_drawer_ladder_light.png", mid); mid += 1

            # Close drawer
            print("Closing Drawer...")
            await evaluate_js(ws, """
                const closeBtn = document.querySelector('button[aria-label="Close drawer"]');
                if (closeBtn) closeBtn.click();
            """, mid); mid += 1
            await asyncio.sleep(1.0)

            # 5. Search Filter in Action
            print("Applying search filter ('Aarav')...")
            await evaluate_js(ws, """
                const search = document.querySelector('input[placeholder*="Search patient"]');
                if (search) {
                    search.value = 'Aarav';
                    search.dispatchEvent(new Event('input', { bubbles: true }));
                }
            """, mid); mid += 1
            await asyncio.sleep(1.2)
            print("Capturing 05_worklist_search_filter_light.png...")
            await capture_screenshot(ws, "05_worklist_search_filter_light.png", mid); mid += 1

            # Reset search
            await evaluate_js(ws, """
                const search = document.querySelector('input[placeholder*="Search patient"]');
                if (search) {
                    search.value = '';
                    search.dispatchEvent(new Event('input', { bubbles: true }));
                }
            """, mid); mid += 1
            await asyncio.sleep(1.0)

            # 6. Grouped Worklist (Dark Mode)
            print("Switching to Dark Mode...")
            await evaluate_js(ws, """
                document.documentElement.setAttribute('data-theme', 'dark');
                localStorage.setItem('careloop_theme', 'dark');
            """, mid); mid += 1
            await asyncio.sleep(1.5)
            print("Capturing 06_worklist_grouped_dark.png...")
            await capture_screenshot(ws, "06_worklist_grouped_dark.png", mid); mid += 1

        print("\nAll Phase 1 screenshots successfully captured and saved to docs/screenshots/phase1_staff/!")
    finally:
        proc.terminate()
        proc.wait()

if __name__ == '__main__':
    asyncio.run(main())
