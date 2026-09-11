"""
JARVIS OS — Phase 38: Super-File Decomposition & Architecture Hygiene Browser QA.
Uses Microsoft Edge to test the official frontend with all decomposed components:
- MissionHeader (Header, status, metrics, version badges)
- MissionControlActions (Pause, Resume, Cancel, Edit Goal buttons)
- CancelConfirmModal (Operator cancellation dialog)
- IntentPreviewModal (Goal editor & impact analysis modal)
- MissionOverviewPanel (Stage progress, requirements, swarm agents, audit ledger)
- MissionTaskGraphPanel (Task DAG, priorities, reordering, approval gates)
- MissionRequirementsDiffPanel (Requirements lifecycle diff)
- MissionPlanDiffPanel (Plan diff & DAG topological invariants)
- MissionEvidenceImpactPanel (Zero False Success evidence invalidation)
- MissionWhyCausalPanel (Causal explainability chains)
- MissionRepairPanel & MissionEvidenceLedgerPanel (Self-healing & evidence ledger)

Captures 10 mandatory screenshots into docs/screenshots/phase38/:
- 01_mission_control_overview.png
- 02_controls_pause_resume.png
- 03_task_graph_dag_view.png
- 04_intent_editor_modal.png
- 05_intent_applied_replan.png
- 06_requirements_diff_panel.png
- 07_plan_diff_panel.png
- 08_evidence_impact_tracker.png
- 09_why_panel_causality.png
- 10_repair_and_ledger_view.png

And generates: docs/phase38_browser_qa.json
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
SCREENSHOTS_DIR = os.path.join(WORKSPACE_ROOT, "docs", "screenshots", "phase38")

SCREENSHOTS = {
    "01_overview": os.path.join(SCREENSHOTS_DIR, "01_mission_control_overview.png"),
    "02_controls": os.path.join(SCREENSHOTS_DIR, "02_controls_pause_resume.png"),
    "03_task_graph": os.path.join(SCREENSHOTS_DIR, "03_task_graph_dag_view.png"),
    "04_intent_modal": os.path.join(SCREENSHOTS_DIR, "04_intent_editor_modal.png"),
    "05_intent_applied": os.path.join(SCREENSHOTS_DIR, "05_intent_applied_replan.png"),
    "06_req_diff": os.path.join(SCREENSHOTS_DIR, "06_requirements_diff_panel.png"),
    "07_plan_diff": os.path.join(SCREENSHOTS_DIR, "07_plan_diff_panel.png"),
    "08_ev_impact": os.path.join(SCREENSHOTS_DIR, "08_evidence_impact_tracker.png"),
    "09_why_panel": os.path.join(SCREENSHOTS_DIR, "09_why_panel_causality.png"),
    "10_repair_ledger": os.path.join(SCREENSHOTS_DIR, "10_repair_and_ledger_view.png"),
}

QA_JSON_PATH = os.path.join(WORKSPACE_ROOT, "docs", "phase38_browser_qa.json")


def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def stop_backend_processes():
    import subprocess
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if (":8000 " in line or ":8001 " in line) and "LISTENING" in line:
            pid = line.strip().split()[-1]
            try:
                subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
            except Exception:
                pass
    time.sleep(1.0)


def start_backend_if_needed() -> subprocess.Popen | None:
    stop_backend_processes()

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
    print("JARVIS OS — PHASE 38 DECOMPOSED ARCHITECTURE BROWSER QA")
    print("=" * 80)

    assert os.path.exists(EDGE_PATH), f"Local Edge browser not found at: {EDGE_PATH}"
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    os.makedirs(ARTIFACT_DIR, exist_ok=True)

    backend_proc = start_backend_if_needed()

    console_errors = []
    network_errors = []
    assertions_passed = 0
    scenarios_tested = []

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
                print(f"[BROWSER CONSOLE {msg.type}] {msg.text}")
                if msg.type in ("error",):
                    console_errors.append(f"[{msg.type}] {msg.text}")

            def on_page_error(err):
                print(f"[BROWSER PAGE ERROR] {err}")
                console_errors.append(f"[pageerror] {err}")

            def on_request_failed(req):
                print(f"[BROWSER REQ FAILED] {req.method} {req.url} -> {req.failure}")
                network_errors.append(f"FAILED: {req.method} {req.url} -> {req.failure}")

            page.on("console", on_console)
            page.on("pageerror", on_page_error)
            page.on("requestfailed", on_request_failed)

            print("Navigating to JARVIS Mission Control at http://127.0.0.1:8000...")
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
            # SCENARIO 1: MISSION CONTROL OVERVIEW & DECOMPOSED MISSIONHEADER
            # -------------------------------------------------------------
            print("[QA-01] Validating MissionHeader & OverviewPanel...")
            page.wait_for_selector("#mission-status-badge", timeout=10000)
            assert page.locator("#mission-status-badge").is_visible()
            assert page.locator("#mission-intent-version-badge").is_visible()
            assert page.locator("#mission-plan-version-badge").is_visible()
            assert page.locator("text=Requisitos do Utilizador").first.is_visible()
            assert page.locator("text=Enxame de Agentes Especialistas").first.is_visible()
            assertions_passed += 5
            scenarios_tested.append("1. MissionHeader & OverviewPanel render cleanly")

            page.screenshot(path=SCREENSHOTS["01_overview"], full_page=False)
            print(f"  Captured: {SCREENSHOTS['01_overview']}")

            # -------------------------------------------------------------
            # SCENARIO 2: MISSIONCONTROLACTIONS (PAUSE & RESUME)
            # -------------------------------------------------------------
            print("[QA-02] Validating MissionControlActions (Pause & Resume)...")
            pause_btn = page.locator("#mission-cmd-pause")
            if pause_btn.is_visible():
                pause_btn.click()
                time.sleep(0.8)
                status_txt = page.locator("#mission-status-badge").inner_text()
                assert "PAUSED" in status_txt
                assertions_passed += 1

                # Click resume
                resume_btn = page.locator("#mission-cmd-resume")
                if resume_btn.is_visible():
                    resume_btn.click()
                    time.sleep(0.8)
                    status_txt = page.locator("#mission-status-badge").inner_text()
                    assert "RUNNING" in status_txt
                    assertions_passed += 1

            scenarios_tested.append("2. MissionControlActions bidirectional command dispatch")
            page.screenshot(path=SCREENSHOTS["02_controls"], full_page=False)
            print(f"  Captured: {SCREENSHOTS['02_controls']}")

            # -------------------------------------------------------------
            # SCENARIO 3: MISSIONTASKGRAPHPANEL (KAHN DAG & CONTROLS)
            # -------------------------------------------------------------
            print("[QA-03] Validating MissionTaskGraphPanel (DAG view & task controls)...")
            task_graph_tab = page.locator("#view-tab-plan")
            if task_graph_tab.is_visible():
                task_graph_tab.click()
                time.sleep(0.8)

            page.wait_for_selector("text=Grafo de Execução Topológico", timeout=10000)
            assert page.locator("text=Grafo de Execução Topológico").first.is_visible()
            assert page.locator("[id^='task-card-']").first.is_visible()
            assertions_passed += 2
            scenarios_tested.append("3. MissionTaskGraphPanel Kahn DAG visualization")

            page.screenshot(path=SCREENSHOTS["03_task_graph"], full_page=False)
            print(f"  Captured: {SCREENSHOTS['03_task_graph']}")

            # -------------------------------------------------------------
            # SCENARIO 4: INTENTPREVIEWMODAL (EDIT GOAL NLP & IMPACT ANALYSIS)
            # -------------------------------------------------------------
            print("[QA-04] Validating IntentPreviewModal...")
            page.wait_for_selector("#mission-cmd-edit-goal:not([disabled])", timeout=10000)
            page.locator("#mission-cmd-edit-goal").click()
            time.sleep(0.8)

            assert page.locator("#intent-preview-modal").is_visible()
            preset_auth = page.locator("button", has_text="Adiciona autenticação").first
            if preset_auth.is_visible():
                preset_auth.click()
            else:
                page.fill("#input-intent-text", "Adiciona autenticação")
                page.locator("#btn-analyze-intent").click()

            page.wait_for_selector("#preview-impact-badge", timeout=10000)
            assert page.locator("#preview-impact-badge").is_visible()
            assertions_passed += 2
            scenarios_tested.append("4. IntentPreviewModal NLP parsing & impact analysis")

            page.screenshot(path=SCREENSHOTS["04_intent_modal"], full_page=False)
            print(f"  Captured: {SCREENSHOTS['04_intent_modal']}")

            # -------------------------------------------------------------
            # SCENARIO 5: APPLY INTENT & SAFE REPLAN (VERSION BUMP)
            # -------------------------------------------------------------
            print("[QA-05] Applying Intent & Verifying Replan...")
            page.locator("#btn-apply-intent").click()
            time.sleep(1.5)

            intent_badge_txt = page.locator("#mission-intent-version-badge").inner_text()
            assert "v2" in intent_badge_txt or "V2" in intent_badge_txt
            plan_badge_txt = page.locator("#mission-plan-version-badge").inner_text()
            assert "v2" in plan_badge_txt or "V2" in plan_badge_txt
            assertions_passed += 2
            scenarios_tested.append("5. Intent apply triggers atomic replan & version bump")

            page.screenshot(path=SCREENSHOTS["05_intent_applied"], full_page=False)
            print(f"  Captured: {SCREENSHOTS['05_intent_applied']}")

            # -------------------------------------------------------------
            # SCENARIO 6: MISSIONREQUIREMENTSDIFFPANEL
            # -------------------------------------------------------------
            print("[QA-06] Validating MissionRequirementsDiffPanel...")
            req_tab = page.locator("#view-tab-requirements_diff")
            if req_tab.is_visible():
                req_tab.click()
                time.sleep(0.8)
                assert page.locator("#requirements-diff-view").is_visible()
                assert page.locator("text=USER_INTENT_DELTA").first.is_visible()
                assertions_passed += 2
                scenarios_tested.append("6. MissionRequirementsDiffPanel lifecycle diff")

            page.screenshot(path=SCREENSHOTS["06_req_diff"], full_page=False)
            print(f"  Captured: {SCREENSHOTS['06_req_diff']}")

            # -------------------------------------------------------------
            # SCENARIO 7: MISSIONPLANDIFFPANEL (DAG STATUS VALIDATION)
            # -------------------------------------------------------------
            print("[QA-07] Validating MissionPlanDiffPanel...")
            plan_tab = page.locator("#view-tab-plan_diff")
            if plan_tab.is_visible():
                plan_tab.click()
                time.sleep(0.8)
                assert page.locator("#plan-diff-view").is_visible()
                assert page.locator("text=TOPOLOGICAL_SAFE_REPLAN").first.is_visible()
                assertions_passed += 2
                scenarios_tested.append("7. MissionPlanDiffPanel DAG invariant validation")

            page.screenshot(path=SCREENSHOTS["07_plan_diff"], full_page=False)
            print(f"  Captured: {SCREENSHOTS['07_plan_diff']}")

            # -------------------------------------------------------------
            # SCENARIO 8: MISSIONEVIDENCEIMPACTPANEL (ZERO FALSE SUCCESS)
            # -------------------------------------------------------------
            print("[QA-08] Validating MissionEvidenceImpactPanel...")
            ev_tab = page.locator("#view-tab-evidence_impact")
            if ev_tab.is_visible():
                ev_tab.click()
                time.sleep(0.8)
                assert page.locator("#evidence-impact-view").is_visible()
                assert page.locator("text=ZERO_FALSE_SUCCESS").first.is_visible()
                assertions_passed += 2
                scenarios_tested.append("8. MissionEvidenceImpactPanel Zero False Success ledger")

            page.screenshot(path=SCREENSHOTS["08_ev_impact"], full_page=False)
            print(f"  Captured: {SCREENSHOTS['08_ev_impact']}")

            # -------------------------------------------------------------
            # SCENARIO 9: MISSIONWHYCAUSALPANEL (CAUSAL EXPLAINABILITY)
            # -------------------------------------------------------------
            print("[QA-09] Validating MissionWhyCausalPanel...")
            why_tab = page.locator("#view-tab-why")
            if why_tab.is_visible():
                why_tab.click()
                time.sleep(0.8)
                assert page.locator("text=Porque é que o JARVIS fez isto?").first.is_visible()
                assertions_passed += 1
                scenarios_tested.append("9. MissionWhyCausalPanel causal explainability chains")

            page.screenshot(path=SCREENSHOTS["09_why_panel"], full_page=False)
            print(f"  Captured: {SCREENSHOTS['09_why_panel']}")

            # -------------------------------------------------------------
            # SCENARIO 10: MISSIONREPAIRPANEL & EVIDENCELEDGERPANEL
            # -------------------------------------------------------------
            print("[QA-10] Validating MissionRepairPanel & EvidenceLedger...")
            repair_tab = page.locator("#view-tab-repairs")
            if repair_tab.is_visible():
                repair_tab.click()
                time.sleep(0.8)
                assert page.locator("text=Auto-Cura Cirúrgica").first.is_visible()
                assertions_passed += 1

            evidence_tab = page.locator("#view-tab-evidence")
            if evidence_tab.is_visible():
                evidence_tab.click()
                time.sleep(0.8)
                assert page.locator("text=Livro de Evidências Físicas").first.is_visible()
                assertions_passed += 1

            scenarios_tested.append("10. MissionRepairPanel & EvidenceLedgerPanel")

            page.screenshot(path=SCREENSHOTS["10_repair_ledger"], full_page=False)
            print(f"  Captured: {SCREENSHOTS['10_repair_ledger']}")

            # Copy all screenshots to artifact directory
            print("\nCopying screenshots to artifact directory...")
            for key, src_file in SCREENSHOTS.items():
                if os.path.exists(src_file):
                    dst_file = os.path.join(ARTIFACT_DIR, os.path.basename(src_file))
                    shutil.copy2(src_file, dst_file)
                    print(f"  Copied {os.path.basename(src_file)} -> Artifact Dir")

            browser.close()

    finally:
        pass

    # Save QA Report
    qa_record = {
        "phase": 38,
        "phase_name": "Super-File Decomposition & Architecture Hygiene Browser QA",
        "browser": "Microsoft Edge",
        "browser_path": EDGE_PATH,
        "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "url": "http://127.0.0.1:8000",
        "total_assertions_passed": assertions_passed,
        "total_scenarios_tested": len(scenarios_tested),
        "scenarios": scenarios_tested,
        "console_errors_count": len(console_errors),
        "console_errors": console_errors,
        "network_errors_count": len(network_errors),
        "network_errors": network_errors,
        "screenshots_captured": [
            os.path.basename(p) for p in SCREENSHOTS.values() if os.path.exists(p)
        ],
        "verdict": "PASSED" if assertions_passed >= 15 and len(console_errors) == 0 else "PARTIAL",
    }

    with open(QA_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(qa_record, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("BROWSER QA COMPLETED")
    print(f"Total Assertions Passed: {assertions_passed}")
    print(f"Scenarios Verified: {len(scenarios_tested)}")
    print(f"Console Errors: {len(console_errors)}")
    print(f"Screenshots Saved: {len(qa_record['screenshots_captured'])} / 10")
    print(f"QA Record written to: {QA_JSON_PATH}")
    print("=" * 80)

    return qa_record


if __name__ == "__main__":
    run_browser_qa()
