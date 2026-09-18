"""
JARVIS OS — Phase 65: Safe Self-Modification & Transactional Architecture Implementation
Package Initialization
"""

from .bridge import SafeSelfModificationBridge
from .governance import GovernanceInputValidator
from .models import (
    BehaviorValidationResult,
    BuildValidationResult,
    CommitEligibility,
    CommitResult,
    ContractValidationResult,
    ConvergenceState,
    ModificationCheckpoint,
    ModificationPatch,
    ModificationPolicyType,
    ModificationTransaction,
    PlanStep,
    PreflightStatus,
    RollbackResult,
    SelfModificationPlan,
    TestValidationResult,
    TransactionalSnapshot,
    TransactionProvenanceRecord,
    TransactionState,
)
from .plan import SelfModificationPlanner
from .preflight import PreflightChecker
from .rollback import RollbackEngine
from .security import SecuritySentinel
from .snapshot import TransactionalSnapshotManager
from .transaction import TransactionEngine

__all__ = [
    "SafeSelfModificationBridge",
    "GovernanceInputValidator",
    "SelfModificationPlanner",
    "PreflightChecker",
    "TransactionalSnapshotManager",
    "TransactionEngine",
    "RollbackEngine",
    "SecuritySentinel",
    "TransactionState",
    "CommitEligibility",
    "ConvergenceState",
    "BehaviorValidationResult",
    "ContractValidationResult",
    "PreflightStatus",
    "ModificationPolicyType",
    "PlanStep",
    "SelfModificationPlan",
    "TransactionalSnapshot",
    "ModificationPatch",
    "ModificationCheckpoint",
    "ModificationTransaction",
    "BuildValidationResult",
    "TestValidationResult",
    "RollbackResult",
    "CommitResult",
    "TransactionProvenanceRecord",
]
