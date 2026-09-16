"""
JARVIS OS — Phase 56: Progress Vector Tracker
Tracks 8-dimensional progress vector, computes Delta P, and enforces strict Lyapunov monotonicity.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from agents.repair_convergence_governance.models import (
    ProgressDelta,
    ProgressVector,
    compute_vector_delta,
)


class ProgressVectorTracker:
    """Manages tracking and verification of the multidimensional progress vector P."""

    def __init__(self, epsilon_progress: float = 0.01):
        self.epsilon_progress = epsilon_progress
        self.vector_history: List[ProgressVector] = []
        self.delta_history: List[ProgressDelta] = []

    def record_initial_state(self, initial_vector: Optional[ProgressVector] = None) -> ProgressVector:
        """Initializes the baseline progress vector P_0."""
        vec = initial_vector or ProgressVector()
        self.vector_history = [vec]
        self.delta_history = []
        return vec

    def record_step_progress(self, p_after: ProgressVector) -> Tuple[ProgressDelta, bool]:
        """Records P_after, computes delta P = P_after - P_before, and evaluates monotonic progress."""
        if not self.vector_history:
            self.record_initial_state()

        p_before = self.vector_history[-1]
        delta = compute_vector_delta(p_before, p_after)

        self.vector_history.append(p_after)
        self.delta_history.append(delta)

        # Monotonicity check: Delta score must be strictly positive and no new blocking failures
        is_strictly_monotonic = (delta.score >= self.epsilon_progress) and (delta.blocking_delta <= 0)
        return delta, is_strictly_monotonic

    def get_latest_vector(self) -> ProgressVector:
        return self.vector_history[-1] if self.vector_history else ProgressVector()

    def get_latest_delta(self) -> Optional[ProgressDelta]:
        return self.delta_history[-1] if self.delta_history else None

    def get_cumulative_progress_score(self) -> float:
        """Returns the total accumulated progress score across all steps."""
        return round(sum(d.score for d in self.delta_history), 4)

    def is_progress_stagnant(self, window_size: int = 3) -> bool:
        """Evaluates whether recent delta scores are below epsilon threshold."""
        if len(self.delta_history) < window_size:
            return False
        recent = self.delta_history[-window_size:]
        return all(d.score < self.epsilon_progress for d in recent)
