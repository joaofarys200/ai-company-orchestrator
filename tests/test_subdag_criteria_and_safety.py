from __future__ import annotations

import asyncio
import os
import shutil
import uuid
import pytest

from agents.dynamic_subdag import (
    DynamicSubDagProposal,
    ExpansionTrigger,
    ProposalStatus,
    SubDagValidator,
)
from agents.mission_orchestrator import (
    MissionLifecycleOrchestrator,
    TaskExecutionResult,
)
from agents.mission_state import MissionStateStore
from agents.task_graph import TaskGraph, TaskNode, TaskStatus


@pytest.fixture
def temp_workspace() -> tuple[str, MissionStateStore]:
    test_id = uuid.uuid4().hex[:8]
    root = os.path.abspath(f"test_ws_subdag_crit_{test_id}")
    os.makedirs(os.path.join(root, "workspace", "projects"), exist_ok=True)
    store = MissionStateStore(workspace_root=root)
    yield root, store
    shutil.rmtree(root, ignore_errors=True)


@pytest.mark.anyio
async def test_t_acceptance_criteria_propagation(temp_workspace: tuple[str, MissionStateStore]) -> None:
    _, store = temp_workspace
    proj = "p_crit"
    miss = "m_crit"
    os.makedirs(os.path.join(store.projects_root, proj), exist_ok=True)
    store.create_mission(proj, "Criteria Propagation", "Goal", mission_id=miss)

    t1 = TaskNode(task_id="T1", title="Task 1", status=TaskStatus.RUNNING)
    graph = TaskGraph([t1])
    orch = MissionLifecycleOrchestrator(
        project_id=proj,
        mission_id=miss,
        mission_state=store,
        task_graph=graph,
    )

    crit_id = f"crit_dyn_{uuid.uuid4().hex[:6]}"
    proposal = DynamicSubDagProposal(
        proposal_id="prop_crit",
        mission_id=miss,
        parent_task_id="T1",
        base_graph_version=1,
        reason="Needs specific verification criterion",
        trigger=ExpansionTrigger.REQUIREMENT_DISCOVERY,
        tasks=[{"task_id": "T2", "title": "SubTask 2"}],
        acceptance_criteria=[{
            "criterion_id": crit_id,
            "description": "Endpoint returns HTTP 200 with valid schema",
            "required": True,
            "owner_id": "T2",
        }],
    )

    success, msg, record = await orch.propose_and_apply_expansion(proposal)
    assert success is True
    assert record is not None

    # Verify criteria exists in MissionStateStore
    m_data = store.load_mission(proj, miss)
    criteria = m_data.get("acceptance_criteria", [])
    matched = [c for c in criteria if c.get("criterion_id") == crit_id]
    assert len(matched) == 1
    assert matched[0]["description"] == "Endpoint returns HTTP 200 with valid schema"
    assert matched[0]["status"] == "PENDING"


@pytest.mark.anyio
async def test_u_evidence_propagation_and_satisfaction(temp_workspace: tuple[str, MissionStateStore]) -> None:
    _, store = temp_workspace
    proj = "p_ev"
    miss = "m_ev"
    os.makedirs(os.path.join(store.projects_root, proj), exist_ok=True)
    store.create_mission(proj, "Evidence Propagation", "Goal", mission_id=miss)

    t1 = TaskNode(task_id="T1", title="Task 1", status=TaskStatus.RUNNING)
    graph = TaskGraph([t1])
    orch = MissionLifecycleOrchestrator(
        project_id=proj,
        mission_id=miss,
        mission_state=store,
        task_graph=graph,
    )

    crit_id = f"crit_{uuid.uuid4().hex[:6]}"
    proposal = DynamicSubDagProposal(
        proposal_id="prop_ev",
        mission_id=miss,
        parent_task_id="T1",
        base_graph_version=1,
        reason="Add task with acceptance criterion",
        trigger=ExpansionTrigger.REQUIREMENT_DISCOVERY,
        tasks=[{"task_id": "T2", "title": "Task 2"}],
        acceptance_criteria=[{
            "criterion_id": crit_id,
            "description": "Task 2 verification",
            "owner_id": "T2",
            "required": True,
        }],
    )
    await orch.propose_and_apply_expansion(proposal)

    # Attach evidence for T2
    ev_id = f"ev_t2_{uuid.uuid4().hex[:6]}"
    store.attach_evidence(
        project_id=proj,
        mission_id=miss,
        work_package_id="T2",
        kind="TEST_OUTPUT",
        source_ref="validation:pytest_run",
        description="All tests passed with 100% green",
        evidence_id=ev_id,
    )

    # Update criterion to satisfied
    crit_entity = [c for c in store.load_mission(proj, miss)["acceptance_criteria"] if c["criterion_id"] == crit_id][0]
    store.set_criterion_status(
        project_id=proj,
        mission_id=miss,
        criterion_id=crit_id,
        status="SATISFIED",
        expected_version=crit_entity["version"],
        evidence_refs=[ev_id],
    )

    # Mark all tasks completed
    orch.task_graph.nodes["T1"].status = TaskStatus.COMPLETED
    orch.task_graph.nodes["T2"].status = TaskStatus.COMPLETED

    satisfied, reason = await orch.verify_satisfaction()
    assert satisfied is True


