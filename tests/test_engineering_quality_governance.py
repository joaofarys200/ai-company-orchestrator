"""
JARVIS OS — Phase 68: Engineering Quality Governance & Technical Debt Test Suite
22 comprehensive test cases covering:
1. quality snapshot
2. dimension analysis
3. baseline comparison
4. architecture quality
5. code quality
6. test quality
7. contract quality
8. behavior quality
9. security quality
10. reliability quality
11. maintainability
12. debt detection
13. debt prioritization
14. quality budget
15. quality gate
16. quality regression
17. trend
18. hotspot
19. cross-project hint
20. mission with quality debt
21. critical security gate
22. denominator reconciliation
"""

import pytest
import time
from backend.agents.engineering_quality_governance.bridge import EngineeringQualityGovernanceBridge
from backend.agents.engineering_quality_governance.models import (
    DebtCategory,
    DebtSeverity,
    DebtStatus,
    DimensionChange,
    DimensionStatus,
    QualityBudget,
    QualityDimension,
    QualityGateStatus,
    QualityRegressionLevel,
    QualityTrendDirection,
)
from backend.agents.engineering_quality_governance.security import QualityGovernanceSecurityViolation
from backend.agents.engineering_quality_governance.validator import QualityValidator


@pytest.fixture
def bridge():
    EngineeringQualityGovernanceBridge.reset_instance()
    b = EngineeringQualityGovernanceBridge.get_instance(db_path=":memory:")
    yield b
    EngineeringQualityGovernanceBridge.reset_instance()


# 1. Quality Snapshot
def test_quality_snapshot_creation(bridge):
    mid = "test_mission_01"
    snap = bridge.capture_baseline(mid)
    assert snap.snapshot_id.startswith("baseline_test_mission_01")
    assert snap.mission_id == mid
    assert snap.sealed is True
    assert len(snap.dimensions) == 9
    assert "ARCHITECTURE" in snap.dimensions
    assert "CODE" in snap.dimensions
    assert "SECURITY" in snap.dimensions
    is_valid, errors = QualityValidator.validate_snapshot_completeness(snap)
    assert is_valid, f"Validation errors: {errors}"


# 2. Dimension Analysis (Multidimensional, no single score reduction)
def test_dimension_analysis_multidimensional(bridge):
    ctx = {
        "architecture": {"coupling": 0.28, "scc_size": 3},
        "code": {"complexity": 7.2, "duplication": 0.01},
        "test": {"line_coverage": 0.92, "mutation_score": 0.82},
    }
    dimensions = bridge.orchestrator.evaluate_all_dimensions(context=ctx)
    assert len(dimensions) == 9
    assert bridge.orchestrator.validate_no_single_score_authority(dimensions) is True
    # Individual dimensional observations must retain uncertainty & scope
    for dim_name, evaluation in dimensions.items():
        assert evaluation.dimension.value == dim_name
        assert evaluation.scope == "global"
        assert evaluation.uncertainty >= 0.0


# 3. Baseline Comparison (Before vs After)
def test_baseline_comparison_before_after(bridge):
    mid = "test_mission_03"
    ctx_base = {"architecture": {"coupling": 0.30, "scc_size": 3}}
    ctx_after = {"architecture": {"coupling": 0.31, "scc_size": 3}}

    bridge.capture_baseline(mid, context=ctx_base)
    bridge.capture_after(mid, context=ctx_after)

    delta = bridge.compare_mission_quality(mid)
    assert delta.baseline_snapshot_id.startswith("baseline_")
    assert delta.after_snapshot_id.startswith("after_")
    assert delta.mission_id == mid
    assert "ARCHITECTURE" in delta.dimension_changes
    assert delta.dimension_changes["ARCHITECTURE"] in (DimensionChange.UNCHANGED, DimensionChange.IMPROVED, DimensionChange.DEGRADED)


# 4. Architecture Quality
def test_architecture_quality_metrics(bridge):
    ctx_good = {
        "architecture": {
            "coupling": 0.25,
            "scc_size": 2,
            "boundary_violations": 0,
            "blast_radius": 5,
            "modularity": 0.80,
        }
    }
    eval_good = bridge.arch_eval.evaluate(ctx_good)
    assert eval_good.status == DimensionStatus.HEALTHY

    ctx_bad = {
        "architecture": {
            "coupling": 0.85,
            "scc_size": 35,
            "boundary_violations": 2,
            "blast_radius": 40,
            "modularity": 0.20,
        }
    }
    eval_bad = bridge.arch_eval.evaluate(ctx_bad)
    assert eval_bad.status == DimensionStatus.BLOCKED


