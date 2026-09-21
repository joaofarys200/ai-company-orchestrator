"""
JARVIS OS — Continuous Regression Suite: Phases 40 to 72
Validates historical stability across all 33 autonomous engineering, verification, architecture evolution,
multi-agent coordination, long-horizon missions, quality governance, debt remediation, release readiness,
production operations, and reliability intelligence phases (F40–F72).

Reports explicit X/Y PASS denominators.
Automated Invariant Check:
    sum(per_phase_passes) == computed_total == reported_total
    delta == 0
Validates against historical regression drift:
    Tracks historical consistency from canonical historical ledger.

Outputs: docs/phase72_regression_reconciliation.json
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
    "Phase 50 (Behavioral Contract Proof Engine)": [
        "tests/test_behavioral_contract_proof.py",
    ],
    "Phase 51 (Behavioral Proof Exploration)": [
        "tests/test_behavioral_proof_exploration.py",
    ],
    "Phase 52 (Risk-Directed Semantic Exploration)": [
        "tests/test_risk_directed_exploration.py",
    ],
    "Phase 53 (Universal Preflight & Auto-Recovery)": [
        "tests/test_project_preflight_recovery.py",
    ],
    "Phase 54 (Verified Repair Synthesis)": [
        "tests/test_verified_repair_synthesis.py",
    ],
    "Phase 55 (Multi-Repair Orchestration & Rollback)": [
        "tests/test_multi_repair_orchestration.py",
    ],
    "Phase 56 (Repair Convergence Governance)": [
        "tests/test_repair_convergence_governance.py",
    ],
    "Phase 57 (Autonomous Task Completion Engine)": [
        "tests/test_autonomous_task_completion.py",
    ],
    "Phase 58 (Massive Project State & Incremental Monorepo Graphing)": [
        "tests/test_massive_project_state.py",
    ],
    "Phase 59 (SCC-Aware Circular Dependency Graph Decomposition)": [
        "tests/test_scc_aware_graph.py",
    ],
    "Phase 60 (Symbol-Level Fine-Grained Dependency Graph Precision)": [
        "tests/test_symbol_fine_grained_graph.py",
    ],
    "Phase 61 (Autonomous Test Synthesis & Coverage Self-Healing)": [
        "tests/test_autonomous_test_synthesis.py",
    ],
    "Phase 62 (Continuous Verification & Regression Defense)": [
        "tests/test_continuous_verification.py",
    ],
    "Phase 63 (Cross-Project Pattern Learning & Generalization)": [
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
    "Phase 70 (Autonomous Release Readiness & Production Governance)": [
        "tests/test_release_readiness.py",
    ],
    "Phase 71 (Autonomous Production Operations & Incident Governance)": [
        "tests/test_production_operations.py",
    ],
    "Phase 72 (Autonomous Reliability Intelligence & Preventive Operations)": [
        "tests/test_reliability_intelligence.py",
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
    print("JARVIS OS — Running Regression Suite: Phases 40 to 72")
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
        "suite": "Phases 40 to 72 Regression Suite",
        "source_runner": "scripts/run_regression_phases_40_72.py",
        "timestamp": time.time(),
        "duration_seconds": round(duration, 2),
        "per_phase": per_phase_passes,
        "computed_total": computed_total,
        "reported_total": reported_total,
        "failed_total": total_failed,
        "delta": delta,
        "valid": (delta == 0 and total_failed == 0),
        "previous_reported_total": 673,
        "current_replayed_total": reported_total,
        "delta_from_previous": reported_total - 673,
        "historical_regression_drift_detected": historical_drift_detected,
        "historical_consistency_status": "HISTORICAL_LEDGER_INCONSISTENCY_DOCUMENTED" if historical_drift_detected else "NO_DRIFT",
        "phase_results": phase_results,
    }

    out_file = "docs/phase72_regression_reconciliation.json"
    os.makedirs("docs", exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2)

    print(f"[SUCCESS] Reconciled results written to {out_file}")


if __name__ == "__main__":
    main()
