"""
scripts/capture_rag_chat_fix.py
Captures a live CDP screenshot of the Discharge Recovery Assistant answering
'What warning signs should I watch for?' with grounded facts and source citations.
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
DEBUG_PORT = 9248

async def send_cmd(ws, method, params=None, msg_id=1):
    msg = {"id": msg_id, "method": method, "params": params or {}}
    await ws.send(json.dumps(msg))
    while True:
        resp = await ws.recv()
        data = json.loads(resp)
        if data.get("id") == msg_id:
            return data.get("result", {})

async def capture_screenshot(ws, filename, msg_id_base):
    await asyncio.sleep(2.0)
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
    print("1. Authenticating as Patient Aarav Patel...")
    pat_res = requests.post(
        "http://127.0.0.1:8000/auth/login",
        json={"email": "aarav.demo@example.test", "password": "Demo@12345"},
    ).json()
    pat_token = pat_res["access_token"]
    pat_user = json.dumps({
        "account_id": pat_res["account_id"],
        "email": "aarav.demo@example.test",
        "name": "Aarav Patel",
        "role": "Patient",
        "patient_id": pat_res["patient_id"],
    })

    print("2. Launching headless Chrome via CDP...")
    user_data_dir = tempfile.mkdtemp()
    proc = subprocess.Popen([
        CHROME_BIN,
        "--headless=new",
        "--disable-gpu",
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={user_data_dir}",
        "--window-size=1280,850",
        "--hide-scrollbars",
        "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await asyncio.sleep(2.0)

    try:
        tab_info = requests.put(f"http://127.0.0.1:{DEBUG_PORT}/json/new").json()
        ws_url = tab_info["webSocketDebuggerUrl"]

        async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
            mid = 100
            await send_cmd(ws, "Page.enable", msg_id=mid); mid += 1
            await send_cmd(ws, "DOM.enable", msg_id=mid); mid += 1

            # Navigate to patient portal
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:3000/patient"}, msg_id=mid); mid += 1
            await asyncio.sleep(2.5)

            # Inject auth into localStorage
            inject_js = f"""
                localStorage.setItem('careloop_token', '{pat_token}');
                localStorage.setItem('careloop_user', JSON.stringify({pat_user}));
                window.location.reload();
            """
            await evaluate_js(ws, inject_js, mid); mid += 1
            await asyncio.sleep(3.0)

            # Click on 'Ask my discharge papers' tab
            click_chat_tab_js = """
                (() => {
                    const buttons = Array.from(document.querySelectorAll('button'));
                    const chatBtn = buttons.find(b => b.textContent.includes('Ask my discharge papers'));
                    if (chatBtn) {
                        chatBtn.click();
                        return 'clicked_tab';
                    }
                    return 'not_found';
                })()
            """
            tab_res = await evaluate_js(ws, click_chat_tab_js, mid); mid += 1
            print("  Tab click result:", tab_res)
            await asyncio.sleep(2.0)

            # Type question and submit
            type_and_submit_js = """
                (() => {
                    const input = document.querySelector('input[placeholder*="Ask about your medicines"]');
                    if (!input) return 'input_not_found';
                    
                    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                    nativeInputValueSetter.call(input, 'What warning signs should I watch for?');
                    input.dispatchEvent(new Event('input', { bubbles: true }));

                    const form = input.closest('form');
                    if (form) {
                        form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
                        return 'submitted_form';
                    }
                    return 'form_not_found';
                })()
            """
            submit_res = await evaluate_js(ws, type_and_submit_js, mid); mid += 1
            print("  Submit result:", submit_res)

            # Wait for RAG pipeline to complete and answer to appear
            print("  Waiting for RAG answer to appear on screen...")
            await asyncio.sleep(7.0)

            # Capture screenshot of chat result
            await capture_screenshot(ws, "rag_assistant_grounded_answer.png", mid); mid += 1
            print("✓ Successfully captured rag_assistant_grounded_answer.png")

    finally:
        proc.terminate()

if __name__ == "__main__":
    asyncio.run(main())