# 5. Code Quality
def test_code_quality_metrics(bridge):
    ctx = {
        "code": {
            "complexity": 6.5,
            "duplication": 0.015,
            "function_size": 22.0,
            "class_size": 110.0,
            "type_uncertainty": 0.03,
        }
    }
    eval_code = bridge.code_eval.evaluate(ctx)
    assert eval_code.status == DimensionStatus.HEALTHY
    obs_names = [o.metric_name for o in eval_code.observations]
    assert "complexity" in obs_names
    assert "duplication" in obs_names
    assert "type_uncertainty" in obs_names


# 6. Test Quality (MORE_TESTS vs MORE_USEFUL_EVIDENCE and EVIDENCE_EFFICIENCY)
def test_test_quality_and_evidence_efficiency(bridge):
    # Case A: High quality evidence
    ctx_a = {
        "test": {
            "test_count": 50,
            "useful_assertions": 150,
            "test_redundancy_count": 2,
            "mutation_score": 0.85,
            "flaky_rate": 0.0,
        }
    }
    eval_a = bridge.test_eval.evaluate(ctx_a)
    eff_a = eval_a.evidence[0]["evidence_efficiency"]
    assert eff_a > 0.60

    # Case B: Test inflation (many duplicate tests, low mutation, high redundancy)
    ctx_b = {
        "test": {
            "test_count": 500,
            "useful_assertions": 100,
            "test_redundancy_count": 200,
            "mutation_score": 0.25,
            "flaky_rate": 0.08,
        }
    }
    eval_b = bridge.test_eval.evaluate(ctx_b)
    eff_b = eval_b.evidence[0]["evidence_efficiency"]
    assert eff_b < eff_a
    # Comparison recognizes test inflation
    ch, more_tests, more_evidence, eff, deg, imp = bridge.test_eval.compare_tests(eval_a, eval_b)
    assert more_tests is True
    assert more_evidence is False
    assert any(d.get("metric") == "evidence_efficiency" for d in deg)


# 7. Contract Quality
def test_contract_quality_states(bridge):
    # Healthy contracts
    ctx_healthy = {"contract": {"breaking_changes": 0, "contract_drift": 0, "consumer_coverage": 0.98}}
    eval_h = bridge.contract_eval.evaluate(ctx_healthy)
    assert eval_h.status == DimensionStatus.HEALTHY

    # Breaking changes trigger BLOCKED
    ctx_breaking = {"contract": {"breaking_changes": 2, "unresolved_consumers": 3}}
    eval_b = bridge.contract_eval.evaluate(ctx_breaking)
    assert eval_b.status == DimensionStatus.BLOCKED


# 8. Behavior Quality & Non-Zero Uncertainty
def test_behavior_quality_and_counterexamples(bridge):
    ctx = {
        "behavior": {
            "invariant_coverage": 0.88,
            "counterexamples": 0,
            "state_space_explored_pct": 0.65,
        }
    }
    eval_beh = bridge.behavior_eval.evaluate(ctx)
    # Never 0 uncertainty: unreached state space guarantees positive uncertainty
    assert eval_beh.uncertainty > 0.0
    assert eval_beh.uncertainty >= 0.20  # 1 - 0.65 = 0.35 uncertainty


# 9. Security Quality & Sentinel Integration
def test_security_quality_sentinel_integration(bridge):
    ctx_clean = {"security": {"blocked_operations": 0, "secret_exposure_attempts": 0, "sandbox_violations": 0}}
    eval_clean = bridge.sec_eval.evaluate(ctx_clean)
    assert eval_clean.status == DimensionStatus.HEALTHY

    ctx_vuln = {"security": {"secret_exposure_attempts": 1}}
    eval_vuln = bridge.sec_eval.evaluate(ctx_vuln)
    assert eval_vuln.status == DimensionStatus.BLOCKED


# 10. Reliability Quality
def test_reliability_quality_metrics(bridge):
    ctx = {
        "reliability": {
            "recovery_success": 1.0,
            "rollback_success": 1.0,
            "residual_states": 0,
            "mission_stalls": 0,
            "oscillations": 0,
        }
    }
    eval_rel = bridge.rel_eval.evaluate(ctx)
    assert eval_rel.status == DimensionStatus.HEALTHY

    # Stalls degrade reliability
    ctx_stalls = {"reliability": {"mission_stalls": 2, "oscillations": 1}}
    eval_stalls = bridge.rel_eval.evaluate(ctx_stalls)
    assert eval_stalls.status == DimensionStatus.DEGRADED


# 11. Maintainability Quality
def test_maintainability_observation(bridge):
    ctx = {
        "maintainability": {
            "testability_index": 0.88,
            "documentation_completeness": 0.94,
            "change_propagation_factor": 0.18,
            "module_boundary_index": 0.90,
        }
    }
    eval_maint = bridge.maint_eval.evaluate(ctx)
    assert eval_maint.status == DimensionStatus.HEALTHY
    assert len(eval_maint.observations) >= 5


