"""Phase 24 Verification Screenshots Capture Script.

Captures:
- screenshot/phase24_admin_overview_desktop.png (1440x900)
- screenshot/phase24_admin_overview_mobile.png (390x844)
- screenshot/phase24_chat_summary_clean.png (1440x900)
"""

import asyncio
import base64
import json
import os
import subprocess
import sys
import time

import httpx
import websockets

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PORT = 9222


async def send_cmd(ws, method, params=None, req_id=1):
    payload = {"id": req_id, "method": method, "params": params or {}}
    await ws.send(json.dumps(payload))
    while True:
        raw = await ws.recv()
        msg = json.loads(raw)
        if msg.get("id") == req_id:
            return msg


async def eval_js(ws, expr, req_id):
    resp = await send_cmd(
        ws,
        "Runtime.evaluate",
        {"expression": expr, "awaitPromise": True, "returnByValue": True},
        req_id=req_id,
    )
    return resp.get("result", {}).get("result", {}).get("value")


async def take_screenshot(ws, output_path, req_id):
    resp = await send_cmd(
        ws,
        "Page.captureScreenshot",
        {"format": "png", "captureBeyondViewport": False},
        req_id=req_id,
    )
    if "result" in resp and "data" in resp["result"]:
        data = base64.b64decode(resp["result"]["data"])
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(data)
        print(f"Captured: {output_path} ({len(data)} bytes)", flush=True)
        return True
    return False


server_proc = None

def ensure_servers():
    global server_proc
    try:
        r = httpx.get("http://localhost:8080/", timeout=2.0)
        frontend_up = (r.status_code == 200)
    except Exception:
        frontend_up = False

    if not frontend_up:
        print("Starting application server with DEMO_MODE=1...", flush=True)
        env = os.environ.copy()
        env["DEMO_MODE"] = "1"
        env["NO_RELOAD"] = "1"
        server_proc = subprocess.Popen([sys.executable, "frontend/main.py"], env=env)
        for _ in range(40):
            time.sleep(1)
            try:
                if httpx.get("http://localhost:8080/", timeout=1.0).status_code == 200:
                    print("Application server is ready!", flush=True)
                    frontend_up = True
                    break
            except Exception:
                pass
    else:
        print("Application server is already running.", flush=True)


