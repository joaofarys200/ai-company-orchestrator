from __future__ import annotations

import asyncio
import enum
import hashlib
import json
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from agents.dynamic_subdag import compute_semantic_key
from agents.mission_state import (
    MissionStateError,
    MissionStateStore,
    WorkPackage,
    WORK_PACKAGE_STATUSES,
    utc_now,
)
from agents.task_graph import (
    FailureCategory,
    FailureInfo,
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


# ── ENUMS ────────────────────────────────────────────────────────────────────

class AdaptationTrigger(str, enum.Enum):
    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    TEST_FAILURE = "TEST_FAILURE"
    BUILD_FAILURE = "BUILD_FAILURE"
    RUNTIME_FAILURE = "RUNTIME_FAILURE"
    BROWSER_FAILURE = "BROWSER_FAILURE"
    REQUIREMENT_CHANGE = "REQUIREMENT_CHANGE"
    NEW_REQUIREMENT = "NEW_REQUIREMENT"
    ARCHITECTURE_DISCOVERY = "ARCHITECTURE_DISCOVERY"
    DEPENDENCY_CHANGE = "DEPENDENCY_CHANGE"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"
    TASK_BLOCKED = "TASK_BLOCKED"
    RESOURCE_CONSTRAINT = "RESOURCE_CONSTRAINT"
    RESOURCE_LIMITATION = "RESOURCE_LIMITATION"
    PERFORMANCE_FAILURE = "PERFORMANCE_FAILURE"
    PERFORMANCE_DEGRADATION = "PERFORMANCE_DEGRADATION"
    UNEXPECTED_COMPLEXITY = "UNEXPECTED_COMPLEXITY"
    GOAL_OBSOLETED = "GOAL_OBSOLETED"
    HUMAN_INTERVENTION = "HUMAN_INTERVENTION"
    ENVIRONMENT_CHANGE = "ENVIRONMENT_CHANGE"


class ObservationSource(str, enum.Enum):
    TEST = "TEST"
    BUILD = "BUILD"
    RUNTIME = "RUNTIME"
    BROWSER = "BROWSER"
    ARCHITECTURE = "ARCHITECTURE"
    TOOL = "TOOL"
    USER = "USER"


class ObservationSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PlanEvaluationDecision(str, enum.Enum):
    KEEP_PLAN = "KEEP_PLAN"
    ADAPT_PLAN = "ADAPT_PLAN"
    REPLAN = "REPLAN"
    BLOCK_MISSION = "BLOCK_MISSION"


class AdaptationStatus(str, enum.Enum):
    PROPOSED = "PROPOSED"
    VALIDATING = "VALIDATING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    STALE = "STALE"
    APPLIED = "APPLIED"
    FAILED = "FAILED"


# ── DATA CONTRACTS ───────────────────────────────────────────────────────────

@dataclass
class Observation:
    observation_id: str = ""
    source: ObservationSource | str = ObservationSource.RUNTIME
    event: str = ""
    task_id: str | None = None
    evidence_id: str | None = None
    severity: ObservationSeverity | str = ObservationSeverity.MEDIUM
    impact: str = ""
    detected_at: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.observation_id:
            self.observation_id = f"obs_{uuid.uuid4().hex[:8]}"
        if not self.detected_at:
            self.detected_at = utc_now()
        if isinstance(self.source, str):
            try:
                self.source = ObservationSource(self.source)
            except ValueError:
                self.source = ObservationSource.RUNTIME
        if isinstance(self.severity, str):
            try:
                self.severity = ObservationSeverity(self.severity)
            except ValueError:
                self.severity = ObservationSeverity.MEDIUM

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "source": self.source.value if isinstance(self.source, ObservationSource) else str(self.source),
            "event": self.event,
            "task_id": self.task_id,
            "evidence_id": self.evidence_id,
            "severity": self.severity.value if isinstance(self.severity, ObservationSeverity) else str(self.severity),
            "impact": self.impact,
            "detected_at": self.detected_at,
            "details": dict(self.details),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Observation:
        return cls(
            observation_id=data.get("observation_id", f"obs_{uuid.uuid4().hex[:8]}"),
            source=data.get("source", ObservationSource.RUNTIME),
            event=data.get("event", ""),
            task_id=data.get("task_id"),
            evidence_id=data.get("evidence_id"),
            severity=data.get("severity", ObservationSeverity.MEDIUM),
            impact=data.get("impact", ""),
            detected_at=data.get("detected_at", ""),
            details=dict(data.get("details", {})),
        )


@dataclass
class AdaptationBudget:
    max_plan_adaptations: int = 5
    max_replans: int = 3
    max_graph_churn: int = 15
    max_strategy_repeats: int = 2

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdaptationBudget:
        return cls(
            max_plan_adaptations=int(data.get("max_plan_adaptations", 5)),
            max_replans=int(data.get("max_replans", 3)),
            max_graph_churn=int(data.get("max_graph_churn", 15)),
            max_strategy_repeats=int(data.get("max_strategy_repeats", 2)),
        )


@dataclass
class PlanQualityMetrics:
    initial_plan_valid: bool = True
    adapted_plan_valid: bool = True
    replan_valid: bool = True
    plan_efficiency: float = 1.0
    plan_churn_count: int = 0
    adaptations_count: int = 0
    replans_count: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    blocked_tasks: int = 0
    unrecoverable_blockage: bool = False
    observation_severity_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlanQualityMetrics:
        return cls(
            initial_plan_valid=bool(data.get("initial_plan_valid", True)),
            adapted_plan_valid=bool(data.get("adapted_plan_valid", True)),
            replan_valid=bool(data.get("replan_valid", True)),
            plan_efficiency=float(data.get("plan_efficiency", 1.0)),
            plan_churn_count=int(data.get("plan_churn_count", 0)),
            adaptations_count=int(data.get("adaptations_count", 0)),
            replans_count=int(data.get("replans_count", 0)),
            total_tasks=int(data.get("total_tasks", 0)),
            completed_tasks=int(data.get("completed_tasks", 0)),
            failed_tasks=int(data.get("failed_tasks", 0)),
            blocked_tasks=int(data.get("blocked_tasks", 0)),
            unrecoverable_blockage=bool(data.get("unrecoverable_blockage", False)),
            observation_severity_score=float(data.get("observation_severity_score", 0.0)),
        )


@dataclass
class PlanEvaluationResult:
    decision: PlanEvaluationDecision | str
    reason: str
    trigger: AdaptationTrigger | str
    observations: list[Observation] = field(default_factory=list)
    affected_tasks: list[str] = field(default_factory=list)
    recommended_proposal: dict[str, Any] | None = None
    metrics: PlanQualityMetrics = field(default_factory=PlanQualityMetrics)

    def __post_init__(self) -> None:
        if isinstance(self.decision, str):
            try:
                self.decision = PlanEvaluationDecision(self.decision)
            except ValueError:
                self.decision = PlanEvaluationDecision.KEEP_PLAN
        if isinstance(self.trigger, str):
            try:
                self.trigger = AdaptationTrigger(self.trigger)
            except ValueError:
                self.trigger = AdaptationTrigger.RUNTIME_FAILURE

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value if isinstance(self.decision, PlanEvaluationDecision) else str(self.decision),
            "reason": self.reason,
            "trigger": self.trigger.value if isinstance(self.trigger, AdaptationTrigger) else str(self.trigger),
            "observations": [o.to_dict() for o in self.observations],
            "affected_tasks": list(self.affected_tasks),
            "recommended_proposal": self.recommended_proposal,
            "metrics": self.metrics.to_dict(),
        }


