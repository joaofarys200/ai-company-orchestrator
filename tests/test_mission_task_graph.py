from __future__ import annotations

import pytest

from agents.task_graph import (
    FailureCategory,
    TaskDependencyError,
    TaskGraph,
    TaskGraphCycleError,
    TaskGraphError,
    TaskNode,
    TaskStatus,
)


def test_task_graph_basic_dag_topological_sort():
    # A -> B -> D
    # A -> C -> D
    task_a = TaskNode(task_id="A", title="Setup Project")
    task_b = TaskNode(task_id="B", title="Create Database", dependencies=["A"])
    task_c = TaskNode(task_id="C", title="Create API", dependencies=["A"])
    task_d = TaskNode(task_id="D", title="Frontend Integration", dependencies=["B", "C"])

    graph = TaskGraph([task_a, task_b, task_c, task_d])
    order = graph.topological_sort()

    assert order.index("A") < order.index("B")
    assert order.index("A") < order.index("C")
    assert order.index("B") < order.index("D")
    assert order.index("C") < order.index("D")


def test_task_graph_detects_self_dependency():
    task = TaskNode(task_id="A", title="Self loop", dependencies=["A"])
    with pytest.raises(TaskGraphCycleError):
        TaskGraph([task])


def test_task_graph_detects_direct_cycle():
    task_a = TaskNode(task_id="A", title="A", dependencies=["B"])
    task_b = TaskNode(task_id="B", title="B", dependencies=["A"])
    with pytest.raises(TaskGraphCycleError):
        TaskGraph([task_a, task_b])


def test_task_graph_detects_indirect_cycle():
    task_a = TaskNode(task_id="A", title="A", dependencies=["C"])
    task_b = TaskNode(task_id="B", title="B", dependencies=["A"])
    task_c = TaskNode(task_id="C", title="C", dependencies=["B"])
    with pytest.raises(TaskGraphCycleError):
        TaskGraph([task_a, task_b, task_c])


def test_task_graph_detects_missing_dependency():
    task_a = TaskNode(task_id="A", title="A", dependencies=["NON_EXISTENT"])
    with pytest.raises(TaskDependencyError):
        TaskGraph([task_a])


def test_task_graph_dependency_resolution_and_ready_queue():
    task_a = TaskNode(task_id="A", title="Step A")
    task_b = TaskNode(task_id="B", title="Step B", dependencies=["A"])
    task_c = TaskNode(task_id="C", title="Step C Independent")

    graph = TaskGraph([task_a, task_b, task_c])

    # Initially A and C are READY; B is PENDING
    ready = [n.task_id for n in graph.get_ready_tasks()]
    assert set(ready) == {"A", "C"}
    assert graph.get_node("B").status == TaskStatus.PENDING

    # Complete A -> now B becomes READY
    graph.get_node("A").status = TaskStatus.COMPLETED
    ready_after = [n.task_id for n in graph.get_ready_tasks()]
    assert "B" in ready_after


def test_task_graph_failure_propagation_blocks_downstream():
    task_a = TaskNode(task_id="A", title="Step A")
    task_b = TaskNode(task_id="B", title="Step B", dependencies=["A"])
    task_c = TaskNode(task_id="C", title="Step C", dependencies=["B"])

    graph = TaskGraph([task_a, task_b, task_c])

    # Mark A as FAILED
    graph.get_node("A").status = TaskStatus.FAILED
    graph.update_derived_statuses()

    # B and C must be BLOCKED, not FAILED
    assert graph.get_node("B").status == TaskStatus.BLOCKED
    assert graph.get_node("C").status == TaskStatus.BLOCKED
    assert graph.get_node("A").status == TaskStatus.FAILED


def test_task_graph_serialization_roundtrip():
    task_a = TaskNode(task_id="A", title="Task Alpha", priority=10)
    task_b = TaskNode(task_id="B", title="Task Beta", dependencies=["A"], priority=5)

    graph = TaskGraph([task_a, task_b])
    data = graph.to_dict()

    restored = TaskGraph.from_dict(data)
    assert len(restored.nodes) == 2
    assert restored.get_node("A").priority == 10
    assert restored.get_node("B").dependencies == ["A"]
