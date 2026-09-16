"""
JARVIS OS — Phase 56: Stall Detector
Detects stagnation, progress plateauing, coverage freezes, and failure count stagnation.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from agents.repair_convergence_governance.models import (
    ProgressVector,
    RepairStepSnapshot,
    StallReport,
    StallType,
)


class StallDetector:
    """Monitors repair iterations to detect stagnation and lack of monotonic progress."""

    def __init__(
        self,
        min_stagnant_iterations: int = 3,
        epsilon_progress: float = 0.01,
        risk_stagnation_tolerance: float = 0.005,
    ):
        self.min_stagnant_iterations = min_stagnant_iterations
        self.epsilon_progress = epsilon_progress
        self.risk_stagnation_tolerance = risk_stagnation_tolerance

    def evaluate_stall(
        self,
        history: List[RepairStepSnapshot],
        progress_vectors: Optional[List[ProgressVector]] = None,
    ) -> StallReport:
        """Evaluates whether recent repair iterations have stalled."""
        if len(history) < self.min_stagnant_iterations:
            return StallReport(
                stalled=False,
                consecutive_stagnant_iterations=0,
                explanation="Insufficient iterations to establish stall condition."
            )

        window = history[-self.min_stagnant_iterations:]

        # 1. Coverage Stagnation (patches applied across steps but coverage did not advance)
        coverages = [s.behavioral_proof_coverage for s in window]
        cov_delta = coverages[-1] - coverages[0]
        all_had_patches = all(len(s.patches_applied) > 0 for s in window[1:])
        if all_had_patches and cov_delta <= self.epsilon_progress:
            return StallReport(
                stalled=True,
                stall_type=StallType.COVERAGE_STAGNATION,
                consecutive_stagnant_iterations=self.min_stagnant_iterations,
                metric_delta=round(cov_delta, 4),
                explanation=f"Behavioral proof coverage stagnated (delta {cov_delta:.4f} <= {self.epsilon_progress}) despite {self.min_stagnant_iterations - 1} patch applications."
            )

        # 2. Failure Count Stagnation
        failure_counts = [len(s.active_failures) for s in window]
        if len(set(failure_counts)) == 1:
            return StallReport(
                stalled=True,
                stall_type=StallType.FAILURE_COUNT_UNCHANGED,
                consecutive_stagnant_iterations=self.min_stagnant_iterations,
                metric_delta=0.0,
                explanation=f"Active failure count remained unchanged at {failure_counts[0]} for {self.min_stagnant_iterations} consecutive iterations."
            )

        # 3. Risk Stagnation (e.g. 0.420 -> 0.421 -> 0.420)
        risks = [s.risk_score for s in window]
        risk_range = max(risks) - min(risks)
        if risk_range <= self.risk_stagnation_tolerance and risks[-1] >= risks[0]:
            return StallReport(
                stalled=True,
                stall_type=StallType.RISK_STAGNATION,
                consecutive_stagnant_iterations=self.min_stagnant_iterations,
                metric_delta=round(risk_range, 4),
                explanation=f"Risk score stagnated in narrow range {risks[0]:.3f}..{risks[-1]:.3f} (range {risk_range:.4f} <= {self.risk_stagnation_tolerance})."
            )

        # 4. Progress Vector Delta Stall
        if progress_vectors and len(progress_vectors) >= self.min_stagnant_iterations:
            recent_vectors = progress_vectors[-self.min_stagnant_iterations:]
            net_resolved = sum(v.resolved_failures - v.new_failures for v in recent_vectors[1:])
            if net_resolved <= 0:
                return StallReport(
                    stalled=True,
                    stall_type=StallType.PROGRESS_METRIC_ZERO,
                    consecutive_stagnant_iterations=self.min_stagnant_iterations,
                    metric_delta=float(net_resolved),
                    explanation=f"Net progress metric score across last {self.min_stagnant_iterations} steps was {net_resolved} (non-positive)."
                )

        return StallReport(
            stalled=False,
            consecutive_stagnant_iterations=0,
            metric_delta=0.0,
            explanation="Monotonic progress observed within acceptable operational bounds."
        )
