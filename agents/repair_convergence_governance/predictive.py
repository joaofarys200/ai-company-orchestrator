"""
JARVIS OS — Phase 56: Predictive Convergence Engine
Predicts Delta P, risk delta, and revealed failures before patch execution; computes predictive calibration.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional, Tuple
from agents.repair_convergence_governance.models import ProgressDelta


class PredictiveConvergenceEngine:
    """Predicts pre-execution patch impact and tracks empirical calibration accuracy."""

    def __init__(self):
        self.prediction_records: List[Dict[str, Any]] = []

    def predict_patch_impact(
        self,
        patch_id: str,
        target_failure: str,
        files_touched: List[str],
        current_failure_count: int,
        current_risk: float,
    ) -> Dict[str, Any]:
        """Predicts Delta P and likelihood of revealed failures before applying the patch."""
        # Simple structural estimation based on file count and failure complexity
        est_resolved = 1
        est_new = 1 if len(files_touched) > 3 else 0
        est_risk_delta = -0.05 if len(files_touched) <= 2 else 0.02
        est_coverage_gain = 0.03
        est_revealed_prob = 0.4 if "auth" in target_failure.lower() or "init" in target_failure.lower() else 0.1

        prediction = {
            "patch_id": patch_id,
            "target_failure": target_failure,
            "predicted_resolved": est_resolved,
            "predicted_new": est_new,
            "predicted_risk_delta": est_risk_delta,
            "predicted_coverage_gain": est_coverage_gain,
            "revealed_failure_probability": est_revealed_prob,
            "predicted_score": est_resolved * 3.0 - est_new * 4.0 + est_coverage_gain * 10.0 + (-est_risk_delta) * 15.0,
        }
        return prediction

    def record_actual_outcome(
        self,
        prediction: Dict[str, Any],
        actual_delta: ProgressDelta,
        revealed_failures_observed: int = 0,
    ) -> Dict[str, Any]:
        """Records actual observed Delta P and evaluates prediction accuracy."""
        pred_score = prediction.get("predicted_score", 0.0)
        actual_score = actual_delta.score

        # Error metrics
        score_error = abs(pred_score - actual_score)
        direction_matched = (pred_score > 0 and actual_score > 0) or (pred_score <= 0 and actual_score <= 0)

        record = {
            "patch_id": prediction.get("patch_id", "unknown"),
            "predicted_score": pred_score,
            "actual_score": actual_score,
            "score_error": score_error,
            "direction_matched": direction_matched,
            "revealed_observed": revealed_failures_observed,
        }
        self.prediction_records.append(record)
        return record

    def compute_calibration_report(self) -> Dict[str, float]:
        """Computes aggregate calibration metrics across all recorded prediction pairs."""
        if not self.prediction_records:
            return {"directional_accuracy": 1.0, "mean_absolute_error": 0.0, "brier_score": 0.0}

        n = len(self.prediction_records)
        matched = sum(1 for r in self.prediction_records if r["direction_matched"])
        directional_acc = matched / n
        mae = sum(r["score_error"] for r in self.prediction_records) / n

        # Brier score for binary success prediction (score > 0)
        brier = sum(
            ((1.0 if r["predicted_score"] > 0 else 0.0) - (1.0 if r["actual_score"] > 0 else 0.0)) ** 2
            for r in self.prediction_records
        ) / n

        return {
            "directional_accuracy": round(directional_acc, 4),
            "mean_absolute_error": round(mae, 4),
            "brier_score": round(brier, 4),
        }
