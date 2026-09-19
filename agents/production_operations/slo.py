"""
Phase 71 — SLI / SLO Evaluation Engine
Evaluates service level objectives across availability, error rate, latency, restarts, and dependencies.
Guarantees INSUFFICIENT_EVIDENCE is never converted to PASS.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from .models import SLOEvaluation, SLOStatus


@dataclass
class SLODefinition:
    """SLO target specification."""
    metric: str
    target_threshold: float
    comparator: str  # "<=", ">=", "<", ">"
    window_seconds: int
    min_samples: int = 5
    description: str = ""


class SLOEvaluator:
    """
    Evaluates observed runtime metrics against explicit SLO definitions.
    """

    def __init__(self, service_id: str):
        self.service_id = service_id
        self._definitions: Dict[str, SLODefinition] = {}
        self._history: List[SLOEvaluation] = []
        self._configure_default_slos()

    def _configure_default_slos(self) -> None:
        """Sets standard JARVIS production SLOs."""
        self.register_slo(SLODefinition(
            metric="availability",
            target_threshold=0.99,
            comparator=">=",
            window_seconds=300,
            min_samples=3,
            description="Service availability must be >= 99.0%"
        ))
        self.register_slo(SLODefinition(
            metric="error_rate",
            target_threshold=0.01,
            comparator="<=",
            window_seconds=300,
            min_samples=3,
            description="Error rate must be <= 1.0%"
        ))
        self.register_slo(SLODefinition(
            metric="latency_p95_ms",
            target_threshold=150.0,
            comparator="<=",
            window_seconds=300,
            min_samples=3,
            description="p95 latency must be <= 150ms"
        ))
        self.register_slo(SLODefinition(
            metric="restart_rate",
            target_threshold=1.0,
            comparator="<=",
            window_seconds=600,
            min_samples=1,
            description="Process restart count in window must be <= 1"
        ))
        self.register_slo(SLODefinition(
            metric="dependency_health_ratio",
            target_threshold=1.0,
            comparator=">=",
            window_seconds=300,
            min_samples=1,
            description="All critical dependencies must be 100% healthy"
        ))

    def register_slo(self, defn: SLODefinition) -> None:
        self._definitions[defn.metric] = defn

    def evaluate(
        self,
        metric: str,
        observed_samples: List[float],
        sample_count: Optional[int] = None,
    ) -> SLOEvaluation:
        """
        Evaluates a metric against its SLO definition.
        Returns INSUFFICIENT_EVIDENCE if observed samples are below min_samples.
        """
        if metric not in self._definitions:
            defn = SLODefinition(
                metric=metric,
                target_threshold=0.0,
                comparator="<=",
                window_seconds=300,
                min_samples=1,
                description=f"Dynamic SLO for {metric}"
            )
        else:
            defn = self._definitions[metric]

        actual_sample_count = len(observed_samples) if sample_count is None else sample_count

        # Enforce invariant: insufficient samples cannot produce PASS
        if actual_sample_count < defn.min_samples:
            eval_res = SLOEvaluation(
                metric=metric,
                threshold=defn.target_threshold,
                observed_value=float(sum(observed_samples) / len(observed_samples)) if observed_samples else 0.0,
                window_seconds=defn.window_seconds,
                status=SLOStatus.INSUFFICIENT_EVIDENCE,
                service_id=self.service_id,
            )
            self._history.append(eval_res)
            return eval_res

        avg_val = float(sum(observed_samples) / len(observed_samples))

        passed = False
        if defn.comparator == "<=":
            passed = avg_val <= defn.target_threshold
        elif defn.comparator == "<":
            passed = avg_val < defn.target_threshold
        elif defn.comparator == ">=":
            passed = avg_val >= defn.target_threshold
        elif defn.comparator == ">":
            passed = avg_val > defn.target_threshold

        status = SLOStatus.PASS if passed else SLOStatus.BREACH

        eval_res = SLOEvaluation(
            metric=metric,
            threshold=defn.target_threshold,
            observed_value=round(avg_val, 4),
            window_seconds=defn.window_seconds,
            status=status,
            service_id=self.service_id,
        )
        self._history.append(eval_res)
        return eval_res

    def evaluate_batch(self, metrics_data: Dict[str, List[float]]) -> List[SLOEvaluation]:
        """Evaluates multiple metrics."""
        return [self.evaluate(m, vals) for m, vals in metrics_data.items()]

    def get_history(self) -> List[SLOEvaluation]:
        return list(self._history)
