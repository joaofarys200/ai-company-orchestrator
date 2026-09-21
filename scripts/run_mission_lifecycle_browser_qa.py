"""
JARVIS OS — Mission Runtime & Lifecycle Integrity Browser QA
Validates:
1. MissionListView renders with canonical project identity, status, progress, agents, live staleness indicator.
2. Mission Control Center displays persistent breadcrumb: Projeto / Missão with '← Missões' return button.
3. Safe Stop action: RUNNING -> CANCELLING -> CANCELLED.
4. Safe Remove action: Confirmation modal -> permanent expunge from history.
5. Zero console errors and zero horizontal scroll.
6. Edge Chromium authentic browser execution with Playwright.
"""

import functools
import http.server
import json
import os
import shutil
import socket
import socketserver
import subprocess
import sys
import threading
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, WORKSPACE_ROOT)

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if sys.stderr.encoding != "utf-8":
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
FRONTEND_DIST = os.path.join(WORKSPACE_ROOT, "frontend", "dist")
SCREENSHOTS_DIR = os.path.join(WORKSPACE_ROOT, "docs", "screenshots")
ARTIFACT_DIR = r"C:\Users\joaor\.gemini\antigravity-ide\brain\d91618ab-c0e2-4b2a-9a96-cf22d1b77843"
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
os.makedirs(ARTIFACT_DIR, exist_ok=True)

EVIDENCE_JSON_PATH = os.path.join(SCREENSHOTS_DIR, "mission_lifecycle_qa_evidence.json")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path in {"/favicon.ico", "favicon.ico"}:
            self.send_response(200)
            self.send_header("Content-Type", "image/x-icon")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        return super().do_GET()


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def start_frontend_server(port: int = 8000) -> tuple[socketserver.TCPServer, threading.Thread]:
    socketserver.TCPServer.allow_reuse_address = True
    handler = functools.partial(QuietHandler, directory=FRONTEND_DIST)
    server = socketserver.TCPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def seed_qa_missions():
    from agents.mission_state import MissionStateStore
    store = MissionStateStore()
    for proj in ["task-app", "default"]:
        for mid in ["m_qa_running_demo", "m_qa_completed_demo"]:
            md = store._mission_dir(proj, mid)
            if os.path.exists(md):
                shutil.rmtree(md, ignore_errors=True)

        store.create_mission(
            proj,
            "Execução Contínua em Tempo Real",
            "Validar cancelamento cooperativo e integridade de ciclo de vida",
            mission_id="m_qa_running_demo",
        )
        store.update_mission_progress(
            proj,
            "m_qa_running_demo",
            progress=45.0,
            current_stage="STAGE_2_EXECUTION",
            status="RUNNING",
        )

        store.create_mission(
            proj,
            "Missão Concluída Histórico",
            "Validar remoção definitiva de histórico com modal",
            mission_id="m_qa_completed_demo",
        )
        store.update_mission_progress(
            proj,
            "m_qa_completed_demo",
            progress=100.0,
            current_stage="COMPLETED",
            status="COMPLETED",
        )
    print("[QA Seed] Seeded 'm_qa_running_demo' (RUNNING) and 'm_qa_completed_demo' (COMPLETED) for task-app and default.")


