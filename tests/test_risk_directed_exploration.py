"""
JARVIS OS — Phase 52: Risk-Directed Behavioral Exploration & Adaptive Proof Search
Comprehensive 24-Scenario Automated Test Suite.
"""

from __future__ import annotations

import copy
import pytest

from agents.behavioral_contract_proof.models import (
    BehaviorBaseline,
    Counterexample,
    ExecutionGateDecision,
    ProofResult,
)
from agents.behavioral_proof_exploration.models import (
    BehavioralCoverage,
    BehavioralScenario,
    CoverageThresholdPolicy,
    ExplorationStrategy,
)
from agents.behavioral_proof_exploration.executor import ScenarioExecutor
from agents.risk_directed_exploration.bridge import RiskDirectedExplorationBridge
from agents.risk_directed_exploration.budget import (
    RiskAdaptiveBudgetController,
    RiskBudgetExhaustedError,
)
from agents.risk_directed_exploration.cache import DeterministicRankingCache
from agents.risk_directed_exploration.coverage import AdaptiveCoverageTracker
from agents.risk_directed_exploration.explorer import RiskDirectedExplorer
from agents.risk_directed_exploration.feedback import AdaptiveFeedbackController
from agents.risk_directed_exploration.index import RiskExplorationIndex
from agents.risk_directed_exploration.memory import ExplorationMemoryBridge
from agents.risk_directed_exploration.models import (
    AdaptiveProofResult,
    BehavioralExplorationRisk,
    BehavioralUncertainty,
    ExplorationPolicy,
    RiskAdaptiveBudget,
    ScenarioGraph,
    ScenarioRanking,
)
from agents.risk_directed_exploration.policy import ExplorationPolicyEngine
from agents.risk_directed_exploration.ranking import ScenarioRanker
from agents.risk_directed_exploration.risk import RiskEvaluator
from agents.risk_directed_exploration.scheduler import AdaptiveScenarioScheduler
from agents.risk_directed_exploration.security import (
    PriorityPoisoningDetectedError,
    RiskSecuritySentinel,
    RiskSpoofingDetectedError,
)
from agents.risk_directed_exploration.uncertainty import UncertaintyEvaluator
from agents.risk_directed_exploration.validator import AdaptiveProofValidator
from agents.risk_directed_exploration.value import ValueOfInformationEstimator


@pytest.fixture
def sample_schema():
    return {
        "type": "object",
        "required": ["id", "amount", "currency"],
        "properties": {
            "id": {"type": "string"},
            "amount": {"type": "number", "minimum": 0.01},
            "currency": {"type": "string", "enum": ["EUR", "USD", "GBP"]},
            "role": {"type": "string", "enum": ["USER", "ADMIN"]},
        },
    }


# ==============================================================================
# 1. Risk Calculation (11 Dimensions)
# ==============================================================================
def test_01_risk_calculation():
    evaluator = RiskEvaluator()
    risk = evaluator.evaluate_risk(
        contract_schema_delta={"removed_fields": ["old_field"]},
        consumers=["c1", "c2", "c3"],
        is_economic=True,
        is_security_critical=True,
        predictive_impact_level="HIGH",
    )

    assert risk.economic_risk == 1.0
    assert risk.security_risk == 1.0
    assert risk.blast_radius == 0.9
    assert risk.risk_score >= 0.70
    d = risk.to_dict()
    assert len(d) == 12
    assert "risk_score" in d


# ==============================================================================
# 2. Uncertainty Calculation (Continuous Score)
# ==============================================================================
def test_02_uncertainty_calculation():
    evaluator = UncertaintyEvaluator()
    unc = evaluator.evaluate_uncertainty(
        has_uncertain_consumer=True,
        insufficient_evidence=True,
        coverage_pct=0.40,
        coverage_threshold=0.80,
        unknown_variants_count=2,
    )

    assert unc.uncertain_consumer == 0.9
    assert unc.insufficient_evidence == 0.85
    assert unc.uncertainty_score > 0.50
    assert isinstance(unc.uncertainty_score, float)


