from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MetricSample:
    node_id: str
    metric_name: str
    value: float
    timestamp: float


@dataclass(frozen=True)
class AnomalyAlert:
    node_id: str
    metric_name: str
    value: float
    mean: float
    std_dev: float
    z_score: float
    severity: str  # WARNING, CRITICAL
    timestamp: float


class SlidingWindowAnomalyDetector:
    """Sliding-Window Z-Score & Moving Average Anomaly Detector."""

    def __init__(self, window_size: int = 30, z_threshold_warning: float = 2.0, z_threshold_critical: float = 3.0):
        self.window_size = window_size
        self.z_threshold_warning = z_threshold_warning
        self.z_threshold_critical = z_threshold_critical
        self._windows: dict[str, deque[float]] = {}

    def process_sample(self, sample: MetricSample) -> AnomalyAlert | None:
        """Ingests a metric sample, updates window, and returns an AnomalyAlert if z-score exceeds threshold."""
        key = f"{sample.node_id}:{sample.metric_name}"
        if key not in self._windows:
            self._windows[key] = deque(maxlen=self.window_size)

        window = self._windows[key]

        # Need at least 5 samples to compute valid z-score
        if len(window) < 5:
            window.append(sample.value)
            return None

        # Compute mean and standard deviation
        mean = sum(window) / len(window)
        variance = sum((x - mean) ** 2 for x in window) / len(window)
        std_dev = max(math.sqrt(variance), 0.1)

        window.append(sample.value)

        z_score = (sample.value - mean) / std_dev

        if abs(z_score) >= self.z_threshold_critical:
            severity = "CRITICAL"
        elif abs(z_score) >= self.z_threshold_warning:
            severity = "WARNING"
        else:
            return None

        return AnomalyAlert(
            node_id=sample.node_id,
            metric_name=sample.metric_name,
            value=sample.value,
            mean=round(mean, 2),
            std_dev=round(std_dev, 2),
            z_score=round(z_score, 2),
            severity=severity,
            timestamp=sample.timestamp,
        )


__all__ = ["MetricSample", "AnomalyAlert", "SlidingWindowAnomalyDetector"]
