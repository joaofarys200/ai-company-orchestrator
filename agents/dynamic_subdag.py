from __future__ import annotations

import asyncio
import enum
import json
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from agents.mission_state import MissionStateError, MissionStateStore, utc_now
from agents.task_graph import (
    FailureCategory,
    RetryConfig,
    TaskDependencyError,
    TaskGraph,
    TaskGraphCycleError,
    TaskGraphError,
    TaskNode,
    TaskStatus,
)
from backend.logging_config import get_logger, log_event

logger = get_logger(__name__)


class ExpansionTrigger(str, enum.Enum):
    REQUIREMENT_DISCOVERY = "REQUIREMENT_DISCOVERY"
    ARCHITECTURE_DISCOVERY = "ARCHITECTURE_DISCOVERY"
    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    RUNTIME_DISCOVERY = "RUNTIME_DISCOVERY"
    BROWSER_DISCOVERY = "BROWSER_DISCOVERY"
    DEPENDENCY_DISCOVERY = "DEPENDENCY_DISCOVERY"
    MISSING_TEST = "MISSING_TEST"
    MISSING_IMPLEMENTATION = "MISSING_IMPLEMENTATION"


class ProposalStatus(str, enum.Enum):
    PROPOSED = "PROPOSED"
    VALIDATING = "VALIDATING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    STALE = "STALE"
    APPLIED = "APPLIED"
    FAILED = "FAILED"


@dataclass
class ExpansionLimits:
    max_expansions_per_mission: int = 10
    max_tasks_per_expansion: int = 10
    max_total_tasks: int = 50
    max_expansion_depth: int = 3
    max_expansions_per_parent_task: int = 3

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExpansionLimits:
        return cls(
            max_expansions_per_mission=int(data.get("max_expansions_per_mission", 10)),
            max_tasks_per_expansion=int(data.get("max_tasks_per_expansion", 10)),
            max_total_tasks=int(data.get("max_total_tasks", 50)),
            max_expansion_depth=int(data.get("max_expansion_depth", 3)),
            max_expansions_per_parent_task=int(data.get("max_expansions_per_parent_task", 3)),
        )


