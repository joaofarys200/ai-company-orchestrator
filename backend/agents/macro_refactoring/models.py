"""
JARVIS OS — Phase 73: Autonomous Macro-Refactoring Engine
Module: models.py
Domain models, contracts, enumerations, and lifecycle states for cross-system migrations.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set


class MigrationState(str, enum.Enum):
    """Lifecycle states for a macro-refactoring migration."""
    INITIALIZED = "INITIALIZED"
    PLANNING = "PLANNING"
    PLANNED = "PLANNED"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ACCEPTED_RISK = "COMPLETED_WITH_ACCEPTED_RISK"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    BLOCKED = "BLOCKED"
    ROLLING_BACK = "ROLLING_BACK"
    ROLLED_BACK = "ROLLED_BACK"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class StepState(str, enum.Enum):
    """Lifecycle states for individual migration steps."""
    PENDING = "PENDING"
    READY = "READY"
    EXECUTING = "EXECUTING"
    APPLIED = "APPLIED"
    LOCALLY_VERIFIED = "LOCALLY_VERIFIED"
    ACCEPTED = "ACCEPTED"
    INVALIDATED = "INVALIDATED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    SKIPPED = "SKIPPED"


class MigrationStepType(str, enum.Enum):
    """Canonical architectural migration stage types."""
    PREPARATION = "PREPARATION"
    COMPATIBILITY_LAYER = "COMPATIBILITY_LAYER"
    CONSUMER_MIGRATION = "CONSUMER_MIGRATION"
    DUAL_PATH = "DUAL_PATH"
    CUTOVER = "CUTOVER"
    OBSERVATION = "OBSERVATION"
    CLEANUP = "CLEANUP"
    ROLLBACK_COMPENSATION = "ROLLBACK_COMPENSATION"


class MacroRefactoringError(Exception):
    """Base exception for macro-refactoring failures."""
    pass


class DependencyCycleError(MacroRefactoringError):
    """Raised when a dependency cycle is detected in the migration graph."""
    pass


class UnresolvedDependencyError(MacroRefactoringError):
    """Raised when a step depends on an unknown or undiscovered step/component."""
    pass


class InvariantViolationError(MacroRefactoringError):
    """Raised when an architectural or behavioral invariant is violated."""
    pass


class StaleEvidenceError(MacroRefactoringError):
    """Raised when an operation attempts to rely on invalidated evidence."""
    pass


class CheckpointCorruptError(MacroRefactoringError):
    """Raised when a migration checkpoint file is corrupted or tampered with."""
    pass


class BudgetExceededError(MacroRefactoringError):
    """Raised when execution cost exceeds the authorized budget."""
    pass


class UnauthorizedMutationError(MacroRefactoringError):
    """Raised when an operation attempts mutation outside authorized workspace bounds."""
    pass


@dataclass
class EvidenceRecord:
    evidence_id: str
    step_id: str
    kind: str  # BUILD_LOG, TEST_RESULT, CONTRACT_HASH, BEHAVIOR_PROOF, ARTIFACT_DIFF
    content_hash: str
    timestamp: float = field(default_factory=time.time)
    valid: bool = True
    invalidation_reason: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InvalidationRecord:
    invalidation_id: str
    triggered_by_step_id: str
    invalidated_step_id: str
    evidence_id: str
    reason: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MigrationStep:
    step_id: str
    step_type: MigrationStepType
    title: str
    description: str
    affected_files: List[str] = field(default_factory=list)
    affected_symbols: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)  # Predecessor step IDs
    state: StepState = StepState.PENDING
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    verification_gates: List[str] = field(default_factory=list)
    compensation_action: str = ""
    evidence_refs: List[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 1
    error: Optional[str] = None
    applied_patch_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["step_type"] = self.step_type.value if isinstance(self.step_type, MigrationStepType) else str(self.step_type)
        d["state"] = self.state.value if isinstance(self.state, StepState) else str(self.state)
        return d


@dataclass
class MigrationCheckpoint:
    checkpoint_id: str
    sequence: int
    migration_id: str
    current_step_id: Optional[str]
    state_snapshot: Dict[str, Any]
    checksum: str
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CompensationPlan:
    plan_id: str
    migration_id: str
    steps_to_revert: List[str]  # Reverse topological order
    rollback_actions: Dict[str, str]
    is_safe: bool = True
    blocking_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MacroMigration:
    migration_id: str
    objective: str
    project_id: str
    status: MigrationState = MigrationState.INITIALIZED
    blast_radius_nodes: int = 0
    steps: Dict[str, MigrationStep] = field(default_factory=dict)
    execution_order: List[str] = field(default_factory=list)
    evidence_ledger: List[EvidenceRecord] = field(default_factory=list)
    invalidations: List[InvalidationRecord] = field(default_factory=list)
    checkpoints: List[MigrationCheckpoint] = field(default_factory=list)
    target_invariants: List[str] = field(default_factory=list)
    current_step_index: int = 0
    risk_score: float = 0.0
    execution_cost_budget: float = 100.0
    consumed_budget: float = 0.0
    provenance_hash: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    error: Optional[str] = None
    unresolved_blockers: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value if isinstance(self.status, MigrationState) else str(self.status)
        d["steps"] = {k: v.to_dict() for k, v in self.steps.items()}
        d["evidence_ledger"] = [e.to_dict() for e in self.evidence_ledger]
        d["invalidations"] = [i.to_dict() for i in self.invalidations]
        d["checkpoints"] = [c.to_dict() for c in self.checkpoints]
        return d
