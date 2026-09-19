"""
Phase 71 — Autonomous Production Operations & Incident Governance
Canonical Models, State Definitions, and Immutable Contracts.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class OperationalState(str, Enum):
    """Deterministic Operational State Machine States."""
    READY_FOR_OPERATIONS = "READY_FOR_OPERATIONS"
    STARTING = "STARTING"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    INCIDENT_DETECTED = "INCIDENT_DETECTED"
    DIAGNOSING = "DIAGNOSING"
    RECOVERY_PLANNED = "RECOVERY_PLANNED"
    RECOVERING = "RECOVERING"
    VERIFYING_RECOVERY = "VERIFYING_RECOVERY"
    RECOVERED = "RECOVERED"
    ROLLBACK_PLANNED = "ROLLBACK_PLANNED"
    ROLLING_BACK = "ROLLING_BACK"
    VERIFYING_ROLLBACK = "VERIFYING_ROLLBACK"
    ROLLED_BACK = "ROLLED_BACK"
    ESCALATED = "ESCALATED"
    OPERATIONS_BLOCKED = "OPERATIONS_BLOCKED"
    DEPLOYMENT_NOT_AVAILABLE = "DEPLOYMENT_NOT_AVAILABLE"
    TERMINATED = "TERMINATED"


class ObservationStatus(str, Enum):
    """Runtime observation epistemic status."""
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    VERIFIED = "VERIFIED"
    UNKNOWN = "UNKNOWN"


class HealthStatus(str, Enum):
    """Deterministic Tri-State Healthcheck Result."""
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class SLOStatus(str, Enum):
    """SLO Evaluation Result Status."""
    PASS = "PASS"
    BREACH = "BREACH"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class SeverityLevel(str, Enum):
    """Rule-based Incident Severity Classification."""
    SEV0 = "SEV0"  # Complete service loss, corruption risk, mandatory rollback
    SEV1 = "SEV1"  # Unavailable with high impact
    SEV2 = "SEV2"  # Significant degradation
    SEV3 = "SEV3"  # Limited error / partial impact
    SEV4 = "SEV4"  # Anomaly without confirmed functional impact


class IncidentCategory(str, Enum):
    """Deterministic Incident Categories."""
    HEALTHCHECK_FAILURE = "HEALTHCHECK_FAILURE"
    HTTP_5XX = "HTTP_5XX"
    HTTP_TIMEOUT = "HTTP_TIMEOUT"
    LATENCY_SLO_BREACH = "LATENCY_SLO_BREACH"
    ERROR_RATE_SLO_BREACH = "ERROR_RATE_SLO_BREACH"
    PROCESS_CRASH = "PROCESS_CRASH"
    RESTART_LOOP = "RESTART_LOOP"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    DATABASE_FAILURE = "DATABASE_FAILURE"
    WEBSOCKET_FAILURE = "WEBSOCKET_FAILURE"
    RESOURCE_EXHAUSTION = "RESOURCE_EXHAUSTION"
    CONFIGURATION_FAILURE = "CONFIGURATION_FAILURE"
    UNKNOWN_RUNTIME_FAILURE = "UNKNOWN_RUNTIME_FAILURE"


class ObservationProvenance(str, Enum):
    """Provenance distinguishing real execution from synthetic simulation."""
    REAL_RUNTIME_OBSERVATION = "REAL_RUNTIME_OBSERVATION"
    SIMULATED_SCENARIO = "SIMULATED_SCENARIO"
    REPLAY = "REPLAY"
    SYNTHETIC_BENCHMARK = "SYNTHETIC_BENCHMARK"


class RecoveryStrategy(str, Enum):
    """Allowed Remediation Strategies."""
    RESTART_PROCESS = "RESTART_PROCESS"
    RECONNECT_DEPENDENCY = "RECONNECT_DEPENDENCY"
    CLEAR_TRANSIENT_STATE = "CLEAR_TRANSIENT_STATE"
    RELOAD_CONFIGURATION = "RELOAD_CONFIGURATION"
    ROLLBACK_RELEASE = "ROLLBACK_RELEASE"
    RESTORE_CHECKPOINT = "RESTORE_CHECKPOINT"
    DISABLE_DEGRADED_FEATURE = "DISABLE_DEGRADED_FEATURE"
    ESCALATE_HUMAN = "ESCALATE_HUMAN"


class RemediationSafety(str, Enum):
    """Remediation action safety authorization."""
    ALLOWED = "ALLOWED"
    HIGH_RISK_WITHOUT_APPROVAL = "HIGH_RISK_WITHOUT_APPROVAL"
    FORBIDDEN = "FORBIDDEN"


class RemediationStage(str, Enum):
    """Remediation execution lifecycle stages."""
    PRECHECK = "PRECHECK"
    SNAPSHOT = "SNAPSHOT"
    EXECUTE = "EXECUTE"
    VERIFY = "VERIFY"
    COMMIT = "COMMIT"
    ROLLBACK = "ROLLBACK"


class VerificationStatus(str, Enum):
    """Post-Recovery Verification Outcome."""
    RECOVERY_VERIFIED = "RECOVERY_VERIFIED"
    RECOVERY_FAILED = "RECOVERY_FAILED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class EscalationState(str, Enum):
    """Target Escalation Categories."""
    HUMAN_REVIEW = "HUMAN_REVIEW"
    INFRASTRUCTURE_REQUIRED = "INFRASTRUCTURE_REQUIRED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    RECOVERY_EXHAUSTED = "RECOVERY_EXHAUSTED"


class RuntimeTarget(str, Enum):
    """Execution Target Environment Classification."""
    LOCAL_RUNTIME = "LOCAL_RUNTIME"
    DEPLOYMENT_TARGET = "DEPLOYMENT_TARGET"
    PRODUCTION_TARGET = "PRODUCTION_TARGET"


class RootCauseStatus(str, Enum):
    """Status of Root Cause Hypotheses."""
    OBSERVED = "OBSERVED"
    SUPPORTED = "SUPPORTED"
    UNCERTAIN = "UNCERTAIN"
    REJECTED = "REJECTED"


# ---------------------------------------------------------------------------
# Data Contracts
# ---------------------------------------------------------------------------

@dataclass
class RuntimeObservation:
    """Normalized runtime observation entity."""
    process_id: str
    service_id: str
    environment: str
    state: OperationalState
    latency_ms: float
    error_rate: float
    availability: float
    health_status: HealthStatus
    cpu: float
    memory: float
    restart_count: int
    dependency_status: Dict[str, str]
    evidence_id: str = field(default_factory=lambda: f"evd-obs-{uuid.uuid4().hex[:8]}")
    provenance: ObservationProvenance = ObservationProvenance.REAL_RUNTIME_OBSERVATION
    status: ObservationStatus = ObservationStatus.OBSERVED
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "process_id": self.process_id,
            "service_id": self.service_id,
            "environment": self.environment,
            "state": self.state.value if isinstance(self.state, Enum) else str(self.state),
            "latency_ms": self.latency_ms,
            "error_rate": self.error_rate,
            "availability": self.availability,
            "health_status": self.health_status.value if isinstance(self.health_status, Enum) else str(self.health_status),
            "cpu": self.cpu,
            "memory": self.memory,
            "restart_count": self.restart_count,
            "dependency_status": dict(self.dependency_status),
            "evidence_id": self.evidence_id,
            "provenance": self.provenance.value if isinstance(self.provenance, Enum) else str(self.provenance),
            "status": self.status.value if isinstance(self.status, Enum) else str(self.status),
            "timestamp": self.timestamp,
        }


@dataclass
class HealthCheckResult:
    """Individual health check evaluation outcome."""
    check_name: str
    service_id: str
    status: HealthStatus
    details: str
    duration_ms: float
    evidence_id: str = field(default_factory=lambda: f"evd-hc-{uuid.uuid4().hex[:8]}")
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_name": self.check_name,
            "service_id": self.service_id,
            "status": self.status.value if isinstance(self.status, Enum) else str(self.status),
            "details": self.details,
            "duration_ms": self.duration_ms,
            "evidence_id": self.evidence_id,
            "timestamp": self.timestamp,
        }


@dataclass
class SLOEvaluation:
    """SLI/SLO threshold comparison result."""
    metric: str
    threshold: float
    observed_value: float
    window_seconds: int
    status: SLOStatus
    service_id: str
    evidence_id: str = field(default_factory=lambda: f"evd-slo-{uuid.uuid4().hex[:8]}")
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "threshold": self.threshold,
            "observed_value": self.observed_value,
            "window_seconds": self.window_seconds,
            "status": self.status.value if isinstance(self.status, Enum) else str(self.status),
            "service_id": self.service_id,
            "evidence_id": self.evidence_id,
            "timestamp": self.timestamp,
        }


@dataclass
class Incident:
    """Detected operational incident entity."""
    incident_id: str
    service: str
    category: IncidentCategory
    severity: SeverityLevel
    confidence: float
    correlation_key: str
    evidence: List[str]
    rule_triggered: str
    description: str
    detection_time: float = field(default_factory=time.time)
    parent_incident_id: Optional[str] = None
    resolved: bool = False
    resolution_time: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "service": self.service,
            "category": self.category.value if isinstance(self.category, Enum) else str(self.category),
            "severity": self.severity.value if isinstance(self.severity, Enum) else str(self.severity),
            "confidence": self.confidence,
            "correlation_key": self.correlation_key,
            "evidence": list(self.evidence),
            "rule_triggered": self.rule_triggered,
            "description": self.description,
            "detection_time": self.detection_time,
            "parent_incident_id": self.parent_incident_id,
            "resolved": self.resolved,
            "resolution_time": self.resolution_time,
        }


@dataclass
class IncidentCorrelation:
    """Correlation group grouping multiple symptoms to an observed incident."""
    correlation_key: str
    primary_incident_id: str
    correlated_incident_ids: List[str]
    root_cause_service: str
    causal_evidence: List[str]
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "correlation_key": self.correlation_key,
            "primary_incident_id": self.primary_incident_id,
            "correlated_incident_ids": list(self.correlated_incident_ids),
            "root_cause_service": self.root_cause_service,
            "causal_evidence": list(self.causal_evidence),
            "created_at": self.created_at,
        }


@dataclass
class RootCauseHypothesis:
    """Hypothesis regarding incident root cause backed by empirical evidence."""
    hypothesis_id: str
    incident_id: str
    hypothesis: str
    supporting_evidence: List[str]
    contradicting_evidence: List[str]
    confidence: float
    status: RootCauseStatus
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "incident_id": self.incident_id,
            "hypothesis": self.hypothesis,
            "supporting_evidence": list(self.supporting_evidence),
            "contradicting_evidence": list(self.contradicting_evidence),
            "confidence": self.confidence,
            "status": self.status.value if isinstance(self.status, Enum) else str(self.status),
            "created_at": self.created_at,
        }


@dataclass
class RecoveryPlan:
    """Planned operational recovery action."""
    plan_id: str
    incident_id: str
    strategy: RecoveryStrategy
    safety: RemediationSafety
    preconditions: List[str]
    expected_effect: str
    risk_level: str
    required_evidence: List[str]
    rollback_action: Optional[str]
    verification_plan: List[str]
    authorized_by_policy: bool
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "incident_id": self.incident_id,
            "strategy": self.strategy.value if isinstance(self.strategy, Enum) else str(self.strategy),
            "safety": self.safety.value if isinstance(self.safety, Enum) else str(self.safety),
            "preconditions": list(self.preconditions),
            "expected_effect": self.expected_effect,
            "risk_level": self.risk_level,
            "required_evidence": list(self.required_evidence),
            "rollback_action": self.rollback_action,
            "verification_plan": list(self.verification_plan),
            "authorized_by_policy": self.authorized_by_policy,
            "created_at": self.created_at,
        }


@dataclass
class RemediationExecution:
    """Safe remediation execution trace across 5 lifecycle stages."""
    execution_id: str
    plan_id: str
    stage: RemediationStage
    success: bool
    precheck_passed: bool
    snapshot_hash: Optional[str]
    actions_executed: List[str]
    verification_passed: bool
    details: str
    executed_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "plan_id": self.plan_id,
            "stage": self.stage.value if isinstance(self.stage, Enum) else str(self.stage),
            "success": self.success,
            "precheck_passed": self.precheck_passed,
            "snapshot_hash": self.snapshot_hash,
            "actions_executed": list(self.actions_executed),
            "verification_passed": self.verification_passed,
            "details": self.details,
            "executed_at": self.executed_at,
        }


@dataclass
class RollbackCertificate:
    """Cryptographic certificate proving rollback execution and integrity."""
    certificate_id: str
    source_release: str
    target_release: str
    pre_rollback_hash: str
    post_rollback_hash: str
    verified: bool
    evidence: List[str]
    issued_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "certificate_id": self.certificate_id,
            "source_release": self.source_release,
            "target_release": self.target_release,
            "pre_rollback_hash": self.pre_rollback_hash,
            "post_rollback_hash": self.post_rollback_hash,
            "verified": self.verified,
            "evidence": list(self.evidence),
            "issued_at": self.issued_at,
        }


@dataclass
class RecoveryVerification:
    """Post-remediation stability verification record."""
    verification_id: str
    incident_id: str
    status: VerificationStatus
    stability_window_seconds: int
    healthchecks_passed: int
    healthchecks_failed: int
    slo_evaluations: List[Dict[str, Any]]
    details: str
    verified_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verification_id": self.verification_id,
            "incident_id": self.incident_id,
            "status": self.status.value if isinstance(self.status, Enum) else str(self.status),
            "stability_window_seconds": self.stability_window_seconds,
            "healthchecks_passed": self.healthchecks_passed,
            "healthchecks_failed": self.healthchecks_failed,
            "slo_evaluations": list(self.slo_evaluations),
            "details": self.details,
            "verified_at": self.verified_at,
        }


@dataclass
class EscalationTicket:
    """Escalation generated when autonomous recovery cannot proceed safely."""
    ticket_id: str
    incident_id: str
    state: EscalationState
    reason: str
    risk_level: str
    suggested_actions: List[str]
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "incident_id": self.incident_id,
            "state": self.state.value if isinstance(self.state, Enum) else str(self.state),
            "reason": self.reason,
            "risk_level": self.risk_level,
            "suggested_actions": list(self.suggested_actions),
            "created_at": self.created_at,
        }


@dataclass
class LedgerEntry:
    """Append-only ledger record cryptographically chained."""
    event_id: str
    parent_event: Optional[str]
    event_type: str
    evidence_ids: List[str]
    state_before: str
    action: str
    state_after: str
    entry_hash: str
    timestamp: float = field(default_factory=time.time)
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "parent_event": self.parent_event,
            "event_type": self.event_type,
            "evidence_ids": list(self.evidence_ids),
            "state_before": self.state_before,
            "action": self.action,
            "state_after": self.state_after,
            "entry_hash": self.entry_hash,
            "timestamp": self.timestamp,
            "payload": dict(self.payload),
        }


@dataclass
class ProductionDecision:
    """High-level operational governance decision."""
    decision_id: str
    service_id: str
    current_state: OperationalState
    recommended_action: str  # CONTINUE, RECOVER, ROLLBACK, ESCALATE
    active_incidents: List[str]
    autonomous_remediation_allowed: bool
    remediation_plan_id: Optional[str]
    escalation_ticket_id: Optional[str]
    rationale: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "service_id": self.service_id,
            "current_state": self.current_state.value if isinstance(self.current_state, Enum) else str(self.current_state),
            "recommended_action": self.recommended_action,
            "active_incidents": list(self.active_incidents),
            "autonomous_remediation_allowed": self.autonomous_remediation_allowed,
            "remediation_plan_id": self.remediation_plan_id,
            "escalation_ticket_id": self.escalation_ticket_id,
            "rationale": self.rationale,
            "timestamp": self.timestamp,
        }
