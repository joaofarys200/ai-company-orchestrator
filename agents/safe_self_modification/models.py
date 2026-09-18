"""
JARVIS OS — Phase 65: Safe Self-Modification & Transactional Architecture Implementation
Module: models.py
Strongly typed domain models, enums, dataclasses, and immutable records for
transactional self-modification, patch lifecycle, snapshots, checkpoints,
build/test validation, contract/behavior verification, architecture rescan,
rollback, convergence, and commit gating.

Core Invariants:
    APPROVAL != IMPLEMENTATION
    IMPLEMENTATION != COMMITTED_STATE
    PATCH_APPLIED != PROBLEM_SOLVED (requires empirical Architecture Re-Scan)
    ROLLBACK_SUCCESS == (CURRENT_HASHES == SNAPSHOT_HASHES)
    SECURITY SENTINEL SUPREMACY & PROTECTED PATHS
"""

from __future__ import annotations

import enum
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


class TransactionState(str, enum.Enum):
    """Finite State Machine states for ModificationTransaction."""
    CREATED = "CREATED"
    PREFLIGHT = "PREFLIGHT"
    SNAPSHOTTED = "SNAPSHOTTED"
    PLANNED = "PLANNED"
    PATCHING = "PATCHING"
    PATCH_VALIDATED = "PATCH_VALIDATED"
    APPLYING = "APPLYING"
    APPLIED = "APPLIED"
    BUILDING = "BUILDING"
    TESTING = "TESTING"
    VERIFYING = "VERIFYING"
    ARCHITECTURE_RESCANNING = "ARCHITECTURE_RESCANNING"
    COMMIT_READY = "COMMIT_READY"
    COMMITTED = "COMMITTED"
    ROLLING_BACK = "ROLLING_BACK"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class CommitEligibility(str, enum.Enum):
    """Multi-condition commit gate verdict."""
    COMMIT_ELIGIBLE = "COMMIT_ELIGIBLE"
    COMMIT_BLOCKED = "COMMIT_BLOCKED"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class ConvergenceState(str, enum.Enum):
    """Lyapunov convergence state for self-modification loop (F56)."""
    CONVERGING = "CONVERGING"
    STABLE = "STABLE"
    STALLED = "STALLED"
    DIVERGING = "DIVERGING"
    OSCILLATING = "OSCILLATING"
    BLOCKED = "BLOCKED"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class BehaviorValidationResult(str, enum.Enum):
    """Behavior preservation verdict (F50-F52)."""
    PRESERVED_WITHIN_SCOPE = "PRESERVED_WITHIN_SCOPE"
    POTENTIAL_DRIFT = "POTENTIAL_DRIFT"
    INCOMPATIBLE = "INCOMPATIBLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ContractValidationResult(str, enum.Enum):
    """Contract compatibility verdict (F44-F49)."""
    NON_BREAKING = "NON_BREAKING"
    POTENTIALLY_BREAKING = "POTENTIALLY_BREAKING"
    BREAKING = "BREAKING"
    UNKNOWN = "UNKNOWN"


class PreflightStatus(str, enum.Enum):
    """Preflight check status."""
    PASSED = "PASSED"
    FAILED = "FAILED"
    WARNING = "WARNING"


class ModificationPolicyType(str, enum.Enum):
    """Execution policy modes."""
    STRICT = "STRICT"
    STANDARD = "STANDARD"
    DEVELOPMENT = "DEVELOPMENT"
    EMERGENCY_ROLLBACK = "EMERGENCY_ROLLBACK"