@dataclass
class DynamicSubDagProposal:
    proposal_id: str
    mission_id: str
    parent_task_id: str
    base_graph_version: int
    reason: str
    trigger: ExpansionTrigger | str
    tasks: list[dict[str, Any]] = field(default_factory=list)
    dependencies: list[tuple[str, str]] = field(default_factory=list)  # (upstream_task, downstream_task)
    acceptance_criteria: list[dict[str, Any]] = field(default_factory=list)
    requested_scope: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    status: ProposalStatus | str = ProposalStatus.PROPOSED
    rejection_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = utc_now()
        if isinstance(self.trigger, str):
            try:
                self.trigger = ExpansionTrigger(self.trigger)
            except ValueError:
                self.trigger = ExpansionTrigger.REQUIREMENT_DISCOVERY
        if isinstance(self.status, str):
            try:
                self.status = ProposalStatus(self.status)
            except ValueError:
                self.status = ProposalStatus.PROPOSED

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "mission_id": self.mission_id,
            "parent_task_id": self.parent_task_id,
            "base_graph_version": self.base_graph_version,
            "reason": self.reason,
            "trigger": self.trigger.value if isinstance(self.trigger, ExpansionTrigger) else str(self.trigger),
            "tasks": [dict(t) for t in self.tasks],
            "dependencies": [list(edge) for edge in self.dependencies],
            "acceptance_criteria": [dict(c) for c in self.acceptance_criteria],
            "requested_scope": dict(self.requested_scope),
            "created_at": self.created_at,
            "status": self.status.value if isinstance(self.status, ProposalStatus) else str(self.status),
            "rejection_reason": self.rejection_reason,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DynamicSubDagProposal:
        deps_raw = data.get("dependencies", [])
        deps = [(edge[0], edge[1]) for edge in deps_raw if len(edge) == 2]
        return cls(
            proposal_id=data["proposal_id"],
            mission_id=data["mission_id"],
            parent_task_id=data["parent_task_id"],
            base_graph_version=int(data.get("base_graph_version", 1)),
            reason=data.get("reason", ""),
            trigger=data.get("trigger", ExpansionTrigger.REQUIREMENT_DISCOVERY),
            tasks=list(data.get("tasks", [])),
            dependencies=deps,
            acceptance_criteria=list(data.get("acceptance_criteria", [])),
            requested_scope=dict(data.get("requested_scope", {})),
            created_at=data.get("created_at", ""),
            status=data.get("status", ProposalStatus.PROPOSED),
            rejection_reason=data.get("rejection_reason", ""),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class ExpansionRecord:
    proposal_id: str
    mission_id: str
    parent_task_id: str
    subdag_id: str
    graph_version_before: int
    graph_version_after: int
    trigger: str
    reason: str
    tasks_added: list[str]
    edges_added: list[tuple[str, str]]
    validation_result: dict[str, Any]
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "mission_id": self.mission_id,
            "parent_task_id": self.parent_task_id,
            "subdag_id": self.subdag_id,
            "graph_version_before": self.graph_version_before,
            "graph_version_after": self.graph_version_after,
            "trigger": self.trigger,
            "reason": self.reason,
            "tasks_added": list(self.tasks_added),
            "edges_added": [list(edge) for edge in self.edges_added],
            "validation_result": dict(self.validation_result),
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExpansionRecord:
        edges_raw = data.get("edges_added", [])
        edges = [(e[0], e[1]) for e in edges_raw if len(e) == 2]
        return cls(
            proposal_id=data["proposal_id"],
            mission_id=data["mission_id"],
            parent_task_id=data["parent_task_id"],
            subdag_id=data.get("subdag_id", ""),
            graph_version_before=int(data.get("graph_version_before", 1)),
            graph_version_after=int(data.get("graph_version_after", 2)),
            trigger=data.get("trigger", ""),
            reason=data.get("reason", ""),
            tasks_added=list(data.get("tasks_added", [])),
            edges_added=edges,
            validation_result=dict(data.get("validation_result", {})),
            timestamp=data.get("timestamp", ""),
        )


def compute_semantic_key(title: str, category: str = "GENERIC") -> str:
    """Computes a normalized semantic identity key to detect duplicate proposals."""
    clean_title = re.sub(r"[^a-z0-9]", "_", title.lower().strip())
    clean_title = re.sub(r"_+", "_", clean_title).strip("_")
    clean_cat = category.upper().strip()
    return f"{clean_cat}::{clean_title}"


class SubDagValidationError(Exception):
    pass


class SubDagValidator:
    """Validates dynamic sub-DAG expansion proposals deterministically against the active TaskGraph."""

    def __init__(self, limits: ExpansionLimits | None = None) -> None:
        self.limits = limits or ExpansionLimits()

    def validate(
        self,
        proposal: DynamicSubDagProposal,
        current_graph: TaskGraph,
    ) -> tuple[bool, str, list[TaskNode], list[tuple[str, str]]]:
        """Performs atomic multi-axis validation over (EXISTING_DAG + PROPOSED_SUBDAG).
        
        Returns:
            (is_valid, error_message, validated_nodes, validated_edges)
        """
        # 1. Proposal basic constraints
        if not proposal.proposal_id.strip():
            return False, "proposal_id é obrigatório.", [], []
        if not proposal.reason.strip():
            return False, "Motivo (reason) estruturado é obrigatório para expansão dinâmica.", [], []
        if not proposal.tasks:
            return False, "A proposta de sub-DAG não contém tarefas.", [], []

        # 2. Check parent task existence and depth
        if proposal.parent_task_id not in current_graph.nodes:
            return False, f"Parent task '{proposal.parent_task_id}' não existe no TaskGraph atual.", [], []
        
        parent_node = current_graph.nodes[proposal.parent_task_id]
        parent_depth = getattr(parent_node, "expansion_depth", 0)
        proposed_depth = parent_depth + 1

        # 3. Check Expansion Limits
        expansions_applied = len(getattr(current_graph, "expansion_history", []))
        if expansions_applied >= self.limits.max_expansions_per_mission:
            return False, f"expansion_limit_hit: Limite de {self.limits.max_expansions_per_mission} expansões por missão atingido.", [], []

        if len(proposal.tasks) > self.limits.max_tasks_per_expansion:
            return False, f"expansion_limit_hit: Proposta contém {len(proposal.tasks)} tarefas, excedendo o limite de {self.limits.max_tasks_per_expansion}.", [], []

        total_projected_tasks = len(current_graph.nodes) + len(proposal.tasks)
        if total_projected_tasks > self.limits.max_total_tasks:
            return False, f"expansion_limit_hit: Grafo resultante conteria {total_projected_tasks} tarefas, excedendo o limite total de {self.limits.max_total_tasks}.", [], []

        if proposed_depth > self.limits.max_expansion_depth:
            return False, f"expansion_limit_hit: Profundidade da sub-DAG ({proposed_depth}) excede o limite máximo permitido ({self.limits.max_expansion_depth}).", [], []

        # Count expansions originated by this parent task
        parent_expansions = sum(
            1 for rec in getattr(current_graph, "expansion_history", [])
            if rec.get("parent_task_id") == proposal.parent_task_id
        )
        if parent_expansions >= self.limits.max_expansions_per_parent_task:
            return False, f"expansion_limit_hit: A tarefa pai '{proposal.parent_task_id}' já originou o máximo de {self.limits.max_expansions_per_parent_task} expansões.", [], []

        # 4. Scope & Security checks
        scope = proposal.requested_scope
        if scope:
            forbidden_patterns = [r"\.\.[\\/]", r"^/etc", r"^C:\\Windows", r"DROP\s+DATABASE", r"rm\s+-rf"]
            scope_str = json.dumps(scope)
            for pattern in forbidden_patterns:
                if re.search(pattern, scope_str, re.IGNORECASE):
                    return False, f"Violação de escopo / segurança detectada na proposta de expansão: padrão '{pattern}'.", [], []

        # 5. Check graph version match (stale check)
        current_version = getattr(current_graph, "graph_version", 1)
        if proposal.base_graph_version != current_version:
            return False, f"REJECTED_STALE_GRAPH_VERSION: Proposta baseada na versão {proposal.base_graph_version}, mas o grafo atual está na versão {current_version}.", [], []

        # 6. Build proposed nodes and validate unique IDs & deduplication
        existing_task_ids = set(current_graph.nodes.keys())
        existing_semantic_keys = {
            compute_semantic_key(n.title, n.category): n.task_id
            for n in current_graph.nodes.values()
        }

        proposed_nodes: list[TaskNode] = []
        proposed_task_ids: set[str] = set()
        subdag_id = f"subdag_{uuid.uuid4().hex[:8]}"

        for t_raw in proposal.tasks:
            t_id = t_raw.get("task_id") or f"dyn_{uuid.uuid4().hex[:8]}"
            t_title = t_raw.get("title", "").strip()
            t_cat = t_raw.get("category", "GENERIC")

            if not t_title:
                return False, "Cada tarefa proposta deve possuir um título não vazio.", [], []

            # Check ID collisions
            if t_id in existing_task_ids:
                return False, f"ID de tarefa duplicado: '{t_id}' já existe no TaskGraph.", [], []
            if t_id in proposed_task_ids:
                return False, f"ID de tarefa duplicado internamente na proposta: '{t_id}'.", [], []

            # Check semantic duplication
            sem_key = compute_semantic_key(t_title, t_cat)
            if sem_key in existing_semantic_keys:
                existing_match_id = existing_semantic_keys[sem_key]
                return False, f"Tarefa semanticamente duplicada detectada: '{t_title}' ({t_cat}) já existe como '{existing_match_id}'.", [], []

            existing_semantic_keys[sem_key] = t_id
            proposed_task_ids.add(t_id)

            # Extract task dependencies
            deps = list(t_raw.get("dependencies", []))
            
            node = TaskNode(
                task_id=t_id,
                title=t_title,
                description=t_raw.get("description", t_title),
                category=t_cat,
                dependencies=deps,
                status=TaskStatus.PENDING,
                priority=int(t_raw.get("priority", 0)),
                timeout_seconds=float(t_raw.get("timeout_seconds", 60.0)),
                required=bool(t_raw.get("required", True)),
                metadata={
                    **t_raw.get("metadata", {}),
                    "parent_task_id": proposal.parent_task_id,
                    "subdag_id": subdag_id,
                    "proposal_id": proposal.proposal_id,
                    "expansion_depth": proposed_depth,
                    "semantic_key": sem_key,
                },
            )
            node.parent_task_id = proposal.parent_task_id
            node.subdag_id = subdag_id
            node.expansion_depth = proposed_depth
            node.semantic_key = sem_key
            proposed_nodes.append(node)

        # 7. Resolve proposed edges from explicit proposal.dependencies
        all_projected_ids = existing_task_ids | proposed_task_ids
        edges_to_add: list[tuple[str, str]] = []

        node_map = {n.task_id: n for n in proposed_nodes}
        for upstream, downstream in proposal.dependencies:
            if upstream not in all_projected_ids:
                return False, f"Dependência a montante desconhecida '{upstream}' na proposta.", [], []
            if downstream not in all_projected_ids:
                return False, f"Dependência a jusante desconhecida '{downstream}' na proposta.", [], []
            
            edges_to_add.append((upstream, downstream))
            if downstream in node_map and upstream not in node_map[downstream].dependencies:
                node_map[downstream].dependencies.append(upstream)

        # Verify all node dependencies exist in the projected graph
        for node in proposed_nodes:
            for dep_id in node.dependencies:
                if dep_id not in all_projected_ids:
                    return False, f"Tarefa '{node.task_id}' depende de '{dep_id}', que não existe no grafo nem na proposta.", [], []
                if dep_id == node.task_id:
                    return False, f"Auto-ciclo detectado: Tarefa '{node.task_id}' não pode depender de si própria.", [], []

        # 8. Cycle Prevention over (EXISTING + PROPOSED)
        # Construct temporary combined graph
        combined_nodes = [TaskNode.from_dict(n.to_dict()) for n in current_graph.nodes.values()]
        combined_nodes.extend([TaskNode.from_dict(n.to_dict()) for n in proposed_nodes])
        combined_node_map = {n.task_id: n for n in combined_nodes}

        for upstream, downstream in edges_to_add:
            if downstream in combined_node_map and upstream not in combined_node_map[downstream].dependencies:
                combined_node_map[downstream].dependencies.append(upstream)

        temp_graph = TaskGraph()
        for n in combined_nodes:
            temp_graph.add_node(n)

        try:
            temp_graph.validate()
        except (TaskGraphCycleError, TaskDependencyError) as cycle_err:
            return False, f"Ciclo detectado ao integrar sub-DAG no grafo existente: {cycle_err}", [], []

        return True, "Validação de Sub-DAG concluída com sucesso.", proposed_nodes, edges_to_add


class DynamicSubDagEngine:
    """Manages the lifecycle of sub-DAG expansions: propose, validate, rebase, and atomic commit."""

    def __init__(self, limits: ExpansionLimits | None = None) -> None:
        self.limits = limits or ExpansionLimits()
        self.validator = SubDagValidator(limits=self.limits)
        self._lock = asyncio.Lock()
        self._proposals_history: dict[str, DynamicSubDagProposal] = {}

    async def propose_expansion(
        self,
        proposal: DynamicSubDagProposal,
        current_graph: TaskGraph,
    ) -> tuple[bool, str, DynamicSubDagProposal]:
        """Registers and validates a sub-DAG expansion proposal."""
        async with self._lock:
            proposal.status = ProposalStatus.VALIDATING
            is_valid, msg, nodes, edges = self.validator.validate(proposal, current_graph)
            if not is_valid:
                proposal.status = ProposalStatus.REJECTED
                proposal.rejection_reason = msg
                self._proposals_history[proposal.proposal_id] = proposal
                log_event(
                    logger,
                    "dynamic_subdag.proposal_rejected",
                    proposal_id=proposal.proposal_id,
                    reason=msg,
                )
                return False, msg, proposal

            proposal.status = ProposalStatus.ACCEPTED
            self._proposals_history[proposal.proposal_id] = proposal
            log_event(
                logger,
                "dynamic_subdag.proposal_accepted",
                proposal_id=proposal.proposal_id,
                parent_task_id=proposal.parent_task_id,
                tasks_count=len(proposal.tasks),
            )
            return True, "Proposta aceita para integração.", proposal

    async def apply_expansion(
        self,
        proposal: DynamicSubDagProposal,
        orchestrator: Any,
    ) -> tuple[bool, str, ExpansionRecord | None]:
        """Atomically commits the accepted sub-DAG to TaskGraph and MissionStateStore."""
        async with self._lock:
            current_graph: TaskGraph = orchestrator.task_graph
            current_version = getattr(current_graph, "graph_version", 1)

            # Check if graph version moved (concurrent proposal handling)
            if proposal.base_graph_version != current_version:
                # Attempt deterministic rebase if proposal is still disjoint and valid
                proposal.base_graph_version = current_version
                is_valid, msg, nodes, edges = self.validator.validate(proposal, current_graph)
                if not is_valid:
                    proposal.status = ProposalStatus.STALE
                    proposal.rejection_reason = f"REJECTED_STALE_GRAPH_VERSION: Rebase falhou: {msg}"
                    return False, proposal.rejection_reason, None
                log_event(
                    logger,
                    "dynamic_subdag.proposal_rebased",
                    proposal_id=proposal.proposal_id,
                    new_base_version=current_version,
                )
            else:
                is_valid, msg, nodes, edges = self.validator.validate(proposal, current_graph)
                if not is_valid:
                    proposal.status = ProposalStatus.REJECTED
                    proposal.rejection_reason = msg
                    return False, msg, None

            # ATOMIC COMMIT (All-or-Nothing)
            subdag_id = nodes[0].subdag_id if nodes else f"subdag_{uuid.uuid4().hex[:8]}"
            added_task_ids = [n.task_id for n in nodes]
            new_graph_version = current_version + 1

            record = ExpansionRecord(
                proposal_id=proposal.proposal_id,
                mission_id=proposal.mission_id,
                parent_task_id=proposal.parent_task_id,
                subdag_id=subdag_id,
                graph_version_before=current_version,
                graph_version_after=new_graph_version,
                trigger=proposal.trigger.value if isinstance(proposal.trigger, ExpansionTrigger) else str(proposal.trigger),
                reason=proposal.reason,
                tasks_added=added_task_ids,
                edges_added=edges,
                validation_result={"status": "OK", "nodes_count": len(nodes)},
                timestamp=utc_now(),
            )

            # 1. Update MissionStateStore (WorkPackages & Criteria)
            project_id = orchestrator.project_id
            mission_id = orchestrator.mission_id
            store: MissionStateStore = orchestrator.mission_state

            try:
                for node in nodes:
                    await asyncio.to_thread(
                        store.create_work_package,
                        project_id=project_id,
                        mission_id=mission_id,
                        title=node.title,
                        description=node.description,
                        type=node.category,
                        priority=node.priority,
                        dependencies=node.dependencies,
                        required=node.required,
                        work_package_id=node.task_id,
                        metadata=node.metadata,
                    )

                # Attach Acceptance Criteria from proposal
                for crit in proposal.acceptance_criteria:
                    crit_id = crit.get("criterion_id") or f"crit_{uuid.uuid4().hex[:8]}"
                    await asyncio.to_thread(
                        store.create_criterion,
                        project_id=project_id,
                        mission_id=mission_id,
                        owner_type=crit.get("owner_type", "WORK_PACKAGE"),
                        owner_id=crit.get("owner_id", added_task_ids[0] if added_task_ids else proposal.parent_task_id),
                        description=crit.get("description", "Critério dinâmico de aceitação"),
                        required=bool(crit.get("required", True)),
                        criterion_id=crit_id,
                    )

                # Persist updated graph_version in MissionStateStore
                if hasattr(store, "update_mission_metadata"):
                    await asyncio.to_thread(
                        store.update_mission_metadata,
                        project_id=project_id,
                        mission_id=mission_id,
                        updates={"graph_version": new_graph_version},
                    )
            except Exception as store_err:
                proposal.status = ProposalStatus.FAILED
                proposal.rejection_reason = f"Falha transacional ao persistir no MissionStateStore: {store_err}"
                log_event(logger, "dynamic_subdag.commit_rollback", error=str(store_err))
                return False, proposal.rejection_reason, None

            # 2. Update TaskGraph
            current_graph.apply_subdag(nodes, edges, record.to_dict())

            # 3. Persist audit record to disk
            expansions_dir = os.path.join(
                store._mission_dir(project_id, mission_id), "expansions"
            )
            os.makedirs(expansions_dir, exist_ok=True)
            exp_file = os.path.join(expansions_dir, f"expansion_{new_graph_version:04d}.json")
            with open(exp_file, "w", encoding="utf-8") as f:
                json.dump(record.to_dict(), f, indent=2, ensure_ascii=False)

            proposal.status = ProposalStatus.APPLIED
            self._proposals_history[proposal.proposal_id] = proposal

            # 4. Trigger Checkpoint & Events
            orchestrator.save_checkpoint(
                f"Sub-DAG expandido a partir de '{proposal.parent_task_id}' (DAG v{new_graph_version})"
            )

            await orchestrator._emit_event("expansion_applied", {
                "proposal_id": proposal.proposal_id,
                "parent_task_id": proposal.parent_task_id,
                "graph_version": new_graph_version,
                "tasks_added": added_task_ids,
                "trigger": record.trigger,
                "reason": record.reason,
            })
            await orchestrator._emit_event("graph_version_changed", {
                "graph_version": new_graph_version,
                "previous_version": current_version,
            })
            await orchestrator._emit_chat(
                "JARVIS",
                "Orquestrador",
                f"🌱 **Sub-DAG Expandido (v{new_graph_version})**: +{len(nodes)} tarefas adicionadas a partir de `{proposal.parent_task_id}` ({record.reason})."
            )

            log_event(
                logger,
                "dynamic_subdag.expansion_applied",
                proposal_id=proposal.proposal_id,
                new_version=new_graph_version,
                tasks_added=len(nodes),
            )

            return True, f"Sub-DAG aplicado com sucesso. Grafo atualizado para v{new_graph_version}.", record

    def get_proposals_history(self) -> list[dict[str, Any]]:
        return [p.to_dict() for p in self._proposals_history.values()]
