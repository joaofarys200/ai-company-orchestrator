"""
JARVIS OS — Phase 46: Contract Drift Detection & Continuous Contract Governance
Core Data Models, Enums, Serialization, and Invariant Definitions.

Invariants:
1. Baseline contract is IMMUTABLE.
2. Runtime observation NEVER directly mutates a verified contract.
3. Drift classification is DETERMINISTIC.
4. Tri-state separation: CONTRACT != CURRENT RUNTIME BEHAVIOR != OBSERVED VARIATION.
5. Environments (DEV, STAGING, PROD) are isolated.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import enum
import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Set

from agents.runtime_discovery.models import RuntimeObservation


class ContractDriftStatus(str, enum.Enum):
    IN_SYNC = "IN_SYNC"
    NON_BREAKING_DRIFT = "NON_BREAKING_DRIFT"
    POTENTIALLY_BREAKING_DRIFT = "POTENTIALLY_BREAKING_DRIFT"
    BREAKING_DRIFT = "BREAKING_DRIFT"
    UNCERTAIN_DRIFT = "UNCERTAIN_DRIFT"


class DriftClassification(str, enum.Enum):
    NON_BREAKING = "NON_BREAKING"
    POTENTIALLY_BREAKING = "POTENTIALLY_BREAKING"
    BREAKING = "BREAKING"
    UNCERTAIN = "UNCERTAIN"


class DriftType(str, enum.Enum):
    FIELD_ADDED = "FIELD_ADDED"
    FIELD_REMOVED = "FIELD_REMOVED"
    TYPE_CHANGED = "TYPE_CHANGED"
    NULLABILITY_CHANGED = "NULLABILITY_CHANGED"
    REQUIREDNESS_CHANGED = "REQUIREDNESS_CHANGED"
    ENUM_CHANGED = "ENUM_CHANGED"
    STATUS_CHANGED = "STATUS_CHANGED"
    ROUTE_CHANGED = "ROUTE_CHANGED"
    METHOD_CHANGED = "METHOD_CHANGED"
    REQUEST_CHANGED = "REQUEST_CHANGED"
    RESPONSE_CHANGED = "RESPONSE_CHANGED"
    ERROR_CONTRACT_CHANGED = "ERROR_CONTRACT_CHANGED"
    AUTH_CONTRACT_CHANGED = "AUTH_CONTRACT_CHANGED"
    HEADER_CONTRACT_CHANGED = "HEADER_CONTRACT_CHANGED"
    UNKNOWN_VARIATION = "UNKNOWN_VARIATION"


class DriftPolicyAction(str, enum.Enum):
    IGNORE = "IGNORE"
    MONITOR = "MONITOR"
    REQUEST_VALIDATION = "REQUEST_VALIDATION"
    REQUEST_HUMAN = "REQUEST_HUMAN"
    BLOCK = "BLOCK"
    PROPOSE_NEW_VERSION = "PROPOSE_NEW_VERSION"


class TemporalStatus(str, enum.Enum):
    CURRENT = "CURRENT"
    AGING = "AGING"
    DRIFTING = "DRIFTING"
    STALE = "STALE"


class EnvironmentType(str, enum.Enum):
    DEVELOPMENT = "DEVELOPMENT"
    STAGING = "STAGING"
    LOCAL = "LOCAL"
    PRODUCTION = "PRODUCTION"


class VariationType(str, enum.Enum):
    ONE_OFF_VARIATION = "ONE_OFF_VARIATION"
    SYSTEMATIC_DRIFT = "SYSTEMATIC_DRIFT"
    CONTRACT_CHANGE = "CONTRACT_CHANGE"


class ConsumerImpactLevel(str, enum.Enum):
    DIRECT = "DIRECT"
    INDIRECT = "INDIRECT"
    POTENTIAL = "POTENTIAL"
    UNCERTAIN = "UNCERTAIN"


class DriftResolutionAction(str, enum.Enum):
    MONITOR = "MONITOR"
    REVALIDATE = "REVALIDATE"
    MIGRATE = "MIGRATE"
    UPDATE_CONSUMER = "UPDATE_CONSUMER"
    CREATE_NEW_VERSION = "CREATE_NEW_VERSION"
    ROLLBACK = "ROLLBACK"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class ContractBaseline:
    """Immutable baseline representation of a verified API contract.
    
    Any version evolution results in a new immutable ContractBaseline; 
    v1 is never mutated in-place.
    """
    contract_id: str
    version: str
    schema_hash: str
    route: str
    method: str
    request_schema: Dict[str, Any] = field(default_factory=dict)
    response_schema: Dict[str, Any] = field(default_factory=dict)
    error_contract: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)
    validated_at: float = field(default_factory=time.time)
    validated_by: str = "human_operator"
    semantic_graph_version: int = 1
    policy_version: str = "1.0.0"
    parent_version: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def compute_schema_hash(
        cls,
        request_schema: Dict[str, Any],
        response_schema: Dict[str, Any],
        error_contract: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Computes a deterministic sha256 hash over canonical representation of schemas."""
        payload = {
            "req": request_schema or {},
            "resp": response_schema or {},
            "err": error_contract or {},
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "version": self.version,
            "schema_hash": self.schema_hash,
            "route": self.route,
            "method": self.method,
            "request_schema": self.request_schema,
            "response_schema": self.response_schema,
            "error_contract": self.error_contract,
            "provenance": self.provenance,
            "validated_at": self.validated_at,
            "validated_by": self.validated_by,
            "semantic_graph_version": self.semantic_graph_version,
            "policy_version": self.policy_version,
            "parent_version": self.parent_version,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


@dataclass
class ObservationWindow:
    """Window of runtime observations scoped by environment, time, and sample limits."""
    window_id: str
    time_window_seconds: float = 3600.0
    min_sample_count: int = 3
    environment: EnvironmentType = EnvironmentType.PRODUCTION
    source: str = "all"
    version_context: Optional[str] = None
    observations: List[RuntimeObservation] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None

    @property
    def sample_count(self) -> int:
        return len(self.observations)

    def add_observation(self, observation: RuntimeObservation) -> None:
        """Adds an observation ensuring environmental isolation."""
        obs_env = observation.metadata.get("environment", EnvironmentType.PRODUCTION.value)
        if isinstance(obs_env, EnvironmentType):
            obs_env = obs_env.value
        if str(obs_env).upper() != self.environment.value:
            raise ValueError(
                f"Environment mismatch: cannot add observation from '{obs_env}' into window for '{self.environment.value}'"
            )
        self.observations.append(observation)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "window_id": self.window_id,
            "time_window_seconds": self.time_window_seconds,
            "min_sample_count": self.min_sample_count,
            "environment": self.environment.value if isinstance(self.environment, EnvironmentType) else str(self.environment),
            "source": self.source,
            "version_context": self.version_context,
            "sample_count": self.sample_count,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }


