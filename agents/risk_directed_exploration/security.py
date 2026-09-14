"""
JARVIS OS — Phase 52: Risk-Directed Behavioral Exploration & Adaptive Proof Search
Security Sentinel: Sovereign authority preventing risk spoofing, priority poisoning, and injection attacks.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from agents.behavioral_proof_exploration.models import (
    BehavioralCoverage,
    BehavioralScenario,
)
from agents.behavioral_proof_exploration.security import ExplorationSecuritySentinel
from agents.risk_directed_exploration.models import (
    BehavioralExplorationRisk,
    ScenarioRanking,
)


class RiskSpoofingDetectedError(Exception):
    """Raised when untrusted metadata attempts to artificially suppress or spoof risk scores."""
    pass


class PriorityPoisoningDetectedError(Exception):
    """Raised when malicious or manipulated priority ordering is detected."""
    pass


class RiskSecuritySentinel:
    """
    Sovereign Security Authority for Risk-Directed Exploration.
    Prevents risk spoofing (e.g. metadata falsely claiming risk=LOW for economic operations),
    coverage spoofing, priority poisoning, and injection attacks.
    """

    def __init__(self) -> None:
        self.base_sentinel = ExplorationSecuritySentinel()

    def inspect_risk_assessment(
        self,
        risk: BehavioralExplorationRisk,
        is_economic: bool = False,
        is_security_critical: bool = False,
        unresolved_consumers_count: int = 0,
    ) -> None:
        """
        Verify that risk calculations are legitimate and not spoofed or suppressed.
        """
        # If operation is economic, economic_risk must NOT be artificially suppressed to 0
        if is_economic and risk.economic_risk < 0.5:
            raise RiskSpoofingDetectedError(
                f"Economic risk suppression detected! Is economic operation but economic_risk is {risk.economic_risk}."
            )

        # If unresolved consumers exist, dynamic_consumer_risk must NOT be zero
        if unresolved_consumers_count > 0 and risk.dynamic_consumer_risk < 0.5:
            raise RiskSpoofingDetectedError(
                f"Dynamic consumer risk suppression detected! {unresolved_consumers_count} unresolved consumers exist."
            )

        # If security critical, security_risk must be elevated
        if is_security_critical and risk.security_risk < 0.8:
            raise RiskSpoofingDetectedError(
                f"Security risk suppression detected! Security-critical operation has security_risk {risk.security_risk}."
            )

    def inspect_rankings(self, rankings: List[ScenarioRanking], is_economic: bool = False) -> None:
        """Verify that ranking priorities adhere to policy constraints."""
        if not rankings:
            return

        # Priorities must be non-negative
        for r in rankings:
            if r.priority < 0:
                raise PriorityPoisoningDetectedError(f"Negative priority detected for scenario {r.scenario_id}: {r.priority}")

    def inspect_scenario(self, scenario: BehavioralScenario) -> None:
        """Delegate payload injection inspection to base sentinel."""
        self.base_sentinel.inspect_scenario(scenario)

    def inspect_coverage(self, coverage: BehavioralCoverage, scenarios: List[BehavioralScenario]) -> None:
        """Delegate coverage spoofing inspection to base sentinel."""
        self.base_sentinel.inspect_coverage(coverage, scenarios)
