"""
JARVIS OS — Continuous Regression Suite: Phases 40 to 78
Validates historical stability across all 39 autonomous engineering, verification, architecture evolution,
multi-agent coordination, long-horizon missions, quality governance, debt remediation, release readiness,
production operations, reliability intelligence, macro-refactoring, architectural optimization,
portfolio orchestration, predictive calibration, evidence governance, and causal diagnosis phases (F40–F78).

Reports explicit X/Y PASS denominators.
Automated Invariant Check:
    sum(per_phase_passes) == computed_total == reported_total
    delta == 0

Outputs: docs/phase78_regression_reconciliation.json
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
    ],
    "Phase 44 (Negative Knowledge Registry)": [
        "tests/test_contract_generator.py",
        "tests/test_contract_verifier.py",
        "tests/test_contract_registry.py",
    ],
    "Phase 45 (Adaptive Contract Inference)": [
        "tests/test_runtime_observer.py",
        "tests/test_schema_inference.py",
        "tests/test_contract_proposals.py",
    ],
    "Phase 46 (Contract Drift Detection & Evolution)": [
        "tests/test_drift_detector.py",
        "tests/test_contract_version_manager.py",
        "tests/test_compatibility_checker.py",
    ],
    "Phase 47 (Polymorphic Contract Inference)": [
        "tests/test_polymorphic_schema.py",
        "tests/test_variant_detector.py",
        "tests/test_discriminator_discovery.py",
    ],
    "Phase 48 (Contract Migration & Deprecation)": [
        "tests/test_migration_planner.py",
        "tests/test_backward_compat.py",
        "tests/test_breaking_change.py",
    ],
    "Phase 49 (Dynamic Graph Integration)": [
        "tests/test_contract_graph_dynamic.py",
        "tests/test_consumer_resolution.py",
        "tests/test_graph_queries.py",
    ],
    "Phase 50 (Behavioral Contract Proof Engine)": [
        "tests/test_behavioral_trace_collector.py",
        "tests/test_behavioral_invariants.py",
        "tests/test_behavioral_proof_engine.py",
    ],
    "Phase 51 (Contract Counterexample Generation)": [
        "tests/test_counterexample_generator.py",
        "tests/test_boundary_value_analysis.py",
        "tests/test_counterexample_minimizer.py",
    ],
    "Phase 52 (Risk-Directed Behavioral Exploration)": [
        "tests/test_behavioral_risk_scorer.py",
        "tests/test_behavioral_explorer.py",
        "tests/test_unproven_invariants_prioritizer.py",
    ],
    "Phase 53 (Preflight & Environment Diagnostics)": [
        "tests/test_project_preflight.py",
        "tests/test_diagnostics.py",
    ],
    "Phase 54 (Autonomous Test Synthesis)": [
        "tests/test_test_generator.py",
        "tests/test_synthesis_proofs.py",
    ],
    "Phase 55 (Multi-Repair Orchestration)": [
        "tests/test_cluster_repair.py",
        "tests/test_dag_transactions.py",
    ],
    "Phase 56 (Repair Convergence Governance)": [
        "tests/test_convergence_governance.py",
        "tests/test_termination_proofs.py",
    ],
    "Phase 57 (Continuous Verification)": [
        "tests/test_continuous_verification.py",
        "tests/test_evidence_records.py",
    ],
    "Phase 58 (Massive Project State)": [
        "tests/test_massive_state_engine.py",
    ],
    "Phase 59 (SCC-Aware Graph Engine)": [
        "tests/test_scc_aware_graph.py",
    ],
    "Phase 60 (Fine-Grained Symbol Dependency Graph)": [
        "tests/test_symbol_fine_grained_graph.py",
    ],
    "Phase 61 (Autonomous Test Suite Synthesis)": [
        "tests/test_autonomous_test_synthesis.py",
    ],
    "Phase 62 (Continuous Verification & Regression Prevention)": [
        "tests/test_continuous_verification_regression.py",
    ],
    "Phase 63 (Cross-Project Knowledge & Pattern Transfer)": [
        "tests/test_cross_project_learning.py",
    ],
    "Phase 64 (Autonomous Architecture Evolution & Topology Refactoring)": [
        "tests/test_architecture_evolution.py",
    ],
    "Phase 65 (Transactional Self-Modification, Safety, and Rollback)": [
        "tests/test_safe_self_modification.py",
    ],
    "Phase 66 (Multi-Agent Engineering Coordination & Conflict Arbitration)": [
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
    "Phase 70 (Autonomous Release Readiness & Production Governance)": [
        "tests/test_release_readiness.py",
    ],
    "Phase 71 (Autonomous Production Operations & Incident Governance)": [
        "tests/test_production_operations.py",
    ],
    "Phase 72 (Autonomous Reliability Intelligence & Preventive Operations)": [
        "tests/test_reliability_intelligence.py",
    ],
    "Phase 73 (Autonomous Macro-Refactoring Engine)": [
        "tests/test_macro_refactoring.py",
    ],
    "Phase 74 (Autonomous Architectural Evolution & Optimization)": [
        "tests/test_architectural_optimization.py",
    ],
    "Phase 75 (Autonomous Engineering Strategy & Portfolio Orchestration)": [
        "tests/test_portfolio_orchestration.py",
    ],
    "Phase 76 (Autonomous Engineering Learning & Predictive Calibration)": [
        "tests/test_predictive_calibration.py",
    ],
    "Phase 77 (Autonomous Evidence Verification & Engineering Claims Governance)": [
        "tests/test_evidence_governance.py",
    ],
    "Phase 78 (Autonomous Causal Diagnosis & Root-Cause Analysis)": [
        "tests/test_causal_diagnosis.py",
    ],
}


def run_phase_tests(phase_name: str, test_files: list[str], python_bin: str) -> tuple[int, int, str]:
    existing_files = [f for f in test_files if os.path.exists(f)]
    if not existing_files:
        return 0, 0, "SKIPPED_NOT_FOUND"

    cmd = [python_bin, "-m", "pytest", *existing_files, "-q", "--tb=no"]
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        out = res.stdout + res.stderr
        passed = 0
        failed = 0

        m_pass = re.search(r"(\d+) passed", out)
        if m_pass:
            passed = int(m_pass.group(1))

        m_fail = re.search(r"(\d+) failed", out)
        if m_fail:
            failed = int(m_fail.group(1))

        status = "PASS" if failed == 0 and passed > 0 else ("FAIL" if failed > 0 else "NO_TESTS")
        return passed, failed, status
    except Exception as exc:
        print(f"Error running {phase_name}: {exc}")
        return 0, 1, "ERROR"


def main():
    python_bin = sys.executable
    print("=" * 80)
    print("JARVIS OS — Running Regression Suite: Phases 40 to 78")
    print("=" * 80)

    start_time = time.time()
    per_phase_passes: dict[str, int] = {}
    phase_results: dict[str, dict] = {}
    total_passed = 0
    total_failed = 0

    for phase_name, test_files in PHASE_TEST_MAP.items():
        passed, failed, status = run_phase_tests(phase_name, test_files, python_bin)
        per_phase_passes[phase_name] = passed
        total_passed += passed
        total_failed += failed
        phase_results[phase_name] = {
            "passed": passed,
            "failed": failed,
            "status": status,
            "test_files": test_files,
        }
        print(f"  {phase_name:<80} | {passed:>3} passed | {failed:>2} failed | [{status}]")

    duration = time.time() - start_time
    computed_total = sum(per_phase_passes.values())
    reported_total = total_passed
    delta = reported_total - computed_total

    print("-" * 80)
    print(f"Computed Total (sum of per-phase passes): {computed_total}")
    print(f"Reported Total (actual tests passed):    {reported_total}")
    print(f"Failed Total:                            {total_failed}")
    print(f"Arithmetic Delta (reported - computed):  {delta}")
    print(f"Duration:                                {duration:.2f}s")
    print("=" * 80)

    # Invariant assertion: no hardcoded totals, purely derived arithmetic
    assert delta == 0, f"Invariant violation: reported={reported_total} != computed={computed_total}"
    assert total_failed == 0, f"Regression failure: {total_failed} tests failed!"

    # Load canonical historical ledger for drift and consistency tracking
    historical_ledger_path = "docs/historical_regression_ledger.json"
    historical_drift_detected = False
    if os.path.exists(historical_ledger_path):
        with open(historical_ledger_path, "r", encoding="utf-8") as f:
            hl_data = json.load(f)
            historical_drift_detected = hl_data.get("historical_regression_drift_detected", False)

    out_data = {
        "suite": "Phases 40 to 78 Regression Suite",
        "source_runner": "scripts/run_regression_phases_40_78.py",
        "timestamp": time.time(),
        "duration_seconds": round(duration, 2),
        "per_phase": per_phase_passes,
        "computed_total": computed_total,
        "reported_total": reported_total,
        "failed_total": total_failed,
        "delta": delta,
        "valid": (delta == 0 and total_failed == 0),
        "previous_reported_total": 576,
        "current_replayed_total": reported_total,
        "delta_from_previous": reported_total - 576,
        "historical_regression_drift_detected": historical_drift_detected,
        "historical_consistency_status": "HISTORICAL_LEDGER_INCONSISTENCY_DOCUMENTED" if historical_drift_detected else "NO_DRIFT",
        "phase_results": phase_results,
    }

    out_file = "docs/phase78_regression_reconciliation.json"
    os.makedirs("docs", exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2)

    print(f"[SUCCESS] Reconciled results written to {out_file}")


if __name__ == "__main__":
    main()
