"""
Phase 72 — Reliability Intelligence Bridge
Unified orchestration bridge integrating Phase 71 runtime telemetry,
producing proactive predictive risk signals without duplicating state machines.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from .anomaly_detection import AnomalyDetector
from .baselines import BaselineCalculator
from .capacity_signals import CapacityMonitor
from .dependency_risk import DependencyRiskEvaluator
from .evidence import ReliabilityEvidenceLedger
from .incident_prediction import IncidentPredictor
from .learning import ReliabilityLearningEngine
from .metrics import ReliabilityMetrics
from .models import (
    AnomalySignal,
    Baseline,
    CapacitySignal,
    DecisionQuality,
    GovernanceDecision,
    ObservationSourceType,
    PreventiveAction,
    PreventiveActionStatus,
    PreventivePlan,
    PreventiveVerification,
    RecurrenceSignal,
    ReliabilityDecision,
    ReliabilityObservation,
    RiskLevel,
    RiskPrediction,
    TrendSignal,
)
from .preventive_governance import PreventiveGovernanceGate
from .preventive_planning import PreventivePlanner
from .recurrence_detection import RecurrenceDetector
from .security import ReliabilitySecurityGuard
from .timeseries import TimeSeriesBuffer, TimeSeriesNormalizer
from .trend_analysis import TrendAnalyzer
from .verification import PreventiveVerifier


class ReliabilityIntelligenceBridge:
    """Coordinates telemetry ingest, anomaly discovery, trend analysis, risk prediction, and preventive plans."""

    def __init__(self, service_id: str = "default-service", autonomous_execution: bool = True):
        self.service_id = service_id
        self.buffer = TimeSeriesBuffer()
        self.baseline_calc = BaselineCalculator()
        self.anomaly_detector = AnomalyDetector()
        self.trend_analyzer = TrendAnalyzer()
        self.capacity_monitor = CapacityMonitor()
        self.recurrence_detector = RecurrenceDetector()
        self.dependency_evaluator = DependencyRiskEvaluator()
        self.predictor = IncidentPredictor()
        self.planner = PreventivePlanner()
        self.gate = PreventiveGovernanceGate(autonomous_execution_enabled=autonomous_execution)
        self.verifier = PreventiveVerifier()
        self.learning_engine = ReliabilityLearningEngine(project_id=service_id)
        self.ledger = ReliabilityEvidenceLedger()
        self.metrics = ReliabilityMetrics()

        self.incident_history: List[Dict[str, Any]] = []

    def ingest_observation(self, raw_payload: Dict[str, Any]) -> ReliabilityObservation:
        obs = TimeSeriesNormalizer.normalize(raw_payload)
        ReliabilitySecurityGuard.validate_observation(obs)
        self.buffer.ingest(obs)
        self.metrics.observations_ingested += 1
        return obs

    def ingest_phase71_incident(self, incident_dict: Dict[str, Any]) -> None:
        """Consumes an incident from Phase 71 incident detector."""
        self.incident_history.append(incident_dict)

    def run_reliability_cycle(
        self,
        metric: str = "latency",
        window_seconds: float = 300.0,
    ) -> ReliabilityDecision:
        now = time.time()
        window = self.buffer.get_window(self.service_id, metric, window_seconds=window_seconds)

        # 1. Baseline
        baseline = self.baseline_calc.compute(window)

        # 2. Anomaly
        anomalies: List[AnomalySignal] = []
        if window.observations:
            latest_obs = window.observations[-1]
            anom = self.anomaly_detector.evaluate(latest_obs, baseline)
            anomalies.append(anom)
            if anom.status.value == "ANOMALOUS":
                self.metrics.anomalies_flagged += 1

        # 3. Trend
        trend = self.trend_analyzer.evaluate(window)
        trends = [trend]
        self.metrics.trends_computed += 1

        # 4. Capacity
        cap = self.capacity_monitor.evaluate(window, trend)
        capacities = [cap]

        # 5. Recurrence
        rec = self.recurrence_detector.evaluate_from_incidents(
            service=self.service_id,
            incident_category=metric,
            incident_history=self.incident_history,
        )
        recurrences = [rec]

        # 6. Predict Risk
        prediction = self.predictor.predict(
            target_service=self.service_id,
            anomalies=anomalies,
            trends=trends,
            capacities=capacities,
            recurrences=recurrences,
            dependencies=[],
            horizon_seconds=window_seconds,
        )
        self.metrics.predictions_made += 1

        # 7. Plan Preventive Action
        plan = self.planner.plan(prediction)
        self.metrics.preventive_plans_created += 1

        # 8. Governance Gate
        gov_decision = self.gate.gate_plan(plan)

        # 9. Formulate Decision
        decision_id = f"dec_{uuid.uuid4().hex[:8]}"
        recommended = "OBSERVE"
        if plan.actions:
            recommended = plan.actions[0].action_type.value

        decision = ReliabilityDecision(
            decision_id=decision_id,
            service=self.service_id,
            prediction=prediction,
            plan=plan,
            recommended_action=recommended,
            decision_quality=DecisionQuality.OPTIMAL if prediction.confidence >= 0.5 else DecisionQuality.UNKNOWN,
            governance_status=gov_decision,
            timestamp=now,
        )

        self.ledger.record_decision(decision)
        return decision

    def execute_plan(
        self,
        plan: PreventivePlan,
        action_handlers: Optional[Dict[str, Callable[[], bool]]] = None,
        force_approved: bool = False,
    ) -> List[PreventiveActionStatus]:
        statuses = []
        for action in plan.actions:
            handler = action_handlers.get(action.action_type.value) if action_handlers else None
            status = self.gate.execute_action(
                action=action,
                plan=plan,
                handler=handler,
                force_approved=force_approved,
            )
            statuses.append(status)
            if status == PreventiveActionStatus.EXECUTED:
                self.metrics.preventive_actions_executed += 1
        return statuses

    def verify_action(
        self,
        plan_id: str,
        action: PreventiveAction,
        pre_baseline: Optional[Baseline],
        metric: str = "latency",
    ) -> PreventiveVerification:
        window = self.buffer.get_window(self.service_id, metric, window_seconds=60.0)
        ver = self.verifier.verify(
            plan_id=plan_id,
            action=action,
            pre_baseline=pre_baseline,
            post_observations=window.observations,
        )
        self.metrics.verifications_completed += 1
        return ver

    def get_status_summary(self) -> Dict[str, Any]:
        return {
            "service_id": self.service_id,
            "metrics": self.metrics.snapshot(),
            "decisions_count": len(self.ledger._decisions),
            "evidence_count": len(self.ledger._evidences),
            "calibration": self.learning_engine.get_calibration_stats(),
        }