async def capture_phase24():
    ensure_servers()
    try:
        r = httpx.get(f"http://localhost:{PORT}/json")
        tabs = r.json()
    except Exception:
        user_data = os.path.expanduser(r"~\AppData\Local\Temp\edge_cdp_phase24")
        cmd = f'"{EDGE_PATH}" --remote-debugging-port={PORT} --user-data-dir="{user_data}" --no-first-run --no-default-browser-check about:blank'
        subprocess.Popen(cmd, shell=True)
        time.sleep(2)
        r = httpx.get(f"http://localhost:{PORT}/json")
        tabs = r.json()

    page_tabs = [t for t in tabs if t.get("type") == "page"]
    ws_url = page_tabs[0]["webSocketDebuggerUrl"]

    async with websockets.connect(ws_url, max_size=50 * 1024 * 1024) as ws:
        await send_cmd(ws, "Page.enable", req_id=1)
        await send_cmd(ws, "DOM.enable", req_id=2)
        await send_cmd(ws, "Network.enable", req_id=3)
        await send_cmd(ws, "Network.clearBrowserCookies", req_id=4)
        await send_cmd(
            ws,
            "Storage.clearDataForOrigin",
            {"origin": "http://localhost:8080", "storageTypes": "all"},
            req_id=5,
        )

        # -------------------------------------------------------------
        # 1. Admin Login & Dashboard Overview
        # -------------------------------------------------------------
        print("\n[1] Navigating to admin login...", flush=True)
        await send_cmd(
            ws,
            "Emulation.setDeviceMetricsOverride",
            {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False},
            req_id=10,
        )
        await send_cmd(ws, "Page.navigate", {"url": "http://localhost:8080/admin/login"}, req_id=11)
        await asyncio.sleep(2.5)

        fill_admin_login = """
        (() => {
            const inputs = Array.from(document.querySelectorAll('input'));
            const emailInput = inputs.find(i => i.type === 'email' || (i.placeholder && i.placeholder.includes('@')));
            const passInput = inputs.find(i => i.type === 'password' || (i.placeholder && i.placeholder.includes('•')));
            if (!emailInput || !passInput) return 'inputs_not_found';
            emailInput.focus();
            document.execCommand('selectAll', false, null);
            document.execCommand('insertText', false, 'admin@university.edu');
            passInput.focus();
            document.execCommand('selectAll', false, null);
            document.execCommand('insertText', false, 'AdminPass123!');
            const buttons = Array.from(document.querySelectorAll('button'));
            const submitBtn = buttons.find(b => b.textContent.includes('Sign in') || b.textContent.includes('Sign In'));
            if (submitBtn) {
                setTimeout(() => submitBtn.click(), 200);
                return 'submitted';
            }
            return 'submit_btn_not_found';
        })()
        """
        res = await eval_js(ws, fill_admin_login, req_id=12)
        print("Login fill result:", res, flush=True)
        await asyncio.sleep(3.5)

        current_url = await eval_js(ws, "window.location.href", req_id=13)
        print("Current URL after admin login:", current_url, flush=True)
        if "/dashboard" not in current_url:
            await send_cmd(ws, "Page.navigate", {"url": "http://localhost:8080/dashboard"}, req_id=14)
            await asyncio.sleep(3.0)

        # Wait for data elements to settle
        await asyncio.sleep(2.0)

        # -------------------------------------------------------------
        # 2. Desktop Admin Overview (1440x900)
        # -------------------------------------------------------------
        print("\n[2] Capturing Admin Overview Desktop (1440x900)...", flush=True)
        await send_cmd(
            ws,
            "Emulation.setDeviceMetricsOverride",
            {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False},
            req_id=20,
        )
        await asyncio.sleep(1.0)
        await take_screenshot(ws, "screenshot/phase24_admin_overview_desktop.png", req_id=21)

        # -------------------------------------------------------------
        # 3. Mobile Admin Overview (390x844)
        # -------------------------------------------------------------
        print("\n[3] Capturing Admin Overview Mobile (390x844)...", flush=True)
        await send_cmd(
            ws,
            "Emulation.setDeviceMetricsOverride",
            {"width": 390, "height": 844, "deviceScaleFactor": 2, "mobile": True},
            req_id=30,
        )
        await asyncio.sleep(1.0)
        await take_screenshot(ws, "screenshot/phase24_admin_overview_mobile.png", req_id=31)

        # -------------------------------------------------------------
        # 4. Student Chat & Natural Answer Formatting
        # -------------------------------------------------------------
        print("\n[4] Navigating to Student Chat...", flush=True)
        await send_cmd(
            ws,
            "Emulation.setDeviceMetricsOverride",
            {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False},
            req_id=40,
        )
        await send_cmd(ws, "Page.navigate", {"url": "http://localhost:8080/chat"}, req_id=41)
        await asyncio.sleep(3.0)

        # Ask a summary question to verify natural markdown formatting
        ask_question = """
        (() => {
            const textarea = document.querySelector('textarea');
            if (!textarea) return 'no_textarea';
            textarea.focus();
            document.execCommand('selectAll', false, null);
            document.execCommand('insertText', false, 'Summarize Flutter course lecture notes');
            const btns = Array.from(document.querySelectorAll('button'));
            const sendBtn = btns.find(b => b.querySelector('i') && (b.querySelector('i').textContent.includes('send') || b.querySelector('i').textContent.includes('arrow_upward')));
            if (sendBtn) {
                setTimeout(() => sendBtn.click(), 300);
                return 'sent';
            }
            return 'no_send_button';
        })()
        """
        q_res = await eval_js(ws, ask_question, req_id=42)
        print("Question submission result:", q_res, flush=True)
        # Wait for answer synthesis
        await asyncio.sleep(8.0)

        await take_screenshot(ws, "screenshot/phase24_chat_summary_clean.png", req_id=43)
        print("\nPhase 24 screenshots captured successfully!", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(capture_phase24())
    finally:
        if server_proc:
            server_proc.terminate()
