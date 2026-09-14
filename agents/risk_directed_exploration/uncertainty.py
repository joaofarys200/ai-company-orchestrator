"""
JARVIS OS — Phase 52: Risk-Directed Behavioral Exploration & Adaptive Proof Search
Behavioral Uncertainty Evaluator: Continuous evaluation of epistemic and structural unknowns.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents.risk_directed_exploration.models import BehavioralUncertainty


class UncertaintyEvaluator:
    """
    Evaluates continuous behavioral uncertainty across 11 explicit sources:
    uncertain consumer, insufficient evidence, insufficient coverage,
    unknown variant, unexplored branch, unknown error path, dynamic dispatch,
    concurrency gap, external dependency, historical failure, missing baseline.
    """

    def evaluate_uncertainty(
        self,
        has_uncertain_consumer: bool = False,
        insufficient_evidence: bool = False,
        coverage_pct: float = 0.0,
        coverage_threshold: float = 0.80,
        unknown_variants_count: int = 0,
        unexplored_branches_count: int = 0,
        unknown_error_paths_count: int = 0,
        has_dynamic_dispatch: bool = False,
        unexplored_interleavings_count: int = 0,
        external_dependencies_count: int = 0,
        historical_failures_count: int = 0,
        missing_baseline: bool = False,
    ) -> BehavioralUncertainty:
        """Compute continuous BehavioralUncertainty score."""
        u_consumer = 0.9 if has_uncertain_consumer else 0.0
        u_evidence = 0.85 if insufficient_evidence else 0.0
        u_coverage = max(0.0, (coverage_threshold - coverage_pct) / max(0.01, coverage_threshold))
        u_variant = min(1.0, unknown_variants_count * 0.4)
        u_branch = min(1.0, unexplored_branches_count * 0.25)
        u_error = min(1.0, unknown_error_paths_count * 0.3)
        u_dispatch = 0.6 if has_dynamic_dispatch else 0.0
        u_concurrency = min(1.0, unexplored_interleavings_count * 0.15)
        u_dependency = min(1.0, external_dependencies_count * 0.2)
        u_hist = min(1.0, historical_failures_count * 0.25)
        u_baseline = 0.95 if missing_baseline else 0.0

        uncertainty = BehavioralUncertainty(
            uncertain_consumer=round(u_consumer, 4),
            insufficient_evidence=round(u_evidence, 4),
            insufficient_coverage=round(u_coverage, 4),
            unknown_variant=round(u_variant, 4),
            unexplored_branch=round(u_branch, 4),
            unknown_error_path=round(u_error, 4),
            dynamic_dispatch=round(u_dispatch, 4),
            concurrency_gap=round(u_concurrency, 4),
            external_dependency=round(u_dependency, 4),
            historical_failure=round(u_hist, 4),
            missing_baseline=round(u_baseline, 4),
        )
        uncertainty.compute_score()
        return uncertainty
