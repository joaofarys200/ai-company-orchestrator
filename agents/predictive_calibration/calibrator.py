"""
JARVIS OS — Phase 76: Autonomous Engineering Learning & Predictive Calibration
Module: calibrator.py
Persistent calibration engine: robust parameter derivation, uncertainty intervals,
and deterministic calibration versions.
"""

from __future__ import annotations

import math
import time
import uuid
from typing import Dict, List, Optional, Tuple

from .error_analyzer import PredictionErrorAnalyzer
from .models import (
    CalibrationParameters,
    CalibrationState,
    CalibrationVersion,
    EstimateResult,
    InsufficientSamplesError,
    PredictionOutcomePair,
    PredictionType,
)


class PredictiveCalibrator:
    """
    Fits and manages versioned calibration models.
    Applies empirical bias-scaling corrections and prediction intervals to raw baseline forecasts.
    """

    def __init__(self, min_samples: int = 5):
        self.min_samples = min_samples

    def fit_calibration_version(
        self,
        version_id: str,
        prediction_type: PredictionType,
        target_metric: str,
        training_pairs: List[PredictionOutcomePair],
        description: str = "",
        parent_version: Optional[str] = None,
    ) -> CalibrationVersion:
        """
        Fit an affine/robust calibration model from verified historical training pairs.
        Enforces minimum sample size threshold.
        """
        if len(training_pairs) < self.min_samples:
            raise InsufficientSamplesError(
                f"Cannot fit calibration for '{target_metric}': {len(training_pairs)} samples "
                f"provided, but minimum {self.min_samples} required."
            )

        # 1. Separate outliers using IQR
        clean_pairs, outliers = PredictionErrorAnalyzer.filter_outliers_iqr(training_pairs)
        if len(clean_pairs) < max(3, int(0.6 * self.min_samples)):
            clean_pairs = training_pairs  # Fallback to all pairs if too aggressive

        # 2. Derive robust bias offset: median of (actual - predicted)
        diffs = [p.outcome.actual_value - p.prediction.predicted_value for p in clean_pairs if p.outcome]
        diffs.sort()
        mid = len(diffs) // 2
        offset_beta = diffs[mid] if len(diffs) % 2 != 0 else (diffs[mid - 1] + diffs[mid]) / 2.0

        # 3. Derive scaling factor alpha
        preds = [p.prediction.predicted_value for p in clean_pairs]
        acts = [p.outcome.actual_value for p in clean_pairs if p.outcome]
        mean_p = sum(preds) / len(preds)
        mean_a = sum(acts) / len(acts)

        var_p = sum((p - mean_p) ** 2 for p in preds)
        cov_pa = sum((preds[i] - mean_p) * (acts[i] - mean_a) for i in range(len(preds)))

        scale_alpha = 1.0
        if var_p > 1e-6:
            raw_alpha = cov_pa / var_p
            # Clip scale_alpha to [0.5, 2.0] to prevent unstable over-correction
            scale_alpha = max(0.5, min(2.0, raw_alpha))

        # 4. Derive residual variance sigma
        residuals = []
        for p in clean_pairs:
            calibrated_p = scale_alpha * p.prediction.predicted_value + offset_beta
            residuals.append((p.outcome.actual_value - calibrated_p) ** 2)
        variance_sigma = math.sqrt(sum(residuals) / max(1, len(residuals)))

        params = CalibrationParameters(
            scale_alpha=round(scale_alpha, 4),
            offset_beta=round(offset_beta, 4),
            variance_sigma=round(variance_sigma, 4),
            sample_count=len(training_pairs),
            min_samples=self.min_samples,
        )

        train_metrics = PredictionErrorAnalyzer.calculate_metrics(training_pairs)

        return CalibrationVersion(
            version_id=version_id,
            prediction_type=prediction_type,
            target_metric=target_metric,
            state=CalibrationState.EXPERIMENTAL,
            parameters=params,
            train_metrics=train_metrics,
            holdout_metrics=None,
            parent_version=parent_version,
            created_at=time.time(),
            description=description or f"Fitted from {len(training_pairs)} observations ({len(outliers)} outliers isolated).",
        )

    def calibrate(
        self,
        baseline_value: float,
        calibration: Optional[CalibrationVersion] = None,
    ) -> EstimateResult:
        """
        Apply calibration parameters to produce a calibrated estimate and prediction interval.
        If calibration is missing, suspended, or unpromoted, falls back safely to baseline.
        """
        if not calibration or calibration.state not in (CalibrationState.PROMOTED, CalibrationState.SHADOW):
            # Safe Fallback to baseline
            return EstimateResult(
                baseline_value=baseline_value,
                calibrated_value=baseline_value,
                uncertainty_low=round(baseline_value * 0.8, 2),
                uncertainty_high=round(baseline_value * 1.2, 2),
                calibration_version=None,
                is_calibrated=False,
                explanation="Uncalibrated baseline estimate (no active calibration version).",
            )

        params = calibration.parameters
        calibrated = params.scale_alpha * baseline_value + params.offset_beta

        # Domain boundary clipping
        if calibration.prediction_type in (
            PredictionType.PROBABILITY_FAILURE,
            PredictionType.PROBABILITY_REGRESSION,
        ):
            calibrated = max(0.0, min(1.0, calibrated))
        elif calibration.prediction_type in (
            PredictionType.CONTINUOUS_EFFORT,
            PredictionType.CONTINUOUS_DURATION,
            PredictionType.CONTINUOUS_COST,
        ):
            calibrated = max(0.1, calibrated)

        # 95% prediction interval (+/- 1.96 * sigma)
        margin = 1.96 * params.variance_sigma
        low = max(0.0, calibrated - margin)
        high = calibrated + margin

        return EstimateResult(
            baseline_value=round(baseline_value, 2),
            calibrated_value=round(calibrated, 2),
            uncertainty_low=round(low, 2),
            uncertainty_high=round(high, 2),
            calibration_version=calibration.version_id,
            is_calibrated=True,
            explanation=(
                f"Calibrated via {calibration.version_id} (scale={params.scale_alpha:.2f}, "
                f"offset={params.offset_beta:+.2f}, sigma={params.variance_sigma:.2f})."
            ),
        )
