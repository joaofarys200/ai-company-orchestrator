"""
JARVIS OS — Phase 57: Dynamic Mission Risk Scorer
Computes multi-dimensional operational and systemic risk throughout mission execution.
"""

from __future__ import annotations

from typing import Any

from .models import AutonomousMission


class MissionRiskScorer:
    """Evaluates multi-factor risk across code changes, contracts, security, and economic scope."""

    @classmethod
    def evaluate_risk(cls, mission: AutonomousMission) -> float:
        domain = mission.provenance.get("domain", "general_engineering")
        base_risk = 0.1

        # Domain risk weighting
        if domain == "security_task":
            base_risk += 0.35
        elif domain in ("backend", "contract_change"):
            base_risk += 0.20
        elif domain == "fullstack":
            base_risk += 0.15

        # Economic risk
        if mission.economic_policy:
            base_risk += 0.25

        # Failure count impact
        active_failures = [f for f in mission.failures if not f.get("resolved", False)]
        base_risk += min(0.3, len(active_failures) * 0.1)

        # Repairs churn impact
        base_risk += min(0.15, len(mission.repairs) * 0.05)

        # Bounded between 0.05 and 0.95
        final_risk = max(0.05, min(0.95, base_risk))
        mission.risk = round(final_risk, 3)
        return mission.risk
