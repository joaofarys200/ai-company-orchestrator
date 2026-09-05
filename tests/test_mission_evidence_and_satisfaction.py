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


def test_evidence_attachment_and_satisfaction(tmp_path):
    async def _run():
        store = MissionStateStore(str(tmp_path))
        os.makedirs(os.path.join(store.projects_root, "test-proj"), exist_ok=True)
        store.create_mission("test-proj", "Evidence Test", "Testing evidence & criteria", mission_id="m_evi_01")
        store.create_work_package("test-proj", "m_evi_01", "Build Backend", work_package_id="T1", required=True)
        crit = store.create_criterion("test-proj", "m_evi_01", owner_type="WORK_PACKAGE", owner_id="T1", description="Valid test suite pass", required=True, criterion_id="c1")

        task = TaskNode(task_id="T1", title="Build Backend")
        graph = TaskGraph([task])

        async def executor_with_evidence(project_id: str, node: TaskNode, context: dict) -> TaskExecutionResult:
            return TaskExecutionResult(
                success=True,
                task_id=node.task_id,
                summary="Backend built with 10 passing tests",
                evidence=[{
                    "kind": "TEST_RESULTS",
                    "source_ref": "validation:pytest_output",
                    "description": "10/10 tests passed in 0.4s",
                }],
            )

        orchestrator = MissionLifecycleOrchestrator(
            project_id="test-proj",
            mission_id="m_evi_01",
            mission_state=store,
            task_graph=graph,
            executor_fn=executor_with_evidence,
        )

        # Before criterion is satisfied, verify_satisfaction returns False
        satisfied, reason = await orchestrator.verify_satisfaction()
        assert satisfied is False

        # Run task -> evidence attached
        await orchestrator._execute_task_with_retry_and_recovery(task)
        assert len(task.evidence_refs) == 1

        # Satisfy criterion using attached evidence
        loaded = store.load_mission("test-proj", "m_evi_01")
        crit_item = [c for c in loaded["acceptance_criteria"] if c["criterion_id"] == "c1"][0]
        store.set_criterion_status(
            "test-proj",
            "m_evi_01",
            "c1",
            "SATISFIED",
            expected_version=crit_item["version"],
            evidence_refs=task.evidence_refs,
        )

        # Now verify_satisfaction must pass
        satisfied, reason = await orchestrator.verify_satisfaction()
        assert satisfied is True

    asyncio.run(_run())
