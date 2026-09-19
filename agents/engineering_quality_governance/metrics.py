"""
JARVIS OS — Phase 68: Quality Metrics Engine
Calculates statistics, dispersion, confidence bounds, moving averages,
evidence efficiency, and hotspot risk weights.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence


class QualityMetricsEngine:
    """
    Mathematical and statistical aggregation utilities for quality governance.
    """

    @staticmethod
    def mean(values: Sequence[float]) -> float:
        if not values:
            return 0.0
        return sum(values) / len(values)

    @staticmethod
    def variance(values: Sequence[float]) -> float:
        if len(values) < 2:
            return 0.0
        m = sum(values) / len(values)
        return sum((x - m) ** 2 for x in values) / (len(values) - 1)

    @staticmethod
    def std_dev(values: Sequence[float]) -> float:
        return math.sqrt(QualityMetricsEngine.variance(values))

    @staticmethod
    def confidence_bounds(values: Sequence[float], confidence: float = 0.95) -> tuple[float, float]:
        if not values:
            return 0.0, 0.0
        m = QualityMetricsEngine.mean(values)
        sd = QualityMetricsEngine.std_dev(values)
        margin = 1.96 * (sd / math.sqrt(len(values))) if len(values) > 1 else sd
        return max(0.0, m - margin), m + margin

    @staticmethod
    def compute_evidence_efficiency(
        useful_assertions: int,
        test_count: int,
        redundancy_count: int,
        mutation_score: float,
        flaky_rate: float,
    ) -> float:
        """
        Computes evidence efficiency ratio:
        Higher when high mutation kill rate and low flakiness are achieved with minimal test redundancy.
        """
        if test_count <= 0:
            return 0.0
        denom = max(1.0, test_count + (redundancy_count * 2.0))
        numerator = useful_assertions * max(0.0, 1.0 - flaky_rate) * max(0.0, mutation_score)
        return float(min(1.0, numerator / denom))

    @staticmethod
    def compute_hotspot_risk_weight(
        failure_count: int,
        regression_count: int,
        debt_count: int,
        review_count: int,
        rollback_count: int,
        flakiness_score: float,
    ) -> float:
        """
        Computes risk weight for a hotspot entity.
        """
        return (
            (regression_count * 4.0)
            + (rollback_count * 3.5)
            + (failure_count * 2.5)
            + (debt_count * 2.0)
            + (review_count * 1.0)
            + (flakiness_score * 5.0)
        )
