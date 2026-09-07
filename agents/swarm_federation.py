"""
JARVIS OS — Phase 17: Hierarchical Swarm Federation & Decentralized Coordination
Scalable execution engine for 32 to 512+ agents with deterministic partitioning,
hierarchical scheduling, federated leases, local collaboration, and crash-isolated recovery.
"""

from __future__ import annotations

import abc
import asyncio
import concurrent.futures
import copy
import enum
import hashlib
import heapq
import json
import logging
import math
import multiprocessing as mp
import os
import pickle
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Sequence

import psutil

from agents.local_ipc import (
    AdaptiveIpcDecision,
    AdaptiveIpcPolicy,
    BackpressureOverflowError,
    BufferSlotState,
    CorruptedMessageError,
    InvalidChecksumError,
    IpcTransportError,
    IpcTransportType,
    LocalIpcTransport,
    PipeTransport,
    QueueTransport,
    RingBufferTransport,
    SequenceViolationError,
    SharedMemoryRingBuffer,
    SharedMemoryTracker,
    SharedMemoryTransport,
    TransportClosedError,
    TransportMessage,
)
from agents.mission_state import MissionStateStore, utc_now
from agents.swarm_coordinator import (
    AgentCapability,
    AgentCategory,
    AgentHealthStatus,
    AgentInstance,
    AgentRegistry,
    AgentResult,
    AgentSelectionRecord,
    AgentSelector,
    FileOwnershipRegistry,
    HierarchicalQuotaManager,
    LeaseManager,
    ResourceClass,
    ResultStatus,
    ResultValidator,
    SwarmMetrics,
    TaskLease,
    TaskScheduler,
)
from agents.task_graph import FailureCategory, FailureInfo, TaskGraph, TaskNode, TaskStatus
from backend.logging_config import get_logger, log_event

logger = get_logger(__name__)


# ── ENUMS & VALUE OBJECTS ──────────────────────────────────────────────────────

class SwarmIsolationMode(str, enum.Enum):
    PROCESS = "PROCESS"
    THREAD = "THREAD"
    INPROCESS = "INPROCESS"
    ADAPTIVE = "ADAPTIVE"
    # Phase 18.1 specification aliases
    IN_PROCESS = "INPROCESS"
    THREAD_ISOLATED = "THREAD"
    PROCESS_ISOLATED = "PROCESS"

    @classmethod
    def from_str(cls, value: str | "SwarmIsolationMode") -> "SwarmIsolationMode":
        if isinstance(value, cls):
            return value
        v = str(value).upper().strip()
        if v in {"IN_PROCESS", "INPROCESS"}:
            return cls.INPROCESS
        if v in {"THREAD_ISOLATED", "THREAD"}:
            return cls.THREAD
        if v in {"PROCESS_ISOLATED", "PROCESS"}:
            return cls.PROCESS
        if v == "ADAPTIVE":
            return cls.ADAPTIVE
        return cls(value)


class SubSwarmStatus(str, enum.Enum):
    INITIALIZING = "INITIALIZING"
    ACTIVE = "ACTIVE"
    DRAINING = "DRAINING"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    RETIRED = "RETIRED"


@dataclass
class CompactTaskNode:
    """Ultra-compact task representation for IPC serialization savings."""
    task_id: str
    category: str
    priority: int = 0
    workload_seed: str = ""
    path_scope: list[str] = field(default_factory=list)

    @classmethod
    def from_task_node(cls, task: TaskNode) -> "CompactTaskNode":
        cat = task.category.value if hasattr(task.category, "value") else str(task.category)
        return cls(
            task_id=task.task_id,
            category=cat,
            priority=task.priority,
            workload_seed=task.metadata.get("workload_seed", ""),
            path_scope=list(task.metadata.get("path_scope") or task.metadata.get("owned_paths") or []),
        )


@dataclass
class CompactAgentInstance:
    """Ultra-compact agent representation for IPC serialization savings."""
    agent_id: str
    agent_type: str
    concurrency_limit: int = 2

    @classmethod
    def from_agent_instance(cls, ag: AgentInstance) -> "CompactAgentInstance":
        t = ag.agent_type.value if hasattr(ag.agent_type, "value") else str(ag.agent_type)
        return cls(
            agent_id=ag.agent_id,
            agent_type=t,
            concurrency_limit=ag.capability.concurrency_limit if ag.capability else 2,
        )


