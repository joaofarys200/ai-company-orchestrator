"""
Quality Readiness Module
Phase 70 — Autonomous Release Readiness & Production Governance

Integrates Phase 68/69 quality metrics and debt governance. Evaluates
quality dimensions, degradation deltas, and uncertainty bounds.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from .models import BlockerCategory, ReleaseBlocker


class QualityReadinessEvaluator:
    """Evaluates software quality dimensions and debt posture for release candidates."""

    @classmethod
    def evaluate(
        cls,
        quality_snapshot: Dict[str, Any],
        quality_deltas: Optional[Dict[str, float]] = None,
        unresolved_unknown_count: int = 0
    ) -> Dict[str, Any]:
        """
        Evaluates quality dimensions, quality degradation, and uncertainty.
        Rules:
        - CRITICAL_QUALITY_DEGRADATION -> BLOCKED
        - UNRESOLVED_UNKNOWN -> HUMAN_REVIEW
        - ACCEPTED_WITH_DEBT does not imply automatically RELEASE_READY
        """
        deltas = quality_deltas or {}
        overall_score = quality_snapshot.get("overall_quality_score", 1.0)
        dimensions = quality_snapshot.get("dimensions", {})
        uncertainty = quality_snapshot.get("quality_uncertainty", 0.0)

        blockers: List[ReleaseBlocker] = []
        requires_human_review = False
        review_reasons: List[str] = []

        # Check for critical quality degradation across any dimension
        for dim, delta in deltas.items():
            if delta < -0.15:  # Significant drop > 15%
                blockers.append(ReleaseBlocker(
                    blocker_id=f"blocker-qual-degrade-{dim}",
                    category=BlockerCategory.QUALITY_GATE_BLOCKED,
                    description=f"Critical quality degradation detected in dimension '{dim}': delta {delta:.2f}",
                    evidence=f"Dimension '{dim}' dropped by {abs(delta)*100:.1f}%. Baseline threshold violated."
                ))
            elif delta < -0.05:
                requires_human_review = True
                review_reasons.append(f"Moderate quality degradation in '{dim}': {delta:.2f}")

        # Check for overall score drop
        if overall_score < 0.70:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-qual-overall-low",
                category=BlockerCategory.QUALITY_GATE_BLOCKED,
                description=f"Overall quality score ({overall_score:.2f}) falls below release threshold (0.70)",
                evidence=f"Evaluated quality score: {overall_score:.3f}"
            ))

        # Check unresolved unknowns / high uncertainty
        if unresolved_unknown_count > 0 or uncertainty > 0.30:
            requires_human_review = True
            review_reasons.append(
                f"Quality uncertainty bounds elevated ({uncertainty:.2f}) with {unresolved_unknown_count} unresolved unknowns"
            )

        status = "READY"
        if blockers:
            status = "BLOCKED"
        elif requires_human_review:
            status = "HUMAN_REVIEW"
        elif quality_snapshot.get("accepted_with_debt", False):
            status = "READY_WITH_RISK"

        return {
            "status": status,
            "overall_score": overall_score,
            "dimensions": dimensions,
            "uncertainty": uncertainty,
            "deltas": deltas,
            "blockers": blockers,
            "requires_human_review": requires_human_review,
            "review_reasons": review_reasons,
            "accepted_with_debt": quality_snapshot.get("accepted_with_debt", False)
        }
