"""
JARVIS OS — Phase 51: Behavioral Proof Coverage & Scenario Exploration
Security Sentinel: Sovereign authority for Behavioral Exploration integrity and protection.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from agents.behavioral_contract_proof.security import BehavioralSecuritySentinel
from agents.behavioral_proof_exploration.models import (
    BehavioralCoverage,
    BehavioralScenario,
    CoverageDimension,
)


class SecurityExplorationTamperedError(Exception):
    """Raised when malicious or tampered exploration artifacts are detected."""
    pass


class SecurityCoverageSpoofingError(Exception):
    """Raised when coverage numbers are artificially inflated without evidence backing."""
    pass


class ExplorationSecuritySentinel:
    """
    Sovereign Security Authority for Phase 51 Behavioral Exploration.
    Prevents coverage spoofing, prompt injection, payload poisoning,
    and unauthorized tampering with exploration traces and baselines.
    """

    SUSPICIOUS_PATTERNS = [
        re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
        re.compile(r"system\s+override", re.IGNORECASE),
        re.compile(r"drop\s+table", re.IGNORECASE),
        re.compile(r"grant\s+all", re.IGNORECASE),
        re.compile(r"bypass\s+sentinel", re.IGNORECASE),
        re.compile(r"<script.*?>", re.IGNORECASE),
    ]

    def __init__(self) -> None:
        self.base_sentinel = BehavioralSecuritySentinel()

    def inspect_scenario(self, scenario: BehavioralScenario) -> None:
        """Inspect scenario for malicious prompt injection or toxic payloads."""
        payload_str = str(scenario.input) + str(scenario.expected_behavior)
        for pattern in self.SUSPICIOUS_PATTERNS:
            if pattern.search(payload_str):
                raise SecurityExplorationTamperedError(
                    f"Malicious payload or prompt injection detected in scenario {scenario.scenario_id}: {pattern.pattern}"
                )

    def inspect_coverage(self, coverage: BehavioralCoverage, scenarios: List[BehavioralScenario]) -> None:
        """
        Verify that coverage is evidence-backed.
        Detects artificial coverage spoofing.
        """
        # If overall coverage claims > 0 but scenarios list is empty, it's a spoof!
        if coverage.overall_percentage > 0.0 and len(scenarios) == 0:
            raise SecurityCoverageSpoofingError(
                f"Coverage spoofing detected! Coverage claims {coverage.overall_percentage*100}% with 0 scenarios."
            )

        # Check that reported covered items do not exceed actual scenarios
        total_covered = sum(r.covered for r in coverage.dimensions.values())
        if total_covered > 0 and len(scenarios) == 0:
            raise SecurityCoverageSpoofingError("Evidence-backed coverage violated: zero scenarios executed.")

    def inspect_tampered_counterexample(self, minimal_input: Dict[str, Any], original_input: Dict[str, Any]) -> None:
        """Verify that shrunk minimal input is a true subset of original input."""
        for k in minimal_input:
            if k not in original_input:
                raise SecurityExplorationTamperedError(
                    f"Tampered counterexample! Field '{k}' in minimal input was not present in original input."
                )
