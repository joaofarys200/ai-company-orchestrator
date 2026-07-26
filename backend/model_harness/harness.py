from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

from backend.model_harness.contracts import (
    ModelRequest,
    ModelResponse,
    ModelResponseStatus,
    ValidationResult,
    ValidationStatus,
)
from backend.model_harness.errors import InvalidModelRequestError
from backend.model_harness.profiles import (
    TaskProfile,
    TaskProfileRegistry,
    create_default_task_profile_registry,
)
from backend.model_harness.progress import ProgressTracker
from backend.model_harness.provider import ProviderRegistry
from backend.model_harness.recovery import RecoveryCoordinator
from backend.model_harness.router import ModelRouter
from backend.model_harness.telemetry import ModelTelemetry
from backend.model_harness.validation import ModelValidationPipeline


class ModelHarness:
    """The single execution boundary between consumers and model providers."""

    def __init__(
        self,
        providers: ProviderRegistry,
        *,
        profiles: TaskProfileRegistry | None = None,
        router: ModelRouter | None = None,
        validation: ModelValidationPipeline | None = None,
        recovery: RecoveryCoordinator | None = None,
        telemetry: ModelTelemetry | None = None,
    ):
        self.providers = providers
        self.profiles = profiles or create_default_task_profile_registry()
        self.router = router or ModelRouter(providers)
        self.validation = validation or ModelValidationPipeline()
        self.recovery = recovery or RecoveryCoordinator()
        self.telemetry = telemetry or ModelTelemetry()
        self._progress: dict[str, ProgressTracker] = {}

    async def execute(self, request: ModelRequest) -> ModelResponse:
        if not isinstance(request, ModelRequest):
            raise InvalidModelRequestError(
                "ModelHarness.execute requer ModelRequest."
            )
        profile = self.profiles.get(request.task_profile)
        current = self._apply_profile(request, profile)
        progress_key = str(
            current.metadata.get("progress_key")
            or current.request_id
        )
        tracker = self._tracker(progress_key)
        recovery_history = []
        attempt = 0

        while attempt < current.execution_constraints.max_attempts:
            attempt += 1
            tracker.record_input(current.fingerprint())
            started = time.perf_counter()
            route = None
            try:
                route = self.router.route(current, profile)
                provider = self.providers.get(route.provider)
                provider_result = await provider.generate(
                    current,
                    route,
                    tracker,
                )
                tracker.record_output(provider_result.raw_text)
                for tool_call in provider_result.tool_calls:
                    tracker.record_tool_call(
                        tool_call.name,
                        tool_call.arguments,
                    )
                expected = (
                    current.expected_output
                    or profile.expected_output
                )
                validation = self.validation.validate(
                    current,
                    route,
                    provider_result,
                    profile.validation_pipeline,
                    expected,
                )
                status = (
                    ModelResponseStatus.SUCCEEDED
                    if validation.is_valid
                    else ModelResponseStatus.VALIDATION_FAILED
                )
                response = ModelResponse(
                    request_id=current.request_id,
                    status=status,
                    raw_text=provider_result.raw_text,
                    structured_output=validation.structured_output,
                    usage=provider_result.usage,
                    provider=route.provider,
                    model=route.model,
                    latency_ms=self._elapsed_ms(started),
                    validation=validation,
                    tool_calls=provider_result.tool_calls,
                    warnings=provider_result.warnings,
                )
            except Exception as exc:
                tracker.record_failure(type(exc).__name__)
                response = ModelResponse(
                    request_id=current.request_id,
                    status=ModelResponseStatus.PROVIDER_FAILED,
                    provider=route.provider if route else "",
                    model=route.model if route else "",
                    latency_ms=self._elapsed_ms(started),
                    validation=ValidationResult(
                        status=ValidationStatus.NOT_RUN
                    ),
                    errors=({
                        "stage": "PROVIDER",
                        "type": type(exc).__name__,
                        "message": str(exc),
                    },),
                    provider_exception=exc,
                )

            progress = tracker.snapshot()
            decision = self.recovery.decide(
                profile.recovery_policy,
                response,
                progress,
            )
            if (
                progress.conditions
                and current.execution_constraints.stop_on_no_progress
            ):
                response.status = ModelResponseStatus.STOPPED
            recovery_history.append(decision)
            response.recovery = tuple(recovery_history)
            self._record_telemetry(
                current,
                profile,
                response,
                progress,
                decision.action.value,
            )

            can_transform = (
                current.execution_constraints.allow_recovery
                and decision.retry_requested
                and attempt < current.execution_constraints.max_attempts
            )
            if not can_transform:
                return response
            updated = await self.recovery.transform(
                current,
                response,
                decision,
            )
            if updated is None:
                return response
            recovery_history[-1] = replace(
                decision,
                input_changed=True,
            )
            current = self._apply_profile(updated, profile)

        return response

    def diagnostics(self) -> dict[str, Any]:
        return {
            "profiles": tuple(self.profiles.describe()),
            "providers": self.providers.names(),
            "telemetry": self.telemetry.snapshot(),
            "progress_keys": len(self._progress),
        }

    def _apply_profile(
        self,
        request: ModelRequest,
        profile: TaskProfile,
    ) -> ModelRequest:
        allowed = set(profile.allowed_tools)
        if "*" not in allowed and not set(request.allowed_tools).issubset(
            allowed
        ):
            raise InvalidModelRequestError(
                "O pedido inclui tools nao permitidas pelo TaskProfile."
            )
        return replace(
            request,
            task_profile=profile.name,
            expected_output=(
                request.expected_output or profile.expected_output
            ),
            temperature=(
                profile.temperature
                if request.temperature is None
                else request.temperature
            ),
            max_context_tokens=(
                profile.max_context_tokens
                if request.max_context_tokens is None
                else request.max_context_tokens
            ),
            max_output_tokens=(
                profile.max_output_tokens
                if request.max_output_tokens is None
                else request.max_output_tokens
            ),
        )

    def _tracker(self, key: str) -> ProgressTracker:
        if key not in self._progress:
            if len(self._progress) >= 256:
                oldest = next(iter(self._progress))
                self._progress.pop(oldest, None)
            self._progress[key] = ProgressTracker()
        return self._progress[key]

    def _record_telemetry(
        self,
        request: ModelRequest,
        profile: TaskProfile,
        response: ModelResponse,
        progress,
        recovery_action: str,
    ) -> None:
        self.telemetry.record(
            request_id=request.request_id,
            request_fingerprint=request.fingerprint(),
            task_profile=profile.name,
            provider=response.provider,
            model=response.model,
            latency_ms=response.latency_ms,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            pipeline=profile.validation_pipeline,
            validation_status=response.validation.status.value,
            recovery_action=recovery_action,
            result_status=response.status.value,
            context_items=len(request.context.items),
            allowed_tool_count=len(request.allowed_tools),
            progress_conditions=tuple(
                item.value for item in progress.conditions
            ),
            metadata_keys=tuple(sorted(
                str(key)
                for key in request.metadata
                if str(key).lower()
                not in {
                    "prompt",
                    "system_prompt",
                    "user_prompt",
                    "context",
                    "content",
                    "api_key",
                    "token",
                    "secret",
                }
            )),
        )

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return max(0, int((time.perf_counter() - started) * 1000))