# ==============================================================================
# 3. Information Value (Value of Information Estimator)
# ==============================================================================
def test_03_information_value():
    estimator = ValueOfInformationEstimator()
    risk = BehavioralExplorationRisk(economic_risk=1.0, risk_score=0.8)
    uncertainty = BehavioralUncertainty(uncertainty_score=0.7)

    scen_high = BehavioralScenario.create(
        "c1", "k1", {"amount": 0.0}, {"status": 400}, coverage_target="boundary_amount_0"
    )
    scen_low = BehavioralScenario.create(
        "c1", "k1", {"note": "abc"}, {"status": 200}, coverage_target="optional_note"
    )

    val_high = estimator.estimate_value(scen_high, risk, uncertainty)
    val_low = estimator.estimate_value(scen_low, risk, uncertainty)

    assert val_high.total_information_value > val_low.total_information_value
    assert len(val_high.explanation) > 0


# ==============================================================================
# 4. Deterministic Ranking
# ==============================================================================
def test_04_deterministic_ranking():
    ranker = ScenarioRanker()
    risk = BehavioralExplorationRisk(risk_score=0.6)
    uncertainty = BehavioralUncertainty(uncertainty_score=0.5)

    scenarios = [
        BehavioralScenario.create("c1", "k1", {"id": "1"}, {"status": 200}, coverage_target="valid_canonical"),
        BehavioralScenario.create("c1", "k1", {"id": "2"}, {"status": 400}, coverage_target="boundary_amount_0"),
        BehavioralScenario.create("c1", "k1", {"id": "3"}, {"status": 401}, coverage_target="authorization_failure"),
    ]

    r1 = ranker.rank_scenarios(scenarios, risk, uncertainty)
    r2 = ranker.rank_scenarios(scenarios, risk, uncertainty)

    assert [item.scenario_id for item in r1] == [item.scenario_id for item in r2]
    assert [item.priority for item in r1] == [item.priority for item in r2]


# ==============================================================================
# 5. Tie Breaking (Deterministic by scenario_id)
# ==============================================================================
def test_05_tie_breaking():
    ranker = ScenarioRanker()
    risk = BehavioralExplorationRisk(risk_score=0.5)
    uncertainty = BehavioralUncertainty(uncertainty_score=0.5)

    # Scenarios with identical inputs/targets but distinct scenario_ids
    s_a = BehavioralScenario.create("c1", "k1", {"id": "same"}, {"status": 200}, seed=1, coverage_target="target_x")
    s_b = BehavioralScenario.create("c1", "k1", {"id": "same"}, {"status": 200}, seed=2, coverage_target="target_x")

    res = ranker.rank_scenarios([s_b, s_a], risk, uncertainty)
    # Alphabetical order of scenario_id on priority tie
    assert res[0].scenario_id < res[1].scenario_id


# ==============================================================================
# 6. Adaptive Re-Ranking
# ==============================================================================
def test_06_adaptive_re_ranking():
    scheduler = AdaptiveScenarioScheduler()
    risk = BehavioralExplorationRisk(economic_risk=0.9, risk_score=0.8)
    uncertainty = BehavioralUncertainty(uncertainty_score=0.7)

    scenarios = [
        BehavioralScenario.create("c1", "k1", {"amount": 0}, {"status": 400}, coverage_target="boundary_amount_0"),
        BehavioralScenario.create("c1", "k1", {"note": "x"}, {"status": 200}, coverage_target="optional_note"),
    ]
    scheduler.set_candidate_pool(scenarios)

    first = scheduler.select_next(risk, uncertainty)
    assert first is not None
    assert first.coverage_target == "boundary_amount_0"

    # After observing amount pass, economic risk drops
    reduced_risk = BehavioralExplorationRisk(economic_risk=0.1, risk_score=0.2)
    second = scheduler.select_next(reduced_risk, uncertainty)
    assert second is not None
    assert second.coverage_target == "optional_note"


# ==============================================================================
# 7. Coverage Feedback (Incremental updates)
# ==============================================================================
def test_07_coverage_feedback(sample_schema):
    tracker = AdaptiveCoverageTracker()
    scen1 = BehavioralScenario.create("c1", "k1", {"id": "1", "amount": 10.0, "currency": "EUR"}, {"status": 200})
    res1 = ScenarioExecutor().execute(scen1)

    cov1 = tracker.update_with_execution("scp_1", scen1, res1, sample_schema, ["c1"])
    assert cov1.overall_percentage > 0.0

    scen2 = BehavioralScenario.create("c1", "k1", {"id": "2", "amount": 0.0}, {"status": 400}, coverage_target="boundary_amount_0")
    res2 = ScenarioExecutor().execute(scen2)
    cov2 = tracker.update_with_execution("scp_1", scen2, res2, sample_schema, ["c1"])

    assert len(tracker.get_executed_scenarios()) == 2
    assert cov2.overall_percentage >= cov1.overall_percentage


