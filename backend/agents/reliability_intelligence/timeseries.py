"""
Phase 72 — Time Series Normalization and Sliding Window Management
Normalizes observations, aggregates sliding windows, and guarantees provenance.
"""

from __future__ import annotations

import collections
import time
from typing import Any, Dict, List, Optional

from .models import (
    MetricType,
    ObservationSourceType,
    ReliabilityObservation,
    ReliabilityWindow,
)


class TimeSeriesBuffer:
    """Maintains sliding-window time series per service and metric."""

    def __init__(self, max_samples_per_series: int = 10000):
        self.max_samples = max_samples_per_series
        # (service, metric) -> deque of ReliabilityObservation
        self._buffers: Dict[tuple[str, str], collections.deque[ReliabilityObservation]] = {}

    def ingest(self, observation: ReliabilityObservation) -> None:
        key = (observation.service, observation.metric)
        if key not in self._buffers:
            self._buffers[key] = collections.deque(maxlen=self.max_samples)
        self._buffers[key].append(observation)

    def get_window(
        self,
        service: str,
        metric: str,
        window_seconds: float = 300.0,
        observation_type: Optional[ObservationSourceType] = None,
    ) -> ReliabilityWindow:
        key = (service, metric)
        if key not in self._buffers:
            return ReliabilityWindow(
                service=service,
                metric=metric,
                observations=[],
                start_time=0.0,
                end_time=0.0,
                sample_count=0,
                window_seconds=window_seconds,
            )

        now = time.time()
        cutoff = now - window_seconds
        all_obs = list(self._buffers[key])

        # Filter by window time and optionally by observation type
        filtered = [
            obs for obs in all_obs
            if obs.timestamp >= cutoff and (observation_type is None or obs.observation_type == observation_type)
        ]

        start_t = filtered[0].timestamp if filtered else 0.0
        end_t = filtered[-1].timestamp if filtered else 0.0

        return ReliabilityWindow(
            service=service,
            metric=metric,
            observations=filtered,
            start_time=start_t,
            end_time=end_t,
            sample_count=len(filtered),
            window_seconds=window_seconds,
        )

    def get_recent_values(self, service: str, metric: str, count: int = 50) -> List[float]:
        key = (service, metric)
        if key not in self._buffers:
            return []
        items = list(self._buffers[key])
        return [o.value for o in items[-count:]]

    def clear(self) -> None:
        self._buffers.clear()


class TimeSeriesNormalizer:
    """Normalizes raw input telemetry into standard ReliabilityObservation models."""

    @staticmethod
    def normalize(payload: Dict[str, Any]) -> ReliabilityObservation:
        ts = float(payload.get("timestamp", time.time()))
        service = str(payload.get("service", payload.get("service_id", "default_service"))).strip()
        metric = str(payload.get("metric", "latency")).strip().lower()
        val = float(payload.get("value", 0.0))
        source = str(payload.get("source", "collector")).strip()

        obs_type_str = str(payload.get("observation_type", "REAL_RUNTIME")).upper()
        try:
            obs_type = ObservationSourceType(obs_type_str)
        except ValueError:
            obs_type = ObservationSourceType.REAL_RUNTIME

        env = str(payload.get("environment", "local")).strip()
        prov = str(payload.get("provenance", "collector")).strip()
        proc_id = payload.get("process_id")
        tags = payload.get("tags", {})
        if not isinstance(tags, dict):
            tags = {}

        return ReliabilityObservation(
            timestamp=ts,
            service=service,
            metric=metric,
            value=val,
            source=source,
            observation_type=obs_type,
            environment=env,
            provenance=prov,
            process_id=proc_id,
            tags=tags,
        )