@pytest.mark.anyio
async def test_v_failed_apply_rollback(temp_workspace: tuple[str, MissionStateStore]) -> None:
    _, store = temp_workspace
    proj = "p_roll"
    miss = "m_roll"
    os.makedirs(os.path.join(store.projects_root, proj), exist_ok=True)
    store.create_mission(proj, "Rollback Mission", "Goal", mission_id=miss)

    t1 = TaskNode(task_id="T1", title="Task 1", status=TaskStatus.RUNNING)
    graph = TaskGraph([t1])
    orch = MissionLifecycleOrchestrator(
        project_id=proj,
        mission_id=miss,
        mission_state=store,
        task_graph=graph,
    )

    # Force failure during store write by monkeypatching create_work_package to raise
    original_fn = store.create_work_package
    def boom(*args, **kwargs):
        raise RuntimeError("Disk write simulation failure")
    store.create_work_package = boom

    proposal = DynamicSubDagProposal(
        proposal_id="prop_boom",
        mission_id=miss,
        parent_task_id="T1",
        base_graph_version=1,
        reason="Will fail on commit",
        trigger=ExpansionTrigger.REQUIREMENT_DISCOVERY,
        tasks=[{"task_id": "T2", "title": "SubTask 2"}],
    )

    success, msg, record = await orch.propose_and_apply_expansion(proposal)
    assert success is False
    assert "Falha transacional" in msg
    # Graph remains at v1 and T2 is NOT present
    assert orch.task_graph.graph_version == 1
    assert "T2" not in orch.task_graph.nodes
    store.create_work_package = original_fn


def test_w_invalid_model_proposal_schema() -> None:
    graph = TaskGraph([TaskNode(task_id="T1", title="Task 1")])
    validator = SubDagValidator()

    # Empty proposal_id
    p1 = DynamicSubDagProposal(
        proposal_id="",
        mission_id="m1",
        parent_task_id="T1",
        base_graph_version=1,
        reason="some reason",
        trigger=ExpansionTrigger.REQUIREMENT_DISCOVERY,
        tasks=[{"title": "Valid title"}],
    )
    ok, msg, _, _ = validator.validate(p1, graph)
    assert ok is False
    assert "proposal_id" in msg

    # Empty reason
    p2 = DynamicSubDagProposal(
        proposal_id="p2",
        mission_id="m1",
        parent_task_id="T1",
        base_graph_version=1,
        reason="",
        trigger=ExpansionTrigger.REQUIREMENT_DISCOVERY,
        tasks=[{"title": "Valid title"}],
    )
    ok, msg, _, _ = validator.validate(p2, graph)
    assert ok is False
    assert "Motivo" in msg

    # Empty tasks
    p3 = DynamicSubDagProposal(
        proposal_id="p3",
        mission_id="m1",
        parent_task_id="T1",
        base_graph_version=1,
        reason="Empty tasks list",
        trigger=ExpansionTrigger.REQUIREMENT_DISCOVERY,
        tasks=[],
    )
    ok, msg, _, _ = validator.validate(p3, graph)
    assert ok is False
    assert "não contém tarefas" in msg


def test_x_scope_violation_rejection() -> None:
    graph = TaskGraph([TaskNode(task_id="T1", title="Task 1")])
    validator = SubDagValidator()

    # Path traversal in requested scope
    p_traversal = DynamicSubDagProposal(
        proposal_id="p_bad_scope",
        mission_id="m1",
        parent_task_id="T1",
        base_graph_version=1,
        reason="Attempting unauthorized access",
        trigger=ExpansionTrigger.ARCHITECTURE_DISCOVERY,
        tasks=[{"task_id": "T_HACK", "title": "Access root"}],
        requested_scope={"path": "../../etc/shadow"},
    )
    ok, msg, _, _ = validator.validate(p_traversal, graph)
    assert ok is False
    assert "Violação de escopo / segurança" in msg


def test_y_mission_gate_destructive_command_rejection() -> None:
    graph = TaskGraph([TaskNode(task_id="T1", title="Task 1")])
    validator = SubDagValidator()

    # Destructive command pattern
    p_destructive = DynamicSubDagProposal(
        proposal_id="p_destruct",
        mission_id="m1",
        parent_task_id="T1",
        base_graph_version=1,
        reason="Destructive task",
        trigger=ExpansionTrigger.REQUIREMENT_DISCOVERY,
        tasks=[{"task_id": "T_RM", "title": "Clean up"}],
        requested_scope={"command": "rm -rf /var/data"},
    )
    ok, msg, _, _ = validator.validate(p_destructive, graph)
    assert ok is False
    assert "Violação de escopo / segurança" in msg
