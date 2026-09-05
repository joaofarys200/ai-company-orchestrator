from __future__ import annotations

import asyncio
import json
import os
import pytest

from agents.mission_orchestrator import (
    MissionLifecycleOrchestrator,
    MissionLifecycleStatus,
    TaskExecutionResult,
)
from agents.mission_state import MissionStateStore
from agents.task_graph import (
    FailureCategory,
    RetryConfig,
    TaskGraph,
    TaskNode,
    TaskStatus,
)


def test_chaos_timeout_handling(tmp_path):
    async def _run():
        store = MissionStateStore(str(tmp_path))
        os.makedirs(os.path.join(store.projects_root, "test-proj"), exist_ok=True)
        store.create_mission("test-proj", "Chaos Timeout", "Testing timeout handling", mission_id="m_chaos_01")

        task = TaskNode(
            task_id="T1",
            title="Hanging Task",
            timeout_seconds=0.05,
            retry_config=RetryConfig(max_attempts=2, initial_delay_seconds=0.01),
        )
        graph = TaskGraph([task])

        async def hanging_executor(project_id: str, node: TaskNode, context: dict) -> TaskExecutionResult:
            await asyncio.sleep(1.0)  # Exceeds 0.05s timeout
            return TaskExecutionResult(success=True, task_id=node.task_id)

        orchestrator = MissionLifecycleOrchestrator(
            project_id="test-proj",
            mission_id="m_chaos_01",
            mission_state=store,
            task_graph=graph,
            executor_fn=hanging_executor,
        )

        status = await orchestrator.run()

        # Both attempts timeout -> FAILED
        assert status == MissionLifecycleStatus.FAILED
        assert graph.get_node("T1").status == TaskStatus.FAILED
        assert graph.get_node("T1").attempt_count == 2
        assert graph.get_node("T1").failure_info.category == FailureCategory.TIMEOUT

    asyncio.run(_run())


def test_chaos_corrupted_checkpoint_recovery(tmp_path):
    store = MissionStateStore(str(tmp_path))
    os.makedirs(os.path.join(store.projects_root, "test-proj"), exist_ok=True)
    store.create_mission("test-proj", "Chaos CP", "Testing corrupted checkpoint", mission_id="m_chaos_cp_01")

    orch = MissionLifecycleOrchestrator(
        project_id="test-proj",
        mission_id="m_chaos_cp_01",
        mission_state=store,
    )

    # 1. Save valid checkpoint 1
    orch.save_checkpoint("Valid CP 1")

    # 2. Write completely corrupted checkpoint 2
    corrupt_path = os.path.join(orch.checkpoints_dir, "checkpoint_0002.json")
    with open(corrupt_path, "w", encoding="utf-8") as f:
        f.write("{ INVALID JSON CORRUPTED DATA !!! @#$")

    # Loading corrupted checkpoint should handle gracefully without crashing
    cp = orch.load_latest_checkpoint()
    assert cp is None or cp.sequence == 1
