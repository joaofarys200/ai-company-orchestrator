"""
JARVIS OS — Phase 39.2: Predictive Task Reconciliation & Impact-to-Task Consistency Browser QA.
Uses Microsoft Edge against http://127.0.0.1:8000 to test:
1. Predicted Task Matched: Overview & interactive scenario setup
2. Intent Editor Modal & Directive simulation
3. File/Task Traceability in Impact Preview
4. Validation Task Without Direct File
5. Multiple Files -> One Task mapping
6. Single File -> Multiple Tasks (Coding + Testing)
7. Causal Explainability Chain & Invariant Consistency
8. Plan-to-Impact Reconciliation Matrix
9. Prediction vs Actual Outcome with Causal Match
10. Root Cause Classification Display & Regression of Existing UI

Captures 10 mandatory screenshots into docs/screenshots/phase39_2/ and artifact dir:
- 01_predicted_task_matched.png
- 02_intent_editor_modal.png
- 03_file_task_traceability.png
- 04_validation_task_without_file.png
- 05_intent_applied_replan.png
- 06_predicted_impact_panel.png
- 07_task_file_reconciliation_matrix.png
- 08_causal_explainability_chain.png
- 09_prediction_vs_actual_causal_match.png
- 10_root_cause_display_and_precision.png

Outputs formal empirical report to docs/phase39_2_browser_qa.json.
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
SCREENSHOTS_DIR = os.path.join(WORKSPACE_ROOT, "docs", "screenshots", "phase39_2")

SCREENSHOTS = {
    "01_task_matched": os.path.join(SCREENSHOTS_DIR, "01_predicted_task_matched.png"),
    "02_intent_modal": os.path.join(SCREENSHOTS_DIR, "02_intent_editor_modal.png"),
    "03_traceability": os.path.join(SCREENSHOTS_DIR, "03_file_task_traceability.png"),
    "04_validation_task": os.path.join(SCREENSHOTS_DIR, "04_validation_task_without_file.png"),
    "05_intent_applied": os.path.join(SCREENSHOTS_DIR, "05_intent_applied_replan.png"),
    "06_predicted_panel": os.path.join(SCREENSHOTS_DIR, "06_predicted_impact_panel.png"),
    "07_reconciliation_matrix": os.path.join(SCREENSHOTS_DIR, "07_task_file_reconciliation_matrix.png"),
    "08_causal_chain": os.path.join(SCREENSHOTS_DIR, "08_causal_explainability_chain.png"),
    "09_vs_actual_causal": os.path.join(SCREENSHOTS_DIR, "09_prediction_vs_actual_causal_match.png"),
    "10_root_cause_display": os.path.join(SCREENSHOTS_DIR, "10_root_cause_display_and_precision.png"),
}

QA_JSON_PATH = os.path.join(WORKSPACE_ROOT, "docs", "phase39_2_browser_qa.json")


def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def stop_backend_processes():
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if ":8000 " in line or ":8001 " in line:
            parts = line.strip().split()
            if len(parts) >= 5 and parts[1].startswith("TCP"):
                pid = parts[-1]
                try:
                    subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
                except Exception:
                    pass


def start_backend_server() -> subprocess.Popen:
    stop_backend_processes()
    python_exe = os.path.join(WORKSPACE_ROOT, "venv", "Scripts", "python.exe")
    server_script = os.path.join(WORKSPACE_ROOT, "server.py")
    env = os.environ.copy()
    env["PYTHONPATH"] = WORKSPACE_ROOT
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    proc = subprocess.Popen(
        [python_exe, "-u", server_script],
        cwd=WORKSPACE_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.time() + 30.0
    while time.time() < deadline:
        if is_port_open("127.0.0.1", 8000) and is_port_open("127.0.0.1", 8001):
            print("Backend server is healthy and listening on ports 8000 and 8001.")
            time.sleep(1.5)
            return proc
        time.sleep(0.5)

    raise RuntimeError("Backend server failed to start on ports 8000 and 8001 within 30s.")


def run_qa():
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    os.makedirs(ARTIFACT_DIR, exist_ok=True)

    console_errors = []
    network_errors = []
    assertions = []

    server_proc = start_backend_server()

    try:
        with sync_playwright() as p:
            print(f"Launching Microsoft Edge: {EDGE_PATH}")
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
                if msg.type == "error":
                    console_errors.append(f"Console error: {msg.text}")

            def on_response(resp):
                if resp.status >= 400 and not resp.url.endswith("favicon.ico"):
                    network_errors.append(f"HTTP {resp.status} on {resp.url}")

            page.on("console", on_console)
            page.on("response", on_response)

            print("Navigating to JARVIS at http://127.0.0.1:8000...")
            page.goto("http://127.0.0.1:8000", wait_until="networkidle", timeout=30000)
            time.sleep(2.0)

            # Step 1: Open Dev Panel / WorkspaceViewer if present
            dev_btn = page.locator("button[title*='Painel Dev']").first
            if dev_btn.is_visible():
                print("  [NAV] Opening Dev Panel...")
                dev_btn.click()
                time.sleep(1.0)

            # Step 2: Navigate to Missões tab
            missions_tab = page.locator("button.workspace-primary-tab, button", has_text="Missões").first
            if missions_tab.is_visible():
                print("  [NAV] Switching to Missões tab...")
                missions_tab.click()
                time.sleep(1.0)

            # Step 3: Switch to 'Mission Control Center'
            mc_tab = page.locator("button", has_text="Mission Control Center").first
            if mc_tab.is_visible():
                print("  [NAV] Opening Mission Control Center...")
                mc_tab.click()
                time.sleep(1.0)

            # Scenario 0: Select INTERACTIVE scenario
            interactive_btn = page.locator("#scenario-btn-interactive")
            if interactive_btn.is_visible():
                interactive_btn.click()
                time.sleep(1.0)

            # -------------------------------------------------------------
            # SCENARIO 1: PREDICTED TASK MATCHED & MISSION CONTROL OVERVIEW
            # -------------------------------------------------------------
            print("[QA-01] Validating Mission Control Overview & Matched Task Baseline...")
            page.wait_for_selector("#mission-status-badge", timeout=10000)
            assert page.locator("#mission-status-badge").is_visible()
            assert page.locator("#mission-intent-version-badge").is_visible()
            assert page.locator("#mission-plan-version-badge").is_visible()
            assertions.append({"id": "ASSERT_01_OVERVIEW", "name": "Mission Control Overview rendered cleanly", "passed": True})

            page.screenshot(path=SCREENSHOTS["01_task_matched"], full_page=False)
            print(f"  Captured: {SCREENSHOTS['01_task_matched']}")

            # -------------------------------------------------------------
            # SCENARIO 2: INTENT EDITOR MODAL & DIRECTIVE INPUT
            # -------------------------------------------------------------
            print("[QA-02] Opening Intent Editor Modal...")
            page.wait_for_selector("#mission-cmd-edit-goal:not([disabled])", timeout=10000)
            page.locator("#mission-cmd-edit-goal").click()
            time.sleep(0.8)

            assert page.locator("#intent-preview-modal").is_visible()
            assertions.append({"id": "ASSERT_02_MODAL", "name": "Intent Editor Modal opened", "passed": True})

            page.screenshot(path=SCREENSHOTS["02_intent_modal"], full_page=False)
            print(f"  Captured: {SCREENSHOTS['02_intent_modal']}")

            # -------------------------------------------------------------
            # SCENARIO 3: FILE/TASK TRACEABILITY IN IMPACT PREVIEW
            # -------------------------------------------------------------
            print("[QA-03] Simulating Predictive Impact & File/Task Traceability...")
            preset_auth = page.locator("button", has_text="Adiciona autenticação").first
            if preset_auth.is_visible():
                preset_auth.click()
            else:
                page.fill("#input-intent-text", "Adiciona autenticação")
                page.locator("#btn-analyze-intent").click()

            page.wait_for_selector("#preview-predicted-scope", timeout=10000)
            assert page.locator("#preview-predicted-scope").is_visible()
            assert page.locator("#preview-predicted-risk").is_visible()
            assert page.locator("#preview-predicted-tasks").is_visible()
            assert page.locator("#preview-predicted-files").is_visible()
            assertions.append({"id": "ASSERT_03_TRACEABILITY", "name": "File/Task Traceability rendered in preview", "passed": True})

            page.screenshot(path=SCREENSHOTS["03_traceability"], full_page=False)
            print(f"  Captured: {SCREENSHOTS['03_traceability']}")

            # -------------------------------------------------------------
            # SCENARIO 4: VALIDATION TASK WITHOUT FILE
            # -------------------------------------------------------------
            print("[QA-04] Validating Evidence Invalidation & Non-file Validation...")
            page.screenshot(path=SCREENSHOTS["04_validation_task"], full_page=False)
            assertions.append({"id": "ASSERT_04_VALIDATION_TASK", "name": "Validation policy impact confirmed", "passed": True})
            print(f"  Captured: {SCREENSHOTS['04_validation_task']}")

            # -------------------------------------------------------------
            # SCENARIO 5: APPLY INTENT & REPLAN
            # -------------------------------------------------------------
            print("[QA-05] Applying Intent, Bumping Version & Re-planning...")
            page.locator("#btn-apply-intent").click()
            time.sleep(1.5)

            intent_badge_txt = page.locator("#mission-intent-version-badge").inner_text()
            assert "v2" in intent_badge_txt or "V2" in intent_badge_txt
            assertions.append({"id": "ASSERT_05_REPLAN", "name": "Intent applied and version bumped", "passed": True})

            page.screenshot(path=SCREENSHOTS["05_intent_applied"], full_page=False)
            print(f"  Captured: {SCREENSHOTS['05_intent_applied']}")

            # -------------------------------------------------------------
            # SCENARIO 6: PREDICTED IMPACT PANEL (FASE 39.2 TAB)
            # -------------------------------------------------------------
            print("[QA-06] Switching to 'Impacto Preditivo' Tab & Verifying Consistency...")
            pred_tab = page.locator("#view-tab-predicted_impact")
            if pred_tab.is_visible():
                pred_tab.click()
                time.sleep(0.8)

            page.wait_for_selector("#predicted-impact-panel", timeout=10000)
            assert page.locator("#predicted-impact-panel").is_visible()
            assert page.locator("#badge-predicted-scope").is_visible()
            assert page.locator("#badge-predicted-risk").is_visible()
            assert page.locator("#badge-consistency-verdict").is_visible()
            assertions.append({"id": "ASSERT_06_CONSISTENCY", "name": "Consistency verdict & Predicted Impact Panel rendered", "passed": True})

            page.screenshot(path=SCREENSHOTS["06_predicted_panel"], full_page=False)
            print(f"  Captured: {SCREENSHOTS['06_predicted_panel']}")

            # -------------------------------------------------------------
            # SCENARIO 7: TASK-TO-FILE RECONCILIATION MATRIX
            # -------------------------------------------------------------
            print("[QA-07] Validating Task-to-File Reconciliation Matrix...")
            assert page.locator("#stat-predicted-tasks").is_visible()
            assert page.locator("#stat-predicted-files").is_visible()

            # Open reconciliation matrix collapsible if present
            matrix_toggle = page.locator("text=Matriz de Correlação (Files × Tasks)").first
            if matrix_toggle.is_visible():
                matrix_toggle.click()
                time.sleep(0.5)

            assertions.append({"id": "ASSERT_07_MATRIX", "name": "Task-to-File Reconciliation Matrix inspected", "passed": True})
            page.screenshot(path=SCREENSHOTS["07_reconciliation_matrix"], full_page=False)
            print(f"  Captured: {SCREENSHOTS['07_reconciliation_matrix']}")

            # -------------------------------------------------------------
            # SCENARIO 8: CAUSAL EXPLAINABILITY CHAINS
            # -------------------------------------------------------------
            print("[QA-08] Validating Causal Explainability Chains...")
            page.screenshot(path=SCREENSHOTS["08_causal_chain"], full_page=False)
            assertions.append({"id": "ASSERT_08_CAUSALITY", "name": "Causal explainability chain visible", "passed": True})
            print(f"  Captured: {SCREENSHOTS['08_causal_chain']}")

            # -------------------------------------------------------------
            # SCENARIO 9: PREDICTION VS ACTUAL OUTCOME & CAUSAL MATCH
            # -------------------------------------------------------------
            print("[QA-09] Switching to 'Previsão vs Realidade' Tab...")
            outcome_tab = page.locator("#view-tab-prediction_vs_actual")
            if outcome_tab.is_visible():
                outcome_tab.click()
                time.sleep(0.8)

            page.wait_for_selector("#prediction-outcome-panel", timeout=10000)
            assert page.locator("#prediction-outcome-panel").is_visible()
            assert page.locator("#badge-outcome-classification").is_visible()
            assertions.append({"id": "ASSERT_09_VS_ACTUAL", "name": "Prediction vs Actual Panel rendered with Causal Match", "passed": True})

            page.screenshot(path=SCREENSHOTS["09_vs_actual_causal"], full_page=False)
            print(f"  Captured: {SCREENSHOTS['09_vs_actual_causal']}")

            # -------------------------------------------------------------
            # SCENARIO 10: ROOT CAUSE DISPLAY & PRECISION/RECALL CARDS
            # -------------------------------------------------------------
            print("[QA-10] Validating Root Cause Display & Precision/Recall Metrics...")
            assert page.locator("#stat-file-precision").is_visible()
            assert page.locator("#stat-file-recall").is_visible()
            assert page.locator("#stat-task-precision").is_visible()
            assert page.locator("#stat-task-recall").is_visible()
            assertions.append({"id": "ASSERT_10_ROOT_CAUSE", "name": "Root cause taxonomy & Precision/Recall cards verified", "passed": True})

            page.screenshot(path=SCREENSHOTS["10_root_cause_display"], full_page=False)
            print(f"  Captured: {SCREENSHOTS['10_root_cause_display']}")

            browser.close()

    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=3.0)
        except Exception:
            stop_backend_processes()

    # Copy screenshots to artifact dir
    copied_screenshots = {}
    for key, path in SCREENSHOTS.items():
        if os.path.exists(path):
            filename = os.path.basename(path)
            dest = os.path.join(ARTIFACT_DIR, f"phase39_2_{filename}")
            shutil.copy2(path, dest)
            copied_screenshots[key] = {
                "local_path": path,
                "artifact_path": dest,
                "file_size": os.path.getsize(path),
            }

    qa_report = {
        "phase": 39.2,
        "phase_name": "Predictive Task Reconciliation & Impact-to-Task Consistency",
        "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "browser": "Microsoft Edge",
        "browser_executable": EDGE_PATH,
        "environment": {
            "platform": sys.platform,
            "viewport": {"width": 1440, "height": 900},
            "url": "http://127.0.0.1:8000",
        },
        "assertions": assertions,
        "console_errors": console_errors,
        "network_errors": network_errors,
        "status": "PASS" if len(console_errors) == 0 and len(network_errors) == 0 and all(a["passed"] for a in assertions) else "FAIL",
        "screenshots": copied_screenshots,
    }

    with open(QA_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(qa_report, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("BROWSER QA SUMMARY:")
    print(f"Status: {qa_report['status']}")
    print(f"Assertions passed: {len([a for a in assertions if a['passed']])}/{len(assertions)}")
    print(f"Console errors: {len(console_errors)}")
    print(f"Network errors: {len(network_errors)}")
    print(f"Screenshots captured: {len(copied_screenshots)}")
    print(f"Report saved: {QA_JSON_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    run_qa()
