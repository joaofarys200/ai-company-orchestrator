"""
JARVIS OS — Phase 76: Autonomous Engineering Learning & Predictive Calibration
Module: recorder.py
Ingestion, unit validation, idempotent reconciliation, and verification gating of predictions and outcomes.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

from .models import (
    IncompatibleUnitsError,
    ObservedOutcome,
    OutcomeVerificationStatus,
    PredictionOutcomePair,
    PredictionRecord,
    PredictionType,
)


class PredictionOutcomeRecorder:
    """
    Manages the lifecycle of predictions and empirical observations, ensuring
    strict unit matching, idempotent pairing, and verification gating.
    """

    def __init__(self):
        # Key: operation_id -> PredictionOutcomePair
        self._pairs_by_op: Dict[str, PredictionOutcomePair] = {}
        # Key: prediction_id -> operation_id
        self._pred_to_op: Dict[str, str] = {}
        # Quarantined invalid observations
        self.quarantine: List[ObservedOutcome] = []

    def record_prediction(self, prediction: PredictionRecord) -> PredictionOutcomePair:
        """
        Record a forecast before operation execution.
        If an outcome already arrived (late prediction), reconciles immediately.
        """
        op_id = prediction.operation_id
        if op_id in self._pairs_by_op:
            pair = self._pairs_by_op[op_id]
            pair.prediction = prediction
        else:
            pair = PredictionOutcomePair(prediction=prediction)
            self._pairs_by_op[op_id] = pair

        self._pred_to_op[prediction.prediction_id] = op_id
        pair.calculate_errors()
        return pair

    def record_outcome(self, outcome: ObservedOutcome) -> PredictionOutcomePair:
        """
        Record an empirical observation.
        Validates unit compatibility with the matching prediction.
        Reconciles idempotently without creating duplicate training samples.
        """
        op_id = outcome.operation_id
        if op_id not in self._pairs_by_op:
            # Create a placeholder prediction or unlinked pair
            dummy_pred = PredictionRecord(
                prediction_id=f"pending_{op_id}",
                operation_id=op_id,
                prediction_type=PredictionType.CONTINUOUS_EFFORT,
                target_metric="unknown",
                predicted_value=0.0,
                unit=outcome.unit,
            )
            pair = PredictionOutcomePair(prediction=dummy_pred, outcome=outcome)
            self._pairs_by_op[op_id] = pair
            return pair

        pair = self._pairs_by_op[op_id]

        # 1. Unit Compatibility Verification
        norm_pred_unit = pair.prediction.unit.strip().lower()
        norm_out_unit = outcome.unit.strip().lower()
        if norm_pred_unit != norm_out_unit and norm_pred_unit != "" and norm_out_unit != "":
            raise IncompatibleUnitsError(
                f"Unit mismatch for operation '{op_id}': prediction has '{pair.prediction.unit}', "
                f"but observed outcome has '{outcome.unit}'."
            )

        # 2. Quarantine invalid or incomparable measurements
        if outcome.verification_status in (
            OutcomeVerificationStatus.INVALID_MEASUREMENT,
            OutcomeVerificationStatus.INCOMPARABLE_ENVIRONMENT,
        ):
            self.quarantine.append(outcome)
            pair.outcome = outcome
            pair.is_eligible_for_calibration = False
            return pair

        # 3. Idempotently update outcome
        pair.outcome = outcome
        pair.calculate_errors()
        return pair

    def get_pair(self, operation_id: str) -> Optional[PredictionOutcomePair]:
        """Retrieve a reconciled pair by operation ID."""
        return self._pairs_by_op.get(operation_id)

    def get_eligible_training_pairs(
        self,
        prediction_type: Optional[PredictionType] = None,
        target_metric: Optional[str] = None,
    ) -> List[PredictionOutcomePair]:
        """
        Retrieve all verified, eligible prediction-outcome pairs sorted chronologically.
        """
        eligible = [
            pair for pair in self._pairs_by_op.values()
            if pair.is_eligible_for_calibration
            and pair.outcome is not None
            and pair.outcome.verification_status == OutcomeVerificationStatus.VERIFIED
        ]

        if prediction_type is not None:
            eligible = [p for p in eligible if p.prediction.prediction_type == prediction_type]
        if target_metric is not None:
            eligible = [p for p in eligible if p.prediction.target_metric == target_metric]

        # Strictly sort chronologically by prediction timestamp
        eligible.sort(key=lambda p: p.prediction.timestamp)
        return eligible