# ==============================================================================
# 8. Counterexample Feedback (Cluster probe generation)
# ==============================================================================
def test_08_counterexample_feedback():
    feedback = AdaptiveFeedbackController()
    risk = BehavioralExplorationRisk(economic_risk=0.3, risk_score=0.4)
    uncertainty = BehavioralUncertainty(uncertainty_score=0.4)

    scen = BehavioralScenario.create("c1", "k1", {"amount": 100.0, "discount_rate": -0.1}, {"status": 200}, coverage_target="discount_amount")
    cx = Counterexample("cx_01", scen.input, scen.expected_behavior, {"status_code": 500}, "Negative discount divergence", scen.consumer_id, scen.contract_id, "tr_1")

    new_risk, new_unc, derived = feedback.process_counterexample_observation(scen, cx, risk, uncertainty)

    assert new_risk.economic_risk == 1.0
    assert len(derived) > 0
    assert any("derived_probe" in s.coverage_target for s in derived)


# ==============================================================================
# 9. Experience Memory Influence
# ==============================================================================
def test_09_experience_memory_influence():
    memory = ExplorationMemoryBridge()
    scen = BehavioralScenario.create("c1", "k_payment", {"amount": -50}, {"status": 400}, coverage_target="negative_amount")

    # Record historical failure
    memory.record_exploration_experience(
        contract_id="k_payment",
        scenario=scen,
        risk_before=0.8,
        risk_after=0.9,
        coverage_delta=0.1,
        had_divergence=True,
    )

    weight_known = memory.get_historical_failure_weight("k_payment", "negative_amount")
    weight_unknown = memory.get_historical_failure_weight("k_other", "clean_field")

    assert weight_known > weight_unknown


# ==============================================================================
# 10. Predictive Impact Influence
# ==============================================================================
def test_10_predictive_impact_influence():
    evaluator = RiskEvaluator()
    risk_high_impact = evaluator.evaluate_risk(predictive_impact_level="CRITICAL")
    risk_low_impact = evaluator.evaluate_risk(predictive_impact_level="LOCAL")

    assert risk_high_impact.blast_radius > risk_low_impact.blast_radius
    assert risk_high_impact.risk_score > risk_low_impact.risk_score


# ==============================================================================
# 11. Economic Override (Mandatory minimum scenario set)
# ==============================================================================
def test_11_economic_override():
    policy_engine = ExplorationPolicyEngine()
    executed_good = [
        BehavioralScenario.create("c1", "k1", {}, {}, coverage_target="authorization"),
        BehavioralScenario.create("c1", "k1", {}, {}, coverage_target="boundary"),
        BehavioralScenario.create("c1", "k1", {}, {}, coverage_target="currency"),
        BehavioralScenario.create("c1", "k1", {}, {}, coverage_target="retry_idempotency"),
        BehavioralScenario.create("c1", "k1", {}, {}, coverage_target="timeout_recovery"),
        BehavioralScenario.create("c1", "k1", {}, {}, coverage_target="partial_failure_rollback"),
    ]
    passed_good, missing_good = policy_engine.verify_mandatory_scenarios(ExplorationPolicy.ECONOMIC_CRITICAL, executed_good)
    assert passed_good is True
    assert len(missing_good) == 0

    executed_bad = [BehavioralScenario.create("c1", "k1", {}, {}, coverage_target="optional_note")]
    passed_bad, missing_bad = policy_engine.verify_mandatory_scenarios(ExplorationPolicy.ECONOMIC_CRITICAL, executed_bad)
    assert passed_bad is False
    assert len(missing_bad) > 0


