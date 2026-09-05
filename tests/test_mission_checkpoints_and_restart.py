from __future__ import annotations

import asyncio
import os
import pytest

from agents.mission_orchestrator import (
    MissionLifecycleOrchestrator,
    MissionLifecycleStatus,
    TaskExecutionResult,
)
from agents.mission_state import MissionStateStore
from agents.task_graph import TaskGraph, TaskNode, TaskStatus


def test_checkpoint_save_and_restore(tmp_path):
    store = MissionStateStore(str(tmp_path))
    os.makedirs(os.path.join(store.projects_root, "test-proj"), exist_ok=True)
    store.create_mission("test-proj", "CP Test", "Testing checkpoints", mission_id="m_cp_01")

    task_a = TaskNode(task_id="A", title="Task A", status=TaskStatus.COMPLETED)
    task_b = TaskNode(task_id="B", title="Task B", dependencies=["A"], status=TaskStatus.READY)
    graph = TaskGraph([task_a, task_b])

    orchestrator = MissionLifecycleOrchestrator(
        project_id="test-proj",
        mission_id="m_cp_01",
        mission_state=store,
        task_graph=graph,
    )

    cp = orchestrator.save_checkpoint("Snapshot after Task A")
    assert cp.sequence == 1
    assert "A" in cp.completed_task_ids

    latest_cp = orchestrator.load_latest_checkpoint()
    assert latest_cp is not None
    assert latest_cp.checkpoint_id == cp.checkpoint_id


def test_process_restart_recovers_interrupted_task_and_resumes(tmp_path):
    async def _run():
        store = MissionStateStore(str(tmp_path))
        os.makedirs(os.path.join(store.projects_root, "test-proj"), exist_ok=True)
        store.create_mission("test-proj", "Restart Test", "Simulating process crash", mission_id="m_restart_01")

        # 1. First run: Task A completes, Task B starts and gets checkpointed as RUNNING, then process crashes
        task_a = TaskNode(task_id="A", title="Task A")
        task_b = TaskNode(task_id="B", title="Task B", dependencies=["A"])
        graph = TaskGraph([task_a, task_b])

        orch1 = MissionLifecycleOrchestrator(
            project_id="test-proj",
            mission_id="m_restart_01",
            mission_state=store,
            task_graph=graph,
        )

        # Simulate A completed, B running
        task_a.status = TaskStatus.COMPLETED
        task_b.status = TaskStatus.RUNNING
        orch1._running_tasks.add("B")
        cp_before_crash = orch1.save_checkpoint("Checkpoint right before crash")

        # 2. Simulate process restart: Create fresh orchestrator instance, load checkpoint
        fresh_orch = MissionLifecycleOrchestrator(
            project_id="test-proj",
            mission_id="m_restart_01",
            mission_state=store,
        )
        loaded_cp = fresh_orch.load_latest_checkpoint()
        assert loaded_cp is not None
        fresh_orch.recover_from_checkpoint(loaded_cp)

        # Verify: Task A remained COMPLETED, Task B was reconciled from RUNNING -> READY
        assert fresh_orch.task_graph.get_node("A").status == TaskStatus.COMPLETED
        assert fresh_orch.task_graph.get_node("B").status == TaskStatus.READY

        # Execute remaining task to completion
        async def fake_executor(project_id: str, node: TaskNode, context: dict) -> TaskExecutionResult:
            return TaskExecutionResult(success=True, task_id=node.task_id, summary="Task B finished post-restart")

        fresh_orch.executor_fn = fake_executor
        final_status = await fresh_orch.run()

        assert final_status == MissionLifecycleStatus.COMPLETED
        assert fresh_orch.task_graph.get_node("B").status == TaskStatus.COMPLETED

    asyncio.run(_run())