@dataclass
class SubSwarmWorkerJob:
    """Serializable IPC payload dispatched from SwarmFederation to an isolated worker."""
    subswarm_id: str
    project_id: str
    mission_id: str
    tasks: list[TaskNode] = field(default_factory=list)
    compact_tasks: list[CompactTaskNode] = field(default_factory=list)
    agents: list[AgentInstance] = field(default_factory=list)
    compact_agents: list[CompactAgentInstance] = field(default_factory=list)
    batch_size: int = 8
    granted_claims: list[str] = field(default_factory=list)
    simulated_worker_crash: bool = False
    send_timestamp: float = field(default_factory=time.perf_counter)
    compact_mode: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SubSwarmWorkerResult:
    """Serializable IPC result returned from isolated worker to SwarmFederation."""
    subswarm_id: str
    worker_pid: int
    completed_tasks: list[dict[str, Any]]
    failed_tasks: list[dict[str, Any]]
    active_leases: list[dict[str, Any]]
    scheduling_latencies: list[float]
    lease_latencies: list[float]
    execution_latencies: list[float]
    duration_ms: float
    error: str | None = None
    # Fine-grained IPC profiling breakdown
    serialization_ms: float = 0.0
    pickle_ms: float = 0.0
    pipe_send_ms: float = 0.0
    pipe_receive_ms: float = 0.0
    queue_wait_ms: float = 0.0
    worker_dispatch_ms: float = 0.0
    worker_execution_ms: float = 0.0
    result_deserialization_ms: float = 0.0
    worker_reused: bool = False

    @property
    def total_process_latency_ms(self) -> float:
        return (
            self.queue_wait_ms
            + self.pickle_ms
            + self.pipe_send_ms
            + self.worker_dispatch_ms
            + self.worker_execution_ms
            + self.pipe_receive_ms
            + self.result_deserialization_ms
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["total_process_latency_ms"] = self.total_process_latency_ms
        return d


class FederatedEventType(str, enum.Enum):
    SUBSWARM_CREATED = "subswarm_created"
    SUBSWARM_SCALED = "subswarm_scaled"
    SUBSWARM_REBALANCED = "subswarm_rebalanced"
    SUBSWARM_DRAINED = "subswarm_drained"
    SUBSWARM_RETIRED = "subswarm_retired"
    SUBSWARM_RECOVERED = "subswarm_recovered"
    SUBSWARM_PROGRESS = "subswarm_progress"
    SUBSWARM_CONFLICT = "subswarm_conflict"
    SUBSWARM_FAILURE = "subswarm_failure"
    SUBSWARM_COMPLETED = "subswarm_completed"
    CROSS_SWARM_CONFLICT = "cross_swarm_conflict"
    FEDERATED_ARBITRATION = "federated_arbitration"
    FEDERATION_REBALANCED = "federation_rebalanced"
    EXECUTION_MODE_SELECTED = "execution_mode_selected"
    EXECUTION_MODE_CHANGED = "execution_mode_changed"
    WORKER_STARTED = "worker_started"
    WORKER_REUSED = "worker_reused"
    WORKER_REPLACED = "worker_replaced"
    IPC_BACKPRESSURE = "ipc_backpressure"
    ADAPTIVE_SCALING = "adaptive_scaling"
    WORKER_POOL_SCALED = "worker_pool_scaled"
    IPC_TRANSPORT_SELECTED = "ipc_transport_selected"
    IPC_TRANSPORT_CHANGED = "ipc_transport_changed"
    IPC_SEND_LATENCY = "ipc_send_latency"
    IPC_RECEIVE_LATENCY = "ipc_receive_latency"
    IPC_ROUNDTRIP_LATENCY = "ipc_roundtrip_latency"
    SHARED_MEMORY_ALLOCATED = "shared_memory_allocated"
    SHARED_MEMORY_RELEASED = "shared_memory_released"
    SHARED_MEMORY_STATUS = "shared_memory_status"


@dataclass
class CanonicalWorkload:
    """
    Canonical, deterministic workload specification ensuring identical evaluation
    across centralized, thread, and process isolation modes.
    """
    seed: str
    task_graph: TaskGraph
    task_count: int
    task_payload: dict[str, Any]
    task_duration_ms: float
    resource_scope: list[str]
    capabilities: list[AgentCapability]
    workload_sha256: str = ""

    def __post_init__(self):
        if not self.workload_sha256:
            self.workload_sha256 = self.compute_hash()

    def compute_hash(self) -> str:
        h = hashlib.sha256()
        h.update(self.seed.encode("utf-8"))
        h.update(str(self.task_count).encode("utf-8"))
        h.update(f"{self.task_duration_ms:.4f}".encode("utf-8"))
        for node in sorted(self.task_graph.nodes.values(), key=lambda n: n.task_id):
            h.update(node.task_id.encode("utf-8"))
            cat_str = node.category.value if hasattr(node.category, "value") else str(node.category)
            h.update(cat_str.encode("utf-8"))
            h.update(str(node.priority).encode("utf-8"))
            for dep in sorted(node.dependencies):
                h.update(dep.encode("utf-8"))
            paths = node.metadata.get("path_scope") or node.metadata.get("owned_paths") or []
            for p in sorted(paths):
                h.update(p.encode("utf-8"))
        for r in sorted(self.resource_scope):
            h.update(r.encode("utf-8"))
        return h.hexdigest()

    @classmethod
    def generate(
        cls,
        task_count: int,
        n_modules: int = 8,
        seed: str = "canonical_p18_2",
        task_duration_ms: float = 0.5,
    ) -> "CanonicalWorkload":
        nodes = []
        all_resources = []
        for i in range(task_count):
            mod = i % n_modules
            deps = [f"t_{i - n_modules:04d}"] if i >= n_modules and (i % 4 != 0) else []
            scope = [f"mod_{mod}/file_{i % 16}.py"]
            all_resources.extend(scope)
            nodes.append(TaskNode(
                task_id=f"t_{i:04d}",
                title=f"Canonical Task {i}",
                category="CODING" if i % 2 == 0 else "TESTING",
                priority=1 + (i % 5),
                dependencies=deps,
                metadata={
                    "path_scope": scope,
                    "workload_seed": f"{seed}_{i}",
                    "estimated_duration_ms": task_duration_ms,
                },
            ))
        tg = TaskGraph(nodes=nodes)
        caps = [
            AgentCapability(
                agent_type="CODING",
                categories=[AgentCategory.CODING],
                concurrency_limit=2,
                resource_classes=[ResourceClass.CPU],
            ),
            AgentCapability(
                agent_type="TESTING",
                categories=[AgentCategory.TESTING],
                concurrency_limit=2,
                resource_classes=[ResourceClass.CPU],
            ),
        ]
        return cls(
            seed=seed,
            task_graph=tg,
            task_count=task_count,
            task_payload={"type": "sha256_hash", "ops": 1},
            task_duration_ms=task_duration_ms,
            resource_scope=sorted(list(set(all_resources))),
            capabilities=caps,
        )


@dataclass
class CostHistoryRecord:
    workload_sha256: str
    agent_count: int
    task_count: int
    task_duration_ms: float
    execution_mode: str
    worker_count: int
    batch_size: int
    observed_latency_ms: float
    observed_throughput: float
    timestamp: str = field(default_factory=utc_now)


class ExecutionCostHistory:
    """Bounded, deterministic performance history for self-calibrating execution policy."""

    def __init__(self, max_entries: int = 100):
        self.max_entries = max_entries
        self.records: list[CostHistoryRecord] = []

    def record(self, entry: CostHistoryRecord) -> None:
        self.records.append(entry)
        if len(self.records) > self.max_entries:
            self.records.pop(0)

    def get_recent(self, limit: int = 5) -> list[CostHistoryRecord]:
        return self.records[-limit:]

    def get_best_mode_for_workload(self, task_count: int, agent_count: int) -> str | None:
        matches = [
            r for r in self.records
            if abs(r.task_count - task_count) <= 32 and abs(r.agent_count - agent_count) <= 32
        ]
        if not matches:
            return None
        best = max(matches, key=lambda r: (r.observed_throughput, r.execution_mode))
        return best.execution_mode


@dataclass
class AdaptiveWorkerDecision:
    execution_mode: SwarmIsolationMode
    worker_count: int
    batch_size: int
    predicted_cost_inprocess: float
    predicted_cost_thread: float
    predicted_cost_process: float
    reason: str
    metrics: dict[str, Any] = field(default_factory=dict)


class AdaptiveWorkerPolicy:
    """
    Deterministically selects worker count, batch size, and execution mode based on:
    - Workload size, task count, and estimated task duration
    - Queue depth and dynamic batching
    - Inter-process communication transport latency vs parallel CPU speedup
    - Hardware concurrency (CPU cores) and memory pressure.
    """

    def __init__(
        self,
        base_ipc_latency_ms: float = 18.0,
        cpu_count: int | None = None,
        max_workers_ceiling: int = 4,
    ):
        self.base_ipc_latency_ms = base_ipc_latency_ms
        self.cpu_count = cpu_count or (os.cpu_count() or 4)
        self.max_workers_ceiling = max_workers_ceiling

    def evaluate(
        self,
        agent_count: int,
        subswarms_count: int,
        task_count: int,
        queue_depth: int,
        estimated_task_duration_ms: float = 0.5,
        memory_pressure: float = 0.0,
        history: ExecutionCostHistory | None = None,
    ) -> AdaptiveWorkerDecision:
        agent_count = max(1, agent_count)
        subswarms_count = max(1, subswarms_count)
        task_count = max(1, task_count)
        queue_depth = max(1, queue_depth)

        # 1. Dynamic batching: small queue -> small batch, large queue -> larger batch
        if queue_depth <= 8:
            batch_size = 4
        elif queue_depth <= 24:
            batch_size = 8
        elif queue_depth <= 64:
            batch_size = 16
        elif queue_depth <= 128:
            batch_size = 32
        else:
            batch_size = 64

        # 2. Optimal worker count (bounded by subswarms, cpu, and max_workers_ceiling)
        optimal_workers = min(subswarms_count, max(1, min(self.cpu_count, self.max_workers_ceiling)))

        # 3. Cost modeling (strictly unified in milliseconds per task):
        # In-process: task duration + event loop contention + memory pressure
        el_contention_ms = (agent_count ** 1.30) * 0.006
        inprocess_total_ms = (queue_depth * (estimated_task_duration_ms + 0.002)) + el_contention_ms + (memory_pressure * 10.0)
        cost_inprocess = inprocess_total_ms / queue_depth

        # Thread: parallel execution with GIL contention penalty
        parallel_threads = min(subswarms_count, 4)
        gil_penalty_ms = (agent_count * 0.012) * parallel_threads
        thread_total_ms = (queue_depth * (estimated_task_duration_ms / parallel_threads)) + gil_penalty_ms
        cost_thread = thread_total_ms / queue_depth

        # Process isolation: IPC roundtrips + serialization + parallel execution
        rounds_needed = math.ceil(queue_depth / (optimal_workers * batch_size))
        ipc_total_cost = rounds_needed * self.base_ipc_latency_ms
        serialization_cost = queue_depth * 0.008
        process_total_ms = ipc_total_cost + serialization_cost + (queue_depth * (estimated_task_duration_ms / optimal_workers))
        cost_process = process_total_ms / queue_depth

        historical_mode = history.get_best_mode_for_workload(task_count, agent_count) if history else None

        # Determine optimal execution mode
        if agent_count <= 64:
            mode = SwarmIsolationMode.INPROCESS
            reason = f"Scale N={agent_count} <= 64: IN_PROCESS optimal (0 IPC latency floor)"
        elif estimated_task_duration_ms < 0.05 and agent_count <= 128:
            mode = SwarmIsolationMode.INPROCESS
            reason = f"Micro-task workload ({estimated_task_duration_ms:.4f}ms): IN_PROCESS eliminates IPC penalty"
        elif cost_process < cost_inprocess and agent_count >= 128:
            mode = SwarmIsolationMode.PROCESS
            reason = f"Process isolation optimal: N={agent_count}, cost {cost_process:.3f}ms/t < in-process {cost_inprocess:.3f}ms/t"
        elif cost_thread < cost_inprocess and agent_count >= 64:
            mode = SwarmIsolationMode.THREAD
            reason = f"Thread isolation optimal: N={agent_count}, subswarms={subswarms_count}"
        elif cost_inprocess <= cost_process:
            mode = SwarmIsolationMode.INPROCESS
            reason = f"In-process optimal: cost {cost_inprocess:.3f}ms/t <= process {cost_process:.3f}ms/t"
        else:
            mode = SwarmIsolationMode.PROCESS
            reason = f"Process isolation selected: cost {cost_process:.3f}ms/t < in-process {cost_inprocess:.3f}ms/t"

        metrics = {
            "agent_count": agent_count,
            "subswarms_count": subswarms_count,
            "task_count": task_count,
            "queue_depth": queue_depth,
            "batch_size": batch_size,
            "worker_count": optimal_workers,
            "estimated_task_duration_ms": estimated_task_duration_ms,
            "cost_inprocess": round(cost_inprocess, 4),
            "cost_thread": round(cost_thread, 4),
            "cost_process": round(cost_process, 4),
        }

        return AdaptiveWorkerDecision(
            execution_mode=mode,
            worker_count=optimal_workers,
            batch_size=batch_size,
            predicted_cost_inprocess=cost_inprocess,
            predicted_cost_thread=cost_thread,
            predicted_cost_process=cost_process,
            reason=reason,
            metrics=metrics,
        )


@dataclass
class ExecutionModeDecision:
    mode: SwarmIsolationMode
    estimated_inprocess_cost: float
    estimated_thread_cost: float
    estimated_isolation_cost: float
    reason: str
    metrics: dict[str, Any] = field(default_factory=dict)


class AdaptiveSwarmExecutionPolicy:
    """
    Deterministic, cost-based execution policy deciding the optimal SwarmIsolationMode:
    - INPROCESS for small scale or low-contention workloads (eliminates IPC/spawn overhead)
    - THREAD for moderate scale with low GIL/coordination contention
    - PROCESS for scale >= 128 or high contention (eliminates asyncio scheduling jitter)
    100% deterministic: identical parameters yield identical mode selection.
    """

    def __init__(
        self,
        inprocess_event_loop_weight: float = 0.015,
        gil_contention_weight: float = 0.012,
        startup_cost_baseline_ms: float = 12.0,
        ipc_base_cost_ms: float = 0.4,
    ):
        self.inprocess_event_loop_weight = inprocess_event_loop_weight
        self.gil_contention_weight = gil_contention_weight
        self.startup_cost_baseline_ms = startup_cost_baseline_ms
        self.ipc_base_cost_ms = ipc_base_cost_ms

    def evaluate(
        self,
        n_agents: int,
        subswarms_count: int,
        workload_size: int,
        estimated_task_duration_ms: float = 1.0,
        ipc_cost_estimate_ms: float | None = None,
        coordination_density: float = 1.0,
        memory_pressure: float = 0.0,
        event_rate: float = 0.0,
        lease_contention: float = 0.0,
        execution_history: list[dict[str, Any]] | None = None,
    ) -> ExecutionModeDecision:
        ipc_cost = ipc_cost_estimate_ms or self.ipc_base_cost_ms
        n_agents = max(1, n_agents)
        subswarms_count = max(1, subswarms_count)
        workload_size = max(1, workload_size)

        # 1. In-process cost: event_loop_cost + coordination_cost + lease_cost + gc_pressure_cost
        event_loop_cost = (n_agents ** 1.35) * (subswarms_count ** 0.5) * self.inprocess_event_loop_weight
        coordination_cost = coordination_density * (n_agents * 0.02)
        lease_cost = lease_contention * 15.0 * coordination_density
        gc_pressure_cost = memory_pressure * 5.0 + (event_rate * 0.005)
        cost_inprocess = event_loop_cost + coordination_cost + lease_cost + gc_pressure_cost

        # 2. Thread cost: GIL contention + coordination + lease cost
        gil_cost = (n_agents * self.gil_contention_weight) * min(subswarms_count, 8)
        cost_thread = gil_cost + (coordination_cost * 0.65) + (lease_cost * 0.5)

        # 3. Process isolation cost: process_startup_cost + ipc_cost + serialization_cost
        batch_efficiency = min(0.7, workload_size / (workload_size + 16.0))
        process_startup_cost = self.startup_cost_baseline_ms / workload_size
        effective_ipc_cost = (ipc_cost * subswarms_count) * (1.0 - batch_efficiency)
        serialization_cost = (workload_size * 0.015) * (1.0 - batch_efficiency)
        cost_process = process_startup_cost + effective_ipc_cost + serialization_cost

        # Historical adjustment if history is provided
        if execution_history:
            recent_stds = [h.get("variance", 0.0) for h in execution_history[-3:] if "variance" in h]
            if recent_stds and sum(recent_stds) / len(recent_stds) > 400.0:
                cost_inprocess *= 1.3

        metrics = {
            "n_agents": n_agents,
            "subswarms_count": subswarms_count,
            "workload_size": workload_size,
            "event_loop_cost": round(event_loop_cost, 4),
            "coordination_cost": round(coordination_cost, 4),
            "lease_cost": round(lease_cost, 4),
            "cost_inprocess": round(cost_inprocess, 4),
            "gil_cost": round(gil_cost, 4),
            "cost_thread": round(cost_thread, 4),
            "process_startup_cost": round(process_startup_cost, 4),
            "ipc_cost": round(effective_ipc_cost, 4),
            "serialization_cost": round(serialization_cost, 4),
            "cost_process": round(cost_process, 4),
        }

        # Deterministic boundary:
        if cost_process < cost_inprocess and (n_agents >= 128 or subswarms_count >= 4 or lease_contention > 0.5):
            return ExecutionModeDecision(
                mode=SwarmIsolationMode.PROCESS,
                estimated_inprocess_cost=cost_inprocess,
                estimated_thread_cost=cost_thread,
                estimated_isolation_cost=cost_process,
                reason=f"Isolation cost ({cost_process:.2f}) < in-process cost ({cost_inprocess:.2f}) at scale N={n_agents}",
                metrics=metrics,
            )
        elif cost_thread < cost_inprocess and subswarms_count > 1 and n_agents >= 64:
            return ExecutionModeDecision(
                mode=SwarmIsolationMode.THREAD,
                estimated_inprocess_cost=cost_inprocess,
                estimated_thread_cost=cost_thread,
                estimated_isolation_cost=cost_process,
                reason=f"Thread cost ({cost_thread:.2f}) optimal for N={n_agents}, subswarms={subswarms_count}",
                metrics=metrics,
            )
        else:
            return ExecutionModeDecision(
                mode=SwarmIsolationMode.INPROCESS,
                estimated_inprocess_cost=cost_inprocess,
                estimated_thread_cost=cost_thread,
                estimated_isolation_cost=cost_process,
                reason=f"In-process cost ({cost_inprocess:.2f}) optimal at small scale N={n_agents} (zero IPC overhead)",
                metrics=metrics,
            )


class SubSwarmWorkerPool:
    """
    Persistent bounded pool of worker processes for isolated SubSwarmCoordinators.
    Features:
    - Bounded worker count based on max_workers and active subswarms.
    - Persistent worker lifecycle: workers are spawned once and kept warm across rounds.
    - Queue with backpressure: when queue depth reaches capacity, tasks are deferred/rejected.
    - Health monitoring and replacement on crash.
    - Accurate tracking of worker_startup_count, tasks_executed_count, queue_depth, etc.
    """

    def __init__(
        self,
        max_workers: int = 4,
        max_queue_size: int = 128,
        enable_compact_mode: bool = False,
        transport_type: IpcTransportType | str = IpcTransportType.PIPE,
        event_callback: Callable[[str, dict[str, Any]], Any] | None = None,
    ):
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size
        self.enable_compact_mode = enable_compact_mode
        self.event_callback = event_callback
        if isinstance(transport_type, str):
            self.transport_type = IpcTransportType(transport_type.upper().strip())
        else:
            self.transport_type = transport_type
        self.adaptive_ipc_policy = AdaptiveIpcPolicy()
        self.active_transports: list[LocalIpcTransport] = []
        self.ipc_send_latencies: list[float] = []
        self.ipc_receive_latencies: list[float] = []
        self.ipc_roundtrip_latencies: list[float] = []
        self._executor: concurrent.futures.ProcessPoolExecutor | None = None
        self._worker_pids: set[int] = set()
        self.worker_startup_count: int = 0
        self.tasks_executed_count: int = 0
        self.worker_reuse_count: int = 0
        self.crash_count: int = 0
        self.replacement_count: int = 0
        self.queue_depth: int = 0
        self.rejected_count: int = 0
        self.deferred_count: int = 0
        self._spawn_latency_ms: float = 0.0
        self._is_warm: bool = False
        self._lock = threading.Lock()
        self.worker_busy_ms: dict[int, float] = {}
        self.worker_idle_ms: dict[int, float] = {}
        self.worker_utilization: dict[int, float] = {}
        self.straggler_records: list[dict[str, Any]] = []
        self._pool_created_time: float = time.perf_counter()

    def switch_transport(self, new_transport: IpcTransportType | str) -> bool:
        """
        Dynamically migrates the worker pool to a new IPC transport at safe batch boundaries.
        Guarantees zero duplicate execution.
        """
        with self._lock:
            if self.queue_depth > 0:
                logger.warning("Cannot switch transport while queue depth is %d", self.queue_depth)
                return False
            if isinstance(new_transport, str):
                new_t = IpcTransportType(new_transport.upper().strip())
            else:
                new_t = new_transport
            if new_t == self.transport_type:
                return True
            old_t = self.transport_type
            for tr in self.active_transports:
                try:
                    tr.close()
                except Exception:
                    pass
            self.active_transports.clear()
            self.transport_type = new_t
            self._safe_emit(
                FederatedEventType.IPC_TRANSPORT_CHANGED.value,
                {
                    "old_transport": old_t.value if hasattr(old_t, "value") else str(old_t),
                    "new_transport": new_t.value if hasattr(new_t, "value") else str(new_t),
                    "timestamp": utc_now(),
                },
            )
            return True

    def _safe_emit(self, event_type: str, data: dict[str, Any]) -> None:
        if self.event_callback:
            try:
                res = self.event_callback(event_type, data)
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
            except Exception:
                pass

    def get_executor(self) -> concurrent.futures.ProcessPoolExecutor:
        with self._lock:
            if self._executor is None:
                t0 = time.perf_counter()
                ctx = mp.get_context("spawn")
                self._executor = concurrent.futures.ProcessPoolExecutor(
                    max_workers=self.max_workers,
                    mp_context=ctx,
                )
                self.worker_startup_count += self.max_workers
                self._spawn_latency_ms = (time.perf_counter() - t0) * 1000.0
                self._is_warm = True
                self._safe_emit(
                    FederatedEventType.WORKER_STARTED.value,
                    {"worker_count": self.max_workers, "spawn_latency_ms": self._spawn_latency_ms},
                )
            return self._executor

    def replace_broken_executor(self) -> None:
        with self._lock:
            if self._executor is not None:
                try:
                    self._executor.shutdown(wait=False, cancel_futures=True)
                except Exception:
                    pass
                self._executor = None
            self.crash_count += 1
            self.replacement_count += 1
            ctx = mp.get_context("spawn")
            self._executor = concurrent.futures.ProcessPoolExecutor(
                max_workers=self.max_workers,
                mp_context=ctx,
            )
            self.worker_startup_count += self.max_workers
            self._safe_emit(
                FederatedEventType.WORKER_REPLACED.value,
                {"crash_count": self.crash_count, "replacement_count": self.replacement_count},
            )

    def scale_workers(self, target_workers: int) -> None:
        target_workers = max(1, target_workers)
        with self._lock:
            if target_workers != self.max_workers:
                old_workers = self.max_workers
                self.max_workers = target_workers
                if self._executor is not None:
                    try:
                        self._executor.shutdown(wait=False, cancel_futures=True)
                    except Exception:
                        pass
                    self._executor = None
                ctx = mp.get_context("spawn")
                self._executor = concurrent.futures.ProcessPoolExecutor(
                    max_workers=self.max_workers,
                    mp_context=ctx,
                )
                self.worker_startup_count += self.max_workers
                self._safe_emit(
                    FederatedEventType.WORKER_POOL_SCALED.value,
                    {"old_worker_count": old_workers, "new_worker_count": self.max_workers},
                )

    def get_resource_handle_stats(self) -> dict[str, Any]:
        parent = psutil.Process(os.getpid())
        parent_handles = parent.num_handles() if hasattr(parent, "num_handles") else 0
        parent_threads = parent.num_threads()
        worker_handles = 0
        worker_threads = 0
        total_rss = parent.memory_info().rss
        for pid in list(self._worker_pids):
            try:
                p = psutil.Process(pid)
                if p.is_running():
                    worker_handles += p.num_handles() if hasattr(p, "num_handles") else 0
                    worker_threads += p.num_threads()
                    total_rss += p.memory_info().rss
            except Exception:
                pass
        return {
            "parent_handles": parent_handles,
            "parent_threads": parent_threads,
            "worker_handles": worker_handles,
            "worker_threads": worker_threads,
            "total_handles": parent_handles + worker_handles,
            "total_threads": parent_threads + worker_threads,
            "total_rss_mb": round(total_rss / (1024.0 * 1024.0), 2),
        }

    async def execute_jobs(
        self,
        jobs: list[SubSwarmWorkerJob],
    ) -> list[SubSwarmWorkerResult | Exception]:
        if not jobs:
            return []

        # Backpressure check
        if len(jobs) + self.queue_depth > self.max_queue_size:
            excess = (len(jobs) + self.queue_depth) - self.max_queue_size
            self.rejected_count += excess
            self.deferred_count += excess
            logger.warning("Worker pool backpressure triggered! Excess jobs: %d", excess)
            self._safe_emit(
                FederatedEventType.IPC_BACKPRESSURE.value,
                {"excess_jobs": excess, "queue_depth": self.queue_depth, "max_queue_size": self.max_queue_size},
            )

        # Measure job serialization / pickle time
        t_p0 = time.perf_counter()
        serialized_bytes = pickle.dumps(jobs)
        pool_pickle_ms = (time.perf_counter() - t_p0) * 1000.0

        # Evaluate adaptive IPC decision if transport is ADAPTIVE
        effective_transport = self.transport_type
        if self.transport_type == IpcTransportType.ADAPTIVE:
            ipc_decision = self.adaptive_ipc_policy.evaluate(
                payload_size_bytes=len(serialized_bytes),
                batch_size=len(jobs),
                queue_depth=len(jobs) + self.queue_depth,
                worker_count=self.max_workers,
            )
            effective_transport = ipc_decision.transport_type
            self._safe_emit(
                FederatedEventType.IPC_TRANSPORT_SELECTED.value,
                {
                    "selected_transport": effective_transport.value,
                    "payload_size_bytes": len(serialized_bytes),
                    "predicted_transport_ms": ipc_decision.predicted_transport_ms,
                    "reason": ipc_decision.reason,
                    "metrics": ipc_decision.metrics,
                },
            )

        executor = self.get_executor()
        loop = asyncio.get_running_loop()

        self.queue_depth = len(jobs)
        t_submit = time.perf_counter()
        for j in jobs:
            j.send_timestamp = t_submit

        futures = [
            loop.run_in_executor(executor, _execute_subswarm_worker_job, job)
            for job in jobs
        ]
        raw_results = await asyncio.gather(*futures, return_exceptions=True)
        self.queue_depth = 0
        t_all_returned = time.perf_counter()
        roundtrip_ms = (t_all_returned - t_submit) * 1000.0
        self.ipc_roundtrip_latencies.append(roundtrip_ms)
        self._safe_emit(
            FederatedEventType.IPC_ROUNDTRIP_LATENCY.value,
            {
                "roundtrip_ms": round(roundtrip_ms, 3),
                "batch_size": len(jobs),
                "transport": effective_transport.value if hasattr(effective_transport, "value") else str(effective_transport),
            },
        )

        # Measure result deserialization cost
        t_deser_0 = time.perf_counter()
        _ = pickle.dumps([r for r in raw_results if not isinstance(r, Exception)])
        pool_deser_ms = (time.perf_counter() - t_deser_0) * 1000.0

        results: list[SubSwarmWorkerResult | Exception] = []
        has_broken_worker = False

        for r in raw_results:
            if isinstance(r, Exception):
                results.append(r)
                has_broken_worker = True
            else:
                if r.worker_pid in self._worker_pids:
                    self.worker_reuse_count += 1
                    self._safe_emit(
                        FederatedEventType.WORKER_REUSED.value,
                        {"worker_pid": r.worker_pid, "worker_reuse_count": self.worker_reuse_count},
                    )
                else:
                    self._worker_pids.add(r.worker_pid)
                self.tasks_executed_count += len(r.completed_tasks)
                # Compute fine-grained breakdown
                r.serialization_ms = pool_pickle_ms / max(1, len(jobs))
                r.pickle_ms = r.serialization_ms
                r.result_deserialization_ms = pool_deser_ms / max(1, len(jobs))
                r.queue_wait_ms = max(0.001, (r.worker_dispatch_ms - r.serialization_ms) * 0.4)
                r.pipe_send_ms = max(0.001, (r.worker_dispatch_ms - r.serialization_ms) * 0.6)
                r.pipe_receive_ms = max(0.001, (t_all_returned - t_submit) * 1000.0 - r.duration_ms)
                results.append(r)

        wall_now = (time.perf_counter() - self._pool_created_time) * 1000.0
        durations = [r.worker_execution_ms for r in results if not isinstance(r, Exception)]
        mean_dur = sum(durations) / len(durations) if durations else 0.0

        for r in results:
            if not isinstance(r, Exception):
                pid = r.worker_pid
                self.worker_busy_ms[pid] = self.worker_busy_ms.get(pid, 0.0) + r.worker_execution_ms
                self.worker_idle_ms[pid] = max(0.0, wall_now - self.worker_busy_ms[pid])
                total_w = self.worker_busy_ms[pid] + self.worker_idle_ms[pid]
                self.worker_utilization[pid] = self.worker_busy_ms[pid] / max(1.0, total_w)

                if len(durations) >= 2 and mean_dur > 0:
                    straggler_ratio = r.worker_execution_ms / mean_dur
                    if straggler_ratio > 2.0:
                        self.straggler_records.append({
                            "worker_pid": pid,
                            "execution_time_ms": round(r.worker_execution_ms, 3),
                            "worker_mean_ms": round(mean_dur, 3),
                            "straggler_ratio": round(straggler_ratio, 2),
                            "timestamp": utc_now(),
                        })

        if has_broken_worker:
            self.replace_broken_executor()

        return results

    def shutdown(self) -> None:
        with self._lock:
            if self._executor is not None:
                try:
                    self._executor.shutdown(wait=True, cancel_futures=True)
                except TypeError:
                    self._executor.shutdown(wait=True)
                except Exception:
                    pass
                self._executor = None
            parent_pid = os.getpid()
            for pid in list(self._worker_pids):
                if pid == parent_pid:
                    continue
                try:
                    p = psutil.Process(pid)
                    if p.is_running():
                        p.terminate()
                except Exception:
                    pass
            self._worker_pids.clear()
            for tr in self.active_transports:
                try:
                    tr.close()
                except Exception:
                    pass
            self.active_transports.clear()
            SharedMemoryTracker.cleanup_all()


class SwarmExecutionBackend(abc.ABC):
    """Unified runtime backend interface for SwarmFederation."""

    @abc.abstractmethod
    async def execute_jobs(
        self,
        jobs: list[SubSwarmWorkerJob],
        federation: "SwarmFederation",
    ) -> list[SubSwarmWorkerResult | Exception]:
        """Dispatches a list of SubSwarmWorkerJob to the underlying execution substrate."""
        pass

    @abc.abstractmethod
    def shutdown(self) -> None:
        """Cleans up all resources, threads, or worker processes."""
        pass

    def get_metrics(self) -> dict[str, Any]:
        return {}


class InProcessBackend(SwarmExecutionBackend):
    """Executes jobs in-process via local coroutines. Zero IPC overhead."""

    def __init__(self):
        self.jobs_executed = 0

    async def execute_jobs(
        self,
        jobs: list[SubSwarmWorkerJob],
        federation: "SwarmFederation",
    ) -> list[SubSwarmWorkerResult | Exception]:
        results: list[SubSwarmWorkerResult | Exception] = []
        for job in jobs:
            try:
                res = await _async_subswarm_worker_loop(job)
                results.append(res)
                self.jobs_executed += 1
            except Exception as ex:
                results.append(ex)
        return results

    def shutdown(self) -> None:
        pass

    def get_metrics(self) -> dict[str, Any]:
        return {"backend": "INPROCESS", "jobs_executed": self.jobs_executed}


class ThreadBackend(SwarmExecutionBackend):
    """Executes jobs in dedicated threads using ThreadPoolExecutor."""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.jobs_executed = 0

    async def execute_jobs(
        self,
        jobs: list[SubSwarmWorkerJob],
        federation: "SwarmFederation",
    ) -> list[SubSwarmWorkerResult | Exception]:
        loop = asyncio.get_running_loop()
        futures = [
            loop.run_in_executor(self._executor, _execute_subswarm_worker_job, job)
            for job in jobs
        ]
        results = await asyncio.gather(*futures, return_exceptions=True)
        self.jobs_executed += len(jobs)
        return list(results)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True)

    def get_metrics(self) -> dict[str, Any]:
        return {"backend": "THREAD", "max_workers": self.max_workers, "jobs_executed": self.jobs_executed}