@dataclass
class DriftChange:
    """Atomic detail of a discrepancy observed between baseline and runtime traffic."""
    field_path: str
    drift_type: DriftType
    classification: DriftClassification
    baseline_value: Any
    observed_value: Any
    observed_frequency: float = 1.0  # 0.0 to 1.0
    baseline_frequency: float = 1.0
    sample_count: int = 1
    message: str = ""
    is_request: bool = False
    is_error: bool = False
    is_auth: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_path": self.field_path,
            "drift_type": self.drift_type.value if isinstance(self.drift_type, DriftType) else str(self.drift_type),
            "classification": self.classification.value if isinstance(self.classification, DriftClassification) else str(self.classification),
            "baseline_value": self.baseline_value,
            "observed_value": self.observed_value,
            "observed_frequency": round(self.observed_frequency, 4),
            "baseline_frequency": round(self.baseline_frequency, 4),
            "sample_count": self.sample_count,
            "message": self.message,
            "is_request": self.is_request,
            "is_error": self.is_error,
            "is_auth": self.is_auth,
        }


@dataclass
class ConsumerImpact:
    """Downstream consumer affected by contract drift, discovered via Semantic Graph."""
    consumer_id: str
    consumer_type: str  # "FRONTEND_COMPONENT", "BACKEND_SERVICE", "TASK", "TEST", "BROWSER_SCENARIO", "SEMANTIC_GRAPH_NODE"
    impact_level: ConsumerImpactLevel
    description: str
    affected_fields: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "consumer_id": self.consumer_id,
            "consumer_type": self.consumer_type,
            "impact_level": self.impact_level.value if isinstance(self.impact_level, ConsumerImpactLevel) else str(self.impact_level),
            "description": self.description,
            "affected_fields": self.affected_fields,
        }


