from __future__ import annotations

import enum
import heapq
from dataclasses import asdict, dataclass, field
from typing import Any, Iterator, Sequence


class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"
    INTERRUPTED = "INTERRUPTED"


class FailureCategory(str, enum.Enum):
    NONE = "NONE"
    TRANSIENT_FAILURE = "TRANSIENT_FAILURE"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"
    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    POLICY_BLOCK = "POLICY_BLOCK"
    TIMEOUT = "TIMEOUT"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"


@dataclass
class FailureInfo:
    category: FailureCategory = FailureCategory.NONE
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    attempt: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value if isinstance(self.category, FailureCategory) else str(self.category),
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
            "attempt": self.attempt,
        }


@dataclass
class RetryConfig:
    max_attempts: int = 3
    initial_delay_seconds: float = 1.0
    backoff_factor: float = 2.0
    retryable_categories: list[FailureCategory] = field(
        default_factory=lambda: [
            FailureCategory.TRANSIENT_FAILURE,
            FailureCategory.TIMEOUT,
            FailureCategory.VALIDATION_FAILURE,
        ]
    )

    def is_retryable(self, category: FailureCategory, attempt_count: int) -> bool:
        if attempt_count >= self.max_attempts:
            return False
        return category in self.retryable_categories

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_attempts": self.max_attempts,
            "initial_delay_seconds": self.initial_delay_seconds,
            "backoff_factor": self.backoff_factor,
            "retryable_categories": [
                c.value if isinstance(c, FailureCategory) else str(c)
                for c in self.retryable_categories
            ],
        }


@dataclass
class TaskNode:
    task_id: str
    title: str
    description: str = ""
    category: str = "GENERIC"  # CODING, RESEARCH, REVIEW, BUILD, EXPERIMENT, GENERIC
    dependencies: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0
    attempt_count: int = 0
    timeout_seconds: float = 60.0
    retry_config: RetryConfig = field(default_factory=RetryConfig)
    result_summary: str = ""
    output_data: dict[str, Any] = field(default_factory=dict)
    failure_info: FailureInfo = field(default_factory=FailureInfo)
    evidence_refs: list[str] = field(default_factory=list)
    required: bool = True
    created_at: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    version: int = 1
    parent_task_id: str | None = None
    subdag_id: str | None = None
    expansion_depth: int = 0
    semantic_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "dependencies": list(self.dependencies),
            "status": self.status.value if isinstance(self.status, TaskStatus) else str(self.status),
            "priority": self.priority,
            "attempt_count": self.attempt_count,
            "timeout_seconds": self.timeout_seconds,
            "retry_config": self.retry_config.to_dict() if hasattr(self.retry_config, "to_dict") else asdict(self.retry_config),
            "result_summary": self.result_summary,
            "output_data": self.output_data,
            "failure_info": self.failure_info.to_dict() if hasattr(self.failure_info, "to_dict") else asdict(self.failure_info),
            "evidence_refs": list(self.evidence_refs),
            "required": self.required,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
            "version": self.version,
            "parent_task_id": self.parent_task_id,
            "subdag_id": self.subdag_id,
            "expansion_depth": self.expansion_depth,
            "semantic_key": self.semantic_key,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskNode:
        retry_raw = data.get("retry_config", {})
        retry_cats = [
            FailureCategory(c) if c in FailureCategory._value2member_map_ else FailureCategory.TRANSIENT_FAILURE
            for c in retry_raw.get("retryable_categories", ["TRANSIENT_FAILURE", "TIMEOUT", "VALIDATION_FAILURE"])
        ]
        retry_config = RetryConfig(
            max_attempts=int(retry_raw.get("max_attempts", 3)),
            initial_delay_seconds=float(retry_raw.get("initial_delay_seconds", 1.0)),
            backoff_factor=float(retry_raw.get("backoff_factor", 2.0)),
            retryable_categories=retry_cats,
        )

        fail_raw = data.get("failure_info", {})
        fail_cat = fail_raw.get("category", "NONE")
        failure_info = FailureInfo(
            category=FailureCategory(fail_cat) if fail_cat in FailureCategory._value2member_map_ else FailureCategory.NONE,
            message=str(fail_raw.get("message", "")),
            details=fail_raw.get("details", {}),
            timestamp=str(fail_raw.get("timestamp", "")),
            attempt=int(fail_raw.get("attempt", 0)),
        )

        status_val = data.get("status", "PENDING")
        status = TaskStatus(status_val) if status_val in TaskStatus._value2member_map_ else TaskStatus.PENDING

        return cls(
            task_id=data["task_id"],
            title=data.get("title", ""),
            description=data.get("description", ""),
            category=data.get("category", "GENERIC"),
            dependencies=list(data.get("dependencies", [])),
            status=status,
            priority=int(data.get("priority", 0)),
            attempt_count=int(data.get("attempt_count", 0)),
            timeout_seconds=float(data.get("timeout_seconds", 60.0)),
            retry_config=retry_config,
            result_summary=data.get("result_summary", ""),
            output_data=data.get("output_data", {}),
            failure_info=failure_info,
            evidence_refs=list(data.get("evidence_refs", [])),
            required=bool(data.get("required", True)),
            created_at=data.get("created_at", ""),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            metadata=data.get("metadata", {}),
            version=int(data.get("version", 1)),
            parent_task_id=data.get("parent_task_id"),
            subdag_id=data.get("subdag_id"),
            expansion_depth=int(data.get("expansion_depth", 0)),
            semantic_key=str(data.get("semantic_key", "")),
        )


