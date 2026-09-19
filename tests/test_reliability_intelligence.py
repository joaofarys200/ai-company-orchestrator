"""
Phase 72 — Autonomous Reliability Intelligence & Preventive Operations Tests
Covers baselines, anomaly detection, trend analysis, risk scoring, calibrated prediction,
recurrence detection, dependency and change risk, preventive planning, governance gates,
post-action verification, learning loop, replay determinism, security guards, and Phase 71 integration.
"""

import time
import unittest

from backend.agents.reliability_intelligence.anomaly_detection import AnomalyDetector
from backend.agents.reliability_intelligence.baselines import BaselineCalculator
from backend.agents.reliability_intelligence.bridge import ReliabilityIntelligenceBridge
from backend.agents.reliability_intelligence.capacity_signals import CapacityMonitor
from backend.agents.reliability_intelligence.change_risk import ChangeRiskEvaluator
from backend.agents.reliability_intelligence.dependency_risk import DependencyRiskEvaluator
from backend.agents.reliability_intelligence.incident_prediction import IncidentPredictor
from backend.agents.reliability_intelligence.invariants import (
    InvariantViolationError,
    ReliabilityInvariantAuditor,
)
from backend.agents.reliability_intelligence.learning import ReliabilityLearningEngine
from backend.agents.reliability_intelligence.models import (
    AnomalySignal,
    AnomalyStatus,
    Baseline,
    BaselineConfidence,
    BaselineStatus,
    CapacitySignal,
    CapacityStatus,
    ChangeRiskAssessment,
    DependencyRiskSignal,
    GovernanceDecision,
    ObservationSourceType,
    PreventionVerificationStatus,
    PreventiveAction,
    PreventiveActionStatus,
    PreventiveActionType,
    PreventivePlan,
    PreventiveVerification,
    RecurrenceSignal,
    RecurrenceStatus,
    ReliabilityObservation,
    ReliabilityWindow,
    RiskLevel,
    RiskPrediction,
    TrendSignal,
    TrendStatus,
)
from backend.agents.reliability_intelligence.preventive_governance import (
    PreventiveGovernanceGate,
    UnauthorizedPreventiveExecutionError,
)
from backend.agents.reliability_intelligence.preventive_planning import PreventivePlanner
from backend.agents.reliability_intelligence.recurrence_detection import RecurrenceDetector
from backend.agents.reliability_intelligence.replay import PredictionReplayer
from backend.agents.reliability_intelligence.risk_scoring import RiskScoringEngine
from backend.agents.reliability_intelligence.security import (
    ReliabilitySecurityGuard,
    SecurityViolationError,
)
from backend.agents.reliability_intelligence.timeseries import TimeSeriesBuffer, TimeSeriesNormalizer
from backend.agents.reliability_intelligence.trend_analysis import TrendAnalyzer
from backend.agents.reliability_intelligence.verification import PreventiveVerifier


