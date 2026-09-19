"""
Phase 72 — Autonomous Reliability Intelligence & Preventive Operations
Models, Enums, and Canonical Data Structures.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ObservationSourceType(str, Enum):
    REAL_RUNTIME = "REAL_RUNTIME"
    CONTROLLED_FAULT_INJECTION = "CONTROLLED_FAULT_INJECTION"
    REPLAY = "REPLAY"
    SIMULATED = "SIMULATED"
    SYNTHETIC_BENCHMARK = "SYNTHETIC_BENCHMARK"


class MetricType(str, Enum):
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    AVAILABILITY = "availability"
    RESTARTS = "restarts"
    MEMORY = "memory"
    CPU = "cpu"
    DEPENDENCY_LATENCY = "dependency_latency"
    REQUEST_VOLUME = "request_volume"
    QUEUE_DEPTH = "queue_depth"
    WEBSOCKET_FAILURES = "websocket_failures"


class BaselineStatus(str, Enum):
    VALID = "VALID"
    WEAK = "WEAK"
    STALE = "STALE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class AnomalyStatus(str, Enum):
    NORMAL = "NORMAL"
    ANOMALOUS = "ANOMALOUS"
    UNKNOWN = "UNKNOWN"


class TrendStatus(str, Enum):
    IMPROVING = "IMPROVING"
    STABLE = "STABLE"
    DEGRADING = "DEGRADING"
    UNKNOWN = "UNKNOWN"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class RecurrenceStatus(str, Enum):
    FIRST_OCCURRENCE = "FIRST_OCCURRENCE"
    RECURRENT = "RECURRENT"
    ESCALATING_RECURRENCE = "ESCALATING_RECURRENCE"
    UNKNOWN = "UNKNOWN"


class CapacityStatus(str, Enum):
    SAFE = "SAFE"
    PRESSURE = "PRESSURE"
    RISK = "RISK"
    UNKNOWN = "UNKNOWN"


class PreventiveActionType(str, Enum):
    INCREASE_OBSERVATION_FREQUENCY = "increase_observation_frequency"
    RUN_ADDITIONAL_HEALTHCHECKS = "run_additional_healthchecks"
    PREFLIGHT_VALIDATION = "preflight_validation"
    ROLLBACK_BEFORE_FAILURE = "rollback_before_failure"
    DISABLE_DEGRADED_FEATURE = "disable_degraded_feature"
    REFRESH_DEPENDENCY = "refresh_dependency"
    RESTART_SERVICE = "restart_service"
    REBUILD_CACHE = "rebuild_cache"
    CREATE_CHECKPOINT = "create_checkpoint"
    HUMAN_REVIEW = "human_review"
    INFRASTRUCTURE_REQUIRED = "infrastructure_required"


class PreventiveActionStatus(str, Enum):
    PLANNED = "PLANNED"
    GATED = "GATED"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class GovernanceDecision(str, Enum):
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
    ESCALATED = "ESCALATED"
    PENDING_REVIEW = "PENDING_REVIEW"


class PreventionVerificationStatus(str, Enum):
    PREVENTION_EFFECTIVE = "PREVENTION_EFFECTIVE"
    PREVENTION_INEFFECTIVE = "PREVENTION_INEFFECTIVE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class DecisionQuality(str, Enum):
    OPTIMAL = "OPTIMAL"
    SUBOPTIMAL = "SUBOPTIMAL"
    UNNECESSARY = "UNNECESSARY"
    HARMFUL = "HARMFUL"
    UNKNOWN = "UNKNOWN"


@dataclass
class ReliabilityObservation:
    timestamp: float
    service: str
    metric: str
    value: float
    source: str
    observation_type: ObservationSourceType = ObservationSourceType.REAL_RUNTIME
    environment: str = "local"
    provenance: str = "collector"
    evidence_id: str = field(default_factory=lambda: f"ev_obs_{uuid.uuid4().hex[:8]}")
    process_id: Optional[str] = None
    tags: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["observation_type"] = self.observation_type.value
        return d


@dataclass
class ReliabilityWindow:
    service: str
    metric: str
    observations: List[ReliabilityObservation] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    sample_count: int = 0
    window_seconds: float = 300.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service": self.service,
            "metric": self.metric,
            "sample_count": len(self.observations),
            "start_time": self.start_time,
            "end_time": self.end_time,
            "window_seconds": self.window_seconds,
        }


@dataclass
class BaselineConfidence:
    sample_count: int
    window: float
    freshness: float
    stability: float
    status: BaselineStatus = BaselineStatus.VALID

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class Baseline:
    service: str
    metric: str
    rolling_mean: float
    rolling_median: float
    min_val: float
    max_val: float
    std_dev: float
    p90: float
    p95: float
    p99: float
    confidence: BaselineConfidence
    window_size: int
    calculated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["confidence"] = self.confidence.to_dict()
        return d


@dataclass
class AnomalySignal:
    signal_id: str
    detector: str
    service: str
    metric: str
    observed_value: float
    baseline_value: float
    deviation: float
    status: AnomalyStatus
    threshold: float
    evidence_id: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class TrendSignal:
    signal_id: str
    service: str
    metric: str
    slope: float
    acceleration: float
    persistence: float
    confidence: float
    status: TrendStatus
    evidence_id: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class CapacitySignal:
    signal_id: str
    service: str
    resource_type: str
    status: CapacityStatus
    utilization: float
    rate_of_change: float
    evidence_id: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class RecurrenceSignal:
    signal_id: str
    incident_category: str
    service: str
    occurrence_count: int
    first_seen: float
    last_seen: float
    status: RecurrenceStatus
    pattern_type: str
    evidence_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class DependencyRiskSignal:
    signal_id: str
    service: str
    dependency: str
    centrality: float
    scc_id: Optional[str]
    breadth: int
    historical_incident_count: int
    runtime_status: str
    risk_level: RiskLevel
    evidence_id: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["risk_level"] = self.risk_level.value
        return d


@dataclass
class ChangeRiskAssessment:
    assessment_id: str
    change_id: str
    changed_files: List[str]
    changed_symbols: List[str]
    contracts_affected: List[str]
    impacted_services: List[str]
    historical_incident_rate: float
    debt_score: float
    coupling_score: float
    risk_level: RiskLevel
    evidence_id: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["risk_level"] = self.risk_level.value
        return d


@dataclass
class RiskPrediction:
    prediction_id: str
    target: str
    failure_class: str
    horizon_seconds: float
    probability_estimate: float
    confidence: float
    risk_level: RiskLevel
    evidence_ids: List[str]
    contributing_signals: List[Dict[str, Any]]
    contradictory_signals: List[Dict[str, Any]]
    model_version: str = "v1.0.0"
    generated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["risk_level"] = self.risk_level.value
        return d


@dataclass
class PreventiveAction:
    action_id: str
    action_type: PreventiveActionType
    target_service: str
    reason: str
    risk_level: RiskLevel
    expected_effect: str
    verification_plan: str
    rollback_action: str
    status: PreventiveActionStatus = PreventiveActionStatus.PLANNED
    evidence_id: str = field(default_factory=lambda: f"ev_act_{uuid.uuid4().hex[:8]}")
    executed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["action_type"] = self.action_type.value
        d["risk_level"] = self.risk_level.value
        d["status"] = self.status.value
        return d


@dataclass
class PreventivePlan:
    plan_id: str
    prediction_id: str
    service: str
    actions: List[PreventiveAction]
    governance_decision: GovernanceDecision = GovernanceDecision.PENDING_REVIEW
    created_at: float = field(default_factory=time.time)
    evidence_id: str = field(default_factory=lambda: f"ev_plan_{uuid.uuid4().hex[:8]}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "prediction_id": self.prediction_id,
            "service": self.service,
            "actions": [a.to_dict() for a in self.actions],
            "governance_decision": self.governance_decision.value,
            "created_at": self.created_at,
            "evidence_id": self.evidence_id,
        }


@dataclass
class PreventiveVerification:
    verification_id: str
    plan_id: str
    action_id: str
    pre_action_baseline: Dict[str, float]
    post_action_baseline: Dict[str, float]
    status: PreventionVerificationStatus
    observed_metrics: Dict[str, float]
    verified_at: float = field(default_factory=time.time)
    stability_window_seconds: float = 60.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class PredictionEvidence:
    evidence_id: str
    timestamp: float
    prediction_id: str
    actual_outcome: str
    is_true_positive: bool
    is_false_positive: bool
    is_false_negative: bool
    lead_time_seconds: float
    calibration_error: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReliabilityDecision:
    decision_id: str
    service: str
    prediction: Optional[RiskPrediction]
    plan: Optional[PreventivePlan]
    recommended_action: str
    decision_quality: DecisionQuality
    governance_status: GovernanceDecision
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "service": self.service,
            "prediction": self.prediction.to_dict() if self.prediction else None,
            "plan": self.plan.to_dict() if self.plan else None,
            "recommended_action": self.recommended_action,
            "decision_quality": self.decision_quality.value,
            "governance_status": self.governance_status.value,
            "timestamp": self.timestamp,
        }
