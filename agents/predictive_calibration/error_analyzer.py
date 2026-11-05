"""
JARVIS OS — Phase 76: Autonomous Engineering Learning & Predictive Calibration
Module: error_analyzer.py
Statistical evaluation of prediction errors: signed bias, MAE, RMSE, Brier score,
and outlier isolation.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from .models import (
    ErrorMetrics,
    PredictionOutcomePair,
    PredictionType,
)


class PredictionErrorAnalyzer:
    """
    Computes rigorous error analytics across continuous and probabilistic engineering predictions,
    isolating systematic directional bias from random noise.
    """

    @staticmethod
    def calculate_metrics(pairs: List[PredictionOutcomePair]) -> ErrorMetrics:
        """
        Compute statistical error metrics for a list of paired predictions and actuals.
        Handles zero denominators safely and rejects invalid observations.
        """
        valid_pairs = [
            p for p in pairs
            if p.is_eligible_for_calibration and p.signed_error is not None and p.outcome is not None
        ]
        n = len(valid_pairs)
        if n == 0:
            return ErrorMetrics(
                sample_count=0,
                signed_bias=0.0,
                mean_absolute_error=0.0,
                root_mean_squared_error=0.0,
                mean_percentage_error=None,
                brier_score=None,
                overestimation_count=0,
                underestimation_count=0,
                exact_count=0,
            )

        signed_errors = [p.signed_error for p in valid_pairs]
        abs_errors = [p.absolute_error for p in valid_pairs]
        squared_errors = [err ** 2 for err in signed_errors]

        signed_bias = round(sum(signed_errors) / n, 4)
        mae = round(sum(abs_errors) / n, 4)
        rmse = round(math.sqrt(sum(squared_errors) / n), 4)

        # MAPE calculation: strictly safe against zero / near-zero denominators
        mape_values = []
        for p in valid_pairs:
            act = p.outcome.actual_value
            if abs(act) > 1e-6:
                mape_values.append(abs(p.prediction.predicted_value - act) / abs(act))
        mape = round((sum(mape_values) / len(mape_values)) * 100.0, 2) if mape_values else None

        # Brier score calculation for probabilistic predictions
        is_prob = any(
            p.prediction.prediction_type in (
                PredictionType.PROBABILITY_FAILURE,
                PredictionType.PROBABILITY_REGRESSION,
            )
            for p in valid_pairs
        )
        brier_score = None
        if is_prob:
            brier_diffs = []
            for p in valid_pairs:
                prob = p.prediction.predicted_value
                act_binary = 1.0 if p.outcome.actual_value > 0.5 else 0.0
                brier_diffs.append((prob - act_binary) ** 2)
            brier_score = round(sum(brier_diffs) / len(brier_diffs), 4)

        # Directional counts
        over_count = sum(1 for err in signed_errors if err > 1e-6)
        under_count = sum(1 for err in signed_errors if err < -1e-6)
        exact_count = n - over_count - under_count

        return ErrorMetrics(
            sample_count=n,
            signed_bias=signed_bias,
            mean_absolute_error=mae,
            root_mean_squared_error=rmse,
            mean_percentage_error=mape,
            brier_score=brier_score,
            overestimation_count=over_count,
            underestimation_count=under_count,
            exact_count=exact_count,
        )

    @staticmethod
    def identify_systematic_bias(pairs: List[PredictionOutcomePair], threshold: float = 0.1) -> Tuple[bool, str, float]:
        """
        Determines whether predictions exhibit systematic bias.
        Returns: (has_bias, "OVERESTIMATION"|"UNDERESTIMATION"|"NEUTRAL", signed_bias)
        """
        metrics = PredictionErrorAnalyzer.calculate_metrics(pairs)
        if metrics.sample_count < 3:
            return False, "NEUTRAL", 0.0

        if metrics.signed_bias > threshold:
            return True, "OVERESTIMATION", metrics.signed_bias
        elif metrics.signed_bias < -threshold:
            return True, "UNDERESTIMATION", metrics.signed_bias
        return False, "NEUTRAL", metrics.signed_bias

    @staticmethod
    def filter_outliers_iqr(
        pairs: List[PredictionOutcomePair],
    ) -> Tuple[List[PredictionOutcomePair], List[PredictionOutcomePair]]:
        """
        Separates statistical outliers from standard observations using IQR on signed errors.
        Prevents a single catastrophic failure or runaway metric from corrupting calibration parameters.
        Returns: (clean_pairs, outlier_pairs)
        """
        valid_pairs = [p for p in pairs if p.signed_error is not None]
        if len(valid_pairs) < 5:
            return valid_pairs, []

        sorted_by_err = sorted(valid_pairs, key=lambda p: p.signed_error)
        n = len(sorted_by_err)
        q1_idx = int(0.25 * n)
        q3_idx = int(0.75 * n)
        q1 = sorted_by_err[q1_idx].signed_error
        q3 = sorted_by_err[q3_idx].signed_error
        iqr = q3 - q1

        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        clean = []
        outliers = []
        for p in valid_pairs:
            if lower_bound <= p.signed_error <= upper_bound:
                clean.append(p)
            else:
                outliers.append(p)

        return clean, outliers
