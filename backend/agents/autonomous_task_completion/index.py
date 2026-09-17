"""
JARVIS OS — Phase 57: Autonomous Task Completion Index
Public export index for the autonomous task completion subsystem.
"""

from .bridge import AutonomousTaskCompletionBridge
from .completion import MissionCompletionEvaluator, ObjectiveRetentionGuard
from .convergence import IntegratedConvergenceEngine
from .evidence import EvidenceCollector
from .executor import AutonomousMissionExecutor
from .failure import FailureCategory, FailureManager, FailureSeverity
from .gate import GateVerdict, MissionSafetyGate
from .intent import IntentUnderstandingEngine
from .memory import MissionExperienceMemory
from .metrics import MissionMetricsCalculator
from .mission import AutonomousMissionManager, MissionTransitionError
from .models import (
    AcceptanceCriterion,
    AmbiguityItem,
    AutonomousMission,
    CompletionDecision,
    CriterionStatus,
    EconomicPolicy,
    EvidenceStatus,
    HumanReviewTicket,
    MissionCheckpoint,
    MissionCheckpointState,
    MissionEvidence,
    MissionEvidenceSet,
    MissionEvidenceType,
    MissionHumanReviewReason,
    MissionScorecard,
    MissionState,
    RequirementCategory,
    RequirementItem,
    TaskUnderstandingResult,
    VerificationMethod,
)
from .observer import MissionObserver
from .planner import MissionPlanner
from .proof import MissionProofSynthesizer
from .repair import IntegratedRepairEngine
from .requirements import RequirementsExtractor
from .risk import MissionRiskScorer
from .security import MissionSecuritySentinel
from .validator import MultiLevelValidator
from .validator_registry import ValidatorRegistry

__all__ = [
    "AutonomousMission",
    "AutonomousMissionExecutor",
    "AutonomousMissionManager",
    "AutonomousTaskCompletionBridge",
    "AcceptanceCriterion",
    "AmbiguityItem",
    "CompletionDecision",
    "CriterionStatus",
    "EconomicPolicy",
    "EvidenceCollector",
    "EvidenceStatus",
    "FailureCategory",
    "FailureManager",
    "FailureSeverity",
    "GateVerdict",
    "HumanReviewTicket",
    "IntegratedConvergenceEngine",
    "IntegratedRepairEngine",
    "IntentUnderstandingEngine",
    "MissionCheckpoint",
    "MissionCheckpointState",
    "MissionCompletionEvaluator",
    "MissionEvidence",
    "MissionEvidenceSet",
    "MissionEvidenceType",
    "MissionExperienceMemory",
    "MissionHumanReviewReason",
    "MissionMetricsCalculator",
    "MissionObserver",
    "MissionPlanner",
    "MissionProofSynthesizer",
    "MissionRiskScorer",
    "MissionSafetyGate",
    "MissionSecuritySentinel",
    "MissionState",
    "MissionTransitionError",
    "MultiLevelValidator",
    "ObjectiveRetentionGuard",
    "RequirementCategory",
    "RequirementItem",
    "RequirementsExtractor",
    "TaskUnderstandingResult",
    "ValidatorRegistry",
    "VerificationMethod",
]
