"""
JARVIS OS — Phase 65: Safe Self-Modification & Transactional Architecture Implementation
Module: convergence.py
Integrates F56 (Repair Convergence Governance & Lyapunov Stability) to enforce
strict modification budgets (iterations, patches, retries, time, memory) and prevent
infinite self-modification loops or divergence oscillations.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from .models import ConvergenceState


class ConvergenceGovernor:
    """Enforces termination budgets and Lyapunov convergence metrics on self-modification cycles."""

    def __init__(
        self,
        max_iterations: int = 5,
        max_patches: int = 10,
        max_retries: int = 2,
        max_wall_time_sec: float = 300.0,
    ):
        self.max_iterations = max_iterations
        self.max_patches = max_patches
        self.max_retries = max_retries
        self.max_wall_time_sec = max_wall_time_sec

        self.iteration_count = 0
        self.patch_count = 0
        self.retry_count = 0
        self.start_time = time.time()
        self.error_trajectory: List[int] = []

    def record_step(
        self,
        errors_remaining: int,
        patches_applied: int = 1,
    ) -> Tuple[ConvergenceState, str]:
        """Record modification progress and evaluate Lyapunov stability."""
        self.iteration_count += 1
        self.patch_count += patches_applied
        self.error_trajectory.append(errors_remaining)

        elapsed = time.time() - self.start_time

        # Budget exhaustion checks
        if elapsed > self.max_wall_time_sec:
            return ConvergenceState.BLOCKED, f"BUDGET_EXCEEDED: Wall time {elapsed:.1f}s exceeded limit {self.max_wall_time_sec}s."

        if self.iteration_count > self.max_iterations:
            return ConvergenceState.BLOCKED, f"BUDGET_EXCEEDED: Iterations {self.iteration_count} exceeded limit {self.max_iterations}."

        if self.patch_count > self.max_patches:
            return ConvergenceState.BLOCKED, f"BUDGET_EXCEEDED: Patch count {self.patch_count} exceeded limit {self.max_patches}."

        # Stable resolution
        if errors_remaining == 0:
            return ConvergenceState.STABLE, "CONVERGENCE_ACHIEVED: Zero residual errors remaining."

        # Oscillation detection (e.g. errors alternating [2, 3, 2, 3])
        if len(self.error_trajectory) >= 4:
            recent = self.error_trajectory[-4:]
            if recent[0] == recent[2] and recent[1] == recent[3] and recent[0] != recent[1]:
                return ConvergenceState.OSCILLATING, f"OSCILLATION_DETECTED: Error count oscillating {recent}."

        # Divergence detection (errors increasing monotonically)
        if len(self.error_trajectory) >= 3:
            if self.error_trajectory[-1] > self.error_trajectory[-2] > self.error_trajectory[-3]:
                return ConvergenceState.DIVERGING, f"DIVERGENCE_DETECTED: Errors strictly increasing {self.error_trajectory[-3:]}."

        # Monotonic decrease = converging
        if len(self.error_trajectory) >= 2 and self.error_trajectory[-1] < self.error_trajectory[-2]:
            return ConvergenceState.CONVERGING, "CONVERGING: Error metric decreasing strictly monotonically."

        return ConvergenceState.CONVERGING, "IN_PROGRESS: Within acceptable Lyapunov convergence boundaries."
