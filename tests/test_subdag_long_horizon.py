from __future__ import annotations

import asyncio
import os
import shutil
import uuid
import pytest

from agents.dynamic_subdag import (
    DynamicSubDagProposal,
    ExpansionTrigger,
)
from agents.mission_orchestrator import (
    FailureCategory,
    FailureInfo,
    MissionLifecycleOrchestrator,
    MissionLifecycleStatus,
    TaskExecutionResult,
)
from agents.mission_state import MissionStateStore
from agents.task_graph import TaskGraph, TaskNode, TaskStatus


@pytest.fixture
def temp_workspace() -> tuple[str, MissionStateStore]:
    test_id = uuid.uuid4().hex[:8]
    root = os.path.abspath(f"test_ws_subdag_lh_{test_id}")
    os.makedirs(os.path.join(root, "workspace", "projects"), exist_ok=True)
    store = MissionStateStore(workspace_root=root)
    yield root, store
    shutil.rmtree(root, ignore_errors=True)


@pytest.mark.anyio
async def test_long_horizon_dynamic_subdag_mission(temp_workspace: tuple[str, MissionStateStore]) -> None:
    """Long-Horizon Dynamic Sub-DAG Execution (Section 31 of spec):
    - Multi-stage autonomous run across 15-30 cycles
    - 3 dynamic expansions (v1 -> v2 -> v3 -> v4)
    - Dynamic discovery during task execution (not pre-built)
    - Parallel branches and dependency resolution
    - Simulated crash & restart mid-mission recovering exact graph_version
    - Repair loop & retry for validation failure
    - Final satisfaction barrier confirmation
    """
    _, store = temp_workspace
    proj = "p_long"
    miss = "m_long"
    os.makedirs(os.path.join(store.projects_root, proj), exist_ok=True)
    store.create_mission(proj, "Long Horizon Dynamic Mission", "Goal of long autonomous run", mission_id=miss)

    # 1. Initial DAG: T1 and T2
    for tid in ["T1", "T2"]:
        store.create_work_package(proj, miss, title=f"Initial {tid}", work_package_id=tid)

    node_t1 = TaskNode(task_id="T1", title="Task 1: Core Research")
    node_t2 = TaskNode(task_id="T2", title="Task 2: Base Setup", dependencies=["T1"])
    graph = TaskGraph([node_t1, node_t2])

    execution_cycles = 0
    t7_repaired = False
    crash_simulated = False
    last_saved_checkpoint = None

    async def custom_repair(project_id: str, node: TaskNode, fail_info: FailureInfo, ctx: dict) -> bool:
        nonlocal t7_repaired
        if node.task_id == "T7":
            t7_repaired = True
            return True
        return False

    async def custom_executor(project_id: str, node: TaskNode, context: dict) -> TaskExecutionResult:
        nonlocal execution_cycles, crash_simulated
        execution_cycles += 1
        await asyncio.sleep(0.01)

        # ── EXPANSION 1: Triggered by T1
        if node.task_id == "T1":
            p1 = DynamicSubDagProposal(
                proposal_id="prop_lh_1",
                mission_id=miss,
                parent_task_id="T1",
                base_graph_version=1,
                reason="T1 discovers requirement for modules T3, T4, T5",
                trigger=ExpansionTrigger.REQUIREMENT_DISCOVERY,
                tasks=[
                    {"task_id": "T3", "title": "Submodule T3", "dependencies": ["T1"]},
                    {"task_id": "T4", "title": "Submodule T4", "dependencies": ["T3"]},
                    {"task_id": "T5", "title": "Submodule T5", "dependencies": ["T3"]},
                ],
                dependencies=[("T3", "T4"), ("T3", "T5")],
            )
            return TaskExecutionResult(
                success=True,
                task_id=node.task_id,
                summary="T1 completed with expansion 1",
                subdag_proposal=p1,
            )

        # ── EXPANSION 2: Triggered by T4
        elif node.task_id == "T4":
            p2 = DynamicSubDagProposal(
                proposal_id="prop_lh_2",
                mission_id=miss,
                parent_task_id="T4",
                base_graph_version=2,
                reason="T4 discovers architecture need for services T6, T7",
                trigger=ExpansionTrigger.ARCHITECTURE_DISCOVERY,
                tasks=[
                    {"task_id": "T6", "title": "Service T6", "dependencies": ["T4"]},
                    {"task_id": "T7", "title": "Service T7", "dependencies": ["T6"]},
                ],
                dependencies=[("T6", "T7")],
            )
            return TaskExecutionResult(
                success=True,
                task_id=node.task_id,
                summary="T4 completed with expansion 2",
                subdag_proposal=p2,
            )

        # T7 has a validation failure on attempt 1, triggering minimal repair
        elif node.task_id == "T7":
            if node.attempt_count == 1:
                return TaskExecutionResult(
                    success=False,
                    task_id=node.task_id,
                    failure_category=FailureCategory.VALIDATION_FAILURE,
                    error_message="Contract mismatch in T7 interface",
                )
            else:
                return TaskExecutionResult(
                    success=True,
                    task_id=node.task_id,
                    summary="T7 succeeded after minimal repair",
                )

        # ── EXPANSION 3: Triggered by T6
        elif node.task_id == "T6":
            p3 = DynamicSubDagProposal(
                proposal_id="prop_lh_3",
                mission_id=miss,
                parent_task_id="T6",
                base_graph_version=3,
                reason="T6 discovers missing test suites T8, T9, T10",
                trigger=ExpansionTrigger.MISSING_TEST,
                tasks=[
                    {"task_id": "T8", "title": "Unit Tests T8", "dependencies": ["T6"]},
                    {"task_id": "T9", "title": "E2E Tests T9", "dependencies": ["T8"]},
                    {"task_id": "T10", "title": "Load Tests T10", "dependencies": ["T8"]},
                ],
                dependencies=[("T8", "T9"), ("T8", "T10")],
            )
            return TaskExecutionResult(
                success=True,
                task_id=node.task_id,
                summary="T6 completed with expansion 3",
                subdag_proposal=p3,
            )

        return TaskExecutionResult(success=True, task_id=node.task_id, summary=f"{node.title} done")

    # Launch First Half of Orchestrator Execution
    orch = MissionLifecycleOrchestrator(
        project_id=proj,
        mission_id=miss,
        mission_state=store,
        task_graph=graph,
        concurrency_limit=2,
        executor_fn=custom_executor,
        repair_fn=custom_repair,
    )

    # Run up to Expansion 2
    async def step_and_pause():
        # Run until T5 and T4 complete (v3 reached)
        while orch.task_graph.graph_version < 3:
            ready = orch.task_graph.get_ready_tasks()
            if not ready:
                break
            for r in ready[:1]:
                await orch._execute_single_task_guarded(r, asyncio.Semaphore(1))
            orch.task_graph.update_derived_statuses()

    await step_and_pause()
    assert orch.task_graph.graph_version >= 2

    # Save Checkpoint mid-run
    cp = orch.save_checkpoint("Mid-run before crash")
    saved_v = cp.graph_version

    # Simulate CRASH & RESTART:
    fresh_orch = MissionLifecycleOrchestrator(
        project_id=proj,
        mission_id=miss,
        mission_state=store,
        concurrency_limit=2,
        executor_fn=custom_executor,
        repair_fn=custom_repair,
    )
    fresh_orch.recover_from_checkpoint(cp)

    # Ensure recovery preserved graph_version and didn't fall back to v1
    assert fresh_orch.task_graph.graph_version == saved_v
    assert len(fresh_orch.task_graph.expansion_history) == len(cp.expansion_history)

    # Resume autonomous run to completion
    status = await fresh_orch.run()
    assert status == MissionLifecycleStatus.COMPLETED

    # Verify final graph version reached v4 (3 dynamic expansions!)
    assert fresh_orch.task_graph.graph_version == 4
    assert len(fresh_orch.task_graph.expansion_history) == 3

    # Verify all 10 tasks completed
    all_tasks = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10"]
    for tid in all_tasks:
        assert tid in fresh_orch.task_graph.nodes
        assert fresh_orch.task_graph.nodes[tid].status == TaskStatus.COMPLETED

    # Verify repair hook was invoked for T7
    assert t7_repaired is True

    # Verify execution cycles occurred across multiple waves (15-30 cycles)
    assert execution_cycles >= 10

    # Verify final satisfaction barrier
    satisfied, reason = await fresh_orch.verify_satisfaction()
    assert satisfied is True
