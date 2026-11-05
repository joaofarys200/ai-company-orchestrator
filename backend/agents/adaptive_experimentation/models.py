"""
JARVIS OS — Phase 79: Autonomous Adaptive Experimentation & Scientific Hypothesis Validation
Module: models.py
Domain models, enums, exceptions, and data structures for scientific hypotheses,
candidate experiments, information metrics, belief distributions, and investigation sessions.
"""

from __future__ import annotations

import enum
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


class InvestigationState(str, enum.Enum):
    """Lifecycle state of an adaptive scientific investigation."""
    INITIALIZED = "INITIALIZED"
    SELECTING_EXPERIMENT = "SELECTING_EXPERIMENT"
    EXECUTING = "EXECUTING"
    UPDATING_BELIEFS = "UPDATING_BELIEFS"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class StoppingReason(str, enum.Enum):
    """Evidence-based reason for stopping an adaptive investigation."""
    HYPOTHESIS_CONFIRMED = "HYPOTHESIS_CONFIRMED"
    MINIMAL_UNCERTAINTY = "MINIMAL_UNCERTAINTY"
    DIMINISHING_INFORMATION_GAIN = "DIMINISHING_INFORMATION_GAIN"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    NO_SAFE_EXPERIMENTS_REMAIN = "NO_SAFE_EXPERIMENTS_REMAIN"
    CONTRADICTED_INCONCLUSIVE = "CONTRADICTED_INCONCLUSIVE"


class OutcomeFidelity(str, enum.Enum):
    """Provenanced fidelity of an experiment outcome."""
    REAL_RUNTIME_EXECUTION = "REAL_RUNTIME_EXECUTION"
    SYNTHETIC_FIXTURE_EVIDENCE = "SYNTHETIC_FIXTURE_EVIDENCE"


# --- Exceptions ---

class AdaptiveExperimentationError(Exception):
    """Base exception for adaptive experimentation."""
    pass


class BudgetExhaustedError(AdaptiveExperimentationError):
    """Raised when an investigation exhausts its allocated resource or cost budget."""
    pass


class UnauthorizedExperimentError(AdaptiveExperimentationError):
    """Raised when an experiment requires privileged authorization that was not provided."""
    pass


class InvalidHypothesisSpaceError(AdaptiveExperimentationError):
    """Raised when a hypothesis space is malformed (e.g. empty or invalid probabilities)."""
    pass


# --- Domain Data Structures ---

@dataclass
class ScientificHypothesis:
    """A competing hypothesis evaluated in an investigation."""
    hypothesis_id: str
    statement: str
    prior_probability: float = 0.5
    posterior_probability: float = 0.5
    evidence_refs: List[str] = field(default_factory=list)
    status: str = "CANDIDATE"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ScientificHypothesis:
        return cls(**data)


@dataclass
class CandidateExperiment:
    """A candidate diagnostic or scientific experiment evaluated for information value."""
    experiment_id: str
    title: str
    probe_check: str
    # Likelihood mapping: outcome_name -> {hypothesis_id: probability P(o | H)}
    outcome_likelihoods: Dict[str, Dict[str, float]]
    cost: float = 0.1                      # Normalized cost in [0.0, 1.0]
    risk: float = 0.0                      # Normalized operational risk in [0.0, 1.0]
    is_read_only: bool = True
    requires_authorization: bool = False
    expected_info_gain: float = 0.0        # Computed Shannon EIG in bits
    utility_score: float = 0.0             # Net expected utility

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CandidateExperiment:
        return cls(**data)


@dataclass
class ExperimentExecutionRecord:
    """Record of an executed experiment and its empirical observation."""
    record_id: str
    experiment_id: str
    observation: str
    matched_outcome: str
    observation_time: float = field(default_factory=time.time)
    provenance_hash: str = ""
    cost_incurred: float = 0.0
    outcome_fidelity: OutcomeFidelity = OutcomeFidelity.REAL_RUNTIME_EXECUTION

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["outcome_fidelity"] = self.outcome_fidelity.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExperimentExecutionRecord:
        d = dict(data)
        d["outcome_fidelity"] = OutcomeFidelity(d["outcome_fidelity"])
        return cls(**d)


@dataclass
class InvestigationSession:
    """The authoritative record of an entire adaptive scientific investigation."""
    session_id: str
    question: str
    hypotheses: List[ScientificHypothesis]
    candidate_experiments: List[CandidateExperiment]
    executed_records: List[ExperimentExecutionRecord] = field(default_factory=list)
    belief_history: List[Dict[str, float]] = field(default_factory=list)
    state: InvestigationState = InvestigationState.INITIALIZED
    stopping_reason: Optional[StoppingReason] = None
    conclusion: str = ""
    confidence_interval: Tuple[float, float] = (0.0, 1.0)
    audit_trail: List[str] = field(default_factory=list)
    accumulated_cost: float = 0.0
    cost_budget: float = 1.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "question": self.question,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "candidate_experiments": [e.to_dict() for e in self.candidate_experiments],
            "executed_records": [r.to_dict() for r in self.executed_records],
            "belief_history": self.belief_history,
            "state": self.state.value,
            "stopping_reason": self.stopping_reason.value if self.stopping_reason else None,
            "conclusion": self.conclusion,
            "confidence_interval": list(self.confidence_interval),
            "audit_trail": self.audit_trail,
            "accumulated_cost": self.accumulated_cost,
            "cost_budget": self.cost_budget,
            "timestamp": self.timestamp,
        }
