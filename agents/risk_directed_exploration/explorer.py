"""
JARVIS OS — Phase 52: Risk-Directed Behavioral Exploration & Adaptive Proof Search
Risk-Directed Explorer: Drives the adaptive SELECT -> EXECUTE -> OBSERVE -> UPDATE -> RE-RANK loop.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from agents.behavioral_contract_proof.models import (
    BehavioralInvariantType,
    Counterexample,
    ExecutionGateDecision,
    ProofResult,
)
from agents.behavioral_proof_exploration.counterexample import (
    ExplorationCounterexampleManager,
)
from agents.behavioral_proof_exploration.executor import ScenarioExecutor
from agents.behavioral_proof_exploration.models import (
    BehavioralCoverage,
    BehavioralScenario,
    CoverageThresholdPolicy,
    ScenarioExecutionResult,
    ShrunkCounterexample,
)
from agents.behavioral_proof_exploration.shrinker import CounterexampleShrinker
from agents.risk_directed_exploration.budget import RiskAdaptiveBudgetController
from agents.risk_directed_exploration.coverage import AdaptiveCoverageTracker
from agents.risk_directed_exploration.feedback import AdaptiveFeedbackController
from agents.risk_directed_exploration.memory import ExplorationMemoryBridge
from agents.risk_directed_exploration.models import (
    BehavioralExplorationRisk,
    BehavioralUncertainty,
    ExplorationPolicy,
    RiskAdaptiveBudget,
    ScenarioRanking,
)
from agents.risk_directed_exploration.policy import ExplorationPolicyEngine
from agents.risk_directed_exploration.ranking import ScenarioRanker
from agents.risk_directed_exploration.scheduler import AdaptiveScenarioScheduler
from agents.risk_directed_exploration.security import RiskSecuritySentinel


class RiskDirectedExplorer:
    """
    Executes adaptive risk-directed scenario exploration:
    1. Selects highest-priority scenario from scheduler;
    2. Executes scenario in sandbox;
    3. Observes execution trace and detects divergence or invariant violations;
    4. Updates incremental coverage;
    5. Updates risk and uncertainty scores (negative evidence or failure feedback);
    6. Dynamically re-ranks remaining scenarios;
    7. Evaluates early-stop conditions.
    """

    def __init__(
        self,
        executor: Optional[ScenarioExecutor] = None,
        ranker: Optional[ScenarioRanker] = None,
        policy_engine: Optional[ExplorationPolicyEngine] = None,
        feedback_controller: Optional[AdaptiveFeedbackController] = None,
        coverage_tracker: Optional[AdaptiveCoverageTracker] = None,
        security_sentinel: Optional[RiskSecuritySentinel] = None,
    ) -> None:
        self.executor = executor or ScenarioExecutor()
        self.ranker = ranker or ScenarioRanker()
        self.policy_engine = policy_engine or ExplorationPolicyEngine()
        self.feedback = feedback_controller or AdaptiveFeedbackController()
        self.coverage_tracker = coverage_tracker or AdaptiveCoverageTracker()
        self.security = security_sentinel or RiskSecuritySentinel()
        self.shrinker = CounterexampleShrinker()
        self.cx_manager = ExplorationCounterexampleManager()

    def run_adaptive_search(
        self,
        scope_id: str,
        initial_candidates: List[BehavioralScenario],
        initial_risk: BehavioralExplorationRisk,
        initial_uncertainty: BehavioralUncertainty,
        schema: Dict[str, Any],
        known_consumers: List[str],
        policy: ExplorationPolicy = ExplorationPolicy.STANDARD,
        budget: Optional[RiskAdaptiveBudget] = None,
        before_handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        after_handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        is_economic: bool = False,
        impact_weight: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Run the full adaptive exploration loop until proof condition or budget exhaustion.
        """
        budget_ctrl = RiskAdaptiveBudgetController(budget)
        budget_ctrl.start()

        scheduler = AdaptiveScenarioScheduler(self.ranker)
        scheduler.set_candidate_pool(initial_candidates)

        current_risk = initial_risk
        current_uncertainty = initial_uncertainty
        cov_policy = self.policy_engine.get_coverage_threshold_policy(policy)

        executed_scenarios: List[BehavioralScenario] = []
        execution_results: List[ScenarioExecutionResult] = []
        counterexamples: List[Counterexample] = []
        shrunk_counterexamples: List[ShrunkCounterexample] = []

        early_stopped = False
        early_stop_reason: Optional[str] = None

        while True:
            # Check budget exhaustion
            if budget_ctrl.is_exhausted():
                break

            # 1. SELECT next highest-priority scenario
            next_scen = scheduler.select_next(
                risk=current_risk,
                uncertainty=current_uncertainty,
                policy=policy,
                impact_weight=impact_weight,
            )
            if not next_scen:
                break

            # Security inspection
            self.security.inspect_scenario(next_scen)

            # 2. EXECUTE scenario
            res = self.executor.execute(
                scenario=next_scen,
                before_handler=before_handler,
                after_handler=after_handler,
            )
            executed_scenarios.append(next_scen)
            execution_results.append(res)
            budget_ctrl.record_scenario_execution(scenario_cost=1.0)

            # 3. UPDATE COVERAGE incrementally
            current_cov = self.coverage_tracker.update_with_execution(
                scope_id=scope_id,
                scenario=next_scen,
                result=res,
                schema=schema,
                known_consumers=known_consumers,
                policy=cov_policy,
                is_economic=is_economic,
            )

            # 4. OBSERVE & UPDATE RISK / UNCERTAINTY
            if res.is_divergent or res.invariants_violated:
                diff_msg = res.divergence_reason or "Behavioral divergence detected"
                cx = self.cx_manager.create_counterexample(
                    scenario=next_scen,
                    before_trace=res.before_trace,
                    after_trace=res.after_trace,
                    difference=diff_msg,
                    scope_id=scope_id,
                )
                counterexamples.append(cx)

                # Shrink counterexample
                def make_checker(target_s: BehavioralScenario):
                    def checker(payload: Dict[str, Any]) -> bool:
                        t_scen = BehavioralScenario.create(
                            consumer_id=target_s.consumer_id,
                            contract_id=target_s.contract_id,
                            input_payload=payload,
                            expected_behavior=target_s.expected_behavior,
                            seed=target_s.seed,
                            strategy=target_s.strategy,
                        )
                        t_res = self.executor.execute(
                            t_scen,
                            before_handler=before_handler,
                            after_handler=after_handler,
                        )
                        return t_res.is_divergent or len(t_res.invariants_violated) > 0
                    return checker

                shrunk = self.shrinker.shrink(
                    scenario=next_scen,
                    divergence_checker=make_checker(next_scen),
                    proof_scope_id=scope_id,
                    difference=diff_msg,
                    trace_id=res.after_trace.trace_id if res.after_trace else "tr_cx",
                )
                shrunk_counterexamples.append(shrunk)

                # Failure feedback: increase risk, generate derived probe scenarios
                current_risk, current_uncertainty, derived_scens = self.feedback.process_counterexample_observation(
                    scenario=next_scen,
                    counterexample=cx,
                    risk=current_risk,
                    uncertainty=current_uncertainty,
                )
                scheduler.add_candidates(derived_scens)

                # Early Stop on failure if policy mandates stop-on-counterexample
                early_stopped = True
                early_stop_reason = f"Counterexample detected in scenario {next_scen.scenario_id}: {diff_msg}"
                break

            else:
                # Negative Evidence feedback: reduce risk & uncertainty
                current_risk, current_uncertainty, _ = self.feedback.process_success_observation(
                    scenario=next_scen,
                    risk=current_risk,
                    uncertainty=current_uncertainty,
                )

            # 5. EARLY STOP on success if criteria satisfied
            if current_cov and current_cov.threshold_met:
                # In economic policy, must also verify mandatory economic scenarios
                mand_ok, missing = self.policy_engine.verify_mandatory_scenarios(policy, executed_scenarios)
                if mand_ok and len(counterexamples) == 0:
                    early_stopped = True
                    early_stop_reason = f"Proof conditions achieved: {current_cov.overall_percentage*100:.1f}% coverage met under {policy.value} policy"
                    break

        # Tally skipped scenarios
        budget_ctrl.budget.scenarios_skipped = scheduler.get_remaining_count()

        return {
            "executed_scenarios": executed_scenarios,
            "execution_results": execution_results,
            "counterexamples": counterexamples,
            "shrunk_counterexamples": shrunk_counterexamples,
            "final_risk": current_risk,
            "final_uncertainty": current_uncertainty,
            "coverage": self.coverage_tracker.get_current_coverage(),
            "budget": budget_ctrl.budget,
            "early_stopped": early_stopped,
            "early_stop_reason": early_stop_reason,
        }