@dataclass
class PlanStep:
    """Atomic step in a SelfModificationPlan."""
    step_id: str
    step_type: str
    title: str
    description: str
    target_files: List[str] = field(default_factory=list)
    target_symbols: List[str] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    expected_changes: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    rollback_action: str = ""
    is_reversibility_supported: bool = True
    verification_gates: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SelfModificationPlan:
    """Concrete, verified self-modification execution plan."""
    plan_id: str
    governance_decision_id: str
    problem_id: str
    alternative_id: str
    ordered_steps: List[PlanStep] = field(default_factory=list)
    affected_files: List[str] = field(default_factory=list)
    affected_symbols: List[str] = field(default_factory=list)
    expected_contract_changes: List[str] = field(default_factory=list)
    expected_behavior_changes: List[str] = field(default_factory=list)
    expected_tests: List[str] = field(default_factory=list)
    checkpoints: List[str] = field(default_factory=list)
    rollback_points: List[str] = field(default_factory=list)
    budgets: Dict[str, Any] = field(default_factory=lambda: {
        "max_iterations": 3,
        "max_patches": 10,
        "max_retries": 2,
        "max_wall_time_sec": 300,
        "max_memory_mb": 512,
    })
    security_policy: str = "STRICT_SENTINEL"
    verification_policy: str = "CONTINUOUS_VERIFICATION_REQUIRED"
    plan_hash: str = ""
    timestamp: float = field(default_factory=time.time)

    def compute_hash(self) -> str:
        payload = {
            "plan_id": self.plan_id,
            "governance_decision_id": self.governance_decision_id,
            "problem_id": self.problem_id,
            "alternative_id": self.alternative_id,
            "affected_files": sorted(self.affected_files),
            "affected_symbols": sorted(self.affected_symbols),
            "steps": [s.step_id for s in self.ordered_steps],
        }
        can = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(can.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["ordered_steps"] = [s.to_dict() for s in self.ordered_steps]
        return res


@dataclass
class TransactionalSnapshot:
    """Immutable pre-modification snapshot of files, symbols, contracts, and baselines."""
    snapshot_id: str
    snapshot_sha256: str = ""
    files_state: Dict[str, str] = field(default_factory=dict)  # path -> sha256
    file_contents: Dict[str, str] = field(default_factory=dict)  # path -> content
    symbol_hashes: Dict[str, str] = field(default_factory=dict)
    contract_hashes: Dict[str, str] = field(default_factory=dict)
    architecture_hash: str = ""
    test_hashes: Dict[str, str] = field(default_factory=dict)
    environment_metadata: Dict[str, Any] = field(default_factory=dict)
    governance_decision_hash: str = ""
    created_at: float = field(default_factory=time.time)

    def compute_hash(self) -> str:
        payload = {
            "snapshot_id": self.snapshot_id,
            "files_state": sorted(self.files_state.items()),
            "symbol_hashes": sorted(self.symbol_hashes.items()),
            "contract_hashes": sorted(self.contract_hashes.items()),
            "architecture_hash": self.architecture_hash,
            "governance_decision_hash": self.governance_decision_hash,
        }
        can = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(can.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "snapshot_sha256": self.snapshot_sha256,
            "files_count": len(self.files_state),
            "files_state": self.files_state,
            "symbol_hashes_count": len(self.symbol_hashes),
            "contract_hashes_count": len(self.contract_hashes),
            "architecture_hash": self.architecture_hash,
            "environment_metadata": self.environment_metadata,
            "governance_decision_hash": self.governance_decision_hash,
            "created_at": self.created_at,
        }


@dataclass
class ModificationPatch:
    """A verified minimal change with an exact inverse rollback patch."""
    patch_id: str
    step_id: str
    target_files: List[str]
    target_symbols: List[str]
    diff: str
    expected_effect: str
    provenance: Dict[str, Any] = field(default_factory=dict)
    risk: str = "LOW"
    rollback_patch: str = ""
    patch_hash: str = ""
    is_valid: bool = True
    new_contents: Dict[str, str] = field(default_factory=dict)  # path -> updated content

    def compute_hash(self) -> str:
        payload = {
            "patch_id": self.patch_id,
            "step_id": self.step_id,
            "target_files": sorted(self.target_files),
            "diff": self.diff,
            "rollback_patch": self.rollback_patch,
        }
        can = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(can.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patch_id": self.patch_id,
            "step_id": self.step_id,
            "target_files": self.target_files,
            "target_symbols": self.target_symbols,
            "diff": self.diff,
            "expected_effect": self.expected_effect,
            "risk": self.risk,
            "patch_hash": self.patch_hash,
            "is_valid": self.is_valid,
            "rollback_patch": self.rollback_patch,
            "provenance": self.provenance,
        }


@dataclass
class ModificationCheckpoint:
    """Audit point captured before/after critical modification operations."""
    checkpoint_id: str
    transaction_id: str
    step_id: str
    file_hashes: Dict[str, str] = field(default_factory=dict)
    graph_hash: str = ""
    contract_hash: str = ""
    behavior_evidence: str = ""
    verification_evidence: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ModificationTransaction:
    """Sovereign transaction managing the lifecycle of an architecture modification."""
    transaction_id: str
    parent_transaction_id: Optional[str] = None
    snapshot_id: str = ""
    checkpoint_ids: List[str] = field(default_factory=list)
    current_state: TransactionState = TransactionState.CREATED
    state_history: List[Dict[str, Any]] = field(default_factory=list)
    governance_decision_id: str = ""
    plan_id: str = ""
    patches: List[ModificationPatch] = field(default_factory=list)
    error_message: Optional[str] = None
    residual_changes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def transition_to(self, new_state: TransactionState, reason: str = "") -> None:
        self.state_history.append({
            "from_state": self.current_state.value,
            "to_state": new_state.value,
            "reason": reason,
            "timestamp": time.time(),
        })
        self.current_state = new_state
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "parent_transaction_id": self.parent_transaction_id,
            "snapshot_id": self.snapshot_id,
            "checkpoint_ids": self.checkpoint_ids,
            "current_state": self.current_state.value,
            "state_history": self.state_history,
            "governance_decision_id": self.governance_decision_id,
            "plan_id": self.plan_id,
            "patches_count": len(self.patches),
            "patches": [p.to_dict() for p in self.patches],
            "error_message": self.error_message,
            "residual_changes": self.residual_changes,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class BuildValidationResult:
    """Result of post-apply build and syntax validation."""
    status: str = "PASS"  # PASS, FAIL
    compile_passed: bool = True
    syntax_passed: bool = True
    import_passed: bool = True
    pip_check_passed: bool = True
    frontend_build_passed: bool = True
    details: List[str] = field(default_factory=list)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TestValidationResult:
    """Result of test execution on modified code (F61/F62)."""
    status: str = "PASS"  # PASS, FAIL
    selected_tests: List[str] = field(default_factory=list)
    executed_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    synthesized_tests_passed: int = 0
    coverage_delta: float = 0.0
    details: List[str] = field(default_factory=list)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ArchitectureRescanResult:
    """Empirical re-scan comparing architecture BEFORE vs AFTER."""
    status: str = "IMPROVED"  # IMPROVED, UNCHANGED, REGRESSED
    problem_resolved: bool = True
    before_coupling: float = 0.0
    after_coupling: float = 0.0
    before_scc_count: int = 0
    after_scc_count: int = 0
    coupling_delta: float = 0.0
    scc_delta: int = 0
    new_problems_detected: List[str] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RollbackResult:
    """Outcome of deterministic rollback execution."""
    success: bool
    restored_files: List[str] = field(default_factory=list)
    hash_verification_passed: bool = True
    residual_changes: List[str] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CommitResult:
    """Final commit outcome after fulfilling all CommitGate requirements."""
    status: CommitEligibility
    commit_hash: str = ""
    message: str = ""
    verification_ledger_entry: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["status"] = self.status.value
        return res


@dataclass
class TransactionProvenanceRecord:
    """Cryptographic audit chain record for transactional actions."""
    record_id: str
    transaction_id: str
    action: str
    actor: str
    timestamp: float = field(default_factory=time.time)
    hash_signature: str = ""
    parent_hash: str = ""

    def compute_signature(self) -> str:
        payload = f"{self.record_id}:{self.transaction_id}:{self.action}:{self.actor}:{self.timestamp}:{self.parent_hash}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
