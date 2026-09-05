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
from agents.task_graph import (
    FailureCategory,
    FailureInfo,
    RetryConfig,
    TaskGraph,
    TaskNode,
    TaskStatus,
)


def test_transient_failure_retry_success(tmp_path):
    async def _run():
        store = MissionStateStore(str(tmp_path))
        os.makedirs(os.path.join(store.projects_root, "test-proj"), exist_ok=True)
        store.create_mission("test-proj", "Retry Test", "Test retry", mission_id="m_retry_01")
        
        task = TaskNode(
            task_id="T1",
            title="Flaky Task",
            retry_config=RetryConfig(max_attempts=3, initial_delay_seconds=0.01, backoff_factor=1.0),
        )
        graph = TaskGraph([task])

        attempts = 0

        async def flaky_executor(project_id: str, node: TaskNode, context: dict) -> TaskExecutionResult:
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                return TaskExecutionResult(
                    success=False,
                    task_id=node.task_id,
                    failure_category=FailureCategory.TRANSIENT_FAILURE,
                    error_message="Network glitch",
                )
            return TaskExecutionResult(
                success=True,
                task_id=node.task_id,
                summary="Succeeded on attempt 2",
            )

        orchestrator = MissionLifecycleOrchestrator(
            project_id="test-proj",
            mission_id="m_retry_01",
            mission_state=store,
            task_graph=graph,
            executor_fn=flaky_executor,
        )

        status = await orchestrator.run()

        assert status == MissionLifecycleStatus.COMPLETED
        assert attempts == 2
        assert graph.get_node("T1").status == TaskStatus.COMPLETED

    asyncio.run(_run())


def test_validation_failure_triggers_minimal_repair(tmp_path):
    async def _run():
        store = MissionStateStore(str(tmp_path))
        os.makedirs(os.path.join(store.projects_root, "test-proj"), exist_ok=True)
        store.create_mission("test-proj", "Repair Test", "Test repair loop", mission_id="m_repair_01")

        task = TaskNode(
            task_id="T1",
            title="Syntax Error Task",
            retry_config=RetryConfig(max_attempts=3, initial_delay_seconds=0.01),
        )
        graph = TaskGraph([task])

        repair_called = False
        repaired = False

        async def broken_code_executor(project_id: str, node: TaskNode, context: dict) -> TaskExecutionResult:
            nonlocal repaired
            if not repaired:
                return TaskExecutionResult(
                    success=False,
                    task_id=node.task_id,
                    failure_category=FailureCategory.VALIDATION_FAILURE,
                    error_message="SyntaxError on line 5",
                )
            return TaskExecutionResult(
                success=True,
                task_id=node.task_id,
                summary="Code validated and passed tests",
            )

        async def minimal_repair_hook(project_id: str, node: TaskNode, fail_info: FailureInfo, context: dict) -> bool:
            nonlocal repair_called, repaired
            repair_called = True
            repaired = True  # Simulated targeted repair
            return True

        orchestrator = MissionLifecycleOrchestrator(
            project_id="test-proj",
            mission_id="m_repair_01",
            mission_state=store,
            task_graph=graph,
            executor_fn=broken_code_executor,
            repair_fn=minimal_repair_hook,
        )

        status = await orchestrator.run()

        assert status == MissionLifecycleStatus.COMPLETED
        assert repair_called is True
        assert graph.get_node("T1").status == TaskStatus.COMPLETED

    asyncio.run(_run())


def test_permanent_failure_exhausts_and_fails_mission(tmp_path):
    async def _run():
        store = MissionStateStore(str(tmp_path))
        os.makedirs(os.path.join(store.projects_root, "test-proj"), exist_ok=True)
        store.create_mission("test-proj", "Fail Test", "Test permanent fail", mission_id="m_fail_01")

        task = TaskNode(
            task_id="T1",
            title="Fatal Task",
            retry_config=RetryConfig(max_attempts=2, initial_delay_seconds=0.01),
        )
        graph = TaskGraph([task])

        async def fatal_executor(project_id: str, node: TaskNode, context: dict) -> TaskExecutionResult:
            return TaskExecutionResult(
                success=False,
                task_id=node.task_id,
                failure_category=FailureCategory.PERMANENT_FAILURE,
                error_message="Hardware failure / unrecoverable error",
            )

        orchestrator = MissionLifecycleOrchestrator(
            project_id="test-proj",
            mission_id="m_fail_01",
            mission_state=store,
            task_graph=graph,
            executor_fn=fatal_executor,
        )

        status = await orchestrator.run()

        assert status == MissionLifecycleStatus.FAILED
        assert graph.get_node("T1").status == TaskStatus.FAILED

    asyncio.run(_run())
