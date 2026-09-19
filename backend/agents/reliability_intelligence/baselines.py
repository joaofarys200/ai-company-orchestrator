"""
Phase 72 — Deterministic Baseline Calculation and Confidence Evaluation
Computes rolling statistics, percentiles, and explicit baseline confidence.
"""

from __future__ import annotations

import math
import statistics
import time
from typing import Any, Dict, List, Optional

from .models import (
    Baseline,
    BaselineConfidence,
    BaselineStatus,
    ReliabilityObservation,
    ReliabilityWindow,
)


class BaselineCalculator:
    """Calculates deterministic baselines and confidence from time series windows."""

    def __init__(
        self,
        min_samples: int = 5,
        target_samples: int = 10,
        max_age_seconds: float = 300.0,
    ):
        self.min_samples = min_samples
        self.target_samples = target_samples
        self.max_age_seconds = max_age_seconds
        self._cached_baselines: Dict[tuple[str, str], Baseline] = {}

    def compute(self, window: ReliabilityWindow) -> Baseline:
        service = window.service
        metric = window.metric
        obs = window.observations
        now = time.time()

        if not obs:
            conf = BaselineConfidence(
                sample_count=0,
                window=window.window_seconds,
                freshness=0.0,
                stability=0.0,
                status=BaselineStatus.INSUFFICIENT_EVIDENCE,
            )
            b = Baseline(
                service=service,
                metric=metric,
                rolling_mean=0.0,
                rolling_median=0.0,
                min_val=0.0,
                max_val=0.0,
                std_dev=0.0,
                p90=0.0,
                p95=0.0,
                p99=0.0,
                confidence=conf,
                window_size=0,
                calculated_at=now,
            )
            self._cached_baselines[(service, metric)] = b
            return b

        values = [o.value for o in obs]
        count = len(values)
        latest_ts = max(o.timestamp for o in obs)
        freshness = max(0.0, now - latest_ts)

        # Basic statistics
        mean_val = statistics.mean(values)
        median_val = statistics.median(values)
        min_val = min(values)
        max_val = max(values)
        std_val = statistics.stdev(values) if count > 1 else 0.0

        # Percentiles
        sorted_vals = sorted(values)
        p90 = self._percentile(sorted_vals, 0.90)
        p95 = self._percentile(sorted_vals, 0.95)
        p99 = self._percentile(sorted_vals, 0.99)

        # Stability: 1.0 - (coefficient of variation clamped to [0, 1])
        cv = (std_val / mean_val) if abs(mean_val) > 1e-6 else 0.0
        stability = max(0.0, min(1.0, 1.0 - min(1.0, cv)))

        # Evaluate Confidence Status
        if count < self.min_samples:
            status = BaselineStatus.INSUFFICIENT_EVIDENCE
        elif freshness > self.max_age_seconds:
            status = BaselineStatus.STALE
        elif count < self.target_samples or stability < 0.3:
            status = BaselineStatus.WEAK
        else:
            status = BaselineStatus.VALID

        conf = BaselineConfidence(
            sample_count=count,
            window=window.window_seconds,
            freshness=freshness,
            stability=stability,
            status=status,
        )

        b = Baseline(
            service=service,
            metric=metric,
            rolling_mean=mean_val,
            rolling_median=median_val,
            min_val=min_val,
            max_val=max_val,
            std_dev=std_val,
            p90=p90,
            p95=p95,
            p99=p99,
            confidence=conf,
            window_size=count,
            calculated_at=now,
        )
        self._cached_baselines[(service, metric)] = b
        return b

    def get_cached(self, service: str, metric: str) -> Optional[Baseline]:
        return self._cached_baselines.get((service, metric))

    @staticmethod
    def _percentile(sorted_values: List[float], percent: float) -> float:
        if not sorted_values:
            return 0.0
        k = (len(sorted_values) - 1) * percent
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_values[int(k)]
        d0 = sorted_values[int(f)] * (c - k)
        d1 = sorted_values[int(c)] * (k - f)
        return d0 + d1
