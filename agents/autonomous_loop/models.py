"""
JARVIS OS — Phase 40: Autonomous Engineering Loop & Closed-Loop Mission Adaptation
Core Data Models, State Definitions, Enums and Serialization.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import enum
import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Set, Tuple


class LoopStage(str, enum.Enum):
    SNAPSHOT = "SNAPSHOT"
    PREDICT = "PREDICT"
    PLAN = "PLAN"
    GATE = "GATE"
    EXECUTE = "EXECUTE"
    OBSERVE = "OBSERVE"
    COMPARE = "COMPARE"
    DECIDE = "DECIDE"
    APPLY_ADAPTATION = "APPLY_ADAPTATION"
    VALIDATE = "VALIDATE"
    RECORD = "RECORD"
    NEXT_CYCLE = "NEXT_CYCLE"
    FINISHED = "FINISHED"
    BLOCKED = "BLOCKED"
    WAITING_HUMAN = "WAITING_HUMAN"


class LoopDecisionType(str, enum.Enum):
    CONTINUE = "CONTINUE"
    ADAPT = "ADAPT"
    REPLAN = "REPLAN"
    REPAIR = "REPAIR"
    REASSIGN = "REASSIGN"
    WAIT = "WAIT"
    REQUEST_HUMAN = "REQUEST_HUMAN"
    BLOCK = "BLOCK"
    ROLLBACK = "ROLLBACK"
    COMPENSATE = "COMPENSATE"
    FINISH = "FINISH"


class AdaptationType(str, enum.Enum):
    MODIFY_TASK = "MODIFY_TASK"
    ADD_TASK = "ADD_TASK"
    REMOVE_TASK = "REMOVE_TASK"
    CHANGE_PRIORITY = "CHANGE_PRIORITY"
    REASSIGN = "REASSIGN"
    ADD_VALIDATION = "ADD_VALIDATION"
    REPLAN = "REPLAN"
    REPAIR = "REPAIR"
    REQUEST_HUMAN = "REQUEST_HUMAN"


class DriftClassification(str, enum.Enum):
    NO_DRIFT = "NO_DRIFT"
    CONTROLLED_DRIFT = "CONTROLLED_DRIFT"
    UNEXPECTED_DRIFT = "UNEXPECTED_DRIFT"


class OscillationStatus(str, enum.Enum):
    NORMAL = "NORMAL"
    SUSPECTED = "SUSPECTED"
    CONFIRMED_OSCILLATION = "CONFIRMED_OSCILLATION"


@dataclass
class AdaptationBudget:
    max_adaptations: int = 15
    max_replans: int = 5
    max_repairs: int = 5
    max_consecutive_failures: int = 3
    max_oscillations: int = 2
    max_human_requests: int = 5

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdaptationBudget:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class CausalExplanation:
    observation: str
    rule: str
    decision: str
    consequence: str
    evidence_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CausalExplanation:
        return cls(
            observation=data.get("observation", ""),
            rule=data.get("rule", ""),
            decision=data.get("decision", ""),
            consequence=data.get("consequence", ""),
            evidence_refs=data.get("evidence_refs", []),
        )


@dataclass
class AdaptationProposal:
    adaptation_id: str
    cycle_id: str
    adaptation_type: AdaptationType
    reason: str
    source_observation: dict[str, Any]
    previous_plan_version: int
    proposed_change: dict[str, Any]
    predicted_impact: dict[str, Any] = field(default_factory=dict)
    risk: str = "LOW"
    requires_approval: bool = False
    gate_result: Optional[dict[str, Any]] = None
    status: str = "PROPOSED"  # PROPOSED, APPROVED, REJECTED, APPLIED
    applied_at: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["adaptation_type"] = self.adaptation_type.value if isinstance(self.adaptation_type, AdaptationType) else self.adaptation_type
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdaptationProposal:
        data_copy = dict(data)
        if "adaptation_type" in data_copy:
            data_copy["adaptation_type"] = AdaptationType(data_copy["adaptation_type"])
        return cls(**{k: v for k, v in data_copy.items() if k in cls.__dataclass_fields__})


@dataclass
class LoopSnapshot:
    snapshot_id: str
    cycle_id: str
    mission_id: str
    intent_version: int
    plan_version: int
    mission_state_hash: str
    dag_hash: str
    active_tasks: list[dict[str, Any]] = field(default_factory=list)
    requirements: list[dict[str, Any]] = field(default_factory=list)
    constraints: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    workspace_snapshot_hash: str = ""
    architecture_graph_hash: str = ""
    prediction_state_hash: str = ""
    agent_state_hash: str = ""
    deterministic_hash: str = ""
    timestamp: float = field(default_factory=time.time)

    def compute_deterministic_hash(self) -> str:
        payload = {
            "snapshot_id": self.snapshot_id,
            "cycle_id": self.cycle_id,
            "mission_id": self.mission_id,
            "intent_version": self.intent_version,
            "plan_version": self.plan_version,
            "mission_state_hash": self.mission_state_hash,
            "dag_hash": self.dag_hash,
            "tasks_count": len(self.active_tasks),
            "requirements_count": len(self.requirements),
            "evidence_count": len(self.evidence),
            "workspace_snapshot_hash": self.workspace_snapshot_hash,
            "architecture_graph_hash": self.architecture_graph_hash,
            "prediction_state_hash": self.prediction_state_hash,
            "agent_state_hash": self.agent_state_hash,
        }
        serialized = json.dumps(payload, sort_keys=True)
        self.deterministic_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
        return self.deterministic_hash

    def to_dict(self) -> dict[str, Any]:
        if not self.deterministic_hash:
            self.compute_deterministic_hash()
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LoopSnapshot:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class LoopObservationOutcome:
    outcome_id: str
    cycle_id: str
    prediction_id: str
    matched: list[str] = field(default_factory=list)
    missed: list[str] = field(default_factory=list)
    overpredicted: list[str] = field(default_factory=list)
    underpredicted: list[str] = field(default_factory=list)
    unexpected_changes: list[str] = field(default_factory=list)
    discrepancy_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LoopObservationOutcome:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class LoopCycleFingerprint:
    cycle_id: str
    plan_hash: str
    adaptation_signature: str
    failure_signature: str
    task_states_signature: str
    state_repetition_count: int = 0
    fingerprint_hash: str = ""

    def compute_hash(self) -> str:
        payload = f"{self.plan_hash}:{self.adaptation_signature}:{self.failure_signature}:{self.task_states_signature}"
        self.fingerprint_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        return self.fingerprint_hash

    def to_dict(self) -> dict[str, Any]:
        if not self.fingerprint_hash:
            self.compute_hash()
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LoopCycleFingerprint:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class AutonomousLoopState:
    mission_id: str
    loop_version: int = 1
    cycle_id: str = "cycle_0"
    mission_version: int = 1
    intent_version: int = 1
    plan_version: int = 1
    current_stage: LoopStage = LoopStage.SNAPSHOT
    current_decision: LoopDecisionType = LoopDecisionType.CONTINUE
    current_observations: list[dict[str, Any]] = field(default_factory=list)
    latest_prediction_id: Optional[str] = None
    latest_outcome_id: Optional[str] = None
    latest_evidence_ids: list[str] = field(default_factory=list)
    active_failures: list[dict[str, Any]] = field(default_factory=list)
    active_repairs: list[dict[str, Any]] = field(default_factory=list)
    active_replans: list[dict[str, Any]] = field(default_factory=list)
    adaptation_count: int = 0
    consecutive_successes: int = 0
    consecutive_failures: int = 0
    human_intervention_count: int = 0
    state_hash: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def compute_state_hash(self) -> str:
        payload = {
            "mission_id": self.mission_id,
            "loop_version": self.loop_version,
            "cycle_id": self.cycle_id,
            "mission_version": self.mission_version,
            "intent_version": self.intent_version,
            "plan_version": self.plan_version,
            "stage": self.current_stage.value if isinstance(self.current_stage, LoopStage) else self.current_stage,
            "decision": self.current_decision.value if isinstance(self.current_decision, LoopDecisionType) else self.current_decision,
            "latest_prediction_id": self.latest_prediction_id,
            "latest_outcome_id": self.latest_outcome_id,
            "adaptation_count": self.adaptation_count,
            "consecutive_successes": self.consecutive_successes,
            "consecutive_failures": self.consecutive_failures,
            "human_intervention_count": self.human_intervention_count,
            "active_failures_count": len(self.active_failures),
            "evidence_count": len(self.latest_evidence_ids),
        }
        serialized = json.dumps(payload, sort_keys=True)
        self.state_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
        return self.state_hash

    def to_dict(self) -> dict[str, Any]:
        if not self.state_hash:
            self.compute_state_hash()
        d = asdict(self)
        d["current_stage"] = self.current_stage.value if isinstance(self.current_stage, LoopStage) else self.current_stage
        d["current_decision"] = self.current_decision.value if isinstance(self.current_decision, LoopDecisionType) else self.current_decision
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AutonomousLoopState:
        data_copy = dict(data)
        if "current_stage" in data_copy:
            data_copy["current_stage"] = LoopStage(data_copy["current_stage"])
        if "current_decision" in data_copy:
            data_copy["current_decision"] = LoopDecisionType(data_copy["current_decision"])
        return cls(**{k: v for k, v in data_copy.items() if k in cls.__dataclass_fields__})
