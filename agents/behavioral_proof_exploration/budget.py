"""
JARVIS OS — Phase 51: Behavioral Proof Coverage & Scenario Exploration
Exploration Budget Controller and Boundary Enforcement.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from agents.behavioral_proof_exploration.models import ExplorationBudget


class BudgetExceededError(Exception):
    """Raised when an exploration execution exceeds its allowed budget limits."""
    pass


class ExplorationBudgetController:
    """
    Monitors and enforces resource bounds during scenario exploration.
    Ensures that the proof certificate transparently records its constraints.
    """

    def __init__(self, budget: Optional[ExplorationBudget] = None) -> None:
        self.budget = budget or ExplorationBudget()
        self._start_time: Optional[float] = None
        self._scenario_count = 0
        self._trace_size_total = 0

    def start(self) -> None:
        """Begin budget monitoring."""
        self._start_time = time.perf_counter()
        self._scenario_count = 0
        self._trace_size_total = 0

    def record_scenario(self, trace_bytes: int = 0) -> None:
        """Record execution of a scenario and verify constraints."""
        self._scenario_count += 1
        self._trace_size_total += trace_bytes

        if self._scenario_count > self.budget.max_scenarios:
            raise BudgetExceededError(
                f"Scenario count limit exceeded: {self._scenario_count} > {self.budget.max_scenarios}"
            )

        if self._start_time:
            elapsed = time.perf_counter() - self._start_time
            if elapsed > self.budget.max_runtime:
                raise BudgetExceededError(
                    f"Runtime budget exceeded: {elapsed:.2f}s > {self.budget.max_runtime:.2f}s"
                )

    def is_exhausted(self) -> bool:
        """Check if any budget dimension is exhausted."""
        if self._scenario_count >= self.budget.max_scenarios:
            return True
        if self._start_time:
            elapsed = time.perf_counter() - self._start_time
            if elapsed >= self.budget.max_runtime:
                return True
        return False

    def get_summary(self) -> Dict[str, Any]:
        """Return usage summary versus budget."""
        elapsed = (time.perf_counter() - self._start_time) if self._start_time else 0.0
        return {
            "budget": self.budget.to_dict(),
            "scenarios_executed": self._scenario_count,
            "runtime_seconds": round(elapsed, 4),
            "trace_size_total": self._trace_size_total,
            "exhausted": self.is_exhausted(),
        }
