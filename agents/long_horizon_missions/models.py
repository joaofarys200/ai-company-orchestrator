"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions & Mission-Level Governance
Core Data Models, Enums, and State Definitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Set, Tuple


class MissionState(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    READY = "READY"
    EXECUTING = "EXECUTING"
    WAITING = "WAITING"
    COLLECTING = "COLLECTING"
    VERIFYING = "VERIFYING"
    ADAPTING = "ADAPTING"
    CHECKPOINTING = "CHECKPOINTING"
    PAUSED = "PAUSED"
    BLOCKED = "BLOCKED"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    RECOVERING = "RECOVERING"
    FINISHING = "FINISHING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    ROLLED_BACK = "ROLLED_BACK"
    INCONCLUSIVE = "INCONCLUSIVE"


class ObjectiveCategory(str, Enum):
    PRIMARY_OBJECTIVES = "PRIMARY_OBJECTIVES"
    SECONDARY_OBJECTIVES = "SECONDARY_OBJECTIVES"
    INVARIANTS = "INVARIANTS"
    NON_GOALS = "NON_GOALS"


class ObjectiveState(str, Enum):
    UNSATISFIED = "UNSATISFIED"
    IN_PROGRESS = "IN_PROGRESS"
    SATISFIED = "SATISFIED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class MilestoneState(str, Enum):
    PLANNED = "PLANNED"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class CheckpointType(str, Enum):
    FULL = "FULL"
    MILESTONE = "MILESTONE"
    FAILURE = "FAILURE"
    PRE_MUTATION = "PRE_MUTATION"
    POST_VERIFICATION = "POST_VERIFICATION"


class FailureType(str, Enum):
    IMPLEMENTATION_FAILURE = "IMPLEMENTATION_FAILURE"
    TEST_FAILURE = "TEST_FAILURE"
    CONTRACT_FAILURE = "CONTRACT_FAILURE"
    BEHAVIOR_FAILURE = "BEHAVIOR_FAILURE"
    ARCHITECTURE_FAILURE = "ARCHITECTURE_FAILURE"
    AGENT_FAILURE = "AGENT_FAILURE"
    MERGE_FAILURE = "MERGE_FAILURE"
    RESOURCE_FAILURE = "RESOURCE_FAILURE"
    SECURITY_FAILURE = "SECURITY_FAILURE"
    TIMEOUT = "TIMEOUT"
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"


class StallOscillationState(str, Enum):
    PROGRESSING = "PROGRESSING"
    STALLED = "STALLED"
    OSCILLATING = "OSCILLATING"
    DIVERGING = "DIVERGING"
    BLOCKED = "BLOCKED"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class CompletionResult(str, Enum):
    COMPLETED_WITHIN_SCOPE = "COMPLETED_WITHIN_SCOPE"
    COMPLETED_WITH_UNRESOLVED_RISK = "COMPLETED_WITH_UNRESOLVED_RISK"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class FinalTerminationState(str, Enum):
    COMPLETED_WITHIN_SCOPE = "COMPLETED_WITHIN_SCOPE"
    COMPLETED_WITH_UNRESOLVED_RISK = "COMPLETED_WITH_UNRESOLVED_RISK"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    ROLLED_BACK = "ROLLED_BACK"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass
class MissionObjective:
    objective_id: str
    description: str
    category: ObjectiveCategory = ObjectiveCategory.PRIMARY_OBJECTIVES
    measurable_conditions: List[str] = field(default_factory=list)
    evidence_requirements: List[str] = field(default_factory=list)
    verification_requirements: List[str] = field(default_factory=list)
    priority: int = 1
    scope: str = "GLOBAL"
    status: ObjectiveState = ObjectiveState.UNSATISFIED
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "objective_id": self.objective_id,
            "description": self.description,
            "category": self.category.value,
            "measurable_conditions": list(self.measurable_conditions),
            "evidence_requirements": list(self.evidence_requirements),
            "verification_requirements": list(self.verification_requirements),
            "priority": self.priority,
            "scope": self.scope,
            "status": self.status.value,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MissionObjective:
        return cls(
            objective_id=data["objective_id"],
            description=data["description"],
            category=ObjectiveCategory(data.get("category", "PRIMARY_OBJECTIVES")),
            measurable_conditions=list(data.get("measurable_conditions", [])),
            evidence_requirements=list(data.get("evidence_requirements", [])),
            verification_requirements=list(data.get("verification_requirements", [])),
            priority=data.get("priority", 1),
            scope=data.get("scope", "GLOBAL"),
            status=ObjectiveState(data.get("status", "UNSATISFIED")),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class Milestone:
    milestone_id: str
    title: str
    objective_ids: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    agent_tasks: List[Dict[str, Any]] = field(default_factory=list)
    expected_outputs: List[str] = field(default_factory=list)
    verification_requirements: List[str] = field(default_factory=list)
    checkpoint_policy: str = "ON_COMPLETION"
    rollback_scope: str = "LOCAL"
    budget: Dict[str, float] = field(default_factory=dict)
    status: MilestoneState = MilestoneState.PLANNED
    actual_outputs: List[str] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "milestone_id": self.milestone_id,
            "title": self.title,
            "objective_ids": list(self.objective_ids),
            "dependencies": list(self.dependencies),
            "agent_tasks": [dict(t) for t in self.agent_tasks],
            "expected_outputs": list(self.expected_outputs),
            "verification_requirements": list(self.verification_requirements),
            "checkpoint_policy": self.checkpoint_policy,
            "rollback_scope": self.rollback_scope,
            "budget": dict(self.budget),
            "status": self.status.value,
            "actual_outputs": list(self.actual_outputs),
            "evidence_ids": list(self.evidence_ids),
            "error_message": self.error_message,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Milestone:
        return cls(
            milestone_id=data["milestone_id"],
            title=data.get("title", data["milestone_id"]),
            objective_ids=list(data.get("objective_ids", [])),
            dependencies=list(data.get("dependencies", [])),
            agent_tasks=[dict(t) for t in data.get("agent_tasks", [])],
            expected_outputs=list(data.get("expected_outputs", [])),
            verification_requirements=list(data.get("verification_requirements", [])),
            checkpoint_policy=data.get("checkpoint_policy", "ON_COMPLETION"),
            rollback_scope=data.get("rollback_scope", "LOCAL"),
            budget=dict(data.get("budget", {})),
            status=MilestoneState(data.get("status", "PLANNED")),
            actual_outputs=list(data.get("actual_outputs", [])),
            evidence_ids=list(data.get("evidence_ids", [])),
            error_message=data.get("error_message"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )


@dataclass
class MissionPlan:
    plan_id: str
    mission_id: str
    milestones: Dict[str, Milestone] = field(default_factory=dict)
    dag_edges: List[Tuple[str, str]] = field(default_factory=list)
    topological_order: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    replan_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "mission_id": self.mission_id,
            "milestones": {k: m.to_dict() for k, m in self.milestones.items()},
            "dag_edges": [list(e) for e in self.dag_edges],
            "topological_order": list(self.topological_order),
            "created_at": self.created_at,
            "replan_count": self.replan_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MissionPlan:
        plan = cls(
            plan_id=data["plan_id"],
            mission_id=data["mission_id"],
            created_at=data.get("created_at", time.time()),
            replan_count=data.get("replan_count", 0),
        )
        plan.milestones = {
            k: Milestone.from_dict(v)
            for k, v in data.get("milestones", {}).items()
        }
        plan.dag_edges = [tuple(e) for e in data.get("dag_edges", [])]
        plan.topological_order = list(data.get("topological_order", []))
        return plan


@dataclass
class MissionBudget:
    # 11 budget dimensions
    wall_time_sec: float = 3600.0
    cpu_sec: float = 1800.0
    memory_mb: float = 4096.0
    agent_executions: int = 500
    patches: int = 200
    retries: int = 50
    rollbacks: int = 30
    generated_tests: int = 500
    browser_sessions: int = 50
    architecture_changes: int = 20
    human_review_requests: int = 15

    # Consumed counters
    consumed_wall_time_sec: float = 0.0
    consumed_cpu_sec: float = 0.0
    consumed_memory_mb: float = 0.0
    consumed_agent_executions: int = 0
    consumed_patches: int = 0
    consumed_retries: int = 0
    consumed_rollbacks: int = 0
    consumed_generated_tests: int = 0
    consumed_browser_sessions: int = 0
    consumed_architecture_changes: int = 0
    consumed_human_review_requests: int = 0

    def remaining_pct(self) -> float:
        ratios = []
        if self.agent_executions > 0:
            ratios.append(max(0.0, 1.0 - (self.consumed_agent_executions / self.agent_executions)))
        if self.patches > 0:
            ratios.append(max(0.0, 1.0 - (self.consumed_patches / self.patches)))
        if self.wall_time_sec > 0:
            ratios.append(max(0.0, 1.0 - (self.consumed_wall_time_sec / self.wall_time_sec)))
        return (sum(ratios) / max(1, len(ratios))) * 100.0

    def is_exhausted(self) -> Tuple[bool, Optional[str]]:
        if self.consumed_wall_time_sec >= self.wall_time_sec:
            return True, "wall_time_sec"
        if self.consumed_cpu_sec >= self.cpu_sec:
            return True, "cpu_sec"
        if self.consumed_memory_mb >= self.memory_mb:
            return True, "memory_mb"
        if self.consumed_agent_executions >= self.agent_executions:
            return True, "agent_executions"
        if self.consumed_patches >= self.patches:
            return True, "patches"
        if self.consumed_retries >= self.retries:
            return True, "retries"
        if self.consumed_rollbacks >= self.rollbacks:
            return True, "rollbacks"
        if self.consumed_generated_tests >= self.generated_tests:
            return True, "generated_tests"
        if self.consumed_browser_sessions >= self.browser_sessions:
            return True, "browser_sessions"
        if self.consumed_architecture_changes >= self.architecture_changes:
            return True, "architecture_changes"
        if self.consumed_human_review_requests >= self.human_review_requests:
            return True, "human_review_requests"
        return False, None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "limits": {
                "wall_time_sec": self.wall_time_sec,
                "cpu_sec": self.cpu_sec,
                "memory_mb": self.memory_mb,
                "agent_executions": self.agent_executions,
                "patches": self.patches,
                "retries": self.retries,
                "rollbacks": self.rollbacks,
                "generated_tests": self.generated_tests,
                "browser_sessions": self.browser_sessions,
                "architecture_changes": self.architecture_changes,
                "human_review_requests": self.human_review_requests,
            },
            "consumed": {
                "wall_time_sec": self.consumed_wall_time_sec,
                "cpu_sec": self.consumed_cpu_sec,
                "memory_mb": self.consumed_memory_mb,
                "agent_executions": self.consumed_agent_executions,
                "patches": self.consumed_patches,
                "retries": self.consumed_retries,
                "rollbacks": self.consumed_rollbacks,
                "generated_tests": self.consumed_generated_tests,
                "browser_sessions": self.consumed_browser_sessions,
                "architecture_changes": self.consumed_architecture_changes,
                "human_review_requests": self.consumed_human_review_requests,
            },
            "remaining_pct": self.remaining_pct(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MissionBudget:
        lim = data.get("limits", {})
        con = data.get("consumed", {})
        return cls(
            wall_time_sec=lim.get("wall_time_sec", 3600.0),
            cpu_sec=lim.get("cpu_sec", 1800.0),
            memory_mb=lim.get("memory_mb", 4096.0),
            agent_executions=lim.get("agent_executions", 500),
            patches=lim.get("patches", 200),
            retries=lim.get("retries", 50),
            rollbacks=lim.get("rollbacks", 30),
            generated_tests=lim.get("generated_tests", 500),
            browser_sessions=lim.get("browser_sessions", 50),
            architecture_changes=lim.get("architecture_changes", 20),
            human_review_requests=lim.get("human_review_requests", 15),
            consumed_wall_time_sec=con.get("wall_time_sec", 0.0),
            consumed_cpu_sec=con.get("cpu_sec", 0.0),
            consumed_memory_mb=con.get("memory_mb", 0.0),
            consumed_agent_executions=con.get("agent_executions", 0),
            consumed_patches=con.get("patches", 0),
            consumed_retries=con.get("retries", 0),
            consumed_rollbacks=con.get("rollbacks", 0),
            consumed_generated_tests=con.get("generated_tests", 0),
            consumed_browser_sessions=con.get("browser_sessions", 0),
            consumed_architecture_changes=con.get("architecture_changes", 0),
            consumed_human_review_requests=con.get("human_review_requests", 0),
        )


@dataclass(frozen=True)
class MissionCheckpoint:
    checkpoint_id: str
    mission_id: str
    checkpoint_type: CheckpointType
    timestamp: float
    mission_state: str
    objective_state: Dict[str, Any]
    plan_dag: Dict[str, Any]
    agent_states: Dict[str, Any]
    claims: List[Dict[str, Any]]
    workspace_states: Dict[str, Any]
    transaction_states: Dict[str, Any]
    architecture_hash: str
    contract_hash: str
    behavior_hash: str
    verification_ledger: List[Dict[str, Any]]
    budget_remaining: Dict[str, float]
    evidence_root: str
    sha256_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "mission_id": self.mission_id,
            "checkpoint_type": self.checkpoint_type.value,
            "timestamp": self.timestamp,
            "mission_state": self.mission_state,
            "objective_state": self.objective_state,
            "plan_dag": self.plan_dag,
            "agent_states": self.agent_states,
            "claims": self.claims,
            "workspace_states": self.workspace_states,
            "transaction_states": self.transaction_states,
            "architecture_hash": self.architecture_hash,
            "contract_hash": self.contract_hash,
            "behavior_hash": self.behavior_hash,
            "verification_ledger": self.verification_ledger,
            "budget_remaining": self.budget_remaining,
            "evidence_root": self.evidence_root,
            "sha256_hash": self.sha256_hash,
        }

    @staticmethod
    def compute_sha256(payload: Dict[str, Any]) -> str:
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass
class MissionCompletionProof:
    mission_id: str
    primary_satisfied: bool
    secondary_status: Dict[str, str]
    required_tests: List[str]
    verification_coverage: float
    architecture_state: str
    contract_state: str
    behavior_state: str
    security_state: str
    unresolved_risks: List[str]
    residual_state: Dict[str, Any]
    evidence_refs: List[str]
    final_checkpoint: str
    result: CompletionResult
    evaluation_timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "primary_satisfied": self.primary_satisfied,
            "secondary_status": dict(self.secondary_status),
            "required_tests": list(self.required_tests),
            "verification_coverage": self.verification_coverage,
            "architecture_state": self.architecture_state,
            "contract_state": self.contract_state,
            "behavior_state": self.behavior_state,
            "security_state": self.security_state,
            "unresolved_risks": list(self.unresolved_risks),
            "residual_state": dict(self.residual_state),
            "evidence_refs": list(self.evidence_refs),
            "final_checkpoint": self.final_checkpoint,
            "result": self.result.value,
            "evaluation_timestamp": self.evaluation_timestamp,
        }


@dataclass
class LongHorizonMission:
    mission_id: str
    objective: str
    success_criteria: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    risk_policy: str = "STANDARD"
    verification_policy: str = "CONTINUOUS_F62"
    security_policy: str = "SANDBOXED_F65"
    budget: MissionBudget = field(default_factory=MissionBudget)
    plan: Optional[MissionPlan] = None
    current_state: MissionState = MissionState.CREATED
    checkpoint_id: Optional[str] = None
    evidence_root: str = "docs/evidence/"
    agent_roster: List[str] = field(default_factory=lambda: [
        "ArchitectAgent",
        "CoderAgent",
        "TesterAgent",
        "SecurityAgent",
        "VerificationAgent",
    ])
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    provenance: Dict[str, Any] = field(default_factory=dict)
    state_history: List[Tuple[str, float]] = field(default_factory=list)
    completion_proof: Optional[MissionCompletionProof] = None

    def __post_init__(self):
        if not self.state_history:
            self.state_history.append((self.current_state.value, self.created_at))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "objective": self.objective,
            "success_criteria": list(self.success_criteria),
            "constraints": list(self.constraints),
            "risk_policy": self.risk_policy,
            "verification_policy": self.verification_policy,
            "security_policy": self.security_policy,
            "budget": self.budget.to_dict(),
            "plan": self.plan.to_dict() if self.plan else None,
            "current_state": self.current_state.value,
            "checkpoint_id": self.checkpoint_id,
            "evidence_root": self.evidence_root,
            "agent_roster": list(self.agent_roster),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "provenance": dict(self.provenance),
            "state_history": list(self.state_history),
            "completion_proof": self.completion_proof.to_dict() if self.completion_proof else None,
        }
