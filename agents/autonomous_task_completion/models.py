"""
JARVIS OS — Phase 57: Autonomous Task Completion & Mission Closure Models
Strongly-typed data contracts for autonomous mission completion, task understanding,
acceptance criteria verification, multi-dimensional evidence, objective retention,
formal completion proof, and human escalation governance.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class MissionState(str, Enum):
    CREATED = "CREATED"
    UNDERSTANDING = "UNDERSTANDING"
    PLANNING = "PLANNING"
    READY = "READY"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    REPAIRING = "REPAIRING"
    CONVERGING = "CONVERGING"
    PROVING = "PROVING"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RequirementCategory(str, Enum):
    USER_REQUIREMENT = "USER_REQUIREMENT"
    SYSTEM_INFERENCE = "SYSTEM_INFERENCE"
    ASSUMPTION = "ASSUMPTION"


class VerificationMethod(str, Enum):
    BUILD = "BUILD"
    TEST = "TEST"
    CONTRACT = "CONTRACT"
    BEHAVIOR = "BEHAVIOR"
    BROWSER = "BROWSER"
    SECURITY = "SECURITY"
    ARTIFACT = "ARTIFACT"


class CriterionStatus(str, Enum):
    PENDING = "PENDING"
    SATISFIED = "SATISFIED"
    FAILED = "FAILED"
    WAIVED = "WAIVED"


class MissionEvidenceType(str, Enum):
    ARTIFACT = "artifact"
    TEST = "test"
    BUILD = "build"
    RUNTIME = "runtime"
    CONTRACT = "contract"
    BEHAVIOR = "behavior"
    BROWSER = "browser"
    SECURITY = "security"
    REPAIR = "repair"
    ROLLBACK = "rollback"
    CONVERGENCE = "convergence"
    HUMAN_APPROVAL = "human_approval"


class EvidenceStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    UNVERIFIED = "UNVERIFIED"


class CompletionDecision(str, Enum):
    MISSION_PROVEN_COMPLETE = "MISSION_PROVEN_COMPLETE"
    MISSION_BLOCKED = "MISSION_BLOCKED"
    MISSION_FAILED = "MISSION_FAILED"
    MISSION_INSUFFICIENT_EVIDENCE = "MISSION_INSUFFICIENT_EVIDENCE"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


class MissionHumanReviewReason(str, Enum):
    REQUIREMENT_AMBIGUITY = "REQUIREMENT_AMBIGUITY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    INSUFFICIENT_COVERAGE = "INSUFFICIENT_COVERAGE"
    SECURITY_RISK = "SECURITY_RISK"
    ECONOMIC_RISK = "ECONOMIC_RISK"
    NON_CONVERGENCE = "NON_CONVERGENCE"
    CONFLICTING_REPAIRS = "CONFLICTING_REPAIRS"
    EXTERNAL_DEPENDENCY = "EXTERNAL_DEPENDENCY"
    HIGH_IMPACT_CHANGE = "HIGH_IMPACT_CHANGE"
    OBJECTIVE_CHANGE = "OBJECTIVE_CHANGE"
    POLICY_REQUIRED = "POLICY_REQUIRED"


class MissionCheckpointState(str, Enum):
    UNDERSTOOD = "UNDERSTOOD"
    PLANNED = "PLANNED"
    EXECUTION_STARTED = "EXECUTION_STARTED"
    FIRST_VALIDATION = "FIRST_VALIDATION"
    REPAIR_STARTED = "REPAIR_STARTED"
    CONVERGENCE_STARTED = "CONVERGENCE_STARTED"
    PROOF_STARTED = "PROOF_STARTED"
    COMPLETED = "COMPLETED"


@dataclass
class RequirementItem:
    req_id: str
    description: str
    category: RequirementCategory
    critical: bool = True
    source: str = "user_input"

    def to_dict(self) -> dict[str, Any]:
        return {
            "req_id": self.req_id,
            "description": self.description,
            "category": self.category.value,
            "critical": self.critical,
            "source": self.source,
        }


@dataclass
class AcceptanceCriterion:
    criterion_id: str
    description: str
    verification_method: VerificationMethod
    required: bool = True
    status: CriterionStatus = CriterionStatus.PENDING
    evidence_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "description": self.description,
            "verification_method": self.verification_method.value,
            "required": self.required,
            "status": self.status.value,
            "evidence_id": self.evidence_id,
            "details": self.details,
        }


@dataclass
class AmbiguityItem:
    ambiguity_id: str
    description: str
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    resolution_strategy: str  # DEFAULT_POLICY, REQUIRE_HUMAN, INFER
    chosen_resolution: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ambiguity_id": self.ambiguity_id,
            "description": self.description,
            "risk_level": self.risk_level,
            "resolution_strategy": self.resolution_strategy,
            "chosen_resolution": self.chosen_resolution,
        }


@dataclass
class TaskUnderstandingResult:
    task_id: str
    raw_intent: str
    normalized_intent: str
    objective: str
    constraints: list[str] = field(default_factory=list)
    required_outputs: list[str] = field(default_factory=list)
    requirements: list[RequirementItem] = field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = field(default_factory=list)
    risk_level: str = "LOW"
    ambiguities: list[AmbiguityItem] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    confidence: float = 1.0
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "raw_intent": self.raw_intent,
            "normalized_intent": self.normalized_intent,
            "objective": self.objective,
            "constraints": self.constraints,
            "required_outputs": self.required_outputs,
            "requirements": [r.to_dict() for r in self.requirements],
            "acceptance_criteria": [c.to_dict() for c in self.acceptance_criteria],
            "risk_level": self.risk_level,
            "ambiguities": [a.to_dict() for a in self.ambiguities],
            "missing_information": self.missing_information,
            "confidence": self.confidence,
            "provenance": self.provenance,
        }


@dataclass
class MissionEvidence:
    evidence_id: str
    type: MissionEvidenceType
    source: str
    timestamp: float
    hash: str
    mission_id: str
    status: EvidenceStatus = EvidenceStatus.VALID
    provenance: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        evidence_type: MissionEvidenceType,
        source: str,
        mission_id: str,
        payload: dict[str, Any],
        status: EvidenceStatus = EvidenceStatus.VALID,
        provenance: dict[str, Any] | None = None,
    ) -> MissionEvidence:
        eid = f"evi_{uuid.uuid4().hex[:10]}"
        now = time.time()
        payload_bytes = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        h = hashlib.sha256(f"{eid}:{evidence_type.value}:{source}:{now}:".encode("utf-8") + payload_bytes).hexdigest()
        return cls(
            evidence_id=eid,
            type=evidence_type,
            source=source,
            timestamp=now,
            hash=h,
            mission_id=mission_id,
            status=status,
            provenance=provenance or {"generator": "autonomous_task_completion"},
            payload=payload,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "type": self.type.value,
            "source": self.source,
            "timestamp": self.timestamp,
            "hash": self.hash,
            "mission_id": self.mission_id,
            "status": self.status.value,
            "provenance": self.provenance,
            "payload": self.payload,
        }


@dataclass
class MissionEvidenceSet:
    mission_id: str
    evidences: list[MissionEvidence] = field(default_factory=list)

    def add_evidence(self, ev: MissionEvidence) -> None:
        self.evidences.append(ev)

    def get_by_type(self, ev_type: MissionEvidenceType) -> list[MissionEvidence]:
        return [e for e in self.evidences if e.type == ev_type]

    def has_valid(self, ev_type: MissionEvidenceType) -> bool:
        return any(e.type == ev_type and e.status == EvidenceStatus.VALID for e in self.evidences)

    def compute_aggregate_hash(self) -> str:
        if not self.evidences:
            return hashlib.sha256(b"empty_evidence_set").hexdigest()
        sorted_hashes = sorted([e.hash for e in self.evidences])
        return hashlib.sha256("".join(sorted_hashes).encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "evidences": [e.to_dict() for e in self.evidences],
            "aggregate_hash": self.compute_aggregate_hash(),
            "count": len(self.evidences),
        }


@dataclass
class HumanReviewTicket:
    ticket_id: str
    mission_id: str
    reason: MissionHumanReviewReason
    evidence: list[str] = field(default_factory=list)
    blocked_action: str = ""
    possible_next_action: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    resolved: bool = False
    resolution: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "mission_id": self.mission_id,
            "reason": self.reason.value,
            "evidence": self.evidence,
            "blocked_action": self.blocked_action,
            "possible_next_action": self.possible_next_action,
            "created_at": self.created_at,
            "resolved": self.resolved,
            "resolution": self.resolution,
        }


@dataclass
class EconomicPolicy:
    authorization: bool = True
    amount: float = 0.0
    currency: str = "USD"
    ledger: str = "main_ledger"
    idempotency_key: str = field(default_factory=lambda: f"idem_{uuid.uuid4().hex[:8]}")
    refund_supported: bool = True
    rollback_supported: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "authorization": self.authorization,
            "amount": self.amount,
            "currency": self.currency,
            "ledger": self.ledger,
            "idempotency_key": self.idempotency_key,
            "refund_supported": self.refund_supported,
            "rollback_supported": self.rollback_supported,
        }


@dataclass
class MissionScorecard:
    tasks_total: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    repairs: int = 0
    rollbacks: int = 0
    risk: float = 0.0
    coverage: float = 1.0
    evidence_count: int = 0
    proofs: int = 0
    human_reviews: int = 0
    mission_duration: float = 0.0
    prediction_accuracy: float = 1.0
    repair_success: float = 1.0
    browser_status: str = "SKIPPED"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MissionCheckpoint:
    checkpoint_id: str
    mission_id: str
    checkpoint_type: MissionCheckpointState
    state_hash: str
    timestamp: float
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "mission_id": self.mission_id,
            "checkpoint_type": self.checkpoint_type.value,
            "state_hash": self.state_hash,
            "timestamp": self.timestamp,
            "data": self.data,
        }


@dataclass
class MissionCompletionProof:
    proof_id: str
    mission_id: str
    objective: str
    acceptance_criteria: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    invariants: list[str]
    failures: list[dict[str, Any]]
    repairs: list[dict[str, Any]]
    coverage: float
    risk: float
    convergence: dict[str, Any]
    initial_state_hash: str
    final_state_hash: str
    decision: CompletionDecision
    signature: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "mission_id": self.mission_id,
            "objective": self.objective,
            "acceptance_criteria": self.acceptance_criteria,
            "evidence": self.evidence,
            "invariants": self.invariants,
            "failures": self.failures,
            "repairs": self.repairs,
            "coverage": self.coverage,
            "risk": self.risk,
            "convergence": self.convergence,
            "initial_state_hash": self.initial_state_hash,
            "final_state_hash": self.final_state_hash,
            "decision": self.decision.value,
            "signature": self.signature,
            "timestamp": self.timestamp,
        }


@dataclass
class AutonomousMission:
    mission_id: str
    task_id: str
    objective: str
    original_objective: str
    requirements: list[RequirementItem] = field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = field(default_factory=list)
    plan: dict[str, Any] = field(default_factory=dict)
    state: MissionState = MissionState.CREATED
    risk: float = 0.0
    evidence_set: MissionEvidenceSet = field(default_factory=lambda: MissionEvidenceSet(mission_id=""))
    proof: MissionCompletionProof | None = None
    failures: list[dict[str, Any]] = field(default_factory=list)
    repairs: list[dict[str, Any]] = field(default_factory=list)
    transaction_history: list[dict[str, Any]] = field(default_factory=list)
    convergence: dict[str, Any] = field(default_factory=dict)
    final_decision: CompletionDecision | None = None
    initial_state_hash: str = ""
    final_state_hash: str = ""
    checkpoints: list[MissionCheckpoint] = field(default_factory=list)
    scorecard: MissionScorecard | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    economic_policy: EconomicPolicy | None = None
    human_tickets: list[HumanReviewTicket] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.evidence_set.mission_id:
            self.evidence_set.mission_id = self.mission_id
        if not self.initial_state_hash:
            self.initial_state_hash = hashlib.sha256(
                f"{self.mission_id}:{self.objective}:{time.time()}".encode("utf-8")
            ).hexdigest()

    def add_checkpoint(self, ctype: MissionCheckpointState, data: dict[str, Any] | None = None) -> MissionCheckpoint:
        cid = f"chk_{self.mission_id}_{ctype.value.lower()}_{len(self.checkpoints) + 1}"
        now = time.time()
        data_to_store = data or {}
        state_repr = f"{cid}:{ctype.value}:{now}:{len(self.evidence_set.evidences)}"
        shash = hashlib.sha256(state_repr.encode("utf-8")).hexdigest()
        cp = MissionCheckpoint(
            checkpoint_id=cid,
            mission_id=self.mission_id,
            checkpoint_type=ctype,
            state_hash=shash,
            timestamp=now,
            data=data_to_store,
        )
        self.checkpoints.append(cp)
        return cp

    def compute_current_state_hash(self) -> str:
        state_parts = [
            self.mission_id,
            self.state.value,
            self.objective,
            str(len(self.requirements)),
            str(len(self.acceptance_criteria)),
            self.evidence_set.compute_aggregate_hash(),
            str(len(self.failures)),
            str(len(self.repairs)),
            str(self.risk),
        ]
        return hashlib.sha256(":".join(state_parts).encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "objective": self.objective,
            "original_objective": self.original_objective,
            "requirements": [r.to_dict() for r in self.requirements],
            "acceptance_criteria": [c.to_dict() for c in self.acceptance_criteria],
            "plan": self.plan,
            "state": self.state.value,
            "risk": self.risk,
            "evidence_set": self.evidence_set.to_dict(),
            "proof": self.proof.to_dict() if self.proof else None,
            "failures": self.failures,
            "repairs": self.repairs,
            "transaction_history": self.transaction_history,
            "convergence": self.convergence,
            "final_decision": self.final_decision.value if self.final_decision else None,
            "initial_state_hash": self.initial_state_hash,
            "final_state_hash": self.final_state_hash,
            "checkpoints": [cp.to_dict() for cp in self.checkpoints],
            "scorecard": self.scorecard.to_dict() if self.scorecard else None,
            "provenance": self.provenance,
            "economic_policy": self.economic_policy.to_dict() if self.economic_policy else None,
            "human_tickets": [t.to_dict() for t in self.human_tickets],
            "metadata": self.metadata,
        }
