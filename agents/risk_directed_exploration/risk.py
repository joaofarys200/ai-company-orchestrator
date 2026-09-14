"""
JARVIS OS — Phase 52: Risk-Directed Behavioral Exploration & Adaptive Proof Search
Multi-dimensional Risk Evaluator.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents.risk_directed_exploration.models import BehavioralExplorationRisk


class RiskEvaluator:
    """
    Evaluates behavioral exploration risk across 11 explicit dimensions.
    Transparently produces normalized risk_score while preserving all components.
    """

    def evaluate_risk(
        self,
        contract_schema_delta: Optional[Dict[str, Any]] = None,
        consumers: Optional[List[str]] = None,
        is_economic: bool = False,
        is_security_critical: bool = False,
        polymorphic_variants: Optional[List[str]] = None,
        dynamic_consumer_uncertainties: Optional[List[str]] = None,
        historical_failure_count: int = 0,
        historical_total_runs: int = 10,
        current_coverage_pct: float = 0.0,
        predictive_impact_level: str = "MEDIUM",
    ) -> BehavioralExplorationRisk:
        """
        Evaluate full risk profile for a migration or operation.
        """
        delta = contract_schema_delta or {}
        consumers_list = consumers or []
        uncertainties = dynamic_consumer_uncertainties or []
        variants = polymorphic_variants or []

        # 1. Contract Risk (breaking changes, field removals, type changes)
        contract_risk = 0.2
        if delta.get("removed_fields"):
            contract_risk += 0.5
        if delta.get("type_changes"):
            contract_risk += 0.3
        contract_risk = min(1.0, contract_risk)

        # 2. Consumer Risk (number of dependent downstream consumers)
        consumer_risk = min(1.0, len(consumers_list) * 0.25)

        # 3. Economic Risk (monetary amount/currency involved)
        economic_risk = 1.0 if is_economic else 0.0

        # 4. Security Risk (auth, roles, token validation)
        security_risk = 1.0 if is_security_critical else 0.1

        # 5. Polymorphic Risk (multiple discriminated variants)
        polymorphic_risk = min(1.0, len(variants) * 0.25) if len(variants) > 1 else 0.1

        # 6. Dynamic Consumer Risk (presence of unresolved dynamic consumers)
        dynamic_consumer_risk = 0.9 if uncertainties else 0.1

        # 7. Behavioral Uncertainty
        behavioral_uncertainty = 0.8 if uncertainties else 0.2

        # 8. Historical Failure Rate
        historical_rate = min(1.0, historical_failure_count / max(1, historical_total_runs))

        # 9. Blast Radius
        impact_upper = predictive_impact_level.upper()
        if impact_upper == "HIGH" or impact_upper == "CRITICAL" or impact_upper == "CROSS_MODULE":
            blast_radius = 0.9
        elif impact_upper == "MEDIUM":
            blast_radius = 0.5
        else:
            blast_radius = 0.2

        # 10. Change Magnitude
        magnitude = 0.2
        if delta.get("properties_changed"):
            magnitude += len(delta["properties_changed"]) * 0.15
        change_magnitude = min(1.0, magnitude)

        # 11. Coverage Gap (1.0 - coverage_pct)
        coverage_gap = max(0.0, 1.0 - current_coverage_pct)

        risk = BehavioralExplorationRisk(
            contract_risk=round(contract_risk, 4),
            consumer_risk=round(consumer_risk, 4),
            economic_risk=round(economic_risk, 4),
            security_risk=round(security_risk, 4),
            polymorphic_risk=round(polymorphic_risk, 4),
            dynamic_consumer_risk=round(dynamic_consumer_risk, 4),
            behavioral_uncertainty=round(behavioral_uncertainty, 4),
            historical_failure_rate=round(historical_rate, 4),
            blast_radius=round(blast_radius, 4),
            change_magnitude=round(change_magnitude, 4),
            coverage_gap=round(coverage_gap, 4),
        )
        risk.compute_score()
        return risk
