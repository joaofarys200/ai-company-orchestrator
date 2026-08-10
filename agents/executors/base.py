from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


EXECUTOR_RISK_LEVELS = {"LOW", "MEDIUM", "HIGH"}


@dataclass(frozen=True)
class ExecutorDescriptor:
    kind: str
    executor_name: str | None
    supported: bool
    requires_apply_approval: bool
    autonomous_allowed: bool
    risk_level: str
    description: str

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "supported": self.supported,
            "executor": self.executor_name,
            "executor_name": self.executor_name,
            "requires_apply_approval": self.requires_apply_approval,
            "autonomous_allowed": self.autonomous_allowed,
            "risk_level": self.risk_level,
            "description": self.description,
        }


@dataclass
class WorkPackageExecutionContext:
    project_id: str
    mission_id: str
    execution_id: str
    executor_kind: str
    mission: dict[str, Any]
    work_package: dict[str, Any]
    execution_snapshot: dict[str, Any]
    input_snapshot: dict[str, Any]
    test_mode: bool
    autonomous: bool
    allow_apply: bool
    service: Any = field(repr=False)
    model_harness: Any = field(default=None, repr=False)
    agent_profile: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkPackageExecutionResult:
    status: str
    phase: str
    output_summary: dict[str, Any] = field(default_factory=dict)
    artifact_refs: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    validation_refs: list[str] = field(default_factory=list)
    requires_review: bool = False
    error: dict[str, Any] | None = None
    rollback_capable: bool = False
    snapshot: dict[str, Any] | None = field(default=None, repr=False)
    exception: Exception | None = field(default=None, repr=False, compare=False)

    @classmethod
    def from_snapshot(
        cls,
        snapshot: dict[str, Any],
        execution_id: str,
        *,
        rollback_capable: bool = False,
    ) -> "WorkPackageExecutionResult":
        execution = next(
            (
                item
                for item in snapshot.get("executions") or []
                if item.get("execution_id") == execution_id
            ),
            {},
        )
        status = str(execution.get("status") or "FAILED")
        output = dict(execution.get("output_summary") or {})
        phase = str(output.get("phase") or status)
        return cls(
            status=status,
            phase=phase,
            output_summary=output,
            artifact_refs=list(execution.get("artifact_refs") or []),
            evidence_refs=list(execution.get("evidence_refs") or []),
            validation_refs=list(execution.get("validation_refs") or []),
            requires_review=(
                status == "WAITING_FOR_REVIEW"
                or phase == "AWAITING_APPLY_APPROVAL"
            ),
            error=execution.get("primary_error"),
            rollback_capable=rollback_capable,
            snapshot=snapshot,
        )

    @classmethod
    def from_exception(
        cls,
        error: Exception,
        *,
        phase: str = "EXECUTOR_FAILED",
        rollback_capable: bool = False,
    ) -> "WorkPackageExecutionResult":
        return cls(
            status="FAILED",
            phase=phase,
            error={
                "type": type(error).__name__,
                "message": str(error),
                "traceback": "".join(
                    traceback.format_exception(type(error), error, error.__traceback__)
                ),
            },
            rollback_capable=rollback_capable,
            exception=error,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "phase": self.phase,
            "output_summary": self.output_summary,
            "artifact_refs": self.artifact_refs,
            "evidence_refs": self.evidence_refs,
            "validation_refs": self.validation_refs,
            "requires_review": self.requires_review,
            "error": self.error,
            "rollback_capable": self.rollback_capable,
        }


@runtime_checkable
class WorkPackageExecutor(Protocol):
    kind: str

    async def execute(
        self,
        context: WorkPackageExecutionContext,
    ) -> WorkPackageExecutionResult:
        ...
