"""
JARVIS OS — Phase 51: Behavioral Proof Coverage & Scenario Exploration
Exploration Search Strategies Orchestrator.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from agents.behavioral_proof_exploration.generator import ScenarioGenerator
from agents.behavioral_proof_exploration.models import (
    BehavioralScenario,
    ExplorationBudget,
    ExplorationStrategy,
    ProofScope,
)


class ExplorationSearchStrategy:
    """
    Search Strategy Orchestrator.
    Dispatches generation across BOUNDARY_EXPLORATION, SCHEMA_MUTATION, TRACE_REPLAY,
    COUNTEREXAMPLE_REPLAY, POLYMORPHIC_EXPLORATION, ERROR_PATH_EXPLORATION, RETRY_EXPLORATION.
    Extensible for property-based generation and state exploration without unsafe fuzzing.
    """

    def __init__(self, generator: Optional[ScenarioGenerator] = None) -> None:
        self.generator = generator or ScenarioGenerator()

    def plan_exploration(
        self,
        scope: ProofScope,
        schema: Dict[str, Any],
        consumer_id: str,
        baseline: Optional[Dict[str, Any]] = None,
        historical_traces: Optional[List[Dict[str, Any]]] = None,
        previous_counterexamples: Optional[List[Dict[str, Any]]] = None,
        known_variants: Optional[List[str]] = None,
    ) -> List[BehavioralScenario]:
        """
        Produce a tailored list of scenarios executing requested strategies within budget.
        """
        all_scenarios = self.generator.generate_scenarios_for_contract(
            contract_id=scope.contract_id,
            consumer_id=consumer_id,
            schema=schema,
            baseline=baseline,
            historical_traces=historical_traces,
            budget=scope.budget,
            polymorphic_variants=known_variants,
        )

        # Filter by scope strategies if specified
        if scope.strategies:
            strategy_set = set(scope.strategies)
            filtered = [s for s in all_scenarios if s.strategy in strategy_set]
            if filtered:
                all_scenarios = filtered

        # Counterexample Replay strategy
        if previous_counterexamples and (
            not scope.strategies or ExplorationStrategy.COUNTEREXAMPLE_REPLAY in scope.strategies
        ):
            for cx in previous_counterexamples[:5]:
                all_scenarios.append(
                    BehavioralScenario.create(
                        consumer_id=consumer_id,
                        contract_id=scope.contract_id,
                        input_payload=cx.get("input_payload", {}),
                        expected_behavior=cx.get("expected_behavior", {"status_code": 200}),
                        seed=scope.seed + len(all_scenarios),
                        coverage_target="previous_counterexample_replay",
                        strategy=ExplorationStrategy.COUNTEREXAMPLE_REPLAY,
                    )
                )

        # Enforce max_scenarios
        return all_scenarios[:scope.budget.max_scenarios]
