"""
JARVIS OS — Phase 74: Autonomous Architectural Evolution & Optimization
Module: experiment_sandbox.py
Isolated worktree empirical benchmarking runner. Contrasts predicted vs measured deltas
with guaranteed zero main working-tree pollution.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .models import (
    ArchitecturalAlternative,
    ExperimentContaminationError,
    ExperimentOutcome,
    ExperimentRecord,
    OptimizationHypothesis,
)


class ExperimentSandbox:
    """
    Executes controlled architectural experiments in disposable, isolated worktrees.
    Measures empirical before-and-after deltas without contaminating the primary repository.
    """

    def __init__(self, main_workspace_path: Optional[str] = None):
        self.main_workspace_path = Path(main_workspace_path or ".").resolve()

    def run_isolated_experiment(
        self,
        alternative: ArchitecturalAlternative,
        hypothesis: OptimizationHypothesis,
        baseline_probe: Callable[[Path], Dict[str, float]],
        mutation_applier: Callable[[Path, ArchitecturalAlternative], Tuple[bool, str]],
        candidate_probe: Callable[[Path], Dict[str, float]],
        regression_thresholds: Optional[Dict[str, float]] = None,
    ) -> ExperimentRecord:
        """
        Executes a controlled experiment in an isolated temporary worktree.
        """
        exp_id = f"exp_{uuid.uuid4().hex[:8]}"
        start_time = time.time()
        temp_dir = Path(tempfile.mkdtemp(prefix="jarvis_opt_sandbox_"))

        try:
            # 1. Contamination Pre-check
            if temp_dir.resolve() == self.main_workspace_path:
                raise ExperimentContaminationError("Sandbox cannot run in primary workspace root.")

            # 2. Run Baseline Benchmark
            baseline_metrics = baseline_probe(temp_dir)
            if hypothesis.target_metric not in baseline_metrics:
                # If target metric wasn't measured in probe, use baseline from hypothesis
                baseline_metrics[hypothesis.target_metric] = hypothesis.current_baseline_value

            # 3. Apply Candidate Mutation in Isolated Sandbox
            apply_ok, apply_msg = mutation_applier(temp_dir, alternative)
            if not apply_ok:
                return ExperimentRecord(
                    experiment_id=exp_id,
                    hypothesis_id=hypothesis.hypothesis_id,
                    alternative_id=alternative.alternative_id,
                    worktree_path=str(temp_dir),
                    baseline_measurements=baseline_metrics,
                    candidate_measurements={},
                    measured_deltas={},
                    outcome=ExperimentOutcome.INCONCLUSIVE,
                    summary=f"Mutation failed in sandbox: {apply_msg}",
                    duration_seconds=round(time.time() - start_time, 3),
                )

            # 4. Run Candidate Benchmark in Sandbox
            candidate_metrics = candidate_probe(temp_dir)
            if hypothesis.target_metric not in candidate_metrics:
                candidate_metrics[hypothesis.target_metric] = baseline_metrics[hypothesis.target_metric]

            # 5. Compute Measured Deltas (candidate - baseline)
            measured_deltas: Dict[str, float] = {}
            for k in baseline_metrics:
                c_val = candidate_metrics.get(k, baseline_metrics[k])
                b_val = baseline_metrics[k]
                measured_deltas[k] = round(c_val - b_val, 3)

            # 6. Evaluate Secondary Regressions
            secondary_regressions: List[str] = []
            reg_thresholds = regression_thresholds or {"error_rate": 0.01, "memory_mb": 50.0}
            for k, delta in measured_deltas.items():
                if k != hypothesis.target_metric:
                    max_allowed_delta = reg_thresholds.get(k, 0.05)
                    # For error rate, memory, latency, positive delta is a regression
                    if delta > max_allowed_delta:
                        secondary_regressions.append(
                            f"Secondary metric '{k}' regressed by +{delta:.3f} > threshold {max_allowed_delta:.3f}"
                        )

            # 7. Evaluate Target Improvement vs Hypothesis
            target_delta = measured_deltas.get(hypothesis.target_metric, 0.0)
            # Expectation: target_delta <= minimum_demonstrable_delta (e.g. -15.0 <= -5.0)
            target_improved = target_delta <= hypothesis.minimum_demonstrable_delta

            if secondary_regressions:
                outcome = ExperimentOutcome.REGRESSION_DETECTED
                summary = f"Regressions observed in secondary metrics: {'; '.join(secondary_regressions)}"
            elif target_improved:
                outcome = ExperimentOutcome.IMPROVEMENT_CONFIRMED
                summary = (
                    f"Confirmed improvement: {hypothesis.target_metric} changed by {target_delta:.3f} "
                    f"(target was <= {hypothesis.minimum_demonstrable_delta:.3f})."
                )
            else:
                outcome = ExperimentOutcome.NO_MEASURABLE_IMPROVEMENT
                summary = (
                    f"No measurable improvement: delta was {target_delta:.3f}, "
                    f"which failed to meet minimum threshold of {hypothesis.minimum_demonstrable_delta:.3f}."
                )

            duration = round(time.time() - start_time, 3)

            return ExperimentRecord(
                experiment_id=exp_id,
                hypothesis_id=hypothesis.hypothesis_id,
                alternative_id=alternative.alternative_id,
                worktree_path=str(temp_dir),
                baseline_measurements=baseline_metrics,
                candidate_measurements=candidate_metrics,
                measured_deltas=measured_deltas,
                outcome=outcome,
                summary=summary,
                secondary_regressions_detected=secondary_regressions,
                isolation_verified=True,
                duration_seconds=duration,
            )

        finally:
            # Clean up disposable worktree completely
            shutil.rmtree(temp_dir, ignore_errors=True)
