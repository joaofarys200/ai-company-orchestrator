from __future__ import annotations

import asyncio
import os
import shutil
import uuid
import pytest

from agents.dynamic_subdag import (
    DynamicSubDagEngine,
    DynamicSubDagProposal,
    ExpansionLimits,
    ExpansionTrigger,
    ProposalStatus,
    SubDagValidator,
)
from agents.mission_orchestrator import (
    Checkpoint,
    MissionLifecycleOrchestrator,
    MissionLifecycleStatus,
    TaskExecutionResult,
)
from agents.mission_state import MissionStateStore
from agents.task_graph import TaskGraph, TaskNode, TaskStatus


@pytest.fixture
def temp_workspace() -> tuple[str, MissionStateStore]:
    test_id = uuid.uuid4().hex[:8]
    root = os.path.abspath(f"test_ws_subdag_{test_id}")
    os.makedirs(os.path.join(root, "workspace", "projects"), exist_ok=True)
    store = MissionStateStore(workspace_root=root)
    yield root, store
    shutil.rmtree(root, ignore_errors=True)


def test_k_scheduler_update_ready_queue() -> None:
    graph = TaskGraph([
        TaskNode(task_id="A", title="Task A", status=TaskStatus.COMPLETED),
    ])
    assert graph.is_all_completed() is True

    # Expand with B (depends on A) and C (depends on B)
    node_b = TaskNode(task_id="B", title="Task B", dependencies=["A"], status=TaskStatus.PENDING)
    node_c = TaskNode(task_id="C", title="Task C", dependencies=["B"], status=TaskStatus.PENDING)
    graph.apply_subdag([node_b, node_c], [("A", "B"), ("B", "C")], {"proposal_id": "p1"})

    # Graph is no longer all completed
    assert graph.is_all_completed() is False
    # B should be READY because A is COMPLETED; C should be PENDING
    ready_ids = [n.task_id for n in graph.get_ready_tasks()]
    assert "B" in ready_ids
    assert "C" not in ready_ids


def test_l_running_task_preservation() -> None:
    node_running = TaskNode(task_id="R1", title="Running Task", status=TaskStatus.RUNNING)
    graph = TaskGraph([node_running])

    # Apply expansion
    node_new = TaskNode(task_id="NEW1", title="New Task", dependencies=[])
    graph.apply_subdag([node_new], [], {"proposal_id": "p2"})

    # Running task MUST remain RUNNING
    assert graph.nodes["R1"].status == TaskStatus.RUNNING
    assert graph.nodes["NEW1"].status == TaskStatus.READY


def test_m_completed_task_preservation() -> None:
    node_completed = TaskNode(
        task_id="C1",
        title="Completed Task",
        status=TaskStatus.COMPLETED,
        result_summary="Done in pass 1",
    )
    graph = TaskGraph([node_completed])

    node_new = TaskNode(task_id="NEW2", title="New Task 2", dependencies=["C1"])
    graph.apply_subdag([node_new], [("C1", "NEW2")], {"proposal_id": "p3"})

    # C1 must stay COMPLETED and never change status
    assert graph.nodes["C1"].status == TaskStatus.COMPLETED
    assert graph.nodes["C1"].result_summary == "Done in pass 1"


def test_n_checkpoint_persistence(temp_workspace: tuple[str, MissionStateStore]) -> None:
    _, store = temp_workspace
    proj = "p_chk"
    miss = "m_chk"
    os.makedirs(os.path.join(store.projects_root, proj), exist_ok=True)
    store.create_mission(proj, "Mission Checkpoint", "Goal", mission_id=miss)

    graph = TaskGraph([TaskNode(task_id="T1", title="T1", status=TaskStatus.COMPLETED)])
    orch = MissionLifecycleOrchestrator(
        project_id=proj,
        mission_id=miss,
        mission_state=store,
        task_graph=graph,
    )

    # Expand graph to v2
    graph.apply_subdag(
        [TaskNode(task_id="T2", title="T2", dependencies=["T1"])],
        [],
        {"proposal_id": "prop_chk", "trigger": "REQUIREMENT_DISCOVERY"},
    )
    assert graph.graph_version == 2

    # Save checkpoint
    cp = orch.save_checkpoint("Expanded to v2")
    assert cp.graph_version == 2
    assert len(cp.expansion_history) == 1

    # Load latest checkpoint
    loaded = orch.load_latest_checkpoint()
    assert loaded is not None
    assert loaded.graph_version == 2
    assert len(loaded.expansion_history) == 1


def test_o_restart_recovery(temp_workspace: tuple[str, MissionStateStore]) -> None:
    _, store = temp_workspace
    proj = "p_rec"
    miss = "m_rec"
    os.makedirs(os.path.join(store.projects_root, proj), exist_ok=True)
    store.create_mission(proj, "Recovery Mission", "Goal", mission_id=miss)

    node1 = TaskNode(task_id="T1", title="T1", status=TaskStatus.COMPLETED)
    node2 = TaskNode(task_id="T2", title="T2", status=TaskStatus.RUNNING)
    graph = TaskGraph([node1, node2])
    graph.graph_version = 4
    graph.expansion_history = [{"expansion": 1}, {"expansion": 2}, {"expansion": 3}]

    orch = MissionLifecycleOrchestrator(
        project_id=proj,
        mission_id=miss,
        mission_state=store,
        task_graph=graph,
    )
    orch._running_tasks.add("T2")
    cp = orch.save_checkpoint("Mid execution v4")

    # Simulate fresh orchestrator process restart
    fresh_orch = MissionLifecycleOrchestrator(
        project_id=proj,
        mission_id=miss,
        mission_state=store,
    )
    fresh_orch.recover_from_checkpoint(cp)

    assert fresh_orch.task_graph.graph_version == 4
    assert len(fresh_orch.task_graph.expansion_history) == 3
    # Interrupted task T2 should be rescued to READY (retryable)
    assert fresh_orch.task_graph.nodes["T2"].status == TaskStatus.READY
    # Completed task T1 remains COMPLETED
    assert fresh_orch.task_graph.nodes["T1"].status == TaskStatus.COMPLETED


