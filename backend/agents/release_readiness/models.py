"""
Release Readiness Models
Phase 70 — Autonomous Release Readiness & Production Governance

Comprehensive domain definitions, data models, state machines, and risk structures
for release candidate assessment and production gate decisions.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
import time


class ReleaseCandidateState(str, Enum):
    """Lifecycle states of a ReleaseCandidate."""
    CREATED = "CREATED"
    ANALYZING = "ANALYZING"
    VALIDATING = "VALIDATING"
    READY = "READY"
    READY_WITH_RISK = "READY_WITH_RISK"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    BLOCKED = "BLOCKED"
    NOT_READY = "NOT_READY"
    REJECTED = "REJECTED"
    RELEASED = "RELEASED"
    ROLLED_BACK = "ROLLED_BACK"


class ArchitectureClassification(str, Enum):
    """Architecture health assessment classifications."""
    HEALTHY = "HEALTHY"
    DEGRADED_ACCEPTABLE = "DEGRADED_ACCEPTABLE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class ContractReadinessStatus(str, Enum):
    """Contract compatibility assessment status."""
    COMPATIBLE = "COMPATIBLE"
    BREAKING = "BREAKING"
    MIGRATED = "MIGRATED"
    DRIFT_DETECTED = "DRIFT_DETECTED"
    UNKNOWN = "UNKNOWN"


class BehaviorReadinessStatus(str, Enum):
    """Behavioral preservation and invariant adherence status."""
    PRESERVED_WITHIN_SCOPE = "PRESERVED_WITHIN_SCOPE"
    POTENTIAL_DRIFT = "POTENTIAL_DRIFT"
    INCOMPATIBLE = "INCOMPATIBLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class PerformanceClassification(str, Enum):
    """Performance evaluation against baseline."""
    IMPROVED = "IMPROVED"
    WITHIN_BUDGET = "WITHIN_BUDGET"
    DEGRADED = "DEGRADED"
    CRITICAL_DEGRADATION = "CRITICAL_DEGRADATION"
    UNKNOWN = "UNKNOWN"


class MetricNature(str, Enum):
    """Epistemic nature of a performance or health metric."""
    OBSERVED = "observed"
    ESTIMATED = "estimated"
    INFERRED = "inferred"


class RuntimeHealthStatus(str, Enum):
    """Operational runtime health classifications."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ObservabilityStatus(str, Enum):
    """Readiness of operational telemetry and logging."""
    READY = "READY"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"


class DependencyStatus(str, Enum):
    """Dependency resolvability and integrity status."""
    READY = "READY"
    RESOLVABLE_WITH_WARNINGS = "RESOLVABLE_WITH_WARNINGS"
    INCOMPATIBLE = "INCOMPATIBLE"
    MISSING_PACKAGES = "MISSING_PACKAGES"
    UNRESOLVABLE = "UNRESOLVABLE"


class ConfigurationStatus(str, Enum):
    """Environment and configuration safety status."""
    READY = "READY"
    MISSING = "MISSING"
    UNSAFE = "UNSAFE"
    UNKNOWN = "UNKNOWN"


class RollbackReadinessStatus(str, Enum):
    """Readiness and verification of rollback procedures."""
    ROLLBACK_READY = "ROLLBACK_READY"
    ROLLBACK_PARTIAL = "ROLLBACK_PARTIAL"
    ROLLBACK_UNVERIFIED = "ROLLBACK_UNVERIFIED"
    ROLLBACK_BLOCKED = "ROLLBACK_BLOCKED"


class CanaryPolicyType(str, Enum):
    """Canary deployment strategies."""
    DISABLED = "DISABLED"
    SIMULATED = "SIMULATED"
    LOCAL = "LOCAL"
    REAL = "REAL"


