"""
JARVIS OS — Phase 52: Risk-Directed Behavioral Exploration & Adaptive Proof Search
Exploration Policy Engine: Manages policy thresholds, caps, and mandatory safety sets.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from agents.behavioral_proof_exploration.models import (
    BehavioralCoverage,
    BehavioralScenario,
    CoverageThresholdPolicy,
)
from agents.risk_directed_exploration.models import (
    BehavioralExplorationRisk,
    ExplorationPolicy,
    RiskAdaptiveBudget,
    ScenarioRanking,
)


class ExplorationPolicyEngine:
    """
    Governs exploration policy parameters, mandatory scenario sets, and threshold enforcement.
    Ensures that Economic and Security safety sets override performance scores.
    """

    MANDATORY_ECONOMIC_TARGETS: Set[str] = {
        "authorization",
        "boundary",
        "currency",
        "retry_idempotency",
        "timeout_recovery",
        "partial_failure_rollback",
    }

    MANDATORY_SECURITY_TARGETS: Set[str] = {
        "authorization_failure",
        "authorization_state",
    }

    def get_coverage_threshold_policy(self, policy: ExplorationPolicy) -> CoverageThresholdPolicy:
        """Map ExplorationPolicy to Phase 51 CoverageThresholdPolicy."""
        if policy in (ExplorationPolicy.CRITICAL, ExplorationPolicy.ECONOMIC_CRITICAL, ExplorationPolicy.SECURITY_CRITICAL):
            return CoverageThresholdPolicy.CRITICAL
        elif policy == ExplorationPolicy.STRICT:
            return CoverageThresholdPolicy.STRICT
        return CoverageThresholdPolicy.STANDARD

    def get_initial_budget(self, policy: ExplorationPolicy, risk_score: float) -> RiskAdaptiveBudget:
        """Allocate initial budget scaled to risk score and policy severity."""
        if policy in (ExplorationPolicy.ECONOMIC_CRITICAL, ExplorationPolicy.SECURITY_CRITICAL):
            return RiskAdaptiveBudget(
                max_cost=150.0,
                max_runtime=8.0,
                max_scenarios=120,
                max_depth=4,
                risk_budget=1.5,
            )
        elif policy == ExplorationPolicy.CRITICAL:
            return RiskAdaptiveBudget(
                max_cost=120.0,
                max_runtime=6.0,
                max_scenarios=100,
                max_depth=3,
                risk_budget=1.2,
            )
        elif policy == ExplorationPolicy.STRICT:
            return RiskAdaptiveBudget(
                max_cost=100.0,
                max_runtime=5.0,
                max_scenarios=80,
                max_depth=3,
                risk_budget=1.0,
            )
        else:
            # STANDARD policy scales dynamically with risk score
            scenario_cap = int(30 + risk_score * 50)
            return RiskAdaptiveBudget(
                max_cost=80.0,
                max_runtime=4.0,
                max_scenarios=max(25, scenario_cap),
                max_depth=2,
                risk_budget=max(0.5, risk_score),
            )

    def verify_mandatory_scenarios(
        self,
        policy: ExplorationPolicy,
        executed_scenarios: List[BehavioralScenario],
    ) -> Tuple[bool, List[str]]:
        """
        Verify that all mandatory safety scenarios for the active policy were executed.
        """
        missing_targets: List[str] = []
        executed_targets = {s.coverage_target.lower() for s in executed_scenarios}

        if policy == ExplorationPolicy.ECONOMIC_CRITICAL:
            for req in self.MANDATORY_ECONOMIC_TARGETS:
                if not any(req in t for t in executed_targets):
                    missing_targets.append(f"economic_mandatory:{req}")

        elif policy == ExplorationPolicy.SECURITY_CRITICAL:
            for req in self.MANDATORY_SECURITY_TARGETS:
                if not any(req in t for t in executed_targets):
                    missing_targets.append(f"security_mandatory:{req}")

        passed = len(missing_targets) == 0
        return passed, missing_targets
