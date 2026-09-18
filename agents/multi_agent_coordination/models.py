"""
JARVIS OS — Phase 66: Multi-Agent Engineering Coordination & Conflict Arbitration
Module: models.py
Domain models, enums, intents, resource claims, conflict structures, and arbitration decisions.
"""

from __future__ import annotations

import enum
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set


class IntentState(str, enum.Enum):
    """Lifecycle state of an AgentEngineeringIntent."""
    PROPOSED = "PROPOSED"
    VALIDATED = "VALIDATED"
    CLAIMED = "CLAIMED"
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CONFLICTED = "CONFLICTED"
    ABORTED = "ABORTED"
    ROLLED_BACK = "ROLLED_BACK"


class ResourceGranularity(str, enum.Enum):
    """Granularity of coordinating shared codebase resources."""
    FILE = "FILE"
    SYMBOL = "SYMBOL"
    CONTRACT = "CONTRACT"
    BEHAVIOR = "BEHAVIOR"
    SERVICE = "SERVICE"
    ARCHITECTURE = "ARCHITECTURE"
    CONFIG = "CONFIG"
    PROTECTED_PATH = "PROTECTED_PATH"


class ClaimType(str, enum.Enum):
    """Resource claim permission levels."""
    READ = "READ"
    WRITE = "WRITE"
    EXCLUSIVE = "EXCLUSIVE"
    SHARED = "SHARED"
    STRUCTURAL = "STRUCTURAL"


class ConflictType(str, enum.Enum):
    """Categorized conflicts between concurrent agent intents."""
    FILE_CONFLICT = "FILE_CONFLICT"
    SYMBOL_CONFLICT = "SYMBOL_CONFLICT"
    CONTRACT_CONFLICT = "CONTRACT_CONFLICT"
    BEHAVIOR_CONFLICT = "BEHAVIOR_CONFLICT"
    ARCHITECTURE_CONFLICT = "ARCHITECTURE_CONFLICT"
    TEST_CONFLICT = "TEST_CONFLICT"
    SECURITY_CONFLICT = "SECURITY_CONFLICT"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    ORDER_CONFLICT = "ORDER_CONFLICT"


class ArbitrationResolution(str, enum.Enum):
    """Actionable resolutions for detected multi-agent conflicts."""
    SERIALIZE = "SERIALIZE"
    MERGE = "MERGE"
    REBASE = "REBASE"
    SPLIT = "SPLIT"
    CANCEL = "CANCEL"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    BLOCK = "BLOCK"


class SchedulingDecision(str, enum.Enum):
    """Scheduling verdict for an intent or wave of intents."""
    PARALLEL_SAFE = "PARALLEL_SAFE"
    SERIAL_REQUIRED = "SERIAL_REQUIRED"
    BLOCKED = "BLOCKED"


class DeadlockState(str, enum.Enum):
    """Status of coordination dependency deadlock analysis."""
    NO_DEADLOCK = "NO_DEADLOCK"
    WAITING = "WAITING"
    DEADLOCK = "DEADLOCK"
    RESOLVING = "RESOLVING"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class StarvationPolicy(str, enum.Enum):
    """Policy for resolving agent starvation."""
    FAIR = "FAIR"
    PRIORITY = "PRIORITY"
    MISSION_CRITICAL = "MISSION_CRITICAL"


class ConvergenceState(str, enum.Enum):
    """Convergence state across multi-agent coordination rounds (F56)."""
    CONVERGING = "CONVERGING"
    STABLE = "STABLE"
    STALLED = "STALLED"
    DIVERGING = "DIVERGING"
    OSCILLATING = "OSCILLATING"
    BLOCKED = "BLOCKED"
    HUMAN_REVIEW = "HUMAN_REVIEW"


