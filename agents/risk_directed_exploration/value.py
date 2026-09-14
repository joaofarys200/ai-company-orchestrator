"""
JARVIS OS — Phase 52: Risk-Directed Behavioral Exploration & Adaptive Proof Search
Value of Information Estimator: Computes audit-ready information gain for candidate scenarios.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents.behavioral_proof_exploration.models import (
    BehavioralCoverage,
    BehavioralScenario,
    CoverageDimension,
)
from agents.risk_directed_exploration.models import (
    BehavioralExplorationRisk,
    BehavioralUncertainty,
    ScenarioInformationValue,
)


class ValueOfInformationEstimator:
    """
    Estimates the information value of executing a specific scenario.
    Provides human-readable, transparent explanations for the score.
    """

    def estimate_value(
        self,
        scenario: BehavioralScenario,
        risk: BehavioralExplorationRisk,
        uncertainty: BehavioralUncertainty,
        current_coverage: Optional[BehavioralCoverage] = None,
        historical_failure_weight: float = 0.0,
        blast_radius: float = 0.5,
    ) -> ScenarioInformationValue:
        """
        Compute information value and explanation.
        """
        target = scenario.coverage_target.lower()
        strategy = scenario.strategy.value

        # 1. Potential Risk Relevance
        pot_risk = 0.2
        if "amount" in target or "currency" in target or "economic" in target:
            pot_risk = max(pot_risk, risk.economic_risk)
        if "auth" in target:
            pot_risk = max(pot_risk, risk.security_risk)
        if "variant" in target:
            pot_risk = max(pot_risk, risk.polymorphic_risk)
        if "timeout" in target or "retry" in target or "partial" in target:
            pot_risk = max(pot_risk, 0.7)

        # 2. Coverage Gain Estimate
        cov_gain = 0.1
        if current_coverage:
            # If target dimension has uncovered items matching this scenario
            if any(target in item.lower() for item in current_coverage.uncovered_items):
                cov_gain = 0.8
            else:
                cov_gain = 0.2
        else:
            cov_gain = 0.5

        # 3. Uncertainty Reduction Estimate
        unc_reduction = 0.2
        if "unknown" in target:
            unc_reduction = max(unc_reduction, uncertainty.unknown_variant)
        if "error" in target or "invalid" in target:
            unc_reduction = max(unc_reduction, uncertainty.unknown_error_path)
        if "boundary" in target:
            unc_reduction = max(unc_reduction, 0.6)

        # 4. Invariant Relevance
        inv_rel = 0.3
        if "economic" in target or "amount" in target:
            inv_rel = 1.0
        elif "auth" in target:
            inv_rel = 0.95
        elif "retry" in target or "idempotency" in target:
            inv_rel = 0.85

        # 5. Contract Delta Relevance
        delta_rel = 0.5
        if scenario.mutation:
            delta_rel = 0.85

        # 6. Novelty
        novelty = 0.7 if "unknown" in target or "boundary" in target else 0.3

        info_val = ScenarioInformationValue(
            scenario_id=scenario.scenario_id,
            potential_risk=round(pot_risk, 4),
            coverage_gain_estimate=round(cov_gain, 4),
            uncertainty_reduction_estimate=round(unc_reduction, 4),
            blast_radius=round(blast_radius, 4),
            novelty=round(novelty, 4),
            historical_failure_weight=round(historical_failure_weight, 4),
            contract_delta_relevance=round(delta_rel, 4),
            invariant_relevance=round(inv_rel, 4),
        )
        score = info_val.compute_value()

        # Generate transparent explanation
        info_val.explanation = (
            f"InfoVal={score:.3f} [RiskRel={pot_risk:.2f}, CovGain={cov_gain:.2f}, "
            f"UncRed={unc_reduction:.2f}, InvRel={inv_rel:.2f}]"
        )
        return info_val
