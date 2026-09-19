"""
JARVIS OS — Phase 68: Quality Dimensions Orchestration
Orchestrates observation and evaluation across all 9 quality dimensions:
ARCHITECTURE, CODE, TEST, CONTRACT, BEHAVIOR, SECURITY, PERFORMANCE, RELIABILITY, MAINTAINABILITY.

Core Principle: QUALITY_SCORE != SINGLE_NUMBER_AUTHORITY.
Never collapse multidimensional observations into a single scalar without preserving
individual dimensional evidence, uncertainty, and scope.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import (
    DimensionEvaluation,
    DimensionStatus,
    ObservationType,
    QualityDimension,
    QualityObservation,
)


class QualityDimensionsOrchestrator:
    """
    Coordinates multi-dimensional quality observations and constructs
    uncompromised, multi-axis dimensional evaluations.
    """

    def __init__(self) -> None:
        self._dimension_evaluators: Dict[QualityDimension, Any] = {}

    def register_evaluator(self, dimension: QualityDimension, evaluator: Any) -> None:
        self._dimension_evaluators[dimension] = evaluator

    def evaluate_all_dimensions(
        self,
        context: Optional[Dict[str, Any]] = None,
        scope: str = "global",
    ) -> Dict[str, DimensionEvaluation]:
        """
        Runs evaluations across all 9 dimensions and returns a dictionary
        mapping dimension names to DimensionEvaluation.
        """
        ctx = context or {}
        results: Dict[str, DimensionEvaluation] = {}

        for dim in QualityDimension:
            evaluator = self._dimension_evaluators.get(dim)
            if evaluator and hasattr(evaluator, "evaluate"):
                evaluation = evaluator.evaluate(ctx, scope=scope)
            else:
                # Default evaluation when specialized evaluator not explicitly plugged
                obs_list = []
                # Check if context provides raw metrics for this dimension
                raw_metrics = ctx.get(dim.value.lower(), {})
                if isinstance(raw_metrics, dict):
                    for k, v in raw_metrics.items():
                        obs_list.append(
                            QualityObservation(
                                dimension=dim,
                                metric_name=k,
                                measured_value=v,
                                evidence={"source": "context_inspection", "key": k},
                                uncertainty=0.1,
                                scope=scope,
                                observation_type=ObservationType.OBSERVED,
                            )
                        )
                evaluation = DimensionEvaluation(
                    dimension=dim,
                    observations=obs_list,
                    evidence=[{"type": "orchestrator_inspection", "dim": dim.value}],
                    uncertainty=0.1 if obs_list else 0.4,
                    scope=scope,
                    status=DimensionStatus.HEALTHY,
                    summary=f"Evaluated {len(obs_list)} metrics for {dim.value}",
                )

            results[dim.value] = evaluation

        return results

    @staticmethod
    def validate_no_single_score_authority(evaluations: Dict[str, DimensionEvaluation]) -> bool:
        """
        Validates that quality is represented as a multi-dimensional structure
        and not compressed into a single authority number.
        """
        if not isinstance(evaluations, dict):
            return False
        # Must retain distinct dimensions
        return len(evaluations) >= len(QualityDimension)
