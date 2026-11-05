"""
JARVIS OS — Phase 78: Autonomous Causal Diagnosis & Root-Cause Analysis
Module: models.py
Domain models, enums, exceptions, and data structures for causal graphs,
competing hypotheses, diagnostic experiments, and root-cause reports.
"""

from __future__ import annotations

import enum
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


class CausalNodeType(str, enum.Enum):
    """Categorization of nodes in a causal graph."""
    ROOT_CAUSE = "ROOT_CAUSE"                      # Originating defect, trigger, or failure
    CONTRIBUTING_FACTOR = "CONTRIBUTING_FACTOR"    # Environmental condition that exacerbated the failure
    INTERMEDIATE_EVENT = "INTERMEDIATE_EVENT"      # Cascading state transition in the causal chain
    OBSERVABLE_SYMPTOM = "OBSERVABLE_SYMPTOM"      # Direct failure manifestation (e.g. 504 Gateway Timeout)
    COMPETING_HYPOTHESIS = "COMPETING_HYPOTHESIS"  # Candidate unconfirmed root cause


class CausalEdgeType(str, enum.Enum):
    """Nature of causal dependency between two nodes."""
    DIRECTLY_CAUSES = "DIRECTLY_CAUSES"          # A directly causes B (deterministic or verified transition)
    EXACERBATES = "EXACERBATES"                  # A increases the likelihood or severity of B
    TRIGGERS = "TRIGGERS"                        # A initiates the occurrence of B
    CORRELATED_WITH = "CORRELATED_WITH"          # Co-occurs without demonstrated causal mechanism


class HypothesisStatus(str, enum.Enum):
    """Status of an explanatory root-cause hypothesis."""
    CANDIDATE = "CANDIDATE"          # Formulated, awaiting evaluation
    SUPPORTED = "SUPPORTED"          # Corroborated by available evidence
    CONFIRMED = "CONFIRMED"          # Authoritatively proven as the root cause
    REJECTED = "REJECTED"            # Contradicted by authoritative evidence
    INCONCLUSIVE = "INCONCLUSIVE"    # Evidence insufficient to confirm or refute


class DiagnosticOutcome(str, enum.Enum):
    """Final outcome of the causal diagnosis process."""
    ROOT_CAUSE_CONFIRMED = "ROOT_CAUSE_CONFIRMED"
    MULTIPLE_INTERACTING_CAUSES = "MULTIPLE_INTERACTING_CAUSES"
    INCONCLUSIVE_INSUFFICIENT_EVIDENCE = "INCONCLUSIVE_INSUFFICIENT_EVIDENCE"
    CONTRADICTED_BY_EVIDENCE = "CONTRADICTED_BY_EVIDENCE"
    NO_CAUSAL_LINK_FOUND = "NO_CAUSAL_LINK_FOUND"


class ExperimentScope(str, enum.Enum):
    """Scope and safety level of a diagnostic experiment."""
    READ_ONLY_INSPECTION = "READ_ONLY_INSPECTION"
    SANDBOX_EXECUTION = "SANDBOX_EXECUTION"
    METRIC_POLL = "METRIC_POLL"
    PRIVILEGED_CHECK = "PRIVILEGED_CHECK"


class ExperimentOutcome(str, enum.Enum):
    """Outcome of running a diagnostic experiment."""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"
    BLOCKED = "BLOCKED"


# --- Exceptions ---

class CausalDiagnosisError(Exception):
    """Base exception for causal diagnosis."""
    pass


class CyclicCausalGraphError(CausalDiagnosisError):
    """Raised when an invalid causal feedback loop is introduced without temporal decoupling."""
    pass


class UnauthorizedDiagnosticActionError(CausalDiagnosisError):
    """Raised when an experiment attempts privileged or destructive execution without authorization."""
    pass


class InconclusiveDiagnosisError(CausalDiagnosisError):
    """Raised or returned when available evidence cannot discriminate root causes."""
    pass


# --- Domain Data Structures ---

@dataclass
class TimelineEvent:
    """An event reconstructed chronologically in the incident context."""
    event_id: str
    timestamp: float
    subsystem: str
    event_type: str
    description: str
    payload: Dict[str, Any] = field(default_factory=dict)
    has_uncertain_timestamp: bool = False
    evidence_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CausalNode:
    """A node in the causal dependency DAG."""
    node_id: str
    node_type: CausalNodeType
    description: str
    subsystem: str
    timestamp: float = field(default_factory=time.time)
    evidence_refs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["node_type"] = self.node_type.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CausalNode:
        d = dict(data)
        d["node_type"] = CausalNodeType(d["node_type"])
        return cls(**d)


@dataclass
class CausalEdge:
    """A directed causal link between two nodes in the causal DAG."""
    source_id: str
    target_id: str
    edge_type: CausalEdgeType
    confidence: float = 1.0
    evidence_refs: List[str] = field(default_factory=list)
    mechanism: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["edge_type"] = self.edge_type.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CausalEdge:
        d = dict(data)
        d["edge_type"] = CausalEdgeType(d["edge_type"])
        return cls(**d)


@dataclass
class CausalHypothesis:
    """A candidate explanation accounting for the observed failure."""
    hypothesis_id: str
    title: str
    root_cause_node_id: str
    causal_path: List[str]                 # Sequence of node IDs from root cause to symptom
    supporting_evidence: List[str] = field(default_factory=list)
    contradicting_evidence: List[str] = field(default_factory=list)
    missing_evidence: List[str] = field(default_factory=list)
    confidence: float = 0.5                # Calibrated confidence in [0.0, 1.0]
    uncertainty_penalty: float = 0.0
    status: HypothesisStatus = HypothesisStatus.CANDIDATE
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CausalHypothesis:
        d = dict(data)
        d["status"] = HypothesisStatus(d["status"])
        return cls(**d)


@dataclass
class DiagnosticExperiment:
    """A safe, targeted diagnostic experiment designed to discriminate competing hypotheses."""
    experiment_id: str
    hypothesis_tested: str
    scope: ExperimentScope
    command_or_check: str
    expected_observation_if_true: str
    expected_observation_if_false: str
    is_read_only: bool = True
    requires_authorization: bool = False
    status: ExperimentOutcome = ExperimentOutcome.INCONCLUSIVE
    actual_observation: Optional[str] = None
    conclusion: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["scope"] = self.scope.value
        d["status"] = self.status.value
        return d


@dataclass
class CorrectiveAction:
    """A targeted remediation linked directly to a confirmed root cause."""
    action_id: str
    target_root_cause_id: str
    action_type: str
    description: str
    risks: str
    expected_effect: str
    verification_criteria: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DiagnosisReport:
    """The authoritative result of a completed causal diagnosis."""
    diagnosis_id: str
    incident_id: str
    symptom_description: str
    outcome: DiagnosticOutcome
    hypotheses: List[CausalHypothesis]
    confirmed_root_causes: List[str]
    causal_chain_descriptions: List[str]
    recommendations: List[CorrectiveAction]
    confidence_interval: Tuple[float, float]
    audit_trail: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "diagnosis_id": self.diagnosis_id,
            "incident_id": self.incident_id,
            "symptom_description": self.symptom_description,
            "outcome": self.outcome.value,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "confirmed_root_causes": self.confirmed_root_causes,
            "causal_chain_descriptions": self.causal_chain_descriptions,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "confidence_interval": list(self.confidence_interval),
            "audit_trail": self.audit_trail,
            "timestamp": self.timestamp,
        }
