"""
JARVIS OS — Phase 62: Generate Canonical Artifacts
Produces:
- docs/phase62_changes.json
- docs/phase62_verification_plans.json
- docs/phase62_test_selection.json
- docs/phase62_execution.json
- docs/phase62_coverage.json
- docs/phase62_regressions.json
- docs/phase62_flaky.json
- docs/phase62_verification_ledger.json
"""

import json
import os
import sys
import time

sys.path.insert(0, os.getcwd())

from backend.agents.continuous_verification.bridge import ContinuousVerificationBridge
from backend.agents.continuous_verification.models import (
    ChangeItem,
    ChangeSet,
    ChangeSource,
    ChangeType,
    CoverageVector,
    FlakyAnalysisResult,
    FlakyStatus,
    RegressionClassification,
    RegressionComparisonResult,
    SelectedTestItem,
    TestSelectionPlan,
    TestSelectionPriority,
    VerificationDecisionOutcome,
    VerificationPolicyName,
    VerificationSurface,
)
from backend.agents.continuous_verification.planner import ContinuousVerificationPlanner
from backend.agents.continuous_verification.policy import VerificationPolicyEngine
from backend.agents.continuous_verification.selector import ContinuousTestSelector


def generate_artifacts():
    docs_dir = os.path.join(os.getcwd(), "docs")
    os.makedirs(docs_dir, exist_ok=True)
    bridge = ContinuousVerificationBridge.get_instance(db_path=":memory:")

    # 1. Changes
    sample_changes = [
        ChangeItem("backend/services/payment.py", "func:process_payment", ChangeType.SYMBOL_CHANGED, "h1", "h2", {"lines_added": 5, "lines_removed": 2}, ChangeSource.WORKSPACE_MODIFICATION),
        ChangeItem("contracts/schemas/payment_dto.py", "class:PaymentDTO", ChangeType.CONTRACT_CHANGED, "h3", "h4", {"lines_added": 3, "lines_removed": 0}, ChangeSource.GIT),
        ChangeItem("backend/legacy/v1_billing.py", "func:old_calc", ChangeType.SYMBOL_REMOVED, "h5", "", {"lines_added": 0, "lines_removed": 12}, ChangeSource.REPAIR_RESULT),
        ChangeItem("frontend/src/features/missions/TaskCard.tsx", None, ChangeType.MODIFIED, "h6", "h7", {"lines_added": 4, "lines_removed": 1}, ChangeSource.RUNTIME_MISSION),
        ChangeItem("tests/test_payment_new.py", None, ChangeType.TEST_CHANGED, "", "h8", {"lines_added": 25, "lines_removed": 0}, ChangeSource.AUTONOMOUS_MODIFICATION),
    ]
    cs = ChangeSet(id="cs_canonical_phase62", changes=sample_changes, source="canonical_generation")
    with open(os.path.join(docs_dir, "phase62_changes.json"), "w", encoding="utf-8") as f:
        json.dump(cs.to_dict(), f, indent=2)

    # 2. Verification Plans
    planner = ContinuousVerificationPlanner()
    surface = bridge.impact_planner.analyze(cs)
    plan_std = planner.create_plan(surface, policy=VerificationPolicyEngine.get_policy(VerificationPolicyName.STANDARD))
    plan_strict = planner.create_plan(surface, policy=VerificationPolicyEngine.get_policy(VerificationPolicyName.STRICT))
    with open(os.path.join(docs_dir, "phase62_verification_plans.json"), "w", encoding="utf-8") as f:
        json.dump({
            "standard_plan": plan_std.to_dict(),
            "strict_plan": plan_strict.to_dict(),
        }, f, indent=2)

    # 3. Test Selection
    selector = ContinuousTestSelector()
    mock_pool = [
        {"test_id": "test_payment_known_failure", "is_regression": True, "target_file": "backend/services/payment.py"},
        {"test_id": "test_process_payment_direct", "target_file": "backend/services/payment.py", "target_symbol": "func:process_payment"},
        {"test_id": "test_payment_consumer_billing", "target_file": "backend/services/billing.py"},
        {"test_id": "test_payment_dto_contract", "target_file": "contracts/schemas/payment_dto.py"},
        {"test_id": "test_payment_pipeline_behavior", "target_file": "backend/workflows/pipeline.py"},
        {"test_id": "test_security_payment_token", "target_file": "backend/services/payment.py"},
        {"test_id": "test_browser_payment_ui", "target_file": "frontend/src/features/missions/TaskCard.tsx", "framework": "playwright"},
        {"test_id": "test_broader_payment_integration", "target_file": "backend/services/payment.py"},
    ]
    sel_plan = selector.select_tests(surface, plan_std, available_tests=mock_pool)
    with open(os.path.join(docs_dir, "phase62_test_selection.json"), "w", encoding="utf-8") as f:
        json.dump(sel_plan.to_dict(), f, indent=2)

    # 4. Execution
    exec_results = bridge.executor.execute_suite(sel_plan.selected)
    with open(os.path.join(docs_dir, "phase62_execution.json"), "w", encoding="utf-8") as f:
        json.dump({
            "total_executed": len(exec_results),
            "results": [r.to_dict() for r in exec_results],
        }, f, indent=2)

    # 5. Coverage
    cov = bridge.coverage_evaluator.compute_coverage(surface, executed_tests=[r.test_id for r in exec_results])
    with open(os.path.join(docs_dir, "phase62_coverage.json"), "w", encoding="utf-8") as f:
        json.dump({
            "vector": cov.to_dict(),
            "composite_score": round((cov.line_coverage + cov.branch_coverage + cov.symbol_coverage + cov.contract_coverage + cov.behavior_coverage + cov.invariant_coverage + cov.consumer_coverage + cov.browser_coverage + cov.mutation_coverage) / 9.0, 4),
        }, f, indent=2)

    # 6. Regressions
    results_map = {r.test_id: r.status for r in exec_results}
    reg_comp = bridge.regression_comparator.compare(current_results=results_map, current_coverage=cov, current_duration=0.45)
    with open(os.path.join(docs_dir, "phase62_regressions.json"), "w", encoding="utf-8") as f:
        json.dump(reg_comp.to_dict(), f, indent=2)

    # 7. Flaky
    flaky_records = [
        FlakyAnalysisResult("test_socket_io_flaky", FlakyStatus.FLAKY, attempts=3, outcomes=["FAIL", "PASS", "PASS"], timing_variance=12.4, environment_variance=0.1, failure_fingerprints=["err_timeout"], review_required=True).to_dict(),
        FlakyAnalysisResult("test_db_stable_pass", FlakyStatus.STABLE_PASS, attempts=1, outcomes=["PASS"], timing_variance=0.0, environment_variance=0.0, failure_fingerprints=[], review_required=False).to_dict(),
    ]
    with open(os.path.join(docs_dir, "phase62_flaky.json"), "w", encoding="utf-8") as f:
        json.dump({"flaky_analysis_records": flaky_records}, f, indent=2)

    # 8. Verification Ledger
    decision = bridge.verify_change(change_set=cs, available_tests=mock_pool)
    with open(os.path.join(docs_dir, "phase62_verification_ledger.json"), "w", encoding="utf-8") as f:
        json.dump({
            "decision_id": decision.decision_id,
            "outcome": decision.outcome.value if hasattr(decision.outcome, "value") else str(decision.outcome),
            "evidence_entries": decision.evidence,
            "signature": decision.evidence[-1]["data_hash"] if decision.evidence else "",
        }, f, indent=2)

    print("Successfully generated all canonical Phase 62 artifacts in docs/.")


if __name__ == "__main__":
    generate_artifacts()