class ReleaseGateDecisionState(str, Enum):
    """Final release gate decision states."""
    RELEASE_READY = "RELEASE_READY"
    RELEASE_READY_WITH_RISK = "RELEASE_READY_WITH_RISK"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    NOT_READY = "NOT_READY"
    BLOCKED = "BLOCKED"
    DEPLOYMENT_NOT_AVAILABLE = "DEPLOYMENT_NOT_AVAILABLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class RiskDimension(str, Enum):
    """Dimensions evaluated in the release risk vector."""
    SECURITY = "security"
    QUALITY = "quality"
    ARCHITECTURE = "architecture"
    BEHAVIOR = "behavior"
    CONTRACT = "contract"
    PERFORMANCE = "performance"
    RUNTIME = "runtime"
    CONFIGURATION = "configuration"
    DEPENDENCY = "dependency"
    ROLLBACK = "rollback"
    OBSERVABILITY = "observability"


class BlockerCategory(str, Enum):
    """Explicit blocker categories for release denial."""
    CRITICAL_SECURITY = "critical_security_violation"
    UNSAFE_CONFIGURATION = "unsafe_configuration"
    BREAKING_CONTRACT = "breaking_contract_without_migration"
    INCOMPATIBLE_BEHAVIOR = "unresolved_incompatible_behavior"
    MISSING_ROLLBACK = "missing_rollback_when_required"
    SEVERE_PERFORMANCE_REGRESSION = "severe_performance_regression"
    CRITICAL_HEALTH_FAILURE = "critical_health_failure"
    MISSING_MANDATORY_EVIDENCE = "missing_mandatory_evidence"
    DEPENDENCY_FAILURE = "dependency_failure"
    QUALITY_GATE_BLOCKED = "quality_gate_blocked"
    UNRESOLVED_RESIDUAL_STATE = "unresolved_residual_state"


@dataclass
class RiskVectorItem:
    """Individual dimension score within release risk vector."""
    dimension: str
    value: float  # 0.0 (safe) to 1.0 (extreme risk)
    confidence: float  # 0.0 (unconfirmed) to 1.0 (fully verified)
    evidence: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "value": round(self.value, 4),
            "confidence": round(self.confidence, 4),
            "evidence": self.evidence
        }


@dataclass
class ReleaseRiskVector:
    """Multi-dimensional risk vector without forced aggregation."""
    dimensions: Dict[str, RiskVectorItem] = field(default_factory=dict)
    overall_risk_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimensions": {k: v.to_dict() for k, v in self.dimensions.items()},
            "overall_risk_score": round(self.overall_risk_score, 4) if self.overall_risk_score is not None else None
        }


@dataclass
class ReleaseBlocker:
    """Explicit blocker preventing candidate release."""
    blocker_id: str
    category: BlockerCategory
    description: str
    evidence: str
    severity: str = "CRITICAL"
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "blocker_id": self.blocker_id,
            "category": self.category.value if isinstance(self.category, BlockerCategory) else str(self.category),
            "description": self.description,
            "evidence": self.evidence,
            "severity": self.severity,
            "timestamp": self.timestamp
        }


@dataclass
class HumanReviewTicket:
    """Mandatory review ticket generated when human signoff is required."""
    ticket_id: str
    candidate_id: str
    reason: str
    evidence: Dict[str, Any]
    timeout_seconds: float = 3600.0
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    status: str = "PENDING"  # PENDING, APPROVED, REJECTED, TIMED_OUT
    decision_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "candidate_id": self.candidate_id,
            "reason": self.reason,
            "evidence": self.evidence,
            "timeout_seconds": self.timeout_seconds,
            "created_at": self.created_at,
            "status": self.status,
            "decision_notes": self.decision_notes
        }


@dataclass
class ReleaseBaseline:
    """Immutable capture of all 13 project dimensions prior to evaluation."""
    baseline_id: str
    architecture_hash: str
    contract_hash: str
    behavior_hash: str
    quality_snapshot: Dict[str, Any]
    technical_debt_snapshot: Dict[str, Any]
    test_results: Dict[str, Any]
    security_state: Dict[str, Any]
    performance_baseline: Dict[str, Any]
    runtime_baseline: Dict[str, Any]
    configuration_baseline: Dict[str, Any]
    dependency_baseline: Dict[str, Any]
    observability_baseline: Dict[str, Any]
    rollback_baseline: Dict[str, Any]
    captured_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    immutable_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "baseline_id": self.baseline_id,
            "architecture_hash": self.architecture_hash,
            "contract_hash": self.contract_hash,
            "behavior_hash": self.behavior_hash,
            "quality_snapshot": self.quality_snapshot,
            "technical_debt_snapshot": self.technical_debt_snapshot,
            "test_results": self.test_results,
            "security_state": self.security_state,
            "performance_baseline": self.performance_baseline,
            "runtime_baseline": self.runtime_baseline,
            "configuration_baseline": self.configuration_baseline,
            "dependency_baseline": self.dependency_baseline,
            "observability_baseline": self.observability_baseline,
            "rollback_baseline": self.rollback_baseline,
            "captured_at": self.captured_at,
            "immutable_hash": self.immutable_hash
        }