@pytest.mark.anyio
async def test_p_concurrent_proposals(temp_workspace: tuple[str, MissionStateStore]) -> None:
    _, store = temp_workspace
    proj = "p_conc"
    miss = "m_conc"
    os.makedirs(os.path.join(store.projects_root, proj), exist_ok=True)
    store.create_mission(proj, "Concurrent Expansion", "Goal", mission_id=miss)

    t1 = TaskNode(task_id="ROOT", title="Root Task", status=TaskStatus.RUNNING)
    graph = TaskGraph([t1])
    orch = MissionLifecycleOrchestrator(
        project_id=proj,
        mission_id=miss,
        mission_state=store,
        task_graph=graph,
    )

    p1 = DynamicSubDagProposal(
        proposal_id="prop_p1",
        mission_id=miss,
        parent_task_id="ROOT",
        base_graph_version=1,
        reason="Branch 1 work",
        trigger=ExpansionTrigger.REQUIREMENT_DISCOVERY,
        tasks=[{"task_id": "T_B1", "title": "Branch 1"}],
    )
    p2 = DynamicSubDagProposal(
        proposal_id="prop_p2",
        mission_id=miss,
        parent_task_id="ROOT",
        base_graph_version=1,  # Also based on v1!
        reason="Branch 2 work",
        trigger=ExpansionTrigger.ARCHITECTURE_DISCOVERY,
        tasks=[{"task_id": "T_B2", "title": "Branch 2"}],
    )

    # Submit concurrently
    res1, res2 = await asyncio.gather(
        orch.propose_and_apply_expansion(p1),
        orch.propose_and_apply_expansion(p2),
    )

    assert res1[0] is True
    assert res2[0] is True
    # One applied from v1 to v2, the other rebased and applied from v2 to v3!
    assert orch.task_graph.graph_version == 3
    assert "T_B1" in orch.task_graph.nodes
    assert "T_B2" in orch.task_graph.nodes


def test_q_duplicate_semantic_tasks() -> None:
    graph = TaskGraph([
        TaskNode(task_id="EXISTING", title="Add Search Endpoint", category="CODING"),
    ])
    validator = SubDagValidator()
    # Proposed with different task_id, but identical semantic title and category
    proposal = DynamicSubDagProposal(
        proposal_id="prop_sem_dup",
        mission_id="m1",
        parent_task_id="EXISTING",
        base_graph_version=1,
        reason="Discover same requirement again",
        trigger=ExpansionTrigger.REQUIREMENT_DISCOVERY,
        tasks=[
            {"task_id": "BRAND_NEW_ID", "title": "add   search  endpoint", "category": "CODING"},
        ],
    )

    is_valid, msg, _, _ = validator.validate(proposal, graph)
    assert is_valid is False
    assert "Tarefa semanticamente duplicada" in msg


def test_r_expansion_depth_limit() -> None:
    limits = ExpansionLimits(max_expansion_depth=2)
    validator = SubDagValidator(limits=limits)

    # Task at depth 2
    root = TaskNode(task_id="ROOT", title="Root")
    child1 = TaskNode(task_id="C1", title="Child 1", parent_task_id="ROOT")
    child1.expansion_depth = 1
    child2 = TaskNode(task_id="C2", title="Child 2", parent_task_id="C1")
    child2.expansion_depth = 2

    graph = TaskGraph([root, child1, child2])

    # Trying to expand child2 would result in depth 3 > max_expansion_depth (2)
    proposal = DynamicSubDagProposal(
        proposal_id="prop_too_deep",
        mission_id="m1",
        parent_task_id="C2",
        base_graph_version=1,
        reason="Deep nesting",
        trigger=ExpansionTrigger.REQUIREMENT_DISCOVERY,
        tasks=[{"task_id": "C3", "title": "Child 3"}],
    )

    is_valid, msg, _, _ = validator.validate(proposal, graph)
    assert is_valid is False
    assert "expansion_limit_hit" in msg
    assert "Profundidade" in msg


def test_s_expansion_limits_total_tasks() -> None:
    limits = ExpansionLimits(max_total_tasks=3, max_tasks_per_expansion=2)
    validator = SubDagValidator(limits=limits)

    graph = TaskGraph([
        TaskNode(task_id="A", title="A"),
        TaskNode(task_id="B", title="B"),
    ])

    # Proposal with 2 tasks would make total 4 > max_total_tasks (3)
    proposal = DynamicSubDagProposal(
        proposal_id="prop_limit_exceeded",
        mission_id="m1",
        parent_task_id="A",
        base_graph_version=1,
        reason="Too many tasks",
        trigger=ExpansionTrigger.REQUIREMENT_DISCOVERY,
        tasks=[
            {"task_id": "C", "title": "C"},
            {"task_id": "D", "title": "D"},
        ],
    )

    is_valid, msg, _, _ = validator.validate(proposal, graph)
    assert is_valid is False
    assert "expansion_limit_hit" in msg
