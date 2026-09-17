import re
import subprocess
import sys

phases = [
    (40, 'tests/test_mission_autonomy.py'),
    (41, 'tests/test_decision_outcome.py'),
    (42, 'tests/test_experience_memory.py'),
    (43, 'tests/test_memory_generalization.py'),
    (44, 'tests/test_semantic_graph.py'),
    (45, 'tests/test_contract_execution_validation.py'),
    (46, 'tests/test_contract_drift.py'),
    (47, 'tests/test_polymorphic_schema.py'),
    (48, 'tests/test_contract_change_analyzer.py'),
    (49, 'tests/test_consumer_impact.py'),
    (50, 'tests/test_contract_validation.py'),
    (51, 'tests/test_subdag_models_and_validation.py'),
    (52, 'tests/test_risk_directed_exploration.py'),
    (53, 'tests/test_project_preflight_recovery.py'),
    (54, 'tests/test_verified_repair_synthesis.py'),
    (55, 'tests/test_multi_repair_orchestration.py'),
    (56, 'tests/test_repair_convergence_governance.py'),
    (57, 'tests/test_autonomous_task_completion.py'),
    (58, 'tests/test_massive_project_state.py'),
    (59, 'tests/test_scc_aware_graph.py'),
]

print("=" * 80)
print("PHASE 40 - 59 REGRESSION EXECUTION LEDGER")
print("=" * 80)

total_passed = 0
total_failed = 0
total_all = 0

for p, f in phases:
    cmd = [sys.executable, '-m', 'pytest', f, '-q']
    res = subprocess.run(cmd, capture_output=True, text=True)
    out = res.stdout + res.stderr
    passed = 0
    failed = 0
    for line in out.splitlines():
        if 'passed' in line:
            m = re.search(r'(\d+)\s+passed', line)
            if m: passed = int(m.group(1))
            mf = re.search(r'(\d+)\s+failed', line)
            if mf: failed = int(mf.group(1))
    total = passed + failed
    total_passed += passed
    total_failed += failed
    total_all += total
    status = "PASS" if (failed == 0 and passed > 0) else "FAIL"
    print(f"Phase {p:02d} | Passed: {passed:3d} | Failed: {failed:1d} | Total: {total:3d} | Status: {status:4s} | File: {f}")

print("=" * 80)
print(f"TOTAL AGGREGATE | Passed: {total_passed} | Failed: {total_failed} | Total: {total_all}")
print("=" * 80)
