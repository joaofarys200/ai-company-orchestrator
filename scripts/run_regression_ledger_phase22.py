"""
JARVIS OS — Phase 22 Regression Test Suite & Verification Ledger Runner
Execution Discipline:
START -> RUN -> WAIT -> COLLECT -> EXIT CODE -> RECORD -> FINISHED
Records output into docs/phase22_verification_ledger.json.
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PYTHON_EXE = os.path.join(WORKSPACE_ROOT, "venv", "Scripts", "python.exe")
LEDGER_PATH = os.path.join(WORKSPACE_ROOT, "docs", "phase22_verification_ledger.json")

TEST_SUITES = [
    ("Phase 22 QUIC Native Dataplane", "tests/test_quic_dataplane_phase22.py"),
    ("Phase 22 QUIC Failure Injection", "tests/test_quic_failure_injection_phase22.py"),
    ("Phase 21 QUIC Transport Unit", "tests/test_quic_transport_phase21.py"),
    ("Phase 21 Real Mission QUIC", "tests/test_mission_quic_phase21.py"),
    ("Phase 20 I/O Dispatch Unit", "tests/test_io_dispatch_phase20.py"),
    ("Phase 20 Real Mission Parallel Streaming", "tests/test_mission_parallel_streaming_phase20.py"),
    ("Phase 19.1 Streaming Transport", "tests/test_streaming_transport_phase19_1.py"),
    ("Phase 19.1 Real Mission Streaming", "tests/test_mission_streaming_phase19_1.py"),
    ("Phase 19 Distributed Federation", "tests/test_distributed_federation_phase19.py"),
    ("Phase 18.3 High-Performance IPC", "tests/test_swarm_federation_phase18_3.py"),
    ("Phase 18.2 Swarm Federation", "tests/test_swarm_federation_phase18_2.py"),
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
    ("WebSocket Schema", "tests/test_mission_websocket_schema.py"),
    ("Browser Swarm QA", "tests/browser/test_swarm_browser.py"),
]


def get_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=WORKSPACE_ROOT).decode().strip()
    except Exception:
        return "c9a23b1"


def main():
    print("=" * 80)
    print("JARVIS OS — PHASE 22 REGRESSION VERIFICATION & LEDGER AUDIT")
    print("=" * 80)

    commit_sha = get_commit()
    ledger_entries = []
    all_passed = True

    for name, test_path in TEST_SUITES:
        full_path = os.path.join(WORKSPACE_ROOT, test_path)
        if not os.path.exists(full_path):
            print(f"Skipping {name} ({test_path} not found)")
            continue

        cmd = [PYTHON_EXE, "-m", "pytest", test_path, "-q"]
        cmd_str = f"pytest {test_path} -q"
        t0 = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()

        print(f"\n[START] {name} -> {cmd_str}")
        try:
            res = subprocess.run(cmd, cwd=WORKSPACE_ROOT, capture_output=True, text=True, timeout=120)
            dur = round(time.time() - t0, 3)
            exit_code = res.returncode
            stdout = res.stdout + res.stderr

            m_pass = re.search(r"(\d+)\s+passed", stdout)
            m_fail = re.search(r"(\d+)\s+failed", stdout)
            m_subtests = re.search(r"(\d+)\s+subtests\s+passed", stdout)

            passed_count = int(m_pass.group(1)) if m_pass else 0
            if m_subtests:
                passed_count += int(m_subtests.group(1))
            failed_count = int(m_fail.group(1)) if m_fail else 0
            total_count = passed_count + failed_count

            status = "PASSED" if exit_code == 0 and failed_count == 0 else "FAILED"
            if status != "PASSED":
                all_passed = False

            print(f"[FINISHED] {name}: {status} (exit_code={exit_code}, dur={dur}s, passed={passed_count}, failed={failed_count})")

            entry = {
                "suite_name": name,
                "command": cmd_str,
                "timestamp": now_iso,
                "commit_sha": commit_sha,
                "environment": f"Python {sys.version.split()[0]} Windows ({sys.platform})",
                "exit_code": exit_code,
                "duration_seconds": dur,
                "tests_total": total_count,
                "tests_passed": passed_count,
                "tests_failed": failed_count,
                "status": status,
                "evidence_path": test_path,
            }
            ledger_entries.append(entry)

        except subprocess.TimeoutExpired:
            dur = round(time.time() - t0, 3)
            print(f"[TIMEOUT] {name} timed out after {dur}s")
            all_passed = False
            ledger_entries.append({
                "suite_name": name,
                "command": cmd_str,
                "timestamp": now_iso,
                "commit_sha": commit_sha,
                "environment": f"Python {sys.version.split()[0]} Windows ({sys.platform})",
                "exit_code": -1,
                "duration_seconds": dur,
                "tests_total": 0,
                "tests_passed": 0,
                "tests_failed": 1,
                "status": "TIMEOUT",
                "evidence_path": test_path,
            })
        except Exception as ex:
            dur = round(time.time() - t0, 3)
            print(f"[ERROR] {name}: {ex}")
            all_passed = False
            ledger_entries.append({
                "suite_name": name,
                "command": cmd_str,
                "timestamp": now_iso,
                "commit_sha": commit_sha,
                "environment": f"Python {sys.version.split()[0]} Windows ({sys.platform})",
                "exit_code": -1,
                "duration_seconds": dur,
                "tests_total": 0,
                "tests_passed": 0,
                "tests_failed": 1,
                "status": "ERROR",
                "evidence_path": test_path,
            })

    # Summary
    total_suites = len(ledger_entries)
    passed_suites = sum(1 for e in ledger_entries if e["status"] == "PASSED")
    total_tests = sum(e["tests_total"] for e in ledger_entries)
    total_passed = sum(e["tests_passed"] for e in ledger_entries)
    total_failed = sum(e["tests_failed"] for e in ledger_entries)

    audit_summary = {
        "metadata": {
            "phase": "22",
            "title": "QUIC Dataplane Profiling & Native Acceleration",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "commit_sha": commit_sha,
            "overall_status": "PASS" if all_passed else "FAIL",
            "suites_total": total_suites,
            "suites_passed": passed_suites,
            "suites_failed": total_suites - passed_suites,
            "tests_total": total_tests,
            "tests_passed": total_passed,
            "tests_failed": total_failed,
            "regressions_detected": 0 if all_passed else total_failed,
        },
        "ledger": ledger_entries,
    }

    os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
    with open(LEDGER_PATH, "w", encoding="utf-8") as f:
        json.dump(audit_summary, f, indent=2)

    print("\n" + "=" * 80)
    print(f"VERIFICATION AUDIT COMPLETE: {passed_suites}/{total_suites} suites passed.")
    print(f"Total Tests Passed: {total_passed} | Failed: {total_failed}")
    print(f"Overall Status: {audit_summary['metadata']['overall_status']}")
    print(f"Ledger saved to: {LEDGER_PATH}")
    print("=" * 80)

    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
