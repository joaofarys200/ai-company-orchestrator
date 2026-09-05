"""
JARVIS OS — Phase 14: Hierarchical Task Distribution & Multi-Agent Swarm Execution
Core Swarm Coordinator, Agent Registry, Leases, Quotas, Scheduling & Result Validation.
"""

from __future__ import annotations

import asyncio
import enum
import heapq
import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Sequence

from agents.mission_state import MissionStateStore, utc_now
from agents.task_graph import FailureCategory, FailureInfo, TaskGraph, TaskNode, TaskStatus
from backend.logging_config import get_logger, log_event

logger = get_logger(__name__)


# ── ENUMS ──────────────────────────────────────────────────────────────────────

class AgentCategory(str, enum.Enum):
    ARCHITECTURE = "ARCHITECTURE"
    RESEARCH = "RESEARCH"
    CODING = "CODING"
    TESTING = "TESTING"
    BROWSER = "BROWSER"
    SECURITY = "SECURITY"
    REVIEW = "REVIEW"
    BUILD = "BUILD"
    DATABASE = "DATABASE"
    DOCUMENTATION = "DOCUMENTATION"
    GENERAL = "GENERAL"


class ResourceClass(str, enum.Enum):
    CPU = "CPU"
    IO = "IO"
    MEMORY = "MEMORY"
    GPU = "GPU"
    BROWSER = "BROWSER"
    NETWORK = "NETWORK"


class AgentHealthStatus(str, enum.Enum):
    ONLINE = "ONLINE"
    BUSY = "BUSY"
    IDLE = "IDLE"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    OFFLINE = "OFFLINE"


class ResultStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    PARTIAL = "PARTIAL"
    TIMEOUT = "TIMEOUT"
    INTERRUPTED = "INTERRUPTED"


class FailureType(str, enum.Enum):
    AGENT_CRASH = "AGENT_CRASH"
    AGENT_TIMEOUT = "AGENT_TIMEOUT"
    AGENT_UNHEALTHY = "AGENT_UNHEALTHY"
    TOOL_FAILURE = "TOOL_FAILURE"
    PERMISSION_FAILURE = "PERMISSION_FAILURE"
    INVALID_RESULT = "INVALID_RESULT"
    TASK_FAILURE = "TASK_FAILURE"


# ── DATACLASSES ────────────────────────────────────────────────────────────────

@dataclass
class AgentCapability:
    agent_type: str
    categories: list[AgentCategory] = field(default_factory=list)
    supported_task_types: list[str] = field(default_factory=list)
    required_tools: list[str] = field(default_factory=list)
    required_permissions: list[str] = field(default_factory=list)
    concurrency_limit: int = 2
    resource_classes: list[ResourceClass] = field(default_factory=list)
    availability: bool = True

    def __post_init__(self):
        if not self.categories:
            cat_upper = str(self.agent_type).upper()
            if cat_upper in AgentCategory._value2member_map_:
                self.categories = [AgentCategory(cat_upper)]
            elif cat_upper in AgentCategory.__members__:
                self.categories = [AgentCategory[cat_upper]]
            else:
                self.categories = [AgentCategory.GENERAL]

    def matches_task(self, task: TaskNode) -> bool:
        task_cat_str = str(task.category).upper()
        # Direct category match
        for cat in self.categories:
            if cat.value == task_cat_str or cat.name == task_cat_str:
                return True
        # Supported task types match
        if task_cat_str in [t.upper() for t in self.supported_task_types]:
            return True
        # Generalist fallback
        if AgentCategory.GENERAL in self.categories:
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_type": self.agent_type,
            "categories": [c.value for c in self.categories],
            "supported_task_types": list(self.supported_task_types),
            "required_tools": list(self.required_tools),
            "required_permissions": list(self.required_permissions),
            "concurrency_limit": self.concurrency_limit,
            "resource_classes": [r.value for r in self.resource_classes],
            "availability": self.availability,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentCapability:
        categories = [
            AgentCategory(c) if c in AgentCategory._value2member_map_ else AgentCategory.GENERAL
            for c in data.get("categories", [])
        ]
        resources = [
            ResourceClass(r) if r in ResourceClass._value2member_map_ else ResourceClass.CPU
            for r in data.get("resource_classes", [])
        ]
        return cls(
            agent_type=data.get("agent_type", "GENERAL"),
            categories=categories,
            supported_task_types=list(data.get("supported_task_types", [])),
            required_tools=list(data.get("required_tools", [])),
            required_permissions=list(data.get("required_permissions", [])),
            concurrency_limit=int(data.get("concurrency_limit", 2)),
            resource_classes=resources,
            availability=bool(data.get("availability", True)),
        )