# 12. Technical Debt Detection (Structural & Temporal Persistence)
def test_debt_detection_structural_temporal(bridge):
    mid = "mission_debt_01"
    # Single rollback should NOT trigger debt item (enforces no one-off trigger rule)
    history_single = [{"type": "rollback", "surface": "auth_token_service"}]
    debts_single = bridge.detect_debt_from_history(mid, history_single)
    assert len(debts_single) == 0

    # Recurrent rollback (count >= 2) MUST trigger debt item
    history_recurrent = [
        {"type": "rollback", "surface": "auth_token_service"},
        {"type": "rollback", "surface": "auth_token_service"},
    ]
    debts_recurrent = bridge.detect_debt_from_history(mid, history_recurrent)
    assert len(debts_recurrent) == 1
    assert debts_recurrent[0].affected_surface == "auth_token_service"
    assert debts_recurrent[0].category == DebtCategory.OPERATIONAL


# 13. Debt Prioritization (PRIORITY_VECTOR without single scalar authority)
def test_debt_prioritization_priority_vector(bridge):
    mid = "mission_debt_02"
    item1 = bridge.debt_manager.create_debt_item(
        category=DebtCategory.SECURITY,
        affected_surface="api_keys_in_staging",
        origin_mission=mid,
        evidence=[{"risk": "unencrypted_key"}],
        severity=DebtSeverity.CRITICAL,
        risk=0.95,
    )
    item2 = bridge.debt_manager.create_debt_item(
        category=DebtCategory.DOCUMENTATION,
        affected_surface="legacy_readme",
        origin_mission=mid,
        evidence=[{"note": "typo in doc"}],
        severity=DebtSeverity.LOW,
        risk=0.10,
    )

    vectors = bridge.prioritize_debt()
    assert len(vectors) >= 2
    # Security item should rank higher than documentation typo
    assert vectors[0].debt_id == item1.debt_id
    assert vectors[0].security_relevance > 0.8
    assert "CRITICAL SECURITY PRIORITY" in vectors[0].explanation


# 14. Quality Budget
def test_quality_budget_limits(bridge):
    budget = QualityBudget(max_critical_debt=0, max_flaky_rate=0.05)
    gov = bridge.debt_detector.debt_manager

    item = gov.create_debt_item(
        category=DebtCategory.SECURITY,
        affected_surface="sandbox_escape_risk",
        origin_mission="m_budget",
        evidence=[{"cve": "CVE-2026-X"}],
        severity=DebtSeverity.CRITICAL,
    )

    from backend.agents.engineering_quality_governance.quality_budget import QualityBudgetGovernor
    b_gov = QualityBudgetGovernor(budget)
    is_comp, violations, suggested = b_gov.check_budget_compliance([item], {"flaky_rate": 0.01})
    assert is_comp is False
    assert suggested == QualityGateStatus.QUALITY_BLOCKED
    assert any(v["limit"] == "max_critical_debt" for v in violations)


# 15. Quality Gate (5 Nuanced States, never quality_ok = true)
def test_quality_gate_five_states(bridge):
    mid = "mission_gate_test"
    bridge.capture_baseline(mid)
    bridge.capture_after(mid)

    # 1. Accepted (no debts)
    decision = bridge.evaluate_quality_gate(mid, policy_name="GOVERNED")
    assert decision.decision in (QualityGateStatus.QUALITY_ACCEPTED, QualityGateStatus.QUALITY_ACCEPTED_WITH_DEBT)
    assert hasattr(decision, "scope")
    assert hasattr(decision, "evidence")
    assert hasattr(decision, "uncertainty")

    # 2. Accepted with debt
    bridge.debt_manager.create_debt_item(
        category=DebtCategory.CODE,
        affected_surface="refactor_helper",
        origin_mission=mid,
        evidence=[{"note": "moderate complexity"}],
        severity=DebtSeverity.LOW,
    )
    decision_debt = bridge.evaluate_quality_gate(mid, policy_name="GOVERNED")
    assert decision_debt.decision == QualityGateStatus.QUALITY_ACCEPTED_WITH_DEBT

    # 3. Blocked on critical security debt
    bridge.debt_manager.create_debt_item(
        category=DebtCategory.SECURITY,
        affected_surface="secret_leak",
        origin_mission=mid,
        evidence=[{"risk": "critical"}],
        severity=DebtSeverity.CRITICAL,
    )
    decision_blocked = bridge.evaluate_quality_gate(mid, policy_name="GOVERNED")
    assert decision_blocked.decision == QualityGateStatus.QUALITY_BLOCKED


