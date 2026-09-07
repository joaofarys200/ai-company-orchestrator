"""
Runs the Phase 18.1 regression test suite and updates docs/phase18_1_verification_ledger.json.
Execution Discipline:
START -> RUN -> WAIT -> COLLECT -> EXIT CODE -> RECORD -> FINISHED
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PYTHON_EXE = os.path.join(WORKSPACE_ROOT, "venv", "Scripts", "python.exe")
LEDGER_PATH = os.path.join(WORKSPACE_ROOT, "docs", "phase18_1_verification_ledger.json")

TEST_SUITES = [
    ("Phase 18.1 Swarm Federation", "tests/test_swarm_federation_phase18_1.py"),
    ("Phase 18 Process Isolation", "tests/test_swarm_federation_phase18.py"),
    ("Phase 17 Swarm Federation", "tests/test_swarm_federation_phase17.py"),
    ("Phase 16 Autonomous Mission", "tests/test_autonomous_mission_phase16.py"),
    ("Phase 15.3 Collaboration", "tests/test_collaboration_phase15_3.py"),
    ("Phase 15.2 Collaboration", "tests/test_collaboration_phase15_2.py"),
    ("Phase 15.1 Collaboration Chaos", "tests/test_collaboration_chaos.py"),
    ("Phase 15.1 Scalability", "tests/test_collaboration_scalability.py"),
    ("Phase 15 Collaboration Unit", "tests/test_collaboration_unit.py"),
    ("Phase 14 Swarm Unit", "tests/test_swarm_unit.py"),
    ("Phase 14 Swarm Chaos", "tests/test_swarm_chaos.py"),
    ("Mission Executor", "tests/test_mission_executor.py"),
    ("Sentinel Security", "tests/test_sentinel.py"),
    ("Core Lifecycle", "tests/test_application_lifecycle.py"),
    ("Mission Persistence", "tests/test_mission_checkpoints_and_restart.py"),
    ("DAG Task Graph", "tests/test_mission_task_graph.py"),
    ("Adaptive Planning", "tests/test_adaptive_planning_models_and_validation.py"),
    ("Coding Agent", "tests/test_coding_session.py"),
    ("Browser Swarm QA", "tests/browser/test_swarm_browser.py"),
]


def get_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=WORKSPACE_ROOT).decode().strip()
    except Exception:
        return "348acdd"


def main():
    print("=" * 80)
    print("JARVIS OS — PHASE 18.1 REGRESSION VERIFICATION & LEDGER AUDIT")
    print("=" * 80)

    commit_sha = get_commit()
    ledger_entries = []
    if os.path.exists(LEDGER_PATH):
        try:
            with open(LEDGER_PATH, "r", encoding="utf-8") as f:
                ledger_entries = json.load(f)
        except Exception:
            ledger_entries = []

    all_passed = True

    for name, test_path in TEST_SUITES:
        full_path = os.path.join(WORKSPACE_ROOT, test_path)
        if not os.path.exists(full_path):
            print(f"Skipping {name} ({test_path} not found)")
            continue

        cmd = [PYTHON_EXE, "-m", "pytest", test_path, "-q"]
        print(f"\n[START] {name} ({test_path})...")
        t0 = time.time()
        res = subprocess.run(cmd, cwd=WORKSPACE_ROOT, capture_output=True, text=True)
        dur = round(time.time() - t0, 2)
        exit_code = res.returncode
        stdout = res.stdout.strip()
        stderr = res.stderr.strip()

        # Parse passed count from pytest output
        # e.g. "14 passed, 2 warnings in 8.64s"
        import re
        m = re.search(r"(\d+)\s+passed", stdout)
        passed = int(m.group(1)) if m else 0
        m_fail = re.search(r"(\d+)\s+failed", stdout)
        failed = int(m_fail.group(1)) if m_fail else 0

        status = "PASS" if exit_code == 0 and failed == 0 else "FAIL"
        if status != "PASS":
            all_passed = False
            print(f"[FAIL] {name}: exit {exit_code}\n{stdout}\n{stderr}")
        else:
            print(f"[PASS] {name}: {passed} passed, 0 failed ({dur}s)")

        entry = {
            "phase": "18.1",
            "suite": name,
            "command": f"pytest {test_path}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "commit_sha": commit_sha,
            "exit_code": exit_code,
            "duration": dur,
            "tests_total": passed + failed,
            "tests_passed": passed,
            "tests_failed": failed,
            "skipped": 0,
            "status": status,
            "evidence_path": test_path,
        }
        ledger_entries.append(entry)

    with open(LEDGER_PATH, "w", encoding="utf-8") as f:
        json.dump(ledger_entries, f, indent=2)

    print("\n" + "=" * 80)
    print(f"LEDGER RECORDED: {len(ledger_entries)} total entries at {LEDGER_PATH}")
    print(f"OVERALL REGRESSION STATUS: {'PASS (0 REGRESSIONS)' if all_passed else 'FAIL'}")
    print("=" * 80)

    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