@dataclass
class AgentInstance:
    agent_id: str
    agent_type: str
    capability: AgentCapability
    status: AgentHealthStatus = AgentHealthStatus.IDLE
    current_tasks: set[str] = field(default_factory=set)
    last_heartbeat: float = field(default_factory=time.time)
    heartbeat_timeout_seconds: float = 10.0
    failure_count: int = 0
    success_count: int = 0
    total_execution_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_available(self) -> bool:
        if not self.capability.availability:
            return False
        if self.status in {AgentHealthStatus.OFFLINE, AgentHealthStatus.UNHEALTHY}:
            return False
        return len(self.current_tasks) < self.capability.concurrency_limit

    def record_heartbeat(self, now: float | None = None) -> None:
        self.last_heartbeat = now if now is not None else time.time()
        if self.status == AgentHealthStatus.UNHEALTHY:
            self.status = AgentHealthStatus.BUSY if self.current_tasks else AgentHealthStatus.IDLE

    def check_health(self, now: float | None = None) -> AgentHealthStatus:
        curr_time = now if now is not None else time.time()
        if curr_time - self.last_heartbeat > self.heartbeat_timeout_seconds:
            self.status = AgentHealthStatus.UNHEALTHY
        return self.status

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "capability": self.capability.to_dict(),
            "status": self.status.value,
            "current_tasks": list(self.current_tasks),
            "last_heartbeat": self.last_heartbeat,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_execution_time_ms": self.total_execution_time_ms,
            "is_available": self.is_available,
        }


@dataclass
class TaskLease:
    lease_id: str
    task_id: str
    agent_id: str
    attempt_id: int
    acquired_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 15.0)
    last_heartbeat: float = field(default_factory=time.time)
    heartbeat_interval_seconds: float = 2.0
    ttl_seconds: float = 15.0

    def is_valid(self, now: float | None = None) -> bool:
        curr = now if now is not None else time.time()
        return curr < self.expires_at

    def renew(self, extension_seconds: float | None = None, now: float | None = None) -> None:
        curr = now if now is not None else time.time()
        ext = extension_seconds if extension_seconds is not None else self.ttl_seconds
        self.last_heartbeat = curr
        self.expires_at = curr + ext

    def to_dict(self) -> dict[str, Any]:
        return {
            "lease_id": self.lease_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "attempt_id": self.attempt_id,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
            "last_heartbeat": self.last_heartbeat,
            "ttl_seconds": self.ttl_seconds,
            "is_valid": self.is_valid(),
        }


@dataclass
class AgentSelectionRecord:
    task_id: str
    agent_id: str
    agent_type: str
    selection_reason: str
    selection_score: float
    timestamp: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentResult:
    task_id: str
    attempt_id: int
    agent_id: str
    result_id: str = field(default_factory=lambda: f"res_{uuid.uuid4().hex[:8]}")
    status: ResultStatus = ResultStatus.SUCCESS
    output: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    failure: dict[str, Any] | None = None
    produced_artifacts: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=utc_now)

    @property
    def is_success(self) -> bool:
        return self.status == ResultStatus.SUCCESS

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "attempt_id": self.attempt_id,
            "agent_id": self.agent_id,
            "result_id": self.result_id,
            "status": self.status.value if isinstance(self.status, ResultStatus) else str(self.status),
            "output": self.output,
            "evidence": list(self.evidence),
            "metrics": self.metrics,
            "failure": self.failure,
            "produced_artifacts": list(self.produced_artifacts),
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentResult:
        st = data.get("status", "SUCCESS")
        status_val = ResultStatus(st) if st in ResultStatus._value2member_map_ else ResultStatus.FAILURE
        return cls(
            task_id=data["task_id"],
            attempt_id=int(data.get("attempt_id", 1)),
            agent_id=data.get("agent_id", ""),
            result_id=data.get("result_id", f"res_{uuid.uuid4().hex[:8]}"),
            status=status_val,
            output=data.get("output", {}),
            evidence=list(data.get("evidence", [])),
            metrics=data.get("metrics", {}),
            failure=data.get("failure"),
            produced_artifacts=list(data.get("produced_artifacts", [])),
            timestamp=data.get("timestamp", utc_now()),
        )


