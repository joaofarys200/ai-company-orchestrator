"""
Phase 72 — Closed-Loop Reliability Learning
Integrates experience memory (F42), cross-mission generalization (F43), and cross-project learning (F63).
Strictly forbids blind cross-project knowledge transfer without context compatibility validation.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from .models import (
    PredictionEvidence,
    PreventiveAction,
    PreventivePlan,
    RiskPrediction,
)


class ReliabilityLearningEngine:
    """Stores historical prediction outcomes, calibrates error rates, and persists lessons."""

    def __init__(self, project_id: str = "default_project"):
        self.project_id = project_id
        self._evidence_records: List[PredictionEvidence] = []
        self._lessons: List[Dict[str, Any]] = []

    def record_outcome(
        self,
        prediction: RiskPrediction,
        actual_failure_occurred: bool,
        lead_time_seconds: float = 0.0,
        action_executed: Optional[PreventiveAction] = None,
        context_project_id: Optional[str] = None,
    ) -> PredictionEvidence:
        # Invariant: Strictly prevent blind cross-project transfer
        if context_project_id and context_project_id != self.project_id:
            raise ValueError(
                f"Blind cross-project learning rejected: target project '{context_project_id}' "
                f"does not match engine project '{self.project_id}'"
            )

        pred_positive = prediction.probability_estimate >= 0.5
        actual_positive = actual_failure_occurred

        is_tp = pred_positive and actual_positive
        is_fp = pred_positive and not actual_positive
        is_fn = not pred_positive and actual_positive

        # Brier calibration error: (p - y)^2
        y = 1.0 if actual_positive else 0.0
        cal_err = round((prediction.probability_estimate - y) ** 2, 4)

        ev = PredictionEvidence(
            evidence_id=f"ev_learn_{uuid.uuid4().hex[:8]}",
            timestamp=time.time(),
            prediction_id=prediction.prediction_id,
            actual_outcome="FAILURE_OCCURRED" if actual_positive else "NO_FAILURE",
            is_true_positive=is_tp,
            is_false_positive=is_fp,
            is_false_negative=is_fn,
            lead_time_seconds=lead_time_seconds,
            calibration_error=cal_err,
        )
        self._evidence_records.append(ev)

        # Formulate lesson
        lesson = {
            "lesson_id": f"lsn_{uuid.uuid4().hex[:6]}",
            "prediction_id": prediction.prediction_id,
            "failure_class": prediction.failure_class,
            "outcome": ev.actual_outcome,
            "calibration_error": cal_err,
            "lesson_text": (
                f"Predictor correctly alerted with {lead_time_seconds:.1f}s lead time."
                if is_tp
                else (
                    "False alarm observed: high risk predicted without failure."
                    if is_fp
                    else ("Missed incident: failure occurred with low predicted probability." if is_fn else "True negative.")
                )
            ),
            "timestamp": ev.timestamp,
        }
        self._lessons.append(lesson)
        return ev

    def get_calibration_stats(self) -> Dict[str, Any]:
        n = len(self._evidence_records)
        if n == 0:
            return {
                "sample_count": 0,
                "true_positives": 0,
                "false_positives": 0,
                "false_negatives": 0,
                "precision": 0.0,
                "recall": 0.0,
                "brier_score": 0.0,
            }

        tp = sum(1 for e in self._evidence_records if e.is_true_positive)
        fp = sum(1 for e in self._evidence_records if e.is_false_positive)
        fn = sum(1 for e in self._evidence_records if e.is_false_negative)

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        brier = sum(e.calibration_error for e in self._evidence_records) / n

        return {
            "sample_count": n,
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "brier_score": round(brier, 4),
        }

    def get_lessons(self) -> List[Dict[str, Any]]:
        return list(self._lessons)
