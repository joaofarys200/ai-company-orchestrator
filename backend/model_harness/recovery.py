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
                recoverable=True,
                retry_requested=True,
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


def default_recovery_transformer(
    request: ModelRequest,
    response: ModelResponse,
    decision: RecoveryRecord,
) -> ModelRequest | None:
    from dataclasses import replace
    if response.status == ModelResponseStatus.PROVIDER_FAILED:
        failover_prompt = request.user_prompt + "\n\n[NOTIFICACAO DE FAILOVER: Provider alternado por resiliencia]"
        return replace(request, user_prompt=failover_prompt, metadata={**dict(request.metadata), "_failover": True})
    if not response.validation or not response.validation.issues:
        return None
    issue = response.validation.issues[0]
    repair_instruction = (
        f"\n\n[CORRECAO AUTONOMA - VIGIL ENGINE]\n"
        f"A sua tentativa anterior falhou na etapa {issue.stage.value} ({issue.code}).\n"
        f"Mensagem de erro: {issue.message}\n"
        f"INSTRUCAO: Corrija o formato imediatamente. Se for uma chamada de ferramenta/JSON, "
        f"forneca a estrutura estrita de argumentos sem texto extra."
    )
    from dataclasses import replace
    return replace(request, user_prompt=request.user_prompt + repair_instruction)


class RecoveryCoordinator:
    def __init__(
        self,
        policies: RecoveryPolicyRegistry | None = None,
        transformer: RecoveryTransformer | None = None,
    ):
        self.policies = policies or RecoveryPolicyRegistry()
        self.transformer = transformer or default_recovery_transformer

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