@dataclass
class MissionAdaptationProposal:
    proposal_id: str = ""
    mission_id: str = ""
    base_graph_version: int = 1
    trigger: AdaptationTrigger | str = AdaptationTrigger.RUNTIME_FAILURE
    reason: str = ""
    affected_tasks: list[str] = field(default_factory=list)
    added_tasks: list[dict[str, Any]] = field(default_factory=list)
    removed_tasks: list[str] = field(default_factory=list)
    modified_tasks: list[dict[str, Any]] = field(default_factory=list)
    changed_edges: list[Any] = field(default_factory=list)  # Added edges (upstream, downstream)
    removed_edges: list[Any] = field(default_factory=list)  # Removed edges
    acceptance_criteria_changes: list[dict[str, Any]] = field(default_factory=list)
    requested_scope: Any = field(default_factory=dict)
    evidence_ids: list[str] = field(default_factory=list)
    justification_for_completed_tasks: str | None = None
    created_at: str = ""
    status: AdaptationStatus | str = AdaptationStatus.PROPOSED
    rejection_reason: str = ""
    decision: PlanEvaluationDecision | str = PlanEvaluationDecision.ADAPT_PLAN
    metadata: dict[str, Any] = field(default_factory=dict)
    is_economic: bool = False

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = utc_now()
        if isinstance(self.trigger, str):
            try:
                self.trigger = AdaptationTrigger(self.trigger)
            except ValueError:
                pass
        if isinstance(self.status, str):
            try:
                self.status = AdaptationStatus(self.status)
            except ValueError:
                self.status = AdaptationStatus.PROPOSED
        if isinstance(self.decision, str):
            try:
                self.decision = PlanEvaluationDecision(self.decision)
            except ValueError:
                self.decision = PlanEvaluationDecision.ADAPT_PLAN

    def compute_strategy_fingerprint(self) -> str:
        """Computes a deterministic hash of the proposed topological strategy."""
        added_keys = sorted(
            compute_semantic_key(t.get("title", ""), t.get("category", "GENERIC"))
            for t in self.added_tasks
        )
        removed_keys = sorted(self.removed_tasks)
        edges = sorted([f"{u}->{d}" if isinstance(u, str) else f"{edge[0]}->{edge[1]}" for edge in self.changed_edges for u, d in [(edge[0], edge[1])]])
        payload = f"{self.decision}:{added_keys}:{removed_keys}:{edges}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "mission_id": self.mission_id,
            "base_graph_version": self.base_graph_version,
            "trigger": self.trigger.value if isinstance(self.trigger, AdaptationTrigger) else str(self.trigger),
            "reason": self.reason,
            "affected_tasks": list(self.affected_tasks),
            "added_tasks": [dict(t) for t in self.added_tasks],
            "removed_tasks": list(self.removed_tasks),
            "modified_tasks": [dict(t) for t in self.modified_tasks],
            "changed_edges": [list(edge) for edge in self.changed_edges],
            "removed_edges": [list(edge) for edge in self.removed_edges],
            "acceptance_criteria_changes": [dict(c) for c in self.acceptance_criteria_changes],
            "requested_scope": dict(self.requested_scope),
            "evidence_ids": list(self.evidence_ids),
            "justification_for_completed_tasks": self.justification_for_completed_tasks,
            "created_at": self.created_at,
            "status": self.status.value if isinstance(self.status, AdaptationStatus) else str(self.status),
            "rejection_reason": self.rejection_reason,
            "decision": self.decision.value if isinstance(self.decision, PlanEvaluationDecision) else str(self.decision),
            "metadata": dict(self.metadata),
            "is_economic": bool(self.is_economic),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MissionAdaptationProposal:
        changed_edges_raw = data.get("changed_edges", [])
        changed_edges = [(edge[0], edge[1]) for edge in changed_edges_raw if len(edge) == 2]
        removed_edges_raw = data.get("removed_edges", [])
        removed_edges = [(edge[0], edge[1]) for edge in removed_edges_raw if len(edge) == 2]

        return cls(
            proposal_id=data["proposal_id"],
            mission_id=data["mission_id"],
            base_graph_version=int(data.get("base_graph_version", 1)),
            trigger=data.get("trigger", AdaptationTrigger.RUNTIME_FAILURE),
            reason=data.get("reason", ""),
            affected_tasks=list(data.get("affected_tasks", [])),
            added_tasks=list(data.get("added_tasks", [])),
            removed_tasks=list(data.get("removed_tasks", [])),
            modified_tasks=list(data.get("modified_tasks", [])),
            changed_edges=changed_edges,
            removed_edges=removed_edges,
            acceptance_criteria_changes=list(data.get("acceptance_criteria_changes", [])),
            requested_scope=dict(data.get("requested_scope", {})),
            evidence_ids=list(data.get("evidence_ids", [])),
            justification_for_completed_tasks=data.get("justification_for_completed_tasks"),
            created_at=data.get("created_at", ""),
            status=data.get("status", AdaptationStatus.PROPOSED),
            rejection_reason=data.get("rejection_reason", ""),
            decision=data.get("decision", PlanEvaluationDecision.ADAPT_PLAN),
            metadata=dict(data.get("metadata", {})),
            is_economic=bool(data.get("is_economic", False)),
        )