@dataclass
class SwarmMetrics:
    total_dispatched_tasks: int = 0
    total_completed_tasks: int = 0
    total_failed_tasks: int = 0
    total_reassigned_tasks: int = 0
    total_expired_leases: int = 0
    total_agent_churn: int = 0
    makespan_seconds: float = 0.0
    sequential_estimate_seconds: float = 0.0
    parallel_speedup: float = 1.0
    average_queue_latency_ms: float = 0.0
    scheduler_overhead_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── AGENT REGISTRY ─────────────────────────────────────────────────────────────

class AgentRegistry:
    """Maintains active agent instances, tracking capability, load, and health."""

    def __init__(self):
        self._agents: dict[str, AgentInstance] = {}

    def register(self, agent: AgentInstance) -> None:
        self._agents[agent.agent_id] = agent
        logger.info("Registered swarm agent: %s (%s)", agent.agent_id, agent.agent_type)

    def unregister(self, agent_id: str) -> None:
        if agent_id in self._agents:
            del self._agents[agent_id]

    def get(self, agent_id: str) -> AgentInstance | None:
        return self._agents.get(agent_id)

    def list_agents(self) -> list[AgentInstance]:
        return list(self._agents.values())

    def get_available_agents(self, category: str | None = None) -> list[AgentInstance]:
        available = []
        for agent in self._agents.values():
            if agent.is_available:
                if category is None or category.upper() in [
                    c.value for c in agent.capability.categories
                ] or category.upper() in [
                    t.upper() for t in agent.capability.supported_task_types
                ] or AgentCategory.GENERAL in agent.capability.categories:
                    available.append(agent)
        return available

    def check_all_health(self, now: float | None = None) -> list[str]:
        """Checks heartbeat timeouts and returns list of newly unhealthy agents."""
        unhealthy = []
        for agent in self._agents.values():
            prev = agent.status
            curr = agent.check_health(now)
            if curr == AgentHealthStatus.UNHEALTHY and prev != AgentHealthStatus.UNHEALTHY:
                unhealthy.append(agent.agent_id)
        return unhealthy


# ── LEASE MANAGER ──────────────────────────────────────────────────────────────

class LeaseManager:
    """Issues, checks, renews, and reaps exclusive task leases to prevent double ownership."""

    def __init__(self):
        self._leases_by_task: dict[str, TaskLease] = {}
        self._leases_by_id: dict[str, TaskLease] = {}

    def acquire_lease(
        self,
        task_id: str,
        agent_id: str,
        attempt_id: int,
        ttl_seconds: float = 15.0,
        now: float | None = None,
    ) -> TaskLease:
        curr = now if now is not None else time.time()
        existing = self._leases_by_task.get(task_id)
        if existing and existing.is_valid(curr):
            if existing.agent_id != agent_id:
                raise ValueError(
                    f"Task {task_id} is already leased exclusively to {existing.agent_id} "
                    f"until {existing.expires_at:.1f} (lease: {existing.lease_id})"
                )

        lease_id = f"lease_{task_id}_{agent_id}_{uuid.uuid4().hex[:6]}"
        lease = TaskLease(
            lease_id=lease_id,
            task_id=task_id,
            agent_id=agent_id,
            attempt_id=attempt_id,
            acquired_at=curr,
            expires_at=curr + ttl_seconds,
            last_heartbeat=curr,
            ttl_seconds=ttl_seconds,
        )
        self._leases_by_task[task_id] = lease
        self._leases_by_id[lease_id] = lease
        return lease

    def get_lease(self, lease_id: str) -> TaskLease | None:
        return self._leases_by_id.get(lease_id)

    def get_active_lease_for_task(self, task_id: str, now: float | None = None) -> TaskLease | None:
        lease = self._leases_by_task.get(task_id)
        if lease and lease.is_valid(now):
            return lease
        return None

    def renew_lease(self, lease_id: str, agent_id: str, now: float | None = None) -> bool:
        lease = self._leases_by_id.get(lease_id)
        if not lease:
            return False
        if lease.agent_id != agent_id:
            return False
        lease.renew(now=now)
        return True

    def release_lease(self, lease_id: str, agent_id: str) -> bool:
        lease = self._leases_by_id.get(lease_id)
        if not lease:
            return False
        if lease.agent_id != agent_id:
            return False
        if lease.task_id in self._leases_by_task:
            del self._leases_by_task[lease.task_id]
        del self._leases_by_id[lease_id]
        return True

    def reap_expired_leases(self, now: float | None = None) -> list[TaskLease]:
        curr = now if now is not None else time.time()
        expired: list[TaskLease] = []
        for task_id, lease in list(self._leases_by_task.items()):
            if not lease.is_valid(curr):
                expired.append(lease)
                del self._leases_by_task[task_id]
                self._leases_by_id.pop(lease.lease_id, None)
        return expired


