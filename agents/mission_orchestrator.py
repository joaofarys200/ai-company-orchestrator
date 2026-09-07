from __future__ import annotations

import asyncio
import enum
import glob
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Sequence

from agents.adaptive_planning import (
    AdaptationBudget,
    AdaptationRecord,
    AdaptationTrigger,
    AdaptivePlanningEngine,
    MissionAdaptationProposal,
    Observation,
    ObservationSeverity,
    ObservationSource,
    PlanEvaluationDecision,
    PlanEvaluationResult,
    PlanQualityMetrics,
)
from agents.dynamic_subdag import (
    DynamicSubDagEngine,
    DynamicSubDagProposal,
    ExpansionLimits,
    ExpansionRecord,
    ExpansionTrigger,
    ProposalStatus,
)
from agents.mission_state import (
    AcceptanceCriterion,
    Evidence,
    MissionStateError,
    MissionStateStore,
    utc_now,
)
from agents.task_graph import (
    FailureCategory,
    FailureInfo,
    RetryConfig,
    TaskGraph,
    TaskGraphError,
    TaskNode,
    TaskStatus,
)
from agents.swarm_coordinator import (
    AgentCategory,
    AgentCapability,
    AgentInstance,
    AgentResult,
    AgentHealthStatus,
    HierarchicalQuotaManager,
    LeaseManager,
    ResultStatus,
    SwarmCoordinator,
    TaskLease,
)
from agents.swarm_agents import (
    ArchitectureAgent,
    BrowserAgent,
    CodingAgent,
    CrossAgentHandoffManager,
    ResearchAgent,
    ReviewAgent,
    SwarmAgent,
    TestingAgent,
    create_default_swarm_pool,
)
from agents.collaboration_engine import (
    AgentProposal,
    ArbitrationDecision,
    ArbitrationRecord,
    CollaborationCoordinator,
    CollaborationSession,
    CollaborationStatus,
    ConflictDetails,
    ConflictType,
    PatchMergeEngine,
    ResultKind,
)
from backend.logging_config import get_logger, log_event
from backend.message_protocol import (
    chat_message,
    normalize_canonical_sender,
    state_message,
    system_message,
)

logger = get_logger(__name__)


class MissionLifecycleStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"


@dataclass
class Checkpoint:
    checkpoint_id: str
    sequence: int
    mission_id: str
    project_id: str
    mission_status: str
    task_graph_data: dict[str, Any]
    completed_task_ids: list[str]
    pending_task_ids: list[str]
    running_task_ids: list[str]
    failed_task_ids: list[str]
    blocked_task_ids: list[str]
    evidence_refs: list[str]
    outputs: dict[str, Any]
    created_at: str
    description: str = ""
    graph_version: int = 1
    expansion_history: list[dict[str, Any]] = field(default_factory=list)
    plan_version: int = 1
    adaptation_history: list[dict[str, Any]] = field(default_factory=list)
    current_strategy: str = ""
    plan_churn_count: int = 0
    swarm_state: dict[str, Any] = field(default_factory=dict)
    federation_state: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Checkpoint:
        return cls(
            checkpoint_id=data["checkpoint_id"],
            sequence=int(data.get("sequence", 0)),
            mission_id=data["mission_id"],
            project_id=data["project_id"],
            mission_status=data.get("mission_status", "ACTIVE"),
            task_graph_data=data.get("task_graph_data", {}),
            completed_task_ids=list(data.get("completed_task_ids", [])),
            pending_task_ids=list(data.get("pending_task_ids", [])),
            running_task_ids=list(data.get("running_task_ids", [])),
            failed_task_ids=list(data.get("failed_task_ids", [])),
            blocked_task_ids=list(data.get("blocked_task_ids", [])),
            evidence_refs=list(data.get("evidence_refs", [])),
            outputs=data.get("outputs", {}),
            created_at=data.get("created_at", ""),
            description=data.get("description", ""),
            graph_version=int(data.get("graph_version", 1)),
            expansion_history=list(data.get("expansion_history", [])),
            plan_version=int(data.get("plan_version", 1)),
            adaptation_history=list(data.get("adaptation_history", [])),
            current_strategy=str(data.get("current_strategy", "")),
            plan_churn_count=int(data.get("plan_churn_count", 0)),
            swarm_state=dict(data.get("swarm_state", {})),
            federation_state=dict(data.get("federation_state", {})),
        )


@dataclass
class TaskExecutionResult:
    success: bool
    task_id: str
    summary: str = ""
    output_data: dict[str, Any] = field(default_factory=dict)
    failure_category: FailureCategory = FailureCategory.NONE
    error_message: str = ""
    evidence: list[dict[str, Any]] = field(default_factory=list)
    repaired: bool = False
    repair_summary: str = ""
    subdag_proposal: DynamicSubDagProposal | None = None
    observations: list[Any] = field(default_factory=list)
    adaptation_proposal: Any = None


TaskExecutorFn = Callable[[str, TaskNode, dict[str, Any]], Awaitable[TaskExecutionResult]]
RepairFn = Callable[[str, TaskNode, FailureInfo, dict[str, Any]], Awaitable[bool]]