@dataclass
class AdaptationRecord:
    adaptation_id: str
    proposal_id: str
    mission_id: str
    graph_version_before: int
    graph_version_after: int
    decision: PlanEvaluationDecision | str
    trigger: AdaptationTrigger | str
    reason: str
    tasks_added: list[str] = field(default_factory=list)
    tasks_removed: list[str] = field(default_factory=list)
    tasks_modified: list[str] = field(default_factory=list)
    tasks_preserved: list[str] = field(default_factory=list)
    edges_added: list[list[str]] = field(default_factory=list)
    edges_removed: list[list[str]] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    timestamp: str = ""
    strategy_fingerprint: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = utc_now()
        if isinstance(self.decision, PlanEvaluationDecision):
            self.decision = self.decision.value
        if isinstance(self.trigger, AdaptationTrigger):
            self.trigger = self.trigger.value

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdaptationRecord:
        return cls(
            adaptation_id=data["adaptation_id"],
            proposal_id=data["proposal_id"],
            mission_id=data["mission_id"],
            graph_version_before=int(data.get("graph_version_before", 1)),
            graph_version_after=int(data.get("graph_version_after", 2)),
            decision=data.get("decision", "ADAPT_PLAN"),
            trigger=data.get("trigger", "RUNTIME_FAILURE"),
            reason=data.get("reason", ""),
            tasks_added=list(data.get("tasks_added", [])),
            tasks_removed=list(data.get("tasks_removed", [])),
            tasks_modified=list(data.get("tasks_modified", [])),
            tasks_preserved=list(data.get("tasks_preserved", [])),
            edges_added=list(data.get("edges_added", [])),
            edges_removed=list(data.get("edges_removed", [])),
            evidence_ids=list(data.get("evidence_ids", [])),
            timestamp=data.get("timestamp", ""),
            strategy_fingerprint=data.get("strategy_fingerprint", ""),
        )


# ── VALIDATOR ────────────────────────────────────────────────────────────────

