"""
JARVIS OS — Phase 68: Engineering Quality Governance & Autonomous Quality Debt Management
Domain models, enums, dataclasses, and immutable records.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class QualityDimension(str, Enum):
    ARCHITECTURE = "ARCHITECTURE"
    CODE = "CODE"
    TEST = "TEST"
    CONTRACT = "CONTRACT"
    BEHAVIOR = "BEHAVIOR"
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    RELIABILITY = "RELIABILITY"
    MAINTAINABILITY = "MAINTAINABILITY"


class ObservationType(str, Enum):
    OBSERVED = "OBSERVED"
    ESTIMATED = "ESTIMATED"
    INFERRED = "INFERRED"


class DimensionChange(str, Enum):
    IMPROVED = "IMPROVED"
    DEGRADED = "DEGRADED"
    UNCHANGED = "UNCHANGED"
    UNCERTAIN = "UNCERTAIN"


class DimensionStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"
    BLOCKED = "BLOCKED"
    STABLE = "STABLE"


class DebtCategory(str, Enum):
    ARCHITECTURAL = "ARCHITECTURAL"
    CODE = "CODE"
    TEST = "TEST"
    CONTRACT = "CONTRACT"
    BEHAVIOR = "BEHAVIOR"
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    DOCUMENTATION = "DOCUMENTATION"
    OPERATIONAL = "OPERATIONAL"


class DebtStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    DEFERRED = "DEFERRED"
    INVALIDATED = "INVALIDATED"
    UNKNOWN = "UNKNOWN"


class DebtSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class QualityGateStatus(str, Enum):
    QUALITY_ACCEPTED = "QUALITY_ACCEPTED"
    QUALITY_ACCEPTED_WITH_DEBT = "QUALITY_ACCEPTED_WITH_DEBT"
    QUALITY_REVIEW_REQUIRED = "QUALITY_REVIEW_REQUIRED"
    QUALITY_BLOCKED = "QUALITY_BLOCKED"
    QUALITY_INCONCLUSIVE = "QUALITY_INCONCLUSIVE"


class QualityRegressionLevel(str, Enum):
    CRITICAL = "CRITICAL"
    SIGNIFICANT = "SIGNIFICANT"
    MINOR = "MINOR"
    UNCERTAIN = "UNCERTAIN"


class QualityTrendDirection(str, Enum):
    IMPROVING = "IMPROVING"
    STABLE = "STABLE"
    DEGRADING = "DEGRADING"
    VOLATILE = "VOLATILE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass
class QualityObservation:
    dimension: QualityDimension
    metric_name: str
    measured_value: Any
    evidence: Dict[str, Any] = field(default_factory=dict)
    uncertainty: float = 0.0  # 0.0 (certain) to 1.0 (completely uncertain)
    scope: str = "global"
    observation_type: ObservationType = ObservationType.OBSERVED
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension.value if isinstance(self.dimension, QualityDimension) else str(self.dimension),
            "metric_name": self.metric_name,
            "measured_value": self.measured_value,
            "evidence": self.evidence,
            "uncertainty": self.uncertainty,
            "scope": self.scope,
            "observation_type": self.observation_type.value if isinstance(self.observation_type, ObservationType) else str(self.observation_type),
            "timestamp": self.timestamp,
        }


@dataclass
class DimensionEvaluation:
    dimension: QualityDimension
    observations: List[QualityObservation] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    uncertainty: float = 0.0
    scope: str = "global"
    status: DimensionStatus = DimensionStatus.HEALTHY
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension.value if isinstance(self.dimension, QualityDimension) else str(self.dimension),
            "observations": [o.to_dict() for o in self.observations],
            "evidence": self.evidence,
            "uncertainty": self.uncertainty,
            "scope": self.scope,
            "status": self.status.value if isinstance(self.status, DimensionStatus) else str(self.status),
            "summary": self.summary,
        }


@dataclass
class QualitySnapshot:
    snapshot_id: str
    mission_id: str
    architecture_hash: str
    contract_hash: str
    behavior_hash: str
    test_hash: str
    security_hash: str
    timestamp: float = field(default_factory=time.time)
    provenance: Dict[str, Any] = field(default_factory=dict)
    dimensions: Dict[str, DimensionEvaluation] = field(default_factory=dict)
    sealed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "mission_id": self.mission_id,
            "architecture_hash": self.architecture_hash,
            "contract_hash": self.contract_hash,
            "behavior_hash": self.behavior_hash,
            "test_hash": self.test_hash,
            "security_hash": self.security_hash,
            "timestamp": self.timestamp,
            "provenance": self.provenance,
            "dimensions": {k: v.to_dict() for k, v in self.dimensions.items()},
            "sealed": self.sealed,
        }


@dataclass
class QualityDelta:
    baseline_snapshot_id: str
    after_snapshot_id: str
    mission_id: str
    dimension_changes: Dict[str, DimensionChange] = field(default_factory=dict)
    evidence_efficiency: float = 1.0
    more_tests: bool = False
    more_useful_evidence: bool = False
    degradations: List[Dict[str, Any]] = field(default_factory=list)
    improvements: List[Dict[str, Any]] = field(default_factory=list)
    uncertainty_delta: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "baseline_snapshot_id": self.baseline_snapshot_id,
            "after_snapshot_id": self.after_snapshot_id,
            "mission_id": self.mission_id,
            "dimension_changes": {
                k: v.value if isinstance(v, DimensionChange) else str(v)
                for k, v in self.dimension_changes.items()
            },
            "evidence_efficiency": self.evidence_efficiency,
            "more_tests": self.more_tests,
            "more_useful_evidence": self.more_useful_evidence,
            "degradations": self.degradations,
            "improvements": self.improvements,
            "uncertainty_delta": self.uncertainty_delta,
            "timestamp": self.timestamp,
        }


@dataclass
class TechnicalDebtItem:
    debt_id: str
    category: DebtCategory
    affected_surface: str
    origin_mission: str
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    severity: DebtSeverity = DebtSeverity.MEDIUM
    confidence: float = 0.8
    estimated_cost: float = 1.0  # arbitrary relative effort units
    risk: float = 0.5  # 0.0 to 1.0
    age: float = 0.0  # seconds or missions
    dependencies: List[str] = field(default_factory=list)
    resolution_options: List[str] = field(default_factory=list)
    status: DebtStatus = DebtStatus.OPEN
    recurrence_count: int = 1
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "debt_id": self.debt_id,
            "category": self.category.value if isinstance(self.category, DebtCategory) else str(self.category),
            "affected_surface": self.affected_surface,
            "origin_mission": self.origin_mission,
            "evidence": self.evidence,
            "severity": self.severity.value if isinstance(self.severity, DebtSeverity) else str(self.severity),
            "confidence": self.confidence,
            "estimated_cost": self.estimated_cost,
            "risk": self.risk,
            "age": self.age,
            "dependencies": self.dependencies,
            "resolution_options": self.resolution_options,
            "status": self.status.value if isinstance(self.status, DebtStatus) else str(self.status),
            "recurrence_count": self.recurrence_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class DebtEvent:
    event_id: str
    debt_id: str
    event_type: str  # "CREATED", "STATUS_CHANGED", "RECURRENCE_INCREMENTED", "SEVERITY_UPDATED"
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "debt_id": self.debt_id,
            "event_type": self.event_type,
            "details": self.details,
            "timestamp": self.timestamp,
        }


@dataclass
class PriorityVector:
    debt_id: str
    risk: float
    impact: float
    recurrence: float
    remediation_cost: float
    affected_missions: int
    security_relevance: float
    reversibility: float
    evidence_strength: float
    rank_score: float  # Multi-criteria combined rank (for sorting, not authority)
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "debt_id": self.debt_id,
            "risk": self.risk,
            "impact": self.impact,
            "recurrence": self.recurrence,
            "remediation_cost": self.remediation_cost,
            "affected_missions": self.affected_missions,
            "security_relevance": self.security_relevance,
            "reversibility": self.reversibility,
            "evidence_strength": self.evidence_strength,
            "rank_score": self.rank_score,
            "explanation": self.explanation,
        }


@dataclass
class QualityBudget:
    max_critical_debt: int = 0
    max_unresolved_contract_drift: int = 0
    max_security_debt: int = 0
    max_flaky_rate: float = 0.05
    max_regression_rate: float = 0.02
    max_architecture_degradation: int = 0
    max_quality_uncertainty: float = 0.35
    max_human_review_backlog: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QualityGateDecision:
    decision: QualityGateStatus
    scope: str
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    degradations: List[Dict[str, Any]] = field(default_factory=list)
    improvements: List[Dict[str, Any]] = field(default_factory=list)
    debt: List[Dict[str, Any]] = field(default_factory=list)
    uncertainty: float = 0.0
    policy: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value if isinstance(self.decision, QualityGateStatus) else str(self.decision),
            "scope": self.scope,
            "evidence": self.evidence,
            "degradations": self.degradations,
            "improvements": self.improvements,
            "debt": self.debt,
            "uncertainty": self.uncertainty,
            "policy": self.policy,
            "timestamp": self.timestamp,
        }


@dataclass
class QualityHotspotItem:
    entity_type: str  # "file", "symbol", "module", "service", "contract", "agent", "mission"
    entity_name: str
    failure_count: int = 0
    regression_count: int = 0
    debt_count: int = 0
    review_count: int = 0
    rollback_count: int = 0
    flakiness_score: float = 0.0
    risk_weight: float = 0.0
    evidence: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_name": self.entity_name,
            "failure_count": self.failure_count,
            "regression_count": self.regression_count,
            "debt_count": self.debt_count,
            "review_count": self.review_count,
            "rollback_count": self.rollback_count,
            "flakiness_score": self.flakiness_score,
            "risk_weight": self.risk_weight,
            "evidence": self.evidence,
        }


@dataclass
class AgentQualityRecord:
    agent_id: str
    intent_id: str
    mission_id: str
    workspace: str
    regressions_count: int = 0
    rollbacks_count: int = 0
    debt_items_count: int = 0
    conflicts_count: int = 0
    merges_successful: int = 0
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MissionQualityRecord:
    mission_id: str
    baseline_id: str
    after_id: str
    gate_decision: QualityGateStatus
    completion_status: str
    unresolved_debt_count: int
    quality_improved: bool
    evidence_efficiency: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "baseline_id": self.baseline_id,
            "after_id": self.after_id,
            "gate_decision": self.gate_decision.value if isinstance(self.gate_decision, QualityGateStatus) else str(self.gate_decision),
            "completion_status": self.completion_status,
            "unresolved_debt_count": self.unresolved_debt_count,
            "quality_improved": self.quality_improved,
            "evidence_efficiency": self.evidence_efficiency,
            "timestamp": self.timestamp,
        }
