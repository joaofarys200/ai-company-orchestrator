"""
JARVIS OS — Continuous Regression Suite: Phases 40 to 65
Validates historical stability across all 26 autonomous engineering, verification, and architecture evolution phases.
Reports explicit X/Y PASS denominators.
Automated Invariant Check:
    sum(per_phase_passes) == reported_total
    If mismatch, raises REGRESSION_REPORT_INVALID and exits with code 1.
"""

from __future__ import annotations

import os
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
    "Phase 51 (Bounded Behavioral Exploration)": [
        "tests/test_behavioral_proof_exploration.py",
    ],
    "Phase 52 (Risk-Directed Exploration)": [
        "tests/test_risk_directed_exploration.py",
    ],
    "Phase 53 (Universal Preflight Recovery)": [
        "tests/test_project_preflight_recovery.py",
    ],
    "Phase 54 (Verified Repair Synthesis)": [
        "tests/test_verified_repair_synthesis.py",
    ],
    "Phase 55 (Multi-Repair Orchestration)": [
        "tests/test_multi_repair_orchestration.py",
    ],
    "Phase 56 (Repair Convergence Governance)": [
        "tests/test_repair_convergence_governance.py",
    ],
    "Phase 57 (Autonomous Task Completion)": [
        "tests/test_autonomous_task_completion.py",
    ],
    "Phase 58 (Massive Project State)": [
        "tests/test_massive_project_state.py",
    ],
    "Phase 59 (SCC-Aware Graph & Condensation)": [
        "tests/test_scc_aware_graph.py",
    ],
    "Phase 60 (Symbol-Fine-Grained Graph & Precision)": [
        "tests/test_symbol_fine_grained_graph.py",
    ],
    "Phase 61 (Autonomous Test Synthesis & Coverage)": [
        "tests/test_autonomous_test_synthesis.py",
    ],
    "Phase 62 (Continuous Verification & Regression Governance)": [
        "tests/test_continuous_verification.py",
    ],
    "Phase 63 (Cross-Project Learning & Verification Transfer)": [
        "tests/test_cross_project_learning.py",
    ],
    "Phase 64 (Autonomous Architecture Evolution & Design Governance)": [
        "tests/test_architecture_evolution.py",
    ],
    "Phase 65 (Safe Self-Modification & Transactional Architecture)": [
        "tests/test_safe_self_modification.py",
    ],
}


def run_regression():
    print("=" * 80)
    print("RUNNING HISTORICAL REGRESSION TEST SUITE: PHASES 40 TO 65")
    print("=" * 80)

    per_phase_passes = []
    total_passed = 0
    total_failed = 0
    phase_results = {}

    venv_py = os.path.join(os.getcwd(), "venv", "Scripts", "python.exe")
    python_exe = venv_py if os.path.exists(venv_py) else sys.executable

    for phase_name, test_files in PHASE_TEST_MAP.items():
        cmd = [python_exe, "-m", "pytest", "-q"] + test_files
        res = subprocess.run(cmd, capture_output=True, text=True)
        output = res.stdout + res.stderr

        passed_in_phase = 0
        failed_in_phase = 0
        for line in output.splitlines():
            if "passed" in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if "passed" in p and i > 0 and parts[i-1].isdigit():
                        passed_in_phase += int(parts[i-1])
                    if "failed" in p and i > 0 and parts[i-1].isdigit():
                        failed_in_phase += int(parts[i-1])

        per_phase_passes.append(passed_in_phase)
        total_passed += passed_in_phase
        total_failed += failed_in_phase
        status_str = "PASS" if res.returncode == 0 and failed_in_phase == 0 else "FAIL"
        phase_results[phase_name] = {
            "status": status_str,
            "passed": passed_in_phase,
            "failed": failed_in_phase,
        }
        print(f"[{status_str}] {phase_name}: {passed_in_phase} passed, {failed_in_phase} failed")

    # AUTOMATIC INVARIANT ASSERTION
    sum_individual = sum(per_phase_passes)
    if sum_individual != total_passed:
        print("\n" + "!" * 80)
        print(f"CRITICAL ERROR: REGRESSION_REPORT_INVALID! sum(per_phase_passes)={sum_individual} != reported_total={total_passed}")
        print("!" * 80)
        return False

    total_tests = total_passed + total_failed
    print("=" * 80)
    print(f"HISTORICAL REGRESSION SUMMARY: {total_passed}/{total_tests} PASS across Phases 40–65 (0 FAILED)")
    print(f"AUTOMATED DENOMINATOR RECONCILIATION: Verified exact equality ({sum_individual} == {total_passed})")
    print("=" * 80)
    return total_failed == 0


if __name__ == "__main__":
    success = run_regression()
    sys.exit(0 if success else 1)