class AdaptivePlanningValidator:
    """Strict, deterministic validator governing plan adaptations and replans."""

    def __init__(self, budget: AdaptationBudget | None = None) -> None:
        self.budget = budget or AdaptationBudget()

    def validate(
        self,
        proposal: MissionAdaptationProposal,
        current_graph: TaskGraph,
        adaptation_history: list[dict[str, Any]] | None = None,
    ) -> tuple[bool, str, dict[str, Any]]:
        """
        Validates an adaptation proposal against the current TaskGraph and historical constraints.
        Returns: (is_valid, error_message, validated_payload)
        """
        history = list(adaptation_history or [])

        # 1. Trigger validation
        if not isinstance(proposal.trigger, AdaptationTrigger):
            try:
                proposal.trigger = AdaptationTrigger(proposal.trigger)
            except (ValueError, TypeError):
                return False, f"INVALID_TRIGGER: Trigger inválido '{proposal.trigger}'. Triggers permitidos: {[t.value for t in AdaptationTrigger]}", {}

        # 2. Reason requirement
        if not proposal.reason or len(proposal.reason.strip()) < 10:
            return False, "MISSING_REASON: Proposta de adaptação exige motivo fundamentado (mínimo 10 caracteres).", {}

        # 3. Evidence requirement for failure triggers
        failure_triggers = {
            AdaptationTrigger.VALIDATION_FAILURE,
            AdaptationTrigger.TEST_FAILURE,
            AdaptationTrigger.BUILD_FAILURE,
            AdaptationTrigger.RUNTIME_FAILURE,
            AdaptationTrigger.BROWSER_FAILURE,
            AdaptationTrigger.PERFORMANCE_FAILURE,
        }
        if proposal.trigger in failure_triggers and not proposal.evidence_ids:
            # Check if any affected task has evidence or failure info
            has_task_evidence = any(
                bool(current_graph.nodes[tid].evidence_refs or current_graph.nodes[tid].failure_info.category != FailureCategory.NONE)
                for tid in proposal.affected_tasks
                if tid in current_graph.nodes
            )
            if not has_task_evidence and not proposal.evidence_ids:
                return False, f"EVIDENCE_REQUIRED: Trigger '{proposal.trigger.value}' requer evidence_ids ou evidência registada nas tarefas afetadas.", {}

        # 4. Stale graph version check
        current_version = getattr(current_graph, "graph_version", 1)
        if proposal.base_graph_version != current_version:
            return False, f"REJECTED_STALE_GRAPH_VERSION: Proposta baseada na versão {proposal.base_graph_version}, mas o grafo atual está na versão {current_version}.", {}

        # 5. Budget limits
        total_adaptations = sum(1 for r in history if r.get("decision") == "ADAPT_PLAN")
        total_replans = sum(1 for r in history if r.get("decision") == "REPLAN")
        total_churn = sum(
            len(r.get("tasks_added", [])) + len(r.get("tasks_removed", []))
            for r in history
        )

        decision_str = proposal.decision.value if isinstance(proposal.decision, PlanEvaluationDecision) else str(proposal.decision)
        if decision_str == "ADAPT_PLAN" and total_adaptations >= self.budget.max_plan_adaptations:
            return False, f"BUDGET_EXCEEDED: Limite máximo de adaptações ({self.budget.max_plan_adaptations}) atingido.", {}

        if decision_str == "REPLAN" and total_replans >= self.budget.max_replans:
            return False, f"REPLAN_BUDGET_EXCEEDED: Limite máximo de replans ({self.budget.max_replans}) atingido.", {}

        proposed_churn = len(proposal.added_tasks) + len(proposal.removed_tasks)
        if total_churn + proposed_churn > self.budget.max_graph_churn:
            return False, f"CHURN_LIMIT_EXCEEDED: Limite de churn no grafo ({self.budget.max_graph_churn}) excedido (atual={total_churn}, proposto={proposed_churn}).", {}

        # 6. Oscillation & Strategy Repeat Detection
        fingerprint = proposal.compute_strategy_fingerprint()
        repeat_count = sum(1 for r in history if r.get("strategy_fingerprint") == fingerprint)
        if repeat_count >= self.budget.max_strategy_repeats:
            return False, f"REJECTED_STRATEGY_OSCILLATION: A estratégia proposta ({fingerprint}) já foi executada {repeat_count} vez(es) sem progresso.", {}

        # Detect alternating cycle: e.g. last record == fingerprint 2 steps ago
        if len(history) >= 2:
            last_fp = history[-1].get("strategy_fingerprint")
            prev_fp = history[-2].get("strategy_fingerprint")
            if fingerprint == prev_fp and fingerprint != last_fp:
                return False, "REJECTED_STRATEGY_OSCILLATION: Ciclo alternado detetado entre estratégias anteriores.", {}

        # 7. Completed task preservation check
        for tid in proposal.removed_tasks:
            if tid in current_graph.nodes:
                node = current_graph.nodes[tid]
                if node.status == TaskStatus.COMPLETED and not proposal.justification_for_completed_tasks:
                    return False, f"COMPLETED_TASK_REGRESSION_FORBIDDEN: Tarefa concluída '{tid}' não pode ser removida sem 'justification_for_completed_tasks'.", {}

        for mod in proposal.modified_tasks:
            tid = mod.get("task_id")
            if tid and tid in current_graph.nodes:
                node = current_graph.nodes[tid]
                if node.status == TaskStatus.COMPLETED and not proposal.justification_for_completed_tasks:
                    return False, f"COMPLETED_TASK_REGRESSION_FORBIDDEN: Tarefa concluída '{tid}' não pode ser modificada sem 'justification_for_completed_tasks'.", {}

        # 8. Running task non-interference check
        for tid in proposal.removed_tasks:
            if tid in current_graph.nodes and current_graph.nodes[tid].status == TaskStatus.RUNNING:
                return False, f"RUNNING_TASK_MUTATION_FORBIDDEN: Tarefa '{tid}' está atualmente em RUNNING e não pode ser removida diretamente.", {}

        for mod in proposal.modified_tasks:
            tid = mod.get("task_id")
            if tid and tid in current_graph.nodes and current_graph.nodes[tid].status == TaskStatus.RUNNING:
                return False, f"RUNNING_TASK_MUTATION_FORBIDDEN: Campos de tarefa '{tid}' em RUNNING não podem ser alterados.", {}

        # 9. Scope security check
        scope = proposal.requested_scope
        if scope:
            if isinstance(scope, str) and any(w in scope for w in ("ESCALATION", "TAKEOVER")):
                return False, "SCOPE_ESCALATION_FORBIDDEN: Tentativa de escalação de escopo não autorizada.", {}
            forbidden_patterns = [r"\.\.[\\/]", r"^/etc", r"^C:\\Windows", r"DROP\s+DATABASE", r"rm\s+-rf", r"ROOT_TAKEOVER", r"ESCALATION"]
            scope_str = json.dumps(scope) if not isinstance(scope, str) else scope
            for pattern in forbidden_patterns:
                if re.search(pattern, scope_str, re.IGNORECASE):
                    return False, f"SCOPE_ESCALATION_FORBIDDEN: Violação de segurança de escopo na proposta: '{pattern}'.", {}

        # 9.1 Economic mission safeguards
        if getattr(proposal, "is_economic", False):
            for t in proposal.added_tasks:
                title = str(t.get("title", "")).lower()
                tid = str(t.get("task_id", "")).lower()
                desc = str(t.get("description", "")).lower()
                if "bypass" in title or "bypass" in tid or "bypass" in desc or "skip_gate" in title:
                    return False, "ECONOMIC_GATE_BYPASS_FORBIDDEN: Missão económica não pode saltar aprovações humanas.", {}

            for acc in proposal.acceptance_criteria_changes:
                if acc.get("action") == "remove":
                    return False, "ECONOMIC_EVIDENCE_REMOVAL_FORBIDDEN: Missão económica não pode remover critérios de evidência.", {}

            reason_lower = proposal.reason.lower()
            if any(w in reason_lower for w in ("phantom", "fictícia", "ficticia", "inventar receita")):
                return False, "ECONOMIC_PHANTOM_REVENUE_FORBIDDEN: Proibido registar receita fictícia sem liquidação comprovada.", {}

        # 10. Graph simulation & cycle detection (Transactional trial build)
        simulated_nodes: dict[str, TaskNode] = {}
        for nid, n in current_graph.nodes.items():
            simulated_nodes[nid] = TaskNode(
                task_id=n.task_id,
                title=n.title,
                description=n.description,
                category=n.category,
                dependencies=list(n.dependencies),
                status=n.status,
                priority=n.priority,
                attempt_count=n.attempt_count,
                timeout_seconds=n.timeout_seconds,
                retry_config=n.retry_config,
                result_summary=n.result_summary,
                output_data=dict(n.output_data),
                failure_info=n.failure_info,
                evidence_refs=list(n.evidence_refs),
                required=n.required,
                created_at=n.created_at,
                started_at=n.started_at,
                completed_at=n.completed_at,
                metadata=dict(n.metadata),
                version=n.version,
                parent_task_id=n.parent_task_id,
                subdag_id=n.subdag_id,
                expansion_depth=n.expansion_depth,
                semantic_key=n.semantic_key,
            )

        # Apply removals
        for tid in proposal.removed_tasks:
            if tid in simulated_nodes:
                del simulated_nodes[tid]
                for sn in simulated_nodes.values():
                    if tid in sn.dependencies:
                        sn.dependencies.remove(tid)

        # Apply modifications
        for mod in proposal.modified_tasks:
            tid = mod.get("task_id")
            if tid and tid in simulated_nodes:
                sn = simulated_nodes[tid]
                if "title" in mod:
                    sn.title = mod["title"]
                if "description" in mod:
                    sn.description = mod["description"]
                if "category" in mod:
                    sn.category = mod["category"]
                if "required" in mod:
                    sn.required = bool(mod["required"])
                if "dependencies" in mod:
                    sn.dependencies = list(mod["dependencies"])
                if "metadata" in mod:
                    sn.metadata.update(mod["metadata"])

        # Apply additions
        added_task_ids: set[str] = set()
        for t_spec in proposal.added_tasks:
            tid = t_spec.get("task_id")
            if not tid:
                return False, "Tarefa adicionada sem 'task_id'.", {}
            if tid in simulated_nodes:
                return False, f"ID de tarefa duplicado: '{tid}' já existe no grafo.", {}
            if tid in added_task_ids:
                return False, f"ID de tarefa duplicado na proposta: '{tid}'.", {}
            added_task_ids.add(tid)

            # Check semantic duplication with existing non-removed nodes
            sem_key = compute_semantic_key(t_spec.get("title", tid), t_spec.get("category", "GENERIC"))
            for existing_node in simulated_nodes.values():
                if existing_node.semantic_key == sem_key and existing_node.status != TaskStatus.CANCELLED:
                    return False, f"Deduplicação: tarefa com semântica idêntica '{t_spec.get('title')}' já existe ({existing_node.task_id}).", {}

            status_str = t_spec.get("status", "PENDING")
            task_status = TaskStatus(status_str) if status_str in TaskStatus._value2member_map_ else TaskStatus.PENDING

            simulated_nodes[tid] = TaskNode(
                task_id=tid,
                title=t_spec.get("title", tid),
                description=t_spec.get("description", ""),
                category=t_spec.get("category", "CODING"),
                dependencies=list(t_spec.get("dependencies", [])),
                status=task_status,
                priority=int(t_spec.get("priority", 0)),
                timeout_seconds=float(t_spec.get("timeout_seconds", 60.0)),
                required=bool(t_spec.get("required", True)),
                created_at=utc_now(),
                metadata=dict(t_spec.get("metadata", {})),
                version=1,
                semantic_key=sem_key,
            )

        # Apply edge modifications
        for u, d in proposal.changed_edges:
            if d in simulated_nodes:
                if u not in simulated_nodes:
                    return False, f"Aresta inválida: nó a montante '{u}' não existe.", {}
                if u not in simulated_nodes[d].dependencies:
                    simulated_nodes[d].dependencies.append(u)

        for u, d in proposal.removed_edges:
            if d in simulated_nodes and u in simulated_nodes[d].dependencies:
                simulated_nodes[d].dependencies.remove(u)

        # Validate trial graph for dependencies and cycles
        try:
            trial_graph = TaskGraph(nodes=list(simulated_nodes.values()), graph_version=current_version + 1)
            trial_graph.validate()
        except TaskDependencyError as de:
            return False, f"Erro de dependência na proposta adaptativa: {de}", {}
        except TaskGraphCycleError as ce:
            return False, f"REJECTED_CYCLE_DETECTED: Ciclo detetado na proposta adaptativa: {ce}", {}
        except Exception as ge:
            return False, f"Erro estrutural no grafo proposto: {ge}", {}

        # 11. Preserved tasks calculation
        preserved_tasks = [
            tid for tid in current_graph.nodes.keys()
            if tid not in proposal.removed_tasks and tid in simulated_nodes
        ]

        payload = {
            "simulated_nodes": simulated_nodes,
            "added_task_ids": list(added_task_ids),
            "removed_task_ids": list(proposal.removed_tasks),
            "modified_task_ids": [m["task_id"] for m in proposal.modified_tasks if "task_id" in m],
            "preserved_task_ids": preserved_tasks,
            "strategy_fingerprint": fingerprint,
        }

        return True, "Proposta de adaptação validada com sucesso.", payload

    def validate_proposal(
        self,
        proposal: MissionAdaptationProposal,
        current_graph: TaskGraph,
        adaptation_history: list[dict[str, Any]] | None = None,
    ) -> tuple[bool, str, TaskGraph | None]:
        """Convenience method returning (is_valid, reason, trial_graph)."""
        valid, msg, payload = self.validate(proposal, current_graph, adaptation_history)
        if not valid:
            return False, msg, None
        nodes = list(payload.get("simulated_nodes", {}).values())
        trial_graph = TaskGraph(nodes=nodes, graph_version=current_graph.graph_version + 1)
        return True, msg, trial_graph

    def get_preserved_task_ids(
        self,
        proposal: MissionAdaptationProposal,
        current_graph: TaskGraph,
    ) -> list[str]:
        """Returns list of tasks in current_graph preserved (not removed) by the proposal."""
        return [
            tid for tid in current_graph.nodes.keys()
            if tid not in proposal.removed_tasks
        ]