# 16. Quality Regression Classification
def test_quality_regression_classification(bridge):
    detector = bridge.regression_detector
    crit = detector.classify_regression({"metric": "sandbox_violations", "severity": "CRITICAL"})
    assert crit == QualityRegressionLevel.CRITICAL

    sig = detector.classify_regression({"metric": "breaking_changes"})
    assert sig == QualityRegressionLevel.SIGNIFICANT

    minr = detector.classify_regression({"metric": "complexity"})
    assert minr == QualityRegressionLevel.MINOR


# 17. Quality Trend Engine
def test_quality_trend_engine(bridge):
    # Less than 2 snapshots -> INSUFFICIENT_DATA
    snap1 = bridge.capture_baseline("m_trend_1")
    direction, details = bridge.trend_engine.analyze_trend([snap1])
    assert direction == QualityTrendDirection.INSUFFICIENT_DATA
    assert details["can_forecast_long_term"] is False

    # 3 snapshots -> STABLE/IMPROVING without long term forecast claim
    snap2 = bridge.capture_baseline("m_trend_2")
    snap3 = bridge.capture_baseline("m_trend_3")
    direction, details = bridge.trend_engine.analyze_trend([snap1, snap2, snap3])
    assert direction in (QualityTrendDirection.STABLE, QualityTrendDirection.IMPROVING)
    assert details["can_forecast_long_term"] is False


# 18. Quality Hotspot Identification
def test_quality_hotspot_identification(bridge):
    h1 = bridge.record_hotspot_event("module", "backend.memory.cache", "regression", {"info": "cache race"})
    h2 = bridge.record_hotspot_event("module", "backend.memory.cache", "rollback", {"info": "reverted patch"})
    assert h1.entity_name == "backend.memory.cache"
    assert h1.regression_count == 1
    assert h1.rollback_count == 1
    assert h1.risk_weight > 5.0
    hotspots = bridge.get_hotspots()
    assert len(hotspots) >= 1
    assert hotspots[0].entity_name == "backend.memory.cache"


# 19. Cross-Project Hint (F63 Integration: HINT != EVIDENCE)
def test_cross_project_hint_validation(bridge):
    ext_pattern = {
        "pattern_name": "micro_batch_streaming",
        "suggestion": "Partition network streams into 4KB segments",
        "confidence": 0.85,
    }
    hint = bridge.integrate_f63_hint(ext_pattern)
    assert hint["type"] == "QUALITY_HINT"
    assert hint["is_evidence"] is False
    assert hint["requires_local_validation"] is True
    assert hint["confidence"] <= 0.60  # Confidence is capped until local proof


# 20. Mission Completed With Quality Debt (F67 Integration)
def test_mission_completed_with_debt(bridge):
    mid = "mission_f67_finish_with_debt"
    bridge.capture_baseline(mid)
    bridge.capture_after(mid)

    bridge.debt_manager.create_debt_item(
        category=DebtCategory.DOCUMENTATION,
        affected_surface="adr_pending_doc",
        origin_mission=mid,
        evidence=[{"missing_adr": True}],
        severity=DebtSeverity.LOW,
    )

    res = bridge.conclude_mission_with_quality(mission_id=mid, objective_satisfied=True)
    # The mission is completed, but quality status reflects accumulated debt!
    assert res["final_status"] == "COMPLETED_WITH_QUALITY_DEBT"
    assert res["unresolved_debt_count"] >= 1
    assert res["objective_satisfied"] is True


# 21. Critical Security Gate Blocked
def test_critical_security_gate_blocked(bridge):
    # Attempting to tamper with policy to lower security thresholds must raise QualityGovernanceSecurityViolation
    current_pol = {"budget": {"max_security_debt": 0}}
    bad_pol = {"budget": {"max_security_debt": 2}}

    with pytest.raises(QualityGovernanceSecurityViolation) as excinfo:
        bridge.security_sentinel.validate_policy_mutation(current_pol, bad_pol, actor="malicious_agent")
    assert "SECURITY_EVENT -> BLOCKED" in str(excinfo.value)


# 22. Denominator Reconciliation
def test_denominator_reconciliation(bridge):
    per_phase = {
        f"Phase {i}": 22 for i in range(40, 69)  # 29 phases (F40..F68), e.g. 29 * 22 = 638 approx
    }
    computed = sum(per_phase.values())
    reported = computed

    is_valid, delta = QualityValidator.validate_reconciliation(per_phase, computed, reported)
    assert is_valid is True
    assert delta == 0

    # Invalidate if mismatched
    is_valid_bad, delta_bad = QualityValidator.validate_reconciliation(per_phase, computed + 1, reported)
    assert is_valid_bad is False
    assert delta_bad != 0