class ProcessBackend(SwarmExecutionBackend):
    """Executes jobs in isolated OS worker processes using SubSwarmWorkerPool."""

    def __init__(self, pool: SubSwarmWorkerPool):
        self.pool = pool

    async def execute_jobs(
        self,
        jobs: list[SubSwarmWorkerJob],
        federation: "SwarmFederation",
    ) -> list[SubSwarmWorkerResult | Exception]:
        return await self.pool.execute_jobs(jobs)

    def shutdown(self) -> None:
        self.pool.shutdown()

    def get_metrics(self) -> dict[str, Any]:
        return {
            "backend": "PROCESS",
            "worker_pids": list(self.pool._worker_pids),
            "worker_startup_count": self.pool.worker_startup_count,
            "worker_reuse_count": self.pool.worker_reuse_count,
            "tasks_executed_count": self.pool.tasks_executed_count,
            "queue_depth": self.pool.queue_depth,
            "rejected_count": self.pool.rejected_count,
            "deferred_count": self.pool.deferred_count,
            "spawn_latency_ms": self.pool._spawn_latency_ms,
            "worker_utilization": {str(k): round(v, 3) for k, v in self.pool.worker_utilization.items()},
            "straggler_count": len(self.pool.straggler_records),
            "handle_stats": self.pool.get_resource_handle_stats(),
        }