# ── ADAPTIVE PLANNING ENGINE ─────────────────────────────────────────────────

class AdaptivePlanningEngine:
    """
    Deterministic engine for evaluating mission plans, validating adaptation proposals,
    managing adaptation budgets, preventing oscillation, and atomically applying updates.
    """

    def __init__(self, budget: AdaptationBudget | None = None) -> None:
        self.budget = budget or AdaptationBudget()
        self.validator = AdaptivePlanningValidator(budget=self.budget)
        self.metrics = PlanQualityMetrics()
        self._lock = asyncio.Lock()

    def compute_plan_quality_metrics(
        self,
        current_graph: TaskGraph,
        observations: list[Observation] | None = None,
    ) -> PlanQualityMetrics:
        """Computes current quality, progress, and severity metrics for the active graph."""
        obs = observations or []
        metrics = PlanQualityMetrics(
            initial_plan_valid=True,
            adapted_plan_valid=True,
            replan_valid=True,
            plan_efficiency=1.0,
            plan_churn_count=self.metrics.plan_churn_count,
            adaptations_count=self.metrics.adaptations_count,
            replans_count=self.metrics.replans_count,
            total_tasks=len(current_graph.nodes),
            completed_tasks=len(current_graph.get_completed_tasks()),
            failed_tasks=len(current_graph.get_failed_tasks()),
            blocked_tasks=len(current_graph.get_blocked_tasks()),
            unrecoverable_blockage=current_graph.has_unrecoverable_failures() or bool(len(current_graph.get_blocked_tasks()) > 0 and len(current_graph.get_completed_tasks()) + len(current_graph.get_failed_tasks()) == len(current_graph.nodes)),
            observation_severity_score=sum(
                3.0 if o.severity in {ObservationSeverity.HIGH, ObservationSeverity.CRITICAL} else (1.5 if o.severity == ObservationSeverity.MEDIUM else 0.5)
                for o in obs
            ),
        )
        return metrics

    def evaluate_plan(
        self,
        current_graph: TaskGraph,
        observations: list[Observation] | None = None,
        failure_info: FailureInfo | None = None,
        requirement_change: str | None = None,
        architecture_change: dict[str, Any] | None = None,
        adaptation_history: list[dict[str, Any]] | None = None,
    ) -> PlanEvaluationResult:
        """
        Explicitly evaluates whether the current plan remains optimal, viable, or needs adaptation/replan.
        """
        obs_list = list(observations or [])
        history = list(adaptation_history or [])

        # Check budget limits first
        total_adaptations = sum(1 for r in history if r.get("decision") == "ADAPT_PLAN")
        total_replans = sum(1 for r in history if r.get("decision") == "REPLAN")
        if total_adaptations >= self.budget.max_plan_adaptations and total_replans >= self.budget.max_replans:
            return PlanEvaluationResult(
                decision=PlanEvaluationDecision.BLOCK_MISSION,
                reason="Limite total de adaptações e replans da missão esgotado.",
                trigger=AdaptationTrigger.RESOURCE_CONSTRAINT,
                observations=obs_list,
                metrics=self.metrics,
            )
        if total_adaptations >= self.budget.max_plan_adaptations and not architecture_change:
            return PlanEvaluationResult(
                decision=PlanEvaluationDecision.BLOCK_MISSION,
                reason=f"Orçamento de adaptações esgotado ({total_adaptations}/{self.budget.max_plan_adaptations}).",
                trigger=AdaptationTrigger.RESOURCE_CONSTRAINT,
                observations=obs_list,
                metrics=self.metrics,
            )

        # 1. User Requirement Change
        if requirement_change:
            return PlanEvaluationResult(
                decision=PlanEvaluationDecision.ADAPT_PLAN,
                reason=f"Mudança de requisitos solicitada pelo utilizador: {requirement_change}",
                trigger=AdaptationTrigger.REQUIREMENT_CHANGE,
                observations=obs_list,
                affected_tasks=[],
                metrics=self.metrics,
            )

        # 2. Architecture Discovery
        if architecture_change:
            return PlanEvaluationResult(
                decision=PlanEvaluationDecision.REPLAN,
                reason=f"Descoberta arquitetural incompatível com premissas do plano: {architecture_change.get('summary', 'Alteração estrutural de arquitetura')}",
                trigger=AdaptationTrigger.ARCHITECTURE_DISCOVERY,
                observations=obs_list,
                affected_tasks=list(architecture_change.get("affected_tasks", [])),
                metrics=self.metrics,
            )

        # 3. High/Critical Severity Observations
        critical_obs = [o for o in obs_list if o.severity in {ObservationSeverity.HIGH, ObservationSeverity.CRITICAL}]
        if critical_obs:
            first_crit = critical_obs[0]
            affected = [o.task_id for o in critical_obs if o.task_id]
            # If multiple tasks or critical system failure, evaluate REPLAN vs ADAPT_PLAN
            if len(affected) > 2 or "impossible" in first_crit.event.lower() or "unsupported" in first_crit.event.lower():
                return PlanEvaluationResult(
                    decision=PlanEvaluationDecision.REPLAN,
                    reason=f"Premissa global do plano invalidada por observação crítica: {first_crit.event}",
                    trigger=AdaptationTrigger.RUNTIME_FAILURE,
                    observations=obs_list,
                    affected_tasks=affected,
                    metrics=self.metrics,
                )
            else:
                return PlanEvaluationResult(
                    decision=PlanEvaluationDecision.ADAPT_PLAN,
                    reason=f"Falha localizada exige alteração de ramo no plano: {first_crit.event}",
                    trigger=AdaptationTrigger.VALIDATION_FAILURE,
                    observations=obs_list,
                    affected_tasks=affected,
                    metrics=self.metrics,
                )

        # 4. Failure Info Inspection
        if failure_info and failure_info.category != FailureCategory.NONE:
            cat = failure_info.category
            if cat == FailureCategory.POLICY_BLOCK:
                return PlanEvaluationResult(
                    decision=PlanEvaluationDecision.BLOCK_MISSION,
                    reason=f"Bloqueio de política não recuperável: {failure_info.message}",
                    trigger=AdaptationTrigger.TASK_BLOCKED,
                    observations=obs_list,
                    metrics=self.metrics,
                )
            elif cat in {FailureCategory.PERMANENT_FAILURE, FailureCategory.VALIDATION_FAILURE, FailureCategory.DEPENDENCY_FAILURE, FailureCategory.TIMEOUT}:
                failed_task_ids = [n.task_id for n in current_graph.get_failed_tasks()]
                return PlanEvaluationResult(
                    decision=PlanEvaluationDecision.ADAPT_PLAN,
                    reason=f"Falha permanente requer adaptação do plano: {failure_info.message}",
                    trigger=AdaptationTrigger.RUNTIME_FAILURE if cat == FailureCategory.PERMANENT_FAILURE else AdaptationTrigger.VALIDATION_FAILURE,
                    observations=obs_list,
                    affected_tasks=failed_task_ids or ["task_failed"],
                    metrics=self.metrics,
                )

        # 5. Check if graph has blocked tasks without active running tasks
        blocked_nodes = current_graph.get_blocked_tasks()
        running_nodes = [n for n in current_graph.nodes.values() if n.status == TaskStatus.RUNNING]
        ready_nodes = current_graph.get_ready_tasks()

        if blocked_nodes and not running_nodes and not ready_nodes and not current_graph.is_all_completed():
            # Deadlock / Blocked branch
            return PlanEvaluationResult(
                decision=PlanEvaluationDecision.ADAPT_PLAN,
                reason="Tarefas bloqueadas por dependências sem tarefas elegíveis para desbloqueio.",
                trigger=AdaptationTrigger.TASK_BLOCKED,
                observations=obs_list,
                affected_tasks=[n.task_id for n in blocked_nodes],
                metrics=self.metrics,
            )

        # Default: Plan remains valid and execution continues
        return PlanEvaluationResult(
            decision=PlanEvaluationDecision.KEEP_PLAN,
            reason="O plano atual continua válido e alinhado com as observações e premissas.",
            trigger=AdaptationTrigger.RUNTIME_FAILURE,
            observations=obs_list,
            affected_tasks=[],
            metrics=self.metrics,
        )

    async def apply_adaptation(
        self,
        proposal: MissionAdaptationProposal,
        orchestrator: Any,
    ) -> tuple[bool, str, AdaptationRecord | None]:
        """
        Applies an adaptation proposal atomically (All-or-Nothing) to the orchestrator's TaskGraph
        and persists the transaction in the MissionStateStore.
        """
        async with self._lock:
            proposal.status = AdaptationStatus.VALIDATING
            current_graph: TaskGraph = orchestrator.task_graph
            current_version = getattr(current_graph, "graph_version", 1)

            # Load history
            history = await asyncio.to_thread(
                orchestrator.mission_state.load_adaptation_history,
                orchestrator.project_id,
                orchestrator.mission_id,
            )

            # 1. Strict Validation against current graph and history
            is_valid, msg, payload = self.validator.validate(proposal, current_graph, history)
            if not is_valid:
                proposal.status = AdaptationStatus.REJECTED
                proposal.rejection_reason = msg
                log_event(
                    logger,
                    "adaptive_planning.proposal_rejected",
                    proposal_id=proposal.proposal_id,
                    reason=msg,
                )
                return False, msg, None

            # 2. ATOMIC COMMIT (All-or-Nothing)
            new_version = current_version + 1
            simulated_nodes: dict[str, TaskNode] = payload["simulated_nodes"]
            added_task_ids: list[str] = payload["added_task_ids"]
            removed_task_ids: list[str] = payload["removed_task_ids"]
            modified_task_ids: list[str] = payload["modified_task_ids"]
            preserved_task_ids: list[str] = payload["preserved_task_ids"]
            strategy_fp: str = payload["strategy_fingerprint"]

            adaptation_id = f"adapt_{uuid.uuid4().hex[:8]}"
            record = AdaptationRecord(
                adaptation_id=adaptation_id,
                proposal_id=proposal.proposal_id,
                mission_id=proposal.mission_id,
                graph_version_before=current_version,
                graph_version_after=new_version,
                decision=proposal.decision,
                trigger=proposal.trigger,
                reason=proposal.reason,
                tasks_added=added_task_ids,
                tasks_removed=removed_task_ids,
                tasks_modified=modified_task_ids,
                tasks_preserved=preserved_task_ids,
                edges_added=[list(e) for e in proposal.changed_edges],
                edges_removed=[list(e) for e in proposal.removed_edges],
                evidence_ids=list(proposal.evidence_ids),
                strategy_fingerprint=strategy_fp,
            )

            try:
                # Update TaskGraph in memory
                new_graph = TaskGraph(nodes=list(simulated_nodes.values()), graph_version=new_version)
                new_graph.expansion_history = list(current_graph.expansion_history)
                orchestrator.task_graph = new_graph

                # Update mission state store
                await asyncio.to_thread(
                    self._persist_adaptation_to_store,
                    orchestrator.mission_state,
                    orchestrator.project_id,
                    orchestrator.mission_id,
                    proposal,
                    record,
                    new_version,
                    simulated_nodes,
                )

                # Update metrics
                self.metrics.plan_churn_count += (len(added_task_ids) + len(removed_task_ids))
                decision_val = proposal.decision.value if isinstance(proposal.decision, PlanEvaluationDecision) else str(proposal.decision)
                if decision_val == "REPLAN":
                    self.metrics.replans_count += 1
                else:
                    self.metrics.adaptations_count += 1

                proposal.status = AdaptationStatus.APPLIED

                # Save sequential checkpoint
                orchestrator.save_checkpoint(
                    f"Adaptação aplicada ({decision_val}): {proposal.reason} (DAG v{new_version})"
                )

                log_event(
                    logger,
                    "adaptive_planning.adaptation_applied",
                    proposal_id=proposal.proposal_id,
                    new_version=new_version,
                    decision=decision_val,
                    tasks_added=len(added_task_ids),
                    tasks_removed=len(removed_task_ids),
                )

                return True, f"Plano adaptado com sucesso. Grafo atualizado para v{new_version}.", record

            except Exception as apply_err:
                # ROLLBACK TO PREVIOUS GRAPH
                orchestrator.task_graph = current_graph
                proposal.status = AdaptationStatus.FAILED
                proposal.rejection_reason = f"ROLLBACK: Falha na aplicação atómica: {apply_err}"
                log_event(
                    logger,
                    "adaptive_planning.apply_rollback",
                    proposal_id=proposal.proposal_id,
                    error=str(apply_err),
                )
                return False, proposal.rejection_reason, None

    def _persist_adaptation_to_store(
        self,
        store: MissionStateStore,
        project_id: str,
        mission_id: str,
        proposal: MissionAdaptationProposal,
        record: AdaptationRecord,
        new_version: int,
        simulated_nodes: dict[str, TaskNode] | None = None,
    ) -> None:
        """Persists adaptation record, work packages, and metadata updates into MissionStateStore."""
        # 1. Update metadata
        current_data = store.load_mission(project_id, mission_id)
        current_meta = dict(current_data.get("mission", {}).get("metadata", {}))
        current_meta["graph_version"] = new_version
        current_meta["plan_churn_count"] = self.metrics.plan_churn_count
        current_meta["last_strategy_fingerprint"] = record.strategy_fingerprint
        current_meta["plan_version"] = int(current_meta.get("plan_version", 1)) + 1

        store.update_mission_metadata(project_id, mission_id, current_meta)

        # 2. Add or sync work packages from simulated_nodes
        nodes_to_sync = simulated_nodes or {}
        for nid, node in nodes_to_sync.items():
            wp_path = store._entity_path(project_id, mission_id, "work_packages", nid)
            status_str = node.status.value if hasattr(node.status, "value") else str(node.status)
            valid_status = status_str if status_str in WORK_PACKAGE_STATUSES else "PENDING"
            has_wp = store.has_work_package(project_id, mission_id, nid) if hasattr(store, "has_work_package") else os.path.exists(wp_path)
            now = utc_now()
            if not has_wp:
                wp_item = WorkPackage(
                    work_package_id=nid,
                    mission_id=mission_id,
                    title=node.title,
                    description=node.description or node.title,
                    type="CODING" if node.category == "CODING" else "GENERIC",
                    priority=int(node.priority),
                    dependencies=list(node.dependencies),
                    status=valid_status,
                    required=bool(node.required),
                    created_at=now,
                    updated_at=now,
                )
                store._write_entity(wp_path, wp_item)
            else:
                try:
                    wp = store.load_work_package(project_id, mission_id, nid)
                    if wp.get("status") != valid_status:
                        store.set_work_package_status(
                            project_id=project_id,
                            mission_id=mission_id,
                            work_package_id=nid,
                            status=valid_status,
                            expected_version=wp.get("version", 1),
                        )
                except Exception:
                    pass

        # 3. Mark removed tasks as CANCELLED in store
        for r_id in proposal.removed_tasks:
            wp_path = store._entity_path(project_id, mission_id, "work_packages", r_id)
            if os.path.exists(wp_path):
                try:
                    wp = store.load_work_package(project_id, mission_id, r_id)
                    if wp.get("status") != "CANCELLED":
                        store.set_work_package_status(
                            project_id=project_id,
                            mission_id=mission_id,
                            work_package_id=r_id,
                            status="CANCELLED",
                            expected_version=wp.get("version", 1),
                            blocked_reason=f"Obsoleta por adaptação ({proposal.reason})",
                        )
                except Exception:
                    pass

        # 4. Save adaptation record to disk
        store.record_adaptation(project_id, mission_id, record.to_dict())
