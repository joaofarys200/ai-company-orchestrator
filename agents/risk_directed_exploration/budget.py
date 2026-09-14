"""
JARVIS OS — Phase 52: Risk-Directed Behavioral Exploration & Adaptive Proof Search
Risk-Adaptive Budget Controller: Dynamically modulates exploration caps according to risk profile.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from agents.risk_directed_exploration.models import RiskAdaptiveBudget


class RiskBudgetExhaustedError(Exception):
    """Raised when an exploration execution exceeds its allowed risk-adjusted budget."""
    pass


class RiskAdaptiveBudgetController:
    """
    Enforces risk-adaptive budgets:
    Higher risk allocations allow deeper exploration, while low-risk changes conserve budget.
    Hard limits (max_cost, max_runtime, max_scenarios) are strictly maintained.
    """

    def __init__(self, budget: Optional[RiskAdaptiveBudget] = None) -> None:
        self.budget = budget or RiskAdaptiveBudget()
        self._start_time: Optional[float] = None

    def start(self) -> None:
        self._start_time = time.perf_counter()
        self.budget.cost_spent = 0.0
        self.budget.runtime_spent = 0.0
        self.budget.scenarios_executed = 0
        self.budget.scenarios_skipped = 0

    def record_scenario_execution(self, scenario_cost: float = 1.0) -> None:
        """Record scenario execution cost and verify constraints."""
        self.budget.scenarios_executed += 1
        self.budget.cost_spent += scenario_cost

        if self._start_time:
            self.budget.runtime_spent = time.perf_counter() - self._start_time

        if self.budget.scenarios_executed > self.budget.max_scenarios:
            raise RiskBudgetExhaustedError(
                f"Max scenarios budget reached: {self.budget.scenarios_executed} > {self.budget.max_scenarios}"
            )

        if self.budget.cost_spent > self.budget.max_cost:
            raise RiskBudgetExhaustedError(
                f"Max cost budget reached: {self.budget.cost_spent:.2f} > {self.budget.max_cost:.2f}"
            )

        if self.budget.runtime_spent > self.budget.max_runtime:
            raise RiskBudgetExhaustedError(
                f"Max runtime budget reached: {self.budget.runtime_spent:.2f}s > {self.budget.max_runtime:.2f}s"
            )

    def record_scenario_skipped(self) -> None:
        self.budget.scenarios_skipped += 1

    def is_exhausted(self) -> bool:
        """Check if any budget dimension is exhausted."""
        if self.budget.scenarios_executed >= self.budget.max_scenarios:
            return True
        if self.budget.cost_spent >= self.budget.max_cost:
            return True
        if self._start_time:
            elapsed = time.perf_counter() - self._start_time
            if elapsed >= self.budget.max_runtime:
                return True
        return False
