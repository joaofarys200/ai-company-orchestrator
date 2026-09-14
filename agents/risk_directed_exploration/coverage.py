"""
JARVIS OS — Phase 52: Risk-Directed Behavioral Exploration & Adaptive Proof Search
Adaptive Incremental Coverage Tracker integrating Phase 51 BehavioralCoverageEngine.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents.behavioral_proof_exploration.coverage import BehavioralCoverageEngine
from agents.behavioral_proof_exploration.models import (
    BehavioralCoverage,
    BehavioralScenario,
    CoverageThresholdPolicy,
    ScenarioExecutionResult,
)


class AdaptiveCoverageTracker:
    """
    Incremental coverage tracker.
    Updates multi-dimensional coverage dynamically after each scenario execution,
    feeding remaining gaps back into the ScenarioRanker.
    """

    def __init__(self, coverage_engine: Optional[BehavioralCoverageEngine] = None) -> None:
        self.engine = coverage_engine or BehavioralCoverageEngine()
        self._executed_scenarios: List[BehavioralScenario] = []
        self._execution_results: List[ScenarioExecutionResult] = []
        self._current_coverage: Optional[BehavioralCoverage] = None

    def update_with_execution(
        self,
        scope_id: str,
        scenario: BehavioralScenario,
        result: ScenarioExecutionResult,
        schema: Dict[str, Any],
        known_consumers: List[str],
        policy: CoverageThresholdPolicy = CoverageThresholdPolicy.STANDARD,
        is_economic: bool = False,
    ) -> BehavioralCoverage:
        """
        Record scenario execution and recompute incremental coverage report.
        """
        self._executed_scenarios.append(scenario)
        self._execution_results.append(result)

        self._current_coverage = self.engine.evaluate_coverage(
            scope_id=scope_id,
            scenarios=self._executed_scenarios,
            execution_results=self._execution_results,
            schema=schema,
            known_consumers=known_consumers,
            policy=policy,
            is_economic_operation=is_economic,
        )
        return self._current_coverage

    def get_current_coverage(self) -> Optional[BehavioralCoverage]:
        return self._current_coverage

    def get_executed_scenarios(self) -> List[BehavioralScenario]:
        return list(self._executed_scenarios)
