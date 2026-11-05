"""
JARVIS OS — Phase 79: Autonomous Adaptive Experimentation & Scientific Hypothesis Validation
Package exports.
"""

from .adapters import Phase75BudgetAdapter, Phase78CausalHypothesisAdapter
from .belief_updater import BayesianBeliefUpdater
from .bridge import AdaptiveExperimentationBridge
from .executor import ExperimentExecutor
from .information_theory import InformationTheoreticEngine
from .models import (
    AdaptiveExperimentationError,
    BudgetExhaustedError,
    CandidateExperiment,
    ExperimentExecutionRecord,
    InvalidHypothesisSpaceError,
    InvestigationSession,
    InvestigationState,
    OutcomeFidelity,
    ScientificHypothesis,
    StoppingReason,
    UnauthorizedExperimentError,
)
from .persistence import AdaptiveExperimentStore
from .selector import AdaptiveExperimentSelector
from .stopping_engine import AdaptiveStoppingEvaluator

__all__ = [
    "AdaptiveExperimentationBridge",
    "InformationTheoreticEngine",
    "BayesianBeliefUpdater",
    "AdaptiveStoppingEvaluator",
    "AdaptiveExperimentSelector",
    "ExperimentExecutor",
    "AdaptiveExperimentStore",
    "Phase78CausalHypothesisAdapter",
    "Phase75BudgetAdapter",
    "InvestigationState",
    "StoppingReason",
    "OutcomeFidelity",
    "ScientificHypothesis",
    "CandidateExperiment",
    "ExperimentExecutionRecord",
    "InvestigationSession",
    "AdaptiveExperimentationError",
    "BudgetExhaustedError",
    "UnauthorizedExperimentError",
    "InvalidHypothesisSpaceError",
]