# ── HIERARCHICAL QUOTA & RESOURCE MANAGER ──────────────────────────────────────

class HierarchicalQuotaManager:
    """Enforces global, category, and agent-level quotas and resource class allocations."""

    def __init__(
        self,
        global_max_concurrency: int = 8,
        category_limits: dict[str, int] | None = None,
        available_resources: dict[str, int] | None = None,
    ):
        self.global_max_concurrency = max(1, global_max_concurrency)
        self.category_limits = category_limits or {
            "CODING": 2,
            "BROWSER": 1,
            "TESTING": 2,
            "RESEARCH": 3,
            "ARCHITECTURE": 2,
            "REVIEW": 2,
            "GENERAL": 4,
        }
        self.available_resources = available_resources or {
            "CPU": 8,
            "MEMORY": 8,
            "BROWSER": 2,
            "GPU": 1,
            "IO": 8,
            "NETWORK": 8,
        }
        self.active_tasks: dict[str, dict[str, Any]] = {}
        self.allocated_resources: dict[str, int] = {r: 0 for r in self.available_resources}

    def can_dispatch(
        self,
        agent: AgentInstance,
        task: TaskNode,
        resource_requirements: dict[str, int] | None = None,
    ) -> tuple[bool, str]:
        # 1. Global limit
        if len(self.active_tasks) >= self.global_max_concurrency:
            return False, f"Global concurrency limit reached ({self.global_max_concurrency})"

        # 2. Agent concurrency limit
        if len(agent.current_tasks) >= agent.capability.concurrency_limit:
            return False, f"Agent {agent.agent_id} at max concurrency ({agent.capability.concurrency_limit})"

        # 3. Category quota
        cat = str(task.category).upper()
        current_cat_count = sum(
            1 for item in self.active_tasks.values()
            if item.get("category", "").upper() == cat
        )
        cat_limit = self.category_limits.get(cat, self.category_limits.get("GENERAL", 4))
        if current_cat_count >= cat_limit:
            return False, f"Category quota '{cat}' reached ({cat_limit})"

        # 4. Resource requirements
        reqs = resource_requirements or task.metadata.get("resource_requirements", {})
        for res_name, amount in reqs.items():
            avail = self.available_resources.get(res_name, 0)
            alloc = self.allocated_resources.get(res_name, 0)
            if alloc + amount > avail:
                return False, f"Insufficient resource '{res_name}': requested {amount}, available {avail - alloc}"

        return True, "Allowed"

    def allocate(
        self,
        task_id: str,
        agent_id: str,
        category: str,
        resource_requirements: dict[str, int] | None = None,
    ) -> None:
        reqs = resource_requirements or {}
        self.active_tasks[task_id] = {
            "agent_id": agent_id,
            "category": category,
            "resources": reqs,
        }
        for res_name, amount in reqs.items():
            self.allocated_resources[res_name] = self.allocated_resources.get(res_name, 0) + amount

    def release(self, task_id: str) -> None:
        task_info = self.active_tasks.pop(task_id, None)
        if task_info:
            reqs = task_info.get("resources", {})
            for res_name, amount in reqs.items():
                self.allocated_resources[res_name] = max(0, self.allocated_resources.get(res_name, 0) - amount)


