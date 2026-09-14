"""
JARVIS OS — Phase 52: Risk-Directed Behavioral Exploration & Adaptive Proof Search
High-Level Orchestrator Bridge: Connects Impact Analysis, Risk/Uncertainty Modeling,
Scenario Generation, Deterministic Ranking, Adaptive Exploration, and Proof Synthesis.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from agents.behavioral_contract_proof.models import (
    BehaviorBaseline,
    Counterexample,
    ExecutionGateDecision,
    ProofResult,
)
from agents.behavioral_proof_exploration.generator import ScenarioGenerator
from agents.behavioral_proof_exploration.models import (
    BehavioralCoverage,
    BehavioralScenario,
    compute_deterministic_id,
)
from agents.risk_directed_exploration.cache import DeterministicRankingCache
from agents.risk_directed_exploration.explorer import RiskDirectedExplorer
from agents.risk_directed_exploration.index import RiskExplorationIndex
from agents.risk_directed_exploration.memory import ExplorationMemoryBridge
from agents.risk_directed_exploration.metrics import RiskDirectedTelemetry
from agents.risk_directed_exploration.models import (
    AdaptiveProofResult,
    BehavioralExplorationRisk,
    BehavioralUncertainty,
    ExplorationPolicy,
    RiskAdaptiveBudget,
    ScenarioRanking,
)
from agents.risk_directed_exploration.policy import ExplorationPolicyEngine
from agents.risk_directed_exploration.ranking import ScenarioRanker
from agents.risk_directed_exploration.risk import RiskEvaluator
from agents.risk_directed_exploration.security import RiskSecuritySentinel
from agents.risk_directed_exploration.uncertainty import UncertaintyEvaluator
from agents.risk_directed_exploration.validator import AdaptiveProofValidator


class RiskDirectedExplorationBridge:
    """
    Central Orchestrator for Phase 52.
    Implements the risk-directed adaptive exploration workflow:
    IMPACT ANALYSIS -> BEHAVIOR MODEL -> RISK MODEL -> UNCERTAINTY MODEL ->
    SCENARIO GENERATION -> SCENARIO RANKING -> ADAPTIVE EXPLORATION LOOP ->
    NEGATIVE EVIDENCE / FAILURE FEEDBACK -> PROOF DECISION -> MISSION/FINISH GATES.
    """

    def __init__(
        self,
        telemetry: Optional[RiskDirectedTelemetry] = None,
        index: Optional[RiskExplorationIndex] = None,
    ) -> None:
        self.telemetry = telemetry or RiskDirectedTelemetry()
        self.index = index or RiskExplorationIndex()
        self.risk_evaluator = RiskEvaluator()
        self.uncertainty_evaluator = UncertaintyEvaluator()
        self.generator = ScenarioGenerator()
        self.ranker = ScenarioRanker()
        self.policy_engine = ExplorationPolicyEngine()
        self.explorer = RiskDirectedExplorer(ranker=self.ranker, policy_engine=self.policy_engine)
        self.memory_bridge = ExplorationMemoryBridge()
        self.ranking_cache = DeterministicRankingCache()
        self.validator = AdaptiveProofValidator()
        self.security_sentinel = RiskSecuritySentinel()

    def run_risk_directed_proof(
        self,
        migration_id: str,
        contract_id: str,
        schema: Dict[str, Any],
        known_consumers: List[str],
        contract_delta: Optional[Dict[str, Any]] = None,
        baseline: Optional[BehaviorBaseline] = None,
        historical_traces: Optional[List[Dict[str, Any]]] = None,
        policy: ExplorationPolicy = ExplorationPolicy.STANDARD,
        predictive_impact_level: str = "MEDIUM",
        is_economic: bool = False,
        is_security_critical: bool = False,
        polymorphic_variants: Optional[List[str]] = None,
        dynamic_consumer_uncertainties: Optional[List[str]] = None,
        seed: int = 42,
        before_handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        after_handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> AdaptiveProofResult:
        """
        Execute full risk-directed adaptive exploration and synthesize proof certificate.
        """
        t_start = time.perf_counter()
        uncertainties = dynamic_consumer_uncertainties or []
        delta = contract_delta or {}

        # 1. RISK MODEL EVALUATION
        initial_risk = self.risk_evaluator.evaluate_risk(
            contract_schema_delta=delta,
            consumers=known_consumers,
            is_economic=is_economic,
            is_security_critical=is_security_critical,
            polymorphic_variants=polymorphic_variants,
            dynamic_consumer_uncertainties=uncertainties,
            predictive_impact_level=predictive_impact_level,
        )
        # Security Sentinel inspection against risk spoofing / suppression
        self.security_sentinel.inspect_risk_assessment(
            risk=initial_risk,
            is_economic=is_economic,
            is_security_critical=is_security_critical,
            unresolved_consumers_count=len(uncertainties),
        )
        self.index.register_risk(contract_id, initial_risk)

        # 2. UNCERTAINTY MODEL EVALUATION
        initial_uncertainty = self.uncertainty_evaluator.evaluate_uncertainty(
            has_uncertain_consumer=len(uncertainties) > 0,
            insufficient_evidence=len(uncertainties) > 0,
            coverage_pct=0.0,
            unknown_variants_count=1 if polymorphic_variants else 0,
            missing_baseline=baseline is None,
        )
        self.index.register_uncertainty(contract_id, initial_uncertainty)

        # 3. SCENARIO CANDIDATES GENERATION (Phase 51)
        budget = self.policy_engine.get_initial_budget(policy, initial_risk.risk_score)
        scenarios = self.generator.generate_scenarios_for_contract(
            contract_id=contract_id,
            consumer_id=known_consumers[0] if known_consumers else "default_consumer",
            schema=schema,
            baseline=baseline.to_dict() if baseline else None,
            historical_traces=historical_traces,
            budget=budget,
            polymorphic_variants=polymorphic_variants,
        )

        # Populate Scenario Graph
        for s in scenarios:
            self.index.graph.add_node(s)

        # 4. DETERMINISTIC SCENARIO RANKING
        impact_weight = 1.5 if predictive_impact_level.upper() in ("HIGH", "CRITICAL") else 1.0
        initial_rankings = self.ranker.rank_scenarios(
            scenarios=scenarios,
            risk=initial_risk,
            uncertainty=initial_uncertainty,
            policy=policy,
            impact_weight=impact_weight,
        )
        # Security inspection on rankings
        self.security_sentinel.inspect_rankings(initial_rankings, is_economic=is_economic)
        self.index.register_rankings(contract_id, initial_rankings)
        self.ranking_cache.store_rankings(contract_id, policy.value, seed, initial_rankings)

        self.telemetry.emit_event(
            "scenarios_ranked",
            migration_id=migration_id,
            contract_id=contract_id,
            policy=policy.value,
            risk_score=initial_risk.risk_score,
            uncertainty_score=initial_uncertainty.uncertainty_score,
            details={"ranked_count": len(initial_rankings), "top_scenario": initial_rankings[0].scenario_id if initial_rankings else None},
        )

        # 5. ADAPTIVE SEARCH LOOP (SELECT -> EXECUTE -> OBSERVE -> UPDATE -> RE-RANK)
        scope_id = compute_deterministic_id({
            "migration_id": migration_id,
            "contract_id": contract_id,
            "policy": policy.value,
            "seed": seed,
        }, prefix="scp_adapt_")

        search_outcome = self.explorer.run_adaptive_search(
            scope_id=scope_id,
            initial_candidates=scenarios,
            initial_risk=initial_risk,
            initial_uncertainty=initial_uncertainty,
            schema=schema,
            known_consumers=known_consumers,
            policy=policy,
            budget=budget,
            before_handler=before_handler,
            after_handler=after_handler,
            is_economic=is_economic,
            impact_weight=impact_weight,
        )

        # 6. VERIFY MANDATORY SAFETY SCENARIOS (Economic / Security)
        mand_ok, missing_targets = self.policy_engine.verify_mandatory_scenarios(
            policy=policy,
            executed_scenarios=search_outcome["executed_scenarios"],
        )

        # 7. PROOF RESULT & GATES SYNTHESIS
        proof_result, gate_decision, decision_reasons = self.validator.evaluate_adaptive_proof_result(
            coverage=search_outcome["coverage"],
            counterexamples=search_outcome["counterexamples"],
            invariants_preserved=len(search_outcome["counterexamples"]) == 0,
            policy=policy,
            consumer_uncertainties=uncertainties,
            mandatory_safety_passed=mand_ok,
        )

        # 8. EFFICIENCY METRICS
        efficiency_stats = self.telemetry.compute_efficiency(
            risk_initial=initial_risk.risk_score,
            risk_final=search_outcome["final_risk"].risk_score,
            cost_spent=search_outcome["budget"].cost_spent,
            scenarios_total=len(scenarios),
            scenarios_executed=len(search_outcome["executed_scenarios"]),
        )

        proof_id = compute_deterministic_id({
            "migration_id": migration_id,
            "contract_id": contract_id,
            "result": proof_result.value,
            "gate": gate_decision.value,
            "seed": seed,
        }, prefix="prf_risk_")

        adaptive_proof = AdaptiveProofResult(
            proof_id=proof_id,
            migration_id=migration_id,
            contract_id=contract_id,
            policy=policy,
            result=proof_result,
            gate_decision=gate_decision,
            initial_risk=initial_risk,
            final_risk=search_outcome["final_risk"],
            initial_uncertainty=initial_uncertainty,
            final_uncertainty=search_outcome["final_uncertainty"],
            coverage=search_outcome["coverage"],
            budget=search_outcome["budget"],
            counterexamples=search_outcome["counterexamples"],
            shrunk_counterexamples=search_outcome["shrunk_counterexamples"],
            scenarios_ranked=len(scenarios),
            scenarios_executed=len(search_outcome["executed_scenarios"]),
            scenarios_skipped=search_outcome["budget"].scenarios_skipped,
            early_stopped=search_outcome["early_stopped"],
            early_stop_reason=search_outcome["early_stop_reason"],
            scenario_efficiency=efficiency_stats["scenario_efficiency"],
            provenance={
                "reasons": decision_reasons,
                "missing_mandatory": missing_targets,
                "efficiency": efficiency_stats,
                "duration_ms": round((time.perf_counter() - t_start) * 1000.0, 2),
            },
        )
        adaptive_proof.proof_hash = adaptive_proof.compute_hash()
        self.index.register_proof(adaptive_proof)

        # Record Experience Memory
        for s in search_outcome["executed_scenarios"]:
            self.memory_bridge.record_exploration_experience(
                contract_id=contract_id,
                scenario=s,
                risk_before=initial_risk.risk_score,
                risk_after=search_outcome["final_risk"].risk_score,
                coverage_delta=0.05,
                had_divergence=len(search_outcome["counterexamples"]) > 0,
                counterexample=search_outcome["counterexamples"][0] if search_outcome["counterexamples"] else None,
                policy=policy.value,
                decision=gate_decision.value,
            )

        self.telemetry.emit_event(
            "proof_synthesized",
            migration_id=migration_id,
            contract_id=contract_id,
            policy=policy.value,
            decision=gate_decision.value,
            details={"result": proof_result.value, "efficiency": efficiency_stats},
        )

        return adaptive_proof
