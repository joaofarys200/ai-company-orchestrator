from __future__ import annotations

import pytest

from agents.dynamic_subdag import (
    DynamicSubDagProposal,
    ExpansionLimits,
    ExpansionTrigger,
    ProposalStatus,
    SubDagValidator,
    compute_semantic_key,
)
from agents.task_graph import TaskGraph, TaskNode, TaskStatus


def make_sample_graph() -> TaskGraph:
    nodes = [
        TaskNode(task_id="T1", title="Initial Task", status=TaskStatus.RUNNING),
        TaskNode(task_id="T2", title="Followup Task", dependencies=["T1"], status=TaskStatus.PENDING),
    ]
    return TaskGraph(nodes=nodes)


def test_a_valid_expansion() -> None:
    graph = make_sample_graph()
    validator = SubDagValidator()
    proposal = DynamicSubDagProposal(
        proposal_id="prop_valid",
        mission_id="m1",
        parent_task_id="T1",
        base_graph_version=1,
        reason="Discovered need for helper service",
        trigger=ExpansionTrigger.REQUIREMENT_DISCOVERY,
        tasks=[
            {"task_id": "T3", "title": "Helper Service", "category": "CODING"},
            {"task_id": "T4", "title": "Helper Tests", "category": "TEST"},
        ],
        dependencies=[("T3", "T4")],
    )

    is_valid, msg, nodes, edges = validator.validate(proposal, graph)
    assert is_valid is True
    assert len(nodes) == 2
    assert ("T3", "T4") in edges


def test_b_missing_dependency() -> None:
    graph = make_sample_graph()
    validator = SubDagValidator()
    proposal = DynamicSubDagProposal(
        proposal_id="prop_missing_dep",
        mission_id="m1",
        parent_task_id="T1",
        base_graph_version=1,
        reason="Needs non-existent task",
        trigger=ExpansionTrigger.DEPENDENCY_DISCOVERY,
        tasks=[
            {"task_id": "T3", "title": "New Task", "dependencies": ["NON_EXISTENT_XYZ"]},
        ],
    )

    is_valid, msg, _, _ = validator.validate(proposal, graph)
    assert is_valid is False
    assert "não existe" in msg


def test_c_duplicate_task_id() -> None:
    graph = make_sample_graph()
    validator = SubDagValidator()
    proposal = DynamicSubDagProposal(
        proposal_id="prop_duplicate_id",
        mission_id="m1",
        parent_task_id="T1",
        base_graph_version=1,
        reason="Attempts to overwrite T2",
        trigger=ExpansionTrigger.REQUIREMENT_DISCOVERY,
        tasks=[
            {"task_id": "T2", "title": "Overwrite T2"},
        ],
    )

    is_valid, msg, _, _ = validator.validate(proposal, graph)
    assert is_valid is False
    assert "já existe no TaskGraph" in msg


def test_d_self_cycle() -> None:
    graph = make_sample_graph()
    validator = SubDagValidator()
    proposal = DynamicSubDagProposal(
        proposal_id="prop_self_cycle",
        mission_id="m1",
        parent_task_id="T1",
        base_graph_version=1,
        reason="Self dependent task",
        trigger=ExpansionTrigger.REQUIREMENT_DISCOVERY,
        tasks=[
            {"task_id": "T3", "title": "Loop", "dependencies": ["T3"]},
        ],
    )

    is_valid, msg, _, _ = validator.validate(proposal, graph)
    assert is_valid is False
    assert "Auto-ciclo" in msg or "Ciclo" in msg


def test_e_direct_cycle() -> None:
    graph = make_sample_graph()
    validator = SubDagValidator()
    proposal = DynamicSubDagProposal(
        proposal_id="prop_direct_cycle",
        mission_id="m1",
        parent_task_id="T1",
        base_graph_version=1,
        reason="Direct cycle between new tasks",
        trigger=ExpansionTrigger.REQUIREMENT_DISCOVERY,
        tasks=[
            {"task_id": "T3", "title": "Step 3", "dependencies": ["T4"]},
            {"task_id": "T4", "title": "Step 4", "dependencies": ["T3"]},
        ],
    )

    is_valid, msg, _, _ = validator.validate(proposal, graph)
    assert is_valid is False
    assert "Ciclo" in msg


