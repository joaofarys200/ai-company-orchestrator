"""
JARVIS OS — Phase 74: Autonomous Architectural Evolution & Optimization
Module: hypothesis_engine.py
Constructs structured, falsifiable optimization hypotheses with explicit quantitative targets.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    InsufficientEvidenceError,
    OptimizationHypothesis,
    OptimizationOpportunity,
    OptimizationState,
)


class HypothesisEngine:
    """
    Constructs formal, testable architectural hypotheses from validated opportunities.
    """

    def form_hypothesis(
        self,
        opportunity: OptimizationOpportunity,
        target_metric: Optional[str] = None,
        expected_improvement_pct: float = 0.25,
        min_demonstrable_delta: Optional[float] = None,
    ) -> OptimizationHypothesis:
        """
        Forms a falsifiable hypothesis with explicit acceptance/rejection criteria.
        """
        if not opportunity.baseline_metrics:
            raise InsufficientEvidenceError(
                f"Cannot form hypothesis for opportunity '{opportunity.opportunity_id}': No baseline metrics present."
            )

        # Select target metric (default to first available)
        chosen_metric = target_metric or list(opportunity.baseline_metrics.keys())[0]
        if chosen_metric not in opportunity.baseline_metrics:
            raise InsufficientEvidenceError(
                f"Target metric '{chosen_metric}' not found in baseline metrics."
            )

        baseline_snap = opportunity.baseline_metrics[chosen_metric]
        baseline_val = baseline_snap.value

        # Calculate predicted improvement (negative delta = reduction in latency/coupling)
        predicted_delta = -abs(baseline_val * expected_improvement_pct)
        min_delta = min_demonstrable_delta if min_demonstrable_delta is not None else -abs(baseline_val * 0.05)

        hyp_id = f"hyp_{uuid.uuid4().hex[:8]}"

        falsification_rules = [
            f"Measured delta >= {min_delta:.3f} implies NO_MEASURABLE_IMPROVEMENT.",
            f"Any increase in secondary regression metrics implies REGRESSION_DETECTED.",
            "Any broken contract or security invariant causes immediate rejection.",
        ]

        return OptimizationHypothesis(
            hypothesis_id=hyp_id,
            opportunity_id=opportunity.opportunity_id,
            target_metric=chosen_metric,
            current_baseline_value=baseline_val,
            predicted_improvement_delta=round(predicted_delta, 3),
            minimum_demonstrable_delta=round(min_delta, 3),
            falsification_conditions=falsification_rules,
            confidence=opportunity.confidence_score,
            status=OptimizationState.HYPOTHESIZED,
        )