# ==============================================================================
# 12. Security Override
# ==============================================================================
def test_12_security_override():
    ranker = ScenarioRanker()
    risk = BehavioralExplorationRisk(security_risk=1.0, risk_score=0.8)
    uncertainty = BehavioralUncertainty(uncertainty_score=0.5)

    scenarios = [
        BehavioralScenario.create("c1", "k1", {}, {}, coverage_target="generic_payload"),
        BehavioralScenario.create("c1", "k1", {}, {}, coverage_target="authorization_state"),
    ]

    rankings = ranker.rank_scenarios(scenarios, risk, uncertainty, policy=ExplorationPolicy.SECURITY_CRITICAL)
    assert rankings[0].target_field == "authorization_state"
    assert rankings[0].policy_override_applied is True


# ==============================================================================
# 13. Risk Spoofing Detection
# ==============================================================================
def test_13_risk_spoofing_detection():
    sentinel = RiskSecuritySentinel()
    # Attempting to declare economic_risk = 0.0 on an economic operation
    spoofed_risk = BehavioralExplorationRisk(economic_risk=0.0, risk_score=0.1)

    with pytest.raises(RiskSpoofingDetectedError):
        sentinel.inspect_risk_assessment(spoofed_risk, is_economic=True)


# ==============================================================================
# 14. Coverage Spoofing Detection
# ==============================================================================
def test_14_coverage_spoofing_detection():
    sentinel = RiskSecuritySentinel()
    spoofed_coverage = BehavioralCoverage(
        coverage_id="cov_fake",
        scope_id="scp_1",
        dimensions={},
        overall_percentage=0.99,
        threshold_policy=CoverageThresholdPolicy.STANDARD,
        threshold_met=True,
    )
    with pytest.raises(Exception):
        sentinel.inspect_coverage(spoofed_coverage, scenarios=[])


# ==============================================================================
# 15. Deterministic Replay
# ==============================================================================
def test_15_deterministic_replay():
    cache = DeterministicRankingCache()
    rankings = [
        ScenarioRanking("s1", 2.5, 1, 0.8, 0.9, 0.7, 1.0),
        ScenarioRanking("s2", 1.2, 2, 0.8, 0.4, 0.3, 1.0),
    ]
    cache.store_rankings("payContract", "ECONOMIC_CRITICAL", 42, rankings)

    retrieved = cache.get_rankings("payContract", "ECONOMIC_CRITICAL", 42)
    assert retrieved is not None
    assert len(retrieved) == 2
    assert retrieved[0]["scenario_id"] == "s1"


# ==============================================================================
# 16. Early Stop Condition
# ==============================================================================
def test_16_early_stop_condition(sample_schema):
    bridge = RiskDirectedExplorationBridge()
    # Uniform passing behavior allows early stop when coverage is met
    proof = bridge.run_risk_directed_proof(
        migration_id="mig_early_stop",
        contract_id="contract_test",
        schema=sample_schema,
        known_consumers=["consumer_a"],
        policy=ExplorationPolicy.STANDARD,
    )
    assert proof.early_stopped is True
    assert proof.scenarios_executed < proof.scenarios_ranked
    assert proof.result == ProofResult.PROVEN_COMPATIBLE_WITHIN_SCOPE


# ==============================================================================
# 17. Budget Exhaustion
# ==============================================================================
def test_17_budget_exhaustion():
    ctrl = RiskAdaptiveBudgetController(RiskAdaptiveBudget(max_scenarios=2))
    ctrl.start()
    ctrl.record_scenario_execution(1.0)
    ctrl.record_scenario_execution(1.0)

    assert ctrl.is_exhausted() is True
    with pytest.raises(RiskBudgetExhaustedError):
        ctrl.record_scenario_execution(1.0)


# ==============================================================================
# 18. Scenario Graph (Edges and clustering)
# ==============================================================================
def test_18_scenario_graph():
    graph = ScenarioGraph()
    s1 = BehavioralScenario.create("c1", "k1", {"amount": 10}, {}, coverage_target="amount_valid")
    s2 = BehavioralScenario.create("c1", "k1", {"amount": 0}, {}, coverage_target="boundary_amount_0")

    graph.add_node(s1)
    graph.add_node(s2)
    graph.add_edge(s1.scenario_id, s2.scenario_id, "same_contract_field")

    neighbors = graph.get_neighbors(s1.scenario_id)
    assert len(neighbors) == 1
    assert neighbors[0] == s2.scenario_id


