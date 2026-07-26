from __future__ import annotations

from agents.executors.base import (
    WorkPackageExecutionContext,
    WorkPackageExecutionResult,
)


class ProjectBuildWorkPackageExecutor:
    kind = "PROJECT_BUILD"

    async def execute(
        self,
        context: WorkPackageExecutionContext,
    ) -> WorkPackageExecutionResult:
        try:
            snapshot = await context.service._run_project_builder(
                context.project_id,
                context.service._load_execution(
                    context.project_id,
                    context.mission_id,
                    context.execution_id,
                ),
                test_mode=context.test_mode,
            )
            return WorkPackageExecutionResult.from_snapshot(
                snapshot,
                context.execution_id,
                rollback_capable=False,
            )
        except Exception as exc:
            return WorkPackageExecutionResult.from_exception(
                exc,
                phase="PROJECT_BUILD_EXECUTOR_FAILED",
                rollback_capable=False,
            )
