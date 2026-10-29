"""
scripts/capture_phase4_screenshots.py

Captures Phase 4 Care Team Portal screenshots:
- audit_log_viewer_light.png
- audit_log_viewer_dark.png
- patient_notes_and_calls_light.png
- command_palette_search.png
- keyboard_shortcuts_modal.png

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

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../docs/screenshots/staff_phase4"))
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

    user_data_dir = tempfile.mkdtemp(prefix="careloop_chrome_p4_")
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

            print("Navigating to staff portal...")
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

            # 1. Audit Log Viewer Light
            print("Capturing Audit Log Viewer (Light)...")
            msg_id += 1
            await evaluate_js(ws, """
                const buttons = Array.from(document.querySelectorAll('button'));
                const auditBtn = buttons.find(b => b.textContent.includes('Audit log viewer'));
                if (auditBtn) auditBtn.click();
            """, msg_id)
            await asyncio.sleep(1.5)
            msg_id += 1
            await capture_screenshot(ws, "audit_log_viewer_light.png", msg_id)

            # 2. Audit Log Viewer Dark
            print("Capturing Audit Log Viewer (Dark)...")
            msg_id += 1
            await evaluate_js(ws, """
                const themeBtn = document.querySelector('button[aria-label*="theme"], button[title*="theme"]') || Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Theme') || b.querySelector('svg'));
                document.documentElement.setAttribute('data-theme', 'dark');
                document.body.classList.add('dark');
            """, msg_id)
            await asyncio.sleep(1.0)
            msg_id += 1
            await capture_screenshot(ws, "audit_log_viewer_dark.png", msg_id)

            # Restore light mode
            msg_id += 1
            await evaluate_js(ws, """
                document.documentElement.setAttribute('data-theme', 'light');
                document.body.classList.remove('dark');
            """, msg_id)
            await asyncio.sleep(0.5)

            # 3. Patient Notes & Calls Subtab
            print("Capturing Patient Notes & Calls Subtab...")
            msg_id += 1
            await evaluate_js(ws, """
                const buttons = Array.from(document.querySelectorAll('button'));
                const patBtn = buttons.find(b => b.textContent.includes('Patient directory'));
                if (patBtn) patBtn.click();
            """, msg_id)
            await asyncio.sleep(1.5)

            msg_id += 1
            await evaluate_js(ws, """
                // Click on first patient card
                const pRows = Array.from(document.querySelectorAll('button, div'));
                const viewChart = pRows.find(el => el.textContent.includes('View Clinical Chart') || el.textContent.includes('Aarav Patel'));
                if (viewChart) viewChart.click();
            """, msg_id)
            await asyncio.sleep(1.5)

            msg_id += 1
            await evaluate_js(ws, """
                const tabButtons = Array.from(document.querySelectorAll('button'));
                const notesTab = tabButtons.find(b => b.textContent.includes('Notes & Calls'));
                if (notesTab) notesTab.click();
            """, msg_id)
            await asyncio.sleep(1.5)
            msg_id += 1
            await capture_screenshot(ws, "patient_notes_and_calls_light.png", msg_id)

            # 4. Command Palette Search (Ctrl+K)
            print("Capturing Command Palette Search Modal...")
            msg_id += 1
            await evaluate_js(ws, """
                window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true, bubbles: true }));
            """, msg_id)
            await asyncio.sleep(1.0)
            msg_id += 1
            await evaluate_js(ws, """
                const input = document.querySelector('input[placeholder*="Search patients"]');
                if (input) {
                    input.value = 'Aarav';
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                }
            """, msg_id)
            await asyncio.sleep(1.2)
            msg_id += 1
            await capture_screenshot(ws, "command_palette_search.png", msg_id)

            # Close Command Palette
            msg_id += 1
            await evaluate_js(ws, """
                window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
            """, msg_id)
            await asyncio.sleep(0.5)

            # 5. Keyboard Shortcuts Help Modal (?)
            print("Capturing Keyboard Shortcuts Modal...")
            msg_id += 1
            await evaluate_js(ws, """
                window.dispatchEvent(new KeyboardEvent('keydown', { key: '?', bubbles: true }));
            """, msg_id)
            await asyncio.sleep(1.0)
            msg_id += 1
            await capture_screenshot(ws, "keyboard_shortcuts_modal.png", msg_id)

    finally:
        proc.terminate()
        proc.wait()

    print("\nPhase 4 screenshot capture complete!")

if __name__ == "__main__":
    asyncio.run(main())