@dataclass
class ReleaseCandidate:
    """The subject undergoing release qualification."""
    release_id: str
    mission_id: str
    commit_sha: str
    workspace_snapshot: str
    artifact_hashes: Dict[str, str]
    version: str
    environment: str
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    provenance: Dict[str, Any] = field(default_factory=dict)
    state: ReleaseCandidateState = ReleaseCandidateState.CREATED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "release_id": self.release_id,
            "mission_id": self.mission_id,
            "commit_sha": self.commit_sha,
            "workspace_snapshot": self.workspace_snapshot,
            "artifact_hashes": self.artifact_hashes,
            "version": self.version,
            "environment": self.environment,
            "created_at": self.created_at,
            "provenance": self.provenance,
            "state": self.state.value if isinstance(self.state, ReleaseCandidateState) else str(self.state)
        }


@dataclass
class ReleasePlanStep:
    """Step in the ReleasePlan DAG."""
    step_id: str
    name: str
    status: str = "PENDING"  # PENDING, IN_PROGRESS, COMPLETED, FAILED, SKIPPED
    depends_on: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "status": self.status,
            "depends_on": self.depends_on,
            "metadata": self.metadata
        }


@dataclass
class ReleasePlan:
    """Execution DAG for release rollout."""
    plan_id: str
    candidate_id: str
    steps: List[ReleasePlanStep] = field(default_factory=list)
    current_step_index: int = 0
    status: str = "PENDING"  # PENDING, EXECUTING, COMPLETED, ROLLED_BACK, ABORTED
    deployment_available: bool = False
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "candidate_id": self.candidate_id,
            "steps": [s.to_dict() for s in self.steps],
            "current_step_index": self.current_step_index,
            "status": self.status,
            "deployment_available": self.deployment_available,
            "created_at": self.created_at
        }


@dataclass
class ReleaseGateDecision:
    """Comprehensive decision payload emitted by the release gate."""
    decision_id: str
    candidate_id: str
    state: ReleaseGateDecisionState
    risk_vector: ReleaseRiskVector
    blockers: List[ReleaseBlocker]
    human_review_ticket: Optional[HumanReviewTicket]
    domain_summaries: Dict[str, Any]
    evidence_ledger: List[Dict[str, Any]]
    provenance_hash: str
    evaluated_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    allowed_to_release: bool = False

    def to_dict(self) -> Dict[str, Any]:
        def _sanitize(obj: Any) -> Any:
            if hasattr(obj, "to_dict") and callable(obj.to_dict):
                return obj.to_dict()
            elif isinstance(obj, list):
                return [_sanitize(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: _sanitize(v) for k, v in obj.items()}
            elif hasattr(obj, "value"):
                return obj.value
            return obj

        return {
            "decision_id": self.decision_id,
            "candidate_id": self.candidate_id,
            "state": self.state.value if isinstance(self.state, ReleaseGateDecisionState) else str(self.state),
            "risk_vector": self.risk_vector.to_dict(),
            "blockers": [b.to_dict() for b in self.blockers],
            "human_review_ticket": self.human_review_ticket.to_dict() if self.human_review_ticket else None,
            "domain_summaries": _sanitize(self.domain_summaries),
            "evidence_ledger": self.evidence_ledger,
            "provenance_hash": self.provenance_hash,
            "evaluated_at": self.evaluated_at,
            "allowed_to_release": self.allowed_to_release
        }