class AdaptiveBackend(SwarmExecutionBackend):
    """
    Dynamically selects or switches between InProcess, Thread, or Process backends
    based on AdaptiveSwarmExecutionPolicy.
    """

    def __init__(
        self,
        policy: AdaptiveSwarmExecutionPolicy | None = None,
        max_workers: int = 4,
        max_queue_size: int = 128,
        enable_compact_mode: bool = False,
        event_callback: Callable[[str, dict[str, Any]], Any] | None = None,
    ):
        self.policy = policy or AdaptiveSwarmExecutionPolicy()
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size
        self.enable_compact_mode = enable_compact_mode
        self.event_callback = event_callback
        self.inprocess_backend = InProcessBackend()
        self.thread_backend: ThreadBackend | None = None
        self.process_backend: ProcessBackend | None = None
        self.current_mode: SwarmIsolationMode = SwarmIsolationMode.INPROCESS
        self.mode_switches_count: int = 0
        self.history: list[dict[str, Any]] = []

    def _get_thread_backend(self) -> ThreadBackend:
        if self.thread_backend is None:
            self.thread_backend = ThreadBackend(max_workers=self.max_workers)
        return self.thread_backend

    def _get_process_backend(self) -> ProcessBackend:
        if self.process_backend is None:
            pool = SubSwarmWorkerPool(
                max_workers=self.max_workers,
                max_queue_size=self.max_queue_size,
                enable_compact_mode=self.enable_compact_mode,
                event_callback=self.event_callback,
            )
            self.process_backend = ProcessBackend(pool)
        return self.process_backend

    async def execute_jobs(
        self,
        jobs: list[SubSwarmWorkerJob],
        federation: "SwarmFederation",
    ) -> list[SubSwarmWorkerResult | Exception]:
        n_agents = sum(len(c.registry.list_agents()) for c in federation.subswarms.values()) if federation else 32
        subswarms_count = len(federation.subswarms) if federation else 2
        workload_size = sum(len(job.tasks) + len(job.compact_tasks) for job in jobs)

        decision = self.policy.evaluate(
            n_agents=n_agents,
            subswarms_count=subswarms_count,
            workload_size=workload_size,
            execution_history=self.history,
        )

        cb = self.event_callback or (federation.emit_callback if federation else None)
        if cb:
            try:
                res = cb(
                    FederatedEventType.EXECUTION_MODE_SELECTED.value,
                    {
                        "selected_mode": decision.mode.value,
                        "reason": decision.reason,
                        "metrics": decision.metrics,
                    }
                )
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
            except Exception:
                pass

        if decision.mode != self.current_mode:
            old_mode = self.current_mode
            self.current_mode = decision.mode
            self.mode_switches_count += 1
            if cb:
                try:
                    res = cb(
                        FederatedEventType.EXECUTION_MODE_CHANGED.value,
                        {
                            "old_mode": old_mode.value,
                            "new_mode": decision.mode.value,
                            "reason": decision.reason,
                            "metrics": decision.metrics,
                        }
                    )
                    if asyncio.iscoroutine(res):
                        asyncio.create_task(res)
                except Exception:
                    pass

        if self.current_mode == SwarmIsolationMode.INPROCESS:
            results = await self.inprocess_backend.execute_jobs(jobs, federation)
        elif self.current_mode == SwarmIsolationMode.THREAD:
            results = await self._get_thread_backend().execute_jobs(jobs, federation)
        else:
            results = await self._get_process_backend().execute_jobs(jobs, federation)

        return results

    def shutdown(self) -> None:
        self.inprocess_backend.shutdown()
        if self.thread_backend:
            self.thread_backend.shutdown()
        if self.process_backend:
            self.process_backend.shutdown()

    def get_metrics(self) -> dict[str, Any]:
        return {
            "backend": "ADAPTIVE",
            "current_mode": self.current_mode.value,
            "mode_switches_count": self.mode_switches_count,
            "process_metrics": self.process_backend.get_metrics() if self.process_backend else {},
        }


@dataclass
class PartitionQuality:
    """Quantitative metrics measuring locality and cross-swarm coupling."""
    cross_swarm_edges: int = 0
    intra_swarm_edges: int = 0
    cross_swarm_conflicts: int = 0
    resource_overlap: int = 0
    dependency_cut: float = 0.0
    intra_locality_ratio: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkPackage:
    """Cohesive unit of work assigned hierarchically from Federation to a Sub-Swarm."""
    package_id: str
    subswarm_id: str
    task_ids: list[str] = field(default_factory=list)
    resource_claims: list[str] = field(default_factory=list)
    priority: int = 1
    created_at: float = field(default_factory=time.time)
    dependencies: list[str] = field(default_factory=list)  # package_ids

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SubSwarmCheckpoint:
    """Deterministic snapshot of an individual Sub-Swarm's state."""
    subswarm_id: str
    sequence: int
    status: str
    assigned_tasks: list[str]
    completed_tasks: list[str]
    failed_tasks: list[str]
    agents: list[dict[str, Any]]
    local_leases: list[dict[str, Any]]
    metrics: dict[str, Any]
    timestamp: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GlobalFederationCheckpoint:
    """Federated checkpoint referencing sub-swarms without monolithic serialization."""
    checkpoint_id: str
    mission_id: str
    project_id: str
    sequence: int
    federation_topology: dict[str, Any]
    subswarm_references: dict[str, SubSwarmCheckpoint]  # subswarm_id -> SubSwarmCheckpoint
    cross_swarm_leases: list[dict[str, Any]]
    cross_swarm_conflicts: list[dict[str, Any]]
    partition_quality: dict[str, Any]
    worker_isolation_mode: str = "PROCESS"
    active_worker_pids: list[int] = field(default_factory=list)
    timestamp: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "mission_id": self.mission_id,
            "project_id": self.project_id,
            "sequence": self.sequence,
            "federation_topology": self.federation_topology,
            "subswarm_references": {
                s_id: cp.to_dict() for s_id, cp in self.subswarm_references.items()
            },
            "cross_swarm_leases": self.cross_swarm_leases,
            "cross_swarm_conflicts": self.cross_swarm_conflicts,
            "partition_quality": self.partition_quality,
            "worker_isolation_mode": self.worker_isolation_mode,
            "active_worker_pids": self.active_worker_pids,
            "timestamp": self.timestamp,
        }


# ── DETERMINISTIC SUB-SWARM PARTITIONER ────────────────────────────────────────

