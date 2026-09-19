"""
JARVIS OS — Phase 69: Autonomous Quality Debt Remediation
Quality comparison engine.
Compares BEFORE vs AFTER across all 9 quality dimensions.
Classifies outcome: REAL_IMPROVEMENT, NO_MEASURABLE_CHANGE, DEGRADATION, UNCERTAIN.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class QualityComparisonOutcome(str, Enum):
    REAL_IMPROVEMENT = "REAL_IMPROVEMENT"
    NO_MEASURABLE_CHANGE = "NO_MEASURABLE_CHANGE"
    DEGRADATION = "DEGRADATION"
    UNCERTAIN = "UNCERTAIN"


@dataclass
class QualityComparisonReport:
    comparison_id: str
    debt_id: str
    outcome: QualityComparisonOutcome
    improved_dimensions: List[str]
    degraded_dimensions: List[str]
    unchanged_dimensions: List[str]
    dimension_deltas: Dict[str, float]
    summary_text: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "comparison_id": self.comparison_id,
            "debt_id": self.debt_id,
            "outcome": self.outcome.value if isinstance(self.outcome, QualityComparisonOutcome) else str(self.outcome),
            "improved_dimensions": self.improved_dimensions,
            "degraded_dimensions": self.degraded_dimensions,
            "unchanged_dimensions": self.unchanged_dimensions,
            "dimension_deltas": self.dimension_deltas,
            "summary_text": self.summary_text,
        }


class QualityComparisonEngine:
    """
    Remeasures quality across the 9 dimensions and verifies if real engineering improvement occurred.
    """

    DIMENSIONS = [
        "ARCHITECTURE",
        "CODE",
        "TEST",
        "CONTRACT",
        "BEHAVIOR",
        "SECURITY",
        "PERFORMANCE",
        "RELIABILITY",
        "MAINTAINABILITY",
    ]

    def compare_quality(
        self,
        debt_id: str,
        quality_before: Dict[str, float],
        quality_after: Dict[str, float],
        minimum_delta_threshold: float = 0.05,
    ) -> QualityComparisonReport:
        comparison_id = f"cmp_{uuid.uuid4().hex[:8]}"
        improved = []
        degraded = []
        unchanged = []
        deltas: Dict[str, float] = {}

        for dim in self.DIMENSIONS:
            score_b = float(quality_before.get(dim, 0.5))
            score_a = float(quality_after.get(dim, 0.5))
            delta = round(score_a - score_b, 4)
            deltas[dim] = delta

            if delta >= minimum_delta_threshold:
                improved.append(dim)
            elif delta <= -minimum_delta_threshold:
                degraded.append(dim)
            else:
                unchanged.append(dim)

        if degraded:
            outcome = QualityComparisonOutcome.DEGRADATION
            summary = f"Quality degraded in {len(degraded)} dimension(s): {', '.join(degraded)}."
        elif improved:
            outcome = QualityComparisonOutcome.REAL_IMPROVEMENT
            summary = f"Real measurable improvement observed in {len(improved)} dimension(s): {', '.join(improved)}."
        elif len(unchanged) == len(self.DIMENSIONS):
            outcome = QualityComparisonOutcome.NO_MEASURABLE_CHANGE
            summary = "No measurable quality change across all 9 dimensions."
        else:
            outcome = QualityComparisonOutcome.UNCERTAIN
            summary = "Quality remeasurement deltas are inconclusive."

        return QualityComparisonReport(
            comparison_id=comparison_id,
            debt_id=debt_id,
            outcome=outcome,
            improved_dimensions=improved,
            degraded_dimensions=degraded,
            unchanged_dimensions=unchanged,
            dimension_deltas=deltas,
            summary_text=summary,
        )
