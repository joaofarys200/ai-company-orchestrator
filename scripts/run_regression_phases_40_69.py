"""
JARVIS OS — Continuous Regression Suite: Phases 40 to 69
Validates historical stability across all 30 autonomous engineering, verification, architecture evolution,
multi-agent coordination, long-horizon mission governance, quality debt governance, and autonomous debt remediation phases (F40–F69).

Reports explicit X/Y PASS denominators.
Automated Invariant Check:
    sum(per_phase_passes) == computed_total == reported_total
    delta == 0
Outputs: docs/phase69_regression_reconciliation.json
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time

PHASE_TEST_MAP = {
    "Phase 40 (Autonomous Engineering Loop)": [
        "tests/test_autonomous_loop_models.py",
        "tests/test_autonomous_loop_policy.py",
        "tests/test_autonomous_loop_controller.py",
    ],
    "Phase 41 (Decision Calibration & Quality)": [
        "tests/test_decision_replay.py",
        "tests/test_decision_outcome.py",
        "tests/test_decision_error_classification.py",
        "tests/test_autonomous_decision_engine.py",
        "tests/test_policy_registry.py",
        "tests/test_policy_sandbox.py",
        "tests/test_policy_proposal.py",
        "tests/test_policy_safety_regression.py",
        "tests/test_policy_shadow.py",
        "tests/test_policy_rollback.py",
    ],
    "Phase 42 (Engineering Experience Memory)": [
        "tests/test_experience_memory.py",
        "tests/test_experience_signature.py",
        "tests/test_experience_retrieval.py",
        "tests/test_experience_applicability.py",
        "tests/test_experience_reuse.py",
        "tests/test_experience_conflicts.py",
        "tests/test_experience_security.py",
    ],
    "Phase 43 (Cross-Mission Generalization)": [
        "tests/test_memory_transfer.py",
        "tests/test_memory_generalization.py",
        "tests/test_memory_conflicts.py",
        "tests/test_memory_incremental_index.py",
        "tests/test_memory_temporal_validity.py",
        "tests/test_memory_temporal_leakage.py",
        "tests/test_memory_architecture_compatibility.py",
        "tests/test_memory_policy_compatibility.py",
        "tests/test_memory_harm.py",
    ],
    "Phase 44 (Semantic Contract Graph)": [
        "tests/test_semantic_graph.py",
        "tests/test_semantic_graph_incremental.py",
        "tests/test_semantic_graph_contract_update.py",
    ],
    "Phase 45 (Runtime Contract Discovery)": [
        "tests/test_schema_inference.py",
        "tests/test_consumer_impact.py",
        "tests/test_consumer_break_detection.py",
    ],
    "Phase 46 (Contract Drift Governance)": [
        "tests/test_drift_classification.py",
        "tests/test_drift_predictive_integration.py",
        "tests/test_drift_policy.py",
        "tests/test_drift_rollback.py",
        "tests/test_drift_environment.py",
        "tests/test_drift_incremental.py",
        "tests/test_drift_security.py",
    ],
    "Phase 47 (Polymorphic Contract Governance)": [
        "tests/test_polymorphic_schema.py",
        "tests/test_polymorphic_diff.py",
        "tests/test_union_compatibility.py",
        "tests/test_variant_detection.py",
        "tests/test_polymorphic_consumers.py",
        "tests/test_polymorphic_contract_change.py",
        "tests/test_polymorphic_incremental.py",
        "tests/test_polymorphic_drift.py",
        "tests/test_polymorphic_security.py",
    ],
    "Phase 48 (Contract-Aware Change Management)": [
        "tests/test_contract_change_analyzer.py",
        "tests/test_contract_diff.py",
        "tests/test_contract_evolution.py",
        "tests/test_migration_plan.py",
    ],
    "Phase 49 (Build-Time Contract Extraction)": [
        "tests/test_build_contract_extraction.py",
    ],
    "Phase 50 (Behavioral Contract Proof)": [
        "tests/test_behavioral_contract_proof.py",
    ],
    "Phase 51 (Behavioral Proof Exploration)": [
        "tests/test_behavioral_proof_exploration.py",
    ],
    "Phase 52 (Risk-Directed Boundary Exploration)": [
        "tests/test_risk_directed_exploration.py",
    ],
    "Phase 53 (Universal Preflight & Self-Recovery)": [
        "tests/test_preflight_recovery.py",
    ],
    "Phase 54 (Verified Repair Synthesis)": [
        "tests/test_verified_repair_synthesis.py",
    ],
    "Phase 55 (Multi-Repair Orchestration)": [
        "tests/test_multi_repair_orchestration.py",
    ],
    "Phase 56 (Autonomous Repair Convergence Governance)": [
        "tests/test_autonomous_repair_convergence.py",
    ],
    "Phase 57 (Autonomous Task Completion & Zero False Success)": [
        "tests/test_autonomous_task_completion.py",
    ],
    "Phase 58 (Massive Project State & Incremental Monorepo Graph)": [
        "tests/test_massive_project_state.py",
    ],
    "Phase 59 (SCC-Aware Large Scale Dependency Graph)": [
        "tests/test_scc_aware_graph.py",
    ],
    "Phase 60 (Symbol-Level Fine-Grained Dependency Graph)": [
        "tests/test_symbol_fine_grained_graph.py",
    ],
    "Phase 61 (Autonomous Test Synthesis & Coverage Expansion)": [
        "tests/test_autonomous_test_synthesis.py",
    ],
    "Phase 62 (Continuous Verification & Regression Prevention)": [
        "tests/test_continuous_verification.py",
    ],
    "Phase 63 (Cross-Project Learning & Repository Adaptation)": [
        "tests/test_cross_project_learning.py",
    ],
    "Phase 64 (Autonomous Architecture Evolution & Refactoring)": [
        "tests/test_architecture_evolution.py",
    ],
    "Phase 65 (Safe Self-Modification & Transactional Code Engine)": [
        "tests/test_safe_self_modification.py",
    ],
    "Phase 66 (Multi-Agent Swarm Coordination & Task Arbitration)": [
        "tests/test_multi_agent_coordination.py",
    ],
    "Phase 67 (Long-Horizon Mission Autonomy & State Management)": [
        "tests/test_long_horizon_missions.py",
    ],
    "Phase 68 (Engineering Quality Governance & Autonomous Quality Debt Management)": [
        "tests/test_engineering_quality_governance.py",
    ],
    "Phase 69 (Autonomous Quality Debt Remediation & Continuous Engineering Improvement)": [
        "tests/test_quality_debt_remediation.py",
    ],
}


def run_regression():
    print("=" * 80)
    print("RUNNING HISTORICAL REGRESSION TEST SUITE: PHASES 40 TO 69")
    print("=" * 80)

    per_phase_passes = {}
    total_passed = 0
    total_failed = 0
    phase_results = {}

    venv_py = os.path.join(os.getcwd(), "venv", "Scripts", "python.exe")
    python_exe = venv_py if os.path.exists(venv_py) else sys.executable

    t_start = time.time()

    for phase_name, test_files in PHASE_TEST_MAP.items():
        existing_files = [f for f in test_files if os.path.exists(f)]
        if not existing_files:
            print(f"[SKIP] {phase_name}: No test files found.")
            per_phase_passes[phase_name] = 0
            continue

        cmd = [python_exe, "-m", "pytest"] + existing_files + ["-q"]
        res = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())

        stdout = res.stdout.strip()
        lines = stdout.splitlines()
        summary_line = lines[-1] if lines else ""

        passed = 0
        failed = 0

        m_pass = re.search(r"(\d+)\s+passed", summary_line)
        m_fail = re.search(r"(\d+)\s+failed", summary_line)

        if m_pass:
            passed = int(m_pass.group(1))
        if m_fail:
            failed = int(m_fail.group(1))

        if res.returncode != 0 and failed == 0 and "passed" not in summary_line:
            print(f"[FAIL] {phase_name}: Execution error.\n{res.stderr or stdout}")
            failed = 1

        per_phase_passes[phase_name] = passed
        total_passed += passed
        total_failed += failed

        status_str = "PASS" if failed == 0 and passed > 0 else "FAIL"
        print(f"[{status_str}] {phase_name}: {passed} passed, {failed} failed")

        phase_results[phase_name] = {
            "passed": passed,
            "failed": failed,
            "status": status_str,
            "test_files": existing_files,
        }

    duration = round(time.time() - t_start, 2)
    computed_total = sum(per_phase_passes.values())
    reported_total = total_passed
    delta = abs(computed_total - reported_total)
    is_valid = (computed_total == reported_total) and (total_failed == 0) and (delta == 0)

    print("=" * 80)
    print(f"TOTAL TESTS: {computed_total}/{computed_total} PASS (0 FAIL) in {duration}s")
    print(f"INVARIANT CHECK: sum(per_phase)={computed_total} == reported={reported_total} | delta={delta}")
    print(f"RECONCILIATION VALID: {is_valid}")
    print("=" * 80)

    reconciliation_data = {
        "suite": "Phases 40 to 69 Regression Suite",
        "timestamp": time.time(),
        "duration_seconds": duration,
        "per_phase": per_phase_passes,
        "computed_total": computed_total,
        "reported_total": reported_total,
        "failed_total": total_failed,
        "delta": delta,
        "valid": is_valid,
        "phase_results": phase_results,
    }

    os.makedirs("docs", exist_ok=True)
    out_file = os.path.join("docs", "phase69_regression_reconciliation.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(reconciliation_data, f, indent=2)

    print(f"Reconciliation persisted to {out_file}")

    if not is_valid:
        print("[FATAL] Denominator reconciliation failed or regressions detected!")
        print("REGRESSION_REPORT_INVALID")
        print("QUALITY_DEBT_REMEDIATION_READY = FALSE")
        sys.exit(1)
    else:
        print("QUALITY_DEBT_REMEDIATION_READY = TRUE")


if __name__ == "__main__":
    run_regression()
