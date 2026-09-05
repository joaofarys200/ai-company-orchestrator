"""Adversarial and Chaos Tests for Fase 13.1 Graph Validation Scalability."""

import pytest

from agents.task_graph import (
    TaskDependencyError,
    TaskGraph,
    TaskGraphCycleError,
    TaskGraphError,
    TaskNode,
)


def test_chaos_1000_node_self_cycle():
    """1000 nodes where node 750 has a self-cycle."""
    nodes = [
        TaskNode(task_id=f"n_{i}", title=f"N {i}", dependencies=[f"n_{i-1}"] if i > 0 else [])
        for i in range(1000)
    ]
    # Invert node 750 to depend on itself
    nodes[750].dependencies.append("n_750")

    with pytest.raises(TaskGraphCycleError) as exc:
        TaskGraph(nodes=nodes)
    assert "não pode depender de si própria" in str(exc.value)


def test_chaos_1000_node_cycle_at_end():
    """1000 nodes where the final 3 nodes form a cycle: 997 -> 998 -> 999 -> 997."""
    nodes = [
        TaskNode(task_id=f"n_{i}", title=f"N {i}", dependencies=[f"n_{i-1}"] if i > 0 else [])
        for i in range(1000)
    ]
    # Add back-edge from 997 to 999
    nodes[997].dependencies.append("n_999")

    with pytest.raises(TaskGraphCycleError) as exc:
        TaskGraph(nodes=nodes)
    assert "Ciclo detectado no TaskGraph" in str(exc.value)
    assert "n_997" in str(exc.value)


def test_chaos_1000_node_cycle_near_beginning():
    """1000 nodes where nodes near the root form a cycle: 2 -> 3 -> 4 -> 2."""
    nodes = [
        TaskNode(task_id=f"n_{i}", title=f"N {i}", dependencies=[f"n_{i-1}"] if i > 0 else [])
        for i in range(1000)
    ]
    # Add back-edge from 2 to 4
    nodes[2].dependencies.append("n_4")

    with pytest.raises(TaskGraphCycleError) as exc:
        TaskGraph(nodes=nodes)
    assert "Ciclo detectado no TaskGraph" in str(exc.value)
    assert "n_2" in str(exc.value)


def test_chaos_disconnected_deep_cycle():
    """1500 valid nodes in one branch and a separate 3-node cycle in another branch."""
    nodes = [
        TaskNode(task_id=f"main_{i}", title=f"Main {i}", dependencies=[f"main_{i-1}"] if i > 0 else [])
        for i in range(1500)
    ]
    nodes.append(TaskNode(task_id="loop_a", title="Loop A", dependencies=["loop_c"]))
    nodes.append(TaskNode(task_id="loop_b", title="Loop B", dependencies=["loop_a"]))
    nodes.append(TaskNode(task_id="loop_c", title="Loop C", dependencies=["loop_b"]))

    with pytest.raises(TaskGraphCycleError) as exc:
        TaskGraph(nodes=nodes)
    assert "Ciclo detectado no TaskGraph" in str(exc.value)
    assert "loop_a" in str(exc.value)


def test_chaos_deep_valid_graph_with_dense_fanout():
    """1000-node graph with wide fan-out: root feeds 500 parallel nodes, which converge to 500 leaves."""
    nodes = [TaskNode(task_id="super_root", title="Super Root")]
    mid_tier = [f"mid_{i}" for i in range(500)]
    for m in mid_tier:
        nodes.append(TaskNode(task_id=m, title=m, dependencies=["super_root"]))

    for i in range(500):
        # Each leaf depends on two adjacent mid nodes
        deps = [mid_tier[i], mid_tier[(i + 1) % 500]]
        nodes.append(TaskNode(task_id=f"leaf_{i}", title=f"Leaf {i}", dependencies=deps))

    g = TaskGraph(nodes=nodes)
    order = g.topological_sort()
    assert len(order) == 1001
    assert order[0] == "super_root"


def test_chaos_deep_graph_missing_dependency():
    """1000 nodes where node 888 depends on a non-existent task."""
    nodes = [
        TaskNode(task_id=f"n_{i}", title=f"N {i}", dependencies=[f"n_{i-1}"] if i > 0 else [])
        for i in range(1000)
    ]
    nodes[888].dependencies.append("phantom_missing_target")

    with pytest.raises(TaskDependencyError) as exc:
        TaskGraph(nodes=nodes)
    assert "phantom_missing_target" in str(exc.value)


def test_chaos_deep_graph_duplicate_task():
    """1000 nodes with an attempted duplicate insertion."""
    nodes = [
        TaskNode(task_id=f"n_{i}", title=f"N {i}", dependencies=[f"n_{i-1}"] if i > 0 else [])
        for i in range(1000)
    ]
    # Add duplicate of n_450
    nodes.append(TaskNode(task_id="n_450", title="Duplicate"))

    with pytest.raises(TaskGraphError) as exc:
        TaskGraph(nodes=nodes)
    assert "já existe no TaskGraph" in str(exc.value)
