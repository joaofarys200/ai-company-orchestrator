"""
JARVIS OS — Phase 40: Autonomous Engineering Loop & Closed-Loop Mission Adaptation
Package Exports.
"""

from agents.autonomous_loop.models import (
    AdaptationBudget,
    AdaptationProposal,
    AdaptationType,
    AutonomousLoopState,
    CausalExplanation,
    DriftClassification,
    LoopCycleFingerprint,
    LoopDecisionType,
    LoopObservationOutcome,
    LoopSnapshot,
    LoopStage,
    OscillationStatus,
)
from agents.autonomous_loop.policy import (
    AutonomousDecisionPolicy,
    PolicyEvaluationContext,
    PolicyRuleDefinition,
)
from agents.autonomous_loop.observation import (
    AutonomousLoopObserver,
    LoopObservation,
    ObservedTaskResult,
    ObservedValidationResult,
)
from agents.autonomous_loop.decision import (
    AutonomousDecisionEngine,
    AutonomousDecisionResult,
)
from agents.autonomous_loop.adaptation import AutonomousAdaptationEngine
from agents.autonomous_loop.state import AutonomousLoopStateManager
from agents.autonomous_loop.controller import AutonomousLoopController
from agents.autonomous_loop.metrics import (
    AutonomousLoopMetricsTracker,
    CycleLatencyBreakdown,
    MultiAxisAutonomyScore,
)

__all__ = [
    "AdaptationBudget",
    "AdaptationProposal",
    "AdaptationType",
    "AutonomousLoopState",
    "CausalExplanation",
    "DriftClassification",
    "LoopCycleFingerprint",
    "LoopDecisionType",
    "LoopObservationOutcome",
    "LoopSnapshot",
    "LoopStage",
    "OscillationStatus",
    "AutonomousDecisionPolicy",
    "PolicyEvaluationContext",
    "PolicyRuleDefinition",
    "AutonomousLoopObserver",
    "LoopObservation",
    "ObservedTaskResult",
    "ObservedValidationResult",
    "AutonomousDecisionEngine",
    "AutonomousDecisionResult",
    "AutonomousAdaptationEngine",
    "AutonomousLoopStateManager",
    "AutonomousLoopController",
    "AutonomousLoopMetricsTracker",
    "CycleLatencyBreakdown",
    "MultiAxisAutonomyScore",
]
