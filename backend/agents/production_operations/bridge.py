"""
Phase 71 — Production Operations Bridge
Coordinates the complete operational lifecycle:
OBSERVE -> DETECT -> CLASSIFY -> CORRELATE -> DIAGNOSE -> PLAN -> GATE -> EXECUTE -> VERIFY -> DECIDE -> RECORD.
Integrates with mission orchestrator and WebSocket handlers.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional
from .cache import OperationsCache
from .correlation import IncidentCorrelator
from .detection import IncidentDetector
from .diagnosis import RootCauseDiagnostician
from .escalation import EscalationManager
from .healthcheck import HealthCheckEngine, create_standard_healthcheck_suite
from .ledger import OperationalLedger
from .local_runtime import InfrastructureDetector, LocalRuntimeController
from .metrics import OperationsTelemetry
from .models import (
    EscalationTicket,
    HealthCheckResult,
    HealthStatus,
    Incident,
    ObservationProvenance,
    ObservationStatus,
    OperationalState,
    ProductionDecision,
    RecoveryPlan,
    RecoveryVerification,
    RemediationExecution,
    RollbackCertificate,
    RuntimeObservation,
    SLOEvaluation,
    VerificationStatus,
)
from .policy import OperationalGovernancePolicy
from .recovery_plan import RecoveryPlanner
from .remediation import RemediationExecutor
from .replay import IncidentReplayer
from .rollback import RollbackOrchestrator
from .slo import SLOEvaluator
from .state_machine import OperationalStateMachine
from .telemetry import TelemetryNormalizer
from .verification import PostRecoveryVerifier


class ProductionOperationsBridge:
    """
    Unified operational governance bridge.
    """

    def __init__(self, service_id: str = "jarvis-service", default_env: str = "local"):
        self.service_id = service_id
        self.default_env = default_env

        # State machine
        self.state_machine = OperationalStateMachine(initial_state=OperationalState.READY_FOR_OPERATIONS)

        # Core subsystems
        self.telemetry = TelemetryNormalizer(service_id=service_id, default_env=default_env)
        self.health = create_standard_healthcheck_suite(service_id=service_id)
        self.slo = SLOEvaluator(service_id=service_id)
        self.detector = IncidentDetector(service_id=service_id)
        self.correlator = IncidentCorrelator()
        self.diagnostician = RootCauseDiagnostician(service_id=service_id)
        self.planner = RecoveryPlanner(service_id=service_id)
        self.remediator = RemediationExecutor(service_id=service_id)
        self.rollback = RollbackOrchestrator(service_id=service_id)
        self.verifier = PostRecoveryVerifier(service_id=service_id)
        self.escalator = EscalationManager(service_id=service_id)
        self.ledger = OperationalLedger(service_id=service_id)
        self.replayer = IncidentReplayer(service_id=service_id)
        self.local_runtime = LocalRuntimeController(service_id=service_id)
        self.policy = OperationalGovernancePolicy(service_id=service_id)
        self.metrics = OperationsTelemetry()
        self.cache = OperationsCache()

        # State tracking
        self.active_incidents: List[Incident] = []
        self.latest_decision: Optional[ProductionDecision] = None
        self.infrastructure_status = InfrastructureDetector.detect()

    def check_infrastructure_grounding(self) -> OperationalState:
        """Enforces truthful physical infrastructure representation."""
        if not self.infrastructure_status["physical_infrastructure_present"]:
            if self.state_machine.can_transition_to(OperationalState.DEPLOYMENT_NOT_AVAILABLE):
                self.state_machine.transition_to(
                    OperationalState.DEPLOYMENT_NOT_AVAILABLE,
                    reason="Physical cloud deployment infrastructure absent in local repository."
                )
                self.ledger.append_event(
                    event_type="INFRASTRUCTURE_UNAVAILABLE",
                    state_before=OperationalState.READY_FOR_OPERATIONS.value,
                    action="EMIT_DEPLOYMENT_NOT_AVAILABLE",
                    state_after=OperationalState.DEPLOYMENT_NOT_AVAILABLE.value,
                    evidence_ids=["evd-infra-absent"],
                    payload=self.infrastructure_status,
                )
        return self.state_machine.current_state

    def ingest_runtime_observation(
        self,
        raw_data: Dict[str, Any],
        provenance: ObservationProvenance = ObservationProvenance.REAL_RUNTIME_OBSERVATION,
    ) -> RuntimeObservation:
        """Ingests and normalizes an observation, advancing metrics and state."""
        start_t = time.perf_counter()
        obs = self.telemetry.normalize(raw_data, provenance=provenance)
        self.metrics.observations_processed += 1

        # Cache observation
        self.cache.put(f"obs:{obs.evidence_id}", obs.to_dict())

        # Record stage timing
        duration_ms = (time.perf_counter() - start_t) * 1000.0
        self.metrics.record_stage_time("telemetry_ingestion", duration_ms)

        # Detect incidents from this observation
        detected = self.detector.detect_from_observation(obs)
        if detected:
            self._handle_detected_incidents(detected)

        return obs

    def execute_healthchecks(self) -> List[HealthCheckResult]:
        """Runs registered healthchecks and detects failures."""
        start_t = time.perf_counter()
        results = self.health.execute_all()
        duration_ms = (time.perf_counter() - start_t) * 1000.0
        self.metrics.record_stage_time("healthcheck_execution", duration_ms)

        detected = self.detector.detect_from_healthchecks(results)
        if detected:
            self._handle_detected_incidents(detected)

        return results

    def evaluate_slos(self, metrics_data: Dict[str, List[float]]) -> List[SLOEvaluation]:
        """Evaluates batch SLOs and detects breaches."""
        start_t = time.perf_counter()
        evals = self.slo.evaluate_batch(metrics_data)
        duration_ms = (time.perf_counter() - start_t) * 1000.0
        self.metrics.record_stage_time("slo_evaluation", duration_ms)

        detected = self.detector.detect_from_slo(evals)
        if detected:
            self._handle_detected_incidents(detected)

        return evals

    def _handle_detected_incidents(self, incidents: List[Incident]) -> None:
        """Processes newly detected incidents."""
        for inc in incidents:
            if inc.incident_id not in [i.incident_id for i in self.active_incidents]:
                self.active_incidents.append(inc)
                self.metrics.incidents_detected += 1
                # Update severity counts
                sev_attr = f"{inc.severity.value.lower()}_count"
                if hasattr(self.metrics, sev_attr):
                    setattr(self.metrics, sev_attr, getattr(self.metrics, sev_attr) + 1)

                # State machine transition to INCIDENT_DETECTED if valid
                if self.state_machine.can_transition_to(OperationalState.INCIDENT_DETECTED):
                    self.state_machine.transition_to(
                        OperationalState.INCIDENT_DETECTED,
                        reason=f"Incident detected: {inc.category.value} ({inc.severity.value})"
                    )

                # Record in ledger
                self.ledger.append_event(
                    event_type="INCIDENT_DETECTED",
                    state_before=OperationalState.HEALTHY.value,
                    action=f"DETECT_{inc.category.value}",
                    state_after=OperationalState.INCIDENT_DETECTED.value,
                    evidence_ids=inc.evidence,
                    payload=inc.to_dict(),
                )

    def run_operational_cycle(self) -> ProductionDecision:
        """
        Executes full cycle: CORRELATE -> DIAGNOSE -> PLAN -> GATE -> DECIDE.
        """
        start_t = time.perf_counter()

        if not self.active_incidents:
            decision = self.policy.evaluate_decision(
                current_state=self.state_machine.current_state,
                active_incidents=[],
                proposed_plan=None,
            )
            self.latest_decision = decision
            return decision

        # 1. Correlate
        self.correlator.correlate(self.active_incidents)

        # 2. Diagnose primary incident
        primary = self.active_incidents[0]
        if self.state_machine.can_transition_to(OperationalState.DIAGNOSING):
            self.state_machine.transition_to(OperationalState.DIAGNOSING, reason="Diagnosing primary incident")

        hypo = self.diagnostician.diagnose_incident(primary)

        # 3. Plan recovery
        if self.state_machine.can_transition_to(OperationalState.RECOVERY_PLANNED):
            self.state_machine.transition_to(OperationalState.RECOVERY_PLANNED, reason="Recovery plan formulated")

        plan = self.planner.plan_recovery(primary, hypothesis=hypo)
        self.metrics.plans_created += 1

        # 4. Gate / Decide
        decision = self.policy.evaluate_decision(
            current_state=self.state_machine.current_state,
            active_incidents=self.active_incidents,
            proposed_plan=plan,
        )
        self.latest_decision = decision

        duration_ms = (time.perf_counter() - start_t) * 1000.0
        self.metrics.record_stage_time("operational_cycle", duration_ms)

        self.ledger.append_event(
            event_type="DECISION_EMITTED",
            state_before=OperationalState.DIAGNOSING.value,
            action=decision.recommended_action,
            state_after=self.state_machine.current_state.value,
            evidence_ids=[hypo.hypothesis_id, plan.plan_id],
            payload=decision.to_dict(),
        )

        return decision

    def execute_autonomous_recovery(
        self,
        plan: RecoveryPlan,
        precheck_fn: Optional[Callable[[], bool]] = None,
        verify_fn: Optional[Callable[[], bool]] = None,
    ) -> RemediationExecution:
        """Executes authorized recovery plan."""
        if self.state_machine.can_transition_to(OperationalState.RECOVERING):
            self.state_machine.transition_to(OperationalState.RECOVERING, reason=f"Executing {plan.strategy.value}")

        exec_res = self.remediator.execute_plan(
            plan=plan,
            precheck_fn=precheck_fn,
            verify_fn=verify_fn,
        )

        if exec_res.success:
            self.metrics.remediations_succeeded += 1
            if self.state_machine.can_transition_to(OperationalState.VERIFYING_RECOVERY):
                self.state_machine.transition_to(OperationalState.VERIFYING_RECOVERY, reason="Remediation executed successfully")
        else:
            self.metrics.remediations_failed += 1
            if self.state_machine.can_transition_to(OperationalState.ESCALATED):
                self.state_machine.transition_to(OperationalState.ESCALATED, reason="Remediation failed execution/verification")

        self.ledger.append_event(
            event_type="REMEDIATION_EXECUTED",
            state_before=OperationalState.RECOVERING.value,
            action=plan.strategy.value,
            state_after=self.state_machine.current_state.value,
            evidence_ids=[exec_res.execution_id],
            payload=exec_res.to_dict(),
        )

        return exec_res

    def verify_recovery_state(
        self,
        incident_id: str,
        stability_window_seconds: int = 60,
    ) -> RecoveryVerification:
        """Validates stability across multi-check window before declaring RECOVERED."""
        hcs = self.health.execute_all()
        slos = self.slo.get_history()

        verif = self.verifier.verify_recovery(
            incident_id=incident_id,
            health_results=hcs,
            slo_evaluations=slos,
            stability_window_seconds=stability_window_seconds,
        )

        if verif.status == VerificationStatus.RECOVERY_VERIFIED:
            if self.state_machine.can_transition_to(OperationalState.RECOVERED):
                self.state_machine.transition_to(OperationalState.RECOVERED, reason="Post-recovery verified")
                # Clear resolved incident
                self.active_incidents = [i for i in self.active_incidents if i.incident_id != incident_id]
        else:
            if self.state_machine.can_transition_to(OperationalState.ESCALATED):
                self.state_machine.transition_to(OperationalState.ESCALATED, reason="Post-recovery verification failed")

        return verif

    def get_status(self) -> Dict[str, Any]:
        """Provides complete operational status dictionary for UI and WebSockets."""
        return {
            "service_id": self.service_id,
            "current_state": self.state_machine.current_state.value,
            "infrastructure": self.infrastructure_status,
            "active_incidents_count": len(self.active_incidents),
            "active_incidents": [i.to_dict() for i in self.active_incidents],
            "latest_decision": self.latest_decision.to_dict() if self.latest_decision else None,
            "metrics": self.metrics.to_dict(),
            "cache": self.cache.get_stats(),
            "ledger_size": len(self.ledger.get_entries()),
            "ledger_integrity": self.ledger.verify_integrity(),
        }
