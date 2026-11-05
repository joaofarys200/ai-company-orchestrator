"""
JARVIS OS — Phase 74: Autonomous Architectural Evolution & Optimization
Public package exports.
"""

from .alternative_generator import AlternativeGenerator
from .bridge import ArchitecturalOptimizationBridge
from .evaluator import MultiObjectiveEvaluator
from .experiment_sandbox import ExperimentSandbox
from .hypothesis_engine import HypothesisEngine
from .learner import OptimizationLearner
from .models import (
    ArchitecturalAlternative,
    ArchitecturalMetricSnapshot,
    ArchitecturalOptimizationError,
    CalibrationRecord,
    ConstraintViolationError,
    ExperimentContaminationError,
    ExperimentOutcome,
    ExperimentRecord,
    InsufficientEvidenceError,
    OpportunityCategory,
    OptimizationDecision,
    OptimizationHypothesis,
    OptimizationOpportunity,
    OptimizationRegressionError,
    OptimizationState,
    ParetoEvaluation,
    StructuralPatternType,
    UnauthorizedExecutionError,
)
from .opportunity_detector import OpportunityDetector
from .persistence import OptimizationStore
from .prioritizer import OptimizationPrioritizer

__all__ = [
    "ArchitecturalOptimizationBridge",
    "OpportunityDetector",
    "HypothesisEngine",
    "AlternativeGenerator",
    "MultiObjectiveEvaluator",
    "ExperimentSandbox",
    "OptimizationPrioritizer",
    "OptimizationLearner",
    "OptimizationStore",
    "OptimizationOpportunity",
    "OptimizationHypothesis",
    "ArchitecturalAlternative",
    "ExperimentRecord",
    "ParetoEvaluation",
    "OptimizationDecision",
    "CalibrationRecord",
    "ArchitecturalMetricSnapshot",
    "OptimizationState",
    "ExperimentOutcome",
    "OpportunityCategory",
    "StructuralPatternType",
    "ArchitecturalOptimizationError",
    "InsufficientEvidenceError",
    "ConstraintViolationError",
    "ExperimentContaminationError",
    "OptimizationRegressionError",
    "UnauthorizedExecutionError",
]
