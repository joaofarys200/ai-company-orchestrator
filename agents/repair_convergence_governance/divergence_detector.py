"""
JARVIS OS — Phase 56: Divergence Detector
Calculates transparent 5-component DivergenceScore and detects failure cascades.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from agents.repair_convergence_governance.models import (
    DivergenceReport,
    DivergenceScore,
    DivergenceType,
    RepairStepSnapshot,
)


class DivergenceDetector:
    """Calculates explicit 5-factor divergence score and halts escalating failure cascades."""

    def __init__(
        self,
        divergence_threshold: float = 0.85,
        max_allowed_regressions: int = 2,
        failure_spike_threshold: int = 3,
    ):
        self.divergence_threshold = divergence_threshold
        self.max_allowed_regressions = max_allowed_regressions
        self.failure_spike_threshold = failure_spike_threshold

    def calculate_divergence_score(
        self,
        history: List[RepairStepSnapshot],
        rollbacks_count: int = 0,
    ) -> DivergenceScore:
        """Calculates decomposed DivergenceScore across the 5 canonical dimensions."""
        if len(history) < 2:
            score = DivergenceScore()
            score.compute_total(self.divergence_threshold)
            return score

        initial = history[0]
        curr = history[-1]

        init_fails = max(1, len(initial.active_failures))
        curr_fails = len(curr.active_failures)

        # 1. Failure Growth
        fail_delta = curr_fails - len(initial.active_failures)
        failure_growth = max(0.0, float(fail_delta) / float(init_fails))

        # 2. Risk Growth
        init_risk = max(0.05, initial.risk_score)
        risk_delta = curr.risk_score - initial.risk_score
        risk_growth = max(0.0, risk_delta / init_risk)

        # 3. Coverage Drop
        coverage_drop = max(0.0, initial.behavioral_proof_coverage - curr.behavioral_proof_coverage)

        # 4. Regression Growth
        regressed = [f for f in curr.active_failures if f not in initial.active_failures]
        regression_growth = float(len(regressed)) / float(init_fails)

        # 5. Rollback Rate
        total_steps = max(1, len(history) - 1)
        rollback_rate = float(rollbacks_count) / float(total_steps)

        score = DivergenceScore(
            risk_growth=round(risk_growth, 4),
            failure_growth=round(failure_growth, 4),
            coverage_drop=round(coverage_drop, 4),
            regression_growth=round(regression_growth, 4),
            rollback_rate=round(rollback_rate, 4),
        )
        score.compute_total(self.divergence_threshold)

        reasons = []
        if fail_delta >= self.failure_spike_threshold:
            reasons.append(f"Failure count grew by {fail_delta} (from {len(initial.active_failures)} to {curr_fails})")
        if len(regressed) > self.max_allowed_regressions:
            reasons.append(f"Regressions ({len(regressed)}) exceeded tolerance ({self.max_allowed_regressions})")
        if risk_growth > 0.5:
            reasons.append(f"Risk increased significantly by {risk_growth * 100.0:.1f}%")
        if coverage_drop > 0.15:
            reasons.append(f"Behavioral proof coverage dropped by {coverage_drop * 100.0:.1f}%")
        if score.is_diverging:
            reasons.append(f"Total DivergenceScore {score.total_score:.3f} >= threshold {self.divergence_threshold:.3f}")

        score.reasons = reasons
        if reasons:
            score.is_diverging = True

        return score

    def evaluate_divergence(
        self,
        history: List[RepairStepSnapshot],
        rollbacks_count: int = 0,
    ) -> DivergenceReport:
        """Evaluates history and produces detailed DivergenceReport."""
        score = self.calculate_divergence_score(history, rollbacks_count)

        if not history:
            return DivergenceReport(diverging=False, explanation="No history.")

        initial = history[0]
        curr = history[-1]
        regressed = [f for f in curr.active_failures if f not in initial.active_failures]
        all_files = set()
        for s in history:
            all_files.update(s.modified_files)

        div_type = None
        if score.is_diverging:
            if score.failure_growth > 0.5:
                div_type = DivergenceType.FAILURE_COUNT_EXPLOSION
            elif score.regression_growth > 0.5:
                div_type = DivergenceType.REGRESSION_CASCADE
            elif score.risk_growth > 0.5:
                div_type = DivergenceType.RISK_SPIKE
            else:
                div_type = DivergenceType.BLAST_RADIUS_EXPANSION

        explanation = "; ".join(score.reasons) if score.reasons else "Trajectory stable or converging."

        return DivergenceReport(
            diverging=score.is_diverging,
            divergence_type=div_type,
            failure_count_trend=[len(s.active_failures) for s in history],
            divergence_velocity=round(score.total_score, 3),
            regressed_failures=regressed,
            blast_radius_files=sorted(list(all_files)),
            explanation=explanation,
        )
