"""
JARVIS OS — Phase 76: Autonomous Engineering Learning & Predictive Calibration
Module: drift_detector.py
Prediction and environmental drift detection, windowed error monitoring, and calibration suspension.
"""

from __future__ import annotations

import time
import uuid
from typing import Dict, List, Optional, Tuple

from .error_analyzer import PredictionErrorAnalyzer
from .models import (
    CalibrationState,
    CalibrationVersion,
    DriftSeverity,
    DriftSignal,
    PredictionOutcomePair,
    PredictionType,
)


class DriftDetector:
    """
    Monitors recent prediction error distributions to detect concept drift, architectural shifts,
    or execution environment divergence, preventing stale calibrations from degrading operations.
    """

    def __init__(
        self,
        window_size: int = 5,
        drift_ratio_threshold: float = 1.30,  # 30% error increase triggers warning
        critical_ratio_threshold: float = 1.60, # 60% error increase suspends calibration
    ):
        self.window_size = window_size
        self.drift_ratio_threshold = drift_ratio_threshold
        self.critical_ratio_threshold = critical_ratio_threshold
        self.drift_signals: List[DriftSignal] = []

    def check_for_drift(
        self,
        calibration: CalibrationVersion,
        recent_pairs: List[PredictionOutcomePair],
    ) -> Optional[DriftSignal]:
        """
        Evaluate sliding window of recent observations against the baseline calibration error.
        If degradation is sustained, suspends the calibration version and returns a DriftSignal.
        """
        if len(recent_pairs) < self.window_size:
            return None

        # Take last window_size observations
        window = recent_pairs[-self.window_size:]
        rolling_metrics = PredictionErrorAnalyzer.calculate_metrics(window)

        # Baseline reference error
        ref_mae = 1.0
        if calibration.holdout_metrics and calibration.holdout_metrics.mean_absolute_error > 0.05:
            ref_mae = calibration.holdout_metrics.mean_absolute_error
        elif calibration.train_metrics and calibration.train_metrics.mean_absolute_error > 0.05:
            ref_mae = calibration.train_metrics.mean_absolute_error

        rolling_mae = rolling_metrics.mean_absolute_error
        drift_ratio = round(rolling_mae / ref_mae, 3)

        if drift_ratio >= self.drift_ratio_threshold:
            severity = (
                DriftSeverity.CRITICAL
                if drift_ratio >= self.critical_ratio_threshold
                else DriftSeverity.MODERATE
            )
            diag = (
                f"Prediction drift detected for '{calibration.target_metric}': rolling MAE {rolling_mae:.2f} "
                f"exceeds reference baseline {ref_mae:.2f} by {((drift_ratio - 1.0) * 100):.1f}%."
            )

            signal = DriftSignal(
                signal_id=f"drift_{uuid.uuid4().hex[:8]}",
                prediction_type=calibration.prediction_type,
                target_metric=calibration.target_metric,
                severity=severity,
                baseline_mae=ref_mae,
                rolling_mae=rolling_mae,
                drift_ratio=drift_ratio,
                sample_count=len(window),
                detected_at=time.time(),
                diagnostic=diag,
            )
            self.drift_signals.append(signal)

            # Automatically suspend calibration if critical drift occurs
            if severity == DriftSeverity.CRITICAL:
                calibration.state = CalibrationState.SUSPENDED

            return signal

        return None
