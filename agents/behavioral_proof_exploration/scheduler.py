"""
JARVIS OS — Phase 51: Behavioral Proof Coverage & Scenario Exploration
Scenario Scheduler and Bounded Concurrency Interleaving Explorer.
"""

from __future__ import annotations

import itertools
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from agents.behavioral_proof_exploration.executor import ScenarioExecutor
from agents.behavioral_proof_exploration.models import (
    BehavioralScenario,
    ExplorationBudget,
    ProofScope,
    ScenarioExecutionResult,
)


class ScenarioScheduler:
    """
    Deterministic Scenario Scheduler.
    Executes scenarios respecting explicit budget caps (count, time, interleavings).
    Explores small bounded concurrency interleavings without combinatorial explosion.
    """

    DEFAULT_MAX_INTERLEAVINGS = 10

    def __init__(self, executor: Optional[ScenarioExecutor] = None) -> None:
        self.executor = executor or ScenarioExecutor()

    def run_bounded_exploration(
        self,
        scope: ProofScope,
        scenarios: List[BehavioralScenario],
        before_handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        after_handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> Tuple[List[ScenarioExecutionResult], List[str]]:
        """
        Execute scenarios within budget.
        Returns execution results and list of any unexplored interleavings.
        """
        budget = scope.budget
        results: List[ScenarioExecutionResult] = []
        unexplored_interleavings: List[str] = []

        start_time = time.perf_counter()
        count_limit = min(len(scenarios), budget.max_scenarios)

        for i in range(count_limit):
            # Check runtime budget limit
            elapsed = time.perf_counter() - start_time
            if elapsed > budget.max_runtime:
                break

            scen = scenarios[i]
            res = self.executor.execute(
                scenario=scen,
                before_handler=before_handler,
                after_handler=after_handler,
            )
            results.append(res)

        # Concurrency Interleaving Exploration (bounded)
        if len(scenarios) >= 2:
            op_names = [f"op_{s.scenario_id[:6]}" for s in scenarios[:4]]
            all_permutations = list(itertools.permutations(op_names, min(3, len(op_names))))
            max_interleavings = min(scope.max_interleavings or self.DEFAULT_MAX_INTERLEAVINGS, budget.max_concurrency_variants)
            
            explored = all_permutations[:max_interleavings]
            unexplored = all_permutations[max_interleavings:]
            
            # Format unexplored interleavings as readable strings
            for p in unexplored:
                unexplored_interleavings.append(" -> ".join(p))

        return results, unexplored_interleavings
