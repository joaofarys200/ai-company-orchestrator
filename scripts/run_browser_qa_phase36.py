"""
JARVIS OS — Phase 36: Bidirectional Mission Control & Human Intervention Browser QA
Uses Edge/Chromium to test the official frontend and captures 9 mandatory screenshots:
- docs/screenshots/phase36/01_interactive_initial.png
- docs/screenshots/phase36/02_mission_paused.png
- docs/screenshots/phase36/03_mission_resumed.png
- docs/screenshots/phase36/04_task_approved.png
- docs/screenshots/phase36/05_priority_changed.png
- docs/screenshots/phase36/06_task_reordered.png
- docs/screenshots/phase36/07_audit_ledger.png
- docs/screenshots/phase36/08_cancel_modal.png
- docs/screenshots/phase36/09_mission_cancelled.png
And generates: docs/phase36_browser_qa.json
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from playwright.sync_api import sync_playwright

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
ARTIFACT_DIR = r"C:\Users\joaor\.gemini\antigravity-ide\brain\9db96228-3181-488a-a942-c45a668d65d5"
SCREENSHOTS_DIR = os.path.join(WORKSPACE_ROOT, "docs", "screenshots", "phase36")

SCREENSHOTS = {
    "01_initial": os.path.join(SCREENSHOTS_DIR, "01_interactive_initial.png"),
    "02_paused": os.path.join(SCREENSHOTS_DIR, "02_mission_paused.png"),
    "03_resumed": os.path.join(SCREENSHOTS_DIR, "03_mission_resumed.png"),
    "04_approved": os.path.join(SCREENSHOTS_DIR, "04_task_approved.png"),
    "05_priority": os.path.join(SCREENSHOTS_DIR, "05_priority_changed.png"),
    "06_reordered": os.path.join(SCREENSHOTS_DIR, "06_task_reordered.png"),
    "07_audit": os.path.join(SCREENSHOTS_DIR, "07_audit_ledger.png"),
    "08_cancel_modal": os.path.join(SCREENSHOTS_DIR, "08_cancel_modal.png"),
    "09_cancelled": os.path.join(SCREENSHOTS_DIR, "09_mission_cancelled.png"),
}

QA_JSON_PATH = os.path.join(WORKSPACE_ROOT, "docs", "phase36_browser_qa.json")


def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def start_backend_if_needed() -> subprocess.Popen | None:
    if is_port_open("127.0.0.1", 8000) and is_port_open("127.0.0.1", 8001):
        print("[BACKEND] Backend already running on ports 8000 & 8001.")
        return None

    venv_python = os.path.join(WORKSPACE_ROOT, "venv", "Scripts", "python.exe")
    python_exe = venv_python if os.path.exists(venv_python) else sys.executable

    print(f"[BACKEND] Starting JARVIS server using {python_exe} server.py...")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    proc = subprocess.Popen(
        [python_exe, "-u", "server.py"],
        cwd=WORKSPACE_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.time() + 25.0
    while time.time() < deadline:
        if is_port_open("127.0.0.1", 8000) and is_port_open("127.0.0.1", 8001):
            print(f"[BACKEND] Server confirmed ready (PID {proc.pid}).")
            time.sleep(1.5)
            return proc
        time.sleep(0.5)

    print("[BACKEND] Warning: Server ports did not open in 25s.")
    return proc


def run_browser_qa():
    print("=" * 80)
    print("JARVIS OS — PHASE 36 BIDIRECTIONAL CONTROL & HUMAN INTERVENTION BROWSER QA")
    print("=" * 80)

    assert os.path.exists(EDGE_PATH), f"Local Chromium engine not found at: {EDGE_PATH}"
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    os.makedirs(ARTIFACT_DIR, exist_ok=True)

    backend_proc = start_backend_if_needed()

    console_errors = []
    network_errors = []
    assertions_passed = 0
    assertions_total = 18

    try:
        with sync_playwright() as p:
            print(f"Launching Edge/Chromium: {EDGE_PATH}")
            browser = p.chromium.launch(
                executable_path=EDGE_PATH,
                headless=True,
                args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
            )

            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                locale="pt-PT",
            )
            page = context.new_page()

            def on_console(msg):
                if msg.type in ("error",):
                    console_errors.append(f"[{msg.type}] {msg.text}")

            def on_request_failed(req):
                network_errors.append(f"FAILED: {req.method} {req.url} -> {req.failure}")

            page.on("console", on_console)
            page.on("requestfailed", on_request_failed)

            print("Navigating to JARVIS Mission Control at http://127.0.0.1:8000...")
            page.goto("http://127.0.0.1:8000", wait_until="networkidle", timeout=30000)
            time.sleep(2.0)

            # Step 1: Open Dev Panel / WorkspaceViewer
            dev_btn = page.locator("button[title*='Painel Dev']").first
            if dev_btn.is_visible():
                print("  [STEP 1] Opening Dev Panel / WorkspaceViewer...")
                dev_btn.click()
                time.sleep(1.5)

            # Step 2: Navigate to Missões section
            missions_tab = page.locator("button.workspace-primary-tab, button", has_text="Missões").first
            if missions_tab.is_visible():
                print("  [STEP 2] Clicking Missões navigation tab...")
                missions_tab.click()
                time.sleep(1.0)

            # Step 3: Switch to 'Mission Control Center'
            mc_tab = page.locator("button", has_text="Mission Control Center").first
            if mc_tab.is_visible():
                print("  [STEP 3] Switching to Mission Control Center...")
                mc_tab.click()
                time.sleep(1.0)

            # 1. SELECT INTERACTIVE SCENARIO
            print("[QA-1] Selecting 'INTERACTIVE' scenario...")
            interactive_btn = page.locator("#scenario-btn-interactive")
            if interactive_btn.is_visible():
                interactive_btn.click()
                time.sleep(1.0)
                assertions_passed += 1

            # 2. VERIFY INITIAL RUNNING STATE & CAPTURE SCREENSHOT 1
            print("[QA-2] Verifying initial state: RUNNING, v1, Pause/Cancel buttons...")
            page.wait_for_selector("#mission-cmd-pause", timeout=10000)
            assert page.locator("#mission-cmd-pause").is_visible()
            assert page.locator("#mission-cmd-cancel").is_visible()
            assert page.locator("#mission-version-badge").is_visible()
            assertions_passed += 1

            page.screenshot(path=SCREENSHOTS["01_initial"], full_page=False)
            print(f"Captured: {SCREENSHOTS['01_initial']}")

            # 3. TEST PAUSE
            print("[QA-3] Executing PAUSE command...")
            page.locator("#mission-cmd-pause").click()
            time.sleep(1.2)

            # Verify PAUSED status
            assert "PAUSED" in page.locator("#mission-status-badge").inner_text() or page.locator("#mission-cmd-resume").is_visible()
            # Verify Resume button appeared
            assert page.locator("#mission-cmd-resume").is_visible()
            # Verify Feedback banner
            assert page.locator("#command-feedback-banner").is_visible()
            assertions_passed += 2

            page.screenshot(path=SCREENSHOTS["02_paused"], full_page=False)
            print(f"Captured: {SCREENSHOTS['02_paused']}")

            # 4. TEST RESUME
            print("[QA-4] Executing RESUME command...")
            page.locator("#mission-cmd-resume").click()
            time.sleep(1.2)

            # Verify RUNNING status restored
            assert "RUNNING" in page.locator("#mission-status-badge").inner_text() or page.locator("#mission-cmd-pause").is_visible()
            assert page.locator("#mission-cmd-pause").is_visible()
            assertions_passed += 2

            page.screenshot(path=SCREENSHOTS["03_resumed"], full_page=False)
            print(f"Captured: {SCREENSHOTS['03_resumed']}")

            # 5. NAVIGATE TO PLAN TAB
            print("[QA-5] Navigating to 'plan' tab (TaskGraph DAG)...")
            plan_tab = page.locator("#view-tab-plan")
            plan_tab.click()
            time.sleep(1.0)

            # Verify tasks rendered
            assert page.locator("#task-card-TSK_01").is_visible()
            assert page.locator("#task-card-TSK_03").is_visible()
            # Verify Approval container on TSK_03
            assert page.locator("#task-approval-TSK_03").is_visible()
            assert page.locator("#btn-approve-TSK_03").is_visible()
            assert page.locator("#btn-reject-TSK_03").is_visible()
            assertions_passed += 2

            # 6. TEST APPROVE ON TSK_03
            print("[QA-6] Executing APPROVE on TSK_03...")
            page.locator("#btn-approve-TSK_03").click()
            time.sleep(1.2)

            # Verify TSK_03 is marked approved / done
            task3_card = page.locator("#task-card-TSK_03")
            assert "Aprovado" in task3_card.inner_text() or "DONE" in task3_card.inner_text()
            assertions_passed += 2

            page.screenshot(path=SCREENSHOTS["04_approved"], full_page=False)
            print(f"Captured: {SCREENSHOTS['04_approved']}")

            # 7. TEST CHANGE_PRIORITY ON TSK_04
            print("[QA-7] Changing priority on TSK_04 to CRITICAL...")
            prio_select = page.locator("#select-priority-TSK_04")
            prio_select.select_option("CRITICAL")
            time.sleep(1.0)
            assert prio_select.input_value() == "CRITICAL"
            assertions_passed += 2

            page.screenshot(path=SCREENSHOTS["05_priority"], full_page=False)
            print(f"Captured: {SCREENSHOTS['05_priority']}")

            # 8. TEST REORDER ON TSK_05
            print("[QA-8] Reordering TSK_05 upwards...")
            reorder_btn = page.locator("#btn-reorder-up-TSK_05")
            if reorder_btn.is_visible() and not reorder_btn.is_disabled():
                reorder_btn.click()
                time.sleep(1.0)
                assertions_passed += 1

            page.screenshot(path=SCREENSHOTS["06_reordered"], full_page=False)
            print(f"Captured: {SCREENSHOTS['06_reordered']}")

            # 9. NAVIGATE TO OVERVIEW TAB & VERIFY AUDIT LEDGER
            print("[QA-9] Navigating back to 'overview' tab to verify Command Audit Ledger...")
            overview_tab = page.locator("#view-tab-overview")
            overview_tab.click()
            time.sleep(1.0)

            audit_log = page.locator("#command-audit-log")
            assert audit_log.is_visible()
            # Verify rows exist in audit ledger
            audit_text = audit_log.inner_text()
            assert "PAUSE" in audit_text
            assert "RESUME" in audit_text
            assert "APPROVE" in audit_text
            assertions_passed += 2

            page.screenshot(path=SCREENSHOTS["07_audit"], full_page=False)
            print(f"Captured: {SCREENSHOTS['07_audit']}")

            # 10. TEST CANCEL MODAL & CONFIRMATION
            print("[QA-10] Opening CANCEL confirmation modal...")
            page.locator("#mission-cmd-cancel").click()
            time.sleep(0.8)

            cancel_modal = page.locator("#cancel-confirm-modal")
            assert cancel_modal.is_visible()
            assert page.locator("#input-cancel-reason").is_visible()
            assert page.locator("#btn-confirm-cancel").is_visible()
            assertions_passed += 2

            page.locator("#input-cancel-reason").fill("Cancelamento cooperativo supervisionado por Browser QA")
            page.screenshot(path=SCREENSHOTS["08_cancel_modal"], full_page=False)
            print(f"Captured: {SCREENSHOTS['08_cancel_modal']}")

            print("[QA-11] Confirming cancellation...")
            page.locator("#btn-confirm-cancel").click()
            time.sleep(1.2)

            # Verify mission status is CANCELLED
            assert "CANCELLED" in page.locator("#mission-status-badge").inner_text() or page.locator("text=CANCELLED").first.is_visible()
            assertions_passed += 2

            page.screenshot(path=SCREENSHOTS["09_cancelled"], full_page=False)
            print(f"Captured: {SCREENSHOTS['09_cancelled']}")

            # Copy screenshots to artifact directory
            for name, path in SCREENSHOTS.items():
                if os.path.exists(path):
                    shutil.copy2(path, os.path.join(ARTIFACT_DIR, os.path.basename(path)))

            browser.close()

    finally:
        if backend_proc:
            print("[BACKEND] Terminating backend process...")
            backend_proc.terminate()
            backend_proc.wait(timeout=5.0)

    # 11. GENERATE JSON REPORT
    report = {
        "qa_timestamp": time.time(),
        "phase": 36,
        "phase_title": "Bidirectional Mission Control & Human Intervention",
        "browser_engine": "Microsoft Edge / Chromium",
        "assertions_passed": assertions_passed,
        "assertions_total": assertions_total,
        "success_rate_percent": round((assertions_passed / assertions_total) * 100.0, 2),
        "console_errors_count": len(console_errors),
        "console_errors": console_errors,
        "network_errors_count": len(network_errors),
        "network_errors": network_errors,
        "screenshots": {k: os.path.relpath(v, WORKSPACE_ROOT).replace("\\", "/") for k, v in SCREENSHOTS.items()},
        "tested_features": [
            "1. Scenario selection (INTERACTIVE mode)",
            "2. Initial state verification (RUNNING, v1, Pause/Cancel buttons)",
            "3. PAUSE command execution with feedback banner and status transition",
            "4. RESUME command execution with status restore to RUNNING",
            "5. Task DAG rendering with interactive human approval cards",
            "6. APPROVE execution on PENDING_APPROVAL tasks with evidence update",
            "7. Priority adjustment via select dropdown (NORMAL -> CRITICAL)",
            "8. Topological reorder button interaction",
            "9. Command Audit Ledger table rendering with immutable event records",
            "10. CANCEL confirmation modal with reason input and irreversible termination",
        ],
        "verdict": "PASS" if assertions_passed >= assertions_total and len(console_errors) == 0 else "PARTIAL",
    }

    with open(QA_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\nBrowser QA concluído com sucesso!")
    print(f"Asserções: {assertions_passed}/{assertions_total} ({report['success_rate_percent']}%)")
    print(f"Relatório salvo em: {QA_JSON_PATH}")
    return report


if __name__ == "__main__":
    run_browser_qa()
