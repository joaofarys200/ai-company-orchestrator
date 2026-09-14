"""
JARVIS OS — Phase 41: Autonomous Decision Calibration & Failure Intelligence
Core Models, Enums, Serialization, and Invariant Definitions.

Principles:
- Auditable Decision Intelligence: "Why was this decision taken? Was it correct? If not, what was missing?"
- Deterministic error taxonomy and causal isolation (Prediction != Decision != Execution).
- Permanent prohibition of security/gate weakening.
- Strict read-only semantics for counterfactuals and historical replay.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import enum
import hashlib
import json
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

if TYPE_CHECKING:
    from agents.autonomous_loop.models import LoopDecisionType


class DecisionCorrectness(str, enum.Enum):
    CORRECT = "CORRECT"
    PARTIALLY_CORRECT = "PARTIALLY_CORRECT"
    INCORRECT = "INCORRECT"
    UNDETERMINED = "UNDETERMINED"


class DecisionErrorTaxonomy(str, enum.Enum):
    OBSERVATION_GAP = "OBSERVATION_GAP"
    POLICY_GAP = "POLICY_GAP"
    POLICY_PRIORITY_ERROR = "POLICY_PRIORITY_ERROR"
    STALE_STATE = "STALE_STATE"
    INCORRECT_CLASSIFICATION = "INCORRECT_CLASSIFICATION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    PREDICTION_ERROR = "PREDICTION_ERROR"
    EXECUTION_ERROR = "EXECUTION_ERROR"
    EXTERNAL_FAILURE = "EXTERNAL_FAILURE"
    EXPECTED_BLOCK = "EXPECTED_BLOCK"
    AMBIGUOUS_CASE = "AMBIGUOUS_CASE"
    UNDETERMINED = "UNDETERMINED"


class DecisionSeverity(str, enum.Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class MissedObservationType(str, enum.Enum):
    OBSERVATION_AVAILABLE_BUT_UNUSED = "OBSERVATION_AVAILABLE_BUT_UNUSED"
    OBSERVATION_UNAVAILABLE = "OBSERVATION_UNAVAILABLE"
    OBSERVATION_LATE = "OBSERVATION_LATE"
    OBSERVATION_INCORRECT = "OBSERVATION_INCORRECT"
    NO_OBSERVATION_GAP = "NO_OBSERVATION_GAP"


class PredictionContributionType(str, enum.Enum):
    PREDICTION_CORRECT = "PREDICTION_CORRECT"
    PREDICTION_PARTIAL = "PREDICTION_PARTIAL"
    PREDICTION_INCORRECT = "PREDICTION_INCORRECT"
    PREDICTION_NOT_RELEVANT = "PREDICTION_NOT_RELEVANT"


class ExecutionContributionType(str, enum.Enum):
    EXECUTION_SUCCESS = "EXECUTION_SUCCESS"
    EXECUTION_FAILED_UNEXPECTEDLY = "EXECUTION_FAILED_UNEXPECTEDLY"
    EXECUTION_CRASHED = "EXECUTION_CRASHED"
    EXECUTION_NOT_RELEVANT = "EXECUTION_NOT_RELEVANT"


class PolicyStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PROPOSED = "PROPOSED"
    SHADOW = "SHADOW"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    ROLLED_BACK = "ROLLED_BACK"


class PolicyChangeType(str, enum.Enum):
    ADD_RULE = "ADD_RULE"
    MODIFY_RULE = "MODIFY_RULE"
    REMOVE_RULE = "REMOVE_RULE"
    CHANGE_PRIORITY = "CHANGE_PRIORITY"
    REFINE_CONDITION = "REFINE_CONDITION"


PROHIBITED_POLICY_OPERATIONS: set[str] = {
    "DISABLE_SECURITY",
    "BYPASS_MISSION_GATE",
    "REMOVE_EVIDENCE_REQUIREMENT",
    "REMOVE_HUMAN_APPROVAL_POLICY",
    "WEAKEN_ECONOMIC_LIMITS",
}


@dataclass
class RuleEvaluationRecord:
    rule_id: str
    priority: int
    condition_name: str
    evaluated: bool
    matched: bool
    rejected_reason: str = ""
    rule_decision: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DecisionTrace:
    trace_id: str
    mission_id: str
    cycle_id: str
    observations_summary: dict[str, Any]
    rules_evaluated: list[RuleEvaluationRecord]
    matched_rule_id: str
    decision: str
    gate_status: str
    action_executed: str
    result_observed: str
    evaluation_summary: str
    retrieved_experiences: list[str] = field(default_factory=list)
    rejected_experiences: list[str] = field(default_factory=list)
    applicability_results: dict[str, str] = field(default_factory=dict)
    memory_influence: str = "NONE"
    semantic_nodes: list[str] = field(default_factory=list)
    semantic_edges: list[str] = field(default_factory=list)
    translation_adapters: list[str] = field(default_factory=list)
    semantic_validation_status: str = "NONE"
    contract_analysis: Optional[dict[str, Any]] = None
    consumer_impact: list[dict[str, Any]] = field(default_factory=list)
    migration_id: Optional[str] = None
    contract_risk: str = "SAFE"
    gate_result: str = "NOT_EVALUATED"
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CounterfactualDecision:
    alternative_decision: LoopDecisionType
    why_valid: str
    why_not_selected: str
    expected_effect: str
    observed_effect: str
    evidence_support: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["alternative_decision"] = self.alternative_decision.value if hasattr(self.alternative_decision, "value") else str(self.alternative_decision)
        return d


@dataclass
class DecisionOutcome:
    outcome_id: str
    mission_id: str
    cycle_id: str
    decision_id: str
    decision_type: LoopDecisionType
    policy_version: str
    rule_id: str
    expected_outcome: str
    observed_outcome: str
    decision_correctness: DecisionCorrectness
    evidence_ids: list[str] = field(default_factory=list)
    deviation_type: str = "NONE"
    severity: DecisionSeverity = DecisionSeverity.INFO
    root_cause: DecisionErrorTaxonomy = DecisionErrorTaxonomy.UNDETERMINED
    contributing_factors: list[str] = field(default_factory=list)
    missed_observations: MissedObservationType = MissedObservationType.NO_OBSERVATION_GAP
    prediction_contribution: PredictionContributionType = PredictionContributionType.PREDICTION_NOT_RELEVANT
    execution_contribution: ExecutionContributionType = ExecutionContributionType.EXECUTION_NOT_RELEVANT
    policy_gap: str = ""
    counterfactual: Optional[CounterfactualDecision] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["decision_type"] = self.decision_type.value if hasattr(self.decision_type, "value") else str(self.decision_type)
        d["decision_correctness"] = self.decision_correctness.value
        d["severity"] = self.severity.value
        d["root_cause"] = self.root_cause.value
        d["missed_observations"] = self.missed_observations.value
        d["prediction_contribution"] = self.prediction_contribution.value
        d["execution_contribution"] = self.execution_contribution.value
        if self.counterfactual:
            d["counterfactual"] = self.counterfactual.to_dict()
        return d


@dataclass
class PolicyChangeProposal:
    proposal_id: str
    source_outcome_id: str
    current_policy_version: str
    proposed_policy_version: str
    change_type: PolicyChangeType
    affected_rules: list[str]
    old_conditions: str
    new_conditions: str
    expected_benefit: str
    possible_regression: str
    evidence_refs: list[str] = field(default_factory=list)
    confidence: float = 0.95
    requires_human_review: bool = True
    status: PolicyStatus = PolicyStatus.PROPOSED
    created_at: float = field(default_factory=time.time)
    approved_by: Optional[str] = None
    approved_at: Optional[float] = None
    rejection_reason: Optional[str] = None

    def validate_prohibited_operations(self) -> tuple[bool, str]:
        for prohibited in PROHIBITED_POLICY_OPERATIONS:
            if prohibited in self.change_type.value or prohibited in self.new_conditions:
                return False, f"Prohibited operation: {prohibited} cannot be proposed or executed."
        return True, "Valid proposal"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["change_type"] = self.change_type.value
        d["status"] = self.status.value
        return d


@dataclass
class DecisionQualityMetrics:
    total_decisions: int = 0
    correct_decisions: int = 0
    partially_correct_decisions: int = 0
    incorrect_decisions: int = 0
    accuracy: float = 0.0
    macro_precision: float = 0.0
    macro_recall: float = 0.0
    per_decision_precision: dict[str, float] = field(default_factory=dict)
    per_decision_recall: dict[str, float] = field(default_factory=dict)
    confusion_matrix: dict[str, dict[str, int]] = field(default_factory=dict)
    escalation_rate: float = 0.0
    false_continue_count: int = 0
    false_continue_rate: float = 0.0
    false_repair_count: int = 0
    false_replan_count: int = 0
    false_finish_count: int = 0
    false_finish_rate: float = 0.0
    false_escalation_count: int = 0
    false_escalation_rate: float = 0.0
    human_request_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ShadowComparisonRecord:
    comparison_id: str
    cycle_id: str
    active_policy_version: str
    active_decision: LoopDecisionType
    shadow_policy_version: str
    shadow_decision: LoopDecisionType
    agreement: bool
    disagreement_reason: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["active_decision"] = self.active_decision.value
        d["shadow_decision"] = self.shadow_decision.value
        return d
