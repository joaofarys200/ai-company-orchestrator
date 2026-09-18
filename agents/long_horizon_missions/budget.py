"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
Resource Budget Governance & Multi-Dimensional Metering.
Strict Invariant: No unbounded autonomous execution when budget <= 0.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from backend.agents.long_horizon_missions.models import MissionBudget


class BudgetExhaustedError(Exception):
    """Raised when any bounded budget dimension is exhausted."""
    pass


class BudgetTracker:
    """
    Accounts for, enforces, and governs resource consumption across all 11 budget dimensions.
    """

    def __init__(self, budget: Optional[MissionBudget] = None):
        self.budget = budget or MissionBudget()
        self._consumption_log: List[Dict[str, Any]] = []

    def record_consumption(
        self,
        dimension: str,
        amount: float = 1.0,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Consumes resource and verifies against limit.
        Returns: (is_exhausted, exhausted_dimension_name)
        """
        attr_name = f"consumed_{dimension}"
        if not hasattr(self.budget, attr_name):
            raise AttributeError(f"Unknown budget dimension: {dimension}")

        current = getattr(self.budget, attr_name)
        new_val = current + amount
        setattr(self.budget, attr_name, new_val)

        self._consumption_log.append({
            "timestamp": time.time(),
            "dimension": dimension,
            "amount": amount,
            "new_total": new_val,
            "context": context or {},
        })

        exhausted, exhausted_dim = self.budget.is_exhausted()
        return exhausted, exhausted_dim

    def assert_available(self, dimension: str, required: float = 1.0) -> None:
        """Throws BudgetExhaustedError if the requested consumption would exceed limits."""
        limit_name = dimension
        consumed_name = f"consumed_{dimension}"
        if not hasattr(self.budget, limit_name) or not hasattr(self.budget, consumed_name):
            raise AttributeError(f"Unknown budget dimension: {dimension}")

        limit = getattr(self.budget, limit_name)
        consumed = getattr(self.budget, consumed_name)

        if consumed + required > limit:
            raise BudgetExhaustedError(
                f"BUDGET_EXHAUSTED: Consuming {required} of '{dimension}' would exceed limit "
                f"({consumed + required} > {limit}). Autonomous execution cannot proceed unbounded."
            )

    def get_summary(self) -> Dict[str, Any]:
        exhausted, exhausted_dim = self.budget.is_exhausted()
        return {
            "budget": self.budget.to_dict(),
            "is_exhausted": exhausted,
            "exhausted_dimension": exhausted_dim,
            "log_entries_count": len(self._consumption_log),
        }