class TaskGraphError(Exception):
    pass


class TaskGraphCycleError(TaskGraphError):
    pass


class TaskDependencyError(TaskGraphError):
    pass


class TaskGraph:
    """Deterministic Directed Acyclic Graph (DAG) for mission task scheduling."""

    def __init__(
        self,
        nodes: Sequence[TaskNode] | None = None,
        graph_version: int = 1,
        expansion_history: list[dict[str, Any]] | None = None,
    ) -> None:
        self._nodes: dict[str, TaskNode] = {}
        self.graph_version: int = max(1, int(graph_version))
        self.expansion_history: list[dict[str, Any]] = list(expansion_history or [])
        if nodes:
            for node in nodes:
                self.add_node(node)
            self.validate()

    @property
    def nodes(self) -> dict[str, TaskNode]:
        return self._nodes

    def add_node(self, node: TaskNode) -> None:
        if node.task_id in self._nodes:
            raise TaskGraphError(f"Task '{node.task_id}' já existe no TaskGraph.")
        self._nodes[node.task_id] = node

    def get_node(self, task_id: str) -> TaskNode:
        if task_id not in self._nodes:
            raise TaskDependencyError(f"Task '{task_id}' não encontrada no TaskGraph.")
        return self._nodes[task_id]

    def remove_node(self, task_id: str) -> None:
        if task_id in self._nodes:
            del self._nodes[task_id]
            for node in self._nodes.values():
                if task_id in node.dependencies:
                    node.dependencies.remove(task_id)

    def _kahn_topological_sort(self) -> list[str]:
        """Iterative Kahn's algorithm for deterministic cycle detection and topological sorting.

        Time Complexity: O(V + E)
        Space Complexity: O(V + E)
        Recursion Depth: O(1) (Completely non-recursive, safe for deep graphs)
        """
        # 1. Structural Dependency & Self-Cycle Validation
        for task_id, node in self._nodes.items():
            for dep_id in node.dependencies:
                if dep_id not in self._nodes:
                    raise TaskDependencyError(
                        f"Task '{task_id}' depende de '{dep_id}', que não existe no grafo."
                    )
                if dep_id == task_id:
                    raise TaskGraphCycleError(f"Task '{task_id}' não pode depender de si própria.")

        if not self._nodes:
            return []

        # 2. Build forward adjacency list and in-degrees
        # Edge u -> v means u is a dependency of v (u must run before v)
        # in_degree[v] is the count of unique prerequisites of v
        dependents: dict[str, list[str]] = {tid: [] for tid in self._nodes}
        in_degree: dict[str, int] = {}

        for task_id, node in self._nodes.items():
            unique_deps = set(node.dependencies)
            in_degree[task_id] = len(unique_deps)
            for dep_id in unique_deps:
                dependents[dep_id].append(task_id)

        # 3. Priority queue (min-heap) of available nodes with in-degree == 0
        # Ordered by: (-priority, task_id) for deterministic prioritization
        ready_heap: list[tuple[float, str]] = [
            (-self._nodes[tid].priority, tid)
            for tid, deg in in_degree.items()
            if deg == 0
        ]
        heapq.heapify(ready_heap)

        order: list[str] = []

        # 4. Iterative processing
        while ready_heap:
            _, curr_id = heapq.heappop(ready_heap)
            order.append(curr_id)

            for dep_child in sorted(dependents[curr_id]):
                in_degree[dep_child] -= 1
                if in_degree[dep_child] == 0:
                    heapq.heappush(ready_heap, (-self._nodes[dep_child].priority, dep_child))

        # 5. Cycle Detection
        if len(order) < len(self._nodes):
            # Nodes with remaining in-degree > 0 contain one or more cycles.
            # Iteratively reconstruct the cycle path deterministically.
            remaining = {tid for tid, deg in in_degree.items() if deg > 0}
            start = min(remaining)
            path: list[str] = [start]
            visited_pos: dict[str, int] = {start: 0}
            curr = start

            while True:
                rem_deps = sorted(d for d in self._nodes[curr].dependencies if d in remaining)
                if not rem_deps:
                    rem_deps = sorted(self._nodes[curr].dependencies)
                next_node = rem_deps[0]

                if next_node in visited_pos:
                    idx = visited_pos[next_node]
                    cycle_nodes = path[idx:] + [next_node]
                    cycle_str = " -> ".join(cycle_nodes)
                    raise TaskGraphCycleError(f"Ciclo detectado no TaskGraph: {cycle_str}")

                visited_pos[next_node] = len(path)
                path.append(next_node)
                curr = next_node

        return order

    def validate(self) -> None:
        """Validates that all dependencies exist and there are zero cycles using iterative Kahn's algorithm."""
        self._kahn_topological_sort()

    def topological_sort(self) -> list[str]:
        """Returns ordered list of task_ids from dependencies to dependents using iterative Kahn's algorithm."""
        return self._kahn_topological_sort()

    def get_dependents(self, task_id: str) -> list[str]:
        """Returns direct dependents of task_id (tasks that depend on task_id)."""
        return [
            node.task_id
            for node in self._nodes.values()
            if task_id in node.dependencies
        ]

    def get_all_downstream_dependents(self, task_id: str) -> set[str]:
        """Returns all transitive dependents that rely on task_id."""
        downstream: set[str] = set()
        queue = [task_id]
        while queue:
            curr = queue.pop(0)
            for dep_child in self.get_dependents(curr):
                if dep_child not in downstream:
                    downstream.add(dep_child)
                    queue.append(dep_child)
        return downstream

    def update_derived_statuses(self) -> None:
        """Deterministically evaluates and updates task statuses based on dependency states.

        Rules:
        - If task is RUNNING, COMPLETED, CANCELLED, SKIPPED -> keep status.
        - If any dependency is FAILED, CANCELLED, or BLOCKED -> mark task as BLOCKED.
        - If all dependencies are COMPLETED and status is PENDING -> mark task as READY.
        - If dependencies are in progress or pending -> remain PENDING.
        """
        for task_id in self.topological_sort():
            node = self._nodes[task_id]
            if node.status in {
                TaskStatus.RUNNING,
                TaskStatus.COMPLETED,
                TaskStatus.CANCELLED,
                TaskStatus.SKIPPED,
            }:
                continue

            if node.status == TaskStatus.FAILED:
                # Failure is terminal unless explicitly retried
                continue

            # Check dependencies
            dep_nodes = [self._nodes[dep_id] for dep_id in node.dependencies if dep_id in self._nodes]
            
            # 1. Blocked by upstream failure/cancellation
            any_dep_failed = any(
                d.status in {TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.BLOCKED}
                for d in dep_nodes
            )
            if any_dep_failed:
                node.status = TaskStatus.BLOCKED
                continue

            # 2. Ready when all dependencies are completed
            all_deps_completed = all(d.status == TaskStatus.COMPLETED for d in dep_nodes)
            if all_deps_completed:
                if node.status in {TaskStatus.PENDING, TaskStatus.BLOCKED}:
                    node.status = TaskStatus.READY
            else:
                if node.status == TaskStatus.READY:
                    node.status = TaskStatus.PENDING

    def get_ready_tasks(self) -> list[TaskNode]:
        """Returns all tasks currently in READY status, ordered by priority."""
        self.update_derived_statuses()
        ready = [n for n in self._nodes.values() if n.status == TaskStatus.READY]
        return sorted(ready, key=lambda n: (-n.priority, n.task_id))

    def get_completed_tasks(self) -> list[TaskNode]:
        return [n for n in self._nodes.values() if n.status == TaskStatus.COMPLETED]

    def get_failed_tasks(self) -> list[TaskNode]:
        return [n for n in self._nodes.values() if n.status == TaskStatus.FAILED]

    def get_blocked_tasks(self) -> list[TaskNode]:
        return [n for n in self._nodes.values() if n.status == TaskStatus.BLOCKED]

    def get_running_tasks(self) -> list[TaskNode]:
        return [n for n in self._nodes.values() if n.status == TaskStatus.RUNNING]

    def is_all_completed(self) -> bool:
        required_nodes = [n for n in self._nodes.values() if n.required]
        if not required_nodes:
            return True
        return all(n.status == TaskStatus.COMPLETED for n in required_nodes)

    def has_unrecoverable_failures(self) -> bool:
        """Returns True if any required task is permanently failed or blocked without ready work."""
        failed_required = any(
            n.status == TaskStatus.FAILED and n.required for n in self._nodes.values()
        )
        if failed_required and not self.get_ready_tasks() and not self.get_running_tasks():
            return True
        return False

    def progress_percentage(self) -> float:
        required = [n for n in self._nodes.values() if n.required]
        if not required:
            return 100.0
        completed = sum(1 for n in required if n.status == TaskStatus.COMPLETED)
        return round(completed / len(required) * 100.0, 2)

    def apply_subdag(
        self,
        nodes: Sequence[TaskNode],
        edges: Sequence[tuple[str, str]],
        expansion_record: dict[str, Any],
    ) -> int:
        """Atomically integrates sub-DAG nodes and edges, validates the resulting DAG,
        increments graph_version, and records the expansion in history."""
        backup_nodes = {k: TaskNode.from_dict(v.to_dict()) for k, v in self._nodes.items()}
        backup_edges = {k: list(v.dependencies) for k, v in self._nodes.items()}

        try:
            for node in nodes:
                self.add_node(node)

            for upstream, downstream in edges:
                if downstream in self._nodes and upstream not in self._nodes[downstream].dependencies:
                    self._nodes[downstream].dependencies.append(upstream)

            # Validate entire combined graph
            self.validate()
        except Exception:
            # Transactional rollback
            self._nodes = backup_nodes
            for k, deps in backup_edges.items():
                if k in self._nodes:
                    self._nodes[k].dependencies = deps
            raise

        self.graph_version += 1
        self.expansion_history.append(dict(expansion_record))
        self.update_derived_statuses()
        return self.graph_version

    def to_dict(self) -> dict[str, Any]:
        return {
            "tasks": {task_id: node.to_dict() for task_id, node in self._nodes.items()},
            "order": self.topological_sort() if self._nodes else [],
            "progress": self.progress_percentage(),
            "graph_version": self.graph_version,
            "expansion_history": [dict(r) for r in self.expansion_history],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskGraph:
        tasks_raw = data.get("tasks", {})
        nodes = [TaskNode.from_dict(raw) for raw in tasks_raw.values()]
        graph_version = int(data.get("graph_version", 1))
        expansion_history = list(data.get("expansion_history", []))
        return cls(nodes, graph_version=graph_version, expansion_history=expansion_history)
