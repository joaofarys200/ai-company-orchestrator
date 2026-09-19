"""
JARVIS OS — Phase 69: Autonomous Quality Debt Remediation & Continuous Engineering Improvement
Domain models, enums, records, and data structures.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class ValidationStatus(str, Enum):
    VALID_DEBT = "VALID_DEBT"
    WEAK_EVIDENCE = "WEAK_EVIDENCE"
    STALE_DEBT = "STALE_DEBT"
    DUPLICATE_DEBT = "DUPLICATE_DEBT"
    INVALID_DEBT = "INVALID_DEBT"
    CONFLICTED_DEBT = "CONFLICTED_DEBT"
    REQUIRES_HUMAN_REVIEW = "REQUIRES_HUMAN_REVIEW"


class RootCauseCategory(str, Enum):
    ARCHITECTURAL_CAUSE = "ARCHITECTURAL_CAUSE"
    CODE_CAUSE = "CODE_CAUSE"
    TEST_CAUSE = "TEST_CAUSE"
    CONTRACT_CAUSE = "CONTRACT_CAUSE"
    BEHAVIOR_CAUSE = "BEHAVIOR_CAUSE"
    SECURITY_CAUSE = "SECURITY_CAUSE"
    PERFORMANCE_CAUSE = "PERFORMANCE_CAUSE"
    RELIABILITY_CAUSE = "RELIABILITY_CAUSE"
    PROCESS_CAUSE = "PROCESS_CAUSE"
    UNKNOWN_CAUSE = "UNKNOWN_CAUSE"


class RemediationOptionType(str, Enum):
    KEEP_CURRENT = "KEEP_CURRENT"
    LOCAL_REFACTOR = "LOCAL_REFACTOR"
    MODULE_EXTRACTION = "MODULE_EXTRACTION"
    DEPENDENCY_INVERSION = "DEPENDENCY_INVERSION"
    CONTRACT_MIGRATION = "CONTRACT_MIGRATION"
    TEST_EXPANSION = "TEST_EXPANSION"
    TEST_REDUCTION = "TEST_REDUCTION"
    ARCHITECTURE_CHANGE = "ARCHITECTURE_CHANGE"
    PERFORMANCE_OPTIMIZATION = "PERFORMANCE_OPTIMIZATION"
    SECURITY_HARDENING = "SECURITY_HARDENING"
    RELIABILITY_IMPROVEMENT = "RELIABILITY_IMPROVEMENT"
    DOCUMENTATION_UPDATE = "DOCUMENTATION_UPDATE"
    OBSERVATION_ONLY = "OBSERVATION_ONLY"


class QualityImpactClassification(str, Enum):
    IMPROVEMENT_EXPECTED = "IMPROVEMENT_EXPECTED"
    DEGRADATION_RISK = "DEGRADATION_RISK"
    NO_EXPECTED_CHANGE = "NO_EXPECTED_CHANGE"
    UNKNOWN = "UNKNOWN"


class ImplementationStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class ResolutionStatus(str, Enum):
    RESOLVED = "RESOLVED"
    PARTIALLY_RESOLVED = "PARTIALLY_RESOLVED"
    DEFERRED = "DEFERRED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    INVALIDATED = "INVALIDATED"


class ConvergenceState(str, Enum):
    CONVERGING = "CONVERGING"
    STABLE = "STABLE"
    STALLED = "STALLED"
    OSCILLATING = "OSCILLATING"
    DIVERGING = "DIVERGING"
    BLOCKED = "BLOCKED"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class GamingType(str, Enum):
    TEST_DELETION = "TEST_DELETION"
    SCOPE_EXCLUSION = "SCOPE_EXCLUSION"
    TARGET_REDUCTION = "TARGET_REDUCTION"
    THRESHOLD_TAMPERING = "THRESHOLD_TAMPERING"
    ROOT_CAUSE_BYPASS = "ROOT_CAUSE_BYPASS"
    UNKNOWN_RECLASSIFICATION = "UNKNOWN_RECLASSIFICATION"
    UNMEASURED_SHIFT = "UNMEASURED_SHIFT"


@dataclass
class DebtValidationResult:
    validation_id: str
    debt_id: str
    status: ValidationStatus
    confidence: float
    evidence_validity: bool
    reproducibility: bool
    scope: str
    explanation: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "debt_id": self.debt_id,
            "status": self.status.value if isinstance(self.status, ValidationStatus) else str(self.status),
            "confidence": self.confidence,
            "evidence_validity": self.evidence_validity,
            "reproducibility": self.reproducibility,
            "scope": self.scope,
            "explanation": self.explanation,
            "timestamp": self.timestamp,
        }


@dataclass
class DebtRootCause:
    cause_id: str
    debt_id: str
    category: RootCauseCategory
    description: str
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.8
    affected_surface: str = "global"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cause_id": self.cause_id,
            "debt_id": self.debt_id,
            "category": self.category.value if isinstance(self.category, RootCauseCategory) else str(self.category),
            "description": self.description,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "affected_surface": self.affected_surface,
            "timestamp": self.timestamp,
        }


@dataclass
class DebtRemediationOption:
    option_id: str
    debt_id: str
    option_type: RemediationOptionType
    title: str
    description: str
    benefits: List[str] = field(default_factory=list)
    estimated_cost: float = 1.0
    risk: float = 0.5
    affected_files: List[str] = field(default_factory=list)
    affected_symbols: List[str] = field(default_factory=list)
    affected_contracts: List[str] = field(default_factory=list)
    affected_behaviors: List[str] = field(default_factory=list)
    verification_requirements: List[str] = field(default_factory=list)
    rollback_strategy: str = "atomic_git_revert"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "option_id": self.option_id,
            "debt_id": self.debt_id,
            "option_type": self.option_type.value if isinstance(self.option_type, RemediationOptionType) else str(self.option_type),
            "title": self.title,
            "description": self.description,
            "benefits": self.benefits,
            "estimated_cost": self.estimated_cost,
            "risk": self.risk,
            "affected_files": self.affected_files,
            "affected_symbols": self.affected_symbols,
            "affected_contracts": self.affected_contracts,
            "affected_behaviors": self.affected_behaviors,
            "verification_requirements": self.verification_requirements,
            "rollback_strategy": self.rollback_strategy,
        }


@dataclass
class QualityImpactPrediction:
    prediction_id: str
    option_id: str
    dimension_impacts: Dict[str, QualityImpactClassification] = field(default_factory=dict)
    overall_assessment: str = ""
    confidence: float = 0.8

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "option_id": self.option_id,
            "dimension_impacts": {
                k: v.value if isinstance(v, QualityImpactClassification) else str(v)
                for k, v in self.dimension_impacts.items()
            },
            "overall_assessment": self.overall_assessment,
            "confidence": self.confidence,
        }


@dataclass
class RemediationPlan:
    plan_id: str
    debt_id: str
    chosen_option_id: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    allocated_budget: Dict[str, Any] = field(default_factory=dict)
    required_agents: List[str] = field(default_factory=list)
    rollback_plan: Dict[str, Any] = field(default_factory=dict)
    governance_decision: str = "APPROVED"
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RemediationMission:
    mission_id: str
    debt_id: str
    plan_id: str
    status: str = "START"
    current_step_index: int = 0
    logs: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ImplementationResult:
    result_id: str
    patch_id: str
    transaction_id: str
    files_modified: List[str] = field(default_factory=list)
    status: ImplementationStatus = ImplementationStatus.SUCCESS
    build_passed: bool = True
    test_passed: bool = True
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "patch_id": self.patch_id,
            "transaction_id": self.transaction_id,
            "files_modified": self.files_modified,
            "status": self.status.value if isinstance(self.status, ImplementationStatus) else str(self.status),
            "build_passed": self.build_passed,
            "test_passed": self.test_passed,
            "details": self.details,
            "timestamp": self.timestamp,
        }


@dataclass
class DebtResolutionResult:
    resolution_id: str
    debt_id: str
    status: ResolutionStatus
    original_evidence_invalidated: bool
    quality_delta: Dict[str, Any] = field(default_factory=dict)
    remaining_child_debts: List[Dict[str, Any]] = field(default_factory=list)
    explanation: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resolution_id": self.resolution_id,
            "debt_id": self.debt_id,
            "status": self.status.value if isinstance(self.status, ResolutionStatus) else str(self.status),
            "original_evidence_invalidated": self.original_evidence_invalidated,
            "quality_delta": self.quality_delta,
            "remaining_child_debts": self.remaining_child_debts,
            "explanation": self.explanation,
            "timestamp": self.timestamp,
        }


@dataclass
class DebtDeferment:
    deferment_id: str
    debt_id: str
    reason: str
    risk: float
    expected_cost: float
    revisit_condition: str
    expiration_date: float
    owner: str = "LeadArchitect"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QualityGamingEvent:
    event_id: str
    gaming_type: GamingType
    actor: str
    reason: str
    blocked: bool = True
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "gaming_type": self.gaming_type.value if isinstance(self.gaming_type, GamingType) else str(self.gaming_type),
            "actor": self.actor,
            "reason": self.reason,
            "blocked": self.blocked,
            "timestamp": self.timestamp,
        }


@dataclass
class RemediationPriorityVector:
    debt_id: str
    risk: float
    severity: float
    recurrence: float
    blast_radius: float
    security: float
    contract_impact: float
    behavior_impact: float
    remediation_cost: float
    evidence_strength: float
    age: float
    rank_score: float
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
