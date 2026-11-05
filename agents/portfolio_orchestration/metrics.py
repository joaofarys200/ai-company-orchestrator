"""
JARVIS OS — Phase 75: Autonomous Engineering Strategy & Portfolio Orchestration
Module: metrics.py
Cumulative outcome tracking, portfolio ROI calculation, regression tracking, and baseline verification.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .models import (
    EngineeringInitiative,
    InitiativeState,
    PortfolioMetrics,
)


class PortfolioMetricsTracker:
    """
    Computes global system-wide indicators and ROI across multi-initiative portfolios.
    Tracks expected versus realized benefits, budget utilization, schedule drift, and regressions.
    """

    def compute_portfolio_metrics(
        self,
        portfolio_id: str,
        initiatives: Dict[str, EngineeringInitiative],
        allocated_budget: float,
        estimated_duration: float,
    ) -> PortfolioMetrics:
        """
        Compute cumulative metrics across all initiatives in the portfolio.
        """
        all_inits = list(initiatives.values())
        total_count = len(all_inits)
        completed = [i for i in all_inits if i.state == InitiativeState.COMPLETED]
        failed = [i for i in all_inits if i.state == InitiativeState.FAILED]
        deferred = [i for i in all_inits if i.state == InitiativeState.DEFERRED]

        expected_benefit = sum(i.expected_benefit * i.confidence for i in all_inits)
        realized_benefit = sum(i.actual_benefit for i in completed)

        budget_consumed = sum(i.actual_cost or i.budget_cost for i in completed) + sum(
            (i.actual_cost or i.budget_cost) * 0.5 for i in failed
        )
        actual_duration = sum(i.actual_duration for i in completed)

        # Regressions: initiatives where actual benefit was negative or error occurred
        regression_count = sum(1 for i in completed if i.actual_benefit < 0) + len(failed)

        verif_pass_rate = 1.0
        if total_count > 0:
            verif_pass_rate = len(completed) / max(1, len(completed) + len(failed))

        roi_ratio = 0.0
        if budget_consumed > 0:
            roi_ratio = realized_benefit / budget_consumed

        summary = (
            f"Portfolio '{portfolio_id}': {len(completed)}/{total_count} initiatives completed "
            f"({verif_pass_rate * 100:.1f}% success). Realized benefit: {realized_benefit:.1f} vs "
            f"expected {expected_benefit:.1f}. Budget consumed: ${budget_consumed:.1f}/${allocated_budget:.1f}. "
            f"ROI: {roi_ratio:.2f}x."
        )

        return PortfolioMetrics(
            portfolio_id=portfolio_id,
            total_initiatives=total_count,
            completed_initiatives=len(completed),
            failed_initiatives=len(failed),
            deferred_initiatives=len(deferred),
            expected_benefit=expected_benefit,
            realized_benefit=realized_benefit,
            budget_allocated=allocated_budget,
            budget_consumed=budget_consumed,
            schedule_estimated_duration=estimated_duration,
            schedule_actual_duration=actual_duration,
            verification_pass_rate=verif_pass_rate,
            regression_count=regression_count,
            roi_ratio=roi_ratio,
            net_improvement_summary=summary,
        )
