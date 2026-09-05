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
    MissionLifecycleOrchestrator,
    MissionLifecycleStatus,
    TaskExecutionResult,
)
from agents.mission_state import MissionStateStore
from agents.task_graph import TaskGraph, TaskNode, TaskStatus


@pytest.fixture
def temp_workspace() -> tuple[str, MissionStateStore]:
    test_id = uuid.uuid4().hex[:8]
    root = os.path.abspath(f"test_ws_subdag_integ_{test_id}")
    os.makedirs(os.path.join(root, "workspace", "projects"), exist_ok=True)
    store = MissionStateStore(workspace_root=root)
    yield root, store
    shutil.rmtree(root, ignore_errors=True)


@pytest.mark.anyio
async def test_subdag_full_integration_flow(temp_workspace: tuple[str, MissionStateStore]) -> None:
    """End-to-end integration scenario (Section 30 of spec):
    1. Mission starts with Task A in INITIAL GRAPH (v1).
    2. Task A executes and discovers requirement for B, C, D (B -> C, B -> D).
    3. Runtime validates, accepts, increments to GRAPH v2, schedules B.
    4. Task B completes successfully.
    5. Tasks C and D become READY. Task C fails transiently on attempt 1, retries and succeeds on attempt 2.
    6. Task D completes.
    7. All tasks complete, evidence gathered, satisfaction barrier verifies mission completion.
    """
    _, store = temp_workspace
    proj = "p_integ"
    miss = "m_integ"
    os.makedirs(os.path.join(store.projects_root, proj), exist_ok=True)
    store.create_mission(proj, "Dynamic Sub-DAG Integration", "Demonstrate end-to-end autonomous discovery", mission_id=miss)
    store.create_work_package(
        project_id=proj,
        mission_id=miss,
        title="Initial Task A",
        work_package_id="TASK_A",
    )

    # Initial graph with Task A
    node_a = TaskNode(task_id="TASK_A", title="Initial Task A", status=TaskStatus.PENDING)
    graph = TaskGraph([node_a])

    c_attempts = 0

    async def custom_executor(project_id: str, node: TaskNode, context: dict) -> TaskExecutionResult:
        nonlocal c_attempts
        await asyncio.sleep(0.01)

        if node.task_id == "TASK_A":
            # Task A discovers need for B, C, D
            subdag_prop = DynamicSubDagProposal(
                proposal_id="prop_integ_1",
                mission_id=miss,
                parent_task_id="TASK_A",
                base_graph_version=1,
                reason="Task A identified need for helper pipeline B -> (C, D)",
                trigger=ExpansionTrigger.REQUIREMENT_DISCOVERY,
                tasks=[
                    {"task_id": "TASK_B", "title": "Setup Pipeline B", "dependencies": ["TASK_A"]},
                    {"task_id": "TASK_C", "title": "Data Ingest C", "dependencies": ["TASK_B"]},
                    {"task_id": "TASK_D", "title": "Model Training D", "dependencies": ["TASK_B"]},
                ],
                dependencies=[("TASK_B", "TASK_C"), ("TASK_B", "TASK_D")],
                acceptance_criteria=[
                    {"criterion_id": "crit_c", "owner_id": "TASK_C", "description": "Ingest validated"},
                    {"criterion_id": "crit_d", "owner_id": "TASK_D", "description": "Training validated"},
                ],
            )
            return TaskExecutionResult(
                success=True,
                task_id=node.task_id,
                summary="Task A completed and proposed subdag B, C, D",
                subdag_proposal=subdag_prop,
            )

        elif node.task_id == "TASK_B":
            return TaskExecutionResult(
                success=True,
                task_id=node.task_id,
                summary="Setup Pipeline B completed successfully.",
            )

        elif node.task_id == "TASK_C":
            c_attempts += 1
            if c_attempts == 1:
                # Transient failure on first attempt
                return TaskExecutionResult(
                    success=False,
                    task_id=node.task_id,
                    failure_category=FailureCategory.TRANSIENT_FAILURE,
                    error_message="Transient network glitch in Ingest C",
                )
            else:
                return TaskExecutionResult(
                    success=True,
                    task_id=node.task_id,
                    summary="Ingest C succeeded on retry.",
                )

        elif node.task_id == "TASK_D":
            return TaskExecutionResult(
                success=True,
                task_id=node.task_id,
                summary="Model Training D completed successfully.",
            )

        return TaskExecutionResult(success=True, task_id=node.task_id)

    orch = MissionLifecycleOrchestrator(
        project_id=proj,
        mission_id=miss,
        mission_state=store,
        task_graph=graph,
        concurrency_limit=2,
        executor_fn=custom_executor,
    )

    status = await orch.run()
    assert status == MissionLifecycleStatus.COMPLETED

    # Verify Graph Version incremented to v2
    assert orch.task_graph.graph_version == 2
    assert len(orch.task_graph.expansion_history) == 1
    assert orch.task_graph.expansion_history[0]["proposal_id"] == "prop_integ_1"

    # Verify all 4 tasks are COMPLETED
    assert orch.task_graph.nodes["TASK_A"].status == TaskStatus.COMPLETED
    assert orch.task_graph.nodes["TASK_B"].status == TaskStatus.COMPLETED
    assert orch.task_graph.nodes["TASK_C"].status == TaskStatus.COMPLETED
    assert orch.task_graph.nodes["TASK_D"].status == TaskStatus.COMPLETED

    # Verify Task C made exactly 2 attempts (retry succeeded)
    assert c_attempts == 2
    assert orch.task_graph.nodes["TASK_C"].attempt_count == 2

    # Verify satisfaction
    satisfied, reason = await orch.verify_satisfaction()
    assert satisfied is True
