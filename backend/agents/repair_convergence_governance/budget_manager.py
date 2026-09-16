"""
JARVIS OS — Phase 56: Termination Budget Manager
Enforces bounded execution bounds and adapts budget limits conditioned on risk.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from agents.repair_convergence_governance.models import (
    AdaptiveBudgetConfig,
    TerminationBudget,
)


class TerminationBudgetManager:
    """Enforces computational boundaries and dynamically scales limits conditioned on risk."""

    def __init__(
        self,
        base_budget: Optional[TerminationBudget] = None,
        config: Optional[AdaptiveBudgetConfig] = None,
    ):
        self.budget = base_budget or TerminationBudget()
        self.config = config or AdaptiveBudgetConfig()
        self.initial_max_repairs = self.budget.max_repairs
        self.initial_max_runtime = self.budget.max_runtime

    def consume_step(
        self,
        repairs: int = 1,
        cycles: int = 0,
        runtime_sec: float = 0.0,
        rollbacks: int = 0,
        revealed: int = 0,
        risk: float = 0.0,
        depth: int = 0,
    ) -> Tuple[bool, List[str]]:
        """Consumes budget across operational dimensions and checks for exhaustion."""
        is_exhausted = self.budget.consume(
            repairs=repairs,
            cycles=cycles,
            runtime_sec=runtime_sec,
            rollbacks=rollbacks,
            revealed=revealed,
            risk=risk,
            depth=depth,
        )
        return is_exhausted, list(self.budget.exhausted_reasons)

    def adapt_budget_to_risk(self, current_risk: float, risk_trend: float = 0.0) -> None:
        """Dynamically adjusts repair limits: increases slightly if risk is low, strictly tightens if risk spikes.
        
        Sovereign rule: Never exceeds security_max_repairs_cap.
        """
        if current_risk >= 0.70 or risk_trend > 0.10:
            # High or worsening risk: reduce allowed remaining repairs to prevent unbounded damage
            reduction = int(self.initial_max_repairs * 0.3)
            self.budget.max_repairs = max(self.budget.consumed_repairs + 2, self.initial_max_repairs - reduction)
        elif current_risk < 0.25 and risk_trend <= 0.0:
            # Low, stable risk: allow controlled adaptive scaling up to Sentinel cap
            scaled = int(self.initial_max_repairs * (1.0 + self.config.risk_scale_factor))
            self.budget.max_repairs = min(self.config.security_max_repairs_cap, scaled)

    def is_exhausted(self) -> bool:
        return self.budget.is_exhausted

    def get_remaining_percentage(self) -> float:
        return self.budget.remaining_percentage()

    def get_budget_summary(self) -> Dict[str, Any]:
        return self.budget.to_dict()
