from __future__ import annotations

import math
import random
from dataclasses import dataclass, field


@dataclass(frozen=True)
class FinancialMetrics:
    mrr: float  # Monthly Recurring Revenue
    arr: float  # Annual Recurring Revenue
    gross_margin_pct: float  # Gross Margin %
    ebitda_margin_pct: float  # EBITDA Margin %
    cac: float  # Customer Acquisition Cost
    ltv: float  # Customer Lifetime Value
    ltv_cac_ratio: float  # LTV:CAC Ratio
    net_revenue_retention_pct: float  # NRR %


@dataclass(frozen=True)
class MonteCarloProjection:
    months: int
    starting_mrr: float
    simulated_trajectories: list[list[float]]
    p10_final_mrr: float
    p50_final_mrr: float
    p90_final_mrr: float


class FinancialAnalyzer:
    """Enterprise Financial Analytics & Forecasting Engine."""

    @staticmethod
    def calculate_metrics(
        mrr: float,
        gross_margin_pct: float,
        operating_expenses: float,
        new_customers_per_month: float,
        sales_marketing_cost: float,
        churn_rate_pct: float,
        arpu: float,
    ) -> FinancialMetrics:
        """Calculates core financial SaaS metrics including MRR, ARR, CAC, LTV, LTV:CAC ratio."""
        arr = mrr * 12.0
        ebitda = (mrr * (gross_margin_pct / 100.0)) - operating_expenses
        ebitda_margin_pct = (ebitda / mrr * 100.0) if mrr > 0 else 0.0

        cac = (sales_marketing_cost / new_customers_per_month) if new_customers_per_month > 0 else 0.0
        monthly_churn_decimal = (churn_rate_pct / 100.0) if churn_rate_pct > 0 else 0.01
        customer_lifespan_months = 1.0 / monthly_churn_decimal if monthly_churn_decimal > 0 else 100.0
        ltv = arpu * (gross_margin_pct / 100.0) * customer_lifespan_months
        ltv_cac_ratio = (ltv / cac) if cac > 0 else 0.0

        # Net Revenue Retention (estimated from churn rate)
        nrr_pct = max(0.0, 100.0 - churn_rate_pct + 3.0)  # assumes +3% expansion

        return FinancialMetrics(
            mrr=round(mrr, 2),
            arr=round(arr, 2),
            gross_margin_pct=round(gross_margin_pct, 2),
            ebitda_margin_pct=round(ebitda_margin_pct, 2),
            cac=round(cac, 2),
            ltv=round(ltv, 2),
            ltv_cac_ratio=round(ltv_cac_ratio, 2),
            net_revenue_retention_pct=round(nrr_pct, 2),
        )

    @staticmethod
    def run_monte_carlo_simulation(
        starting_mrr: float,
        months: int = 12,
        num_simulations: int = 500,
        expected_monthly_growth_pct: float = 5.0,
        volatility_pct: float = 2.0,
        seed: int = 42,
    ) -> MonteCarloProjection:
        """Simulates 12-month MRR growth trajectory using Monte Carlo geometric Brownian motion."""
        random.seed(seed)
        trajectories: list[list[float]] = []
        final_mrrs: list[float] = []

        mean_growth = expected_monthly_growth_pct / 100.0
        volatility = volatility_pct / 100.0

        for _ in range(num_simulations):
            current = starting_mrr
            path = [current]
            for _ in range(months):
                random_shock = random.gauss(0, 1)
                growth_factor = 1.0 + mean_growth + (volatility * random_shock)
                current = max(0.0, current * growth_factor)
                path.append(round(current, 2))
            trajectories.append(path)
            final_mrrs.append(current)

        sorted_finals = sorted(final_mrrs)
        p10 = sorted_finals[int(num_simulations * 0.10)]
        p50 = sorted_finals[int(num_simulations * 0.50)]
        p90 = sorted_finals[int(num_simulations * 0.90)]

        return MonteCarloProjection(
            months=months,
            starting_mrr=starting_mrr,
            simulated_trajectories=trajectories[:10],  # sample first 10 for plotting/reporting
            p10_final_mrr=round(p10, 2),
            p50_final_mrr=round(p50, 2),
            p90_final_mrr=round(p90, 2),
        )


__all__ = ["FinancialMetrics", "MonteCarloProjection", "FinancialAnalyzer"]
