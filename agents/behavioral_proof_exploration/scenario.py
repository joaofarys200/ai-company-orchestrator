"""
JARVIS OS — Phase 51: Behavioral Proof Coverage & Scenario Exploration
Scenario Management & Deterministic Lineage Tracking.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Set

from agents.behavioral_proof_exploration.models import (
    BehavioralScenario,
    ExplorationStrategy,
    compute_deterministic_id,
)


class ScenarioIntegrityError(Exception):
    """Raised when a scenario ID does not match its canonical payload."""
    pass


class ScenarioManager:
    """
    Registry and lifecycle controller for BehavioralScenarios.
    Maintains deterministic hashes and parent-child exploration lineage.
    """

    def __init__(self) -> None:
        self._scenarios: Dict[str, BehavioralScenario] = {}
        self._by_contract: Dict[str, List[str]] = {}
        self._by_consumer: Dict[str, List[str]] = {}
        self._by_strategy: Dict[str, List[str]] = {}
        self._lineage_children: Dict[str, List[str]] = {}

    def register_scenario(self, scenario: BehavioralScenario) -> BehavioralScenario:
        """Register a scenario with integrity validation."""
        # Validate deterministic scenario ID
        recalculated = BehavioralScenario.create(
            consumer_id=scenario.consumer_id,
            contract_id=scenario.contract_id,
            input_payload=scenario.input,
            expected_behavior=scenario.expected_behavior,
            mutation=scenario.mutation,
            preconditions=scenario.preconditions,
            environment=scenario.environment,
            seed=scenario.seed,
            parent_scenario=scenario.parent_scenario,
            coverage_target=scenario.coverage_target,
            strategy=scenario.strategy,
        )
        if recalculated.scenario_id != scenario.scenario_id:
            raise ScenarioIntegrityError(
                f"Scenario ID mismatch! Given {scenario.scenario_id}, expected {recalculated.scenario_id}"
            )

        self._scenarios[scenario.scenario_id] = scenario
        self._by_contract.setdefault(scenario.contract_id, []).append(scenario.scenario_id)
        self._by_consumer.setdefault(scenario.consumer_id, []).append(scenario.scenario_id)
        self._by_strategy.setdefault(scenario.strategy.value, []).append(scenario.scenario_id)

        if scenario.parent_scenario:
            self._lineage_children.setdefault(scenario.parent_scenario, []).append(scenario.scenario_id)

        return scenario

    def get_scenario(self, scenario_id: str) -> Optional[BehavioralScenario]:
        """Retrieve a registered scenario by ID."""
        return self._scenarios.get(scenario_id)

    def get_children(self, parent_id: str) -> List[BehavioralScenario]:
        """Retrieve child scenarios derived from a parent scenario."""
        child_ids = self._lineage_children.get(parent_id, [])
        return [self._scenarios[cid] for cid in child_ids if cid in self._scenarios]

    def list_scenarios(
        self,
        contract_id: Optional[str] = None,
        consumer_id: Optional[str] = None,
        strategy: Optional[ExplorationStrategy] = None,
    ) -> List[BehavioralScenario]:
        """List scenarios matching filters."""
        candidates = list(self._scenarios.values())
        if contract_id:
            candidates = [s for s in candidates if s.contract_id == contract_id]
        if consumer_id:
            candidates = [s for s in candidates if s.consumer_id == consumer_id]
        if strategy:
            candidates = [s for s in candidates if s.strategy == strategy]
        return candidates

    def count(self) -> int:
        """Total number of registered scenarios."""
        return len(self._scenarios)

    def clear(self) -> None:
        """Clear the scenario registry."""
        self._scenarios.clear()
        self._by_contract.clear()
        self._by_consumer.clear()
        self._by_strategy.clear()
        self._lineage_children.clear()
