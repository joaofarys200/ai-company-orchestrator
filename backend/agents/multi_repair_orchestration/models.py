"""
JARVIS OS — Phase 55: Transactional Multi-Repair Orchestration & Convergence
Core domain models, enumerations, and cryptographic data structures.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


def compute_deterministic_hash(data: Any) -> str:
    """Computes a stable SHA-256 hash over arbitrary structured data."""
    if isinstance(data, (dict, list)):
        payload = json.dumps(data, sort_keys=True, default=str)
    else:
        payload = str(data)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class TransactionStatus(str, Enum):
    PLANNED = "PLANNED"
    GATED = "GATED"
    EXECUTING = "EXECUTING"
    CHECKPOINTED = "CHECKPOINTED"
    VERIFYING = "VERIFYING"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    COMMITTED = "COMMITTED"
    PROVEN = "PROVEN"


class ConvergenceState(str, Enum):
    CONVERGING = "CONVERGING"
    CONVERGED = "CONVERGED"
    DIVERGING = "DIVERGING"
    STALLED = "STALLED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class RevealedFailureType(str, Enum):
    ORIGINAL_FAILURE = "ORIGINAL_FAILURE"
    REVEALED_FAILURE = "REVEALED_FAILURE"
    REGRESSION_FAILURE = "REGRESSION_FAILURE"
    NEW_UNRELATED_FAILURE = "NEW_UNRELATED_FAILURE"


class NodeRelationType(str, Enum):
    REPAIRS = "REPAIRS"
    DEPENDS_ON = "DEPENDS_ON"
    MAY_REVEAL = "MAY_REVEAL"
    CONFLICTS_WITH = "CONFLICTS_WITH"
    AFFECTS = "AFFECTS"
    VALIDATES = "VALIDATES"
    ROLLS_BACK = "ROLLS_BACK"


class ConflictType(str, Enum):
    OVERLAPPING_PATCH = "OVERLAPPING_PATCH"
    SYMBOL_COLLISION = "SYMBOL_COLLISION"
    DEPENDENCY_CONTRADICTION = "DEPENDENCY_CONTRADICTION"
    CONTRACT_VERSION_CONFLICT = "CONTRACT_VERSION_CONFLICT"
    AUTH_CONFLICT = "AUTH_CONFLICT"
    ECONOMIC_CONFLICT = "ECONOMIC_CONFLICT"


class TransactionProofResult(str, Enum):
    TRANSACTION_PROVEN = "TRANSACTION_PROVEN"
    TRANSACTION_REJECTED = "TRANSACTION_REJECTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    INSUFFICIENT_COVERAGE = "INSUFFICIENT_COVERAGE"
    NON_CONVERGENT = "NON_CONVERGENT"


@dataclass
class FailureItem:
    failure_id: str
    error_class: str
    symbol: str
    file_path: str
    line: int
    message: str
    evidence: str = ""
    mission_id: str = "default_mission"
    raw_log: str = ""
    fingerprint: str = ""
    failure_type: RevealedFailureType = RevealedFailureType.ORIGINAL_FAILURE
    revealed_by_repair_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.fingerprint:
            self.fingerprint = compute_deterministic_hash(
                f"{self.error_class}:{self.symbol}:{self.file_path}:{self.line}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FailureCluster:
    cluster_id: str
    root_cause_category: str
    shared_files: List[str]
    shared_symbols: List[str]
    shared_contracts: List[str]
    shared_consumers: List[str]
    shared_tasks: List[str]
    failures: List[FailureItem]
    cluster_signature: str = ""
    risk_score: float = 0.0
    mission_id: str = "default_mission"
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.cluster_signature:
            parts = [self.root_cause_category] + sorted(self.shared_files) + sorted(self.shared_symbols)
            self.cluster_signature = compute_deterministic_hash(":".join(parts))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "root_cause_category": self.root_cause_category,
            "shared_files": self.shared_files,
            "shared_symbols": self.shared_symbols,
            "shared_contracts": self.shared_contracts,
            "shared_consumers": self.shared_consumers,
            "shared_tasks": self.shared_tasks,
            "failures": [f.to_dict() for f in self.failures],
            "cluster_signature": self.cluster_signature,
            "risk_score": self.risk_score,
            "mission_id": self.mission_id,
            "created_at": self.created_at,
        }


@dataclass
class RepairNode:
    node_id: str
    node_type: str  # "REPAIR", "FAILURE", "ROOT_CAUSE", "FILE", "SYMBOL", "CONTRACT", "TASK"
    label: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RepairEdge:
    source_id: str
    target_id: str
    relation: NodeRelationType
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation.value,
            "metadata": self.metadata,
        }


@dataclass
class RepairGraph:
    nodes: Dict[str, RepairNode] = field(default_factory=dict)
    edges: List[RepairEdge] = field(default_factory=list)
    graph_hash: str = ""

    def __post_init__(self):
        if not self.graph_hash:
            self.recompute_hash()

    def recompute_hash(self) -> str:
        data = {
            "nodes": {k: n.to_dict() for k, n in sorted(self.nodes.items())},
            "edges": [e.to_dict() for e in self.edges],
        }
        self.graph_hash = compute_deterministic_hash(data)
        return self.graph_hash

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": {k: n.to_dict() for k, n in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
            "graph_hash": self.graph_hash,
        }


@dataclass
class ConflictReport:
    has_conflicts: bool
    conflict_type: Optional[ConflictType] = None
    description: str = ""
    conflicting_repairs: List[str] = field(default_factory=list)
    requires_human_review: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "has_conflicts": self.has_conflicts,
            "conflict_type": self.conflict_type.value if self.conflict_type else None,
            "description": self.description,
            "conflicting_repairs": self.conflicting_repairs,
            "requires_human_review": self.requires_human_review,
        }


@dataclass
class RepairCheckpoint:
    checkpoint_id: str
    transaction_id: str
    step_index: int
    repair_id: str
    state_hash: str
    tree_hash: str
    patch_hash: str
    verification_result: str
    created_at: float = field(default_factory=time.time)
    rollback_snapshot: Dict[str, str] = field(default_factory=dict)  # filepath -> content

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "transaction_id": self.transaction_id,
            "step_index": self.step_index,
            "repair_id": self.repair_id,
            "state_hash": self.state_hash,
            "tree_hash": self.tree_hash,
            "patch_hash": self.patch_hash,
            "verification_result": self.verification_result,
            "created_at": self.created_at,
            "snapshot_files": list(self.rollback_snapshot.keys()),
        }


@dataclass
class TransactionRisk:
    blast_radius: int
    files_count: int
    contracts_count: int
    consumers_count: int
    has_economic: bool
    has_security: bool
    max_repair_risk: float
    aggregated_risk_score: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TransactionProof:
    proof_id: str
    transaction_id: str
    repairs_count: int
    resolved_failures_count: int
    revealed_failures_count: int
    before_hash: str
    after_hash: str
    checkpoints_count: int
    behavior_proof: Dict[str, Any]
    regression_proof: Dict[str, Any]
    security_validation: Dict[str, Any]
    economic_validation: Dict[str, Any]
    rollback_validation: Dict[str, Any]
    convergence_status: ConvergenceState
    result: TransactionProofResult
    invariants: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "transaction_id": self.transaction_id,
            "repairs_count": self.repairs_count,
            "resolved_failures_count": self.resolved_failures_count,
            "revealed_failures_count": self.revealed_failures_count,
            "before_hash": self.before_hash,
            "after_hash": self.after_hash,
            "checkpoints_count": self.checkpoints_count,
            "behavior_proof": self.behavior_proof,
            "regression_proof": self.regression_proof,
            "security_validation": self.security_validation,
            "economic_validation": self.economic_validation,
            "rollback_validation": self.rollback_validation,
            "convergence_status": self.convergence_status.value,
            "result": self.result.value,
            "invariants": self.invariants,
            "created_at": self.created_at,
        }


@dataclass
class RepairTransaction:
    transaction_id: str
    mission_id: str
    cluster_id: str
    repairs: List[Any]  # List[RepairCandidate] from verified_repair
    dependencies: List[Tuple[str, str]]  # [(producer_repair_id, consumer_repair_id)]
    checkpoints: List[RepairCheckpoint] = field(default_factory=list)
    state_before_hash: str = ""
    state_after_hash: str = ""
    status: TransactionStatus = TransactionStatus.PLANNED
    proof: Optional[TransactionProof] = None
    rollback_lineage: List[Dict[str, Any]] = field(default_factory=list)
    revealed_failures: List[FailureItem] = field(default_factory=list)
    risk: Optional[TransactionRisk] = None
    convergence_state: ConvergenceState = ConvergenceState.UNKNOWN
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "mission_id": self.mission_id,
            "cluster_id": self.cluster_id,
            "repairs_count": len(self.repairs),
            "repair_ids": [getattr(r, "repair_id", str(r)) for r in self.repairs],
            "dependencies": self.dependencies,
            "checkpoints_count": len(self.checkpoints),
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "state_before_hash": self.state_before_hash,
            "state_after_hash": self.state_after_hash,
            "status": self.status.value,
            "proof": self.proof.to_dict() if self.proof else None,
            "rollback_lineage": self.rollback_lineage,
            "revealed_failures_count": len(self.revealed_failures),
            "revealed_failures": [rf.to_dict() for rf in self.revealed_failures],
            "risk": self.risk.to_dict() if self.risk else None,
            "convergence_state": self.convergence_state.value,
            "created_at": self.created_at,
        }
