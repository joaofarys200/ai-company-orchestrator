from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable

from backend.model_harness.contracts import (
    ModelRequest,
    ModelResponse,
    ModelResponseStatus,
    ProgressCondition,
    RecoveryAction,
    RecoveryRecord,
    ValidationStage,
)
from backend.model_harness.errors import RecoveryPolicyError, UnsafeRecoveryError
from backend.model_harness.progress import ProgressSnapshot


RecoveryTransformer = Callable[
    [ModelRequest, ModelResponse, RecoveryRecord],
    ModelRequest | None | Awaitable[ModelRequest | None],
]


class RecoveryPolicy:
    """Classifies recovery; it never mutates prompts by itself."""

    def __init__(self, name: str):
        self.name = str(name or "").strip().upper()
        if not self.name:
            raise RecoveryPolicyError("Recovery policy sem nome.")

    def decide(
        self,
        response: ModelResponse,
        progress: ProgressSnapshot,
    ) -> RecoveryRecord:
        if self.name == "NONE":
            return RecoveryRecord(
                action=(
                    RecoveryAction.NONE
                    if response.status == ModelResponseStatus.SUCCEEDED
                    else RecoveryAction.STOP
                ),
                reason="recovery_policy_disabled",
                recoverable=False,
            )
        if any(
            condition in progress.conditions
            for condition in (
                ProgressCondition.NO_PROGRESS,
                ProgressCondition.REPEATED_REASONING,
                ProgressCondition.REPEATED_TOOL_CALLS,
                ProgressCondition.REPEATED_FAILURES,
            )
        ):
            return RecoveryRecord(
                action=RecoveryAction.STOP,
                reason="progress_guard_triggered",
                recoverable=False,
            )
        if response.status == ModelResponseStatus.PROVIDER_FAILED:
            return RecoveryRecord(
                action=RecoveryAction.ESCALATION,
                reason="provider_failed",
                recoverable=False,
            )
        if response.status != ModelResponseStatus.VALIDATION_FAILED:
            return RecoveryRecord(
                action=RecoveryAction.NONE,
                reason="recovery_not_required",
                recoverable=False,
            )
        issue = response.validation.issues[0]
        if not issue.recoverable:
            return RecoveryRecord(
                action=RecoveryAction.STOP,
                reason=f"non_recoverable:{issue.code}",
                recoverable=False,
            )
        if issue.code == "OUTPUT_TRUNCATED":
            action = RecoveryAction.MECHANICAL_COMPLETION
        elif issue.stage == ValidationStage.PARSING:
            action = RecoveryAction.PARSE_RECOVERY
        elif issue.stage in {
            ValidationStage.SCHEMA,
            ValidationStage.ENUMS,
            ValidationStage.REFERENCES,
            ValidationStage.PRECONDITIONS,
        }:
            action = RecoveryAction.SEMANTIC_RETRY
        else:
            action = RecoveryAction.CONTRADICTION_RETRY
        return RecoveryRecord(
            action=action,
            reason=f"{issue.stage.value}:{issue.code}",
            recoverable=True,
            retry_requested=True,
        )


class RecoveryPolicyRegistry:
    def __init__(self):
        self._policies = {
            name: RecoveryPolicy(name)
            for name in (
                "NONE",
                "STRUCTURED_CONSERVATIVE",
                "SEMANTIC_CONSERVATIVE",
            )
        }

    def get(self, name: str) -> RecoveryPolicy:
        normalized = str(name or "").strip().upper()
        try:
            return self._policies[normalized]
        except KeyError as exc:
            raise RecoveryPolicyError(
                f"Recovery policy desconhecida: {normalized}."
            ) from exc


class RecoveryCoordinator:
    def __init__(
        self,
        policies: RecoveryPolicyRegistry | None = None,
        transformer: RecoveryTransformer | None = None,
    ):
        self.policies = policies or RecoveryPolicyRegistry()
        self.transformer = transformer

    def decide(
        self,
        policy_name: str,
        response: ModelResponse,
        progress: ProgressSnapshot,
    ) -> RecoveryRecord:
        return self.policies.get(policy_name).decide(response, progress)

    async def transform(
        self,
        request: ModelRequest,
        response: ModelResponse,
        decision: RecoveryRecord,
    ) -> ModelRequest | None:
        if not decision.retry_requested or self.transformer is None:
            return None
        updated = self.transformer(request, response, decision)
        if inspect.isawaitable(updated):
            updated = await updated
        if updated is None:
            return None
        if not isinstance(updated, ModelRequest):
            raise RecoveryPolicyError(
                "Recovery transformer devolveu tipo invalido."
            )
        if updated.fingerprint() == request.fingerprint():
            raise UnsafeRecoveryError(
                "Recovery recusado: a nova prompt e identica a anterior."
            )
        return updated