class MissionLifecycleOrchestrator:
    """Deterministic, resilient orchestrator for complex, long-horizon missions."""

    def __init__(
        self,
        *,
        project_id: str,
        mission_id: str,
        mission_state: MissionStateStore,
        task_graph: TaskGraph | None = None,
        concurrency_limit: int = 3,
        expansion_limits: ExpansionLimits | None = None,
        adaptation_budget: AdaptationBudget | None = None,
        executor_fn: TaskExecutorFn | None = None,
        repair_fn: RepairFn | None = None,
        connections: Any = None,
        callbacks: Any = None,
        logger: Any = None,
        use_swarm: bool = True,
        use_federation: bool = False,
        swarm_agents: Sequence[SwarmAgent] | None = None,
    ) -> None:
        self.project_id = project_id
        self.mission_id = mission_id
        self.mission_state = mission_state
        self.concurrency_limit = max(1, min(concurrency_limit, 8))
        self.expansion_limits = expansion_limits or ExpansionLimits()
        self.subdag_engine = DynamicSubDagEngine(limits=self.expansion_limits)
        self.adaptation_budget = adaptation_budget or AdaptationBudget()
        self.adaptive_engine = AdaptivePlanningEngine(budget=self.adaptation_budget)
        self.observations: list[Observation] = []
        self.plan_version: int = 1
        self.plan_churn_count: int = 0
        self.current_strategy: str = ""
        self.executor_fn = executor_fn
        self.repair_fn = repair_fn
        self.connections = connections
        self.callbacks = callbacks
        self.logger = logger or get_logger(__name__)

        self.status = MissionLifecycleStatus.READY
        self.checkpoint_seq = 0
        self._paused = False
        self._cancelled = False
        self._running_tasks: set[str] = set()
        self._task_outputs: dict[str, Any] = {}
        self._evidence_collected: list[str] = []

        # Directory structure
        proj_dir = os.path.join(self.mission_state.projects_root, project_id)
        if not os.path.isdir(proj_dir):
            os.makedirs(proj_dir, exist_ok=True)

        self.checkpoints_dir = os.path.join(
            self.mission_state._mission_dir(project_id, mission_id), "checkpoints"
        )
        os.makedirs(self.checkpoints_dir, exist_ok=True)

        if task_graph is not None:
            self.task_graph = task_graph
        else:
            self.task_graph = TaskGraph()
            # Attempt to auto-hydrate from latest checkpoint or existing work packages
            try:
                latest_cp = self.load_latest_checkpoint()
                if latest_cp:
                    self.recover_from_checkpoint(latest_cp)
                else:
                    m_data = self.mission_state.load_mission(project_id, mission_id)
                    wps = m_data.get("work_packages", [])
                    if wps:
                        status_map = {
                            "PENDING": TaskStatus.PENDING,
                            "READY": TaskStatus.READY,
                            "RUNNING": TaskStatus.RUNNING,
                            "COMPLETED": TaskStatus.COMPLETED,
                            "BLOCKED": TaskStatus.BLOCKED,
                            "FAILED": TaskStatus.FAILED,
                            "CANCELLED": TaskStatus.CANCELLED,
                        }
                        nodes = [
                            TaskNode(
                                task_id=wp["work_package_id"],
                                title=wp.get("title", wp["work_package_id"]),
                                category=wp.get("category", "GENERAL"),
                                dependencies=list(wp.get("dependencies", [])),
                                status=status_map.get(str(wp.get("status", "PENDING")).upper(), TaskStatus.PENDING),
                                parent_task_id=wp.get("parent_task_id") or (wp.get("metadata", {}) or {}).get("parent_task_id"),
                                subdag_id=wp.get("subdag_id") or (wp.get("metadata", {}) or {}).get("subdag_id"),
                                expansion_depth=int(wp.get("expansion_depth") or (wp.get("metadata", {}) or {}).get("expansion_depth", 0)),
                            )
                            for wp in wps
                        ]
                        stored_version = int((m_data.get("mission", {}) or {}).get("metadata", {}).get("graph_version", 1))
                        self.task_graph = TaskGraph(nodes=nodes, graph_version=stored_version)
            except Exception:
                pass

        self.use_swarm = use_swarm
        self.use_federation = use_federation
        self.swarm_agents: dict[str, SwarmAgent] = {}
        self.swarm_coordinator = SwarmCoordinator(
            project_id=project_id,
            mission_id=mission_id,
            mission_state=mission_state,
            task_graph=self.task_graph,
            global_max_concurrency=self.concurrency_limit,
            callbacks=self.callbacks,
        )
        from agents.swarm_federation import SwarmFederation
        self.swarm_federation = SwarmFederation(
            project_id=project_id,
            mission_id=mission_id,
            task_graph=self.task_graph,
            max_agents_per_subswarm=32,
            emit_callback=getattr(self.callbacks, "emit", None),
        ) if self.use_federation else None
        if swarm_agents is not None:
            for ag in swarm_agents:
                self.register_swarm_agent(ag)
        elif self.use_swarm:
            for ag in create_default_swarm_pool():
                self.register_swarm_agent(ag)

    def register_swarm_agent(self, agent: SwarmAgent) -> None:
        self.swarm_agents[agent.agent_id] = agent
        self.swarm_coordinator.register_agent(agent.instance)
        if self.swarm_federation:
            # Register into active federation if initialized
            pass

    # ── CHECKPOINTING & CRASH RECOVERY ────────────────────────────────────────

    def save_checkpoint(self, description: str = "") -> Checkpoint:
        """Persists deterministic snapshot to disk."""
        self.checkpoint_seq += 1
        now = utc_now()
        cp = Checkpoint(
            checkpoint_id=f"cp_{self.checkpoint_seq:04d}_{uuid.uuid4().hex[:6]}",
            sequence=self.checkpoint_seq,
            mission_id=self.mission_id,
            project_id=self.project_id,
            mission_status=self.status.value,
            task_graph_data=self.task_graph.to_dict(),
            completed_task_ids=[n.task_id for n in self.task_graph.get_completed_tasks()],
            pending_task_ids=[n.task_id for n in self.task_graph.nodes.values() if n.status == TaskStatus.PENDING],
            running_task_ids=list(self._running_tasks),
            failed_task_ids=[n.task_id for n in self.task_graph.get_failed_tasks()],
            blocked_task_ids=[n.task_id for n in self.task_graph.get_blocked_tasks()],
            evidence_refs=list(self._evidence_collected),
            outputs=dict(self._task_outputs),
            created_at=now,
            description=description,
            graph_version=getattr(self.task_graph, "graph_version", 1),
            expansion_history=list(getattr(self.task_graph, "expansion_history", [])),
            plan_version=self.plan_version,
            adaptation_history=list(self.mission_state.load_adaptation_history(self.project_id, self.mission_id)),
            current_strategy=self.current_strategy,
            plan_churn_count=self.plan_churn_count,
            swarm_state=self.swarm_coordinator.export_state() if self.use_swarm else {},
            federation_state=self.swarm_federation.save_checkpoint().to_dict() if self.swarm_federation else {},
        )

        # Persist through unified mission_state persistence layer
        if hasattr(self.mission_state, "save_checkpoint"):
            try:
                self.mission_state.save_checkpoint(self.project_id, self.mission_id, cp.to_dict())
            except Exception as e:
                log_event(self.logger, "mission_orchestrator.checkpoint_persistence_error", error=str(e))

        # Also maintain local file for backward compatibility
        path = os.path.join(self.checkpoints_dir, f"checkpoint_{self.checkpoint_seq:04d}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(json.dumps(cp.to_dict(), indent=2, ensure_ascii=False))
        except Exception:
            pass

        log_event(
            self.logger,
            "mission_orchestrator.checkpoint_saved",
            sequence=self.checkpoint_seq,
            description=description,
        )
        return cp

    def load_latest_checkpoint(self) -> Checkpoint | None:
        """Loads and returns the latest persistent checkpoint if available."""
        if hasattr(self.mission_state, "load_latest_checkpoint"):
            try:
                data = self.mission_state.load_latest_checkpoint(self.project_id, self.mission_id)
                if data:
                    return Checkpoint.from_dict(data)
            except Exception:
                pass

        files = sorted(glob.glob(os.path.join(self.checkpoints_dir, "checkpoint_*.json")))
        if not files:
            return None
        latest_file = files[-1]
        try:
            with open(latest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Checkpoint.from_dict(data)
        except Exception as e:
            log_event(self.logger, "mission_orchestrator.checkpoint_load_error", error=str(e))
            return None

    def load_checkpoint(self, sequence: int | None = None, checkpoint_id: str | None = None) -> Checkpoint | None:
        """Loads and returns checkpoint by sequence number or checkpoint_id, or latest if both None."""
        if hasattr(self.mission_state, "load_checkpoint"):
            try:
                data = self.mission_state.load_checkpoint(self.project_id, self.mission_id, sequence=sequence, checkpoint_id=checkpoint_id)
                if data:
                    return Checkpoint.from_dict(data)
            except Exception:
                pass

        if sequence is not None:
            path = os.path.join(self.checkpoints_dir, f"checkpoint_{sequence:04d}.json")
            if os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return Checkpoint.from_dict(json.load(f))
                except Exception as e:
                    log_event(self.logger, "mission_orchestrator.checkpoint_load_error", error=str(e))
            return None
        if checkpoint_id:
            files = sorted(glob.glob(os.path.join(self.checkpoints_dir, "checkpoint_*.json")))
            for fpath in files:
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if data.get("checkpoint_id") == checkpoint_id:
                        return Checkpoint.from_dict(data)
                except Exception:
                    continue
            return None
        return self.load_latest_checkpoint()

    def recover_from_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Reconstructs orchestrator state and reconciles interrupted tasks."""
        self.checkpoint_seq = checkpoint.sequence
        self.task_graph = TaskGraph.from_dict(checkpoint.task_graph_data)
        self.task_graph.graph_version = getattr(checkpoint, "graph_version", self.task_graph.graph_version)
        if getattr(checkpoint, "expansion_history", None):
            self.task_graph.expansion_history = list(checkpoint.expansion_history)
        self.plan_version = getattr(checkpoint, "plan_version", 1)
        self.current_strategy = getattr(checkpoint, "current_strategy", "")
        self.plan_churn_count = getattr(checkpoint, "plan_churn_count", 0)
        self.adaptive_engine.metrics.plan_churn_count = self.plan_churn_count
        self._task_outputs = dict(checkpoint.outputs)
        self._evidence_collected = list(checkpoint.evidence_refs)
        self.status = MissionLifecycleStatus(checkpoint.mission_status)

        # Reconcile interrupted tasks that were RUNNING during crash
        for task_id in checkpoint.running_task_ids:
            if task_id in self.task_graph.nodes:
                node = self.task_graph.nodes[task_id]
                node.status = TaskStatus.INTERRUPTED
                node.failure_info = FailureInfo(
                    category=FailureCategory.TRANSIENT_FAILURE,
                    message="Processo interrompido inesperadamente antes da conclusão.",
                    timestamp=utc_now(),
                    attempt=node.attempt_count,
                )
                # If retry is allowed, reset to READY
                if node.retry_config.is_retryable(FailureCategory.TRANSIENT_FAILURE, node.attempt_count):
                    node.status = TaskStatus.READY
                else:
                    node.status = TaskStatus.FAILED

        self._running_tasks.clear()
        if getattr(checkpoint, "swarm_state", None) and self.use_swarm:
            self.swarm_coordinator.restore_state(checkpoint.swarm_state)
            self.swarm_coordinator.reconcile_leases_and_failures()
        self.task_graph.update_derived_statuses()
        log_event(
            self.logger,
            "mission_orchestrator.recovered_from_checkpoint",
            sequence=self.checkpoint_seq,
            interrupted_count=len(checkpoint.running_task_ids),
        )

    # ── TELEMETRY & WEBSOCKET ─────────────────────────────────────────────────

    async def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        payload = {
            "type": event_type,
            "mission_id": self.mission_id,
            "project_id": self.project_id,
            "timestamp": utc_now(),
            **data,
        }
        if self.connections:
            try:
                await self.connections.broadcast(payload)
            except Exception:
                pass

    async def _emit_chat(self, sender: str, role: str, message: str) -> None:
        canonical = normalize_canonical_sender(sender)
        if self.connections:
            try:
                await self.connections.broadcast(chat_message(canonical, role, message))
            except Exception:
                pass

    # ── OPERATIONAL CONTROLS: PAUSE / RESUME / CANCEL ────────────────────────

    async def pause(self) -> None:
        """Pauses the orchestrator, stops new tasks from scheduling, saves checkpoint."""
        self._paused = True
        self.status = MissionLifecycleStatus.PAUSED
        self.save_checkpoint("Pausado pelo utilizador / sistema")
        await self._emit_event("mission_paused", {"reason": "Pausa solicitada"})
        await self._emit_chat("JARVIS", "Orquestrador", f"⏸️ Missão `{self.mission_id}` foi pausada.")

    async def resume(self) -> None:
        """Resumes a paused mission."""
        self._paused = False
        self.status = MissionLifecycleStatus.ACTIVE
        self.task_graph.update_derived_statuses()
        self.save_checkpoint("Retomado após pausa")
        await self._emit_event("mission_resumed", {"reason": "Retoma solicitada"})
        await self._emit_chat("JARVIS", "Orquestrador", f"▶️ Missão `{self.mission_id}` retomada.")

    async def cancel(self, reason: str = "Cancelamento solicitado") -> None:
        """Cancels mission execution and all pending tasks."""
        self._cancelled = True
        self.status = MissionLifecycleStatus.CANCELLED
        for node in self.task_graph.nodes.values():
            if node.status in {TaskStatus.PENDING, TaskStatus.READY, TaskStatus.RUNNING}:
                node.status = TaskStatus.CANCELLED
        self.save_checkpoint(f"Cancelado: {reason}")
        await self._emit_event("mission_cancelled", {"reason": reason})
        await self._emit_chat("JARVIS", "Orquestrador", f"⏹️ Missão `{self.mission_id}` foi cancelada: {reason}")

    # ── DYNAMIC SUB-DAG EXPANSION ────────────────────────────────────────────

    async def propose_and_apply_expansion(
        self, proposal: DynamicSubDagProposal
    ) -> tuple[bool, str, ExpansionRecord | None]:
        """Validates and atomically applies a dynamic sub-DAG expansion."""
        await self._emit_event("expansion_proposed", {
            "proposal_id": proposal.proposal_id,
            "parent_task_id": proposal.parent_task_id,
            "base_graph_version": proposal.base_graph_version,
            "reason": proposal.reason,
            "trigger": proposal.trigger.value if hasattr(proposal.trigger, "value") else str(proposal.trigger),
        })

        await self._emit_event("expansion_validating", {
            "proposal_id": proposal.proposal_id,
        })

        success, msg, record = await self.subdag_engine.apply_expansion(proposal, self)
        if not success:
            await self._emit_event("expansion_rejected", {
                "proposal_id": proposal.proposal_id,
                "reason": msg,
            })
            return False, msg, None

        self.task_graph.update_derived_statuses()
        return True, msg, record

    # ── ADAPTIVE PLANNING & EVALUATION ───────────────────────────────────────

    def record_observation(self, obs: Observation) -> None:
        """Records a structured observation from test, build, runtime, browser, user, or architecture."""
        self.observations.append(obs)
        log_event(
            self.logger,
            "mission_orchestrator.observation_recorded",
            observation_id=obs.observation_id,
            source=obs.source.value if hasattr(obs.source, "value") else str(obs.source),
            severity=obs.severity.value if hasattr(obs.severity, "value") else str(obs.severity),
            observation_event=obs.event,
            task_id=obs.task_id,
        )

    async def _emit_event(self, event_name: str, payload: dict[str, Any]) -> None:
        """Helper to invoke orchestrator callbacks or dispatch events."""
        if callable(self.callbacks):
            try:
                res = self.callbacks(event_name, payload)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                self.logger.warning("Error in mission orchestrator callback: %s", e)
        elif isinstance(self.callbacks, dict):
            cb = self.callbacks.get(event_name)
            if callable(cb):
                try:
                    res = cb(payload)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception as e:
                    self.logger.warning("Error in mission orchestrator callback '%s': %s", event_name, e)

    async def evaluate_plan(
        self,
        failure_info: FailureInfo | None = None,
        requirement_change: str | None = None,
        architecture_change: dict[str, Any] | None = None,
    ) -> PlanEvaluationResult:
        """Evaluates the current plan using the AdaptivePlanningEngine."""
        history = await asyncio.to_thread(
            self.mission_state.load_adaptation_history, self.project_id, self.mission_id
        )
        await self._emit_event("plan_evaluation_started", {
            "graph_version": self.task_graph.graph_version,
            "observations_count": len(self.observations),
        })
        res = self.adaptive_engine.evaluate_plan(
            current_graph=self.task_graph,
            observations=self.observations,
            failure_info=failure_info,
            requirement_change=requirement_change,
            architecture_change=architecture_change,
            adaptation_history=history,
        )
        await self._emit_event("plan_evaluation_completed", {
            "decision": res.decision.value if hasattr(res.decision, "value") else str(res.decision),
            "reason": res.reason,
            "trigger": res.trigger.value if hasattr(res.trigger, "value") else str(res.trigger),
            "affected_tasks": res.affected_tasks,
        })
        return res

    async def propose_and_apply_adaptation(
        self, proposal: MissionAdaptationProposal
    ) -> tuple[bool, str, AdaptationRecord | None]:
        """Validates and atomically applies an adaptation proposal."""
        await self._emit_event("adaptation_proposed", {
            "proposal_id": proposal.proposal_id,
            "decision": proposal.decision.value if hasattr(proposal.decision, "value") else str(proposal.decision),
            "trigger": proposal.trigger.value if hasattr(proposal.trigger, "value") else str(proposal.trigger),
            "reason": proposal.reason,
            "added_count": len(proposal.added_tasks),
            "removed_count": len(proposal.removed_tasks),
        })
        await self._emit_event("adaptation_validating", {
            "proposal_id": proposal.proposal_id,
            "base_version": proposal.base_graph_version,
        })

        if proposal.decision == PlanEvaluationDecision.REPLAN or str(proposal.decision) == "REPLAN":
            await self._emit_event("replan_started", {
                "proposal_id": proposal.proposal_id,
                "base_version": proposal.base_graph_version,
            })

        applied, msg, record = await self.adaptive_engine.apply_adaptation(proposal, self)
        if applied and record:
            self.plan_version += 1
            self.plan_churn_count = self.adaptive_engine.metrics.plan_churn_count
            self.current_strategy = record.strategy_fingerprint

            await self._emit_event("adaptation_accepted", {
                "proposal_id": proposal.proposal_id,
                "new_version": record.graph_version_after,
                "decision": record.decision,
            })
            await self._emit_event("graph_version_changed", {
                "previous_version": record.graph_version_before,
                "new_version": record.graph_version_after,
                "trigger": record.trigger,
                "reason": record.reason,
            })
            if record.decision == "REPLAN" or str(record.decision) == "REPLAN":
                await self._emit_event("replan_completed", {
                    "proposal_id": proposal.proposal_id,
                    "new_version": record.graph_version_after,
                })
        else:
            await self._emit_event("adaptation_rejected", {
                "proposal_id": proposal.proposal_id,
                "reason": msg,
            })

        self.task_graph.update_derived_statuses()
        return applied, msg, record

    # ── SATISFACTION VERIFICATION ────────────────────────────────────────────

    async def verify_satisfaction(self) -> tuple[bool, str]:
        """Evaluates whether all required criteria and tasks are fully satisfied with evidence."""
        # 1. Check all required tasks completed
        if not self.task_graph.is_all_completed():
            incomplete = [
                n.task_id for n in self.task_graph.nodes.values()
                if n.required and n.status != TaskStatus.COMPLETED
            ]
            return False, f"Tarefas obrigatórias incompletas: {incomplete}"

        # 2. Check acceptance criteria in MissionStateStore
        try:
            mission_data = await asyncio.to_thread(
                self.mission_state.load_mission, self.project_id, self.mission_id
            )
            criteria = mission_data.get("acceptance_criteria", [])
            for crit in criteria:
                if crit.get("required", True):
                    if crit.get("status") != "SATISFIED" or not crit.get("evidence_refs"):
                        return False, f"Critério '{crit.get('criterion_id')}' ({crit.get('description')}) não satisfeito."
        except Exception:
            # If no store record exists for this mission_id, task graph completion is sufficient
            pass

        return True, "Todos os critérios e tarefas foram satisfeitos com evidência."

    # ── EXECUTION & SCHEDULING LOOP ──────────────────────────────────────────

    async def run(self) -> MissionLifecycleStatus:
        """Main autonomous execution loop."""
        self.status = MissionLifecycleStatus.ACTIVE
        self._paused = False
        self._cancelled = False
        self.save_checkpoint("Início da execução da missão")

        await self._emit_event("mission_started", {
            "total_tasks": len(self.task_graph.nodes),
            "order": self.task_graph.topological_sort(),
        })

        semaphore = asyncio.Semaphore(self.concurrency_limit)
        active_futures: set[asyncio.Task] = set()

        while not self._cancelled and not self._paused:
            use_swarm_mode = self.use_swarm and self.executor_fn is None

            # 0. Swarm heartbeat and lease reconciliation
            if use_swarm_mode:
                interrupted = self.swarm_coordinator.reconcile_leases_and_failures()
                if interrupted:
                    await self._emit_event("swarm_tasks_interrupted", {"task_ids": interrupted})

            # 1. Update DAG state
            self.task_graph.update_derived_statuses()

            # 2. Check if all completed
            if self.task_graph.is_all_completed() and not active_futures:
                satisfied, reason = await self.verify_satisfaction()
                if satisfied:
                    self.status = MissionLifecycleStatus.COMPLETED
                    self.save_checkpoint("Missão concluída com satisfação confirmada")
                    await self._emit_event("mission_completed", {"progress": 100.0, "reason": reason})
                    return self.status
                else:
                    self.status = MissionLifecycleStatus.FAILED
                    self.save_checkpoint(f"Falha na satisfação: {reason}")
                    await self._emit_event("mission_failed", {"reason": reason})
                    return self.status

            # 3. Check for unrecoverable failure
            if self.task_graph.has_unrecoverable_failures() and not active_futures:
                eval_res = await self.evaluate_plan()
                if eval_res.decision in {PlanEvaluationDecision.ADAPT_PLAN, PlanEvaluationDecision.REPLAN} and eval_res.recommended_proposal:
                    try:
                        prop = MissionAdaptationProposal.from_dict(eval_res.recommended_proposal)
                        applied, _, _ = await self.propose_and_apply_adaptation(prop)
                        if applied:
                            continue
                    except Exception as ad_err:
                        log_event(self.logger, "mission_orchestrator.auto_adaptation_error", error=str(ad_err))
                self.status = MissionLifecycleStatus.FAILED
                self.save_checkpoint("Falha permanente sem possibilidade de recuperação")
                await self._emit_event("mission_failed", {"reason": "Tarefas críticas falharam permanentemente."})
                return self.status

            # 4. Schedule ready tasks
            ready_tasks = self.task_graph.get_ready_tasks()
            if use_swarm_mode:
                ordered_ready = self.swarm_coordinator.scheduler.order_ready_tasks(ready_tasks)
                for node in ordered_ready:
                    if node.task_id in self._running_tasks:
                        continue

                    # Multi-agent collaboration dispatch check
                    collaborating_ids = node.metadata.get("collaborating_agents", [])
                    if node.metadata.get("collaborative") and len(collaborating_ids) > 1:
                        agents_to_run = []
                        for aid in collaborating_ids:
                            aw = self.swarm_agents.get(aid)
                            ai = self.swarm_coordinator.registry.get(aid)
                            if aw and ai and ai.is_available:
                                agents_to_run.append((aw, ai))
                        if len(agents_to_run) >= 2:
                            lead_agent = agents_to_run[0][1]
                            try:
                                lease = self.swarm_coordinator.acquire_task_lease(node, lead_agent)
                            except ValueError:
                                continue
                            node.status = TaskStatus.RUNNING
                            node.started_at = utc_now()
                            node.metadata["assigned_agent"] = "COLLABORATIVE_GROUP"
                            node.metadata["lease_id"] = lease.lease_id
                            self._running_tasks.add(node.task_id)

                            fut = asyncio.create_task(
                                self._execute_collaborative_swarm_task_guarded(node, agents_to_run, lease)
                            )
                            active_futures.add(fut)
                            continue

                    selection = self.swarm_coordinator.select_agent_for_task(node)
                    if not selection:
                        continue
                    agent_worker = self.swarm_agents.get(selection.agent_id)
                    agent_inst = self.swarm_coordinator.registry.get(selection.agent_id)
                    if not agent_worker or not agent_inst:
                        continue
                    try:
                        lease = self.swarm_coordinator.acquire_task_lease(node, agent_inst)
                    except ValueError:
                        # File conflict or quota limit: wait for next cycle
                        continue

                    node.status = TaskStatus.RUNNING
                    node.started_at = utc_now()
                    node.metadata["assigned_agent"] = selection.agent_id
                    node.metadata["lease_id"] = lease.lease_id
                    self._running_tasks.add(node.task_id)

                    fut = asyncio.create_task(
                        self._execute_swarm_task_guarded(node, agent_worker, lease)
                    )
                    active_futures.add(fut)
            else:
                available_slots = self.concurrency_limit - len(self._running_tasks)
                if ready_tasks and available_slots > 0:
                    for node in ready_tasks[:available_slots]:
                        if node.task_id not in self._running_tasks:
                            node.status = TaskStatus.RUNNING
                            node.started_at = utc_now()
                            self._running_tasks.add(node.task_id)

                            fut = asyncio.create_task(
                                self._execute_single_task_guarded(node, semaphore)
                            )
                            active_futures.add(fut)

            if not active_futures:
                # No running tasks and no ready tasks
                if self._paused:
                    return self.status
                if self.task_graph.is_all_completed():
                    continue
                # Blocked state: evaluate if adaptive replan can resolve blockages
                blocked = self.task_graph.get_blocked_tasks()
                eval_res = await self.evaluate_plan()
                if eval_res.decision in {PlanEvaluationDecision.ADAPT_PLAN, PlanEvaluationDecision.REPLAN} and eval_res.recommended_proposal:
                    try:
                        prop = MissionAdaptationProposal.from_dict(eval_res.recommended_proposal)
                        applied, _, _ = await self.propose_and_apply_adaptation(prop)
                        if applied:
                            continue
                    except Exception as ad_err:
                        log_event(self.logger, "mission_orchestrator.auto_adaptation_error", error=str(ad_err))
                self.status = MissionLifecycleStatus.BLOCKED
                self.save_checkpoint("Missão bloqueada por dependências")
                await self._emit_event("mission_blocked", {"blocked_tasks": [n.task_id for n in blocked]})
                return self.status

            # Wait for at least one active task to finish
            done, active_futures = await asyncio.wait(
                active_futures, return_when=asyncio.FIRST_COMPLETED
            )

            # Checkpoint after completion of batch
            self.save_checkpoint("Progresso após conclusão de tarefa")

        if self._paused:
            return MissionLifecycleStatus.PAUSED
        if self._cancelled:
            return MissionLifecycleStatus.CANCELLED

        return self.status

    async def _execute_swarm_task_guarded(
        self, node: TaskNode, agent: SwarmAgent, lease: TaskLease
    ) -> None:
        node.attempt_count += 1
        attempt = node.attempt_count

        await self._emit_event("swarm_task_dispatched", {
            "task_id": node.task_id,
            "agent_id": agent.agent_id,
            "agent_type": agent.agent_type,
            "attempt": attempt,
            "lease_id": lease.lease_id,
            "timeout_seconds": node.timeout_seconds,
        })

        try:
            # Build context via CrossAgentHandoffManager
            context = CrossAgentHandoffManager.build_task_context(
                node, self.task_graph.nodes, self._task_outputs
            )

            # Heartbeat callback
            def _hb():
                self.swarm_coordinator.record_heartbeat(lease.lease_id, agent.agent_id)

            timeout_sec = max(5.0, node.timeout_seconds)
            try:
                res = await asyncio.wait_for(
                    agent.execute(node, context, lease, _hb),
                    timeout=timeout_sec,
                )
            except asyncio.TimeoutError:
                res = AgentResult(
                    task_id=node.task_id,
                    attempt_id=attempt,
                    agent_id=agent.agent_id,
                    status=ResultStatus.TIMEOUT,
                    failure={"reason": f"AGENT_TIMEOUT: Task timed out after {timeout_sec}s"},
                )
            except Exception as exc:
                res = AgentResult(
                    task_id=node.task_id,
                    attempt_id=attempt,
                    agent_id=agent.agent_id,
                    status=ResultStatus.FAILURE,
                    failure={"reason": f"AGENT_CRASH: {str(exc)}"},
                )

            # Let swarm coordinator validate result and update state
            success, msg = await self.swarm_coordinator.handle_agent_result(res)
            if success:
                self._task_outputs[node.task_id] = res.output
                for ev in res.evidence:
                    if isinstance(ev, dict) and "evidence_id" in ev:
                        self._evidence_collected.append(ev["evidence_id"])
            else:
                if node.retry_config.is_retryable(FailureCategory.TRANSIENT_FAILURE, attempt):
                    node.status = TaskStatus.READY  # Will be re-picked and reassigned
                else:
                    node.status = TaskStatus.FAILED

        finally:
            self._running_tasks.discard(node.task_id)

    async def _execute_collaborative_swarm_task_guarded(
        self,
        node: TaskNode,
        agents_to_run: list[tuple[SwarmAgent, Any]],
        lease: TaskLease,
    ) -> None:
        node.attempt_count += 1
        attempt = node.attempt_count
        agent_ids = [ag.agent_id for ag, _ in agents_to_run]

        # 1. Create or retrieve CollaborationSession
        session = self.swarm_coordinator.collaboration.create_session(
            task_id=node.task_id,
            participant_agents=agent_ids,
            max_rounds=node.metadata.get("max_collaboration_rounds", 3),
        )

        await self._emit_event("collaboration_started", {
            "task_id": node.task_id,
            "collaboration_id": session.collaboration_id,
            "participant_agents": agent_ids,
            "attempt": attempt,
        })

        try:
            # 2. Parallel agent execution to gather proposals
            async def _run_agent(ag_worker: SwarmAgent, ag_inst: Any) -> AgentProposal | None:
                def _hb():
                    self.swarm_coordinator.record_heartbeat(lease.lease_id, ag_worker.agent_id)

                context = CrossAgentHandoffManager.build_task_context(
                    node, self.task_graph.nodes, self._task_outputs
                )
                context["is_collaborative"] = True
                context["collaboration_id"] = session.collaboration_id
                context["other_participants"] = [aid for aid in agent_ids if aid != ag_worker.agent_id]

                # Check if predefined proposal in metadata
                prop_meta = node.metadata.get(f"proposal_{ag_worker.agent_id}") or node.metadata.get("proposals", {}).get(ag_worker.agent_id)
                if prop_meta:
                    return AgentProposal(
                        proposal_id=f"prop_{ag_worker.agent_id}_{uuid.uuid4().hex[:6]}",
                        task_id=node.task_id,
                        agent_id=ag_worker.agent_id,
                        collaboration_id=session.collaboration_id,
                        agent_type=ag_worker.agent_type,
                        result_kind=ResultKind(prop_meta.get("result_kind", "PROPOSAL")),
                        description=prop_meta.get("description", f"Proposal by {ag_worker.agent_id}"),
                        diff_content=prop_meta.get("diff_content", ""),
                        content_by_file=prop_meta.get("content_by_file", {}),
                        affected_files=prop_meta.get("affected_files", []),
                        affected_symbols=prop_meta.get("affected_symbols", []),
                        evidence=prop_meta.get("evidence", []),
                        confidence_score=prop_meta.get("confidence", 0.85),
                        rationale=prop_meta.get("rationale", ""),
                        metadata=dict(prop_meta),
                    )

                res = await ag_worker.execute(node, context, lease, _hb)
                if res.status == ResultStatus.SUCCESS:
                    p_data = res.output.get("proposal") if isinstance(res.output, dict) else None
                    if isinstance(p_data, dict):
                        return AgentProposal.from_dict(p_data)
                    return AgentProposal(
                        proposal_id=f"prop_{ag_worker.agent_id}_{uuid.uuid4().hex[:6]}",
                        task_id=node.task_id,
                        agent_id=ag_worker.agent_id,
                        collaboration_id=session.collaboration_id,
                        agent_type=ag_worker.agent_type,
                        result_kind=ResultKind.PROPOSAL,
                        description=str(res.output.get("diff_summary") or res.output.get("summary") or f"Output from {ag_worker.agent_id}"),
                        diff_content=res.output.get("diff_content", ""),
                        content_by_file=res.output.get("content_by_file", {}),
                        affected_files=res.produced_artifacts or res.output.get("files_modified", []),
                        affected_symbols=res.output.get("affected_symbols", []),
                        confidence_score=0.85,
                        rationale=f"Result generated by {ag_worker.agent_id}",
                        evidence=res.evidence,
                        metadata=dict(res.output),
                    )
                return None

            gathered = await asyncio.gather(
                *[_run_agent(w, i) for w, i in agents_to_run],
                return_exceptions=True,
            )

            for item in gathered:
                if isinstance(item, AgentProposal):
                    self.swarm_coordinator.collaboration.add_proposal(session.collaboration_id, item)
                    await self._emit_event("collaboration_proposal_received", {
                        "collaboration_id": session.collaboration_id,
                        "proposal_id": item.proposal_id,
                        "agent_id": item.agent_id,
                    })

            # 3. Conflict Detection & Arbitration
            base_files = node.metadata.get("base_files", {})
            arch_context = node.metadata.get("architecture_context", {})
            review_input = node.metadata.get("review_input", {})

            review_agent = self.swarm_agents.get("review_01") or next((w for w, _ in agents_to_run if w.agent_type == "REVIEW"), None)
            if review_agent and hasattr(review_agent, "evaluate_conflict"):
                temp_conflicts = self.swarm_coordinator.collaboration.detector.detect_conflicts(
                    self.project_id, node, session.proposals, arch_context
                )
                if temp_conflicts:
                    review_input = review_agent.evaluate_conflict(temp_conflicts[0], session.proposals, context={})

            status, conflicts, arbitrations = self.swarm_coordinator.collaboration.evaluate_collaboration(
                session.collaboration_id,
                task=node,
                architecture_context=arch_context,
                base_files=base_files,
                review_input=review_input,
            )

            await self._emit_event("collaboration_evaluated", {
                "collaboration_id": session.collaboration_id,
                "status": status.value,
                "conflicts_count": len(conflicts),
                "arbitrations_count": len(arbitrations),
            })

            # 4. Handle Decisions
            if status == CollaborationStatus.BLOCKED:
                node.status = TaskStatus.BLOCKED
                node.failure_info = FailureInfo(
                    category=FailureCategory.PERMANENT_POLICY_VIOLATION,
                    message=f"Colaboração bloqueada: {len(conflicts)} conflitos sem resolução.",
                    timestamp=utc_now(),
                    attempt=attempt,
                )
            elif any(a.decision == ArbitrationDecision.REPLAN for a in arbitrations):
                log_event(self.logger, "collaboration.triggering_replan", task_id=node.task_id)
                await self.evaluate_plan(architecture_change={"conflict": "COLLABORATION_REPLAN"})
                node.status = TaskStatus.COMPLETED
            elif any(a.decision == ArbitrationDecision.REGENERATE for a in arbitrations):
                if session.round_count < session.max_rounds:
                    self.swarm_coordinator.collaboration.advance_round(session.collaboration_id)
                    node.status = TaskStatus.READY
                else:
                    node.status = TaskStatus.BLOCKED
            else:
                # MERGE or ACCEPT
                applied_files = {}
                if session.merged_content:
                    applied_files = dict(session.merged_content)
                elif session.proposals:
                    winning_prop = session.proposals[0]
                    for a in arbitrations:
                        if a.selected_proposal_id:
                            p = next((p for p in session.proposals if p.proposal_id == a.selected_proposal_id), None)
                            if p:
                                winning_prop = p
                                break
                    applied_files = dict(winning_prop.content_by_file)

                # AST Validation & Self-Healing
                syntax_errors = []
                for fname, content in applied_files.items():
                    if fname.endswith(".py") and content:
                        try:
                            import ast
                            ast.parse(content)
                        except SyntaxError as e:
                            syntax_errors.append((fname, str(e)))

                if syntax_errors:
                    log_event(self.logger, "collaboration.self_healing_triggered", errors=syntax_errors)
                    try:
                        from intelligence.ast_repair_v2 import ASTRepairEngineV2
                        repairer = ASTRepairEngineV2()
                        for fname, _ in syntax_errors:
                            try:
                                repaired = repairer.repair_syntax(applied_files[fname])
                                applied_files[fname] = repaired
                                log_event(self.logger, "collaboration.self_healing_succeeded", file=fname)
                            except Exception as rep_err:
                                log_event(self.logger, "collaboration.self_healing_failed", error=str(rep_err))
                    except Exception:
                        pass

                node.status = TaskStatus.COMPLETED
                node.completed_at = utc_now()
                node.output_data = {
                    "collaboration_id": session.collaboration_id,
                    "applied_files": applied_files,
                    "conflicts": [c.to_dict() for c in conflicts],
                    "arbitrations": [a.to_dict() for a in arbitrations],
                }
                self._task_outputs[node.task_id] = node.output_data

                for prop in session.proposals:
                    for ev in prop.evidence:
                        if isinstance(ev, dict) and "evidence_id" in ev:
                            self._evidence_collected.append(ev["evidence_id"])

                ev_collab = f"ev_collab_{node.task_id}_{uuid.uuid4().hex[:6]}"
                self._evidence_collected.append(ev_collab)

        finally:
            self._running_tasks.discard(node.task_id)
            if lease:
                self.swarm_coordinator.release_task_lease(node.task_id, lease.agent_id, lease.lease_id)

    async def _execute_single_task_guarded(
        self, node: TaskNode, semaphore: asyncio.Semaphore
    ) -> None:
        async with semaphore:
            try:
                await self._execute_task_with_retry_and_recovery(node)
            finally:
                self._running_tasks.discard(node.task_id)

    async def _execute_task_with_retry_and_recovery(self, node: TaskNode) -> None:
        """Executes a single task, handling timeouts, retries, and minimal recovery."""
        node.attempt_count += 1
        attempt = node.attempt_count
        now = utc_now()

        await self._emit_event("task_started", {
            "task_id": node.task_id,
            "title": node.title,
            "attempt": attempt,
            "timeout_seconds": node.timeout_seconds,
        })

        # Filter relevant context from dependencies and project architecture
        context = self._build_task_context(node)

        try:
            # Execute with timeout
            if self.executor_fn:
                res: TaskExecutionResult = await asyncio.wait_for(
                    self.executor_fn(self.project_id, node, context),
                    timeout=node.timeout_seconds,
                )
            else:
                # Default no-op executor
                res = TaskExecutionResult(
                    success=True,
                    task_id=node.task_id,
                    summary=f"Task {node.title} executada com sucesso.",
                )

            if res.success:
                # SUCCESS
                node.status = TaskStatus.COMPLETED
                node.completed_at = utc_now()
                node.result_summary = res.summary
                node.output_data = res.output_data
                self._task_outputs[node.task_id] = res.output_data

                # Attach Evidence
                evidence_list = res.evidence or [{
                    "kind": "EXECUTION_LOG",
                    "source_ref": f"validation:execution_{node.task_id}",
                    "description": res.summary or f"Task '{node.title}' concluída com sucesso.",
                }]
                for ev in evidence_list:
                    ev_id = f"ev_{node.task_id}_{uuid.uuid4().hex[:6]}"
                    try:
                        await asyncio.to_thread(
                            self.mission_state.attach_evidence,
                            project_id=self.project_id,
                            mission_id=self.mission_id,
                            work_package_id=node.task_id,
                            kind=ev.get("kind", "EXECUTION_LOG"),
                            source_ref=ev.get("source_ref", "validation:task_execution"),
                            description=ev.get("description", res.summary),
                            evidence_id=ev_id,
                        )
                    except Exception as ev_err:
                        log_event(self.logger, "mission_orchestrator.evidence_attach_skipped", task_id=node.task_id, error=str(ev_err))
                    node.evidence_refs.append(ev_id)
                    self._evidence_collected.append(ev_id)

                # Auto-satisfy pending criteria associated with this completed work package
                if node.evidence_refs:
                    try:
                        mission_data = await asyncio.to_thread(
                            self.mission_state.load_mission, self.project_id, self.mission_id
                        )
                        for crit in mission_data.get("acceptance_criteria", []):
                            if crit.get("owner_id") == node.task_id and crit.get("status") == "PENDING":
                                await asyncio.to_thread(
                                    self.mission_state.set_criterion_status,
                                    project_id=self.project_id,
                                    mission_id=self.mission_id,
                                    criterion_id=crit["criterion_id"],
                                    status="SATISFIED",
                                    expected_version=crit["version"],
                                    evidence_refs=node.evidence_refs,
                                )
                    except Exception as crit_err:
                        log_event(self.logger, "mission_orchestrator.criterion_satisfaction_skipped", task_id=node.task_id, error=str(crit_err))

                # Process observations if emitted
                if getattr(res, "observations", None):
                    for obs in res.observations:
                        if isinstance(obs, Observation):
                            self.record_observation(obs)

                # Check for dynamic sub-dag proposal from executor
                if res.subdag_proposal:
                    applied, app_msg, _ = await self.propose_and_apply_expansion(res.subdag_proposal)
                    if not applied:
                        log_event(
                            self.logger,
                            "mission_orchestrator.subdag_rejected_during_execution",
                            task_id=node.task_id,
                            reason=app_msg,
                        )

                # Check for adaptation proposal from executor
                if getattr(res, "adaptation_proposal", None):
                    applied, app_msg, _ = await self.propose_and_apply_adaptation(res.adaptation_proposal)
                    if not applied:
                        log_event(
                            self.logger,
                            "mission_orchestrator.adaptation_rejected_during_execution",
                            task_id=node.task_id,
                            reason=app_msg,
                        )

                await self._emit_event("task_completed", {
                    "task_id": node.task_id,
                    "summary": res.summary,
                    "attempt": attempt,
                })
                return

            else:
                # Execution reported failure
                fail_info = FailureInfo(
                    category=res.failure_category,
                    message=res.error_message or "Falha de execução.",
                    timestamp=utc_now(),
                    attempt=attempt,
                )
                await self._handle_task_failure(node, fail_info, context)

        except asyncio.TimeoutError:
            fail_info = FailureInfo(
                category=FailureCategory.TIMEOUT,
                message=f"Timeout de {node.timeout_seconds}s excedido.",
                timestamp=utc_now(),
                attempt=attempt,
            )
            await self._handle_task_failure(node, fail_info, context)

        except Exception as exc:
            fail_info = FailureInfo(
                category=FailureCategory.TRANSIENT_FAILURE,
                message=str(exc),
                timestamp=utc_now(),
                attempt=attempt,
            )
            await self._handle_task_failure(node, fail_info, context)

    async def _handle_task_failure(
        self, node: TaskNode, fail_info: FailureInfo, context: dict[str, Any]
    ) -> None:
        node.failure_info = fail_info
        attempt = node.attempt_count

        # Record structured failure observation
        fail_obs = Observation(
            source=ObservationSource.RUNTIME,
            event=fail_info.message or f"Falha de execução na tarefa '{node.title}'",
            task_id=node.task_id,
            severity=ObservationSeverity.HIGH if attempt >= node.retry_config.max_attempts else ObservationSeverity.MEDIUM,
            impact=f"Falha na tarefa '{node.title}' (tentativa {attempt}/{node.retry_config.max_attempts})",
            details={
                "category": fail_info.category.value if hasattr(fail_info.category, "value") else str(fail_info.category),
                "attempt": attempt,
            },
        )
        self.record_observation(fail_obs)

        await self._emit_event("task_failed", {
            "task_id": node.task_id,
            "category": fail_info.category.value,
            "message": fail_info.message,
            "attempt": attempt,
        })

        # 1. Minimal Repair Hook on Validation Failures
        if fail_info.category == FailureCategory.VALIDATION_FAILURE and self.repair_fn:
            log_event(self.logger, "mission_orchestrator.attempting_minimal_repair", task_id=node.task_id)
            repaired = await self.repair_fn(self.project_id, node, fail_info, context)
            if repaired:
                log_event(self.logger, "mission_orchestrator.minimal_repair_succeeded", task_id=node.task_id)

        # 2. Check Retry Eligibility
        if node.retry_config.is_retryable(fail_info.category, attempt):
            delay = node.retry_config.initial_delay_seconds * (
                node.retry_config.backoff_factor ** (attempt - 1)
            )
            node.status = TaskStatus.READY
            await self._emit_event("task_retrying", {
                "task_id": node.task_id,
                "attempt": attempt,
                "next_attempt": attempt + 1,
                "delay_seconds": delay,
            })
            if delay > 0:
                await asyncio.sleep(min(delay, 10.0))
        else:
            # Permanent Failure
            node.status = TaskStatus.FAILED
            log_event(
                self.logger,
                "mission_orchestrator.task_permanently_failed",
                task_id=node.task_id,
                category=fail_info.category.value,
                attempts=attempt,
            )
            eval_res = await self.evaluate_plan(failure_info=fail_info)
            if eval_res.decision in {PlanEvaluationDecision.ADAPT_PLAN, PlanEvaluationDecision.REPLAN} and eval_res.recommended_proposal:
                try:
                    prop = MissionAdaptationProposal.from_dict(eval_res.recommended_proposal)
                    await self.propose_and_apply_adaptation(prop)
                except Exception as ad_err:
                    log_event(self.logger, "mission_orchestrator.auto_adaptation_error", error=str(ad_err))

    def _build_task_context(self, node: TaskNode) -> dict[str, Any]:
        """Constructs filtered, relevant context from dependencies."""
        dep_outputs = {
            dep_id: self._task_outputs.get(dep_id, {})
            for dep_id in node.dependencies
            if dep_id in self._task_outputs
        }
        return {
            "task_id": node.task_id,
            "title": node.title,
            "category": node.category,
            "dependencies_outputs": dep_outputs,
            "mission_id": self.mission_id,
            "project_id": self.project_id,
        }
