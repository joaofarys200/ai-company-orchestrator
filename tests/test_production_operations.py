"""
Tests for Phase 71 — Autonomous Production Operations & Incident Governance
Covers all 24 required operational test cases plus security regression invariants.
"""

import time
import unittest

from backend.agents.production_operations.bridge import ProductionOperationsBridge
from backend.agents.production_operations.correlation import IncidentCorrelator
from backend.agents.production_operations.detection import IncidentDetector
from backend.agents.production_operations.diagnosis import RootCauseDiagnostician
from backend.agents.production_operations.escalation import EscalationManager
from backend.agents.production_operations.healthcheck import HealthCheckEngine
from backend.agents.production_operations.invariants import (
    InvariantViolationError,
    OperationalInvariantAuditor,
)
from backend.agents.production_operations.ledger import OperationalLedger
from backend.agents.production_operations.local_runtime import InfrastructureDetector, LocalRuntimeController
from backend.agents.production_operations.models import (
    EscalationState,
    HealthCheckResult,
    HealthStatus,
    Incident,
    IncidentCategory,
    ObservationProvenance,
    ObservationStatus,
    OperationalState,
    RecoveryPlan,
    RecoveryStrategy,
    RecoveryVerification,
    RemediationExecution,
    RemediationSafety,
    RemediationStage,
    RollbackCertificate,
    RootCauseHypothesis,
    RootCauseStatus,
    RuntimeObservation,
    SeverityLevel,
    SLOEvaluation,
    SLOStatus,
    VerificationStatus,
)
from backend.agents.production_operations.policy import OperationalGovernancePolicy
from backend.agents.production_operations.recovery_plan import RecoveryPlanner
from backend.agents.production_operations.remediation import (
    RemediationExecutor,
    UnauthorizedRemediationError,
)
from backend.agents.production_operations.replay import IncidentReplayer
from backend.agents.production_operations.rollback import (
    InvalidRollbackTargetError,
    ProtectedPathViolationError,
    RollbackOrchestrator,
)
from backend.agents.production_operations.security import (
    OperationalSecurityGuard,
    SecurityViolationError,
)
from backend.agents.production_operations.slo import SLODefinition, SLOEvaluator
from backend.agents.production_operations.state_machine import (
    InvalidStateTransitionError,
    OperationalStateMachine,
)
from backend.agents.production_operations.telemetry import TelemetryNormalizer
from backend.agents.production_operations.verification import PostRecoveryVerifier


