from __future__ import annotations

import asyncio

from agents.executors.base import (
    WorkPackageExecutionContext,
    WorkPackageExecutionResult,
)


class CodingWorkPackageExecutor:
    kind = "CODING"

    async def execute(
        self,
        context: WorkPackageExecutionContext,
    ) -> WorkPackageExecutionResult:
        try:
            snapshot = await context.service._prepare_coding_execution(
                context.project_id,
                context.service._load_execution(
                    context.project_id,
                    context.mission_id,
                    context.execution_id,
                ),
            )
            if context.test_mode and context.allow_apply:
                execution = context.service._execution_from_snapshot(
                    snapshot,
                    context.execution_id,
                )
                snapshot = await asyncio.to_thread(
                    context.service.apply_execution,
                    context.project_id,
                    context.mission_id,
                    context.execution_id,
                    execution.version,
                    True,
                )
            return WorkPackageExecutionResult.from_snapshot(
                snapshot,
                context.execution_id,
                rollback_capable=True,
            )
        except Exception as exc:
            return WorkPackageExecutionResult.from_exception(
                exc,
                phase="CODING_EXECUTOR_FAILED",
                rollback_capable=True,
            )