def test_f_indirect_cycle() -> None:
    graph = make_sample_graph()
    validator = SubDagValidator()
    proposal = DynamicSubDagProposal(
        proposal_id="prop_indirect_cycle",
        mission_id="m1",
        parent_task_id="T1",
        base_graph_version=1,
        reason="Indirect cycle A -> B -> C -> A",
        trigger=ExpansionTrigger.REQUIREMENT_DISCOVERY,
        tasks=[
            {"task_id": "T3", "title": "Step 3", "dependencies": ["T4"]},
            {"task_id": "T4", "title": "Step 4", "dependencies": ["T5"]},
            {"task_id": "T5", "title": "Step 5", "dependencies": ["T3"]},
        ],
    )

    is_valid, msg, _, _ = validator.validate(proposal, graph)
    assert is_valid is False
    assert "Ciclo" in msg


def test_g_cross_old_new_cycle() -> None:
    # T1 -> T2. Proposed: T3 depends on T2, but T1 depends on T3!
    graph = make_sample_graph()
    validator = SubDagValidator()
    proposal = DynamicSubDagProposal(
        proposal_id="prop_cross_cycle",
        mission_id="m1",
        parent_task_id="T1",
        base_graph_version=1,
        reason="Cross old-new cycle",
        trigger=ExpansionTrigger.ARCHITECTURE_DISCOVERY,
        tasks=[
            {"task_id": "T3", "title": "New Node", "dependencies": ["T2"]},
        ],
        dependencies=[("T3", "T1")],  # T1 now depends on T3 -> T2 -> T1 cycle!
    )

    is_valid, msg, _, _ = validator.validate(proposal, graph)
    assert is_valid is False
    assert "Ciclo" in msg


def test_h_stale_graph_version() -> None:
    graph = make_sample_graph()
    graph.graph_version = 3  # Graph is at v3
    validator = SubDagValidator()
    proposal = DynamicSubDagProposal(
        proposal_id="prop_stale",
        mission_id="m1",
        parent_task_id="T1",
        base_graph_version=1,  # Stale proposal based on v1
        reason="Built on old snapshot",
        trigger=ExpansionTrigger.RUNTIME_DISCOVERY,
        tasks=[{"task_id": "T3", "title": "Valid task"}],
    )

    is_valid, msg, _, _ = validator.validate(proposal, graph)
    assert is_valid is False
    assert "REJECTED_STALE_GRAPH_VERSION" in msg


def test_i_atomic_rejection_no_partial_leak() -> None:
    graph = make_sample_graph()
    initial_node_count = len(graph.nodes)
    validator = SubDagValidator()
    proposal = DynamicSubDagProposal(
        proposal_id="prop_partial_bad",
        mission_id="m1",
        parent_task_id="T1",
        base_graph_version=1,
        reason="First task ok, second task cycle",
        trigger=ExpansionTrigger.REQUIREMENT_DISCOVERY,
        tasks=[
            {"task_id": "T_GOOD", "title": "Good Node"},
            {"task_id": "T_BAD", "title": "Bad Node", "dependencies": ["T_BAD"]},
        ],
    )

    is_valid, msg, _, _ = validator.validate(proposal, graph)
    assert is_valid is False
    # Verify graph was NOT modified
    assert len(graph.nodes) == initial_node_count
    assert "T_GOOD" not in graph.nodes


def test_j_version_increment() -> None:
    graph = make_sample_graph()
    assert graph.graph_version == 1
    new_node = TaskNode(task_id="T3", title="New Task", dependencies=["T1"])
    record = {"proposal_id": "prop_test", "tasks_added": ["T3"]}
    v2 = graph.apply_subdag([new_node], [], record)
    assert v2 == 2
    assert graph.graph_version == 2
    assert "T3" in graph.nodes
    assert len(graph.expansion_history) == 1
