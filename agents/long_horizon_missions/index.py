"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
Package Index & High-Level API.
"""

from __future__ import annotations

from agents.long_horizon_missions.adaptation import (
    AdaptiveReplanner,
    UnauthorizedObjectiveModificationError,
)
from agents.long_horizon_missions.architecture import ArchitectureConsistencyGovernor
from agents.long_horizon_missions.behavior import BehaviorConsistencyGovernor
from agents.long_horizon_missions.bridge import LongHorizonMissionBridge
from agents.long_horizon_missions.budget import (
    BudgetExhaustedError,
    BudgetTracker,
)
from agents.long_horizon_missions.cache import MissionStateCache
from agents.long_horizon_missions.checkpoint import (
    CheckpointManager,
    CheckpointTamperError,
)
from agents.long_horizon_missions.completion import (
    CompletionEvaluator,
    PrematureCompletionError,
)
from agents.long_horizon_missions.constraints import (
    ConstraintSeverity,
    ConstraintValidator,
    MissionConstraint,
)
from agents.long_horizon_missions.contracts import ContractConsistencyGovernor
from agents.long_horizon_missions.coordination import (
    MissionCoordinationManager,
    MultiAgentBypassError,
)
from agents.long_horizon_missions.evidence import (
    EvidenceItem,
    EvidenceLedger,
)
from agents.long_horizon_missions.execution import MissionExecutionEngine
from agents.long_horizon_missions.metrics import MissionMetricsTracker
from agents.long_horizon_missions.milestones import (
    MilestoneManager,
    UnverifiedMilestoneError,
)
from agents.long_horizon_missions.mission_state import (
    InvalidStateTransitionError,
    MissionStateMachine,
)
from agents.long_horizon_missions.models import (
    CheckpointType,
    CompletionResult,
    FailureType,
    FinalTerminationState,
    LongHorizonMission,
    Milestone,
    MilestoneState,
    MissionBudget,
    MissionCheckpoint,
    MissionCompletionProof,
    MissionObjective,
    MissionPlan,
    MissionState,
    ObjectiveCategory,
    ObjectiveState,
    StallOscillationState,
)
from agents.long_horizon_missions.objectives import (
    ObjectiveDriftError,
    ObjectiveTracker,
)
from agents.long_horizon_missions.persistence import MissionPersistenceStore
from agents.long_horizon_missions.planning import (
    CyclicDependencyError,
    MissionPlanner,
)
from agents.long_horizon_missions.policy import (
    MissionGovernancePolicy,
    get_policy,
)
from agents.long_horizon_missions.provenance import ProvenanceTracker
from agents.long_horizon_missions.recovery import (
    CrashRecoveryEngine,
    RecoveryReconciliationError,
)
from agents.long_horizon_missions.risk import (
    RiskGovernor,
    RiskItem,
    RiskSeverity,
)
from agents.long_horizon_missions.security import (
    MissionSecuritySentinel,
    SecurityViolationError,
)
from agents.long_horizon_missions.validator import (
    MissionValidationError,
    MissionValidator,
)
from agents.long_horizon_missions.verification import (
    MissionVerifier,
    VerificationFailedError,
)

__all__ = [
    "AdaptiveReplanner",
    "ArchitectureConsistencyGovernor",
    "BehaviorConsistencyGovernor",
    "BudgetExhaustedError",
    "BudgetTracker",
    "CheckpointManager",
    "CheckpointTamperError",
    "CheckpointType",
    "CompletionEvaluator",
    "CompletionResult",
    "ConstraintSeverity",
    "ConstraintValidator",
    "ContractConsistencyGovernor",
    "CrashRecoveryEngine",
    "CyclicDependencyError",
    "EvidenceItem",
    "EvidenceLedger",
    "FailureType",
    "FinalTerminationState",
    "InvalidStateTransitionError",
    "LongHorizonMission",
    "LongHorizonMissionBridge",
    "Milestone",
    "MilestoneManager",
    "MilestoneState",
    "MissionBudget",
    "MissionCheckpoint",
    "MissionCompletionProof",
    "MissionConstraint",
    "MissionCoordinationManager",
    "MissionExecutionEngine",
    "MissionGovernancePolicy",
    "MissionMetricsTracker",
    "MissionObjective",
    "MissionPersistenceStore",
    "MissionPlan",
    "MissionPlanner",
    "MissionSecuritySentinel",
    "MissionState",
    "MissionStateCache",
    "MissionStateMachine",
    "MissionValidationError",
    "MissionValidator",
    "MissionVerifier",
    "MultiAgentBypassError",
    "ObjectiveCategory",
    "ObjectiveDriftError",
    "ObjectiveState",
    "ObjectiveTracker",
    "PrematureCompletionError",
    "ProvenanceTracker",
    "RecoveryReconciliationError",
    "RiskGovernor",
    "RiskItem",
    "RiskSeverity",
    "SecurityViolationError",
    "StallOscillationState",
    "UnauthorizedObjectiveModificationError",
    "UnverifiedMilestoneError",
    "VerificationFailedError",
    "get_policy",
]
