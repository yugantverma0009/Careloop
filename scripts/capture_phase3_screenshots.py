"""
scripts/capture_phase3_screenshots.py

Captures Phase 3 screens:
- task_queue_light.png
- clinical_summaries_light.png
- shift_handoff_light.png

Saved to docs/screenshots/staff_phase3/
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

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../docs/screenshots/staff_phase3"))
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
        print(f"  ✗ Failed to capture {filename}")

async def evaluate_js(ws, expr, msg_id):
    return await send_cmd(ws, "Runtime.evaluate", {"expression": expr, "awaitPromise": True}, msg_id=msg_id)

async def main():
    print("Authenticating as Dr. Ananya Sharma...")
    doc_res = requests.post("http://127.0.0.1:8000/auth/login", json={"email": "ananya.demo@example.test", "password": "Demo@12345"}).json()
    doc_token = doc_res["access_token"]
    doc_user = json.dumps({
        "account_id": doc_res["account_id"],
        "email": "ananya.demo@example.test",
        "role": "Doctor",
        "name": "Dr. Ananya Sharma",
        "staff_id": doc_res.get("staff_id", 1),
    })

    user_data_dir = tempfile.mkdtemp(prefix="careloop_chrome_p3_")
    chrome_cmd = [
        CHROME_BIN,
        f"--remote-debugging-port={DEBUG_PORT}",
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        f"--user-data-dir={user_data_dir}",
        "--window-size=1440,920",
    ]

    print("Launching Chrome...")
    proc = subprocess.Popen(chrome_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)

    try:
        tab_info = requests.put(f"http://127.0.0.1:{DEBUG_PORT}/json/new").json()
        ws_url = tab_info["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
            msg_id = 1
            await send_cmd(ws, "Page.enable", msg_id=msg_id)

            msg_id += 1
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/staff"}, msg_id=msg_id)
            await asyncio.sleep(2.0)

            # Set localStorage doctor session
            msg_id += 1
            setup_script = f"""
                localStorage.setItem('careloop_token', '{doc_token}');
                localStorage.setItem('careloop_user', '{doc_user}');
                localStorage.setItem('careloop_theme', 'light');
                window.location.reload();
            """
            await evaluate_js(ws, setup_script, msg_id)
            await asyncio.sleep(2.5)

            # 1. Follow-up Tasks (D-07)
            print("Capturing Follow-up Task Queue...")
            msg_id += 1
            await evaluate_js(ws, """
                const buttons = Array.from(document.querySelectorAll('button'));
                const btn = buttons.find(b => b.textContent.includes('Follow-up tasks'));
                if (btn) btn.click();
            """, msg_id)
            await asyncio.sleep(1.5)
            msg_id += 1
            await capture_screenshot(ws, "task_queue_light.png", msg_id)

            # 2. Draft Clinical Summaries (D-08)
            print("Capturing Clinical Summaries...")
            msg_id += 1
            await evaluate_js(ws, """
                const buttons = Array.from(document.querySelectorAll('button'));
                const btn = buttons.find(b => b.textContent.includes('Draft summaries'));
                if (btn) btn.click();
            """, msg_id)
            await asyncio.sleep(1.5)
            msg_id += 1
            await capture_screenshot(ws, "clinical_summaries_light.png", msg_id)

            # 3. Shift Handoff (D-09)
            print("Capturing Shift Handoff (I-PASS)...")
            msg_id += 1
            await evaluate_js(ws, """
                const buttons = Array.from(document.querySelectorAll('button'));
                const btn = buttons.find(b => b.textContent.includes('Shift handoff'));
                if (btn) btn.click();
            """, msg_id)
            await asyncio.sleep(1.5)
            msg_id += 1
            await capture_screenshot(ws, "shift_handoff_light.png", msg_id)

    finally:
        proc.terminate()
        proc.wait()

    print("\nPhase 3 screenshot capture complete!")

if __name__ == "__main__":
    asyncio.run(main())
