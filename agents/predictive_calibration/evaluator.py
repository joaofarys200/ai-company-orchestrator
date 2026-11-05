"""
JARVIS OS — Phase 76: Autonomous Engineering Learning & Predictive Calibration
Module: evaluator.py
Leakage-resistant chronological holdout evaluation and promotion governance.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

from .error_analyzer import PredictionErrorAnalyzer
from .models import (
    CalibrationPromotionError,
    CalibrationState,
    CalibrationVersion,
    DataLeakageError,
    ErrorMetrics,
    PredictionOutcomePair,
    PredictionRecord,
)


class HoldoutEvaluator:
    """
    Validates candidate calibrations against held-out chronological test sets,
    preventing temporal leakage and ensuring empirical accuracy improvement before promotion.
    """

    def __init__(self, train_split_ratio: float = 0.70):
        self.train_split_ratio = train_split_ratio

    def split_chronological(
        self,
        pairs: List[PredictionOutcomePair],
    ) -> Tuple[List[PredictionOutcomePair], List[PredictionOutcomePair]]:
        """
        Split observations strictly by chronological timestamp into train and holdout sets.
        Validates that no future observations leak into the training set.
        """
        if len(pairs) < 4:
            raise DataLeakageError("At least 4 paired observations are required for a chronological split.")

        sorted_pairs = sorted(pairs, key=lambda p: p.prediction.timestamp)
        split_idx = int(len(sorted_pairs) * self.train_split_ratio)
        if split_idx == len(sorted_pairs):
            split_idx = len(sorted_pairs) - 1

        train_set = sorted_pairs[:split_idx]
        holdout_set = sorted_pairs[split_idx:]

        # Invariant: No temporal leakage
        max_train_ts = max(p.prediction.timestamp for p in train_set)
        min_holdout_ts = min(p.prediction.timestamp for p in holdout_set)
        if max_train_ts > min_holdout_ts:
            raise DataLeakageError(
                f"Temporal leakage detected: max train timestamp ({max_train_ts}) "
                f"> min holdout timestamp ({min_holdout_ts})."
            )

        return train_set, holdout_set

    def evaluate_and_promote(
        self,
        calibration: CalibrationVersion,
        holdout_pairs: List[PredictionOutcomePair],
        min_mae_improvement_pct: float = 5.0,
    ) -> Tuple[bool, ErrorMetrics, ErrorMetrics, str]:
        """
        Compares original baseline predictions vs calibrated predictions on the held-out test set.
        Enforces predefined promotion criteria:
        1. Holdout MAE must improve by at least min_mae_improvement_pct.
        2. Holdout RMSE must not worsen significantly (<= 1.05x baseline).
        3. Absolute directional bias must decrease.
        """
        if not holdout_pairs:
            return False, ErrorMetrics(0, 0, 0, 0, None, None, 0, 0, 0), ErrorMetrics(0, 0, 0, 0, None, None, 0, 0, 0), "Empty holdout set"

        # 1. Baseline metrics on holdout
        baseline_metrics = PredictionErrorAnalyzer.calculate_metrics(holdout_pairs)

        # 2. Simulate calibrated predictions on holdout
        calibrated_pairs: List[PredictionOutcomePair] = []
        for p in holdout_pairs:
            raw_pred = p.prediction.predicted_value
            cal_val = calibration.parameters.scale_alpha * raw_pred + calibration.parameters.offset_beta
            # Create synthetic pair for analysis
            cal_pred = PredictionRecord(
                prediction_id=f"eval_{p.prediction.prediction_id}",
                operation_id=p.prediction.operation_id,
                prediction_type=p.prediction.prediction_type,
                target_metric=p.prediction.target_metric,
                predicted_value=cal_val,
                unit=p.prediction.unit,
                timestamp=p.prediction.timestamp,
            )
            sim_pair = PredictionOutcomePair(prediction=cal_pred, outcome=p.outcome)
            sim_pair.calculate_errors()
            calibrated_pairs.append(sim_pair)

        calibrated_metrics = PredictionErrorAnalyzer.calculate_metrics(calibrated_pairs)
        calibration.holdout_metrics = calibrated_metrics

        # 3. Check Predefined Promotion Criteria
        mae_improved = calibrated_metrics.mean_absolute_error < baseline_metrics.mean_absolute_error
        mae_imp_pct = 0.0
        if baseline_metrics.mean_absolute_error > 1e-6:
            mae_imp_pct = (
                (baseline_metrics.mean_absolute_error - calibrated_metrics.mean_absolute_error)
                / baseline_metrics.mean_absolute_error
            ) * 100.0

        rmse_acceptable = calibrated_metrics.root_mean_squared_error <= (baseline_metrics.root_mean_squared_error * 1.05 + 1e-6)
        bias_improved = abs(calibrated_metrics.signed_bias) <= abs(baseline_metrics.signed_bias) + 1e-4

        meets_criteria = mae_improved and (mae_imp_pct >= min_mae_improvement_pct) and rmse_acceptable and bias_improved

        if meets_criteria:
            calibration.state = CalibrationState.PROMOTED
            calibration.promoted_at = time.time()
            reason = (
                f"PROMOTED: MAE improved by {mae_imp_pct:.1f}% ({baseline_metrics.mean_absolute_error:.2f} -> "
                f"{calibrated_metrics.mean_absolute_error:.2f}), Bias reduced from {baseline_metrics.signed_bias:+.2f} "
                f"to {calibrated_metrics.signed_bias:+.2f}."
            )
            return True, baseline_metrics, calibrated_metrics, reason
        else:
            calibration.state = CalibrationState.EXPERIMENTAL
            reasons = []
            if not mae_improved:
                reasons.append(f"MAE did not improve ({baseline_metrics.mean_absolute_error:.2f} vs {calibrated_metrics.mean_absolute_error:.2f})")
            elif mae_imp_pct < min_mae_improvement_pct:
                reasons.append(f"MAE improvement ({mae_imp_pct:.1f}%) below required threshold ({min_mae_improvement_pct}%)")
            if not rmse_acceptable:
                reasons.append("RMSE degraded beyond tolerance")
            if not bias_improved:
                reasons.append("Signed bias increased")
            reason = f"PROMOTION_REJECTED: {'; '.join(reasons)}"
            return False, baseline_metrics, calibrated_metrics, reason
