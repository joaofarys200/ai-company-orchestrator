"""
JARVIS OS — Phase 52: Risk-Directed Behavioral Exploration & Adaptive Proof Search
Adaptive Scenario Scheduler: Priority-queue based scheduling with dynamic re-ranking.
"""

from __future__ import annotations

import heapq
from typing import Any, Dict, List, Optional, Set

from agents.behavioral_proof_exploration.models import BehavioralScenario
from agents.risk_directed_exploration.models import (
    BehavioralExplorationRisk,
    BehavioralUncertainty,
    ExplorationPolicy,
    ScenarioRanking,
)
from agents.risk_directed_exploration.ranking import ScenarioRanker


class AdaptiveScenarioScheduler:
    """
    Adaptive Priority Scheduler.
    Selects top-ranked scenarios, dynamically re-ranks candidate pool after observations,
    and supports dynamic injection of high-value mutations.
    """

    def __init__(self, ranker: Optional[ScenarioRanker] = None) -> None:
        self.ranker = ranker or ScenarioRanker()
        self._pool: Dict[str, BehavioralScenario] = {}
        self._executed_ids: Set[str] = set()

    def set_candidate_pool(self, scenarios: List[BehavioralScenario]) -> None:
        """Initialize candidate pool."""
        self._pool = {s.scenario_id: s for s in scenarios}
        self._executed_ids.clear()

    def add_candidates(self, scenarios: List[BehavioralScenario]) -> None:
        """Add new scenarios (e.g. from counterexample feedback) into pool."""
        for s in scenarios:
            if s.scenario_id not in self._executed_ids:
                self._pool[s.scenario_id] = s

    def select_next(
        self,
        risk: BehavioralExplorationRisk,
        uncertainty: BehavioralUncertainty,
        policy: ExplorationPolicy = ExplorationPolicy.STANDARD,
        impact_weight: float = 1.0,
    ) -> Optional[BehavioralScenario]:
        """
        Re-rank remaining candidates and pick the highest priority scenario.
        """
        remaining = [s for sid, s in self._pool.items() if sid not in self._executed_ids]
        if not remaining:
            return None

        rankings = self.ranker.rank_scenarios(
            scenarios=remaining,
            risk=risk,
            uncertainty=uncertainty,
            policy=policy,
            impact_weight=impact_weight,
        )
        if not rankings:
            return None

        top_id = rankings[0].scenario_id
        self._executed_ids.add(top_id)
        return self._pool[top_id]

    def get_remaining_count(self) -> int:
        return len(self._pool) - len(self._executed_ids)

    def get_ranked_list(
        self,
        risk: BehavioralExplorationRisk,
        uncertainty: BehavioralUncertainty,
        policy: ExplorationPolicy = ExplorationPolicy.STANDARD,
        impact_weight: float = 1.0,
    ) -> List[ScenarioRanking]:
        """Return full ranking of all pool scenarios."""
        return self.ranker.rank_scenarios(
            scenarios=list(self._pool.values()),
            risk=risk,
            uncertainty=uncertainty,
            policy=policy,
            impact_weight=impact_weight,
        )
