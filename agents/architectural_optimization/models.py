"""
JARVIS OS — Phase 74: Autonomous Architectural Evolution & Optimization
Module: models.py
Domain models, contracts, enumerations, and lifecycle states for evidence-driven architectural optimization.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


class OptimizationState(str, enum.Enum):
    """Lifecycle states for an architectural optimization candidate."""
    DISCOVERED = "DISCOVERED"
    HYPOTHESIZED = "HYPOTHESIZED"
    BENCHMARKED = "BENCHMARKED"
    RANKED = "RANKED"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    MEASURED = "MEASURED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"


class ExperimentOutcome(str, enum.Enum):
    """Outcomes from isolated empirical benchmarking."""
    IMPROVEMENT_CONFIRMED = "IMPROVEMENT_CONFIRMED"
    NO_MEASURABLE_IMPROVEMENT = "NO_MEASURABLE_IMPROVEMENT"
    REGRESSION_DETECTED = "REGRESSION_DETECTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    BLOCKED_BY_GOVERNANCE = "BLOCKED_BY_GOVERNANCE"


class OpportunityCategory(str, enum.Enum):
    """Structural and empirical opportunity categories."""
    EXCESSIVE_COUPLING = "EXCESSIVE_COUPLING"
    DEPENDENCY_CONCENTRATION = "DEPENDENCY_CONCENTRATION"
    COORDINATION_BOTTLENECK = "COORDINATION_BOTTLENECK"
    INEFFICIENT_EXECUTION_PATH = "INEFFICIENT_EXECUTION_PATH"
    FRAGILE_MODULE_BOUNDARY = "FRAGILE_MODULE_BOUNDARY"
    REDUNDANT_ABSTRACTION = "REDUNDANT_ABSTRACTION"
    FAILURE_PROPAGATION_CLUSTER = "FAILURE_PROPAGATION_CLUSTER"


class StructuralPatternType(str, enum.Enum):
    """Architectural patterns applied during optimization."""
    INTERFACE_INVERSION = "INTERFACE_INVERSION"
    FACADE_SHIM = "FACADE_SHIM"
    EVENT_DRIVEN_DECOUPLING = "EVENT_DRIVEN_DECOUPLING"
    ADAPTER_DECOMPOSITION = "ADAPTER_DECOMPOSITION"
    DIRECT_SIMPLIFICATION = "DIRECT_SIMPLIFICATION"


class ArchitecturalOptimizationError(Exception):
    """Base exception for Phase 74 failures."""
    pass


class InsufficientEvidenceError(ArchitecturalOptimizationError):
    """Raised when evidence is missing or below minimum confidence thresholds."""
    pass


class ConstraintViolationError(ArchitecturalOptimizationError):
    """Raised when a candidate violates a hard security or compatibility constraint."""
    pass


class ExperimentContaminationError(ArchitecturalOptimizationError):
    """Raised when an isolated experiment is contaminated by external working-tree changes."""
    pass


class OptimizationRegressionError(ArchitecturalOptimizationError):
    """Raised when an optimization candidate induces measurable regressions."""
    pass


class UnauthorizedExecutionError(ArchitecturalOptimizationError):
    """Raised when an operation attempts execution without mandatory governance approval."""
    pass


@dataclass
class ArchitecturalMetricSnapshot:
    """Quantitative measurement of an architectural property."""
    metric_name: str  # e.g. "coupling_ratio", "coordination_latency_ms", "dependency_depth"
    value: float
    sample_count: int = 1
    std_dev: float = 0.0
    unit: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OptimizationOpportunity:
    """An identified architectural improvement opportunity backed by multi-source evidence."""
    opportunity_id: str
    title: str
    category: OpportunityCategory
    affected_components: List[str]
    supporting_evidence: List[str]
    baseline_metrics: Dict[str, ArchitecturalMetricSnapshot]
    severity_score: float = 0.5  # 0.0 to 1.0
    confidence_score: float = 0.8  # 0.0 to 1.0
    discovered_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        d["baseline_metrics"] = {k: v.to_dict() for k, v in self.baseline_metrics.items()}
        return d


@dataclass
class ArchitecturalAlternative:
    """A competing structural design candidate addressing an opportunity."""
    alternative_id: str
    pattern_type: StructuralPatternType
    title: str
    description: str
    producers: List[str]
    consumers: List[str]
    affected_files: List[str]
    predicted_metric_deltas: Dict[str, float]  # metric_name -> predicted delta (negative = reduction)
    estimated_implementation_cost: float = 20.0  # arbitrary cost units
    estimated_verification_cost: float = 10.0
    regression_risk_score: float = 0.2  # 0.0 to 1.0
    reversibility: bool = True
    is_security_sensitive: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["pattern_type"] = self.pattern_type.value
        return d


@dataclass
class OptimizationHypothesis:
    """A falsifiable quantitative optimization hypothesis."""
    hypothesis_id: str
    opportunity_id: str
    target_metric: str
    current_baseline_value: float
    predicted_improvement_delta: float
    minimum_demonstrable_delta: float
    falsification_conditions: List[str]
    confidence: float = 0.8
    status: OptimizationState = OptimizationState.HYPOTHESIZED
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class ExperimentRecord:
    """Empirical benchmarking result from an isolated worktree experiment."""
    experiment_id: str
    hypothesis_id: str
    alternative_id: str
    worktree_path: str
    baseline_measurements: Dict[str, float]
    candidate_measurements: Dict[str, float]
    measured_deltas: Dict[str, float]  # candidate - baseline
    outcome: ExperimentOutcome
    summary: str
    secondary_regressions_detected: List[str] = field(default_factory=list)
    isolation_verified: bool = True
    executed_at: float = field(default_factory=time.time)
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["outcome"] = self.outcome.value
        return d


@dataclass
class ParetoEvaluation:
    """Multi-objective ranking across competing architectural candidates."""
    evaluation_id: str
    opportunity_id: str
    ranked_alternatives: List[str]  # Ordered from best to worst
    pareto_frontier: List[str]  # Non-dominated alternative IDs
    objective_scores: Dict[str, Dict[str, float]]  # alt_id -> {metric: score}
    hard_constraint_rejections: Dict[str, str]  # alt_id -> rejection reason
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OptimizationDecision:
    """Governed decision on whether to accept, reject, or execute an optimization."""
    decision_id: str
    opportunity_id: str
    selected_alternative_id: Optional[str]
    governance_authorized: bool
    requires_human_approval: bool
    human_approval_token: Optional[str] = None
    rationale: str = ""
    rejection_reasons: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CalibrationRecord:
    """Historical learning record comparing predicted vs measured outcomes."""
    calibration_id: str
    pattern_type: str
    target_metric: str
    predicted_delta: float
    measured_delta: float
    prediction_error: float  # abs(predicted - measured)
    successful: bool
    notes: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
