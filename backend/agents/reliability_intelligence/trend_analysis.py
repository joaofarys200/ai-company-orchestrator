"""
Phase 72 — Deterministic Trend Analysis
Measures slope, acceleration, persistence, and confidence across time series windows.
Never declares trend from an isolated observation.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from .models import (
    ReliabilityObservation,
    ReliabilityWindow,
    TrendSignal,
    TrendStatus,
)


class TrendAnalyzer:
    """Analyzes direction, slope, and persistence of metrics over time."""

    def __init__(self, min_samples: int = 4, slope_significance_threshold: float = 0.001):
        self.min_samples = min_samples
        self.slope_threshold = slope_significance_threshold

    def evaluate(self, window: ReliabilityWindow) -> TrendSignal:
        evidence_id = f"ev_trend_{uuid.uuid4().hex[:8]}"
        now = time.time()
        obs = window.observations
        service = window.service
        metric = window.metric.lower()

        # Invariant: Never declare trend with insufficient samples or an isolated observation
        if len(obs) < self.min_samples:
            return TrendSignal(
                signal_id=f"trend_{uuid.uuid4().hex[:6]}",
                service=service,
                metric=metric,
                slope=0.0,
                acceleration=0.0,
                persistence=0.0,
                confidence=0.0,
                status=TrendStatus.UNKNOWN,
                evidence_id=evidence_id,
                timestamp=now,
            )

        # Extract normalized coordinates (x: time in seconds from start, y: metric value)
        t0 = obs[0].timestamp
        x_vals = [o.timestamp - t0 for o in obs]
        y_vals = [o.value for o in obs]
        n = len(x_vals)

        # Linear regression for slope
        mean_x = sum(x_vals) / n
        mean_y = sum(y_vals) / n
        denom = sum((x - mean_x) ** 2 for x in x_vals)
        if denom == 0.0:
            slope = 0.0
        else:
            slope = sum((x_vals[i] - mean_x) * (y_vals[i] - mean_y) for i in range(n)) / denom

        # Calculate acceleration (change in slope between first half and second half)
        mid = n // 2
        slope_first = (y_vals[mid] - y_vals[0]) / max(1.0, (x_vals[mid] - x_vals[0]))
        slope_second = (y_vals[-1] - y_vals[mid]) / max(1.0, (x_vals[-1] - x_vals[mid]))
        acceleration = slope_second - slope_first

        # Persistence: fraction of steps that moved in the same direction as overall slope
        diffs = [y_vals[i] - y_vals[i - 1] for i in range(1, n)]
        if slope > 0:
            matching = sum(1 for d in diffs if d > 0)
        elif slope < 0:
            matching = sum(1 for d in diffs if d < 0)
        else:
            matching = sum(1 for d in diffs if abs(d) <= 1e-6)
        persistence = matching / len(diffs) if diffs else 0.0

        # Confidence: product of sample coverage and persistence
        sample_factor = min(1.0, n / 10.0)
        confidence = round(sample_factor * (0.5 + 0.5 * persistence), 3)

        # Determine Trend Status based on metric semantics
        # Higher is worse: latency, error_rate, restarts, cpu, memory, queue_depth
        # Higher is better: availability
        is_higher_better = metric in ("availability", "uptime", "throughput")

        # Normalize relative slope or absolute rate
        rel_slope = (slope / abs(mean_y)) if abs(mean_y) > 1e-4 else slope
        is_bounded_rate = is_higher_better or metric in ("error_rate", "error_ratio")
        effective_slope = abs(slope) if is_bounded_rate else abs(rel_slope)

        if effective_slope < self.slope_threshold:
            status = TrendStatus.STABLE
        elif (slope > 0 if is_bounded_rate else rel_slope > 0):
            status = TrendStatus.IMPROVING if is_higher_better else TrendStatus.DEGRADING
        else:
            status = TrendStatus.DEGRADING if is_higher_better else TrendStatus.IMPROVING

        return TrendSignal(
            signal_id=f"trend_{uuid.uuid4().hex[:6]}",
            service=service,
            metric=metric,
            slope=round(slope, 5),
            acceleration=round(acceleration, 5),
            persistence=round(persistence, 3),
            confidence=confidence,
            status=status,
            evidence_id=evidence_id,
            timestamp=now,
        )
