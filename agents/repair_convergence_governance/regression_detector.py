"""
JARVIS OS — Phase 56: Regression Detector
Tracks resolved failures vs newly introduced or reintroduced failures during repair cycles.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set
from agents.repair_convergence_governance.models import (
    RegressionReport,
    RepairStepSnapshot,
)


class RegressionDetector:
    """Detects regressions, reintroduced bugs, and collateral damage during iterative repair."""

    def __init__(self, tolerance_threshold: int = 0):
        # By default, 0 tolerance for reintroducing previously fixed bugs
        self.tolerance_threshold = tolerance_threshold

    def evaluate_regression(self, history: List[RepairStepSnapshot]) -> RegressionReport:
        """Evaluates whether the most recent repair step caused a regression."""
        if len(history) < 2:
            return RegressionReport(
                regressed=False,
                reintroduced_failures=[],
                new_failures=[],
                explanation="Initial repair step; baseline established."
            )

        prev = history[-2]
        curr = history[-1]

        prev_active = set(prev.active_failures)
        curr_active = set(curr.active_failures)

        # Failures that were fixed prior to curr
        all_past_active: Set[str] = set()
        for snap in history[:-1]:
            all_past_active.update(snap.active_failures)

        # Failures that were fixed in prev
        resolved_previously = all_past_active - prev_active

        # Newly introduced in curr
        introduced = curr_active - prev_active

        # Reintroduced: introduced failures that existed in the past and were resolved
        reintroduced = list(introduced.intersection(resolved_previously))
        brand_new = list(introduced - set(reintroduced))

        regressed = len(reintroduced) > self.tolerance_threshold or len(brand_new) > 0

        severity = "NONE"
        if reintroduced:
            severity = "CRITICAL" if len(reintroduced) >= 2 else "HIGH"
        elif brand_new:
            severity = "MEDIUM" if len(brand_new) >= 2 else "LOW"

        explanation_parts = []
        if reintroduced:
            explanation_parts.append(f"Reintroduced {len(reintroduced)} previously resolved failure(s): {reintroduced}.")
        if brand_new:
            explanation_parts.append(f"Introduced {len(brand_new)} brand new failure(s): {brand_new}.")
        if not regressed:
            explanation_parts.append("No regressions detected. Progress is strictly monotonic or neutral.")

        return RegressionReport(
            regressed=regressed,
            reintroduced_failures=reintroduced,
            new_failures=brand_new,
            regression_severity=severity,
            explanation=" ".join(explanation_parts)
        )
