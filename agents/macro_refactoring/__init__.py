"""
JARVIS OS — Phase 73: Autonomous Macro-Refactoring Engine
Public module initialization.
"""

from .bridge import MacroRefactoringBridge
from .governance import MacroRefactoringGovernance
from .graph import MigrationGraph
from .invalidation import EvidenceInvalidator
from .models import (
    BudgetExceededError,
    CheckpointCorruptError,
    CompensationPlan,
    DependencyCycleError,
    EvidenceRecord,
    InvalidationRecord,
    InvariantViolationError,
    MacroMigration,
    MacroRefactoringError,
    MigrationCheckpoint,
    MigrationState,
    MigrationStep,
    MigrationStepType,
    StaleEvidenceError,
    StepState,
    UnauthorizedMutationError,
    UnresolvedDependencyError,
)
from .persistence import MacroRefactoringStore
from .planner import MacroRefactoringPlanner
from .recovery import (
    AdaptiveReplanEngine,
    CheckpointManager,
    CompensationOrchestrator,
)
from .step_executor import StepExecutor
from .verification import GlobalVerificationReport, MacroRefactoringVerifier

__all__ = [
    "MacroRefactoringBridge",
    "MacroRefactoringGovernance",
    "MigrationGraph",
    "EvidenceInvalidator",
    "MacroMigration",
    "MigrationStep",
    "MigrationState",
    "StepState",
    "MigrationStepType",
    "EvidenceRecord",
    "InvalidationRecord",
    "MigrationCheckpoint",
    "CompensationPlan",
    "MacroRefactoringError",
    "DependencyCycleError",
    "UnresolvedDependencyError",
    "InvariantViolationError",
    "StaleEvidenceError",
    "CheckpointCorruptError",
    "BudgetExceededError",
    "UnauthorizedMutationError",
    "MacroRefactoringStore",
    "MacroRefactoringPlanner",
    "CheckpointManager",
    "CompensationOrchestrator",
    "AdaptiveReplanEngine",
    "StepExecutor",
    "GlobalVerificationReport",
    "MacroRefactoringVerifier",
]
