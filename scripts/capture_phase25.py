"""Phase 25 Verification Screenshots Capture Script.

Captures:
1. screenshot/phase25_student_composer_three_modes.png (1440x900)
2. screenshot/phase25_student_document_mode_pdf_list.png (1440x900)
3. screenshot/phase25_student_document_mode_selected_pill.png (1440x900)
4. screenshot/phase25_student_single_canonical_new_chat.png (1440x900)
5. screenshot/phase25_flutter_widget_list_clean_answer.png (1440x900)
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
BASE_URL = "http://localhost:8080"


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
        r = httpx.get(f"{BASE_URL}/", timeout=2.0)
        frontend_up = (r.status_code == 200)
    except Exception:
        frontend_up = False

    if not frontend_up:
        print("Starting application server (frontend/main.py)...", flush=True)
        env = os.environ.copy()
        env["NO_RELOAD"] = "1"
        server_proc = subprocess.Popen([sys.executable, "frontend/main.py"], env=env)
        for _ in range(40):
            time.sleep(1)
            try:
                if httpx.get(f"{BASE_URL}/", timeout=1.0).status_code == 200:
                    print("Application server is ready!", flush=True)
                    frontend_up = True
                    break
            except Exception:
                pass
    else:
        print("Application server is already running.", flush=True)


async def login_as_student(ws, step_id=100):
    await send_cmd(ws, "Page.navigate", {"url": f"{BASE_URL}/student/login"}, req_id=step_id)
    await asyncio.sleep(2.5)

    fill_student_login = """
    (() => {
        const inputs = Array.from(document.querySelectorAll('input'));
        const emailInput = inputs.find(i => i.type === 'email' || (i.placeholder && i.placeholder.includes('@')));
        const passInput = inputs.find(i => i.type === 'password' || (i.placeholder && i.placeholder.includes('•')));
        if (!emailInput || !passInput) return 'inputs_not_found: inputs=' + inputs.length;
        emailInput.focus();
        document.execCommand('selectAll', false, null);
        document.execCommand('insertText', false, 'student@university.edu');
        passInput.focus();
        document.execCommand('selectAll', false, null);
        document.execCommand('insertText', false, 'StudentPass123!');
        const buttons = Array.from(document.querySelectorAll('button'));
        const submitBtn = buttons.find(b => b.textContent.includes('Sign in') || b.textContent.includes('Sign In'));
        if (submitBtn) {
            setTimeout(() => submitBtn.click(), 200);
            return 'submitted';
        }
        return 'submit_btn_not_found';
    })()
    """
    res = await eval_js(ws, fill_student_login, req_id=step_id + 1)
    print("Student login fill result:", res, flush=True)
    await asyncio.sleep(3.5)

    curr_url = await eval_js(ws, "window.location.href", req_id=step_id + 2)
    print("URL after student login:", curr_url, flush=True)
    if "/chat" not in curr_url:
        await send_cmd(ws, "Page.navigate", {"url": f"{BASE_URL}/chat"}, req_id=step_id + 3)
        await asyncio.sleep(3.0)


async def capture_all():
    ensure_servers()

    try:
        r = httpx.get(f"http://localhost:{PORT}/json")
        tabs = r.json()
    except Exception:
        user_data = os.path.expanduser(r"~\AppData\Local\Temp\edge_cdp_phase25")
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
            {"origin": BASE_URL, "storageTypes": "all"},
            req_id=5,
        )

        await send_cmd(
            ws,
            "Emulation.setDeviceMetricsOverride",
            {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False},
            req_id=6,
        )

        # -------------------------------------------------------------
        # 1. Login as Student
        # -------------------------------------------------------------
        print("\n--- [Step 1] Logging in as Student ---", flush=True)
        await login_as_student(ws, step_id=10)
        await asyncio.sleep(2.0)

        # -------------------------------------------------------------
        # 2. Scope Selector: Open Three Modes Popover
        # -------------------------------------------------------------
        print("\n--- [Step 2] Capturing phase25_student_composer_three_modes.png ---", flush=True)
        open_scope_popover = """
        (() => {
            const btn = document.querySelector('.scope-selector-btn') || 
                        document.querySelector('button[aria-label*="scope selector"]');
            if (btn) {
                btn.click();
                return 'clicked_scope_btn';
            }
            return 'scope_btn_not_found';
        })()
        """
        res = await eval_js(ws, open_scope_popover, req_id=20)
        print("Scope button click result:", res, flush=True)
        await asyncio.sleep(1.5)

        await take_screenshot(ws, "screenshot/phase25_student_composer_three_modes.png", req_id=21)

        # -------------------------------------------------------------
        # 3. Scope Selector: Document Mode & PDF list
        # -------------------------------------------------------------
        print("\n--- [Step 3] Capturing phase25_student_document_mode_pdf_list.png ---", flush=True)
        click_document_mode = """
        (() => {
            const elements = Array.from(document.querySelectorAll('.scope-popover-menu div, .scope-popover-menu span, .scope-popover-menu label'));
            const docTab = elements.find(el => el.textContent.trim() === 'Document');
            if (docTab) {
                const clickable = docTab.closest('.cursor-pointer') || docTab;
                clickable.click();
                return 'clicked_document_tab';
            }
            return 'document_tab_not_found';
        })()
        """
        res = await eval_js(ws, click_document_mode, req_id=30)
        print("Click Document mode tab:", res, flush=True)
        await asyncio.sleep(1.0)

        # In Document mode, select course 'MSC' from the list of courses
        select_msc_course = """
        (() => {
            const rows = Array.from(document.querySelectorAll('.scope-popover-menu .cursor-pointer'));
            const mscRow = rows.find(r => r.textContent.includes('MSC'));
            if (mscRow) {
                mscRow.click();
                return 'clicked_msc_course';
            }
            return 'msc_row_not_found: ' + rows.map(r => r.textContent.trim()).join(' | ');
        })()
        """
        res = await eval_js(ws, select_msc_course, req_id=31)
        print("Select MSC course for documents:", res, flush=True)
        await asyncio.sleep(1.5)

        # Take screenshot of Document mode showing PDF list
        await take_screenshot(ws, "screenshot/phase25_student_document_mode_pdf_list.png", req_id=32)

        # -------------------------------------------------------------
        # 4. Scope Selector: Select PDF and verify pill
        # -------------------------------------------------------------
        print("\n--- [Step 4] Capturing phase25_student_document_mode_selected_pill.png ---", flush=True)
        click_pdf_item = """
        (() => {
            const docRows = Array.from(document.querySelectorAll('.scope-popover-menu .cursor-pointer'));
            const flutterDoc = docRows.find(r => r.textContent.includes('Flutter') || r.textContent.includes('.pdf'));
            if (flutterDoc) {
                flutterDoc.click();
                return 'clicked_flutter_doc';
            }
            return 'flutter_doc_not_found: ' + docRows.map(r => r.textContent.trim()).join(' | ');
        })()
        """
        res = await eval_js(ws, click_pdf_item, req_id=40)
        print("Click PDF item in list:", res, flush=True)
        await asyncio.sleep(1.5)

        await take_screenshot(ws, "screenshot/phase25_student_document_mode_selected_pill.png", req_id=41)

        # -------------------------------------------------------------
        # 5. Repeated login/refresh verification (Single canonical New Chat)
        # -------------------------------------------------------------
        print("\n--- [Step 5] Simulating repeated logins & capturing phase25_student_single_canonical_new_chat.png ---", flush=True)
        for i in range(3):
            print(f"Cycle {i+1}/3: Refresh / navigate to /chat...", flush=True)
            await send_cmd(ws, "Page.navigate", {"url": f"{BASE_URL}/chat"}, req_id=50 + i * 2)
            await asyncio.sleep(2.5)

        await take_screenshot(ws, "screenshot/phase25_student_single_canonical_new_chat.png", req_id=59)

        # -------------------------------------------------------------
        # 6. Ask 'flutter widget list' and capture clean list answer
        # -------------------------------------------------------------
        print("\n--- [Step 6] Asking 'flutter widget list' & capturing answer ---", flush=True)
        ask_flutter_widget_list = """
        (() => {
            const textarea = document.querySelector('textarea');
            if (!textarea) return 'no_textarea';
            textarea.focus();
            textarea.value = 'flutter widget list';
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
            textarea.dispatchEvent(new Event('change', { bubbles: true }));
            
            setTimeout(() => {
                const btns = Array.from(document.querySelectorAll('button'));
                const sendBtn = btns.find(b => b.getAttribute('aria-label') === 'Send question' || 
                                              (b.querySelector('i') && b.querySelector('i').textContent.includes('arrow_upward')));
                if (sendBtn) {
                    sendBtn.click();
                }
            }, 300);
            return 'dispatched_and_triggered_submit';
        })()
        """
        res = await eval_js(ws, ask_flutter_widget_list, req_id=60)
        print("Submit query result:", res, flush=True)

        print("Waiting for generation to finish...", flush=True)
        # Wait a minimum of 6 seconds before checking so Ollama generation starts
        await asyncio.sleep(6.0)

        for cycle in range(65):
            is_generating = await eval_js(
                ws,
                "Boolean(document.querySelector('button[aria-label=\"Stop generating\"]'))",
                req_id=70 + cycle,
            )
            print(f"Generating status ({cycle+1}/65): {is_generating}", flush=True)
            if not is_generating:
                # Extra wait for UI / markdown rendering to complete
                await asyncio.sleep(3.0)
                break
            await asyncio.sleep(2.0)

        await take_screenshot(ws, "screenshot/phase25_flutter_widget_list_clean_answer.png", req_id=199)
        print("\nAll 5 Phase 25 screenshots captured successfully!", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(capture_all())
    finally:
        if server_proc:
            server_proc.terminate()
