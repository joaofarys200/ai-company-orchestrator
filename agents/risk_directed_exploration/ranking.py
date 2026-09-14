"""
JARVIS OS — Phase 52: Risk-Directed Behavioral Exploration & Adaptive Proof Search
Scenario Ranker: Deterministic scenario prioritization with policy overrides and tie-breaking.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents.behavioral_proof_exploration.models import BehavioralScenario
from agents.risk_directed_exploration.models import (
    BehavioralExplorationRisk,
    BehavioralUncertainty,
    ExplorationPolicy,
    ScenarioInformationValue,
    ScenarioRanking,
)
from agents.risk_directed_exploration.value import ValueOfInformationEstimator


class ScenarioRanker:
    """
    Ranks exploration scenarios deterministically based on:
    priority = risk * information_value * uncertainty_reduction * impact_weight
    Resolves ties deterministically by scenario_id.
    Applies policy caps and mandatory overrides for critical risks.
    """

    def __init__(self, value_estimator: Optional[ValueOfInformationEstimator] = None) -> None:
        self.value_estimator = value_estimator or ValueOfInformationEstimator()

    def rank_scenarios(
        self,
        scenarios: List[BehavioralScenario],
        risk: BehavioralExplorationRisk,
        uncertainty: BehavioralUncertainty,
        policy: ExplorationPolicy = ExplorationPolicy.STANDARD,
        impact_weight: float = 1.0,
    ) -> List[ScenarioRanking]:
        """
        Produce a deterministic ranked list of scenarios.
        """
        ranked_entries: List[ScenarioRanking] = []

        for scen in scenarios:
            info_val = self.value_estimator.estimate_value(scen, risk, uncertainty)

            # Base priority formula
            base_priority = (
                (0.2 + risk.risk_score * 0.8)
                * (0.2 + info_val.total_information_value * 0.8)
                * (0.2 + info_val.uncertainty_reduction_estimate * 0.8)
                * impact_weight
            )

            # Check Policy Overrides
            policy_override = False
            override_reason: Optional[str] = None
            target = scen.coverage_target.lower()

            # ECONOMIC_CRITICAL override
            if policy == ExplorationPolicy.ECONOMIC_CRITICAL:
                if any(k in target for k in ("amount", "currency", "idempotency", "retry", "economic")):
                    base_priority += 2.0  # Massive boost guaranteeing top rank
                    policy_override = True
                    override_reason = "Mandatory Economic Critical scenario"

            # SECURITY_CRITICAL override
            elif policy == ExplorationPolicy.SECURITY_CRITICAL:
                if "auth" in target or "permission" in target or "token" in target:
                    base_priority += 2.0
                    policy_override = True
                    override_reason = "Mandatory Security Critical scenario"

            # CRITICAL policy general boost
            elif policy == ExplorationPolicy.CRITICAL:
                if scen.mutation and any(k in scen.mutation.get("type", "") for k in ("boundary", "missing")):
                    base_priority += 0.5

            entry = ScenarioRanking(
                scenario_id=scen.scenario_id,
                priority=round(base_priority, 6),
                rank=0,  # assigned after sorting
                risk_score=risk.risk_score,
                information_value=info_val.total_information_value,
                uncertainty_reduction=info_val.uncertainty_reduction_estimate,
                impact_weight=impact_weight,
                policy_override_applied=policy_override,
                override_reason=override_reason,
                target_field=scen.coverage_target,
                strategy=scen.strategy,
            )
            ranked_entries.append(entry)

        # Deterministic sorting: primary key is -priority (descending), secondary key is scenario_id (ascending)
        ranked_entries.sort(key=lambda item: (-item.priority, item.scenario_id))

        # Assign 1-indexed ranks
        for idx, entry in enumerate(ranked_entries, start=1):
            entry.rank = idx

        return ranked_entries
