from __future__ import annotations

import asyncio
import json
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
    MissionLifecycleOrchestrator,
    MissionLifecycleStatus,
)
from agents.mission_state import MissionStateStore
from agents.task_graph import TaskGraph, TaskNode, TaskStatus


@pytest.fixture
def temp_workspace() -> tuple[str, MissionStateStore]:
    test_id = uuid.uuid4().hex[:8]
    root = os.path.abspath(f"test_ws_subdag_chaos_{test_id}")
    os.makedirs(os.path.join(root, "workspace", "projects"), exist_ok=True)
    store = MissionStateStore(workspace_root=root)
    yield root, store
    shutil.rmtree(root, ignore_errors=True)


@pytest.mark.anyio
async def test_chaos_duplicate_proposal_id(temp_workspace: tuple[str, MissionStateStore]) -> None:
    _, store = temp_workspace
    proj = "p_chaos"
    miss = "m_chaos_dup"
    os.makedirs(os.path.join(store.projects_root, proj), exist_ok=True)
    store.create_mission(proj, "Chaos Mission", "Goal", mission_id=miss)
    store.create_work_package(proj, miss, title="Root", work_package_id="ROOT")

    orch = MissionLifecycleOrchestrator(
        project_id=proj,
        mission_id=miss,
        mission_state=store,
        task_graph=TaskGraph([TaskNode(task_id="ROOT", title="Root")]),
    )

    prop = DynamicSubDagProposal(
        proposal_id="dup_prop_id",
        mission_id=miss,
        parent_task_id="ROOT",
        base_graph_version=1,
        reason="First try",
        trigger=ExpansionTrigger.REQUIREMENT_DISCOVERY,
        tasks=[{"task_id": "NEW1", "title": "New 1"}],
    )

    res1 = await orch.propose_and_apply_expansion(prop)
    assert res1[0] is True
    assert orch.task_graph.graph_version == 2

    # Second submission of same proposal against now stale v1
    res2 = await orch.propose_and_apply_expansion(prop)
    # Must either reject or fail cleanly without duplicating tasks in graph
    assert "NEW1" in orch.task_graph.nodes
    # Count of nodes in graph must be 2 (ROOT and NEW1), not 3!
    assert len(orch.task_graph.nodes) == 2


@pytest.mark.anyio
async def test_chaos_cycle_injection(temp_workspace: tuple[str, MissionStateStore]) -> None:
    _, store = temp_workspace
    proj = "p_chaos"
    miss = "m_chaos_cycle"
    os.makedirs(os.path.join(store.projects_root, proj), exist_ok=True)
    store.create_mission(proj, "Chaos Cycle", "Goal", mission_id=miss)
    store.create_work_package(proj, miss, title="Root", work_package_id="ROOT")

    orch = MissionLifecycleOrchestrator(
        project_id=proj,
        mission_id=miss,
        mission_state=store,
        task_graph=TaskGraph([TaskNode(task_id="ROOT", title="Root")]),
    )

    # Injected cycle: X -> Y -> X
    bad_prop = DynamicSubDagProposal(
        proposal_id="cycle_inject",
        mission_id=miss,
        parent_task_id="ROOT",
        base_graph_version=1,
        reason="Malicious or flawed model cycle proposal",
        trigger=ExpansionTrigger.ARCHITECTURE_DISCOVERY,
        tasks=[
            {"task_id": "CYCLE_X", "title": "Node X", "dependencies": ["CYCLE_Y"]},
            {"task_id": "CYCLE_Y", "title": "Node Y", "dependencies": ["CYCLE_X"]},
        ],
    )

    success, msg, record = await orch.propose_and_apply_expansion(bad_prop)
    assert success is False
    assert "Ciclo" in msg
    assert orch.task_graph.graph_version == 1
    assert "CYCLE_X" not in orch.task_graph.nodes
    assert "CYCLE_Y" not in orch.task_graph.nodes


@pytest.mark.anyio
async def test_chaos_corrupted_expansion_record_recovery(temp_workspace: tuple[str, MissionStateStore]) -> None:
    _, store = temp_workspace
    proj = "p_chaos"
    miss = "m_chaos_corrupt"
    os.makedirs(os.path.join(store.projects_root, proj), exist_ok=True)
    store.create_mission(proj, "Corrupted Record", "Goal", mission_id=miss)

    orch = MissionLifecycleOrchestrator(
        project_id=proj,
        mission_id=miss,
        mission_state=store,
        task_graph=TaskGraph([TaskNode(task_id="R", title="R")]),
    )
    cp = orch.save_checkpoint("Valid cp")

    # Corrupt an expansion JSON on disk
    exp_dir = os.path.join(store._mission_dir(proj, miss), "expansions")
    os.makedirs(exp_dir, exist_ok=True)
    with open(os.path.join(exp_dir, "expansion_0002.json"), "w", encoding="utf-8") as f:
        f.write("{ CORRUPTED JSON !!!")

    # Orchestrator should still safely recover from checkpoint without crashing
    fresh = MissionLifecycleOrchestrator(
        project_id=proj,
        mission_id=miss,
        mission_state=store,
    )
    fresh.recover_from_checkpoint(cp)
    assert fresh.task_graph.graph_version == 1


@pytest.mark.anyio
async def test_chaos_limits_exhaustion(temp_workspace: tuple[str, MissionStateStore]) -> None:
    _, store = temp_workspace
    proj = "p_chaos"
    miss = "m_chaos_limits"
    os.makedirs(os.path.join(store.projects_root, proj), exist_ok=True)
    store.create_mission(proj, "Limits Test", "Goal", mission_id=miss)
    store.create_work_package(proj, miss, title="T0", work_package_id="T0")

    # Set tight limit: max 2 expansions
    limits = ExpansionLimits(max_expansions_per_mission=2)
    orch = MissionLifecycleOrchestrator(
        project_id=proj,
        mission_id=miss,
        mission_state=store,
        expansion_limits=limits,
        task_graph=TaskGraph([TaskNode(task_id="T0", title="T0")]),
    )

    # Expansion 1
    p1 = DynamicSubDagProposal(
        proposal_id="p1",
        mission_id=miss,
        parent_task_id="T0",
        base_graph_version=1,
        reason="Exp 1",
        trigger=ExpansionTrigger.REQUIREMENT_DISCOVERY,
        tasks=[{"task_id": "T1", "title": "T1"}],
    )
    ok1, _, _ = await orch.propose_and_apply_expansion(p1)
    assert ok1 is True

    # Expansion 2
    p2 = DynamicSubDagProposal(
        proposal_id="p2",
        mission_id=miss,
        parent_task_id="T0",
        base_graph_version=2,
        reason="Exp 2",
        trigger=ExpansionTrigger.REQUIREMENT_DISCOVERY,
        tasks=[{"task_id": "T2", "title": "T2"}],
    )
    ok2, _, _ = await orch.propose_and_apply_expansion(p2)
    assert ok2 is True

    # Expansion 3 -> Must be rejected due to limit exhaustion!
    p3 = DynamicSubDagProposal(
        proposal_id="p3",
        mission_id=miss,
        parent_task_id="T0",
        base_graph_version=3,
        reason="Exp 3 - Over limit",
        trigger=ExpansionTrigger.REQUIREMENT_DISCOVERY,
        tasks=[{"task_id": "T3", "title": "T3"}],
    )
    ok3, msg3, _ = await orch.propose_and_apply_expansion(p3)
    assert ok3 is False
    assert "expansion_limit_hit" in msg3
    assert "T3" not in orch.task_graph.nodes