@dataclass
class ContractDriftReport:
    """Consolidated contract drift detection and governance report."""
    drift_id: str
    contract_id: str
    baseline_version: str
    observed_version: str
    changes: List[DriftChange] = field(default_factory=list)
    classification: DriftClassification = DriftClassification.NON_BREAKING
    status: ContractDriftStatus = ContractDriftStatus.IN_SYNC
    variation_type: VariationType = VariationType.SYSTEMATIC_DRIFT
    evidence_refs: List[str] = field(default_factory=list)
    sample_count: int = 0
    confidence: float = 1.0
    affected_consumers: List[ConsumerImpact] = field(default_factory=list)
    affected_tasks: List[str] = field(default_factory=list)
    affected_graph_nodes: List[str] = field(default_factory=list)
    recommended_action: DriftPolicyAction = DriftPolicyAction.MONITOR
    environment: str = "PRODUCTION"
    temporal_status: TemporalStatus = TemporalStatus.CURRENT
    timestamp: float = field(default_factory=time.time)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "drift_id": self.drift_id,
            "contract_id": self.contract_id,
            "baseline_version": self.baseline_version,
            "observed_version": self.observed_version,
            "changes": [c.to_dict() for c in self.changes],
            "classification": self.classification.value if isinstance(self.classification, DriftClassification) else str(self.classification),
            "status": self.status.value if isinstance(self.status, ContractDriftStatus) else str(self.status),
            "variation_type": self.variation_type.value if isinstance(self.variation_type, VariationType) else str(self.variation_type),
            "evidence_refs": self.evidence_refs,
            "sample_count": self.sample_count,
            "confidence": round(self.confidence, 4),
            "affected_consumers": [c.to_dict() for c in self.affected_consumers],
            "affected_tasks": self.affected_tasks,
            "affected_graph_nodes": self.affected_graph_nodes,
            "recommended_action": self.recommended_action.value if isinstance(self.recommended_action, DriftPolicyAction) else str(self.recommended_action),
            "environment": self.environment,
            "temporal_status": self.temporal_status.value if isinstance(self.temporal_status, TemporalStatus) else str(self.temporal_status),
            "timestamp": self.timestamp,
            "notes": self.notes,
        }


@dataclass
class ProposedContractVersion:
    """Represents a proposed new contract version (e.g. v2) evolved from a baseline v1."""
    proposal_id: str
    contract_id: str
    parent_version: str
    new_version: str
    proposed_baseline: ContractBaseline
    diff_report: ContractDriftReport
    evidence_refs: List[str] = field(default_factory=list)
    affected_consumers: List[ConsumerImpact] = field(default_factory=list)
    migration_impact: str = ""
    approval_required: bool = True
    status: str = "PENDING_APPROVAL"  # "PENDING_APPROVAL", "APPROVED", "REJECTED", "ACTIVE", "ROLLED_BACK"
    approved_by: Optional[str] = None
    approval_notes: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "contract_id": self.contract_id,
            "parent_version": self.parent_version,
            "new_version": self.new_version,
            "proposed_baseline": self.proposed_baseline.to_dict(),
            "diff_report": self.diff_report.to_dict(),
            "evidence_refs": self.evidence_refs,
            "affected_consumers": [c.to_dict() for c in self.affected_consumers],
            "migration_impact": self.migration_impact,
            "approval_required": self.approval_required,
            "status": self.status,
            "approved_by": self.approved_by,
            "approval_notes": self.approval_notes,
            "created_at": self.created_at,
        }


@dataclass
class DriftResolution:
    """Formal audit record of how a drift event was resolved."""
    resolution_id: str
    drift_id: str
    contract_id: str
    action: DriftResolutionAction
    contract_version_before: str
    contract_version_after: str
    tasks: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    approved_by: Optional[str] = None
    outcome: str = "RESOLVED"
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resolution_id": self.resolution_id,
            "drift_id": self.drift_id,
            "contract_id": self.contract_id,
            "action": self.action.value if isinstance(self.action, DriftResolutionAction) else str(self.action),
            "contract_version_before": self.contract_version_before,
            "contract_version_after": self.contract_version_after,
            "tasks": self.tasks,
            "evidence": self.evidence,
            "approved_by": self.approved_by,
            "outcome": self.outcome,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
