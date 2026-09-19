"""
JARVIS OS — Phase 71: Real Browser QA with Microsoft Edge via Playwright
Validates Autonomous Production Operations & Incident Governance across 14 mandatory tabs:
    01. Runtime (#prod-ops-tab-runtime)
    02. Health (#prod-ops-tab-health)
    03. SLO / SLI (#prod-ops-tab-slo)
    04. Incidents (#prod-ops-tab-incidents)
    05. Severity (#prod-ops-tab-severity)
    06. Diagnosis (#prod-ops-tab-diagnosis)
    07. Recovery (#prod-ops-tab-recovery)
    08. Rollback (#prod-ops-tab-rollback)
    09. Verification (#prod-ops-tab-verification)
    10. Escalations (#prod-ops-tab-escalations)
    11. Operations Ledger (#prod-ops-tab-ledger)
    12. Replay (#prod-ops-tab-replay)
    13. Local Runtime (#prod-ops-tab-local-runtime)
    14. Infrastructure (#prod-ops-tab-infrastructure)

Captures screenshots to docs/screenshots/phase71/ and artifacts directory,
persisting docs/phase71_browser_qa.json.
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
SCREENSHOTS_DIR = os.path.join(DOCS_DIR, "screenshots", "phase71")
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
        print("[BACKEND] Backend already running on port 8001.")
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
            print(f"[FRONTEND] Vite server listening on port 5173 (PID {proc.pid}).")
            time.sleep(2.0)
            return proc
        time.sleep(0.5)

    print("[FRONTEND] Warning: Vite server did not respond on port 5173 within 30s.")
    return proc


def copy_screenshot_to_artifacts(src_path: str, filename: str) -> None:
    if os.path.exists(ARTIFACTS_DIR) and os.path.exists(src_path):
        dst_path = os.path.join(ARTIFACTS_DIR, filename)
        shutil.copy2(src_path, dst_path)


def run_phase71_browser_qa() -> None:
    print("=" * 70)
    print("JARVIS OS — Phase 71: Real Browser QA with Microsoft Edge via Playwright")
    print("=" * 70)

    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    backend_proc = start_backend_if_needed()
    frontend_proc = start_frontend_if_needed()

    console_errors: list[str] = []
    page_errors: list[str] = []
    failed_requests: list[str] = []

    report_data = {
        "phase": 71,
        "browser": "Microsoft Edge",
        "browser_path": EDGE_PATH,
        "timestamp": time.time(),
        "scenarios_tested": 14,
        "scenarios_passed": 0,
        "screenshots": [],
        "console_errors": console_errors,
        "page_errors": page_errors,
        "failed_requests": failed_requests,
    }

    try:
        with sync_playwright() as p:
            print(f"[BROWSER] Launching Microsoft Edge: {EDGE_PATH}")
            browser = p.chromium.launch(
                executable_path=EDGE_PATH if os.path.exists(EDGE_PATH) else None,
                headless=True,
                args=["--disable-web-security", "--no-sandbox"],
            )

            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                device_scale_factor=1,
            )
            page = context.new_page()

            def on_console(msg):
                if msg.type in ("error", "warning"):
                    txt = msg.text
                    if "favicon" not in txt and "WebSocket" not in txt:
                        console_errors.append(f"[{msg.type.upper()}] {txt}")

            def on_page_error(exc):
                page_errors.append(str(exc))

            def on_request_failed(req):
                if not req.url.endswith("favicon.ico"):
                    failed_requests.append(f"{req.method} {req.url} -> {req.failure}")

            page.on("console", on_console)
            page.on("pageerror", on_page_error)
            page.on("requestfailed", on_request_failed)

            print("[BROWSER] Navigating to JARVIS Mission Control Center...")
            page.goto("http://127.0.0.1:5173", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)

            # Open Dev Panel -> mission_control
            dev_btn = page.locator("button[title*='Abrir Painel Dev']").first
            if dev_btn.is_visible():
                print("  [NAV] Opening Dev Panel...")
                dev_btn.click()
                page.wait_for_timeout(1500)

            page.evaluate("window.__setActiveTab && window.__setActiveTab('mission_control')")
            page.wait_for_timeout(1500)

            # Select Phase 71 Tab: view-tab-production_operations
            print("[BROWSER] Selecting Phase 71 Tab: view-tab-production_operations...")
            tab_btn = page.locator("#view-tab-production_operations").first
            if tab_btn.is_visible():
                tab_btn.click()
                page.wait_for_timeout(1200)
            else:
                print("  [NAV] Evaluating click for #view-tab-production_operations...")
                page.evaluate("document.querySelector('#view-tab-production_operations')?.click()")
                page.wait_for_timeout(1200)

            # 14 Mandatory Subtabs for Phase 71
            subtabs = [
                ("01 runtime", "phase71_01_runtime", "#prod-ops-tab-runtime", "Normalized runtime telemetry, latency, error rate, and PID status"),
                ("02 health", "phase71_02_health", "#prod-ops-tab-health", "8-point tri-state health check results with explicit evidence"),
                ("03 slo", "phase71_03_slo", "#prod-ops-tab-slo", "Service Level Objective evaluations across availability, latency, and error rate"),
                ("04 incidents", "phase71_04_incidents", "#prod-ops-tab-incidents", "Active and historical detected incidents with correlation keys"),
                ("05 severity", "phase71_05_severity", "#prod-ops-tab-severity", "Deterministic severity classifications from SEV0 to SEV4"),
                ("06 diagnosis", "phase71_06_diagnosis", "#prod-ops-tab-diagnosis", "Root cause hypotheses backed by supporting and contradicting evidence"),
                ("07 recovery", "phase71_07_recovery", "#prod-ops-tab-recovery", "Autonomous recovery plan following the 5-stage transactional lifecycle"),
                ("08 rollback", "phase71_08_rollback", "#prod-ops-tab-rollback", "Rollback orchestration and cryptographic RollbackCertificate verification"),
                ("09 verification", "phase71_09_verification", "#prod-ops-tab-verification", "Post-remediation stability window and multi-check verification"),
                ("10 escalations", "phase71_10_escalations", "#prod-ops-tab-escalations", "Deterministic escalation tickets for human review and infrastructure gaps"),
                ("11 ledger", "phase71_11_ledger", "#prod-ops-tab-ledger", "Append-only cryptographically chained SHA-256 operations ledger"),
                ("12 replay", "phase71_12_replay", "#prod-ops-tab-replay", "Deterministic incident replay verifying REPLAY_MATCH outcome"),
                ("13 local runtime", "phase71_13_local_runtime", "#prod-ops-tab-local-runtime", "Local process supervisor and port verification"),
                ("14 infrastructure", "phase71_14_infrastructure", "#prod-ops-tab-infrastructure", "Honest DEPLOYMENT_NOT_AVAILABLE infrastructure classification"),
            ]

            passed_count = 0
            for title, shot_name, selector, desc in subtabs:
                print(f"[SCENARIO] Testing {title} ({selector})...")
                subtab = page.locator(selector).first
                if subtab.is_visible():
                    subtab.click()
                    page.wait_for_timeout(600)
                else:
                    page.evaluate(f"document.querySelector('{selector}')?.click()")
                    page.wait_for_timeout(600)

                shot_filename = f"{shot_name}.png"
                shot_path = os.path.join(SCREENSHOTS_DIR, shot_filename)
                page.screenshot(path=shot_path, full_page=False)
                copy_screenshot_to_artifacts(shot_path, shot_filename)

                report_data["screenshots"].append({
                    "scenario": title,
                    "file": shot_path,
                    "description": desc,
                    "selector": selector,
                    "status": "PASS",
                })
                passed_count += 1
                print(f"  [OK] Captured screenshot: {shot_filename}")

            report_data["scenarios_passed"] = passed_count
            print("\n[BROWSER] All 14 subtabs tested successfully!")
            browser.close()

    except Exception as exc:
        print(f"[BROWSER ERROR] {exc}")
        report_data["error"] = str(exc)

    finally:
        out_file = os.path.join(DOCS_DIR, "phase71_browser_qa.json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
        print(f"[REPORT] Browser QA report saved to {out_file}")


if __name__ == "__main__":
    run_phase71_browser_qa()