class TestProductionOperations(unittest.TestCase):
    def setUp(self):
        self.service_id = "test-service"
        self.bridge = ProductionOperationsBridge(service_id=self.service_id)

    # 1. Healthy Runtime
    def test_01_healthy_runtime(self):
        obs = self.bridge.ingest_runtime_observation({
            "process_id": "p-101",
            "service_id": self.service_id,
            "environment": "local",
            "state": "HEALTHY",
            "latency_ms": 45.0,
            "error_rate": 0.001,
            "availability": 1.0,
            "health_status": "HEALTHY",
            "cpu": 12.5,
            "memory": 150.0,
            "restart_count": 0,
            "dependency_status": {"db": "up", "redis": "up"},
        })
        self.assertEqual(obs.health_status, HealthStatus.HEALTHY)
        self.assertEqual(len(self.bridge.active_incidents), 0)
        decision = self.bridge.run_operational_cycle()
        self.assertEqual(decision.recommended_action, "CONTINUE")

    # 2. Healthcheck Failure
    def test_02_healthcheck_failure(self):
        engine = HealthCheckEngine(service_id=self.service_id)
        engine.register_check("custom_check", lambda: (HealthStatus.UNHEALTHY, "Critical ping failed"))
        res = engine.execute_check("custom_check")
        self.assertEqual(res.status, HealthStatus.UNHEALTHY)
        detector = IncidentDetector(service_id=self.service_id)
        incidents = detector.detect_from_healthchecks([res])
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0].category, IncidentCategory.HEALTHCHECK_FAILURE)

    # 3. HTTP 500
    def test_03_http_500_detection(self):
        obs = self.bridge.ingest_runtime_observation({
            "process_id": "p-102",
            "service_id": self.service_id,
            "environment": "local",
            "state": "DEGRADED",
            "latency_ms": 55.0,
            "error_rate": 0.65,  # High error rate -> HTTP_5XX
            "availability": 0.8,
            "health_status": "UNHEALTHY",
            "cpu": 35.0,
            "memory": 200.0,
            "restart_count": 0,
            "dependency_status": {},
        })
        self.assertGreater(len(self.bridge.active_incidents), 0)
        http_inc = next((i for i in self.bridge.active_incidents if i.category == IncidentCategory.HTTP_5XX), None)
        self.assertIsNotNone(http_inc)
        self.assertEqual(http_inc.severity, SeverityLevel.SEV1)

    # 4. Timeout
    def test_04_timeout_detection(self):
        evaluator = SLOEvaluator(service_id=self.service_id)
        evaluator.register_slo(SLODefinition(
            metric="timeout_rate",
            target_threshold=0.01,
            comparator="<=",
            window_seconds=300,
            min_samples=1,
        ))
        eval_res = evaluator.evaluate("timeout_rate", [0.05])
        self.assertEqual(eval_res.status, SLOStatus.BREACH)

    # 5. Process Crash
    def test_05_process_crash(self):
        detector = IncidentDetector(service_id=self.service_id)
        obs = RuntimeObservation(
            process_id="p-crash",
            service_id=self.service_id,
            environment="local",
            state=OperationalState.DEGRADED,
            latency_ms=0.0,
            error_rate=1.0,
            availability=0.0,  # 0 availability -> crash
            health_status=HealthStatus.UNHEALTHY,
            cpu=0.0,
            memory=0.0,
            restart_count=1,
            dependency_status={},
        )
        incidents = detector.detect_from_observation(obs)
        self.assertTrue(any(i.category == IncidentCategory.PROCESS_CRASH for i in incidents))

    # 6. Restart Loop
    def test_06_restart_loop(self):
        detector = IncidentDetector(service_id=self.service_id)
        obs = RuntimeObservation(
            process_id="p-loop",
            service_id=self.service_id,
            environment="local",
            state=OperationalState.DEGRADED,
            latency_ms=10.0,
            error_rate=0.2,
            availability=0.5,
            health_status=HealthStatus.UNHEALTHY,
            cpu=10.0,
            memory=50.0,
            restart_count=5,  # >= 3 triggers restart loop
            dependency_status={},
        )
        incidents = detector.detect_from_observation(obs)
        loop_inc = next((i for i in incidents if i.category == IncidentCategory.RESTART_LOOP), None)
        self.assertIsNotNone(loop_inc)
        self.assertEqual(loop_inc.severity, SeverityLevel.SEV0)

    # 7. Dependency Failure
    def test_07_dependency_failure(self):
        detector = IncidentDetector(service_id=self.service_id)
        obs = RuntimeObservation(
            process_id="p-dep",
            service_id=self.service_id,
            environment="local",
            state=OperationalState.DEGRADED,
            latency_ms=10.0,
            error_rate=0.02,
            availability=0.98,
            health_status=HealthStatus.HEALTHY,
            cpu=10.0,
            memory=50.0,
            restart_count=0,
            dependency_status={"auth_service": "down"},
        )
        incidents = detector.detect_from_observation(obs)
        dep_inc = next((i for i in incidents if i.category == IncidentCategory.DEPENDENCY_FAILURE), None)
        self.assertIsNotNone(dep_inc)
        self.assertEqual(dep_inc.severity, SeverityLevel.SEV2)

    # 8. Database Failure
    def test_08_database_failure(self):
        detector = IncidentDetector(service_id=self.service_id)
        obs = RuntimeObservation(
            process_id="p-db",
            service_id=self.service_id,
            environment="local",
            state=OperationalState.DEGRADED,
            latency_ms=10.0,
            error_rate=0.1,
            availability=0.9,
            health_status=HealthStatus.HEALTHY,
            cpu=10.0,
            memory=50.0,
            restart_count=0,
            dependency_status={"postgres_db": "unhealthy"},
        )
        incidents = detector.detect_from_observation(obs)
        db_inc = next((i for i in incidents if i.category == IncidentCategory.DATABASE_FAILURE), None)
        self.assertIsNotNone(db_inc)
        self.assertEqual(db_inc.severity, SeverityLevel.SEV1)

    # 9. WebSocket Failure
    def test_09_websocket_failure(self):
        engine = HealthCheckEngine(service_id=self.service_id)
        engine.register_check("websocket_check", lambda: (HealthStatus.UNHEALTHY, "WebSocket handshakes dropped"))
        res = engine.execute_check("websocket_check")
        detector = IncidentDetector(service_id=self.service_id)
        incidents = detector.detect_from_healthchecks([res])
        ws_inc = next((i for i in incidents if i.category == IncidentCategory.WEBSOCKET_FAILURE), None)
        self.assertIsNotNone(ws_inc)
        self.assertEqual(ws_inc.severity, SeverityLevel.SEV2)

    # 10. Latency SLO Breach
    def test_10_latency_slo_breach(self):
        evaluator = SLOEvaluator(service_id=self.service_id)
        eval_res = evaluator.evaluate("latency_p95_ms", [180.0, 195.0, 210.0])
        self.assertEqual(eval_res.status, SLOStatus.BREACH)
        detector = IncidentDetector(service_id=self.service_id)
        incidents = detector.detect_from_slo([eval_res])
        lat_inc = next((i for i in incidents if i.category == IncidentCategory.LATENCY_SLO_BREACH), None)
        self.assertIsNotNone(lat_inc)
        self.assertEqual(lat_inc.severity, SeverityLevel.SEV3)

    # 11. Recovery Success
    def test_11_recovery_success(self):
        executor = RemediationExecutor(service_id=self.service_id)
        plan = RecoveryPlan(
            plan_id="plan-rec-ok",
            incident_id="inc-01",
            strategy=RecoveryStrategy.RESTART_PROCESS,
            safety=RemediationSafety.ALLOWED,
            preconditions=[],
            expected_effect="Restart daemon",
            risk_level="LOW",
            required_evidence=[],
            rollback_action=None,
            verification_plan=[],
            authorized_by_policy=True,
        )
        executor.register_handler(RecoveryStrategy.RESTART_PROCESS, lambda: True)
        execution = executor.execute_plan(
            plan=plan,
            precheck_fn=lambda: True,
            verify_fn=lambda: True,
        )
        self.assertTrue(execution.success)
        self.assertEqual(execution.stage, RemediationStage.COMMIT)

    # 12. Recovery Failure
    def test_12_recovery_failure(self):
        executor = RemediationExecutor(service_id=self.service_id)
        plan = RecoveryPlan(
            plan_id="plan-rec-fail",
            incident_id="inc-02",
            strategy=RecoveryStrategy.RECONNECT_DEPENDENCY,
            safety=RemediationSafety.ALLOWED,
            preconditions=[],
            expected_effect="Reconnect DB",
            risk_level="LOW",
            required_evidence=[],
            rollback_action="None",
            verification_plan=[],
            authorized_by_policy=True,
        )
        executor.register_handler(RecoveryStrategy.RECONNECT_DEPENDENCY, lambda: False)
        execution = executor.execute_plan(plan=plan, precheck_fn=lambda: True, verify_fn=lambda: False)
        self.assertFalse(execution.success)

    # 13. Rollback Success
    def test_13_rollback_success(self):
        orchestrator = RollbackOrchestrator(service_id=self.service_id)
        orchestrator.register_checkpoint("v69.0.0", "6969696969696969696969696969696969696969696969696969696969696969")
        cert = orchestrator.execute_rollback(
            source_release="v70.0.0",
            target_release="v69.0.0",
            verification_fn=lambda: True,
        )
        self.assertTrue(cert.verified)
        self.assertEqual(cert.target_release, "v69.0.0")

    # 14. Rollback Failure
    def test_14_rollback_failure_unknown_target(self):
        orchestrator = RollbackOrchestrator(service_id=self.service_id)
        with self.assertRaises(InvalidRollbackTargetError):
            orchestrator.execute_rollback(source_release="v70.0.0", target_release="UNKNOWN")

    # 15. Insufficient Evidence
    def test_15_insufficient_evidence_slo(self):
        evaluator = SLOEvaluator(service_id=self.service_id)
        # min_samples is 3 for error_rate, provide only 1
        eval_res = evaluator.evaluate("error_rate", [0.005], sample_count=1)
        self.assertEqual(eval_res.status, SLOStatus.INSUFFICIENT_EVIDENCE)
        # Invariant: Must not be PASS
        self.assertNotEqual(eval_res.status, SLOStatus.PASS)

    # 16. Human Escalation
    def test_16_human_escalation(self):
        manager = EscalationManager(service_id=self.service_id)
        inc = Incident(
            incident_id="inc-esc-1",
            service=self.service_id,
            category=IncidentCategory.UNKNOWN_RUNTIME_FAILURE,
            severity=SeverityLevel.SEV2,
            confidence=0.55,  # Below 0.70 threshold
            correlation_key="corr:test",
            evidence=["Anomalous crash without stack trace"],
            rule_triggered="RULE_UNKNOWN",
            description="Unknown anomaly",
        )
        tkt = manager.check_and_escalate(incident=inc, confidence=0.55, recovery_attempts=0)
        self.assertIsNotNone(tkt)
        self.assertEqual(tkt.state, EscalationState.HUMAN_REVIEW)

    # 17. Incident Correlation
    def test_17_incident_correlation(self):
        correlator = IncidentCorrelator(temporal_window_seconds=60.0)
        now = time.time()
        root_inc = Incident(
            incident_id="inc-db-root",
            service="database-node",
            category=IncidentCategory.DATABASE_FAILURE,
            severity=SeverityLevel.SEV1,
            confidence=0.95,
            correlation_key="corr:db",
            evidence=["DB pool exhausted"],
            rule_triggered="RULE_DB",
            description="DB down",
            detection_time=now,
        )
        symptom_inc = Incident(
            incident_id="inc-http-symptom",
            service="api-gateway",
            category=IncidentCategory.HTTP_5XX,
            severity=SeverityLevel.SEV2,
            confidence=0.90,
            correlation_key="corr:http",
            evidence=["500 received"],
            rule_triggered="RULE_5XX",
            description="API 500",
            detection_time=now + 2.0,
        )
        groups = correlator.correlate([root_inc, symptom_inc], dependency_graph={"database-node": ["api-gateway"]})
        self.assertEqual(len(groups), 1)
        self.assertIn("inc-http-symptom", groups[0].correlated_incident_ids)

    # 18. Root Cause Rejection
    def test_18_root_cause_rejection(self):
        diagnostician = RootCauseDiagnostician(service_id=self.service_id)
        inc = Incident(
            incident_id="inc-proc-test",
            service=self.service_id,
            category=IncidentCategory.PROCESS_CRASH,
            severity=SeverityLevel.SEV1,
            confidence=0.9,
            correlation_key="corr:test",
            evidence=[],
            rule_triggered="RULE_CRASH",
            description="Crash claimed",
        )
        # Contradicting evidence proves process is alive
        hypo = diagnostician.diagnose_incident(inc, logs_evidence=["process running normally"])
        self.assertEqual(hypo.status, RootCauseStatus.REJECTED)

    # 19. Replay Determinism
    def test_19_replay_determinism(self):
        ledger = OperationalLedger(service_id=self.service_id)
        ledger.append_event(
            event_type="START",
            state_before="READY_FOR_OPERATIONS",
            action="START_SERVICE",
            state_after="STARTING",
        )
        ledger.append_event(
            event_type="HEALTH_CHECK",
            state_before="STARTING",
            action="MARK_HEALTHY",
            state_after="HEALTHY",
        )
        replayer = IncidentReplayer(service_id=self.service_id)
        status, steps, _ = replayer.replay(ledger.get_entries())
        self.assertEqual(status, "REPLAY_MATCH")
        self.assertEqual(len(steps), 2)

    # 20. Invalid State Transition
    def test_20_invalid_state_transition(self):
        sm = OperationalStateMachine(initial_state=OperationalState.HEALTHY)
        # HEALTHY -> RECOVERED is strictly illegal
        with self.assertRaises(InvalidStateTransitionError):
            sm.transition_to(OperationalState.RECOVERED)

        # HEALTHY -> ROLLED_BACK is strictly illegal
        with self.assertRaises(InvalidStateTransitionError):
            sm.transition_to(OperationalState.ROLLED_BACK)

    # 21. Deployment Unavailable
    def test_21_deployment_unavailable(self):
        bridge = ProductionOperationsBridge(service_id=self.service_id)
        # Force detection of absent physical infrastructure
        bridge.infrastructure_status = {
            "docker_available": False,
            "kubectl_available": False,
            "cloud_runner_available": False,
            "physical_infrastructure_present": False,
        }
        state = bridge.check_infrastructure_grounding()
        self.assertEqual(state, OperationalState.DEPLOYMENT_NOT_AVAILABLE)

    # 22. Local Runtime Available
    def test_22_local_runtime_available(self):
        ctrl = LocalRuntimeController(service_id=self.service_id)
        # Check port detection function executes without crashing
        is_open = ctrl.check_port_open(port=65432, timeout=0.1)
        self.assertIsInstance(is_open, bool)

    # 23. Forbidden Remediation
    def test_23_forbidden_remediation(self):
        executor = RemediationExecutor(service_id=self.service_id)
        forbidden_plan = RecoveryPlan(
            plan_id="plan-forbidden",
            incident_id="inc-forbid",
            strategy=RecoveryStrategy.RESTORE_CHECKPOINT,
            safety=RemediationSafety.FORBIDDEN,  # Forbidden action
            preconditions=[],
            expected_effect="Unsafe purge",
            risk_level="CRITICAL",
            required_evidence=[],
            rollback_action=None,
            verification_plan=[],
            authorized_by_policy=False,
        )
        with self.assertRaises(UnauthorizedRemediationError):
            executor.execute_plan(forbidden_plan)

    # 24. Recovery Requiring Rollback
    def test_24_recovery_requiring_rollback(self):
        policy = OperationalGovernancePolicy(service_id=self.service_id)
        sev0_inc = Incident(
            incident_id="inc-sev0-catastrophic",
            service=self.service_id,
            category=IncidentCategory.DATABASE_FAILURE,
            severity=SeverityLevel.SEV0,  # SEV0 mandates rollback
            confidence=0.99,
            correlation_key="corr:sev0",
            evidence=["Database corruption detected"],
            rule_triggered="RULE_DB_CORRUPTION_SEV0",
            description="Critical data integrity alert",
        )
        decision = policy.evaluate_decision(
            current_state=OperationalState.DIAGNOSING,
            active_incidents=[sev0_inc],
        )
        self.assertEqual(decision.recommended_action, "ROLLBACK")

    # 25. Security & Invariant Hardening
    def test_25_security_and_invariant_hardening(self):
        # Command injection check
        with self.assertRaises(SecurityViolationError):
            OperationalSecurityGuard.sanitize_command_args(["python", "app.py; rm -rf /"])

        # Path traversal check
        with self.assertRaises(SecurityViolationError):
            OperationalSecurityGuard.validate_filepath("../../etc/shadow")

        # Invariant: UNKNOWN cannot be promoted to HEALTHY
        with self.assertRaises(InvariantViolationError):
            OperationalInvariantAuditor.assert_no_unknown_promotion(
                status=HealthStatus.UNKNOWN,
                promoted_to=HealthStatus.HEALTHY,
            )


if __name__ == "__main__":
    unittest.main()
