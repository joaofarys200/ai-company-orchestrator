"""
Phase 72 — Deterministic Anomaly Detection
Multi-detector anomaly engine with strict tri-state outputs (NORMAL, ANOMALOUS, UNKNOWN).
UNKNOWN is never auto-promoted to NORMAL or ANOMALOUS.
"""

from __future__ import annotations

import math
import time
import uuid
from typing import Any, Dict, List, Optional

from .models import (
    AnomalySignal,
    AnomalyStatus,
    Baseline,
    BaselineStatus,
    ReliabilityObservation,
)


class AnomalyDetector:
    """Deterministic anomaly detector across 10 signal patterns."""

    def __init__(
        self,
        spike_sigma_multiplier: float = 3.0,
        drift_sigma_multiplier: float = 2.0,
        error_burst_threshold: float = 0.05,
        restart_rate_threshold: float = 2.0,
        latency_multiplier: float = 2.5,
    ):
        self.spike_sigma = spike_sigma_multiplier
        self.drift_sigma = drift_sigma_multiplier
        self.error_burst_thresh = error_burst_threshold
        self.restart_rate_thresh = restart_rate_threshold
        self.latency_multiplier = latency_multiplier

    def evaluate(
        self,
        observation: ReliabilityObservation,
        baseline: Optional[Baseline],
    ) -> AnomalySignal:
        evidence_id = f"ev_anom_{uuid.uuid4().hex[:8]}"
        now = observation.timestamp or time.time()

        # Invariant: If baseline is missing or has insufficient evidence, result MUST be UNKNOWN
        if baseline is None or baseline.confidence.status in (
            BaselineStatus.INSUFFICIENT_EVIDENCE,
            BaselineStatus.STALE,
        ):
            return AnomalySignal(
                signal_id=f"sig_{uuid.uuid4().hex[:6]}",
                detector="baseline_confidence_guard",
                service=observation.service,
                metric=observation.metric,
                observed_value=observation.value,
                baseline_value=0.0,
                deviation=0.0,
                status=AnomalyStatus.UNKNOWN,
                threshold=0.0,
                evidence_id=evidence_id,
                timestamp=now,
            )

        metric = observation.metric.lower()
        val = observation.value
        base_mean = baseline.rolling_mean
        std_dev = baseline.std_dev

        # 1. Error burst detector
        if metric in ("error_rate", "errors", "http_5xx"):
            threshold = max(self.error_burst_thresh, base_mean + 2.0 * std_dev)
            dev = val - base_mean
            status = AnomalyStatus.ANOMALOUS if val >= threshold else AnomalyStatus.NORMAL
            return AnomalySignal(
                signal_id=f"sig_err_{uuid.uuid4().hex[:6]}",
                detector="error_burst_detector",
                service=observation.service,
                metric=metric,
                observed_value=val,
                baseline_value=base_mean,
                deviation=dev,
                status=status,
                threshold=threshold,
                evidence_id=evidence_id,
                timestamp=now,
            )

        # 2. Restart acceleration detector
        if metric in ("restarts", "restart_count"):
            threshold = max(self.restart_rate_thresh, base_mean + 2.0 * max(1.0, std_dev))
            dev = val - base_mean
            status = AnomalyStatus.ANOMALOUS if val >= threshold else AnomalyStatus.NORMAL
            return AnomalySignal(
                signal_id=f"sig_rst_{uuid.uuid4().hex[:6]}",
                detector="restart_acceleration_detector",
                service=observation.service,
                metric=metric,
                observed_value=val,
                baseline_value=base_mean,
                deviation=dev,
                status=status,
                threshold=threshold,
                evidence_id=evidence_id,
                timestamp=now,
            )

        # 3. Latency degradation detector
        if metric in ("latency", "latency_ms", "dependency_latency"):
            effective_std = std_dev if std_dev > 1e-4 else (base_mean * 0.2 if base_mean > 0 else 10.0)
            threshold = max(baseline.p95, base_mean + self.latency_multiplier * effective_std)
            dev = val - base_mean
            status = AnomalyStatus.ANOMALOUS if val >= threshold else AnomalyStatus.NORMAL
            return AnomalySignal(
                signal_id=f"sig_lat_{uuid.uuid4().hex[:6]}",
                detector="latency_degradation_detector",
                service=observation.service,
                metric=metric,
                observed_value=val,
                baseline_value=base_mean,
                deviation=dev,
                status=status,
                threshold=threshold,
                evidence_id=evidence_id,
                timestamp=now,
            )

        # 4. Resource pressure (CPU / Memory)
        if metric in ("cpu", "memory"):
            # If absolute value is extreme or exceeds baseline by 3 sigma
            effective_std = max(5.0, std_dev)
            threshold = min(95.0, base_mean + 3.0 * effective_std)
            dev = val - base_mean
            status = AnomalyStatus.ANOMALOUS if val >= threshold else AnomalyStatus.NORMAL
            return AnomalySignal(
                signal_id=f"sig_res_{uuid.uuid4().hex[:6]}",
                detector="resource_pressure_detector",
                service=observation.service,
                metric=metric,
                observed_value=val,
                baseline_value=base_mean,
                deviation=dev,
                status=status,
                threshold=threshold,
                evidence_id=evidence_id,
                timestamp=now,
            )

        # 5. Generic statistical sudden spike / drop detector
        effective_std = std_dev if std_dev > 1e-4 else max(0.01, abs(base_mean) * 0.1)
        upper_threshold = base_mean + (self.spike_sigma * effective_std)
        lower_threshold = base_mean - (self.spike_sigma * effective_std)
        dev = abs(val - base_mean)

        if val > upper_threshold:
            status = AnomalyStatus.ANOMALOUS
            thresh = upper_threshold
            det_name = "sudden_spike_detector"
        elif val < lower_threshold and lower_threshold > 0:
            status = AnomalyStatus.ANOMALOUS
            thresh = lower_threshold
            det_name = "sudden_drop_detector"
        else:
            status = AnomalyStatus.NORMAL
            thresh = upper_threshold
            det_name = "statistical_norm_detector"

        return AnomalySignal(
            signal_id=f"sig_gen_{uuid.uuid4().hex[:6]}",
            detector=det_name,
            service=observation.service,
            metric=metric,
            observed_value=val,
            baseline_value=base_mean,
            deviation=dev,
            status=status,
            threshold=thresh,
            evidence_id=evidence_id,
            timestamp=now,
        )

    def detect_sustained_drift(
        self,
        observations: List[ReliabilityObservation],
        baseline: Optional[Baseline],
        consecutive_points: int = 5,
    ) -> AnomalySignal:
        evidence_id = f"ev_drift_{uuid.uuid4().hex[:8]}"
        now = time.time()
        if not observations or baseline is None or len(observations) < consecutive_points:
            return AnomalySignal(
                signal_id=f"sig_drift_{uuid.uuid4().hex[:6]}",
                detector="sustained_drift_detector",
                service=observations[0].service if observations else "unknown",
                metric=observations[0].metric if observations else "unknown",
                observed_value=0.0,
                baseline_value=0.0,
                deviation=0.0,
                status=AnomalyStatus.UNKNOWN,
                threshold=0.0,
                evidence_id=evidence_id,
                timestamp=now,
            )

        recent = observations[-consecutive_points:]
        base_mean = baseline.rolling_mean
        std_dev = max(1e-4, baseline.std_dev)
        upper = base_mean + self.drift_sigma * std_dev
        lower = base_mean - self.drift_sigma * std_dev

        all_above = all(o.value > upper for o in recent)
        all_below = all(o.value < lower for o in recent)

        if all_above or all_below:
            status = AnomalyStatus.ANOMALOUS
            thresh = upper if all_above else lower
            dev = abs(recent[-1].value - base_mean)
        else:
            status = AnomalyStatus.NORMAL
            thresh = upper
            dev = abs(recent[-1].value - base_mean)

        return AnomalySignal(
            signal_id=f"sig_drift_{uuid.uuid4().hex[:6]}",
            detector="sustained_drift_detector",
            service=recent[0].service,
            metric=recent[0].metric,
            observed_value=recent[-1].value,
            baseline_value=base_mean,
            deviation=dev,
            status=status,
            threshold=thresh,
            evidence_id=evidence_id,
            timestamp=now,
        )