# ==============================================================================
# 19. Uniform vs Risk Benchmark (Efficiency ratio)
# ==============================================================================
def test_19_uniform_vs_risk_benchmark(sample_schema):
    bridge = RiskDirectedExplorationBridge()
    proof = bridge.run_risk_directed_proof(
        migration_id="mig_bench_test",
        contract_id="contract_bench",
        schema=sample_schema,
        known_consumers=["c_bench"],
        policy=ExplorationPolicy.STANDARD,
    )
    # Verifies that risk-directed search skips unnecessary low-value scenarios
    assert proof.scenarios_skipped > 0
    assert proof.scenario_efficiency > 0.0


# ==============================================================================
# 20. Proof Integration (PROVEN_COMPATIBLE_WITHIN_SCOPE)
# ==============================================================================
def test_20_proof_integration(sample_schema):
    bridge = RiskDirectedExplorationBridge()
    proof = bridge.run_risk_directed_proof(
        migration_id="mig_proof_int",
        contract_id="contract_orders",
        schema=sample_schema,
        known_consumers=["orders_ui"],
        policy=ExplorationPolicy.STANDARD,
    )
    assert proof.result == ProofResult.PROVEN_COMPATIBLE_WITHIN_SCOPE
    assert proof.gate_decision == ExecutionGateDecision.GATE_CLEARED
    assert len(proof.proof_hash) > 0


# ==============================================================================
# 21. Rollback on Failure
# ==============================================================================
def test_21_rollback_on_failure(sample_schema):
    bridge = RiskDirectedExplorationBridge()

    def buggy_after(payload: dict) -> dict:
        return {"status_code": 500, "output": {"error": "CRITICAL_BUG"}}

    proof = bridge.run_risk_directed_proof(
        migration_id="mig_rollback_test",
        contract_id="contract_orders",
        schema=sample_schema,
        known_consumers=["orders_ui"],
        policy=ExplorationPolicy.STANDARD,
        after_handler=buggy_after,
    )
    assert proof.result == ProofResult.PROVEN_INCOMPATIBLE
    assert proof.gate_decision == ExecutionGateDecision.EXECUTION_BLOCKED
    assert len(proof.counterexamples) > 0


# ==============================================================================
# 22. Insufficient Evidence Preservation
# ==============================================================================
def test_22_insufficient_evidence_preservation(sample_schema):
    bridge = RiskDirectedExplorationBridge()
    proof = bridge.run_risk_directed_proof(
        migration_id="mig_unc_test",
        contract_id="contract_dynamic",
        schema=sample_schema,
        known_consumers=["dyn_consumer"],
        dynamic_consumer_uncertainties=["UNCERTAIN_DYNAMIC_PLUGIN_RUNNER"],
    )
    assert proof.result == ProofResult.INSUFFICIENT_EVIDENCE
    assert proof.gate_decision == ExecutionGateDecision.HUMAN_REVIEW_REQUIRED


# ==============================================================================
# 23. Insufficient Coverage Preservation
# ==============================================================================
def test_23_insufficient_coverage_preservation(sample_schema):
    validator = AdaptiveProofValidator()
    cov_low = BehavioralCoverage(
        coverage_id="cov_low",
        scope_id="scp_1",
        dimensions={},
        overall_percentage=0.60,
        threshold_policy=CoverageThresholdPolicy.STRICT,
        threshold_met=False,
    )
    res, gate, reasons = validator.evaluate_adaptive_proof_result(
        coverage=cov_low,
        counterexamples=[],
        invariants_preserved=True,
        policy=ExplorationPolicy.STRICT,
    )
    assert res == ProofResult.INSUFFICIENT_COVERAGE
    assert gate == ExecutionGateDecision.HUMAN_REVIEW_REQUIRED


# ==============================================================================
# 24. Critical Policy Enforcement
# ==============================================================================
def test_24_critical_policy_enforcement(sample_schema):
    bridge = RiskDirectedExplorationBridge()
    proof = bridge.run_risk_directed_proof(
        migration_id="mig_crit_test",
        contract_id="contract_critical",
        schema=sample_schema,
        known_consumers=["core_bank"],
        policy=ExplorationPolicy.CRITICAL,
    )
    assert proof.policy == ExplorationPolicy.CRITICAL
    assert proof.coverage.threshold_policy == CoverageThresholdPolicy.CRITICAL
