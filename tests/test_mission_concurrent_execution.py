from __future__ import annotations

import asyncio
import os
import time
import pytest

from agents.mission_orchestrator import (
    MissionLifecycleOrchestrator,
    MissionLifecycleStatus,
    TaskExecutionResult,
)
from agents.mission_state import MissionStateStore
from agents.task_graph import TaskGraph, TaskNode


def test_concurrent_and_sequential_execution(tmp_path):
    async def _run():
        store = MissionStateStore(str(tmp_path))
        os.makedirs(os.path.join(store.projects_root, "test-proj"), exist_ok=True)
        store.create_mission("test-proj", "Concurrent Test", "Test parallel work", mission_id="m_conc_01")
        
        # Build DAG:
        # A (independent)
        # B (independent)
        # C (depends on A and B)
        task_a = TaskNode(task_id="A", title="Parallel Task A")
        task_b = TaskNode(task_id="B", title="Parallel Task B")
        task_c = TaskNode(task_id="C", title="Sequential Task C", dependencies=["A", "B"])
        graph = TaskGraph([task_a, task_b, task_c])

        execution_log = []
        max_concurrent_observed = 0
        currently_running = 0

        async def fake_executor(project_id: str, node: TaskNode, context: dict) -> TaskExecutionResult:
            nonlocal currently_running, max_concurrent_observed
            currently_running += 1
            max_concurrent_observed = max(max_concurrent_observed, currently_running)
            execution_log.append(f"START_{node.task_id}")
            
            await asyncio.sleep(0.05)
            
            execution_log.append(f"END_{node.task_id}")
            currently_running -= 1
            return TaskExecutionResult(
                success=True,
                task_id=node.task_id,
                summary=f"{node.task_id} done",
            )

        orchestrator = MissionLifecycleOrchestrator(
            project_id="test-proj",
            mission_id="m_conc_01",
            mission_state=store,
            task_graph=graph,
            concurrency_limit=2,
            executor_fn=fake_executor,
        )

        status = await orchestrator.run()

        assert status == MissionLifecycleStatus.COMPLETED
        assert max_concurrent_observed == 2  # A and B ran concurrently
        assert execution_log.index("END_A") < execution_log.index("START_C")
        assert execution_log.index("END_B") < execution_log.index("START_C")

    asyncio.run(_run())