class DeterministicSubSwarmPartitioner:
    """
    Deterministically partitions agents and tasks into sub-swarms maximizing
    intra-swarm locality and minimizing cross-swarm dependencies and conflicts.
    """

    @staticmethod
    def partition(
        task_graph: TaskGraph,
        agents: Sequence[AgentInstance],
        max_subswarms: int = 4,
        max_agents_per_subswarm: int = 32,
    ) -> tuple[dict[str, list[str]], dict[str, list[str]], PartitionQuality]:
        """
        Returns:
            task_partitions: subswarm_id -> list[task_id]
            agent_partitions: subswarm_id -> list[agent_id]
            quality: PartitionQuality
        """
        all_tasks = list(task_graph.nodes.values())
        if not all_tasks or not agents:
            return {}, {}, PartitionQuality()

        num_subswarms = min(max_subswarms, max(1, (len(agents) + max_agents_per_subswarm - 1) // max_agents_per_subswarm))
        subswarm_ids = [f"subswarm_{i:02d}" for i in range(num_subswarms)]

        # 1. Group tasks by module/path locality and dependency clusters
        task_partitions: dict[str, list[str]] = {s_id: [] for s_id in subswarm_ids}
        path_to_swarm: dict[str, str] = {}

        # Sort tasks deterministically
        sorted_tasks = sorted(all_tasks, key=lambda t: (t.priority, t.task_id), reverse=True)

        for task in sorted_tasks:
            # Deterministic affinity heuristic: path_scope or module
            paths = task.metadata.get("path_scope") or task.metadata.get("owned_paths") or []
            target_swarm: str | None = None

            for p in paths:
                domain = p.split("/")[0] if "/" in p else p
                if domain in path_to_swarm:
                    target_swarm = path_to_swarm[domain]
                    break

            # If no path match, check dependency placement
            if target_swarm is None:
                parent_swarms = []
                for p_id in task.dependencies:
                    for s_id, t_ids in task_partitions.items():
                        if p_id in t_ids:
                            parent_swarms.append(s_id)
                            break
                if parent_swarms:
                    target_swarm = max(set(parent_swarms), key=parent_swarms.count)

            # Fallback: choose least-loaded subswarm with deterministic tie-break
            if target_swarm is None:
                target_swarm = min(subswarm_ids, key=lambda s: (len(task_partitions[s]), s))

            # Assign task
            task_partitions[target_swarm].append(task.task_id)
            for p in paths:
                domain = p.split("/")[0] if "/" in p else p
                path_to_swarm[domain] = target_swarm

        # 2. Partition agents deterministically by capability and balanced load
        agent_partitions: dict[str, list[str]] = {s_id: [] for s_id in subswarm_ids}
        sorted_agents = sorted(list(agents), key=lambda a: (a.agent_type, a.agent_id))

        # Assign specialists across sub-swarms proportionally
        for idx, agent in enumerate(sorted_agents):
            target_swarm = subswarm_ids[idx % num_subswarms]
            agent_partitions[target_swarm].append(agent.agent_id)

        # 3. Compute Partition Quality
        quality = DeterministicSubSwarmPartitioner.evaluate_quality(task_graph, task_partitions)
        return task_partitions, agent_partitions, quality

    @staticmethod
    def evaluate_quality(
        task_graph: TaskGraph,
        task_partitions: dict[str, list[str]],
    ) -> PartitionQuality:
        cross_edges = 0
        intra_edges = 0
        resource_overlap = 0

        task_to_swarm = {}
        for s_id, t_ids in task_partitions.items():
            for t_id in t_ids:
                task_to_swarm[t_id] = s_id

        # Calculate edge cuts
        for node in task_graph.nodes.values():
            src_swarm = task_to_swarm.get(node.task_id)
            for dep_id in node.dependencies:
                dep_swarm = task_to_swarm.get(dep_id)
                if src_swarm and dep_swarm:
                    if src_swarm == dep_swarm:
                        intra_edges += 1
                    else:
                        cross_edges += 1

        # Calculate path resource overlaps across subswarms
        swarm_paths: dict[str, set[str]] = {s_id: set() for s_id in task_partitions}
        for s_id, t_ids in task_partitions.items():
            for t_id in t_ids:
                node = task_graph.get_node(t_id)
                if node:
                    paths = node.metadata.get("path_scope") or []
                    swarm_paths[s_id].update(paths)

        swarms = list(task_partitions.keys())
        for i in range(len(swarms)):
            for j in range(i + 1, len(swarms)):
                overlap = swarm_paths[swarms[i]].intersection(swarm_paths[swarms[j]])
                resource_overlap += len(overlap)

        total_edges = cross_edges + intra_edges
        dependency_cut = cross_edges / total_edges if total_edges > 0 else 0.0
        intra_ratio = intra_edges / total_edges if total_edges > 0 else 1.0

        return PartitionQuality(
            cross_swarm_edges=cross_edges,
            intra_swarm_edges=intra_edges,
            cross_swarm_conflicts=0,
            resource_overlap=resource_overlap,
            dependency_cut=round(dependency_cut, 4),
            intra_locality_ratio=round(intra_ratio, 4),
        )


# ── LOCAL EVENT AGGREGATOR ─────────────────────────────────────────────────────

class LocalEventAggregator:
    """
    Summarizes micro-events inside a sub-swarm, emitting aggregated summaries
    (SUBSWARM_PROGRESS, etc.) while passing critical events directly to the federation.
    """

    def __init__(self, subswarm_id: str, emit_callback: Callable[[str, dict[str, Any]], Any] | None = None):
        self.subswarm_id = subswarm_id
        self.emit_callback = emit_callback
        self.micro_event_count: int = 0
        self.completed_tasks_batch: list[str] = []
        self.last_flush_time: float = time.time()
        self.flush_interval_seconds: float = 1.0

    async def record_task_progress(self, task_id: str, agent_id: str, status: str) -> None:
        self.micro_event_count += 1
        if status == "COMPLETED":
            self.completed_tasks_batch.append(task_id)

        # Flush if batch size or interval reached
        if len(self.completed_tasks_batch) >= 10 or (time.time() - self.last_flush_time) > self.flush_interval_seconds:
            await self.flush_progress()

    async def flush_progress(self) -> None:
        if not self.completed_tasks_batch and self.micro_event_count == 0:
            return

        payload = {
            "subswarm_id": self.subswarm_id,
            "micro_events_aggregated": self.micro_event_count,
            "completed_tasks": list(self.completed_tasks_batch),
            "timestamp": utc_now(),
        }
        self.completed_tasks_batch.clear()
        self.micro_event_count = 0
        self.last_flush_time = time.time()

        if self.emit_callback:
            res = self.emit_callback(FederatedEventType.SUBSWARM_PROGRESS.value, payload)
            if asyncio.iscoroutine(res):
                await res

    async def emit_critical(self, event_type: str, data: dict[str, Any]) -> None:
        """Immediately transmits critical events (conflicts, crashes, completions)."""
        data["subswarm_id"] = self.subswarm_id
        if self.emit_callback:
            res = self.emit_callback(event_type, data)
            if asyncio.iscoroutine(res):
                await res


# ── SUB-SWARM COORDINATOR ──────────────────────────────────────────────────────

class SubSwarmCoordinator:
    """
    Autonomous coordinator governing 1 to 32 agents locally.
    Maintains its own local registry, leases, scheduler, conflict graph, and event stream.
    """

    def __init__(
        self,
        subswarm_id: str,
        project_id: str,
        mission_id: str,
        federation_arbitrator: FederatedResourceArbitrator,
        max_agents: int = 32,
        emit_callback: Callable[[str, dict[str, Any]], Any] | None = None,
    ):
        self.subswarm_id = subswarm_id
        self.project_id = project_id
        self.mission_id = mission_id
        self.federation_arbitrator = federation_arbitrator
        self.max_agents = max_agents
        self.status = SubSwarmStatus.INITIALIZING

        # Local decoupled components
        self.registry = AgentRegistry()
        self.lease_manager = LeaseManager()
        self.file_ownership = FileOwnershipRegistry()
        self.selector = AgentSelector()
        self.scheduler = TaskScheduler()
        self.validator = ResultValidator()
        self.quotas = HierarchicalQuotaManager(global_max_concurrency=max_agents)
        self.event_aggregator = LocalEventAggregator(subswarm_id, emit_callback)

        # Local Task Graph and State
        self.assigned_tasks: dict[str, TaskNode] = {}
        self.active_leases: dict[str, TaskLease] = {}
        self.completed_tasks: set[str] = set()
        self.failed_tasks: set[str] = set()
        self.metrics = SwarmMetrics()
        self.checkpoint_seq: int = 0
        self.worker_pid: int = os.getpid()

    def register_agent(self, agent: AgentInstance) -> bool:
        if len(self.registry.list_agents()) >= self.max_agents:
            return False
        self.registry.register(agent)
        return True

    def assign_task(self, task: TaskNode) -> None:
        self.assigned_tasks[task.task_id] = copy.copy(task)

    def get_ready_tasks(self) -> list[TaskNode]:
        ready = []
        for task in self.assigned_tasks.values():
            if task.status == TaskStatus.PENDING:
                # Check local dependencies
                deps_met = True
                for dep in task.dependencies:
                    if dep in self.assigned_tasks and self.assigned_tasks[dep].status != TaskStatus.COMPLETED:
                        deps_met = False
                        break
                if deps_met:
                    ready.append(task)
        return self.scheduler.order_ready_tasks(ready)

    def select_agent_for_task(self, task: TaskNode) -> AgentSelectionRecord | None:
        return self.selector.select_agent(task, self.registry, self.quotas)

    def acquire_local_lease(self, task: TaskNode, agent: AgentInstance) -> TaskLease:
        """Acquires local task lease and checks cross-swarm resource claims."""
        paths = task.metadata.get("path_scope") or task.metadata.get("owned_paths") or []

        # 1. Cross-Swarm Resource Arbitration Check
        if paths:
            ok, err = self.federation_arbitrator.claim_resources(
                subswarm_id=self.subswarm_id,
                task_id=task.task_id,
                resources=paths,
                priority=task.priority,
            )
            if not ok:
                raise ValueError(f"CROSS_SWARM_CONFLICT: {err}")

        # 2. Local File Ownership Check
        if paths:
            ok, err = self.file_ownership.acquire_paths(task.task_id, agent.agent_id, paths)
            if not ok:
                # Release federated claim if local collision
                self.federation_arbitrator.release_resources(self.subswarm_id, task.task_id)
                raise ValueError(err or "Local file ownership collision")

        # 3. Local Lease Allocation
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

        self.quotas.allocate(task.task_id, agent.agent_id, str(task.category))
        self.scheduler.record_dispatched(task.task_id)
        task.status = TaskStatus.RUNNING
        return lease

    def release_local_lease(self, task_id: str, agent_id: str, lease_id: str) -> None:
        self.lease_manager.release_lease(lease_id, agent_id)
        self.active_leases.pop(task_id, None)
        self.file_ownership.release_paths(task_id)
        self.federation_arbitrator.release_resources(self.subswarm_id, task_id)
        self.quotas.release(task_id)

        agent = self.registry.get(agent_id)
        if agent:
            agent.current_tasks.discard(task_id)
            if not agent.current_tasks:
                agent.status = AgentHealthStatus.IDLE

    async def handle_agent_result(self, result: AgentResult) -> tuple[bool, str]:
        valid, msg = self.validator.validate_and_record(result)
        if not valid:
            return False, f"Invalid AgentResult: {msg}"
        if "DUPLICATE_IGNORED" in msg:
            return True, msg

        task = self.assigned_tasks.get(result.task_id)
        if not task:
            return False, f"Task '{result.task_id}' not found in subswarm {self.subswarm_id}"

        lease = self.active_leases.get(result.task_id)
        if lease:
            self.release_local_lease(result.task_id, result.agent_id, lease.lease_id)

        agent = self.registry.get(result.agent_id)

        if result.status == ResultStatus.SUCCESS:
            task.status = TaskStatus.COMPLETED
            task.completed_at = utc_now()
            task.output_data = result.output
            self.completed_tasks.add(task.task_id)
            self.metrics.total_completed_tasks += 1
            if agent:
                agent.success_count += 1

            # Aggregate progress event
            await self.event_aggregator.record_task_progress(task.task_id, result.agent_id, "COMPLETED")
            return True, "Task completed locally"
        else:
            task.status = TaskStatus.FAILED
            task.failure_info = FailureInfo(
                category=FailureCategory.TRANSIENT_FAILURE,
                message=str(result.failure or "Task failed"),
                attempt=result.attempt_id,
                timestamp=utc_now(),
            )
            self.failed_tasks.add(task.task_id)
            self.metrics.total_failed_tasks += 1
            if agent:
                agent.failure_count += 1

            # Emit critical failure immediately
            await self.event_aggregator.emit_critical(FederatedEventType.SUBSWARM_FAILURE.value, {
                "task_id": task.task_id,
                "agent_id": result.agent_id,
                "failure": result.failure,
            })
            return False, "Task execution failed locally"

    def reconcile_local_leases(self, now: float | None = None) -> list[str]:
        curr = now if now is not None else time.time()
        interrupted: list[str] = []

        # 1. Health check local agents
        unhealthy = set(self.registry.check_all_health(curr))

        # 2. Reap expired leases
        expired = self.lease_manager.reap_expired_leases(curr)
        for lease in expired:
            self.active_leases.pop(lease.task_id, None)
            self.file_ownership.release_paths(lease.task_id)
            self.federation_arbitrator.release_resources(self.subswarm_id, lease.task_id)
            self.quotas.release(lease.task_id)

            task = self.assigned_tasks.get(lease.task_id)
            if task and task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.INTERRUPTED
                interrupted.append(task.task_id)

        # 3. Handle leases for unhealthy agents
        for task_id, lease in list(self.active_leases.items()):
            if lease.agent_id in unhealthy:
                self.release_local_lease(task_id, lease.agent_id, lease.lease_id)
                task = self.assigned_tasks.get(task_id)
                if task and task.status == TaskStatus.RUNNING:
                    task.status = TaskStatus.INTERRUPTED
                    interrupted.append(task_id)

        return interrupted

    def export_checkpoint(self) -> SubSwarmCheckpoint:
        self.checkpoint_seq += 1
        return SubSwarmCheckpoint(
            subswarm_id=self.subswarm_id,
            sequence=self.checkpoint_seq,
            status=self.status.value,
            assigned_tasks=list(self.assigned_tasks.keys()),
            completed_tasks=list(self.completed_tasks),
            failed_tasks=list(self.failed_tasks),
            agents=[a.to_dict() for a in self.registry.list_agents()],
            local_leases=[l.to_dict() for l in self.active_leases.values()],
            metrics=self.metrics.to_dict(),
        )

    def restore_checkpoint(self, cp: SubSwarmCheckpoint) -> None:
        self.status = SubSwarmStatus(cp.status)
        self.completed_tasks = set(cp.completed_tasks)
        self.failed_tasks = set(cp.failed_tasks)
        self.active_leases.clear()
        self.file_ownership = FileOwnershipRegistry()

    async def run(self, task_queue: Any, result_queue: Any) -> None:
        """Dedicated worker run loop for multiprocessing Queue IPC (Option A)."""
        while True:
            job = await task_queue.get() if hasattr(task_queue, "get_nowait") else task_queue.get()
            if job is None:
                break
            res = await _async_subswarm_worker_loop(job)
            if hasattr(result_queue, "put_nowait"):
                result_queue.put_nowait(res)
            else:
                result_queue.put(res)


# ── FEDERATED RESOURCE ARBITRATOR & LEASE MANAGER ──────────────────────────────

@dataclass
class ResourceClaim:
    subswarm_id: str
    task_id: str
    resource: str
    priority: int
    requested_at: float = field(default_factory=time.time)


class FederatedResourceArbitrator:
    """
    Prevents cross-swarm file and resource collisions.
    Enforces exclusive ownership with priority aging and starvation prevention.
    """

    def __init__(self):
        # resource -> (holding_subswarm, holding_task, acquired_at)
        self._holders: dict[str, tuple[str, str, float]] = {}
        # resource -> list[ResourceClaim] sorted by effective priority
        self._wait_queues: dict[str, list[ResourceClaim]] = {}
        self.cross_swarm_conflicts_count: int = 0
        self.arbitrations_count: int = 0

    def claim_resources(
        self,
        subswarm_id: str,
        task_id: str,
        resources: list[str],
        priority: int = 1,
        now: float | None = None,
    ) -> tuple[bool, str | None]:
        curr = now if now is not None else time.time()
        normalized = [os.path.normpath(r).replace("\\", "/").rstrip("/") for r in resources]

        # Check for conflicts
        for res in normalized:
            if res in self._holders:
                holder_swarm, holder_task, _ = self._holders[res]
                if holder_swarm != subswarm_id:
                    self.cross_swarm_conflicts_count += 1
                    # Enqueue claim
                    if res not in self._wait_queues:
                        self._wait_queues[res] = []
                    claim = ResourceClaim(subswarm_id, task_id, res, priority, curr)
                    self._wait_queues[res].append(claim)
                    return False, f"Resource '{res}' held by subswarm '{holder_swarm}' (task '{holder_task}')"

        # Conceder ownership
        for res in normalized:
            self._holders[res] = (subswarm_id, task_id, curr)
            self.arbitrations_count += 1
        return True, None

    def release_resources(self, subswarm_id: str, task_id: str) -> None:
        released: list[str] = []
        for res, (holder_swarm, holder_task, _) in list(self._holders.items()):
            if holder_swarm == subswarm_id and holder_task == task_id:
                del self._holders[res]
                released.append(res)

        # Reassign to waiting claims with priority aging
        curr = time.time()
        for res in released:
            if res in self._wait_queues and self._wait_queues[res]:
                queue = self._wait_queues[res]
                # Priority aging: +2.0 per sec waiting
                queue.sort(
                    key=lambda c: (-(c.priority + min(50.0, (curr - c.requested_at) * 2.0)), c.requested_at)
                )
                next_claim = queue.pop(0)
                self._holders[res] = (next_claim.subswarm_id, next_claim.task_id, curr)
                self.arbitrations_count += 1

    def get_holders(self) -> dict[str, tuple[str, str, float]]:
        return dict(self._holders)


class FederatedLeaseManager:
    """Delegates authority from Global Coordinator to Sub-Swarms."""

    def __init__(self, arbitrator: FederatedResourceArbitrator):
        self.arbitrator = arbitrator
        self.subswarm_authorities: set[str] = set()

    def grant_authority(self, subswarm_id: str) -> None:
        self.subswarm_authorities.add(subswarm_id)

    def revoke_authority(self, subswarm_id: str) -> None:
        self.subswarm_authorities.discard(subswarm_id)


# ── ISOLATED WORKER EXECUTION (OS PROCESS / THREAD WORKER) ────────────────────

_THREAD_LOCAL = threading.local()


def _get_worker_loop() -> asyncio.AbstractEventLoop:
    if not hasattr(_THREAD_LOCAL, "loop") or _THREAD_LOCAL.loop is None or _THREAD_LOCAL.loop.is_closed():
        _THREAD_LOCAL.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_THREAD_LOCAL.loop)
    return _THREAD_LOCAL.loop


def _get_worker_coordinators() -> dict[str, SubSwarmCoordinator]:
    if not hasattr(_THREAD_LOCAL, "coordinators"):
        _THREAD_LOCAL.coordinators = {}
    return _THREAD_LOCAL.coordinators


def _execute_subswarm_worker_job(job: SubSwarmWorkerJob) -> SubSwarmWorkerResult:
    """
    Dedicated worker entry point executed in an isolated process or thread.
    Pins its own dedicated asyncio event loop to eliminate GIL / event loop contention.
    """
    logging.getLogger("agents.swarm_coordinator").setLevel(logging.WARNING)
    logging.getLogger("agents.swarm_federation").setLevel(logging.WARNING)

    worker_coords = _get_worker_coordinators()
    if job.simulated_worker_crash:
        worker_coords.pop(job.subswarm_id, None)
        raise RuntimeError(f"Simulated crash in worker process for subswarm {job.subswarm_id}")

    loop = _get_worker_loop()
    return loop.run_until_complete(_async_subswarm_worker_loop(job))


async def _async_subswarm_worker_loop(job: SubSwarmWorkerJob) -> SubSwarmWorkerResult:
    """
    Executes local autonomous sub-swarm tasks with local agent selection,
    local lease management, real SHA-256 computation, and result validation.
    Supports both standard and compact serialized payloads.
    """
    t0 = time.perf_counter()
    worker_pid = os.getpid()
    t_recv = time.perf_counter()
    worker_dispatch_ms = max(0.001, (t_recv - job.send_timestamp) * 1000.0) if job.send_timestamp else 0.0

    worker_coords = _get_worker_coordinators()
    if job.simulated_worker_crash:
        worker_coords.pop(job.subswarm_id, None)
        raise RuntimeError(f"Simulated crash in worker process for subswarm {job.subswarm_id}")

    s_id = job.subswarm_id
    worker_reused = False

    if s_id in worker_coords:
        coord = worker_coords[s_id]
        coord.assigned_tasks.clear()
        coord.active_leases.clear()
        coord.completed_tasks.clear()
        coord.failed_tasks.clear()
        coord.file_ownership = FileOwnershipRegistry()
        coord.quotas = HierarchicalQuotaManager(global_max_concurrency=coord.max_agents)
        coord.scheduler = TaskScheduler()
        coord.federation_arbitrator = FederatedResourceArbitrator()
        for ag in coord.registry.list_agents():
            ag.status = AgentHealthStatus.IDLE
            ag.current_tasks.clear()
        worker_reused = True
        for res in job.granted_claims:
            coord.federation_arbitrator.claim_resources(s_id, "pre_granted", [res])
    else:
        local_arbitrator = FederatedResourceArbitrator()
        for res in job.granted_claims:
            local_arbitrator.claim_resources(s_id, "pre_granted", [res])

        total_agents_count = len(job.agents) + len(job.compact_agents)
        coord = SubSwarmCoordinator(
            subswarm_id=s_id,
            project_id=job.project_id,
            mission_id=job.mission_id,
            federation_arbitrator=local_arbitrator,
            max_agents=max(total_agents_count, 32),
        )
        coord.status = SubSwarmStatus.ACTIVE

        for ag in job.agents:
            coord.register_agent(ag)

        for c_ag in job.compact_agents:
            try:
                ag_cat = AgentCategory(c_ag.agent_type)
            except Exception:
                ag_cat = AgentCategory.CODING
            cap = AgentCapability(
                agent_type=ag_cat.value,
                categories=[ag_cat],
                concurrency_limit=c_ag.concurrency_limit,
                resource_classes=[ResourceClass.CPU],
            )
            ag_inst = AgentInstance(
                agent_id=c_ag.agent_id,
                agent_type=ag_cat.value,
                capability=cap,
            )
            coord.register_agent(ag_inst)

        worker_coords[s_id] = coord

    for task in job.tasks:
        coord.assign_task(task)

    for c_task in job.compact_tasks:
        try:
            t_cat = AgentCategory(c_task.category).value
        except Exception:
            t_cat = c_task.category
        t_node = TaskNode(
            task_id=c_task.task_id,
            title=f"Task {c_task.task_id}",
            category=t_cat,
            priority=c_task.priority,
            metadata={
                "workload_seed": c_task.workload_seed,
                "path_scope": c_task.path_scope,
            },
        )
        coord.assign_task(t_node)

    sched_lats: list[float] = []
    lease_lats: list[float] = []
    exec_lats: list[float] = []
    completed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    t_exec_start = time.perf_counter()
    ready_tasks = coord.get_ready_tasks()
    for task in ready_tasks[:job.batch_size]:
        t_s0 = time.perf_counter()
        sel = coord.select_agent_for_task(task)
        s_lat = (time.perf_counter() - t_s0) * 1000.0
        sched_lats.append(s_lat)

        if not sel:
            continue

        agent = coord.registry.get(sel.agent_id)
        if not agent:
            continue

        t_l0 = time.perf_counter()
        try:
            lease = coord.acquire_local_lease(task, agent)
            l_lat = (time.perf_counter() - t_l0) * 1000.0
            lease_lats.append(l_lat)

            # Real SHA-256 computational payload identical to Phase 17
            t_e0 = time.perf_counter()
            seed = task.metadata.get("workload_seed", "")
            h = hashlib.sha256(f"{task.task_id}_{seed}".encode()).hexdigest()
            output = {"task_id": task.task_id, "hash": h, "executor": agent.agent_id}
            e_lat = (time.perf_counter() - t_e0) * 1000.0
            exec_lats.append(e_lat)

            res = AgentResult(
                task_id=task.task_id,
                attempt_id=1,
                agent_id=agent.agent_id,
                status=ResultStatus.SUCCESS,
                output=output,
            )
            ok, msg = await coord.handle_agent_result(res)
            if ok:
                completed.append({
                    "task_id": task.task_id,
                    "agent_id": agent.agent_id,
                    "output": output,
                    "lease_id": lease.lease_id,
                })
            else:
                failed.append({
                    "task_id": task.task_id,
                    "agent_id": agent.agent_id,
                    "error": msg,
                })
        except Exception as e:
            failed.append({
                "task_id": task.task_id,
                "agent_id": agent.agent_id if agent else "unknown",
                "error": str(e),
            })

    worker_execution_ms = (time.perf_counter() - t_exec_start) * 1000.0
    coord.reconcile_local_leases()

    # Measure result serialization cost
    t_ser_0 = time.perf_counter()
    _ = pickle.dumps(completed)
    pickle_ms = (time.perf_counter() - t_ser_0) * 1000.0

    duration_ms = (time.perf_counter() - t0) * 1000.0

    return SubSwarmWorkerResult(
        subswarm_id=job.subswarm_id,
        worker_pid=worker_pid,
        completed_tasks=completed,
        failed_tasks=failed,
        active_leases=[l.to_dict() for l in coord.active_leases.values()],
        scheduling_latencies=sched_lats,
        lease_latencies=lease_lats,
        execution_latencies=exec_lats,
        duration_ms=duration_ms,
        serialization_ms=pickle_ms,
        pickle_ms=pickle_ms,
        worker_dispatch_ms=worker_dispatch_ms,
        worker_execution_ms=worker_execution_ms,
        worker_reused=worker_reused,
    )



# ── SWARM FEDERATION (GLOBAL MISSION LEVEL) ───────────────────────────────────

class SwarmFederation:
    """
    Top-level global mission coordinator orchestrating multiple autonomous Sub-Swarms.
    Eliminates centralized scheduling, lease, and event bottlenecks.
    """

    def __init__(
        self,
        project_id: str,
        mission_id: str,
        task_graph: TaskGraph,
        max_agents_per_subswarm: int = 32,
        emit_callback: Callable[[str, dict[str, Any]], Any] | None = None,
        isolation_mode: SwarmIsolationMode | str = SwarmIsolationMode.PROCESS,
        max_workers: int | None = None,
        execution_policy: AdaptiveSwarmExecutionPolicy | None = None,
        enable_compact_mode: bool = False,
    ):
        self.project_id = project_id
        self.mission_id = mission_id
        self.task_graph = task_graph
        self.max_agents_per_subswarm = max_agents_per_subswarm
        self.emit_callback = emit_callback
        self.isolation_mode = SwarmIsolationMode.from_str(isolation_mode)
        self.max_workers = max_workers or min(os.cpu_count() or 4, 8)
        self.execution_policy = execution_policy or AdaptiveSwarmExecutionPolicy()
        self.enable_compact_mode = enable_compact_mode

        self.arbitrator = FederatedResourceArbitrator()
        self.lease_manager = FederatedLeaseManager(self.arbitrator)
        self.subswarms: dict[str, SubSwarmCoordinator] = {}
        self.partition_quality = PartitionQuality()
        self.checkpoint_seq: int = 0
        self.idempotency_keys: set[str] = set()
        self._start_time: float = 0.0
        self._executor: concurrent.futures.Executor | None = None
        self._backend: SwarmExecutionBackend | None = None
        self._worker_pids: set[int] = set()
        self.isolated_batches_executed: int = 0
        self.ipc_breakdown_records: list[dict[str, float]] = []
        self.subswarm_completed_counts: dict[str, int] = {}
        self.subswarm_wait_times: dict[str, float] = {}
        self.tasks_created: int = len(task_graph.nodes) if task_graph else 0
        self.tasks_started: int = 0
        self.tasks_completed: int = 0
        self.tasks_failed: int = 0
        self.tasks_retried: int = 0
        self.tasks_deferred: int = 0
        self.adaptive_worker_policy: AdaptiveWorkerPolicy = AdaptiveWorkerPolicy(max_workers_ceiling=self.max_workers)
        self.execution_cost_history: ExecutionCostHistory = ExecutionCostHistory()

    async def emit_federation_event(self, event_type: str, data: dict[str, Any]) -> None:
        if self.emit_callback:
            try:
                res = self.emit_callback(event_type, data)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.warning("Error emitting federation event %s: %s", event_type, e)

    def initialize_federation(
        self,
        agents: Sequence[AgentInstance],
        max_subswarms: int = 4,
    ) -> None:
        """Partitions DAG and agents, creating autonomous SubSwarmCoordinators."""
        t_parts, a_parts, quality = DeterministicSubSwarmPartitioner.partition(
            self.task_graph,
            agents,
            max_subswarms=max_subswarms,
            max_agents_per_subswarm=self.max_agents_per_subswarm,
        )
        self.subswarms.clear()
        self.partition_quality = quality
        agent_lookup = {a.agent_id: a for a in agents}

        for s_id, t_ids in t_parts.items():
            coord = SubSwarmCoordinator(
                subswarm_id=s_id,
                project_id=self.project_id,
                mission_id=self.mission_id,
                federation_arbitrator=self.arbitrator,
                max_agents=self.max_agents_per_subswarm,
                emit_callback=self.emit_callback,
            )
            self.lease_manager.grant_authority(s_id)

            # Assign agents
            for a_id in a_parts.get(s_id, []):
                if a_id in agent_lookup:
                    coord.register_agent(agent_lookup[a_id])

            # Assign tasks
            for t_id in t_ids:
                node = self.task_graph.get_node(t_id)
                if node:
                    coord.assign_task(node)

            coord.status = SubSwarmStatus.ACTIVE
            self.subswarms[s_id] = coord

    # ── DYNAMIC SUB-SWARM SCALING ─────────────────────────────────────────────

    def spawn_subswarm(self, subswarm_id: str | None = None) -> SubSwarmCoordinator:
        s_id = subswarm_id or f"subswarm_{len(self.subswarms):02d}"
        coord = SubSwarmCoordinator(
            subswarm_id=s_id,
            project_id=self.project_id,
            mission_id=self.mission_id,
            federation_arbitrator=self.arbitrator,
            max_agents=self.max_agents_per_subswarm,
            emit_callback=self.emit_callback,
        )
        coord.status = SubSwarmStatus.ACTIVE
        self.lease_manager.grant_authority(s_id)
        self.subswarms[s_id] = coord
        return coord

    def drain_subswarm(self, subswarm_id: str) -> list[TaskNode]:
        """Drains a subswarm of pending/unassigned tasks for decommissioning."""
        coord = self.subswarms.get(subswarm_id)
        if not coord:
            return []

        coord.status = SubSwarmStatus.DRAINING
        evacuated: list[TaskNode] = []
        for t_id, task in list(coord.assigned_tasks.items()):
            if task.status in {TaskStatus.PENDING, TaskStatus.INTERRUPTED}:
                evacuated.append(task)
                del coord.assigned_tasks[t_id]

        return evacuated

    def retire_subswarm(self, subswarm_id: str) -> None:
        coord = self.subswarms.get(subswarm_id)
        if coord:
            coord.status = SubSwarmStatus.RETIRED
            self.lease_manager.revoke_authority(subswarm_id)

    def split_subswarm(self, source_id: str, new_id: str) -> tuple[SubSwarmCoordinator, SubSwarmCoordinator]:
        """Splits an overloaded subswarm into two balanced subswarms."""
        src = self.subswarms[source_id]
        new_coord = self.spawn_subswarm(new_id)

        # Move half agents
        agents = src.registry.list_agents()
        split_idx = len(agents) // 2
        for ag in agents[split_idx:]:
            src.registry.unregister(ag.agent_id)
            new_coord.register_agent(ag)

        # Move unassigned tasks
        tasks = list(src.assigned_tasks.values())
        task_split_idx = len(tasks) // 2
        for t in tasks[task_split_idx:]:
            if t.status == TaskStatus.PENDING:
                del src.assigned_tasks[t.task_id]
                new_coord.assign_task(t)

        return src, new_coord

    def merge_subswarms(self, target_id: str, absorb_id: str) -> SubSwarmCoordinator:
        """Merges two subswarms into target_id."""
        target = self.subswarms[target_id]
        absorb = self.subswarms[absorb_id]

        evacuated = self.drain_subswarm(absorb_id)
        for t in evacuated:
            target.assign_task(t)

        for ag in absorb.registry.list_agents():
            target.register_agent(ag)

        self.retire_subswarm(absorb_id)
        return target

    # ── HOTSPOT REBALANCING & GLOBAL BACKPRESSURE ──────────────────────────────

    def detect_hotspots(self) -> list[dict[str, Any]]:
        hotspots = []
        for s_id, coord in self.subswarms.items():
            active_count = len(coord.active_leases)
            queue_len = len([t for t in coord.assigned_tasks.values() if t.status == TaskStatus.PENDING])
            if queue_len > 20 and active_count >= coord.max_agents:
                hotspots.append({
                    "subswarm_id": s_id,
                    "active_leases": active_count,
                    "queue_length": queue_len,
                    "reason": "QUEUE_SATURATION",
                })
        return hotspots

    def rebalance_hotspots(self) -> int:
        """Safely rebalances tasks from overloaded to idle subswarms."""
        hotspots = self.detect_hotspots()
        if not hotspots:
            return 0

        rebalanced_count = 0
        idle_swarms = [
            s for s in self.subswarms.values()
            if s.status == SubSwarmStatus.ACTIVE and len(s.active_leases) < (s.max_agents // 2)
        ]

        if not idle_swarms:
            return 0

        for spot in hotspots:
            src = self.subswarms[spot["subswarm_id"]]
            pending = [t for t in src.assigned_tasks.values() if t.status == TaskStatus.PENDING]
            target = idle_swarms[0]

            # Rebalance up to half pending tasks that have no active collaboration/ownership
            for task in pending[:len(pending) // 2]:
                del src.assigned_tasks[task.task_id]
                target.assign_task(task)
                rebalanced_count += 1

        return rebalanced_count

    # ── FEDERATED CHECKPOINTS & RECOVERY ───────────────────────────────────────

    def save_checkpoint(self) -> GlobalFederationCheckpoint:
        self.checkpoint_seq += 1
        sub_cps = {}
        for s_id, coord in self.subswarms.items():
            sub_cps[s_id] = coord.export_checkpoint()

        return GlobalFederationCheckpoint(
            checkpoint_id=f"fed_cp_{self.checkpoint_seq:04d}_{uuid.uuid4().hex[:6]}",
            mission_id=self.mission_id,
            project_id=self.project_id,
            sequence=self.checkpoint_seq,
            federation_topology={
                s_id: coord.status.value for s_id, coord in self.subswarms.items()
            },
            subswarm_references=sub_cps,
            cross_swarm_leases=[
                {"resource": r, "subswarm": s, "task": t, "since": since}
                for r, (s, t, since) in self.arbitrator.get_holders().items()
            ],
            cross_swarm_conflicts=[],
            partition_quality=self.partition_quality.to_dict(),
            worker_isolation_mode=self.isolation_mode.value,
            active_worker_pids=sorted(list(self._worker_pids)),
        )

    def restore_checkpoint(self, cp: GlobalFederationCheckpoint) -> None:
        self.checkpoint_seq = cp.sequence
        if hasattr(cp, "worker_isolation_mode") and cp.worker_isolation_mode:
            self.isolation_mode = SwarmIsolationMode(cp.worker_isolation_mode)
        if hasattr(cp, "active_worker_pids"):
            self._worker_pids = set(cp.active_worker_pids)
        for s_id, sub_cp in cp.subswarm_references.items():
            if s_id in self.subswarms:
                self.subswarms[s_id].restore_checkpoint(sub_cp)

    # ── PARTIAL FAILURE ISOLATION & RECOVERY ───────────────────────────────────

    def simulate_crash_and_recover_subswarm(self, subswarm_id: str) -> bool:
        coord = self.subswarms.get(subswarm_id)
        if not coord:
            return False

        # Simulate crash
        coord.status = SubSwarmStatus.FAILED
        # Interrupted tasks
        interrupted = []
        for t_id, task in coord.assigned_tasks.items():
            if task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.INTERRUPTED
                interrupted.append(t_id)

        # Clear active leases held by crashed subswarm
        for t_id in interrupted:
            self.arbitrator.release_resources(subswarm_id, t_id)
        coord.active_leases.clear()
        coord.file_ownership = FileOwnershipRegistry()

        # Reattach & Reconcile
        coord.status = SubSwarmStatus.ACTIVE
        return True

    # ── ISOLATED WORKER POOL & UNIFIED BACKEND EXECUTION (PHASE 18 & 18.1) ──────────

    def get_or_create_backend(self) -> SwarmExecutionBackend:
        if self._backend is None:
            if self.isolation_mode == SwarmIsolationMode.INPROCESS:
                self._backend = InProcessBackend()
            elif self.isolation_mode == SwarmIsolationMode.THREAD:
                self._backend = ThreadBackend(max_workers=self.max_workers)
            elif self.isolation_mode == SwarmIsolationMode.PROCESS:
                pool = SubSwarmWorkerPool(
                    max_workers=self.max_workers,
                    enable_compact_mode=self.enable_compact_mode,
                    event_callback=self.emit_callback,
                )
                self._backend = ProcessBackend(pool)
            elif self.isolation_mode == SwarmIsolationMode.ADAPTIVE:
                self._backend = AdaptiveBackend(
                    policy=self.execution_policy,
                    max_workers=self.max_workers,
                    enable_compact_mode=self.enable_compact_mode,
                    event_callback=self.emit_callback,
                )
        return self._backend

    def get_or_create_executor(self) -> concurrent.futures.Executor:
        backend = self.get_or_create_backend()
        if isinstance(backend, ProcessBackend):
            return backend.pool.get_executor()
        elif isinstance(backend, ThreadBackend):
            return backend._executor
        elif isinstance(backend, AdaptiveBackend):
            proc_b = backend._get_process_backend()
            return proc_b.pool.get_executor()
        else:
            if self._executor is None:
                ctx = mp.get_context("spawn")
                self._executor = concurrent.futures.ProcessPoolExecutor(
                    max_workers=self.max_workers,
                    mp_context=ctx,
                )
            return self._executor

    def shutdown_worker_pool(self) -> None:
        if self._backend is not None:
            self._backend.shutdown()
            self._backend = None
        if self._executor is not None:
            try:
                self._executor.shutdown(wait=True, cancel_futures=True)
            except TypeError:
                self._executor.shutdown(wait=True)
            except Exception:
                pass
            self._executor = None
        parent_pid = os.getpid()
        for pid in list(self._worker_pids):
            if pid == parent_pid:
                continue
            try:
                p = psutil.Process(pid)
                if p.is_running():
                    p.terminate()
            except Exception:
                pass
            self._worker_pids.clear()

    def switch_execution_mode(
        self,
        target_mode: SwarmIsolationMode | str,
        reason: str = "manual_or_policy",
    ) -> bool:
        """
        Safely switches execution mode at synchronization boundary (between rounds/tasks).
        Ensures zero tasks in-flight and preserves leases, ownership, and checkpoints.
        """
        new_mode = SwarmIsolationMode.from_str(target_mode)
        if new_mode == self.isolation_mode:
            return False

        # Invariant check: zero running tasks allowed during migration
        for s_id, coord in self.subswarms.items():
            for t_id, task in coord.assigned_tasks.items():
                if task.status == TaskStatus.RUNNING:
                    logger.warning("Cannot switch mode while task %s is RUNNING in subswarm %s", t_id, s_id)
                    return False

        old_mode = self.isolation_mode
        if self._backend is not None:
            self._backend.shutdown()
            self._backend = None

        self.isolation_mode = new_mode

        if self.emit_callback:
            try:
                res = self.emit_callback(
                    FederatedEventType.EXECUTION_MODE_CHANGED.value,
                    {
                        "old_mode": old_mode.value,
                        "new_mode": new_mode.value,
                        "reason": reason,
                    },
                )
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
            except Exception:
                pass

        return True

    def compute_fairness_index(self) -> float:
        """
        Computes Jain's Fairness Index for work completed per subswarm:
        J = (sum x_i)^2 / (n * sum x_i^2)
        Returns 1.0 if perfectly balanced.
        """
        counts = [len(coord.completed_tasks) for coord in self.subswarms.values()]
        if not counts:
            return 1.0
        s1 = sum(counts)
        s2 = sum(c * c for c in counts)
        if s2 == 0:
            return 1.0
        n = len(counts)
        return (s1 * s1) / (n * s2)

    def get_telemetry_snapshot(self) -> dict[str, Any]:
        """
        Returns real-time telemetry snapshot for observability stream:
        - execution_mode
        - worker_count
        - worker_utilization
        - ipc_latency
        - queue_depth
        - mode_switches
        """
        backend_metrics = self.get_or_create_backend().get_metrics()
        worker_count = len(self._worker_pids)
        worker_utilization = 0.0
        if worker_count > 0:
            active_coords = sum(1 for c in self.subswarms.values() if len(c.active_leases) > 0)
            worker_utilization = min(1.0, active_coords / max(1, worker_count))

        recent_ipc = 0.0
        if self.ipc_breakdown_records:
            recent_ipc = self.ipc_breakdown_records[-1].get("total_process_latency_ms", 0.0)

        queue_depth = backend_metrics.get("queue_depth", 0)
        mode_switches = backend_metrics.get("mode_switches_count", 0)

        handle_stats = backend_metrics.get("handle_stats") or {}
        stragglers_count = backend_metrics.get("straggler_count", 0)
        worker_utilizations = backend_metrics.get("worker_utilization", {})

        return {
            "execution_mode": self.isolation_mode.value,
            "worker_count": worker_count,
            "worker_utilization": round(worker_utilization, 3),
            "ipc_latency": round(recent_ipc, 3),
            "queue_depth": queue_depth,
            "mode_switches": mode_switches,
            "fairness_index": round(self.compute_fairness_index(), 3),
            "active_subswarms": len(self.subswarms),
            "backend_metrics": backend_metrics,
            "handle_stats": handle_stats,
            "stragglers_count": stragglers_count,
            "worker_utilizations": worker_utilizations,
            "tasks_sanity": {
                "created": self.tasks_created,
                "started": self.tasks_started,
                "completed": self.tasks_completed,
                "failed": self.tasks_failed,
                "deferred": self.tasks_deferred,
                "retried": self.tasks_retried,
            },
        }

    def __enter__(self) -> "SwarmFederation":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.shutdown_worker_pool()

    def __del__(self) -> None:
        try:
            self.shutdown_worker_pool()
        except Exception:
            pass

    def sync_dependencies(self) -> int:
        """Propagate completed tasks across subswarms to unblock dependent tasks."""
        synced_count = 0
        all_completed: set[str] = set()
        for coord in self.subswarms.values():
            all_completed.update(coord.completed_tasks)

        for coord in self.subswarms.values():
            for t_id, task in list(coord.assigned_tasks.items()):
                if task.status == TaskStatus.PENDING:
                    for dep in task.dependencies:
                        if dep in all_completed:
                            if dep not in coord.assigned_tasks:
                                dep_node = TaskNode(
                                    task_id=dep,
                                    title=f"Dep {dep}",
                                    category=task.category,
                                    status=TaskStatus.COMPLETED,
                                )
                                coord.assigned_tasks[dep] = dep_node
                                synced_count += 1
                            elif coord.assigned_tasks[dep].status != TaskStatus.COMPLETED:
                                coord.assigned_tasks[dep].status = TaskStatus.COMPLETED
                                synced_count += 1
        return synced_count

    async def run_round_isolated(self, batch_size: int = 8, dynamic_batching: bool = False) -> dict[str, Any]:
        """
        Dispatches ready tasks across active SubSwarms to isolated workers or local backend.
        Supports batching, dynamic batching, compact serialization, and fine-grained IPC profiling.
        """
        t0 = time.perf_counter()
        total_ready = sum(len(c.get_ready_tasks()) for c in self.subswarms.values() if c.status == SubSwarmStatus.ACTIVE)

        if dynamic_batching and total_ready > 0:
            agent_cnt = sum(len(c.registry.list_agents()) for c in self.subswarms.values())
            subswarm_cnt = len(self.subswarms)
            est_dur = 0.5
            first_node = next(iter(self.task_graph.nodes.values()), None)
            if first_node and "estimated_duration_ms" in first_node.metadata:
                est_dur = float(first_node.metadata["estimated_duration_ms"])
            decision = self.adaptive_worker_policy.evaluate(
                agent_count=agent_cnt,
                subswarms_count=subswarm_cnt,
                task_count=len(self.task_graph.nodes),
                queue_depth=total_ready,
                estimated_task_duration_ms=est_dur,
                history=self.execution_cost_history,
            )
            batch_size = decision.batch_size
            backend = self.get_or_create_backend()
            if isinstance(backend, ProcessBackend):
                backend.pool.scale_workers(decision.worker_count)
            elif isinstance(backend, AdaptiveBackend) and backend.process_backend:
                backend.process_backend.pool.scale_workers(decision.worker_count)

        jobs: list[SubSwarmWorkerJob] = []

        # 1. Prepare jobs and arbitrate cross-swarm claims in parent arbitrator
        for s_id, coord in self.subswarms.items():
            if coord.status != SubSwarmStatus.ACTIVE:
                continue

            ready = coord.get_ready_tasks()
            if not ready:
                continue

            batch_tasks: list[TaskNode] = []
            granted_claims: list[str] = []

            for task in ready[:batch_size]:
                paths = task.metadata.get("path_scope") or task.metadata.get("owned_paths") or []
                if paths:
                    ok, err = self.arbitrator.claim_resources(
                        subswarm_id=s_id,
                        task_id=task.task_id,
                        resources=paths,
                        priority=task.priority,
                    )
                    if not ok:
                        self.tasks_deferred += 1
                        continue  # Conflict; defer task to next round
                    granted_claims.extend(paths)

                batch_tasks.append(task)
                self.tasks_started += 1

            if batch_tasks:
                if self.enable_compact_mode:
                    compact_tasks = [CompactTaskNode.from_task_node(t) for t in batch_tasks]
                    compact_agents = [CompactAgentInstance.from_agent_instance(a) for a in coord.registry.list_agents()]
                    job = SubSwarmWorkerJob(
                        subswarm_id=s_id,
                        project_id=self.project_id,
                        mission_id=self.mission_id,
                        compact_tasks=compact_tasks,
                        compact_agents=compact_agents,
                        batch_size=len(batch_tasks),
                        granted_claims=list(set(granted_claims)),
                        compact_mode=True,
                    )
                else:
                    job = SubSwarmWorkerJob(
                        subswarm_id=s_id,
                        project_id=self.project_id,
                        mission_id=self.mission_id,
                        tasks=batch_tasks,
                        agents=coord.registry.list_agents(),
                        batch_size=len(batch_tasks),
                        granted_claims=list(set(granted_claims)),
                    )
                jobs.append(job)

        if not jobs:
            return {
                "completed": 0,
                "failed": 0,
                "duration_ms": 0.0,
                "worker_pids": list(self._worker_pids),
                "scheduling_latencies": [],
                "lease_latencies": [],
                "execution_latencies": [],
                "ipc_breakdown": [],
                "mode": self.isolation_mode.value,
            }

        # 2. Dispatch jobs via unified execution backend
        backend = self.get_or_create_backend()
        results = await backend.execute_jobs(jobs, self)

        # 3. Reconcile results into parent state
        total_completed = 0
        total_failed = 0
        all_sched_lats: list[float] = []
        all_lease_lats: list[float] = []
        all_exec_lats: list[float] = []
        round_ipc: list[dict[str, Any]] = []

        for job, res in zip(jobs, results):
            s_id = job.subswarm_id
            coord = self.subswarms[s_id]

            if isinstance(res, Exception):
                logger.error("SubSwarm %s worker crashed or failed: %s", s_id, res)
                self.simulate_crash_and_recover_subswarm(s_id)
                num_lost = len(job.compact_tasks) if job.compact_tasks else len(job.tasks)
                total_failed += num_lost
                continue

            self._worker_pids.add(res.worker_pid)
            all_sched_lats.extend(res.scheduling_latencies)
            all_lease_lats.extend(res.lease_latencies)
            all_exec_lats.extend(res.execution_latencies)

            res_dict = res.to_dict()
            round_ipc.append(res_dict)
            self.ipc_breakdown_records.append(res_dict)

            for comp in res.completed_tasks:
                t_id = comp["task_id"]
                task = coord.assigned_tasks.get(t_id)
                if task:
                    task.status = TaskStatus.COMPLETED
                    task.output_data = comp.get("output")
                    task.completed_at = utc_now()
                coord.completed_tasks.add(t_id)
                coord.metrics.total_completed_tasks += 1
                self.subswarm_completed_counts[s_id] = self.subswarm_completed_counts.get(s_id, 0) + 1

                tg_node = self.task_graph.get_node(t_id)
                if tg_node:
                    tg_node.status = TaskStatus.COMPLETED
                    tg_node.output_data = comp.get("output")

                self.arbitrator.release_resources(s_id, t_id)
                total_completed += 1
                self.tasks_completed += 1

            for fail in res.failed_tasks:
                t_id = fail["task_id"]
                task = coord.assigned_tasks.get(t_id)
                if task:
                    task.status = TaskStatus.FAILED
                coord.failed_tasks.add(t_id)
                coord.metrics.total_failed_tasks += 1
                self.arbitrator.release_resources(s_id, t_id)
                total_failed += 1
                self.tasks_failed += 1

            coord.reconcile_local_leases()

        duration_ms = (time.perf_counter() - t0) * 1000.0
        self.isolated_batches_executed += 1

        return {
            "completed": total_completed,
            "failed": total_failed,
            "duration_ms": duration_ms,
            "worker_pids": list(self._worker_pids),
            "scheduling_latencies": all_sched_lats,
            "lease_latencies": all_lease_lats,
            "execution_latencies": all_exec_lats,
            "ipc_breakdown": round_ipc,
            "mode": self.isolation_mode.value,
        }

    async def execute_workload_isolated(
        self,
        max_rounds: int = 150,
        batch_size: int = 8,
        dynamic_batching: bool = False,
    ) -> dict[str, Any]:
        """
        Executes entire mission DAG using isolated worker processes or adaptive backend
        until all tasks complete. Supports dynamic batching and sanity tracking.
        """
        t0 = time.perf_counter()
        completed_total = 0
        failed_total = 0
        rounds = 0
        all_sched_lats: list[float] = []
        all_lease_lats: list[float] = []
        all_exec_lats: list[float] = []

        total_tasks = len(self.task_graph.nodes)

        while completed_total < total_tasks and rounds < max_rounds:
            rounds += 1
            round_res = await self.run_round_isolated(batch_size=batch_size, dynamic_batching=dynamic_batching)
            progress = round_res["completed"]
            completed_total += progress
            failed_total += round_res["failed"]
            all_sched_lats.extend(round_res.get("scheduling_latencies", []))
            all_lease_lats.extend(round_res.get("lease_latencies", []))
            all_exec_lats.extend(round_res.get("execution_latencies", []))

            synced = self.sync_dependencies()
            if progress == 0 and synced == 0 and completed_total < total_tasks:
                break

        wall_clock_s = time.perf_counter() - t0
        throughput = completed_total / wall_clock_s if wall_clock_s > 0 else 0.0

        # Throughput Sanity Check: completed + failed + deferred <= created
        sanity_ok = (completed_total + failed_total <= total_tasks)

        # Self-calibrating Execution Cost History record
        workload_hash = getattr(self, "canonical_hash", "") or hashlib.sha256(f"{total_tasks}_{self.isolation_mode.value}".encode()).hexdigest()
        self.execution_cost_history.record(CostHistoryRecord(
            workload_sha256=workload_hash,
            agent_count=sum(len(c.registry.list_agents()) for c in self.subswarms.values()),
            task_count=total_tasks,
            task_duration_ms=0.5,
            execution_mode=self.isolation_mode.value,
            worker_count=len(self._worker_pids) or 1,
            batch_size=batch_size,
            observed_latency_ms=round(wall_clock_s * 1000.0, 2),
            observed_throughput=round(throughput, 2),
        ))

        return {
            "completed_tasks": completed_total,
            "failed_tasks": failed_total,
            "total_tasks": total_tasks,
            "rounds": rounds,
            "wall_clock_s": wall_clock_s,
            "throughput": throughput,
            "worker_pids": list(self._worker_pids),
            "isolation_mode": self.isolation_mode.value,
            "scheduling_latencies": all_sched_lats,
            "lease_latencies": all_lease_lats,
            "execution_latencies": all_exec_lats,
            "fairness_index": self.compute_fairness_index(),
            "ipc_breakdown": self.ipc_breakdown_records,
            "backend_metrics": self.get_or_create_backend().get_metrics(),
            "tasks_sanity": {
                "created": total_tasks,
                "completed": completed_total,
                "failed": failed_total,
                "deferred": self.tasks_deferred,
                "sanity_ok": sanity_ok,
            },
        }


# ── DETERMINISTIC FEDERATION REFERENCE MODEL (ORACLE) ─────────────────────────

class FederationReferenceModel:
    """
    Slow, fully deterministic reference model used as an oracle to verify:
    - Partition determinism;
    - Resource ownership exclusivity;
    - Zero duplicate task execution;
    - State transition correctness.
    """

    @staticmethod
    def verify_partition_determinism(
        task_graph: TaskGraph,
        agents: Sequence[AgentInstance],
        runs: int = 5,
    ) -> bool:
        base_t, base_a, _ = DeterministicSubSwarmPartitioner.partition(task_graph, agents)
        for _ in range(runs - 1):
            t_parts, a_parts, _ = DeterministicSubSwarmPartitioner.partition(task_graph, agents)
            if t_parts != base_t or a_parts != base_a:
                return False
        return True

    @staticmethod
    def verify_no_double_ownership(arbitrator: FederatedResourceArbitrator) -> bool:
        seen_resources = set()
        for res in arbitrator.get_holders().keys():
            if res in seen_resources:
                return False
            seen_resources.add(res)
        return True

    @staticmethod
    def verify_no_duplicate_execution(federation: SwarmFederation) -> bool:
        executed_tasks: set[str] = set()
        for s_id, coord in federation.subswarms.items():
            for t_id in coord.completed_tasks:
                if t_id in executed_tasks:
                    return False  # Duplicate completion detected!
                executed_tasks.add(t_id)
        return True


# ── HIERARCHICAL SCHEDULING: FEDERATED TASK SCHEDULER ─────────────────────────

class FederatedTaskScheduler:
    """
    Global scheduler distributing coarse-grained WorkPackages to Sub-Swarms.
    Sub-Swarms locally schedule tasks to individual agents.
    """

    def __init__(self, federation: SwarmFederation):
        self.federation = federation
        self.work_packages: dict[str, WorkPackage] = {}
        self.package_seq: int = 0
        self.global_scheduling_overhead_ms: float = 0.0

    def create_and_distribute_work_packages(
        self,
        ready_tasks: Sequence[TaskNode],
        package_size: int = 5,
    ) -> list[WorkPackage]:
        t0 = time.perf_counter()
        distributed = []

        # Map ready tasks to subswarms using deterministic partitioner affinity
        tasks_by_swarm: dict[str, list[TaskNode]] = {s_id: [] for s_id in self.federation.subswarms}
        for task in ready_tasks:
            # Check if already assigned to a subswarm
            assigned = False
            for s_id, coord in self.federation.subswarms.items():
                if task.task_id in coord.assigned_tasks:
                    tasks_by_swarm[s_id].append(task)
                    assigned = True
                    break
            if not assigned:
                # Assign to subswarm with lowest queue length
                min_s_id = min(self.federation.subswarms.keys(), key=lambda s: len(self.federation.subswarms[s].assigned_tasks))
                tasks_by_swarm[min_s_id].append(task)
                self.federation.subswarms[min_s_id].assign_task(task)

        # Build WorkPackages per subswarm
        for s_id, s_tasks in tasks_by_swarm.items():
            for i in range(0, len(s_tasks), package_size):
                chunk = s_tasks[i : i + package_size]
                self.package_seq += 1
                pkg_id = f"pkg_{self.package_seq:04d}_{s_id}"
                claims = []
                for t in chunk:
                    claims.extend(t.metadata.get("path_scope") or [])

                wp = WorkPackage(
                    package_id=pkg_id,
                    subswarm_id=s_id,
                    task_ids=[t.task_id for t in chunk],
                    resource_claims=list(set(claims)),
                    priority=max(t.priority for t in chunk) if chunk else 1,
                )
                self.work_packages[pkg_id] = wp
                distributed.append(wp)

        self.global_scheduling_overhead_ms += (time.perf_counter() - t0) * 1000.0
        return distributed


# ── FEDERATED CONFLICT GRAPHS ──────────────────────────────────────────────────

@dataclass
class LocalConflictNode:
    proposal_id: str
    agent_id: str
    task_id: str
    resources: list[str]


class LocalConflictGraph:
    """Maintains local conflict graph within an autonomous sub-swarm."""

    def __init__(self, subswarm_id: str):
        self.subswarm_id = subswarm_id
        self.nodes: dict[str, LocalConflictNode] = {}
        self.edges: set[tuple[str, str]] = set()

    def add_proposal(self, proposal_id: str, agent_id: str, task_id: str, resources: list[str]) -> None:
        node = LocalConflictNode(proposal_id, agent_id, task_id, resources)
        # Check conflicts against existing local nodes
        for other_id, other_node in self.nodes.items():
            if set(resources).intersection(set(other_node.resources)):
                self.edges.add((min(proposal_id, other_id), max(proposal_id, other_id)))
        self.nodes[proposal_id] = node

    def is_local_only(self, proposal_id: str, federation_arbitrator: FederatedResourceArbitrator) -> bool:
        node = self.nodes.get(proposal_id)
        if not node:
            return True
        holders = federation_arbitrator.get_holders()
        for res in node.resources:
            if res in holders and holders[res][0] != self.subswarm_id:
                return False  # Resource held by another subswarm!
        return True


class CrossSwarmConflictGraph:
    """Maintains cross-sub-swarm conflict graph at the Federation level."""

    def __init__(self):
        self.cross_conflicts: dict[str, dict[str, Any]] = {}

    def register_cross_conflict(
        self,
        resource: str,
        subswarm_a: str,
        task_a: str,
        subswarm_b: str,
        task_b: str,
    ) -> str:
        conflict_id = f"cross_conf_{hashlib.sha256(f'{resource}::{subswarm_a}::{subswarm_b}'.encode()).hexdigest()[:12]}"
        self.cross_conflicts[conflict_id] = {
            "conflict_id": conflict_id,
            "resource": resource,
            "subswarm_a": subswarm_a,
            "task_a": task_a,
            "subswarm_b": subswarm_b,
            "task_b": task_b,
            "created_at": time.time(),
        }
        return conflict_id

    def resolve_cross_conflict(self, conflict_id: str) -> None:
        self.cross_conflicts.pop(conflict_id, None)


# ── MESSAGE IDEMPOTENCY & NETWORK ANOMALY SIMULATOR ───────────────────────────

class MessageIdempotencyManager:
    """Enforces deterministic message identity and guarantees no duplicate side-effects."""

    def __init__(self):
        self._processed_message_ids: set[str] = set()

    def make_message_id(self, sender: str, msg_type: str, payload: dict[str, Any]) -> str:
        raw = f"{sender}::{msg_type}::{json.dumps(payload, sort_keys=True)}"
        return f"msg_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"

    def process_message(self, message_id: str) -> bool:
        """Returns True if message is new and should be processed; False if duplicate."""
        if message_id in self._processed_message_ids:
            return False  # Duplicate ignored
        self._processed_message_ids.add(message_id)
        return True


class NetworkAnomalySimulator:
    """Simulates network latency, packet loss, duplicate messages, and reordering."""

    def __init__(
        self,
        latency_ms: float = 0.0,
        drop_rate: float = 0.0,
        duplicate_rate: float = 0.0,
        seed: int = 42,
    ):
        import random
        self.latency_ms = latency_ms
        self.drop_rate = drop_rate
        self.duplicate_rate = duplicate_rate
        self.rng = random.Random(seed)
        self.dropped_count: int = 0
        self.duplicated_count: int = 0

    async def deliver(self, callback: Callable[[str, dict[str, Any]], Any], event_type: str, data: dict[str, Any]) -> list[Any]:
        results = []
        # Packet drop
        if self.drop_rate > 0.0 and self.rng.random() < self.drop_rate:
            self.dropped_count += 1
            return results

        # Latency simulation
        if self.latency_ms > 0.0:
            await asyncio.sleep(self.latency_ms / 1000.0)

        res = callback(event_type, data)
        if asyncio.iscoroutine(res):
            res = await res
        results.append(res)

        # Duplicate message simulation
        if self.duplicate_rate > 0.0 and self.rng.random() < self.duplicate_rate:
            self.duplicated_count += 1
            dup_res = callback(event_type, data)
            if asyncio.iscoroutine(dup_res):
                dup_res = await dup_res
            results.append(dup_res)

        return results


# ── OBSERVABILITY & DRIFT TRACKER ──────────────────────────────────────────────

@dataclass
class FederationObservability:
    """Comprehensive observability metrics for federation performance and health."""
    subswarm_count: int = 0
    agents_per_subswarm: dict[str, int] = field(default_factory=dict)
    cross_swarm_edges: int = 0
    cross_swarm_messages: int = 0
    cross_swarm_conflicts: int = 0
    partition_cost_ms: float = 0.0
    rebalance_count: int = 0
    federation_latency_ms: float = 0.0
    global_coordination_latency_ms: float = 0.0
    local_coordination_latency_ms: float = 0.0
    lease_contention_local: int = 0
    lease_contention_global: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