class TestReliabilityIntelligence(unittest.TestCase):
    def setUp(self):
        self.service_id = "test-service"
        self.bridge = ReliabilityIntelligenceBridge(service_id=self.service_id)

    # 1. Baseline Calculation
    def test_01_baseline_calculation(self):
        calc = BaselineCalculator(min_samples=5)
        now = time.time()
        obs = [
            ReliabilityObservation(
                timestamp=now - (10 - i) * 5,
                service=self.service_id,
                metric="latency",
                value=40.0 + (i % 3) * 2.0,
                source="collector",
            )
            for i in range(10)
        ]
        window = ReliabilityWindow(
            service=self.service_id,
            metric="latency",
            observations=obs,
            sample_count=10,
            window_seconds=100.0,
        )
        base = calc.compute(window)
        self.assertAlmostEqual(base.rolling_mean, 41.2, delta=1.0)
        self.assertEqual(base.confidence.status, BaselineStatus.VALID)
        self.assertGreater(base.p95, 40.0)

    # 2. Baseline Insufficient Evidence
    def test_02_baseline_insufficient_evidence(self):
        calc = BaselineCalculator(min_samples=5)
        obs = [
            ReliabilityObservation(
                timestamp=time.time(),
                service=self.service_id,
                metric="latency",
                value=45.0,
                source="collector",
            )
        ]
        window = ReliabilityWindow(
            service=self.service_id,
            metric="latency",
            observations=obs,
            sample_count=1,
            window_seconds=60.0,
        )
        base = calc.compute(window)
        self.assertEqual(base.confidence.status, BaselineStatus.INSUFFICIENT_EVIDENCE)

    # 3. Baseline Stale Detection
    def test_03_baseline_stale_detection(self):
        calc = BaselineCalculator(min_samples=5, max_age_seconds=100.0)
        now = time.time()
        obs = [
            ReliabilityObservation(
                timestamp=now - 500.0 + i,
                service=self.service_id,
                metric="latency",
                value=40.0,
                source="collector",
            )
            for i in range(10)
        ]
        window = ReliabilityWindow(
            service=self.service_id,
            metric="latency",
            observations=obs,
            sample_count=10,
            window_seconds=600.0,
        )
        base = calc.compute(window)
        self.assertEqual(base.confidence.status, BaselineStatus.STALE)

    # 4. Anomaly: Error Burst
    def test_04_anomaly_error_burst(self):
        detector = AnomalyDetector(error_burst_threshold=0.05)
        now = time.time()
        base = Baseline(
            service=self.service_id,
            metric="error_rate",
            rolling_mean=0.001,
            rolling_median=0.001,
            min_val=0.0,
            max_val=0.01,
            std_dev=0.002,
            p90=0.002,
            p95=0.003,
            p99=0.005,
            confidence=BaselineConfidence(10, 100.0, 5.0, 0.9, BaselineStatus.VALID),
            window_size=10,
        )
        obs = ReliabilityObservation(
            timestamp=now,
            service=self.service_id,
            metric="error_rate",
            value=0.15,
            source="collector",
        )
        sig = detector.evaluate(obs, base)
        self.assertEqual(sig.status, AnomalyStatus.ANOMALOUS)
        self.assertEqual(sig.detector, "error_burst_detector")

    # 5. Anomaly: Latency Degradation
    def test_05_anomaly_latency_degradation(self):
        detector = AnomalyDetector(latency_multiplier=2.0)
        now = time.time()
        base = Baseline(
            service=self.service_id,
            metric="latency",
            rolling_mean=40.0,
            rolling_median=40.0,
            min_val=35.0,
            max_val=45.0,
            std_dev=3.0,
            p90=43.0,
            p95=44.0,
            p99=45.0,
            confidence=BaselineConfidence(15, 100.0, 5.0, 0.9, BaselineStatus.VALID),
            window_size=15,
        )
        obs = ReliabilityObservation(
            timestamp=now,
            service=self.service_id,
            metric="latency",
            value=120.0,
            source="collector",
        )
        sig = detector.evaluate(obs, base)
        self.assertEqual(sig.status, AnomalyStatus.ANOMALOUS)
        self.assertEqual(sig.detector, "latency_degradation_detector")

    # 6. Anomaly: Restart Acceleration
    def test_06_anomaly_restart_acceleration(self):
        detector = AnomalyDetector(restart_rate_threshold=2.0)
        now = time.time()
        base = Baseline(
            service=self.service_id,
            metric="restarts",
            rolling_mean=0.0,
            rolling_median=0.0,
            min_val=0.0,
            max_val=0.0,
            std_dev=0.0,
            p90=0.0,
            p95=0.0,
            p99=0.0,
            confidence=BaselineConfidence(10, 100.0, 5.0, 0.9, BaselineStatus.VALID),
            window_size=10,
        )
        obs = ReliabilityObservation(
            timestamp=now,
            service=self.service_id,
            metric="restarts",
            value=4.0,
            source="collector",
        )
        sig = detector.evaluate(obs, base)
        self.assertEqual(sig.status, AnomalyStatus.ANOMALOUS)
        self.assertEqual(sig.detector, "restart_acceleration_detector")

    # 7. Anomaly: Resource Pressure
    def test_07_anomaly_resource_pressure(self):
        detector = AnomalyDetector()
        now = time.time()
        base = Baseline(
            service=self.service_id,
            metric="cpu",
            rolling_mean=30.0,
            rolling_median=30.0,
            min_val=20.0,
            max_val=40.0,
            std_dev=5.0,
            p90=38.0,
            p95=40.0,
            p99=42.0,
            confidence=BaselineConfidence(10, 100.0, 5.0, 0.9, BaselineStatus.VALID),
            window_size=10,
        )
        obs = ReliabilityObservation(
            timestamp=now,
            service=self.service_id,
            metric="cpu",
            value=95.0,
            source="collector",
        )
        sig = detector.evaluate(obs, base)
        self.assertEqual(sig.status, AnomalyStatus.ANOMALOUS)

    # 8. Anomaly: Sudden Spike and Drop
    def test_08_anomaly_sudden_spike_and_drop(self):
        detector = AnomalyDetector(spike_sigma_multiplier=3.0)
        base = Baseline(
            service=self.service_id,
            metric="request_volume",
            rolling_mean=100.0,
            rolling_median=100.0,
            min_val=80.0,
            max_val=120.0,
            std_dev=5.0,
            p90=108.0,
            p95=110.0,
            p99=115.0,
            confidence=BaselineConfidence(10, 100.0, 5.0, 0.9, BaselineStatus.VALID),
            window_size=10,
        )
        obs_spike = ReliabilityObservation(
            timestamp=time.time(),
            service=self.service_id,
            metric="request_volume",
            value=200.0,
            source="collector",
        )
        sig_spike = detector.evaluate(obs_spike, base)
        self.assertEqual(sig_spike.status, AnomalyStatus.ANOMALOUS)
        self.assertEqual(sig_spike.detector, "sudden_spike_detector")

    # 9. Anomaly: Sustained Drift
    def test_09_anomaly_sustained_drift(self):
        detector = AnomalyDetector(drift_sigma_multiplier=1.5)
        now = time.time()
        base = Baseline(
            service=self.service_id,
            metric="memory",
            rolling_mean=500.0,
            rolling_median=500.0,
            min_val=480.0,
            max_val=520.0,
            std_dev=10.0,
            p90=515.0,
            p95=518.0,
            p99=520.0,
            confidence=BaselineConfidence(10, 100.0, 5.0, 0.9, BaselineStatus.VALID),
            window_size=10,
        )
        drift_obs = [
            ReliabilityObservation(
                timestamp=now - (5 - i) * 2,
                service=self.service_id,
                metric="memory",
                value=530.0 + i * 2.0,
                source="collector",
            )
            for i in range(5)
        ]
        sig = detector.detect_sustained_drift(drift_obs, base, consecutive_points=5)
        self.assertEqual(sig.status, AnomalyStatus.ANOMALOUS)
        self.assertEqual(sig.detector, "sustained_drift_detector")

    # 10. UNKNOWN Anomaly Not Auto-Promoted
    def test_10_unknown_anomaly_not_auto_promoted(self):
        detector = AnomalyDetector()
        obs = ReliabilityObservation(
            timestamp=time.time(),
            service=self.service_id,
            metric="latency",
            value=50.0,
            source="collector",
        )
        base_weak = Baseline(
            service=self.service_id,
            metric="latency",
            rolling_mean=50.0,
            rolling_median=50.0,
            min_val=40.0,
            max_val=60.0,
            std_dev=5.0,
            p90=55.0,
            p95=58.0,
            p99=60.0,
            confidence=BaselineConfidence(2, 60.0, 1.0, 0.5, BaselineStatus.INSUFFICIENT_EVIDENCE),
            window_size=2,
        )
        sig = detector.evaluate(obs, base_weak)
        self.assertEqual(sig.status, AnomalyStatus.UNKNOWN)
        # Verify auditor raises if attempting to claim NORMAL or ANOMALOUS
        with self.assertRaises(InvariantViolationError):
            ReliabilityInvariantAuditor.assert_no_unknown_promotion(
                AnomalyStatus.NORMAL, BaselineStatus.INSUFFICIENT_EVIDENCE
            )

    # 11. Trend Analysis: Degrading
    def test_11_trend_analysis_degrading(self):
        analyzer = TrendAnalyzer(min_samples=4)
        now = time.time()
        obs = [
            ReliabilityObservation(
                timestamp=now - (10 - i) * 10,
                service=self.service_id,
                metric="latency",
                value=40.0 + i * 15.0,  # Strongly increasing latency
                source="collector",
            )
            for i in range(10)
        ]
        window = ReliabilityWindow(
            service=self.service_id,
            metric="latency",
            observations=obs,
            sample_count=10,
            window_seconds=100.0,
        )
        trend = analyzer.evaluate(window)
        self.assertEqual(trend.status, TrendStatus.DEGRADING)
        self.assertGreater(trend.slope, 0.0)
        self.assertGreater(trend.confidence, 0.7)

    # 12. Trend Analysis: Improving
    def test_12_trend_analysis_improving(self):
        analyzer = TrendAnalyzer(min_samples=4)
        now = time.time()
        obs = [
            ReliabilityObservation(
                timestamp=now - (6 - i) * 10,
                service=self.service_id,
                metric="availability",
                value=0.90 + i * 0.02,  # Increasing availability
                source="collector",
            )
            for i in range(6)
        ]
        window = ReliabilityWindow(
            service=self.service_id,
            metric="availability",
            observations=obs,
            sample_count=6,
            window_seconds=60.0,
        )
        trend = analyzer.evaluate(window)
        self.assertEqual(trend.status, TrendStatus.IMPROVING)

    # 13. Trend Analysis: Isolated Observation Rejected
    def test_13_trend_analysis_isolated_observation_rejected(self):
        analyzer = TrendAnalyzer(min_samples=4)
        obs = [
            ReliabilityObservation(
                timestamp=time.time(),
                service=self.service_id,
                metric="latency",
                value=150.0,
                source="collector",
            )
        ]
        window = ReliabilityWindow(
            service=self.service_id,
            metric="latency",
            observations=obs,
            sample_count=1,
            window_seconds=10.0,
        )
        trend = analyzer.evaluate(window)
        self.assertEqual(trend.status, TrendStatus.UNKNOWN)

    # 14. Capacity Signal Risk
    def test_14_capacity_signal_risk(self):
        monitor = CapacityMonitor(cpu_risk_threshold=90.0)
        now = time.time()
        obs = [
            ReliabilityObservation(
                timestamp=now,
                service=self.service_id,
                metric="cpu",
                value=94.5,
                source="collector",
            )
        ]
        window = ReliabilityWindow(
            service=self.service_id,
            metric="cpu",
            observations=obs,
            sample_count=1,
            window_seconds=60.0,
        )
        cap = monitor.evaluate(window)
        self.assertEqual(cap.status, CapacityStatus.RISK)

    # 15. Recurrence: First Occurrence
    def test_15_recurrence_first_occurrence(self):
        detector = RecurrenceDetector()
        history = [
            {"service": self.service_id, "category": "latency", "detection_time": time.time() - 30}
        ]
        rec = detector.evaluate_from_incidents(self.service_id, "latency", history)
        self.assertEqual(rec.status, RecurrenceStatus.FIRST_OCCURRENCE)
        self.assertEqual(rec.occurrence_count, 1)

    # 16. Recurrence: Recurrent and Escalating
    def test_16_recurrence_recurrent_and_escalating(self):
        detector = RecurrenceDetector(recurrence_threshold=2, escalating_threshold=4)
        now = time.time()
        history = [
            {"service": self.service_id, "category": "restart_loop", "detection_time": now - i * 10}
            for i in range(5)
        ]
        rec = detector.evaluate_from_incidents(self.service_id, "restart_loop", history)
        self.assertEqual(rec.status, RecurrenceStatus.ESCALATING_RECURRENCE)
        self.assertEqual(rec.occurrence_count, 5)

    # 17. Dependency Risk Scoring
    def test_17_dependency_risk_scoring(self):
        evaluator = DependencyRiskEvaluator()
        meta = {
            "centrality": 0.85,
            "in_cycle": True,
            "dependency_count": 10,
            "contract_status": "drifting",
        }
        sig = evaluator.evaluate(
            service=self.service_id,
            dependency="db-master",
            graph_metadata=meta,
            runtime_latency_ms=650.0,
            historical_incidents=3,
        )
        self.assertEqual(sig.risk_level, RiskLevel.HIGH)

    # 18. Change Risk Assessment
    def test_18_change_risk_assessment(self):
        evaluator = ChangeRiskEvaluator()
        assessment = evaluator.evaluate(
            change_id="chg-101",
            changed_files=["a.py", "b.py", "c.py", "d.py", "e.py"],
            changed_symbols=["func1", "func2", "func3", "class1", "class2", "class3"],
            contracts_affected=["ContractA", "ContractB"],
            impacted_services=["auth", "billing", "gateway"],
            historical_incident_rate=0.35,
            debt_score=45.0,
            coupling_score=0.8,
            prior_rollback=True,
        )
        self.assertEqual(assessment.risk_level, RiskLevel.HIGH)

    # 19. Risk Prediction Generation
    def test_19_risk_prediction_generation(self):
        predictor = IncidentPredictor()
        now = time.time()
        anom = AnomalySignal(
            signal_id="s1",
            detector="latency_degradation_detector",
            service=self.service_id,
            metric="latency",
            observed_value=120.0,
            baseline_value=40.0,
            deviation=80.0,
            status=AnomalyStatus.ANOMALOUS,
            threshold=80.0,
            evidence_id="ev1",
            timestamp=now,
        )
        trend = TrendSignal(
            signal_id="t1",
            service=self.service_id,
            metric="latency",
            slope=0.15,
            acceleration=0.01,
            persistence=0.9,
            confidence=0.85,
            status=TrendStatus.DEGRADING,
            evidence_id="ev2",
            timestamp=now,
        )
        pred = predictor.predict(
            target_service=self.service_id,
            anomalies=[anom],
            trends=[trend],
            capacities=[],
            recurrences=[],
            dependencies=[],
        )
        self.assertEqual(pred.failure_class, "LATENCY_SLO_BREACH")
        self.assertIn(pred.risk_level, (RiskLevel.MEDIUM, RiskLevel.HIGH))
        self.assertGreater(pred.probability_estimate, 0.3)

    # 20. Prediction Insufficient Evidence
    def test_20_prediction_insufficient_evidence(self):
        predictor = IncidentPredictor()
        pred = predictor.predict(
            target_service=self.service_id,
            anomalies=[],
            trends=[],
            capacities=[],
            recurrences=[],
            dependencies=[],
        )
        self.assertEqual(pred.risk_level, RiskLevel.UNKNOWN)
        self.assertEqual(pred.failure_class, "INSUFFICIENT_EVIDENCE")

    # 21. Preventive Planning: Low Risk
    def test_21_preventive_planning_low_risk(self):
        planner = PreventivePlanner()
        pred = RiskPrediction(
            prediction_id="p1",
            target=self.service_id,
            failure_class="NONE",
            horizon_seconds=300.0,
            probability_estimate=0.1,
            confidence=0.8,
            risk_level=RiskLevel.LOW,
            evidence_ids=[],
            contributing_signals=[],
            contradictory_signals=[],
        )
        plan = planner.plan(pred)
        self.assertEqual(len(plan.actions), 1)
        self.assertEqual(plan.actions[0].action_type, PreventiveActionType.INCREASE_OBSERVATION_FREQUENCY)

    # 22. Preventive Planning: Medium Risk
    def test_22_preventive_planning_medium_risk(self):
        planner = PreventivePlanner()
        pred = RiskPrediction(
            prediction_id="p2",
            target=self.service_id,
            failure_class="LATENCY_SLO_BREACH",
            horizon_seconds=300.0,
            probability_estimate=0.45,
            confidence=0.8,
            risk_level=RiskLevel.MEDIUM,
            evidence_ids=[],
            contributing_signals=[],
            contradictory_signals=[],
        )
        plan = planner.plan(pred)
        self.assertEqual(len(plan.actions), 1)
        self.assertEqual(plan.actions[0].action_type, PreventiveActionType.REBUILD_CACHE)

    # 23. Preventive Planning: High Risk
    def test_23_preventive_planning_high_risk(self):
        planner = PreventivePlanner()
        pred = RiskPrediction(
            prediction_id="p3",
            target=self.service_id,
            failure_class="RESTART_LOOP",
            horizon_seconds=120.0,
            probability_estimate=0.88,
            confidence=0.9,
            risk_level=RiskLevel.HIGH,
            evidence_ids=[],
            contributing_signals=[],
            contradictory_signals=[],
        )
        plan = planner.plan(pred)
        self.assertGreaterEqual(len(plan.actions), 2)
        # First action creates a checkpoint
        self.assertEqual(plan.actions[0].action_type, PreventiveActionType.CREATE_CHECKPOINT)
        # Second action is rollback before failure
        self.assertEqual(plan.actions[1].action_type, PreventiveActionType.ROLLBACK_BEFORE_FAILURE)

    # 24. Governance Blocks Autonomous High Risk
    def test_24_governance_blocks_autonomous_high_risk(self):
        gate = PreventiveGovernanceGate(autonomous_execution_enabled=True)
        act = PreventiveAction(
            action_id="act-1",
            action_type=PreventiveActionType.ROLLBACK_BEFORE_FAILURE,
            target_service=self.service_id,
            reason="Restart loop",
            risk_level=RiskLevel.HIGH,
            expected_effect="Rollback release",
            verification_plan="Check boot",
            rollback_action="None",
        )
        plan = PreventivePlan(
            plan_id="pl-1",
            prediction_id="pred-1",
            service=self.service_id,
            actions=[act],
        )
        can_run, reason = gate.can_execute_autonomously(act, plan)
        self.assertFalse(can_run)
        self.assertIn("HIGH_RISK", reason)

        # Attempting to execute autonomously raises error
        with self.assertRaises(UnauthorizedPreventiveExecutionError):
            gate.execute_action(act, plan)

    # 25. Governance Blocks Unknown Risk
    def test_25_governance_blocks_unknown_risk(self):
        gate = PreventiveGovernanceGate(autonomous_execution_enabled=True)
        act = PreventiveAction(
            action_id="act-2",
            action_type=PreventiveActionType.RESTART_SERVICE,
            target_service=self.service_id,
            reason="Uncertain telemetry",
            risk_level=RiskLevel.UNKNOWN,
            expected_effect="Restart",
            verification_plan="Check boot",
            rollback_action="None",
        )
        plan = PreventivePlan(
            plan_id="pl-2",
            prediction_id="pred-2",
            service=self.service_id,
            actions=[act],
        )
        can_run, reason = gate.can_execute_autonomously(act, plan)
        self.assertFalse(can_run)
        self.assertIn("UNKNOWN", reason)

    # 26. Preventive Action Verification Success
    def test_26_preventive_action_verification_success(self):
        verifier = PreventiveVerifier(min_verification_samples=3)
        now = time.time()
        pre_base = Baseline(
            service=self.service_id,
            metric="latency",
            rolling_mean=95.0,
            rolling_median=95.0,
            min_val=80.0,
            max_val=110.0,
            std_dev=5.0,
            p90=100.0,
            p95=105.0,
            p99=108.0,
            confidence=BaselineConfidence(10, 100.0, 5.0, 0.9, BaselineStatus.VALID),
            window_size=10,
        )
        post_obs = [
            ReliabilityObservation(
                timestamp=now + i,
                service=self.service_id,
                metric="latency",
                value=45.0 + i,  # Significantly improved latency
                source="collector",
            )
            for i in range(5)
        ]
        act = PreventiveAction(
            action_id="act-1",
            action_type=PreventiveActionType.REBUILD_CACHE,
            target_service=self.service_id,
            reason="Cache evicted",
            risk_level=RiskLevel.LOW,
            expected_effect="Reduced latency",
            verification_plan="Check p95",
            rollback_action="None",
        )
        ver = verifier.verify("plan-1", act, pre_base, post_obs)
        self.assertEqual(ver.status, PreventionVerificationStatus.PREVENTION_EFFECTIVE)

    # 27. Preventive Action Verification Insufficient Evidence
    def test_27_preventive_action_verification_insufficient_evidence(self):
        verifier = PreventiveVerifier(min_verification_samples=3)
        act = PreventiveAction(
            action_id="act-1",
            action_type=PreventiveActionType.REBUILD_CACHE,
            target_service=self.service_id,
            reason="Cache evicted",
            risk_level=RiskLevel.LOW,
            expected_effect="Reduced latency",
            verification_plan="Check p95",
            rollback_action="None",
        )
        # Empty post-action observations
        ver = verifier.verify("plan-1", act, None, [])
        self.assertEqual(ver.status, PreventionVerificationStatus.INSUFFICIENT_EVIDENCE)

    # 28. Learning Loop and Calibration
    def test_28_learning_loop_and_calibration(self):
        engine = ReliabilityLearningEngine(project_id=self.service_id)
        pred = RiskPrediction(
            prediction_id="pred-cal-1",
            target=self.service_id,
            failure_class="HTTP_5XX_BURST",
            horizon_seconds=300.0,
            probability_estimate=0.85,
            confidence=0.9,
            risk_level=RiskLevel.HIGH,
            evidence_ids=[],
            contributing_signals=[],
            contradictory_signals=[],
        )
        ev = engine.record_outcome(pred, actual_failure_occurred=True, lead_time_seconds=95.0)
        self.assertTrue(ev.is_true_positive)
        self.assertFalse(ev.is_false_positive)
        self.assertAlmostEqual(ev.calibration_error, (0.85 - 1.0) ** 2, places=3)
        stats = engine.get_calibration_stats()
        self.assertEqual(stats["true_positives"], 1)
        self.assertEqual(stats["precision"], 1.0)

    # 29. Learning Loop Rejects Blind Cross-Project Transfer
    def test_29_learning_loop_rejects_cross_project_transfer(self):
        engine = ReliabilityLearningEngine(project_id="project-alpha")
        pred = RiskPrediction(
            prediction_id="pred-1",
            target=self.service_id,
            failure_class="NONE",
            horizon_seconds=100.0,
            probability_estimate=0.5,
            confidence=0.5,
            risk_level=RiskLevel.LOW,
            evidence_ids=[],
            contributing_signals=[],
            contradictory_signals=[],
        )
        with self.assertRaises(ValueError):
            engine.record_outcome(pred, actual_failure_occurred=False, context_project_id="project-beta")

    # 30. Deterministic Prediction Replay
    def test_30_deterministic_prediction_replay(self):
        replayer = PredictionReplayer()
        now = time.time()
        obs = [
            ReliabilityObservation(
                timestamp=now - (10 - i) * 5,
                service=self.service_id,
                metric="latency",
                value=40.0 + i * 5.0,
                source="collector",
            )
            for i in range(10)
        ]
        res = replayer.replay_stream(obs)
        self.assertEqual(res["status"], "REPLAY_MATCH")
        self.assertEqual(res["observations_replayed"], 10)
        self.assertIn("baseline", res)
        self.assertIn("prediction", res)

    # 31. Security Guard Rejects Malicious Inputs
    def test_31_security_guard_rejects_malicious_inputs(self):
        # 1. Reject NaN value
        obs_nan = ReliabilityObservation(
            timestamp=time.time(),
            service=self.service_id,
            metric="latency",
            value=float("nan"),
            source="collector",
        )
        with self.assertRaises(SecurityViolationError):
            ReliabilitySecurityGuard.validate_observation(obs_nan)

        # 2. Reject path traversal in service ID
        with self.assertRaises(SecurityViolationError):
            ReliabilitySecurityGuard.validate_service_id("../../etc/shadow")

        # 3. Reject command injection characters
        with self.assertRaises(SecurityViolationError):
            ReliabilitySecurityGuard.validate_service_id("service; rm -rf /")

    # 32. Integration with F71 Bridge
    def test_32_integration_with_f71_bridge(self):
        # Ingest F71-style telemetry into F72 bridge
        now = time.time()
        for i in range(8):
            self.bridge.ingest_observation({
                "service": self.service_id,
                "metric": "latency",
                "value": 45.0 + i * 8.0,
                "timestamp": now - (8 - i) * 10,
                "source": "collector",
            })

        # Ingest F71 incident
        self.bridge.ingest_phase71_incident({
            "service": self.service_id,
            "category": "latency",
            "detection_time": now - 30,
            "evidence": "ev_f71_test",
        })

        decision = self.bridge.run_reliability_cycle(metric="latency")
        self.assertIsNotNone(decision.prediction)
        self.assertIsNotNone(decision.plan)
        summary = self.bridge.get_status_summary()
        self.assertGreater(summary["metrics"]["observations_ingested"], 0)


if __name__ == "__main__":
    unittest.main()
