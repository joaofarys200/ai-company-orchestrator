"""
JARVIS OS — Phase 56: Divergence Monitor
Monitors failure count growth, regression rates, blast radius expansion, and divergence velocity.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set
from agents.repair_convergence_governance.models import (
    DivergenceReport,
    RepairStepSnapshot,
)


class DivergenceMonitor:
    """Monitors whether a repair process is diverging rather than converging."""

    def __init__(
        self,
        failure_increase_threshold: int = 3,
        blast_radius_threshold: int = 5,
        velocity_threshold: float = 2.0,
    ):
        self.failure_increase_threshold = failure_increase_threshold
        self.blast_radius_threshold = blast_radius_threshold
        self.velocity_threshold = velocity_threshold

    def evaluate_divergence(self, history: List[RepairStepSnapshot]) -> DivergenceReport:
        """Evaluates snapshots for divergent behavior."""
        if len(history) < 2:
            return DivergenceReport(diverging=False, explanation="Insufficient history to assess divergence.")

        initial = history[0]
        previous = history[-2]
        current = history[-1]

        # 1. Failure Trend
        init_fails = len(initial.active_failures)
        curr_fails = len(current.active_failures)
        prev_fails = len(previous.active_failures)

        net_failure_delta = curr_fails - init_fails
        step_failure_delta = curr_fails - prev_fails

        # 2. Regressions (failures present now that were not present in initial baseline)
        regressed_failures = [f for f in current.active_failures if f not in initial.active_failures]

        # 3. Blast radius
        files_touched = set()
        for s in history:
            files_touched.update(s.modified_files)
        blast_radius = len(files_touched)

        # 4. Divergence velocity
        # Velocity = step_failure_delta + 0.5 * len(regressed_failures) + 0.2 * (curr_fails / max(1, init_fails))
        divergence_velocity = max(0.0, float(step_failure_delta) + 0.5 * len(regressed_failures))

        # Check conditions for divergence
        is_diverging = False
        reasons = []

        if net_failure_delta >= self.failure_increase_threshold:
            is_diverging = True
            reasons.append(
                f"Net failure count increased by {net_failure_delta} (from {init_fails} to {curr_fails})."
            )

        if len(regressed_failures) >= 3:
            is_diverging = True
            reasons.append(
                f"{len(regressed_failures)} newly introduced regressed failures detected."
            )

        if blast_radius >= self.blast_radius_threshold and curr_fails >= init_fails:
            is_diverging = True
            reasons.append(
                f"Blast radius expanded to {blast_radius} files while failures remained unconverged ({curr_fails} active)."
            )

        if divergence_velocity >= self.velocity_threshold:
            is_diverging = True
            reasons.append(
                f"Divergence velocity {divergence_velocity:.2f} exceeded threshold {self.velocity_threshold:.2f}."
            )

        explanation = "; ".join(reasons) if reasons else "Repair trajectory is stable or progressing towards convergence."

        return DivergenceReport(
            diverging=is_diverging,
            failure_count_trend=[len(s.active_failures) for s in history],
            divergence_velocity=round(divergence_velocity, 3),
            regressed_failures=regressed_failures,
            blast_radius_files=sorted(list(files_touched)),
            explanation=explanation,
        )
