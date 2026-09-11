"""
JARVIS OS — Phase 39: Predictive Impact Models & Schemas

Defines the formal data contracts for:
- PredictiveImpactReport: Structural simulation projection before applying intent
- PredictionOutcome: Empirical comparison of Prediction vs Observed Reality
- Enums for Scope, Risk, Classification, and Validation Status
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import enum
import time
import uuid
from typing import Any, Dict, List, Optional


class PredictionStatus(str, enum.Enum):
    GENERATED = "GENERATED"
    REVIEWED = "REVIEWED"
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"
    STALE = "STALE"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"


class ImpactScope(str, enum.Enum):
    NONE = "NONE"
    LOCAL = "LOCAL"
    CROSS_FILE = "CROSS_FILE"
    CROSS_MODULE = "CROSS_MODULE"
    ARCHITECTURAL = "ARCHITECTURAL"
    MISSION_WIDE = "MISSION_WIDE"


class FileImpactClassification(str, enum.Enum):
    DIRECT = "DIRECT"
    INDIRECT = "INDIRECT"
    POSSIBLE = "POSSIBLE"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class OutcomeClassification(str, enum.Enum):
    CORRECT = "CORRECT"
    PARTIALLY_CORRECT = "PARTIALLY_CORRECT"
    MISSED = "MISSED"
    OVERPREDICTED = "OVERPREDICTED"
    UNDERPREDICTED = "UNDERPREDICTED"


class DeviationType(str, enum.Enum):
    MATCHED = "MATCHED"
    UNEXPECTED = "UNEXPECTED"
    MISSED = "MISSED"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    RISK_MISMATCH = "RISK_MISMATCH"


class TaskCategory(str, enum.Enum):
    ARCHITECTURE = "Architecture"
    RESEARCH = "Research"
    CODING = "Coding"
    TESTING = "Testing"
    BROWSER = "Browser"
    REVIEW = "Review"
    REPAIR = "Repair"
    UNMAPPED_TASK_CATEGORY = "UNMAPPED_TASK_CATEGORY"


class TaskDerivationType(str, enum.Enum):
    DIRECT_FILE_IMPACT = "DIRECT_FILE_IMPACT"
    DOWNSTREAM_FILE_IMPACT = "DOWNSTREAM_FILE_IMPACT"
    REQUIREMENT_DRIVEN = "REQUIREMENT_DRIVEN"
    VALIDATION_DRIVEN = "VALIDATION_DRIVEN"
    ARCHITECTURE_DRIVEN = "ARCHITECTURE_DRIVEN"
    CONTROL_DRIVEN = "CONTROL_DRIVEN"


class ConfidenceClass(str, enum.Enum):
    DETERMINISTIC = "DETERMINISTIC"
    INFERRED = "INFERRED"
    UNCERTAIN = "UNCERTAIN"


class TaskRootCauseType(str, enum.Enum):
    MISSING_FILE_TO_TASK_MAPPING = "MISSING_FILE_TO_TASK_MAPPING"
    MISSING_SYMBOL_TO_TASK_MAPPING = "MISSING_SYMBOL_TO_TASK_MAPPING"
    TASK_GRANULARITY_MISMATCH = "TASK_GRANULARITY_MISMATCH"
    VALIDATION_TASK_NOT_FILE_DRIVEN = "VALIDATION_TASK_NOT_FILE_DRIVEN"
    SEMANTIC_TASK_NOT_FILE_DRIVEN = "SEMANTIC_TASK_NOT_FILE_DRIVEN"
    DEPENDENCY_PROPAGATION_GAP = "DEPENDENCY_PROPAGATION_GAP"
    PLANNING_CONTRACT_GAP = "PLANNING_CONTRACT_GAP"
    EXPECTED_UNCERTAINTY = "EXPECTED_UNCERTAINTY"
    OVER_AGGRESSIVE_TASK_DERIVATION = "OVER_AGGRESSIVE_TASK_DERIVATION"
    DUPLICATE_DERIVATION = "DUPLICATE_DERIVATION"
    OTHER = "OTHER"


class ConsistencyVerdict(str, enum.Enum):
    CONSISTENT = "CONSISTENT"
    INCONSISTENT = "INCONSISTENT"
    PARTIALLY_TRACEABLE = "PARTIALLY_TRACEABLE"


class TaskFileRelationType(str, enum.Enum):
    DIRECT = "DIRECT"
    INDIRECT = "INDIRECT"
    DOWNSTREAM = "DOWNSTREAM"
    VALIDATION = "VALIDATION"
    UNKNOWN = "UNKNOWN"


@dataclass
class PredictedTask:
    predicted_task_id: str
    action: str  # ADD_TASK, REMOVE_TASK, MODIFY_TASK, ADD_DEPENDENCY, REASSIGN
    title: str
    description: str
    source_requirement: str
    dependencies: list[str] = field(default_factory=list)
    predicted_owner: str = "coder"  # coder, test_engineer, architect, planner
    confidence: float = 0.90
    status: str = "PREDICTED_ONLY"
    
    # Phase 39.2: Explicit Task-to-File Reconciliation & Causal Traceability
    category: str = TaskCategory.CODING.value
    derivation_type: str = TaskDerivationType.DIRECT_FILE_IMPACT.value
    confidence_class: str = ConfidenceClass.DETERMINISTIC.value
    predicted_files: list[str] = field(default_factory=list)
    impacted_symbols: list[str] = field(default_factory=list)
    source_requirements: list[str] = field(default_factory=list)
    source_constraints: list[str] = field(default_factory=list)
    derived_from: list[str] = field(default_factory=list)
    reason: str = ""
    causal_trace: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if not d.get("source_requirements") and self.source_requirement:
            d["source_requirements"] = [self.source_requirement]
        return d


@dataclass
class PredictedFile:
    file_path: str
    classification: str  # DIRECT, INDIRECT, POSSIBLE
    reason: str
    estimated_change_type: str = "MODIFY"  # CREATE, MODIFY, DELETE
    related_symbol: Optional[str] = None
    confidence: float = 0.85

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PredictedSymbol:
    name: str
    file_path: str
    symbol_type: str  # function, class, interface, type, endpoint
    change_nature: str  # ADD, MODIFY, DEPRECATE
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PredictedEvidenceImpact:
    evidence_id: str
    requirement_id: str
    title: str
    predicted_status: str  # REQUIRES_REVALIDATION, SUPERSEDED, UNAFFECTED
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PredictedAssumption:
    assumption_id: str
    statement: str
    category: str  # SYSTEM_ASSUMPTION, INFERRED
    confidence: float = 0.80

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PredictiveImpactReport:
    """
    Comprehensive, non-mutating prediction of intent delta impact.
    Separates PREDICTION from FACT. All hypothetical items marked SIMULATION_ONLY.
    """
    prediction_id: str
    mission_id: str
    source_intent_version: int
    proposed_intent_version: int
    generated_at: float
    analysis_version: str = "1.0.0"
    
    # Scope & Risk
    predicted_scope: str = ImpactScope.LOCAL.value
    predicted_risk: str = RiskLevel.LOW.value
    risk_factors: dict[str, Any] = field(default_factory=dict)
    
    # Affected Elements
    affected_requirements: list[str] = field(default_factory=list)
    affected_constraints: list[str] = field(default_factory=list)
    predicted_tasks: list[dict[str, Any]] = field(default_factory=list)
    predicted_dependencies: list[dict[str, Any]] = field(default_factory=list)
    predicted_agents: list[str] = field(default_factory=list)
    predicted_files: list[dict[str, Any]] = field(default_factory=list)
    predicted_symbols: list[dict[str, Any]] = field(default_factory=list)
    predicted_architecture_changes: list[dict[str, Any]] = field(default_factory=list)
    predicted_tests: list[dict[str, Any]] = field(default_factory=list)
    predicted_evidence_impact: list[dict[str, Any]] = field(default_factory=list)
    predicted_checkpoint_impact: list[dict[str, Any]] = field(default_factory=list)
    
    # Operational Flags
    predicted_browser_validation: bool = False
    predicted_pause_required: bool = False
    predicted_approval_required: bool = False
    
    # Calibrated Epistemic Meta
    assumptions: list[dict[str, Any]] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    confidence: float = 0.85
    causal_chains: list[dict[str, Any]] = field(default_factory=list)
    status: str = PredictionStatus.GENERATED.value
    simulation_marker: str = "SIMULATION_ONLY"

    # Phase 39.2: Reconciliation & Consistency
    task_file_matrix: dict[str, Any] = field(default_factory=dict)
    consistency_report: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PredictionOutcome:
    """
    Empirical telemetry comparing Prediction vs Actual Observation after execution.
    Calculates observable Precision & Recall without hidden false positives.
    """
    outcome_id: str
    prediction_id: str
    mission_id: str
    actual_intent_version: int
    actual_plan_version: int
    evaluated_at: float
    
    # Actual observations
    actual_tasks_added: list[str] = field(default_factory=list)
    actual_tasks_modified: list[str] = field(default_factory=list)
    actual_tasks_removed: list[str] = field(default_factory=list)
    actual_files_changed: list[str] = field(default_factory=list)
    actual_tests_added: list[str] = field(default_factory=list)
    actual_evidence_invalidated: list[str] = field(default_factory=list)
    actual_agents_used: list[str] = field(default_factory=list)
    actual_browser_validation: bool = False
    actual_scope: str = ImpactScope.LOCAL.value
    
    # Metrics
    file_precision: float = 1.0
    file_recall: float = 1.0
    task_precision: float = 1.0
    task_recall: float = 1.0
    evidence_precision: float = 1.0
    evidence_recall: float = 1.0
    
    # Deviations
    classification: str = OutcomeClassification.CORRECT.value
    matched_files: list[str] = field(default_factory=list)
    missed_files: list[str] = field(default_factory=list)  # False negatives
    unexpected_files: list[str] = field(default_factory=list)  # False positives
    matched_tasks: list[str] = field(default_factory=list)
    missed_tasks: list[str] = field(default_factory=list)
    unexpected_tasks: list[str] = field(default_factory=list)
    deviations: list[dict[str, Any]] = field(default_factory=list)

    # Phase 39.2: Task Reconciliation & Root-Cause Classification
    task_mismatches_by_root_cause: dict[str, int] = field(default_factory=dict)
    task_causal_matches: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
