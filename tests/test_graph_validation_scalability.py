"""Unit and Scalability Test Suite for Fase 13.1 — Iterative Graph Validation & Scalability."""

import json
import os
import shutil
import tempfile
import pytest

from agents.adaptive_planning import (
    AdaptationBudget,
    AdaptationTrigger,
    AdaptivePlanningValidator,
    MissionAdaptationProposal,
    PlanEvaluationDecision,
)
from agents.dynamic_subdag import DynamicSubDagProposal, ExpansionTrigger
from agents.mission_orchestrator import MissionLifecycleOrchestrator
from agents.mission_state import MissionStateStore
from agents.task_graph import (
    TaskDependencyError,
    TaskGraph,
    TaskGraphCycleError,
    TaskGraphError,
    TaskNode,
    TaskStatus,
)


@pytest.fixture
def temp_store_dir():
    temp_dir = tempfile.mkdtemp(prefix="jarvis_graph_scalability_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


# A. 1000-node linear DAG
def test_a_1000_node_linear_dag():
    nodes = [
        TaskNode(task_id=f"t_{i}", title=f"Task {i}", dependencies=[f"t_{i-1}"] if i > 0 else [])
        for i in range(1000)
    ]
    graph = TaskGraph(nodes=nodes)
    order = graph.topological_sort()
    assert len(order) == 1000
    assert order[0] == "t_0"
    assert order[-1] == "t_999"


# B. 2000-node linear DAG
def test_b_2000_node_linear_dag():
    nodes = [
        TaskNode(task_id=f"t_{i}", title=f"Task {i}", dependencies=[f"t_{i-1}"] if i > 0 else [])
        for i in range(2000)
    ]
    graph = TaskGraph(nodes=nodes)
    order = graph.topological_sort()
    assert len(order) == 2000
    assert order[0] == "t_0"
    assert order[-1] == "t_1999"


# C. 5000-node linear DAG
def test_c_5000_node_linear_dag():
    nodes = [
        TaskNode(task_id=f"t_{i}", title=f"Task {i}", dependencies=[f"t_{i-1}"] if i > 0 else [])
        for i in range(5000)
    ]
    graph = TaskGraph(nodes=nodes)
    order = graph.topological_sort()
    assert len(order) == 5000
    assert order[0] == "t_0"
    assert order[-1] == "t_4999"


# D. Reverse insertion
def test_d_reverse_insertion_deep_graph():
    # Insert nodes in reversed order so roots are added last
    nodes = [
        TaskNode(task_id=f"rev_{i}", title=f"Rev {i}", dependencies=[f"rev_{i-1}"] if i > 0 else [])
        for i in reversed(range(1500))
    ]
    graph = TaskGraph(nodes=nodes)
    order = graph.topological_sort()
    assert len(order) == 1500
    assert order[0] == "rev_0"
    assert order[-1] == "rev_1499"


# E. Self-cycle
def test_e_self_cycle_detection():
    node = TaskNode(task_id="self_loop", title="Self", dependencies=["self_loop"])
    with pytest.raises(TaskGraphCycleError) as exc_info:
        TaskGraph([node])
    assert "não pode depender de si própria" in str(exc_info.value)


# F. Direct cycle
def test_f_direct_cycle_detection():
    n1 = TaskNode(task_id="t1", title="Task 1", dependencies=["t2"])
    n2 = TaskNode(task_id="t2", title="Task 2", dependencies=["t1"])
    with pytest.raises(TaskGraphCycleError) as exc_info:
        TaskGraph([n1, n2])
    assert "Ciclo detectado no TaskGraph" in str(exc_info.value)
    assert "t1" in str(exc_info.value) and "t2" in str(exc_info.value)


# G. Indirect cycle
def test_g_indirect_cycle_detection():
    n1 = TaskNode(task_id="a", title="A", dependencies=["c"])
    n2 = TaskNode(task_id="b", title="B", dependencies=["a"])
    n3 = TaskNode(task_id="c", title="C", dependencies=["b"])
    with pytest.raises(TaskGraphCycleError) as exc_info:
        TaskGraph([n1, n2, n3])
    assert "Ciclo detectado no TaskGraph" in str(exc_info.value)


# H. Disconnected cycle in large graph
def test_h_disconnected_cycle_in_deep_graph():
    # Valid linear chain of 1000 nodes + independent cycle of 2 nodes
    nodes = [
        TaskNode(task_id=f"chain_{i}", title=f"Chain {i}", dependencies=[f"chain_{i-1}"] if i > 0 else [])
        for i in range(1000)
    ]
    nodes.append(TaskNode(task_id="cycle_x", title="Cycle X", dependencies=["cycle_y"]))
    nodes.append(TaskNode(task_id="cycle_y", title="Cycle Y", dependencies=["cycle_x"]))

    with pytest.raises(TaskGraphCycleError) as exc_info:
        TaskGraph(nodes)
    assert "Ciclo detectado no TaskGraph" in str(exc_info.value)
    assert "cycle_x" in str(exc_info.value)
    assert "cycle_y" in str(exc_info.value)


# I. Missing dependency
def test_i_missing_dependency_detection():
    n1 = TaskNode(task_id="valid_node", title="Valid", dependencies=["ghost_dependency"])
    with pytest.raises(TaskDependencyError) as exc_info:
        TaskGraph([n1])
    assert "ghost_dependency" in str(exc_info.value)


# J. Duplicate node
def test_j_duplicate_node_detection():
    n1 = TaskNode(task_id="dup_id", title="First")
    n2 = TaskNode(task_id="dup_id", title="Second")
    with pytest.raises(TaskGraphError) as exc_info:
        TaskGraph([n1, n2])
    assert "já existe no TaskGraph" in str(exc_info.value)


# K. Deterministic order
def test_k_deterministic_topological_order():
    # Multiple branches with priorities
    nodes = [
        TaskNode(task_id="root", title="Root"),
        TaskNode(task_id="branch_b", title="B", priority=5, dependencies=["root"]),
        TaskNode(task_id="branch_a", title="A", priority=10, dependencies=["root"]),
        TaskNode(task_id="branch_c", title="C", priority=5, dependencies=["root"]),
        TaskNode(task_id="leaf", title="Leaf", dependencies=["branch_a", "branch_b", "branch_c"]),
    ]

    for _ in range(20):
        g = TaskGraph(nodes=nodes)
        order = g.topological_sort()
        # branch_a (priority 10) must precede branch_b and branch_c (priority 5)
        assert order[0] == "root"
        assert order[1] == "branch_a"
        # branch_b precedes branch_c due to alphabetical tie-breaking
        assert order[2] == "branch_b"
        assert order[3] == "branch_c"
        assert order[4] == "leaf"


# L. Dynamic Sub-DAG deep graph
def test_l_dynamic_subdag_on_deep_graph(temp_store_dir):
    async def _run():
        project_id = "p_deep_subdag"
        mission_id = "m_deep_subdag"
        os.makedirs(os.path.join(temp_store_dir, "workspace", "projects", project_id), exist_ok=True)
        store = MissionStateStore(temp_store_dir)
        store.create_mission(
            project_id=project_id,
            title="Deep Graph Sub-DAG Mission",
            objective="Verify dynamic sub-DAG on 1000-node graph",
            mission_id=mission_id,
        )

        # Initial chain of 1000 nodes
        nodes = [
            TaskNode(task_id=f"n_{i}", title=f"Node {i}", dependencies=[f"n_{i-1}"] if i > 0 else [], status=TaskStatus.READY)
            for i in range(1000)
        ]
        graph = TaskGraph(nodes=nodes, graph_version=1)

        from agents.dynamic_subdag import ExpansionLimits
        orchestrator = MissionLifecycleOrchestrator(
            project_id=project_id,
            mission_id=mission_id,
            mission_state=store,
            task_graph=graph,
            expansion_limits=ExpansionLimits(max_total_tasks=2000),
        )

        proposal = DynamicSubDagProposal(
            proposal_id="prop_deep_subdag_1",
            mission_id=mission_id,
            parent_task_id="n_500",
            base_graph_version=1,
            trigger=ExpansionTrigger.REQUIREMENT_DISCOVERY,
            reason="Expand node 500 into 5 sub-tasks",
            tasks=[
                {
                    "task_id": f"sub_500_{j}",
                    "title": f"Sub Task {j}",
                    "category": "CODING",
                }
                for j in range(5)
            ],
            dependencies=[(f"sub_500_{j}", f"sub_500_{j+1}") for j in range(4)],
        )

        success, msg, rec = await orchestrator.propose_and_apply_expansion(proposal)
        assert success is True
        assert orchestrator.task_graph.graph_version == 2
        assert len(orchestrator.task_graph.nodes) == 1005
        # Verify whole graph remains a valid DAG
        order = orchestrator.task_graph.topological_sort()
        assert len(order) == 1005

    import asyncio
    asyncio.run(_run())


# M. Adaptive planning deep graph
def test_m_adaptive_planning_on_deep_graph(temp_store_dir):
    async def _run():
        project_id = "p_deep_adapt"
        mission_id = "m_deep_adapt"
        os.makedirs(os.path.join(temp_store_dir, "workspace", "projects", project_id), exist_ok=True)
        store = MissionStateStore(temp_store_dir)
        store.create_mission(
            project_id=project_id,
            title="Deep Graph Adaptive Mission",
            objective="Verify adaptive planning proposal on 1000-node graph",
            mission_id=mission_id,
        )

        nodes = [
            TaskNode(task_id=f"t_{i}", title=f"Task {i}", dependencies=[f"t_{i-1}"] if i > 0 else [], status=TaskStatus.COMPLETED if i < 100 else TaskStatus.READY)
            for i in range(1000)
        ]
        graph = TaskGraph(nodes=nodes, graph_version=1)

        orchestrator = MissionLifecycleOrchestrator(
            project_id=project_id,
            mission_id=mission_id,
            mission_state=store,
            task_graph=graph,
            adaptation_budget=AdaptationBudget(max_graph_churn=50),
        )

        # Propose inserting a fix task between t_99 and t_100
        proposal = MissionAdaptationProposal(
            proposal_id="prop_deep_patch",
            mission_id=mission_id,
            base_graph_version=1,
            decision=PlanEvaluationDecision.ADAPT_PLAN,
            trigger=AdaptationTrigger.RUNTIME_FAILURE,
            reason="Patch critical interface between t_99 and t_100 in deep graph.",
            added_tasks=[
                {
                    "task_id": "patch_deep_node",
                    "title": "Patch Deep Node",
                    "category": "CODING",
                    "dependencies": ["t_99"],
                }
            ],
            changed_edges=[("patch_deep_node", "t_100")],
            evidence_ids=["ev_deep_patch"],
        )

        ok, msg, rec = await orchestrator.propose_and_apply_adaptation(proposal)
        assert ok is True
        assert orchestrator.task_graph.graph_version == 2
        assert "patch_deep_node" in orchestrator.task_graph.nodes
        assert "patch_deep_node" in orchestrator.task_graph.nodes["t_100"].dependencies

    import asyncio
    asyncio.run(_run())


# N. Checkpoint deep graph
def test_n_checkpoint_save_and_restore_deep_graph(temp_store_dir):
    project_id = "p_deep_cp"
    mission_id = "m_deep_cp"
    os.makedirs(os.path.join(temp_store_dir, "workspace", "projects", project_id), exist_ok=True)
    store = MissionStateStore(temp_store_dir)
    store.create_mission(
        project_id=project_id,
        title="Deep Graph Checkpoint",
        objective="Verify checkpoint save/restore on 1200-node graph",
        mission_id=mission_id,
    )

    nodes = [
        TaskNode(task_id=f"c_{i}", title=f"CP Node {i}", dependencies=[f"c_{i-1}"] if i > 0 else [], status=TaskStatus.READY)
        for i in reversed(range(1200))
    ]
    graph = TaskGraph(nodes=nodes, graph_version=3)

    orch1 = MissionLifecycleOrchestrator(
        project_id=project_id,
        mission_id=mission_id,
        mission_state=store,
        task_graph=graph,
    )

    cp = orch1.save_checkpoint("Deep graph checkpoint sequence 1")
    assert cp.graph_version == 3

    orch2 = MissionLifecycleOrchestrator(
        project_id=project_id,
        mission_id=mission_id,
        mission_state=store,
    )
    loaded_cp = orch2.load_latest_checkpoint()
    assert loaded_cp is not None
    orch2.recover_from_checkpoint(loaded_cp)
    assert orch2.task_graph.graph_version == 3
    assert len(orch2.task_graph.nodes) == 1200
    order = orch2.task_graph.topological_sort()
    assert len(order) == 1200


# O. No RecursionError
def test_o_no_recursion_error_under_strict_limits():
    """Confirms that even with thousands of nodes, validation executes in constant stack space."""
    nodes = [
        TaskNode(task_id=f"k_{i}", title=f"Kahn {i}", dependencies=[f"k_{i-1}"] if i > 0 else [])
        for i in reversed(range(3000))
    ]
    # In earlier versions, this threw RecursionError around 995 frames.
    g = TaskGraph(nodes=nodes)
    order = g.topological_sort()
    assert len(order) == 3000


# PROPERTY / INVARIANT TESTS
def test_property_topological_invariants():
    """Tests the two fundamental DAG invariants:
    1. Every node appears exactly once.
    2. For every directed edge u -> v (where u is a dependency of v), u appears before v.
    """
    import random
    rng = random.Random(42)

    # Build a complex branching DAG with 400 nodes
    nodes = [TaskNode(task_id="root", title="Root")]
    all_ids = ["root"]

    for i in range(1, 400):
        tid = f"prop_{i}"
        # Pick 1 to 3 random predecessors from earlier nodes to ensure acyclic DAG
        num_deps = min(len(all_ids), rng.randint(1, 3))
        deps = sorted(rng.sample(all_ids, num_deps))
        nodes.append(TaskNode(task_id=tid, title=f"Prop {i}", dependencies=deps))
        all_ids.append(tid)

    # Shuffle nodes to ensure order independence
    rng.shuffle(nodes)
    graph = TaskGraph(nodes=nodes)
    order = graph.topological_sort()

    # Invariant 1: Exactly once
    assert len(order) == len(nodes)
    assert set(order) == set(all_ids)

    # Invariant 2: u appears before v for all u in v.dependencies
    pos = {tid: idx for idx, tid in enumerate(order)}
    for node in nodes:
        for dep in node.dependencies:
            assert pos[dep] < pos[node.task_id], f"Invariant violated: {dep} (idx {pos[dep]}) not before {node.task_id} (idx {pos[node.task_id]})"
