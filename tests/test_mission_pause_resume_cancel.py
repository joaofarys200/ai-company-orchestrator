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


def test_mission_pause_and_resume(tmp_path):
    async def _run():
        store = MissionStateStore(str(tmp_path))
        os.makedirs(os.path.join(store.projects_root, "test-proj"), exist_ok=True)
        store.create_mission("test-proj", "Pause Test", "Testing pause/resume", mission_id="m_pause_01")

        task_a = TaskNode(task_id="A", title="Task A")
        task_b = TaskNode(task_id="B", title="Task B", dependencies=["A"])
        graph = TaskGraph([task_a, task_b])

        async def slow_executor(project_id: str, node: TaskNode, context: dict) -> TaskExecutionResult:
            await asyncio.sleep(0.05)
            return TaskExecutionResult(success=True, task_id=node.task_id, summary=f"{node.task_id} done")

        orchestrator = MissionLifecycleOrchestrator(
            project_id="test-proj",
            mission_id="m_pause_01",
            mission_state=store,
            task_graph=graph,
            executor_fn=slow_executor,
        )

        # Start orchestrator in background task
        run_task = asyncio.create_task(orchestrator.run())
        
        # Pause after slight delay
        await asyncio.sleep(0.02)
        await orchestrator.pause()
        
        # Wait for run to finish due to pause
        status_after_pause = await run_task
        assert status_after_pause == MissionLifecycleStatus.PAUSED
        assert orchestrator.status == MissionLifecycleStatus.PAUSED

        # Resume execution
        await orchestrator.resume()
        resume_task = asyncio.create_task(orchestrator.run())
        final_status = await resume_task

        assert final_status == MissionLifecycleStatus.COMPLETED
        assert orchestrator.task_graph.is_all_completed()

    asyncio.run(_run())


def test_mission_cancel(tmp_path):
    async def _run():
        store = MissionStateStore(str(tmp_path))
        os.makedirs(os.path.join(store.projects_root, "test-proj"), exist_ok=True)
        store.create_mission("test-proj", "Cancel Test", "Testing cancel", mission_id="m_cancel_01")

        task_a = TaskNode(task_id="A", title="Task A")
        task_b = TaskNode(task_id="B", title="Task B", dependencies=["A"])
        graph = TaskGraph([task_a, task_b])

        async def slow_executor(project_id: str, node: TaskNode, context: dict) -> TaskExecutionResult:
            await asyncio.sleep(0.1)
            return TaskExecutionResult(success=True, task_id=node.task_id, summary=f"{node.task_id} done")

        orchestrator = MissionLifecycleOrchestrator(
            project_id="test-proj",
            mission_id="m_cancel_01",
            mission_state=store,
            task_graph=graph,
            executor_fn=slow_executor,
        )

        run_task = asyncio.create_task(orchestrator.run())
        await asyncio.sleep(0.02)
        await orchestrator.cancel(reason="User aborted mission")

        final_status = await run_task
        assert final_status == MissionLifecycleStatus.CANCELLED
        assert orchestrator.status == MissionLifecycleStatus.CANCELLED

    asyncio.run(_run())