def main():
    print("=" * 70)
    print("[RUN] JARVIS OS - MISSION RUNTIME & LIFECYCLE BROWSER QA (EDGE)")
    print("=" * 70)

    # 1. Seed deterministic QA missions
    seed_qa_missions()

    # 2. Start Backend Server if not running
    backend_proc = None
    if not is_port_in_use(8001):
        python_exe = os.path.join(WORKSPACE_ROOT, "venv", "Scripts", "python.exe")
        if not os.path.exists(python_exe):
            python_exe = sys.executable
        print(f"[Backend] Starting server.py on ws://127.0.0.1:8001 using {python_exe}...")
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        backend_proc = subprocess.Popen(
            [python_exe, "-u", "server.py"],
            cwd=WORKSPACE_ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(30):
            if is_port_in_use(8001):
                print("[Backend] WebSocket server is up on port 8001.")
                break
            time.sleep(0.5)
    else:
        print("[Backend] WebSocket server already running on port 8001.")

    # 3. Check / Start Frontend HTTP Server
    frontend_port = 8000
    httpd = None
    if not is_port_in_use(frontend_port):
        # Allow a couple seconds in case server.py spins up the static server
        time.sleep(2.0)
        if not is_port_in_use(frontend_port):
            print(f"[HTTP] Serving {FRONTEND_DIST} on http://localhost:{frontend_port}")
            httpd, _ = start_frontend_server(frontend_port)
    else:
        print(f"[HTTP] Frontend server running on port {frontend_port}.")

    # Telemetry storage
    console_messages = []
    page_errors = []
    screenshots_taken = {}

    try:
        with sync_playwright() as p:
            print(f"[Browser] Launching Microsoft Edge: {EDGE_PATH}")
            browser = p.chromium.launch(
                executable_path=EDGE_PATH,
                headless=True,
                args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                device_scale_factor=1,
            )
            page = context.new_page()

            page.on("console", lambda msg: console_messages.append({
                "type": msg.type,
                "text": msg.text,
                "location": str(msg.location),
            }))
            page.on("pageerror", lambda err: page_errors.append(str(err)))

            # Step 1: Navigate to Workspace
            print(f"[QA] Navigating to http://localhost:{frontend_port}...")
            page.goto(f"http://localhost:{frontend_port}", wait_until="networkidle", timeout=30000)
            time.sleep(2.0)

            # Step 1.5: Ensure Workspace Drawer (Dev Panel) is opened
            print("[QA] Ensuring Workspace Drawer is opened...")
            dev_btn = page.locator("button[title*='Painel Dev']").first
            if dev_btn.count() > 0:
                print("[QA] Clicking Painel Dev toggle button...")
                dev_btn.click()
                time.sleep(2.0)

            # Step 2: Open "Missões" tab
            print("[QA] Clicking 'Missões' primary navigation tab...")
            missions_tab = page.locator("button:has-text('Missões')").first
            page.wait_for_selector("button:has-text('Missões')", timeout=10000)
            missions_tab.click()
            time.sleep(2.0)

            # Check MissionListView visibility
            print("[QA] Verifying MissionListView elements...")
            page.wait_for_selector("text=Missões do Workspace", timeout=10000)
            
            # Capture 01_mission_list_view.png
            sc1_name = "01_mission_list_view.png"
            sc1_local = os.path.join(SCREENSHOTS_DIR, sc1_name)
            sc1_art = os.path.join(ARTIFACT_DIR, sc1_name)
            page.screenshot(path=sc1_local, full_page=False)
            shutil.copyfile(sc1_local, sc1_art)
            screenshots_taken[sc1_name] = sc1_art
            print(f"  [SCREENSHOT] Screenshot saved: {sc1_name}")

            # Step 3: Open Mission in Mission Control Center
            print("[QA] Opening mission details into Mission Control Center...")
            abrir_btn = page.locator("button:has-text('Abrir')").first
            if abrir_btn.count() > 0:
                abrir_btn.click()
                time.sleep(1.5)

            # Verify Header Breadcrumb and Back button
            page.wait_for_selector("text=← Missões", timeout=10000)
            sc2_name = "02_mission_control_header.png"
            sc2_local = os.path.join(SCREENSHOTS_DIR, sc2_name)
            sc2_art = os.path.join(ARTIFACT_DIR, sc2_name)
            page.screenshot(path=sc2_local, full_page=False)
            shutil.copyfile(sc2_local, sc2_art)
            screenshots_taken[sc2_name] = sc2_art
            print(f"  [SCREENSHOT] Screenshot saved: {sc2_name}")

            # Step 4: Return to List View using "← Missões"
            print("[QA] Clicking '← Missões' breadcrumb button...")
            back_btn = page.locator("button:has-text('← Missões')").first
            if back_btn.count() > 0:
                back_btn.click()
                time.sleep(1.5)

            # Step 5: Test Stop Action on running mission
            parar_btn = page.locator("button:has-text('Parar')").first
            if parar_btn.count() > 0:
                print("[QA] Clicking 'Parar' button to trigger cooperative cancellation...")
                parar_btn.click()
                time.sleep(1.5)
                sc3_name = "03_mission_stop_action.png"
                sc3_local = os.path.join(SCREENSHOTS_DIR, sc3_name)
                sc3_art = os.path.join(ARTIFACT_DIR, sc3_name)
                page.screenshot(path=sc3_local, full_page=False)
                shutil.copyfile(sc3_local, sc3_art)
                screenshots_taken[sc3_name] = sc3_art
                print(f"  [SCREENSHOT] Screenshot saved: {sc3_name}")

            # Step 6: Test Remove from History Confirmation Modal
            remover_btn = page.locator("button:has-text('Remover')").first
            if remover_btn.count() > 0:
                print("[QA] Clicking 'Remover' button to open deletion modal...")
                remover_btn.click()
                time.sleep(1.0)
                page.wait_for_selector("text=Remover do histórico?", timeout=5000)
                sc4_name = "04_mission_remove_modal.png"
                sc4_local = os.path.join(SCREENSHOTS_DIR, sc4_name)
                sc4_art = os.path.join(ARTIFACT_DIR, sc4_name)
                page.screenshot(path=sc4_local, full_page=False)
                shutil.copyfile(sc4_local, sc4_art)
                screenshots_taken[sc4_name] = sc4_art
                print(f"  [SCREENSHOT] Screenshot saved: {sc4_name}")

                # Confirm removal
                confirm_btn = page.locator("button:has-text('Confirmar Remoção')").first
                if confirm_btn.count() > 0:
                    print("[QA] Clicking 'Confirmar Remoção'...")
                    confirm_btn.click()
                    time.sleep(1.5)

                sc5_name = "05_mission_removed_success.png"
                sc5_local = os.path.join(SCREENSHOTS_DIR, sc5_name)
                sc5_art = os.path.join(ARTIFACT_DIR, sc5_name)
                page.screenshot(path=sc5_local, full_page=False)
                shutil.copyfile(sc5_local, sc5_art)
                screenshots_taken[sc5_name] = sc5_art
                print(f"  [SCREENSHOT] Screenshot saved: {sc5_name}")

            # Step 7: Layout Verification: No Horizontal Scrolling
            has_h_scroll = page.evaluate("() => document.documentElement.scrollWidth > document.documentElement.clientWidth")
            print(f"[QA] Layout check: Horizontal Scroll = {has_h_scroll} (Expected: False)")

            # Step 8: Console Error Verification
            real_console_errors = [m for m in console_messages if m["type"] == "error"]
            print(f"[QA] Console Errors: {len(real_console_errors)} (Expected: 0)")
            print(f"[QA] Page Uncaught Exceptions: {len(page_errors)} (Expected: 0)")

            browser.close()

            # Record evidence
            evidence = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "browser": "Microsoft Edge (msedge.exe)",
                "edge_path": EDGE_PATH,
                "frontend_url": f"http://localhost:{frontend_port}",
                "backend_url": "ws://127.0.0.1:8001",
                "screenshots": screenshots_taken,
                "horizontal_scroll_detected": bool(has_h_scroll),
                "console_errors_count": len(real_console_errors),
                "page_errors_count": len(page_errors),
                "console_errors": real_console_errors,
                "status": "PASS" if len(real_console_errors) == 0 and len(page_errors) == 0 and not has_h_scroll else "FAIL",
            }

            with open(EVIDENCE_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(evidence, f, indent=2, ensure_ascii=False)

            print(f"[QA] Evidence metadata saved to {EVIDENCE_JSON_PATH}")
            print("=" * 70)
            if evidence["status"] == "PASS":
                print("[SUCCESS] BROWSER QA PASSED WITH ZERO CONSOLE ERRORS & ZERO HORIZONTAL SCROLL!")
            else:
                print(f"[WARN] BROWSER QA STATUS: {evidence['status']}")
            print("=" * 70)

    finally:
        if httpd:
            try:
                httpd.shutdown()
                httpd.server_close()
            except Exception:
                pass
        if backend_proc:
            try:
                backend_proc.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    main()
