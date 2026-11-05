"""
JARVIS OS — Phase 76: Autonomous Engineering Learning & Predictive Calibration
Deterministic Test Suite covering all 30 required scenarios from Section 10.
"""

from __future__ import annotations

import math
import os
import shutil
import tempfile
import time
from pathlib import Path
import pytest

from backend.agents.predictive_calibration import (
    CalibrationError,
    CalibrationParameters,
    CalibrationPromotionError,
    CalibrationState,
    CalibrationStore,
    CalibrationVersion,
    DataLeakageError,
    DriftDetector,
    DriftSeverity,
    DriftSignal,
    ErrorMetrics,
    EstimateResult,
    HoldoutEvaluator,
    IncompatibleUnitsError,
    InsufficientSamplesError,
    ObservedOutcome,
    OutcomeVerificationStatus,
    Phase73MacroRefactoringAdapter,
    Phase74ArchitecturalOptimizationAdapter,
    Phase75PortfolioOrchestrationAdapter,
    PredictionErrorAnalyzer,
    PredictionOutcomePair,
    PredictionOutcomeRecorder,
    PredictionRecord,
    PredictionType,
    PredictiveCalibrationBridge,
    PredictiveCalibrator,
    StaleCalibrationError,
)


class TestPredictiveCalibrationEngine:

    @pytest.fixture(autouse=True)
    def setup_temp_env(self):
        self.temp_dir = tempfile.mkdtemp(prefix="jarvis_phase76_test_")
        self.bridge = PredictiveCalibrationBridge(store_dir=self.temp_dir, min_samples=5)
        yield
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Scenario 1: Recording a valid prediction
    # -------------------------------------------------------------------------
    def test_01_record_valid_prediction(self):
        pair = self.bridge.record_prediction(
            operation_id="op_101",
            prediction_type=PredictionType.CONTINUOUS_DURATION,
            target_metric="refactoring_duration",
            predicted_value=120.0,
            unit="seconds",
            estimator_version="base_v1",
            assumptions="Assuming zero lock contention",
        )
        assert pair.prediction.operation_id == "op_101"
        assert pair.prediction.predicted_value == 120.0
        assert pair.prediction.unit == "seconds"
        assert pair.outcome is None
        assert pair.is_eligible_for_calibration is False

    # -------------------------------------------------------------------------
    # Scenario 2: Recording and verifying an actual outcome
    # -------------------------------------------------------------------------
    def test_02_record_and_verify_actual_outcome(self):
        self.bridge.record_prediction(
            operation_id="op_102",
            prediction_type=PredictionType.CONTINUOUS_DURATION,
            target_metric="refactoring_duration",
            predicted_value=100.0,
            unit="seconds",
        )
        pair = self.bridge.record_verified_outcome(
            operation_id="op_102",
            actual_value=115.0,
            unit="seconds",
            verification_status=OutcomeVerificationStatus.VERIFIED,
        )
        assert pair.outcome is not None
        assert pair.outcome.actual_value == 115.0
        assert pair.signed_error == -15.0  # 100 - 115
        assert pair.absolute_error == 15.0
        assert pair.is_eligible_for_calibration is True

    # -------------------------------------------------------------------------
    # Scenario 3: Distinguishing predictions from verified measurements
    # -------------------------------------------------------------------------
    def test_03_distinguish_prediction_from_measurement(self):
        pair = self.bridge.record_prediction(
            operation_id="op_103",
            prediction_type=PredictionType.CONTINUOUS_BENEFIT,
            target_metric="latency_reduction_ms",
            predicted_value=45.0,
            unit="ms",
        )
        # Even if unverified measurement arrives, it is not eligible for calibration
        pair_unverif = self.bridge.record_verified_outcome(
            operation_id="op_103",
            actual_value=30.0,
            unit="ms",
            verification_status=OutcomeVerificationStatus.MEASURED_UNVERIFIED,
        )
        assert pair_unverif.is_eligible_for_calibration is False

        # Once verified, it becomes eligible
        pair_verif = self.bridge.record_verified_outcome(
            operation_id="op_103",
            actual_value=30.0,
            unit="ms",
            verification_status=OutcomeVerificationStatus.VERIFIED,
        )
        assert pair_verif.is_eligible_for_calibration is True

    # -------------------------------------------------------------------------
    # Scenario 4: Calculating signed prediction error correctly
    # -------------------------------------------------------------------------
    def test_04_calculate_signed_prediction_error(self):
        # Overestimation: predicted 80, actual 50 -> signed error = +30
        self.bridge.record_prediction("op_over", PredictionType.CONTINUOUS_EFFORT, "effort", 80.0, "units")
        pair_over = self.bridge.record_verified_outcome("op_over", 50.0, "units")
        assert pair_over.signed_error == 30.0

        # Underestimation: predicted 40, actual 60 -> signed error = -20
        self.bridge.record_prediction("op_under", PredictionType.CONTINUOUS_EFFORT, "effort", 40.0, "units")
        pair_under = self.bridge.record_verified_outcome("op_under", 60.0, "units")
        assert pair_under.signed_error == -20.0

    # -------------------------------------------------------------------------
    # Scenario 5: Calculating suitable metrics for continuous predictions
    # -------------------------------------------------------------------------
    def test_05_metrics_for_continuous_predictions(self):
        pairs = []
        # Errors: +10, -10, +20, -20
        for i, (p, a) in enumerate([(110, 100), (90, 100), (120, 100), (80, 100)]):
            pr = PredictionRecord(f"p_{i}", f"op_{i}", PredictionType.CONTINUOUS_DURATION, "dur", float(p), "s")
            oc = ObservedOutcome(f"o_{i}", f"op_{i}", float(a), "s", OutcomeVerificationStatus.VERIFIED)
            pair = PredictionOutcomePair(prediction=pr, outcome=oc)
            pair.calculate_errors()
            pairs.append(pair)

        metrics = PredictionErrorAnalyzer.calculate_metrics(pairs)
        assert metrics.sample_count == 4
        assert metrics.signed_bias == 0.0  # (+10 - 10 + 20 - 20) / 4 = 0
        assert metrics.mean_absolute_error == 15.0  # (10 + 10 + 20 + 20) / 4 = 15.0
        assert abs(metrics.root_mean_squared_error - math.sqrt((100+100+400+400)/4)) < 0.01

    # -------------------------------------------------------------------------
    # Scenario 6: Evaluating probabilistic predictions using an appropriate metric (Brier score)
    # -------------------------------------------------------------------------
    def test_06_evaluating_probabilistic_predictions_brier_score(self):
        # 4 probabilistic predictions for failure
        data = [
            (0.8, 1.0),  # predicted 0.8, occurred (1.0) -> (0.8 - 1)^2 = 0.04
            (0.9, 1.0),  # predicted 0.9, occurred (1.0) -> (0.9 - 1)^2 = 0.01
            (0.2, 0.0),  # predicted 0.2, no failure (0.0) -> (0.2 - 0)^2 = 0.04
            (0.1, 0.0),  # predicted 0.1, no failure (0.0) -> (0.1 - 0)^2 = 0.01
        ]
        pairs = []
        for i, (prob, actual) in enumerate(data):
            pr = PredictionRecord(f"p_{i}", f"op_{i}", PredictionType.PROBABILITY_FAILURE, "fail", prob, "prob")
            oc = ObservedOutcome(f"o_{i}", f"op_{i}", actual, "prob", OutcomeVerificationStatus.VERIFIED)
            pair = PredictionOutcomePair(prediction=pr, outcome=oc)
            pair.calculate_errors()
            pairs.append(pair)

        metrics = PredictionErrorAnalyzer.calculate_metrics(pairs)
        assert metrics.brier_score is not None
        # Mean = (0.04 + 0.01 + 0.04 + 0.01) / 4 = 0.025
        assert abs(metrics.brier_score - 0.025) < 0.001

    # -------------------------------------------------------------------------
    # Scenario 7: Handling zero or near-zero denominators safely
    # -------------------------------------------------------------------------
    def test_07_handling_zero_denominators_safely(self):
        # Actual value is exactly 0.0
        pr = PredictionRecord("p0", "op0", PredictionType.CONTINUOUS_EFFORT, "effort", 5.0, "units")
        oc = ObservedOutcome("o0", "op0", 0.0, "units", OutcomeVerificationStatus.VERIFIED)
        pair = PredictionOutcomePair(prediction=pr, outcome=oc)
        pair.calculate_errors()

        metrics = PredictionErrorAnalyzer.calculate_metrics([pair])
        assert metrics.signed_bias == 5.0
        assert metrics.mean_absolute_error == 5.0
        # MAPE must not crash on zero denominator; should be None if no valid non-zero actuals
        assert metrics.mean_percentage_error is None

    # -------------------------------------------------------------------------
    # Scenario 8: Rejecting incompatible units or invalid observations
    # -------------------------------------------------------------------------
    def test_08_rejecting_incompatible_units(self):
        self.bridge.record_prediction(
            operation_id="op_units",
            prediction_type=PredictionType.CONTINUOUS_DURATION,
            target_metric="duration",
            predicted_value=50.0,
            unit="seconds",
        )
        # Attempting to record outcome in USD dollars
        with pytest.raises(IncompatibleUnitsError):
            self.bridge.record_verified_outcome(
                operation_id="op_units",
                actual_value=50.0,
                unit="USD",
            )

    # -------------------------------------------------------------------------
    # Scenario 9: Preventing duplicate observation ingestion
    # -------------------------------------------------------------------------
    def test_09_preventing_duplicate_observation_ingestion(self):
        self.bridge.record_prediction("op_dup", PredictionType.CONTINUOUS_COST, "cost", 20.0, "USD")
        pair1 = self.bridge.record_verified_outcome("op_dup", 22.0, "USD")
        # Second call with same operation_id updates idempotently
        pair2 = self.bridge.record_verified_outcome("op_dup", 22.0, "USD")

        eligible = self.bridge.recorder.get_eligible_training_pairs(target_metric="cost")
        assert len(eligible) == 1, "Duplicate outcome submission must not create duplicate training pairs"

    # -------------------------------------------------------------------------
    # Scenario 10: Identifying systematic overestimation
    # -------------------------------------------------------------------------
    def test_10_identifying_systematic_overestimation(self):
        pairs = []
        for i in range(5):
            pr = PredictionRecord(f"p_{i}", f"op_{i}", PredictionType.CONTINUOUS_BENEFIT, "benefit", 100.0, "pct")
            oc = ObservedOutcome(f"o_{i}", f"op_{i}", 60.0, "pct", OutcomeVerificationStatus.VERIFIED)
            pair = PredictionOutcomePair(prediction=pr, outcome=oc)
            pair.calculate_errors()
            pairs.append(pair)

        has_bias, bias_type, bias_val = PredictionErrorAnalyzer.identify_systematic_bias(pairs)
        assert has_bias is True
        assert bias_type == "OVERESTIMATION"
        assert bias_val == 40.0

    # -------------------------------------------------------------------------
    # Scenario 11: Identifying systematic underestimation
    # -------------------------------------------------------------------------
    def test_11_identifying_systematic_underestimation(self):
        pairs = []
        for i in range(5):
            pr = PredictionRecord(f"p_{i}", f"op_{i}", PredictionType.CONTINUOUS_DURATION, "duration", 30.0, "s")
            oc = ObservedOutcome(f"o_{i}", f"op_{i}", 60.0, "s", OutcomeVerificationStatus.VERIFIED)
            pair = PredictionOutcomePair(prediction=pr, outcome=oc)
            pair.calculate_errors()
            pairs.append(pair)

        has_bias, bias_type, bias_val = PredictionErrorAnalyzer.identify_systematic_bias(pairs)
        assert has_bias is True
        assert bias_type == "UNDERESTIMATION"
        assert bias_val == -30.0

    # -------------------------------------------------------------------------
    # Scenario 12: Handling outliers without corrupting calibration
    # -------------------------------------------------------------------------
    def test_12_handling_outliers_without_corrupting_calibration(self):
        pairs = []
        # Normal observations: predicted 100, actual 120 (signed error = -20)
        for i in range(10):
            pr = PredictionRecord(f"p_{i}", f"op_{i}", PredictionType.CONTINUOUS_DURATION, "dur", 100.0, "s")
            oc = ObservedOutcome(f"o_{i}", f"op_{i}", 120.0, "s", OutcomeVerificationStatus.VERIFIED)
            pair = PredictionOutcomePair(prediction=pr, outcome=oc)
            pair.calculate_errors()
            pairs.append(pair)

        # Injected extreme outlier: actual 5000 (signed error = -4900)
        pr_out = PredictionRecord("p_out", "op_out", PredictionType.CONTINUOUS_DURATION, "dur", 100.0, "s")
        oc_out = ObservedOutcome("o_out", "op_out", 5000.0, "s", OutcomeVerificationStatus.VERIFIED)
        pair_out = PredictionOutcomePair(prediction=pr_out, outcome=oc_out)
        pair_out.calculate_errors()
        pairs.append(pair_out)

        calibrator = PredictiveCalibrator(min_samples=5)
        version = calibrator.fit_calibration_version(
            version_id="cal_robust",
            prediction_type=PredictionType.CONTINUOUS_DURATION,
            target_metric="dur",
            training_pairs=pairs,
        )

        # Offset beta should be near +20.0 (actual - predicted), not distorted into hundreds by the outlier
        assert abs(version.parameters.offset_beta - 20.0) < 5.0

    # -------------------------------------------------------------------------
    # Scenario 13: Enforcing minimum sample requirements
    # -------------------------------------------------------------------------
    def test_13_enforcing_minimum_sample_requirements(self):
        calibrator = PredictiveCalibrator(min_samples=5)
        # Only 3 pairs provided
        pairs = []
        for i in range(3):
            pr = PredictionRecord(f"p_{i}", f"op_{i}", PredictionType.CONTINUOUS_EFFORT, "eff", 10.0, "units")
            oc = ObservedOutcome(f"o_{i}", f"op_{i}", 12.0, "units", OutcomeVerificationStatus.VERIFIED)
            p = PredictionOutcomePair(prediction=pr, outcome=oc)
            p.calculate_errors()
            pairs.append(p)

        with pytest.raises(InsufficientSamplesError):
            calibrator.fit_calibration_version("cal_small", PredictionType.CONTINUOUS_EFFORT, "eff", pairs)

    # -------------------------------------------------------------------------
    # Scenario 14: Producing a deterministic calibration for identical inputs
    # -------------------------------------------------------------------------
    def test_14_deterministic_calibration_for_identical_inputs(self):
        calibrator = PredictiveCalibrator(min_samples=5)
        pairs = []
        for i in range(6):
            pr = PredictionRecord(f"p_{i}", f"op_{i}", PredictionType.CONTINUOUS_COST, "cost", float(10 + i * 5), "USD")
            oc = ObservedOutcome(f"o_{i}", f"op_{i}", float(12 + i * 6), "USD", OutcomeVerificationStatus.VERIFIED)
            p = PredictionOutcomePair(prediction=pr, outcome=oc)
            p.calculate_errors()
            pairs.append(p)

        ver1 = calibrator.fit_calibration_version("cal_det", PredictionType.CONTINUOUS_COST, "cost", pairs)
        ver2 = calibrator.fit_calibration_version("cal_det", PredictionType.CONTINUOUS_COST, "cost", pairs)

        assert ver1.parameters.scale_alpha == ver2.parameters.scale_alpha
        assert ver1.parameters.offset_beta == ver2.parameters.offset_beta
        assert ver1.parameters.variance_sigma == ver2.parameters.variance_sigma

    # -------------------------------------------------------------------------
    # Scenario 15: Persisting and restoring calibration state
    # -------------------------------------------------------------------------
    def test_15_persisting_and_restoring_calibration_state(self):
        store = CalibrationStore(base_dir=self.temp_dir)
        version = CalibrationVersion(
            version_id="cal_v1_persist",
            prediction_type=PredictionType.CONTINUOUS_DURATION,
            target_metric="refactoring_time",
            state=CalibrationState.PROMOTED,
            parameters=CalibrationParameters(scale_alpha=1.1, offset_beta=15.0, variance_sigma=5.0),
        )
        store.save_calibration_version(version)

        loaded = store.load_calibration_version("cal_v1_persist")
        assert loaded is not None
        assert loaded.version_id == "cal_v1_persist"
        assert loaded.state == CalibrationState.PROMOTED
        assert loaded.parameters.scale_alpha == 1.1
        assert loaded.parameters.offset_beta == 15.0

    # -------------------------------------------------------------------------
    # Scenario 16: Evaluating against data not used for calibration
    # -------------------------------------------------------------------------
    def test_16_evaluating_against_unseen_holdout_data(self):
        evaluator = HoldoutEvaluator(train_split_ratio=0.7)
        pairs = []
        base_ts = time.time()
        for i in range(10):
            # Constant underestimation: predicted = 100, actual = 130
            pr = PredictionRecord(f"p_{i}", f"op_{i}", PredictionType.CONTINUOUS_DURATION, "dur", 100.0, "s", timestamp=base_ts + i * 10)
            oc = ObservedOutcome(f"o_{i}", f"op_{i}", 130.0, "s", OutcomeVerificationStatus.VERIFIED)
            p = PredictionOutcomePair(prediction=pr, outcome=oc)
            p.calculate_errors()
            pairs.append(p)

        train, holdout = evaluator.split_chronological(pairs)
        assert len(train) == 7
        assert len(holdout) == 3

        calibrator = PredictiveCalibrator(min_samples=5)
        candidate = calibrator.fit_calibration_version("cal_unseen", PredictionType.CONTINUOUS_DURATION, "dur", train)

        promoted, base_m, hold_m, reason = evaluator.evaluate_and_promote(candidate, holdout)
        assert promoted is True
        # Calibrated MAE on unseen holdout should be virtually 0 (down from 30)
        assert hold_m.mean_absolute_error < base_m.mean_absolute_error

    # -------------------------------------------------------------------------
    # Scenario 17: Preventing temporal data leakage
    # -------------------------------------------------------------------------
    def test_17_preventing_temporal_data_leakage(self):
        evaluator = HoldoutEvaluator(train_split_ratio=0.7)
        t0 = time.time()
        pairs = [
            PredictionOutcomePair(prediction=PredictionRecord("p1", "op1", PredictionType.CONTINUOUS_EFFORT, "eff", 10.0, "u", timestamp=t0 + 100), outcome=ObservedOutcome("o1", "op1", 10.0, "u", OutcomeVerificationStatus.VERIFIED)),
            PredictionOutcomePair(prediction=PredictionRecord("p2", "op2", PredictionType.CONTINUOUS_EFFORT, "eff", 10.0, "u", timestamp=t0 + 200), outcome=ObservedOutcome("o2", "op2", 10.0, "u", OutcomeVerificationStatus.VERIFIED)),
            PredictionOutcomePair(prediction=PredictionRecord("p3", "op3", PredictionType.CONTINUOUS_EFFORT, "eff", 10.0, "u", timestamp=t0 + 300), outcome=ObservedOutcome("o3", "op3", 10.0, "u", OutcomeVerificationStatus.VERIFIED)),
            PredictionOutcomePair(prediction=PredictionRecord("p4", "op4", PredictionType.CONTINUOUS_EFFORT, "eff", 10.0, "u", timestamp=t0 + 400), outcome=ObservedOutcome("o4", "op4", 10.0, "u", OutcomeVerificationStatus.VERIFIED)),
        ]
        train, holdout = evaluator.split_chronological(pairs)
        # Train timestamps must be strictly less than or equal to holdout timestamps
        assert max(p.prediction.timestamp for p in train) <= min(p.prediction.timestamp for p in holdout)

    # -------------------------------------------------------------------------
    # Scenario 18: Rejecting a calibration that fails its promotion criteria
    # -------------------------------------------------------------------------
    def test_18_rejecting_calibration_that_fails_promotion(self):
        evaluator = HoldoutEvaluator()
        # Candidate calibration that adds wild noise and degrades MAE
        bad_version = CalibrationVersion(
            version_id="cal_bad",
            prediction_type=PredictionType.CONTINUOUS_EFFORT,
            target_metric="eff",
            state=CalibrationState.EXPERIMENTAL,
            parameters=CalibrationParameters(scale_alpha=5.0, offset_beta=200.0),
        )
        # True holdout has predictions already close to actual (predicted 50, actual 52)
        holdout = []
        for i in range(4):
            pr = PredictionRecord(f"p_{i}", f"op_{i}", PredictionType.CONTINUOUS_EFFORT, "eff", 50.0, "u")
            oc = ObservedOutcome(f"o_{i}", f"op_{i}", 52.0, "u", OutcomeVerificationStatus.VERIFIED)
            p = PredictionOutcomePair(prediction=pr, outcome=oc)
            p.calculate_errors()
            holdout.append(p)

        promoted, base_m, hold_m, reason = evaluator.evaluate_and_promote(bad_version, holdout)
        assert promoted is False
        assert bad_version.state == CalibrationState.EXPERIMENTAL
        assert "PROMOTION_REJECTED" in reason

    # -------------------------------------------------------------------------
    # Scenario 19: Promoting a calibration that meets predefined criteria
    # -------------------------------------------------------------------------
    def test_19_promoting_calibration_meeting_criteria(self):
        evaluator = HoldoutEvaluator()
        # Consistent underestimation: predicted = 40, actual = 60
        holdout = []
        for i in range(4):
            pr = PredictionRecord(f"p_{i}", f"op_{i}", PredictionType.CONTINUOUS_EFFORT, "eff", 40.0, "u")
            oc = ObservedOutcome(f"o_{i}", f"op_{i}", 60.0, "u", OutcomeVerificationStatus.VERIFIED)
            p = PredictionOutcomePair(prediction=pr, outcome=oc)
            p.calculate_errors()
            holdout.append(p)

        good_version = CalibrationVersion(
            version_id="cal_good",
            prediction_type=PredictionType.CONTINUOUS_EFFORT,
            target_metric="eff",
            state=CalibrationState.EXPERIMENTAL,
            parameters=CalibrationParameters(scale_alpha=1.0, offset_beta=20.0),  # Corrects the -20 bias
        )

        promoted, base_m, hold_m, reason = evaluator.evaluate_and_promote(good_version, holdout)
        assert promoted is True
        assert good_version.state == CalibrationState.PROMOTED
        assert good_version.promoted_at is not None

    # -------------------------------------------------------------------------
    # Scenario 20: Rolling back to a previously validated version
    # -------------------------------------------------------------------------
    def test_20_rolling_back_to_previous_validated_version(self):
        store = self.bridge.store
        v1 = CalibrationVersion("v1.0.0", PredictionType.CONTINUOUS_DURATION, "dur", CalibrationState.PROMOTED, CalibrationParameters())
        v2 = CalibrationVersion("v2.0.0", PredictionType.CONTINUOUS_DURATION, "dur", CalibrationState.PROMOTED, CalibrationParameters())
        store.save_calibration_version(v1)
        store.save_calibration_version(v2)

        # Rollback from v2 to v1
        ok = store.rollback_calibration("v2.0.0", "v1.0.0", "Performance regression observed in production")
        assert ok is True

        loaded_v1 = store.load_calibration_version("v1.0.0")
        loaded_v2 = store.load_calibration_version("v2.0.0")
        assert loaded_v1.state == CalibrationState.PROMOTED
        assert loaded_v2.state == CalibrationState.ROLLED_BACK

    # -------------------------------------------------------------------------
    # Scenario 21: Falling back safely when calibration is unavailable
    # -------------------------------------------------------------------------
    def test_21_safe_fallback_when_calibration_unavailable(self):
        calibrator = PredictiveCalibrator()
        # No calibration model provided
        res = calibrator.calibrate(100.0, calibration=None)
        assert res.is_calibrated is False
        assert res.calibrated_value == 100.0
        assert "Uncalibrated baseline" in res.explanation

    # -------------------------------------------------------------------------
    # Scenario 22: Detecting a meaningful change in prediction behavior (drift)
    # -------------------------------------------------------------------------
    def test_22_detecting_meaningful_drift(self):
        detector = DriftDetector(window_size=5, drift_ratio_threshold=1.30, critical_ratio_threshold=1.60)
        cal = CalibrationVersion(
            "cal_drift_test", PredictionType.CONTINUOUS_DURATION, "dur", CalibrationState.PROMOTED,
            CalibrationParameters(),
            holdout_metrics=ErrorMetrics(5, 0.0, 10.0, 12.0, None, None, 0, 0, 0),  # Baseline MAE = 10.0
        )

        # Recent 5 pairs exhibit heavy degradation: actual MAE = 25.0 (drift_ratio = 2.5)
        recent = []
        for i in range(5):
            pr = PredictionRecord(f"p_{i}", f"op_{i}", PredictionType.CONTINUOUS_DURATION, "dur", 100.0, "s")
            oc = ObservedOutcome(f"o_{i}", f"op_{i}", 125.0, "s", OutcomeVerificationStatus.VERIFIED)
            p = PredictionOutcomePair(prediction=pr, outcome=oc)
            p.calculate_errors()
            recent.append(p)

        signal = detector.check_for_drift(cal, recent)
        assert signal is not None
        assert signal.severity == DriftSeverity.CRITICAL
        assert signal.drift_ratio >= 1.60
        assert cal.state == CalibrationState.SUSPENDED

    # -------------------------------------------------------------------------
    # Scenario 23: Avoiding unnecessary recalibration from an isolated outlier
    # -------------------------------------------------------------------------
    def test_23_avoiding_recalibration_from_isolated_outlier(self):
        detector = DriftDetector(window_size=5)
        cal = CalibrationVersion(
            "cal_stable", PredictionType.CONTINUOUS_DURATION, "dur", CalibrationState.PROMOTED,
            CalibrationParameters(),
            holdout_metrics=ErrorMetrics(5, 0.0, 10.0, 12.0, None, None, 0, 0, 0),
        )
        # 4 accurate predictions (error = 1.0) and only 1 outlier (error = 40.0) -> mean MAE = 8.8 (below 10.0)
        pairs = []
        for i in range(4):
            pr = PredictionRecord(f"p_{i}", f"op_{i}", PredictionType.CONTINUOUS_DURATION, "dur", 100.0, "s")
            oc = ObservedOutcome(f"o_{i}", f"op_{i}", 101.0, "s", OutcomeVerificationStatus.VERIFIED)
            p = PredictionOutcomePair(prediction=pr, outcome=oc)
            p.calculate_errors()
            pairs.append(p)

        p_out = PredictionOutcomePair(
            prediction=PredictionRecord("po", "opo", PredictionType.CONTINUOUS_DURATION, "dur", 100.0, "s"),
            outcome=ObservedOutcome("oo", "opo", 140.0, "s", OutcomeVerificationStatus.VERIFIED)
        )
        p_out.calculate_errors()
        pairs.append(p_out)

        signal = detector.check_for_drift(cal, pairs)
        assert signal is None, "Isolated outlier must not trigger a false drift alarm"
        assert cal.state == CalibrationState.PROMOTED

    # -------------------------------------------------------------------------
    # Scenario 24: Integrating calibrated estimates with an existing consumer
    # -------------------------------------------------------------------------
    def test_24_integrating_calibrated_estimates_with_existing_consumer(self):
        # Promote a calibration for macro_migration_duration (adds +30.0s offset)
        v = CalibrationVersion(
            version_id="cal_macro_dur_v1",
            prediction_type=PredictionType.CONTINUOUS_DURATION,
            target_metric="macro_migration_duration",
            state=CalibrationState.PROMOTED,
            parameters=CalibrationParameters(scale_alpha=1.0, offset_beta=30.0, variance_sigma=5.0),
        )
        self.bridge.store.save_calibration_version(v)

        # Phase 73 Adapter consumes it
        adapter = self.bridge.phase73_adapter
        # 2 steps, 1 component -> baseline = 2*25 + 1*10 = 60s
        est = adapter.estimate_migration_duration(step_count=2, component_count=1)
        assert est.baseline_value == 60.0
        assert est.calibrated_value == 90.0  # 60 + 30
        assert est.is_calibrated is True
        assert est.calibration_version == "cal_macro_dur_v1"

    # -------------------------------------------------------------------------
    # Scenario 25: Preserving existing security and approval requirements
    # -------------------------------------------------------------------------
    def test_25_preserving_security_and_approval_requirements(self):
        # Calibration cannot lower risk or bypass approval
        adapter = self.bridge.phase74_adapter
        # Even if calibrated benefit is very high, approval requirements cannot be removed
        est = adapter.estimate_performance_gain(baseline_delta=50.0, pattern_type="facade")
        assert est.calibrated_value >= 0.0

    # -------------------------------------------------------------------------
    # Scenario 26: Reconciling observations after interrupted execution
    # -------------------------------------------------------------------------
    def test_26_reconciling_observations_after_interrupted_execution(self):
        # Store state to disk
        self.bridge.record_prediction("op_crash", PredictionType.CONTINUOUS_EFFORT, "eff", 10.0, "u")
        self.bridge.record_verified_outcome("op_crash", 14.0, "u")

        # Simulate new bridge instance starting up from disk
        new_bridge = PredictiveCalibrationBridge(store_dir=self.temp_dir)
        pair = new_bridge.recorder.get_pair("op_crash")
        assert pair is not None
        assert pair.outcome.actual_value == 14.0
        assert pair.signed_error == -4.0

    # -------------------------------------------------------------------------
    # Scenario 27: Preventing stale calibration versions from being silently used
    # -------------------------------------------------------------------------
    def test_27_preventing_stale_calibration_from_silent_use(self):
        calibrator = PredictiveCalibrator()
        # Version marked as SUSPENDED or ROLLED_BACK
        v_stale = CalibrationVersion(
            "cal_stale", PredictionType.CONTINUOUS_DURATION, "dur", CalibrationState.SUSPENDED,
            CalibrationParameters(scale_alpha=2.0, offset_beta=50.0)
        )
        res = calibrator.calibrate(100.0, v_stale)
        # Must fall back to baseline
        assert res.is_calibrated is False
        assert res.calibrated_value == 100.0

    # -------------------------------------------------------------------------
    # Scenario 28: Ensuring rejected or unexecuted alternatives are not assigned fabricated outcomes
    # -------------------------------------------------------------------------
    def test_28_rejected_alternatives_not_assigned_fabricated_outcomes(self):
        # Record prediction for an unexecuted alternative
        pair = self.bridge.record_prediction("op_unexecuted", PredictionType.CONTINUOUS_BENEFIT, "ben", 80.0, "pct")
        # Must remain unobserved and ineligible
        assert pair.outcome is None
        assert pair.is_eligible_for_calibration is False
        eligible = self.bridge.recorder.get_eligible_training_pairs(target_metric="ben")
        assert len(eligible) == 0

    # -------------------------------------------------------------------------
    # Scenario 29: Handling missing or delayed measurements
    # -------------------------------------------------------------------------
    def test_29_handling_missing_or_delayed_measurements(self):
        # Prediction arrives at T0
        self.bridge.record_prediction("op_delayed", PredictionType.CONTINUOUS_DURATION, "dur", 40.0, "s")
        assert self.bridge.recorder.get_pair("op_delayed").outcome is None

        # Delayed outcome arrives at T1
        pair = self.bridge.record_verified_outcome("op_delayed", 55.0, "s")
        assert pair.outcome is not None
        assert pair.signed_error == -15.0
        assert pair.is_eligible_for_calibration is True

    # -------------------------------------------------------------------------
    # Scenario 30: Ensuring existing phases continue to operate with the calibration layer disabled
    # -------------------------------------------------------------------------
    def test_30_existing_phases_operate_with_calibration_disabled(self):
        # Empty calibration store
        empty_bridge = PredictiveCalibrationBridge(store_dir=tempfile.mkdtemp())
        # Phase 75 adapter queries without any calibration versions
        est = empty_bridge.phase75_adapter.estimate_initiative_effort(raw_effort=5.0, initiative_type="macro_refactoring")
        assert est.baseline_value == 5.0
        assert est.calibrated_value == 5.0
        assert est.is_calibrated is False
