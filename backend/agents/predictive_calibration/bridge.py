"""
JARVIS OS — Phase 76: Autonomous Engineering Learning & Predictive Calibration
Module: bridge.py
Central predictive calibration bridge implementing the complete 9-stage learning lifecycle.
"""

from __future__ import annotations

import time
import uuid
from typing import Dict, List, Optional, Tuple

from .adapters import (
    Phase73MacroRefactoringAdapter,
    Phase74ArchitecturalOptimizationAdapter,
    Phase75PortfolioOrchestrationAdapter,
)
from .calibrator import PredictiveCalibrator
from .drift_detector import DriftDetector
from .error_analyzer import PredictionErrorAnalyzer
from .evaluator import HoldoutEvaluator
from .models import (
    CalibrationState,
    CalibrationVersion,
    DriftSignal,
    ErrorMetrics,
    EstimateResult,
    ObservedOutcome,
    OutcomeVerificationStatus,
    PredictionOutcomePair,
    PredictionRecord,
    PredictionType,
)
from .persistence import CalibrationStore
from .recorder import PredictionOutcomeRecorder


class PredictiveCalibrationBridge:
    """
    Central orchestrator for Phase 76.
    Coordinates prediction ingestion, outcome verification, error analytics,
    holdout evaluation, calibration version promotion, drift detection, and safe feedback.
    """

    def __init__(
        self,
        store_dir: str = ".jarvis/predictive_calibration",
        min_samples: int = 5,
        train_split_ratio: float = 0.70,
    ):
        self.store = CalibrationStore(base_dir=store_dir)
        self.recorder = PredictionOutcomeRecorder()
        self.calibrator = PredictiveCalibrator(min_samples=min_samples)
        self.evaluator = HoldoutEvaluator(train_split_ratio=train_split_ratio)
        self.drift_detector = DriftDetector()

        # Load persisted state
        self.store.load_recorder_state(self.recorder)

        # Adapters for existing engineering subsystems
        self.phase73_adapter = Phase73MacroRefactoringAdapter(self.store, self.calibrator)
        self.phase74_adapter = Phase74ArchitecturalOptimizationAdapter(self.store, self.calibrator)
        self.phase75_adapter = Phase75PortfolioOrchestrationAdapter(self.store, self.calibrator)

    def record_prediction(
        self,
        operation_id: str,
        prediction_type: PredictionType,
        target_metric: str,
        predicted_value: float,
        unit: str,
        estimator_version: str = "baseline_v1.0.0",
        context_features: Optional[Dict[str, Any]] = None,
        assumptions: str = "",
    ) -> PredictionOutcomePair:
        """Stage 1 & 2: Record a forecast with context and assumptions."""
        pred = PredictionRecord(
            prediction_id=f"pred_{uuid.uuid4().hex[:8]}",
            operation_id=operation_id,
            prediction_type=prediction_type,
            target_metric=target_metric,
            predicted_value=predicted_value,
            unit=unit,
            estimator_version=estimator_version,
            context_features=context_features or {},
            assumptions=assumptions,
            timestamp=time.time(),
        )
        pair = self.recorder.record_prediction(pred)
        self.store.save_recorder_state(self.recorder)
        return pair

    def record_verified_outcome(
        self,
        operation_id: str,
        actual_value: float,
        unit: str,
        verification_status: OutcomeVerificationStatus = OutcomeVerificationStatus.VERIFIED,
        measurement_method: str = "empirical_benchmark",
        notes: str = "",
    ) -> PredictionOutcomePair:
        """Stage 4: Ingest and reconcile verified empirical measurement."""
        outcome = ObservedOutcome(
            outcome_id=f"out_{uuid.uuid4().hex[:8]}",
            operation_id=operation_id,
            actual_value=actual_value,
            unit=unit,
            verification_status=verification_status,
            measurement_method=measurement_method,
            notes=notes,
            timestamp=time.time(),
        )
        pair = self.recorder.record_outcome(outcome)
        self.store.save_recorder_state(self.recorder)
        return pair

    def analyze_errors(
        self,
        prediction_type: Optional[PredictionType] = None,
        target_metric: Optional[str] = None,
    ) -> ErrorMetrics:
        """Stage 5 & 6: Compute error analytics and directional bias."""
        pairs = self.recorder.get_eligible_training_pairs(prediction_type, target_metric)
        return PredictionErrorAnalyzer.calculate_metrics(pairs)

    def train_and_evaluate_calibration(
        self,
        version_id: str,
        prediction_type: PredictionType,
        target_metric: str,
        description: str = "",
        min_mae_improvement_pct: float = 5.0,
    ) -> Tuple[bool, CalibrationVersion, str]:
        """
        Stage 7 & 8:
        1. Retrieve eligible historical pairs.
        2. Split chronologically into train and holdout sets.
        3. Fit candidate calibration version on train set.
        4. Evaluate candidate calibration against baseline on holdout set.
        5. If promotion criteria met, promote and persist.
        """
        all_pairs = self.recorder.get_eligible_training_pairs(prediction_type, target_metric)
        if len(all_pairs) < self.calibrator.min_samples:
            empty_ver = CalibrationVersion(
                version_id=version_id,
                prediction_type=prediction_type,
                target_metric=target_metric,
                state=CalibrationState.EXPERIMENTAL,
                parameters=self.calibrator.min_samples,
                description="Insufficient samples to train",
            )
            return False, empty_ver, f"Insufficient samples: {len(all_pairs)} < {self.calibrator.min_samples}"

        # Chronological split
        train_pairs, holdout_pairs = self.evaluator.split_chronological(all_pairs)

        # Fit candidate version on train set
        candidate_version = self.calibrator.fit_calibration_version(
            version_id=version_id,
            prediction_type=prediction_type,
            target_metric=target_metric,
            training_pairs=train_pairs,
            description=description,
        )

        # Evaluate on holdout set
        promoted, base_m, hold_m, reason = self.evaluator.evaluate_and_promote(
            calibration=candidate_version,
            holdout_pairs=holdout_pairs,
            min_mae_improvement_pct=min_mae_improvement_pct,
        )

        # Persist version
        self.store.save_calibration_version(candidate_version)
        return promoted, candidate_version, reason

    def check_for_drift(
        self,
        prediction_type: PredictionType,
        target_metric: str,
    ) -> Optional[DriftSignal]:
        """Check if active promoted calibration is experiencing drift."""
        active = self.store.get_active_promoted_version(prediction_type, target_metric)
        if not active:
            return None
        recent_pairs = self.recorder.get_eligible_training_pairs(prediction_type, target_metric)
        signal = self.drift_detector.check_for_drift(active, recent_pairs)
        if signal and active.state == CalibrationState.SUSPENDED:
            # Persist suspended state
            self.store.save_calibration_version(active)
        return signal

    def rollback_calibration(
        self,
        current_version_id: str,
        target_version_id: str,
        reason: str = "Rollback requested",
    ) -> bool:
        """Rollback an active calibration to a previously validated version."""
        return self.store.rollback_calibration(current_version_id, target_version_id, reason)

    def estimate(
        self,
        baseline_value: float,
        prediction_type: PredictionType,
        target_metric: str,
    ) -> EstimateResult:
        """Stage 9: Provide calibrated estimate to downstream consumers with safe fallback."""
        active = self.store.get_active_promoted_version(prediction_type, target_metric)
        return self.calibrator.calibrate(baseline_value, active)
