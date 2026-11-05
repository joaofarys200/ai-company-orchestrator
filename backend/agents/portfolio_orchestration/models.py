"""
JARVIS OS — Phase 75: Autonomous Engineering Strategy & Portfolio Orchestration
Module: models.py
Domain models, enums, exceptions, and data structures for portfolio orchestration.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


class InitiativeState(str, enum.Enum):
    """Lifecycle states of an engineering initiative."""
    PROPOSED = "PROPOSED"
    SELECTED = "SELECTED"
    SCHEDULED = "SCHEDULED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    AUTHORIZED = "AUTHORIZED"
    EXECUTING = "EXECUTING"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DEFERRED = "DEFERRED"
    CANCELLED = "CANCELLED"


class InitiativeType(str, enum.Enum):
    """Supported types of engineering initiatives."""
    ARCHITECTURAL_OPTIMIZATION = "ARCHITECTURAL_OPTIMIZATION"
    MACRO_REFACTORING = "MACRO_REFACTORING"
    TECHNICAL_DEBT_REMEDIATION = "TECHNICAL_DEBT_REMEDIATION"
    RELIABILITY_IMPROVEMENT = "RELIABILITY_IMPROVEMENT"
    VERIFICATION_HARDENING = "VERIFICATION_HARDENING"


class DependencyType(str, enum.Enum):
    """Types of inter-initiative dependencies."""
    HARD_PREREQUISITE = "HARD_PREREQUISITE"          # Target cannot commence until source is COMPLETED
    SOFT_PREFERENCE = "SOFT_PREFERENCE"              # Target prefers source to run first if both selected
    MUTUAL_EXCLUSION = "MUTUAL_EXCLUSION"            # Source and target cannot both be selected
    SHARED_RESOURCE = "SHARED_RESOURCE"              # Source and target touch common files; cannot run concurrently
    EVIDENCE_INVALIDATION = "EVIDENCE_INVALIDATION"  # Source changes invalidate target's baseline evidence


class ConflictType(str, enum.Enum):
    """Classification of conflicts between initiatives."""
    MUTUAL_EXCLUSION = "MUTUAL_EXCLUSION"
    RESOURCE_CONTENTION = "RESOURCE_CONTENTION"
    OVERLAPPING_COMPONENTS = "OVERLAPPING_COMPONENTS"
    EVIDENCE_STALENESS = "EVIDENCE_STALENESS"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    CYCLE_DETECTED = "CYCLE_DETECTED"
    UNAUTHORIZED_EXECUTION = "UNAUTHORIZED_EXECUTION"


class ReplanningTriggerType(str, enum.Enum):
    """Triggers that cause a portfolio replan."""
    INITIATIVE_FAILURE = "INITIATIVE_FAILURE"
    BUDGET_OVERRUN = "BUDGET_OVERRUN"
    EVIDENCE_INVALIDATED = "EVIDENCE_INVALIDATED"
    NEW_HIGH_PRIORITY_INITIATIVE = "NEW_HIGH_PRIORITY_INITIATIVE"
    SECURITY_GATE_DENIAL = "SECURITY_GATE_DENIAL"


# --- Exceptions ---

class PortfolioError(Exception):
    """Base exception for portfolio orchestration."""
    pass


class DependencyCycleError(PortfolioError):
    """Raised when a dependency cycle is detected in the initiatives graph."""
    def __init__(self, cycle_path: List[str]):
        self.cycle_path = cycle_path
        super().__init__(f"Dependency cycle detected among initiatives: {' -> '.join(cycle_path)}")


class InfeasiblePortfolioError(PortfolioError):
    """Raised when no safe, feasible portfolio satisfies the hard constraints."""
    def __init__(self, reasons: List[str]):
        self.reasons = reasons
        super().__init__(f"No feasible portfolio found. Reasons: {'; '.join(reasons)}")


class ConstraintViolationError(PortfolioError):
    """Raised when a hard invariant or security constraint is violated."""
    pass


class UnauthorizedInitiativeError(PortfolioError):
    """Raised when an initiative requires human or release approval but lacks a valid token."""
    pass


class ReplanningLoopError(PortfolioError):
    """Raised when replanning exceeds maximum allowed attempts."""
    pass


# --- Domain Data Structures ---

@dataclass
class ResourceRequirement:
    """Resource needs for an initiative."""
    agents_required: int = 1
    estimated_duration_seconds: float = 60.0
    estimated_cost_usd: float = 0.0
    memory_mb: int = 256

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceProvenance:
    """Provenance and validation evidence supporting an initiative."""
    source_phase: str
    artifact_path: str = ""
    baseline_metric: str = ""
    baseline_value: float = 0.0
    confidence: float = 1.0  # 0.0 to 1.0
    is_valid: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DependencyRelation:
    """Directed dependency relation between two initiatives."""
    source_id: str
    target_id: str
    relation_type: DependencyType
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type.value,
            "reason": self.reason,
        }


@dataclass
class ConflictDiagnostic:
    """Diagnostic explaining a detected conflict."""
    conflict_type: ConflictType
    initiative_ids: List[str]
    description: str
    resolvable: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_type": self.conflict_type.value,
            "initiative_ids": self.initiative_ids,
            "description": self.description,
            "resolvable": self.resolvable,
        }


@dataclass
class SynergyDefinition:
    """Synergy bonus between two or more initiatives."""
    initiative_ids: Set[str]
    bonus_benefit: float
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "initiative_ids": list(self.initiative_ids),
            "bonus_benefit": self.bonus_benefit,
            "description": self.description,
        }


@dataclass
class RedundancyDefinition:
    """Redundancy penalty between two or more initiatives."""
    initiative_ids: Set[str]
    penalty_benefit: float
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "initiative_ids": list(self.initiative_ids),
            "penalty_benefit": self.penalty_benefit,
            "description": self.description,
        }


@dataclass
class EngineeringInitiative:
    """
    Normalized engineering initiative model representing an existing or proposed
    architectural optimization, macro-refactoring, debt remediation, or reliability task.
    """
    id: str
    title: str
    initiative_type: InitiativeType
    description: str = ""
    affected_components: List[str] = field(default_factory=list)
    state: InitiativeState = InitiativeState.PROPOSED
    
    # Economics and Estimations
    effort_units: float = 1.0
    budget_cost: float = 10.0
    expected_benefit: float = 50.0  # Qualitative or quantitative expected utility
    confidence: float = 0.85        # Confidence in evidence (0.0 to 1.0)
    risk_score: float = 0.2         # Estimated risk of failure/regression (0.0 to 1.0)
    reversibility: bool = True
    
    # Governance & Authorization
    requires_approval: bool = False
    approval_token: Optional[str] = None
    
    # Dependencies & Provenance
    prerequisites: List[str] = field(default_factory=list)       # IDs that must complete first
    mutual_exclusions: List[str] = field(default_factory=list)   # IDs that cannot co-exist
    soft_preferences: List[str] = field(default_factory=list)    # IDs preferred to run before this
    evidence: Optional[EvidenceProvenance] = None
    
    # Realized Outcomes (filled after execution)
    actual_cost: float = 0.0
    actual_duration: float = 0.0
    actual_benefit: float = 0.0
    error_message: Optional[str] = None
    assigned_agent: Optional[str] = None
    completed_at: Optional[float] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["state"] = self.state.value
        res["initiative_type"] = self.initiative_type.value
        if self.evidence:
            res["evidence"] = self.evidence.to_dict()
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EngineeringInitiative:
        d = dict(data)
        d["state"] = InitiativeState(d.get("state", "PROPOSED"))
        d["initiative_type"] = InitiativeType(d.get("initiative_type", "TECHNICAL_DEBT_REMEDIATION"))
        if d.get("evidence"):
            d["evidence"] = EvidenceProvenance(**d["evidence"])
        return cls(**d)


@dataclass
class PortfolioEvaluationResult:
    """Outcome of combinatorial portfolio evaluation."""
    selected_initiatives: List[str]
    rejected_initiatives: List[str]
    total_benefit: float
    total_cost: float
    total_effort: float
    net_utility: float
    synergy_bonus: float
    redundancy_penalty: float
    risk_penalty: float
    is_feasible: bool
    infeasibility_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionScheduleItem:
    """A scheduled item within a portfolio roadmap wave."""
    initiative_id: str
    wave_index: int
    estimated_duration: float
    assigned_agent: str = "agent-default"
    claimed_resources: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionSchedule:
    """Wave-based execution schedule respecting dependencies and concurrency limits."""
    schedule_id: str
    portfolio_id: str
    items: List[ExecutionScheduleItem] = field(default_factory=list)
    total_waves: int = 0
    critical_path: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schedule_id": self.schedule_id,
            "portfolio_id": self.portfolio_id,
            "items": [item.to_dict() for item in self.items],
            "total_waves": self.total_waves,
            "critical_path": self.critical_path,
        }


@dataclass
class MilestoneCheckpoint:
    """A verification checkpoint between execution waves."""
    checkpoint_id: str
    wave_index: int
    required_verifications: List[str]
    passed: bool = False
    verified_at: Optional[float] = None
    diagnostic: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PortfolioRoadmap:
    """Versioned roadmap representing the authorized execution plan."""
    roadmap_id: str
    version: str
    portfolio_id: str
    selected_initiatives: List[str]
    rejected_initiatives: List[str]
    schedule: ExecutionSchedule
    milestones: List[MilestoneCheckpoint] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    status: str = "ACTIVE"
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "roadmap_id": self.roadmap_id,
            "version": self.version,
            "portfolio_id": self.portfolio_id,
            "selected_initiatives": self.selected_initiatives,
            "rejected_initiatives": self.rejected_initiatives,
            "schedule": self.schedule.to_dict(),
            "milestones": [m.to_dict() for m in self.milestones],
            "created_at": self.created_at,
            "status": self.status,
            "rationale": self.rationale,
        }


@dataclass
class ReplanningEvent:
    """Record of an automated or governed portfolio replan."""
    event_id: str
    roadmap_id: str
    trigger_type: ReplanningTriggerType
    failed_initiative_id: Optional[str]
    affected_initiatives: List[str]
    previous_version: str
    new_version: str
    preserved_initiatives: List[str]
    reason: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "roadmap_id": self.roadmap_id,
            "trigger_type": self.trigger_type.value,
            "failed_initiative_id": self.failed_initiative_id,
            "affected_initiatives": self.affected_initiatives,
            "previous_version": self.previous_version,
            "new_version": self.new_version,
            "preserved_initiatives": self.preserved_initiatives,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


@dataclass
class PortfolioMetrics:
    """Strategic cumulative metrics measured across the portfolio."""
    portfolio_id: str
    total_initiatives: int = 0
    completed_initiatives: int = 0
    failed_initiatives: int = 0
    deferred_initiatives: int = 0
    expected_benefit: float = 0.0
    realized_benefit: float = 0.0
    budget_allocated: float = 0.0
    budget_consumed: float = 0.0
    schedule_estimated_duration: float = 0.0
    schedule_actual_duration: float = 0.0
    verification_pass_rate: float = 1.0
    regression_count: int = 0
    roi_ratio: float = 0.0
    net_improvement_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