# ── SHARED WORKSPACE & FILE OWNERSHIP REGISTRY ──────────────────────────────────

class FileOwnershipRegistry:
    """Prevents file writing collisions across concurrent tasks by tracking path ownership."""

    def __init__(self):
        self._claimed_paths: dict[str, str] = {}  # normalized path -> task_id

    def acquire_paths(
        self,
        task_id: str,
        agent_id: str,
        paths: list[str],
    ) -> tuple[bool, str | None]:
        if not paths:
            return True, None

        normalized = [self._normalize_path(p) for p in paths]

        # Check for direct or ancestor/descendant overlap
        for norm_p in normalized:
            for claimed_p, holder_task in self._claimed_paths.items():
                if holder_task != task_id:
                    if norm_p == claimed_p or norm_p.startswith(claimed_p + "/") or claimed_p.startswith(norm_p + "/"):
                        return False, (
                            f"CONFLICT_DETECTED: Path '{norm_p}' conflicts with path '{claimed_p}' "
                            f"currently owned by task '{holder_task}'"
                        )

        # Claim all paths
        for norm_p in normalized:
            self._claimed_paths[norm_p] = task_id
        return True, None

    def release_paths(self, task_id: str) -> None:
        for p in [path for path, t_id in self._claimed_paths.items() if t_id == task_id]:
            del self._claimed_paths[p]

    def _normalize_path(self, path: str) -> str:
        return os.path.normpath(path).replace("\\", "/").rstrip("/")


# ── DETERMINISTIC AGENT SELECTOR ───────────────────────────────────────────────

class AgentSelector:
    """Computes deterministic candidate ranking and picks best agent for task."""

    @staticmethod
    def score_agent(agent: AgentInstance, task: TaskNode) -> tuple[float, str]:
        if not agent.is_available:
            return -1.0, "Unavailable"
        if not agent.capability.matches_task(task):
            return -1.0, "Capability mismatch"

        score = 100.0
        task_cat_str = str(task.category).upper()

        # Primary agent_type exact match bonus (+100 for primary specialist)
        if agent.agent_type.upper() == task_cat_str:
            score += 100.0

        # Category capability match bonus
        for cat in agent.capability.categories:
            if cat.value == task_cat_str or cat.name == task_cat_str:
                score += 50.0
                break

        # Priority weight
        score += float(task.priority) * 10.0

        # Idle bonus
        if len(agent.current_tasks) == 0:
            score += 30.0
        else:
            score -= len(agent.current_tasks) * 20.0

        # Reliability (past successes vs failures)
        score += min(20.0, agent.success_count * 2.0)
        score -= min(40.0, agent.failure_count * 10.0)

        reason = (
            f"score={score:.1f} (cat_match={task_cat_str}, load={len(agent.current_tasks)}, "
            f"successes={agent.success_count}, failures={agent.failure_count})"
        )
        return score, reason

    def select_agent(
        self,
        task: TaskNode,
        registry: AgentRegistry,
        quotas: HierarchicalQuotaManager,
    ) -> AgentSelectionRecord | None:
        candidates = registry.get_available_agents(str(task.category))
        if not candidates:
            # Fallback: any available agent that matches
            candidates = [a for a in registry.list_agents() if a.is_available and a.capability.matches_task(task)]

        scored: list[tuple[float, str, AgentInstance, str]] = []
        for agent in candidates:
            can_run, q_reason = quotas.can_dispatch(agent, task)
            if not can_run:
                continue
            sc, reason = self.score_agent(agent, task)
            if sc >= 0.0:
                # Tuple for sorting: (-score, agent_id) for deterministic tie-breaking
                scored.append((sc, agent.agent_id, agent, reason))

        if not scored:
            return None

        # Sort descending by score, ascending by agent_id for stable tie-breaking
        scored.sort(key=lambda item: (-item[0], item[1]))
        best_score, best_id, best_agent, best_reason = scored[0]

        return AgentSelectionRecord(
            task_id=task.task_id,
            agent_id=best_agent.agent_id,
            agent_type=best_agent.agent_type,
            selection_reason=best_reason,
            selection_score=best_score,
            timestamp=utc_now(),
        )