@dataclass
class AgentEngineeringIntent:
    """Explicit declaration of intent by an engineering agent before modifying workspace."""
    agent_id: str
    mission_id: str
    task_id: str
    intent_id: str
    requested_files: List[str] = field(default_factory=list)
    requested_symbols: List[str] = field(default_factory=list)
    requested_contracts: List[str] = field(default_factory=list)
    expected_changes: List[str] = field(default_factory=list)
    expected_effect: str = ""
    risk: str = "LOW"
    priority: Dict[str, Any] = field(default_factory=lambda: {
        "mission_criticality": 1.0,
        "urgency": 1.0,
        "risk_penalty": 0.0,
        "priority_vector": [1.0, 1.0, 0.0],
    })
    dependencies: List[str] = field(default_factory=list)  # list of intent_ids
    provenance: Dict[str, Any] = field(default_factory=dict)
    policy: str = "STANDARD"
    timestamp: float = field(default_factory=time.time)
    state: IntentState = IntentState.PROPOSED
    wait_count: int = 0
    wait_age_sec: float = 0.0

    def compute_hash(self) -> str:
        payload = {
            "agent_id": self.agent_id,
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "intent_id": self.intent_id,
            "requested_files": sorted(self.requested_files),
            "requested_symbols": sorted(self.requested_symbols),
            "requested_contracts": sorted(self.requested_contracts),
            "expected_effect": self.expected_effect,
            "dependencies": sorted(self.dependencies),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["state"] = self.state.value if isinstance(self.state, IntentState) else str(self.state)
        res["intent_hash"] = self.compute_hash()
        return res


@dataclass
class ResourceClaim:
    """Lease or permission claim on a granular system resource."""
    claim_id: str
    agent_id: str
    intent_id: str
    resource_id: str = ""
    resource_type: ResourceGranularity = ResourceGranularity.FILE
    claim_type: ClaimType = ClaimType.READ
    granted_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    ttl_seconds: float = 300.0
    is_active: bool = True
    resource_uri: str = ""
    granularity: Optional[ResourceGranularity] = None

    def __post_init__(self):
        if not self.resource_id and self.resource_uri:
            self.resource_id = self.resource_uri
        elif not self.resource_uri and self.resource_id:
            self.resource_uri = self.resource_id
        if self.granularity is not None:
            self.resource_type = self.granularity
        else:
            self.granularity = self.resource_type
        if self.expires_at == 0.0:
            self.expires_at = self.granted_at + self.ttl_seconds

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        t = current_time or time.time()
        return t > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["resource_type"] = self.resource_type.value if isinstance(self.resource_type, ResourceGranularity) else str(self.resource_type)
        res["claim_type"] = self.claim_type.value if isinstance(self.claim_type, ClaimType) else str(self.claim_type)
        return res


@dataclass
class AgentConflict:
    """Detected conflict between two concurrent agent intents."""
    conflict_id: str
    intent_a: str
    intent_b: str
    resource: str
    conflict_type: ConflictType
    evidence: str = ""
    severity: str = "HIGH"  # LOW, MEDIUM, HIGH, CRITICAL
    resolution_options: List[ArbitrationResolution] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["conflict_type"] = self.conflict_type.value if isinstance(self.conflict_type, ConflictType) else str(self.conflict_type)
        res["resolution_options"] = [
            r.value if isinstance(r, ArbitrationResolution) else str(r)
            for r in self.resolution_options
        ]
        return res


@dataclass
class ArbitrationDecision:
    """Authoritative decision resolving an AgentConflict."""
    decision_id: str
    conflict_id: str
    resolution: ArbitrationResolution
    reason: str
    execution_order: List[str] = field(default_factory=list)  # ordered intent_ids
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    @property
    def preferred_order(self) -> List[str]:
        return self.execution_order

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["resolution"] = self.resolution.value if isinstance(self.resolution, ArbitrationResolution) else str(self.resolution)
        return res


@dataclass
class AgentChangeSet:
    """Produced code change proposal from an agent for merge coordination."""
    changeset_id: str
    agent_id: str
    intent_id: str
    transaction_id: str
    base_snapshot: str  # snapshot_sha256 of common ancestor
    patch: Any = ""
    affected_files: List[str] = field(default_factory=list)
    affected_symbols: List[str] = field(default_factory=list)
    affected_contracts: List[str] = field(default_factory=list)
    verification_evidence: Dict[str, Any] = field(default_factory=dict)
    patch_hash: str = ""
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self):
        if isinstance(self.patch, dict):
            self.patch = json.dumps(self.patch, sort_keys=True)
        elif not isinstance(self.patch, str):
            self.patch = str(self.patch)

    def is_stale(self, latest_snapshot: str) -> bool:
        return self.base_snapshot != latest_snapshot

    def compute_patch_hash(self) -> str:
        return hashlib.sha256(str(self.patch).encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["patch_hash"] = self.patch_hash or self.compute_patch_hash()
        return res


@dataclass
class MergeResult:
    """Outcome of 3-way merge and post-merge verification."""
    success: bool
    merge_id: str
    base_snapshot: str
    merged_snapshot: str = ""
    conflicts_encountered: List[str] = field(default_factory=list)
    files_merged: List[str] = field(default_factory=list)
    merged_files: Dict[str, str] = field(default_factory=dict)
    verification_passed: bool = False
    evidence_hash: str = ""
    duration_ms: float = 0.0
    status: str = "MERGED"  # MERGED, CONFLICT, FAILED, HUMAN_REVIEW

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RebaseResult:
    """Outcome of rebasing an agent's change onto a newer base snapshot."""
    success: bool
    rebase_id: str
    old_base: str
    new_base: str
    semantic_drift_detected: bool = False
    status: str = "REBASED"  # REBASED, REBASE_CONFLICT, HUMAN_REVIEW
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def new_base_snapshot(self) -> str:
        return self.new_base

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProvenanceRecord:
    """Causal lineage link in the multi-agent coordination graph."""
    record_id: str
    agent_id: str
    mission_id: str
    intent_id: str
    claim_ids: List[str] = field(default_factory=list)
    transaction_id: str = ""
    base_snapshot: str = ""
    patch_hash: str = ""
    merge_hash: str = ""
    verification_hash: str = ""
    parent_records: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    def compute_hash(self) -> str:
        payload = {
            "record_id": self.record_id,
            "agent_id": self.agent_id,
            "intent_id": self.intent_id,
            "transaction_id": self.transaction_id,
            "base_snapshot": self.base_snapshot,
            "patch_hash": self.patch_hash,
            "merge_hash": self.merge_hash,
            "verification_hash": self.verification_hash,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["record_hash"] = self.compute_hash()
        return res
