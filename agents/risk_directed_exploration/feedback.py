"""
JARVIS OS — Phase 52: Risk-Directed Behavioral Exploration & Adaptive Proof Search
Adaptive Feedback Controller: Negative evidence risk diminution & counterexample cluster amplification.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple

from agents.behavioral_proof_exploration.models import (
    BehavioralScenario,
    Counterexample,
    ExplorationStrategy,
    ScenarioExecutionResult,
    ShrunkCounterexample,
)
from agents.risk_directed_exploration.models import (
    BehavioralExplorationRisk,
    BehavioralUncertainty,
    NegativeEvidence,
    ScenarioGraph,
    ScenarioRanking,
)


class AdaptiveFeedbackController:
    """
    Manages feedback updates to Risk, Uncertainty, and Scenario Priorities:
    - Successful scenario -> records NegativeEvidence, slightly decreases risk and uncertainty.
    - Divergent scenario (Counterexample) -> amplifies related risk dimensions, generates derived mutations,
      and escalates priorities of neighboring nodes in the ScenarioGraph.
    """

    def __init__(self, scenario_graph: Optional[ScenarioGraph] = None) -> None:
        self.graph = scenario_graph or ScenarioGraph()
        self._negative_evidence: Dict[str, NegativeEvidence] = {}

    def process_success_observation(
        self,
        scenario: BehavioralScenario,
        risk: BehavioralExplorationRisk,
        uncertainty: BehavioralUncertainty,
    ) -> Tuple[BehavioralExplorationRisk, BehavioralUncertainty, NegativeEvidence]:
        """
        Incorporate negative evidence from a passing scenario.
        Reduces related risk and uncertainty dimensions without dropping them to zero.
        """
        ev = self._negative_evidence.get(scenario.scenario_id)
        if ev:
            ev.execution_count += 1
            ev.risk_reduction_factor = min(0.40, ev.risk_reduction_factor + 0.05)
        else:
            ev = NegativeEvidence(scenario_id=scenario.scenario_id)
            self._negative_evidence[scenario.scenario_id] = ev

        target = scenario.coverage_target.lower()

        # Diminish relevant uncertainty
        if "variant" in target:
            uncertainty.unknown_variant = max(0.05, uncertainty.unknown_variant - 0.15)
        elif "error" in target:
            uncertainty.unknown_error_path = max(0.05, uncertainty.unknown_error_path - 0.15)
        elif "branch" in target:
            uncertainty.unexplored_branch = max(0.05, uncertainty.unexplored_branch - 0.15)

        # Diminish relevant risk component
        if "economic" in target or "amount" in target or "currency" in target:
            risk.economic_risk = max(0.10, risk.economic_risk - 0.05)
        elif "auth" in target:
            risk.security_risk = max(0.10, risk.security_risk - 0.05)
        elif "retry" in target:
            risk.contract_risk = max(0.05, risk.contract_risk - 0.05)

        # General negative evidence: coverage gap narrows and contract confidence increases
        risk.coverage_gap = max(0.05, risk.coverage_gap - 0.03)
        risk.contract_risk = max(0.05, risk.contract_risk - 0.01)

        risk.compute_score()
        uncertainty.compute_score()
        return risk, uncertainty, ev

    def process_counterexample_observation(
        self,
        scenario: BehavioralScenario,
        counterexample: Counterexample,
        risk: BehavioralExplorationRisk,
        uncertainty: BehavioralUncertainty,
    ) -> Tuple[BehavioralExplorationRisk, BehavioralUncertainty, List[BehavioralScenario]]:
        """
        Process failure observation:
        1. Increase related risk dimensions
        2. Generate derived boundary mutations around the failing payload
        3. Escalate graph neighbor weights
        """
        target = scenario.coverage_target.lower()

        # Amplify risk
        if "amount" in target or "discount" in target or "currency" in target:
            risk.economic_risk = 1.0
        elif "auth" in target:
            risk.security_risk = 1.0
        risk.change_magnitude = min(1.0, risk.change_magnitude + 0.25)
        risk.compute_score()

        # Generate derived mutations to probe cluster
        derived_scenarios: List[BehavioralScenario] = []
        base_input = copy.deepcopy(scenario.input)

        # If numerical field divergence (e.g. discount_rate, amount)
        numeric_fields = [k for k, v in base_input.items() if isinstance(v, (int, float))]
        for num_f in numeric_fields[:2]:
            cur_val = base_input[num_f]
            probes = [0.0, cur_val * 2, -cur_val, 0.001, -0.001]
            for p_val in probes:
                mut_input = copy.deepcopy(base_input)
                mut_input[num_f] = p_val
                derived_scen = BehavioralScenario.create(
                    consumer_id=scenario.consumer_id,
                    contract_id=scenario.contract_id,
                    input_payload=mut_input,
                    expected_behavior={"status_code": 200},
                    mutation={"type": "derived_cluster_probe", "field": num_f, "probe_value": p_val},
                    seed=scenario.seed + len(derived_scenarios) + 1,
                    parent_scenario=scenario.scenario_id,
                    coverage_target=f"derived_probe_{num_f}_{p_val}",
                    strategy=ExplorationStrategy.BOUNDARY_EXPLORATION,
                )
                derived_scenarios.append(derived_scen)
                self.graph.add_node(derived_scen)
                self.graph.add_edge(scenario.scenario_id, derived_scen.scenario_id, "child_mutation", weight=2.0)

        return risk, uncertainty, derived_scenarios