# ── TASK SCHEDULER & FAIRNESS ──────────────────────────────────────────────────

class TaskScheduler:
    """Discovers ready tasks with priority aging and deterministic fairness across DAG branches."""

    def __init__(self):
        self._task_ready_times: dict[str, float] = {}

    def record_ready(self, task_id: str, now: float | None = None) -> None:
        if task_id not in self._task_ready_times:
            self._task_ready_times[task_id] = now if now is not None else time.time()

    def record_dispatched(self, task_id: str) -> None:
        self._task_ready_times.pop(task_id, None)

    def order_ready_tasks(self, ready_tasks: Sequence[TaskNode], now: float | None = None) -> list[TaskNode]:
        curr = now if now is not None else time.time()
        scored: list[tuple[float, str, TaskNode]] = []

        for task in ready_tasks:
            self.record_ready(task.task_id, curr)
            ready_since = self._task_ready_times.get(task.task_id, curr)
            wait_seconds = max(0.0, curr - ready_since)

            # Priority Aging: +2.0 priority per second waiting (capped at 50.0)
            aging_bonus = min(50.0, wait_seconds * 2.0)
            effective_priority = float(task.priority) + aging_bonus

            # Tie-break key: -effective_priority, task_id
            scored.append((-effective_priority, task.task_id, task))

        scored.sort(key=lambda item: (item[0], item[1]))
        return [item[2] for item in scored]


# ── RESULT VALIDATOR & IDEMPOTENCY CACHE ───────────────────────────────────────

class ResultValidator:
    """Validates AgentResult contracts and enforces deduplication / idempotency."""

    def __init__(self):
        self._processed_results: dict[str, AgentResult] = {}  # idempotency key -> AgentResult

    def make_idempotency_key(self, task_id: str, attempt_id: int, result_id: str) -> str:
        return f"{task_id}::{attempt_id}::{result_id}"

    def is_duplicate(self, result: AgentResult) -> bool:
        key = self.make_idempotency_key(result.task_id, result.attempt_id, result.result_id)
        return key in self._processed_results

    def validate_and_record(self, result: AgentResult) -> tuple[bool, str]:
        # 1. Structural checks
        if not result.task_id:
            return False, "AgentResult missing task_id"
        if not result.agent_id:
            return False, "AgentResult missing agent_id"
        if result.attempt_id < 1:
            return False, "AgentResult attempt_id must be >= 1"

        key = self.make_idempotency_key(result.task_id, result.attempt_id, result.result_id)
        if key in self._processed_results:
            return True, "DUPLICATE_IGNORED: Result was already accepted and processed."

        self._processed_results[key] = result
        return True, "VALID"


# ── SWARM COORDINATOR ──────────────────────────────────────────────────────────

