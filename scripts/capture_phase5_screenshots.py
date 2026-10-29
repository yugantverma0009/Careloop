"""
scripts/capture_phase5_screenshots.py

Captures Phase 5 upgraded Staff Portal screens via Chrome DevTools Protocol:
1. operational_insights_light.png
2. operational_insights_dark.png
3. patient_rules_tab_with_pathways.png
4. pathway_template_modal_blank_thresholds.png
5. lace_context_card.png

Saved to docs/screenshots/phase5/
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

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../docs/screenshots/phase5"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEBUG_PORT = 9235

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
    else:
        print(f"  ✗ Warning: No data for {filename}")

async def evaluate_js(ws, expr, msg_id):
    return await send_cmd(ws, "Runtime.evaluate", {"expression": expr, "awaitPromise": True}, msg_id=msg_id)

async def main():
    print("Authenticating as Dr. Ananya Sharma...")
    doc_res = requests.post(
        "http://127.0.0.1:8000/auth/login",
        json={"email": "ananya.demo@example.test", "password": "Demo@12345"},
    ).json()
    doc_token = doc_res["access_token"]
    doc_user = json.dumps({
        "account_id": doc_res["account_id"],
        "email": "ananya.demo@example.test",
        "full_name": "Dr. Ananya Sharma",
        "role": "Doctor",
        "is_doctor": True,
        "staff_id": 1,
    })

    print("Launching headless Chrome for Phase 5 CDP captures...")
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

            print("1. Injecting Doctor auth session into Staff Portal...")
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/staff"}, msg_id=mid); mid += 1
            await asyncio.sleep(2.0)

            setup_script = f"""
                localStorage.setItem('careloop_token', '{doc_token}');
                localStorage.setItem('careloop_user', '{doc_user}');
                localStorage.setItem('careloop_theme', 'light');
                window.location.reload();
            """
            await evaluate_js(ws, setup_script, mid); mid += 1
            await asyncio.sleep(2.5)

            # 2. Navigate to Operational Insights
            print("2. Capturing Operational Insights (Light Mode)...")
            await evaluate_js(ws, """
                (() => {
                    const buttons = Array.from(document.querySelectorAll('button'));
                    const insightsBtn = buttons.find(b => b.innerText.includes('Operational insights'));
                    if (insightsBtn) insightsBtn.click();
                })()
            """, msg_id=mid); mid += 1
            await asyncio.sleep(2.0)
            await capture_screenshot(ws, "operational_insights_light.png", mid); mid += 1

            # 3. Operational Insights Dark Mode
            print("3. Capturing Operational Insights (Dark Mode)...")
            await evaluate_js(ws, """
                (() => {
                    document.documentElement.setAttribute('data-theme', 'dark');
                    localStorage.setItem('careloop_theme', 'dark');
                })()
            """, msg_id=mid); mid += 1
            await asyncio.sleep(1.0)
            await capture_screenshot(ws, "operational_insights_dark.png", mid); mid += 1

            # Reset back to light theme
            await evaluate_js(ws, """
                (() => {
                    document.documentElement.setAttribute('data-theme', 'light');
                    localStorage.setItem('careloop_theme', 'light');
                })()
            """, msg_id=mid); mid += 1
            await asyncio.sleep(0.5)

            # 4. Navigate to Patient Directory -> Patient 1 Overview
            print("4. Navigating to Patient 1 Chart...")
            await evaluate_js(ws, """
                (() => {
                    const buttons = Array.from(document.querySelectorAll('button'));
                    const patBtn = buttons.find(b => b.innerText.includes('Patient directory'));
                    if (patBtn) patBtn.click();
                })()
            """, msg_id=mid); mid += 1
            await asyncio.sleep(1.5)

            # Click Patient 1 to open chart
            await evaluate_js(ws, """
                (() => {
                    const viewButtons = Array.from(document.querySelectorAll('button')).filter(b => b.innerText.includes('View chart'));
                    if (viewButtons.length > 0) viewButtons[0].click();
                })()
            """, msg_id=mid); mid += 1
            await asyncio.sleep(2.0)

            # 5. Capture LACE Risk Context Card in Overview Tab
            print("5. Capturing LACE Context Card...")
            await evaluate_js(ws, """
                (() => {
                    const updateLace = document.getElementById('update-lace-btn');
                    if (updateLace) updateLace.scrollIntoView({ behavior: 'smooth', block: 'center' });
                })()
            """, msg_id=mid); mid += 1
            await asyncio.sleep(1.0)
            await capture_screenshot(ws, "lace_context_card.png", mid); mid += 1

            # 6. Switch to Rules Subtab
            print("6. Switching to Rules Subtab...")
            await evaluate_js(ws, """
                (() => {
                    const rulesTab = document.getElementById('tab-rules');
                    if (rulesTab) rulesTab.click();
                })()
            """, msg_id=mid); mid += 1
            await asyncio.sleep(1.5)
            await capture_screenshot(ws, "patient_rules_tab_with_pathways.png", mid); mid += 1

            # 7. Open Pathway Template Modal with blank thresholds
            print("7. Opening Pathway Template Modal...")
            await evaluate_js(ws, """
                (() => {
                    const btn = document.getElementById('apply-pathway-btn');
                    if (btn) btn.click();
                })()
            """, msg_id=mid); mid += 1
            await asyncio.sleep(1.5)
            await capture_screenshot(ws, "pathway_template_modal_blank_thresholds.png", mid); mid += 1

            print("All Phase 5 CDP captures completed successfully!")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

if __name__ == "__main__":
    asyncio.run(main())
