"""
scripts/capture_task_queue_fix.py
Captures CDP screenshot of Follow-Up Tasks queue verifying tasks load correctly for Dr. Ananya Sharma.
"""
import os
import json
import base64
import subprocess
import asyncio
import tempfile
import requests
import websockets

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../docs/screenshots/fixes"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEBUG_PORT = 9239

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

    print("Launching headless Chrome for Task Queue CDP capture...")
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

            # Navigate to staff portal
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/staff"}, msg_id=mid); mid += 1
            await asyncio.sleep(2.0)

            # Set localStorage tokens
            js_login = f"""
                localStorage.setItem('careloop_token', '{doc_token}');
                localStorage.setItem('careloop_user', JSON.stringify({doc_user}));
                localStorage.setItem('careloop_theme', 'light');
                window.location.reload();
            """
            await evaluate_js(ws, js_login, mid); mid += 1
            await asyncio.sleep(2.5)

            # Navigate to Follow-up tasks tab
            print("Navigating to Follow-up tasks tab...")
            js_click_tasks = """
                const btn = Array.from(document.querySelectorAll('button, div[role=\"button\"]')).find(b => b.innerText && b.innerText.includes('Follow-up tasks'));
                if (btn) btn.click();
            """
            await evaluate_js(ws, js_click_tasks, mid); mid += 1
            await asyncio.sleep(2.0)

            # Click "Team tasks" scope button (exactly like user screenshot)
            print("Clicking 'Team tasks' filter button...")
            js_click_team = """
                const teamBtn = Array.from(document.querySelectorAll('button')).find(b => b.innerText && b.innerText.trim() === 'Team tasks');
                if (teamBtn) teamBtn.click();
            """
            await evaluate_js(ws, js_click_team, mid); mid += 1
            await asyncio.sleep(2.0)

            print("Capturing verified Task Queue screen...")
            await capture_screenshot(ws, "task_queue_fixed_team_tasks.png", mid); mid += 1
            print("Capture complete!")

    finally:
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    asyncio.run(main())