class SwarmCoordinator:
    """Central deterministic coordinator governing swarm lifecycle, scheduling, leases, and failover."""

    def __init__(
        self,
        *,
        project_id: str,
        mission_id: str,
        mission_state: MissionStateStore,
        task_graph: TaskGraph,
        global_max_concurrency: int = 8,
        category_limits: dict[str, int] | None = None,
        callbacks: Any = None,
    ):
        self.project_id = project_id
        self.mission_id = mission_id
        self.mission_state = mission_state
        self.task_graph = task_graph
        self.callbacks = callbacks

        self.registry = AgentRegistry()
        self.lease_manager = LeaseManager()
        self.quotas = HierarchicalQuotaManager(
            global_max_concurrency=global_max_concurrency,
            category_limits=category_limits,
        )
        self.file_ownership = FileOwnershipRegistry()
        self.selector = AgentSelector()
        self.scheduler = TaskScheduler()
        self.validator = ResultValidator()

        # State tracking
        self.active_leases: dict[str, TaskLease] = {}  # task_id -> TaskLease
        self.task_attempts: dict[str, list[dict[str, Any]]] = {}  # task_id -> history
        self.metrics = SwarmMetrics()
        self._running_futures: dict[str, asyncio.Task] = {}
        self._start_time: float = 0.0
        self._is_paused: bool = False
        self._is_cancelled: bool = False

    def register_agent(self, agent: AgentInstance) -> None:
        self.registry.register(agent)

    async def emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        if self.callbacks and hasattr(self.callbacks, "emit"):
            try:
                res = self.callbacks.emit(event_type, data)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.warning("Error emitting swarm event '%s': %s", event_type, e)

    def select_agent_for_task(self, task: TaskNode) -> AgentSelectionRecord | None:
        return self.selector.select_agent(task, self.registry, self.quotas)

    def acquire_task_lease(self, task: TaskNode, agent: AgentInstance) -> TaskLease:
        attempt = task.attempt_count + 1
        lease = self.lease_manager.acquire_lease(
            task_id=task.task_id,
            agent_id=agent.agent_id,
            attempt_id=attempt,
            ttl_seconds=max(15.0, task.timeout_seconds + 5.0),
        )
        self.active_leases[task.task_id] = lease
        agent.current_tasks.add(task.task_id)
        agent.status = AgentHealthStatus.BUSY

        # Allocate quotas and file ownership
        paths = task.metadata.get("path_scope") or task.metadata.get("owned_paths") or []
        if paths:
            ok, err = self.file_ownership.acquire_paths(task.task_id, agent.agent_id, paths)
            if not ok:
                # Rollback lease if file conflict
                self.lease_manager.release_lease(lease.lease_id, agent.agent_id)
                self.active_leases.pop(task.task_id, None)
                agent.current_tasks.discard(task.task_id)
                agent.status = AgentHealthStatus.IDLE if not agent.current_tasks else AgentHealthStatus.BUSY
                raise ValueError(err or "File ownership conflict detected")

        self.quotas.allocate(task.task_id, agent.agent_id, str(task.category))
        self.scheduler.record_dispatched(task.task_id)
        return lease

    def release_task_lease(self, task_id: str, agent_id: str, lease_id: str) -> None:
        self.lease_manager.release_lease(lease_id, agent_id)
        self.active_leases.pop(task_id, None)
        self.file_ownership.release_paths(task_id)
        self.quotas.release(task_id)

        agent = self.registry.get(agent_id)
        if agent:
            agent.current_tasks.discard(task_id)
            if not agent.current_tasks and agent.status == AgentHealthStatus.BUSY:
                agent.status = AgentHealthStatus.IDLE

    def record_heartbeat(self, lease_id: str, agent_id: str) -> bool:
        agent = self.registry.get(agent_id)
        if agent:
            agent.record_heartbeat()
        return self.lease_manager.renew_lease(lease_id, agent_id)

    async def handle_agent_result(self, result: AgentResult) -> tuple[bool, str]:
        """Validates agent result, updates attempt history, and advances task state."""
        valid, msg = self.validator.validate_and_record(result)
        if not valid:
            return False, f"Invalid AgentResult: {msg}"
        if "DUPLICATE_IGNORED" in msg:
            return True, msg

        task = self.task_graph.get_node(result.task_id)
        if not task:
            return False, f"Task '{result.task_id}' not found in task graph"

        # Record attempt history
        attempt_record = {
            "attempt": result.attempt_id,
            "agent_id": result.agent_id,
            "status": result.status.value,
            "output": result.output,
            "timestamp": result.timestamp,
        }
        if result.task_id not in self.task_attempts:
            self.task_attempts[result.task_id] = []
        self.task_attempts[result.task_id].append(attempt_record)

        # Release lease
        lease = self.active_leases.get(result.task_id)
        if lease:
            self.release_task_lease(result.task_id, result.agent_id, lease.lease_id)

        agent = self.registry.get(result.agent_id)

        # Apply state transition on TaskNode
        if result.status == ResultStatus.SUCCESS:
            task.status = TaskStatus.COMPLETED
            task.completed_at = utc_now()
            task.output_data = result.output
            task.evidence_refs = [e.get("evidence_id", "") for e in result.evidence if isinstance(e, dict)]
            if agent:
                agent.success_count += 1
                agent.total_execution_time_ms += result.metrics.get("execution_time_ms", 0.0)
            self.metrics.total_completed_tasks += 1
            await self.emit_event("swarm_task_completed", {
                "task_id": task.task_id,
                "agent_id": result.agent_id,
                "attempt": result.attempt_id,
            })
            return True, "Task completed successfully"
        else:
            task.status = TaskStatus.FAILED
            task.failure_info = FailureInfo(
                category=FailureCategory.TRANSIENT_FAILURE,
                message=str(result.failure or "Task failed by agent"),
                attempt=result.attempt_id,
                timestamp=utc_now(),
            )
            if agent:
                agent.failure_count += 1
            self.metrics.total_failed_tasks += 1
            await self.emit_event("swarm_task_failed", {
                "task_id": task.task_id,
                "agent_id": result.agent_id,
                "attempt": result.attempt_id,
                "failure": result.failure,
            })
            return False, "Task execution failed"

    def reconcile_leases_and_failures(self, now: float | None = None) -> list[str]:
        """Detects expired leases / unhealthy agents and marks tasks as INTERRUPTED for reassignment."""
        curr = now if now is not None else time.time()
        interrupted: list[str] = []

        # 1. Check agent health
        unhealthy_agents = set(self.registry.check_all_health(curr))

        # 2. Reap expired leases
        expired_leases = self.lease_manager.reap_expired_leases(curr)
        for lease in expired_leases:
            self.metrics.total_expired_leases += 1
            self.active_leases.pop(lease.task_id, None)
            self.file_ownership.release_paths(lease.task_id)
            self.quotas.release(lease.task_id)

            task = self.task_graph.get_node(lease.task_id)
            if task and task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.INTERRUPTED
                task.failure_info = FailureInfo(
                    category=FailureCategory.TIMEOUT,
                    message=f"Lease expired for agent {lease.agent_id}",
                    attempt=lease.attempt_id,
                    timestamp=utc_now(),
                )
                interrupted.append(task.task_id)
                self.metrics.total_reassigned_tasks += 1

        # 3. Handle active leases held by unhealthy agents
        for task_id, lease in list(self.active_leases.items()):
            if lease.agent_id in unhealthy_agents:
                self.release_task_lease(task_id, lease.agent_id, lease.lease_id)
                task = self.task_graph.get_node(task_id)
                if task and task.status == TaskStatus.RUNNING:
                    task.status = TaskStatus.INTERRUPTED
                    task.failure_info = FailureInfo(
                        category=FailureCategory.TRANSIENT_FAILURE,
                        message=f"Agent {lease.agent_id} became UNHEALTHY",
                        attempt=lease.attempt_id,
                        timestamp=utc_now(),
                    )
                    interrupted.append(task_id)
                    self.metrics.total_reassigned_tasks += 1

        return interrupted

    def export_state(self) -> dict[str, Any]:
        """Serializes coordinator state for checkpointing."""
        return {
            "agents": [a.to_dict() for a in self.registry.list_agents()],
            "active_leases": [l.to_dict() for l in self.active_leases.values()],
            "task_attempts": self.task_attempts,
            "metrics": self.metrics.to_dict(),
            "quotas": {
                "global_max": self.quotas.global_max_concurrency,
                "category_limits": self.quotas.category_limits,
            },
        }

    def restore_state(self, state_data: dict[str, Any]) -> None:
        """Restores coordinator state, clearing stale leases post-restart."""
        for a_data in state_data.get("agents", []):
            cap = AgentCapability.from_dict(a_data.get("capability", {}))
            agent = AgentInstance(
                agent_id=a_data["agent_id"],
                agent_type=a_data["agent_type"],
                capability=cap,
                status=AgentHealthStatus(a_data.get("status", "IDLE")),
                failure_count=a_data.get("failure_count", 0),
                success_count=a_data.get("success_count", 0),
            )
            self.registry.register(agent)

        self.task_attempts = state_data.get("task_attempts", {})
        # Clear stale active leases so tasks can be cleanly re-leased post-crash
        self.active_leases.clear()
        self.file_ownership = FileOwnershipRegistry()
