"""
JARVIS OS — Phase 69: Autonomous Quality Debt Remediation
Cost and ROI evaluation model. Separates observed, estimated, and inferred metrics without single-number reductionism.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass
class CostCategoryBreakdown:
    implementation_cost: float
    verification_cost: float
    maintenance_cost: float
    risk_reduction: float
    quality_benefit: float
    reversal_cost: float

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


@dataclass
class MultiDimensionalCostProfile:
    debt_id: str
    observed: CostCategoryBreakdown
    estimated: CostCategoryBreakdown
    inferred: CostCategoryBreakdown
    composite_summary: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "debt_id": self.debt_id,
            "observed": self.observed.to_dict(),
            "estimated": self.estimated.to_dict(),
            "inferred": self.inferred.to_dict(),
            "composite_summary": self.composite_summary,
        }


class DebtRemediationCostModel:
    """
    Evaluates multi-dimensional costs across implementation, verification,
    maintenance, and reversibility without collapsing to a single scalar ROI.
    """

    def compute_cost_profile(
        self,
        debt_id: str,
        files_count: int,
        test_suites_count: int,
        complexity_delta: float = 0.0,
        observed_execution_seconds: float = 0.0,
    ) -> MultiDimensionalCostProfile:
        # 1. Observed metrics (factual measured runs)
        observed = CostCategoryBreakdown(
            implementation_cost=round(observed_execution_seconds * 0.01, 3),
            verification_cost=round(observed_execution_seconds * 0.005, 3),
            maintenance_cost=0.0,
            risk_reduction=0.0,
            quality_benefit=0.0,
            reversal_cost=0.0,
        )

        # 2. Estimated metrics (analytical approximations)
        est_impl = round(files_count * 1.5, 2)
        est_verif = round(test_suites_count * 0.8, 2)
        est_maint = round(max(0.5, files_count * 0.3), 2)
        est_risk_red = round(files_count * 2.0, 2)
        est_qual_ben = round(max(1.0, files_count * 2.5), 2)
        est_reversal = round(files_count * 0.5, 2)

        estimated = CostCategoryBreakdown(
            implementation_cost=est_impl,
            verification_cost=est_verif,
            maintenance_cost=est_maint,
            risk_reduction=est_risk_red,
            quality_benefit=est_qual_ben,
            reversal_cost=est_reversal,
        )

        # 3. Inferred metrics (long-horizon extrapolations)
        inferred = CostCategoryBreakdown(
            implementation_cost=round(est_impl * 1.2, 2),
            verification_cost=round(est_verif * 1.4, 2),
            maintenance_cost=round(est_maint * 3.0, 2),
            risk_reduction=round(est_risk_red * 1.5, 2),
            quality_benefit=round(est_qual_ben * 1.8, 2),
            reversal_cost=round(est_reversal * 2.0, 2),
        )

        composite_summary = {
            "total_estimated_burden": round(est_impl + est_verif + est_maint, 2),
            "total_estimated_value": round(est_risk_red + est_qual_ben, 2),
            "reversibility_margin": round(est_reversal, 2),
            "decision_posture": "FAVORABLE" if (est_risk_red + est_qual_ben) > (est_impl + est_verif) else "MARGINAL",
        }

        return MultiDimensionalCostProfile(
            debt_id=debt_id,
            observed=observed,
            estimated=estimated,
            inferred=inferred,
            composite_summary=composite_summary,
        )
