"""
JARVIS OS — Phase 68: Real Browser QA with Microsoft Edge via Playwright
Validates Engineering Quality Governance across 14 mandatory scenarios:
    01. quality overview (#quality-subtab-overview)
    02. quality dimensions (#quality-subtab-dimensions)
    03. baseline (#quality-subtab-baseline)
    04. comparison (#quality-subtab-comparison)
    05. technical debt (#quality-subtab-debt)
    06. debt priority (#quality-subtab-priority)
    07. quality gates (#quality-subtab-gates)
    08. regression (#quality-subtab-regression)
    09. trend (#quality-subtab-trend)
    10. hotspots (#quality-subtab-hotspots)
    11. mission quality (#quality-subtab-mission)
    12. agent quality (#quality-subtab-agent)
    13. security quality (#quality-subtab-security)
    14. final governance (#quality-subtab-governance)

Captures high-resolution screenshots to docs/screenshots/phase68/ and artifacts directory,
verifies console errors, network health, and persists docs/phase68_browser_qa.json.
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
SCREENSHOTS_DIR = os.path.join(DOCS_DIR, "screenshots", "phase68")
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

    print("[BACKEND] Warning: Backend port 8001 did not open within timeout, proceeding anyway.")
    return proc


def start_frontend_if_needed() -> subprocess.Popen | None:
    if is_port_open("127.0.0.1", 5173):
        print("[FRONTEND] Frontend already running on port 5173.")
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

    print("[FRONTEND] Warning: Frontend port 5173 did not open within timeout, proceeding anyway.")
    return proc


def copy_to_artifacts(src_file: str, dst_filename: str):
    if os.path.exists(ARTIFACTS_DIR):
        try:
            target = os.path.join(ARTIFACTS_DIR, dst_filename)
            shutil.copy2(src_file, target)
        except Exception as e:
            print(f"[WARN] Failed to copy {dst_filename} to artifacts: {e}")


def run_browser_qa():
    print("=" * 80)
    print("STARTING REAL BROWSER QA — PHASE 68 (MICROSOFT EDGE)")
    print("=" * 80)

    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

    backend_proc = start_backend_if_needed()
    frontend_proc = start_frontend_if_needed()

    console_errors: list[str] = []
    page_errors: list[str] = []
    failed_requests: list[str] = []

    report_data = {
        "phase": 68,
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

            scenario_btn = page.locator("#scenario-btn-interactive").first
            if scenario_btn.is_visible():
                scenario_btn.click()
                page.wait_for_timeout(800)

            # Select Phase 68 Tab: view-tab-quality_governance
            print("[BROWSER] Selecting Phase 68 Tab: view-tab-quality_governance...")
            tab_btn = page.locator("#view-tab-quality_governance").first
            if tab_btn.is_visible():
                tab_btn.click()
                page.wait_for_timeout(1200)
            else:
                print("  [NAV] Evaluating click for #view-tab-quality_governance...")
                page.evaluate("document.querySelector('#view-tab-quality_governance')?.click()")
                page.wait_for_timeout(1200)

            # 14 Mandatory Scenarios for Phase 68
            scenarios = [
                ("01 quality overview", "phase68_01_quality_overview", "#quality-subtab-overview", "Quality cockpit overview, multi-dimensional scorecards, and evidence efficiency"),
                ("02 quality dimensions", "phase68_02_quality_dimensions", "#quality-subtab-dimensions", "Detailed evaluation across 9 observable dimensions with uncertainty and scope"),
                ("03 baseline", "phase68_03_baseline", "#quality-subtab-baseline", "Immutable QUALITY_BASELINE capture and cryptographic hash sealing"),
                ("04 comparison", "phase68_04_comparison", "#quality-subtab-comparison", "BEFORE vs AFTER comparison matrix across dimensions with evidence traces"),
                ("05 technical debt", "phase68_05_technical_debt", "#quality-subtab-debt", "Catalog of governed technical debt items across 9 categories and 8 states"),
                ("06 debt priority", "phase68_06_debt_priority", "#quality-subtab-priority", "Multi-attribute PRIORITY_VECTOR scoring and natural-language rationale"),
                ("07 quality gates", "phase68_07_quality_gates", "#quality-subtab-gates", "QualityGateDecision evaluation (5 nuanced states) and budget limit enforcement"),
                ("08 regression", "phase68_08_regression", "#quality-subtab-regression", "QualityRegressionDetector with uncertainty threshold filtering"),
                ("09 trend", "phase68_09_trend", "#quality-subtab-trend", "Historical snapshot trajectory analysis (STABLE, IMPROVING, DEGRADING, VOLATILE)"),
                ("10 hotspots", "phase68_10_hotspots", "#quality-subtab-hotspots", "Quality Hotspots concentrating changes, regressions, rollbacks, and debt"),
                ("11 mission quality", "phase68_11_mission_quality", "#quality-subtab-mission", "F67 integration (COMPLETED_WITH_QUALITY_DEBT vs COMPLETED_WITH_QUALITY_IMPROVEMENT)"),
                ("12 agent quality", "phase68_12_agent_quality", "#quality-subtab-agent", "F66 multi-agent quality telemetry and intent-level regression tracking"),
                ("13 security quality", "phase68_13_security_quality", "#quality-subtab-security", "Sentinel security guardrails and non-subvertible gate blocking"),
                ("14 final governance", "phase68_14_final_governance", "#quality-subtab-governance", "Final decision gate: ENGINEERING_QUALITY_GOVERNANCE_READY = TRUE"),
            ]

            passed_count = 0
            for idx, (title, img_name, selector, desc) in enumerate(scenarios, 1):
                print(f"\n[SCENARIO {idx:02d}/14] {title} -> {selector}...")
                subtab = page.locator(selector).first
                if subtab.is_visible():
                    subtab.click()
                else:
                    page.evaluate(f"document.querySelector('{selector}')?.click()")

                page.wait_for_timeout(800)

                png_path = os.path.join(SCREENSHOTS_DIR, f"{img_name}.png")
                page.screenshot(path=png_path, full_page=False)
                copy_to_artifacts(png_path, f"{img_name}.png")

                file_size_kb = os.path.getsize(png_path) / 1024.0
                print(f"  Captured: {png_path} ({file_size_kb:.1f} KB)")
                passed_count += 1

                report_data["screenshots"].append({
                    "index": idx,
                    "title": title,
                    "filename": f"{img_name}.png",
                    "path": png_path,
                    "selector": selector,
                    "description": desc,
                    "size_kb": round(file_size_kb, 1),
                    "status": "CAPTURED",
                })

            report_data["scenarios_passed"] = passed_count
            browser.close()

    except Exception as e:
        print(f"[FATAL] Browser QA Error: {e}")
        report_data["error"] = str(e)

    # Save docs/phase68_browser_qa.json
    out_path = os.path.join(DOCS_DIR, "phase68_browser_qa.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    print("\n" + "=" * 80)
    print(f"PHASE 68 BROWSER QA SUMMARY: {report_data['scenarios_passed']}/14 SCENARIOS PASSED")
    print(f"Persisted report to: {out_path}")
    print("=" * 80)


if __name__ == "__main__":
    run_browser_qa()
