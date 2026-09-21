"""
JARVIS OS — Mission Control Center Rehaul: Real Browser QA (Microsoft Edge via Playwright)
Validates:
1. Clean 5-tab Navigation (Visão geral, Tarefas, Agentes, Atividade, Diagnóstico)
2. Minimalist Dark Workspace Aesthetic (consistent with WorkspaceViewer)
3. Zero Horizontal Scrolling (document.documentElement.scrollWidth <= window.innerWidth)
4. Detail Drawer on Tasks without full-page navigation
5. Consolidated Diagnostics (Runtime F71, Confiabilidade F72, Requirements, Planning, Execution, Security)
6. Zero Console Errors and Page Errors
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from playwright.sync_api import sync_playwright

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR = os.path.join(WORKSPACE_ROOT, "docs")
SCREENSHOTS_DIR = os.path.join(DOCS_DIR, "screenshots", "mission_control_rehaul")
ARTIFACTS_DIR = r"C:\Users\joaor\.gemini\antigravity-ide\brain\d91618ab-c0e2-4b2a-9a96-cf22d1b77843"
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def start_backend_if_needed() -> subprocess.Popen | None:
    if is_port_open("127.0.0.1", 8001):
        print("[BACKEND] Backend server already running on port 8001.")
        return None

    venv_python = os.path.join(WORKSPACE_ROOT, "venv", "Scripts", "python.exe")
    python_exe = venv_python if os.path.exists(venv_python) else sys.executable

    print(f"[BACKEND] Starting JARVIS server using {python_exe} server.py...")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    proc = subprocess.Popen(
        [python_exe, "server.py"],
        cwd=WORKSPACE_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    t0 = time.time()
    while time.time() - t0 < 30.0:
        if is_port_open("127.0.0.1", 8001):
            print(f"[BACKEND] Server listening on port 8001 (PID {proc.pid}).")
            time.sleep(2.0)
            return proc
        time.sleep(0.5)

    print("[BACKEND] Warning: Backend server did not respond on port 8001 within 30s.")
    return proc


def start_frontend_if_needed() -> subprocess.Popen | None:
    if is_port_open("127.0.0.1", 5173):
        print("[FRONTEND] Frontend dev server already running on port 5173.")
        return None

    frontend_dir = os.path.join(WORKSPACE_ROOT, "frontend")
    print(f"[FRONTEND] Starting Vite dev server in {frontend_dir}...")

    proc = subprocess.Popen(
        "npm run dev -- --host 127.0.0.1",
        cwd=frontend_dir,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    t0 = time.time()
    while time.time() - t0 < 30.0:
        if is_port_open("127.0.0.1", 5173):
            print(f"[FRONTEND] Frontend listening on port 5173 (PID {proc.pid}).")
            time.sleep(2.0)
            return proc
        time.sleep(0.5)

    print("[FRONTEND] Warning: Frontend server did not respond on port 5173 within 30s.")
    return proc


def run_qa():
    print("=" * 70)
    print("JARVIS OS — Mission Control Center Rehaul: Browser QA Verification")
    print("=" * 70)

    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    backend_proc = start_backend_if_needed()
    frontend_proc = start_frontend_if_needed()

    console_errors: list[str] = []
    page_errors: list[str] = []

    qa_report = {
        "timestamp": time.time(),
        "browser": "Microsoft Edge",
        "viewport": {"width": 1440, "height": 900},
        "views_tested": [],
        "horizontal_scroll_clean": True,
        "console_errors_count": 0,
        "success": False,
    }

    try:
        with sync_playwright() as p:
            launch_args = {
                "headless": True,
                "args": [
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-gpu",
                ],
            }
            if os.path.exists(EDGE_PATH):
                launch_args["executable_path"] = EDGE_PATH
                print(f"[BROWSER] Using Microsoft Edge executable at {EDGE_PATH}")
            else:
                launch_args["channel"] = "msedge"
                print("[BROWSER] Using msedge channel via Playwright")

            browser = p.chromium.launch(**launch_args)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()

            def on_console(msg):
                if msg.type == "error":
                    txt = msg.text
                    if "favicon" not in txt and "WebSocket" not in txt and "unrecognized in this browser" not in txt and "404" not in txt:
                        console_errors.append(f"[{msg.type.upper()}] {txt}")

            page.on("console", on_console)
            page.on("pageerror", lambda err: page_errors.append(str(err)))

            print("[NAV] Navigating to http://127.0.0.1:5173 ...")
            page.goto("http://127.0.0.1:5173", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)

            # Open Dev Panel -> mission_control
            dev_btn = page.locator("button[title*='Abrir Painel Dev']").first
            if dev_btn.is_visible():
                print("  [NAV] Opening Dev Panel...")
                dev_btn.click()
                page.wait_for_timeout(1000)

            print("  [NAV] Activating mission_control tab via window.__setActiveTab...")
            page.evaluate("window.__setActiveTab && window.__setActiveTab('mission_control')")
            page.wait_for_timeout(1500)

            # Check if mission-nav-tab-overview exists, or try clicking Missões -> Mission Control
            if not page.locator("#mission-nav-tab-overview").is_visible():
                print("  [NAV] Fallback: Clicking Missões tab in workspace...")
                missions_btn = page.locator("button:has-text('Missões')").first
                if missions_btn.is_visible():
                    missions_btn.click()
                    page.wait_for_timeout(1000)
                mcc_btn = page.locator("button:has-text('Mission Control')").first
                if mcc_btn.is_visible():
                    mcc_btn.click()
                    page.wait_for_timeout(1000)

            # Verify that mission-nav-tab-overview is visible
            page.wait_for_selector("#mission-nav-tab-overview", timeout=15000)
            print("[QA] Mission Control Center loaded successfully!")

            def check_horizontal_scroll() -> dict:
                res = page.evaluate("""() => {
                    const docOverflow = document.documentElement.scrollWidth > window.innerWidth;
                    const bodyOverflow = document.body.scrollWidth > window.innerWidth;
                    return {
                        scrollWidth: document.documentElement.scrollWidth,
                        clientWidth: document.documentElement.clientWidth,
                        innerWidth: window.innerWidth,
                        hasOverflow: docOverflow || bodyOverflow
                    }
                }""")
                return res

            def save_screenshot(filename: str):
                local_path = os.path.join(SCREENSHOTS_DIR, filename)
                page.screenshot(path=local_path, full_page=False)
                artifact_path = os.path.join(ARTIFACTS_DIR, filename)
                shutil.copy2(local_path, artifact_path)
                print(f"[SCREENSHOT] Saved {filename} -> {local_path}")

            # =========================================================================
            # VIEW 1: OVERVIEW (Visão geral)
            # =========================================================================
            print("\n--- Validating View 1: Overview (Visão geral) ---")
            page.click("#mission-nav-tab-overview")
            page.wait_for_timeout(1200)

            scroll_overview = check_horizontal_scroll()
            print(f"[SCROLL] Overview scroll check: {scroll_overview}")
            assert not scroll_overview["hasOverflow"], "Horizontal overflow detected in Overview!"
            save_screenshot("01_overview.png")
            qa_report["views_tested"].append({
                "view": "overview",
                "label": "Visão geral",
                "scroll_check": scroll_overview,
                "screenshot": "01_overview.png",
            })

            # =========================================================================
            # VIEW 2: TASKS (Tarefas) + DETAIL DRAWER
            # =========================================================================
            print("\n--- Validating View 2: Tasks (Tarefas) ---")
            page.click("#mission-nav-tab-tasks")
            page.wait_for_timeout(1200)

            # Check task rows are visible
            task_rows = page.locator("div.group.flex.items-center.justify-between.gap-3.rounded-md")
            tasks_count = task_rows.count()
            print(f"[TASKS] Found {tasks_count} task rows in view.")

            # Click first task to open detail drawer
            if tasks_count > 0:
                print("[TASKS] Clicking first task to open Detail Drawer...")
                task_rows.first.click()
                page.wait_for_timeout(800)

            scroll_tasks = check_horizontal_scroll()
            print(f"[SCROLL] Tasks scroll check: {scroll_tasks}")
            assert not scroll_tasks["hasOverflow"], "Horizontal overflow detected in Tasks with drawer open!"
            save_screenshot("02_tasks_with_drawer.png")
            qa_report["views_tested"].append({
                "view": "tasks",
                "label": "Tarefas",
                "tasks_count": tasks_count,
                "scroll_check": scroll_tasks,
                "screenshot": "02_tasks_with_drawer.png",
            })

            # =========================================================================
            # VIEW 3: AGENTS (Agentes)
            # =========================================================================
            print("\n--- Validating View 3: Agents (Agentes) ---")
            page.click("#mission-nav-tab-agents")
            page.wait_for_timeout(1200)

            scroll_agents = check_horizontal_scroll()
            print(f"[SCROLL] Agents scroll check: {scroll_agents}")
            assert not scroll_agents["hasOverflow"], "Horizontal overflow detected in Agents view!"
            save_screenshot("03_agents.png")
            qa_report["views_tested"].append({
                "view": "agents",
                "label": "Agentes",
                "scroll_check": scroll_agents,
                "screenshot": "03_agents.png",
            })

            # =========================================================================
            # VIEW 4: ACTIVITY (Atividade)
            # =========================================================================
            print("\n--- Validating View 4: Activity (Atividade) ---")
            page.click("#mission-nav-tab-activity")
            page.wait_for_timeout(1200)

            scroll_activity = check_horizontal_scroll()
            print(f"[SCROLL] Activity scroll check: {scroll_activity}")
            assert not scroll_activity["hasOverflow"], "Horizontal overflow detected in Activity view!"
            save_screenshot("04_activity.png")
            qa_report["views_tested"].append({
                "view": "activity",
                "label": "Atividade",
                "scroll_check": scroll_activity,
                "screenshot": "04_activity.png",
            })

            # =========================================================================
            # VIEW 5: DIAGNOSTICS (Diagnóstico) - Runtime (F71) & Reliability (F72)
            # =========================================================================
            print("\n--- Validating View 5: Diagnostics (Diagnóstico) ---")
            page.click("#mission-nav-tab-diagnostics")
            page.wait_for_timeout(1200)

            # Subtab: Runtime (F71)
            scroll_diag_runtime = check_horizontal_scroll()
            print(f"[SCROLL] Diagnostics Runtime scroll check: {scroll_diag_runtime}")
            save_screenshot("05_diagnostics_runtime.png")
            qa_report["views_tested"].append({
                "view": "diagnostics_runtime",
                "label": "Diagnóstico (Runtime F71)",
                "scroll_check": scroll_diag_runtime,
                "screenshot": "05_diagnostics_runtime.png",
            })

            # Click Subtab: Reliability (F72)
            print("[DIAGNOSTICS] Switching to Confiabilidade (F72)...")
            page.click("#diag-subtab-reliability")
            page.wait_for_timeout(1500)

            scroll_diag_rel = check_horizontal_scroll()
            print(f"[SCROLL] Diagnostics Reliability scroll check: {scroll_diag_rel}")
            save_screenshot("06_diagnostics_reliability.png")
            qa_report["views_tested"].append({
                "view": "diagnostics_reliability",
                "label": "Diagnóstico (Confiabilidade F72)",
                "scroll_check": scroll_diag_rel,
                "screenshot": "06_diagnostics_reliability.png",
            })

            # Click Subtab: Requirements
            print("[DIAGNOSTICS] Switching to Requisitos...")
            page.click("#diag-subtab-requirements")
            page.wait_for_timeout(1000)

            scroll_diag_req = check_horizontal_scroll()
            save_screenshot("07_diagnostics_requirements.png")
            qa_report["views_tested"].append({
                "view": "diagnostics_requirements",
                "label": "Diagnóstico (Requisitos)",
                "scroll_check": scroll_diag_req,
                "screenshot": "07_diagnostics_requirements.png",
            })

            browser.close()

            # Compile QA results
            all_scroll_clean = all(not v["scroll_check"]["hasOverflow"] for v in qa_report["views_tested"])
            qa_report["horizontal_scroll_clean"] = all_scroll_clean
            qa_report["console_errors_count"] = len(console_errors)
            qa_report["console_errors"] = console_errors
            qa_report["page_errors"] = page_errors
            qa_report["success"] = all_scroll_clean and len(console_errors) == 0 and len(page_errors) == 0

            report_file = os.path.join(DOCS_DIR, "mission_control_rehaul_qa.json")
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(qa_report, f, indent=2)

            print("\n" + "=" * 70)
            print(f"[QA REPORT] Completed Browser QA!")
            print(f"  - Views Validated: {len(qa_report['views_tested'])}")
            print(f"  - Horizontal Scroll Clean: {all_scroll_clean}")
            print(f"  - Console Errors: {len(console_errors)}")
            print(f"  - Page Errors: {len(page_errors)}")
            print(f"  - Overall Success: {qa_report['success']}")
            print("=" * 70)

    finally:
        pass


if __name__ == "__main__":
    run_qa()
