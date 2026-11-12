from __future__ import annotations

import os
from typing import Any, Callable

from backend.model_harness import (
    ExecutionConstraints,
    ExpectedOutput,
    ModelPreferences,
    ModelRequest,
    ModelResponse,
    ModelResponseStatus,
    OllamaExecutionOptions,
    OutputFormat,
)


class ModelExecutionService:
    """Productive model boundary backed by the shared ModelHarness."""

    def __init__(self, harness: Any = None) -> None:
        self.harness = harness

    def _resolve_harness(self) -> Any:
        if self.harness is not None:
            return self.harness
        from backend.model_harness.runtime import get_model_harness

        return get_model_harness()

    def get_provider_endpoint(self, provider: str = "ollama") -> str | None:
        """Return the configured base URL for a registered provider, if exposed."""
        try:
            harness = self._resolve_harness()
            provider_impl = harness.providers.get(provider)
        except Exception:
            return None
        base_url = getattr(provider_impl, "base_url", None)
        return str(base_url).rstrip("/") if base_url else None

    def describe_provider_error(
        self,
        error: BaseException,
        *,
        provider: str = "ollama",
        timeout_env_var: str = "JARVIS_CODING_PLAN_TIMEOUT_SECONDS",
    ) -> str:
        """Format an actionable timeout/connection diagnostic via registered provider metadata."""
        error_name = type(error).__name__
        detail = str(error).strip() or error_name
        if "timeout" in error_name.lower():
            return (
                "O modelo local demorou demasiado a gerar o plano "
                f"({error_name}). Tente um objetivo mais restrito ou "
                f"aumente {timeout_env_var}."
            )
        if "connect" in error_name.lower():
            endpoint = self.get_provider_endpoint(provider)
            if endpoint:
                return (
                    f"Nao foi possivel contactar o fornecedor local ({provider}) em "
                    f"{endpoint}. Confirme que o servico esta a correr."
                )
            return (
                f"Nao foi possivel contactar o fornecedor local ({provider}). "
                "Confirme que o servico esta a correr."
            )
        return detail

    async def check_model_available(
        self,
        *,
        provider: str = "ollama",
        model: str = "qwen3.5:9b",
        match_family_prefix: str | None = None,
        timeout_seconds: float = 1.5,
    ) -> bool:
        """Probe model availability through the ModelHarness provider registry."""
        try:
            harness = self._resolve_harness()
            provider_impl = harness.providers.get(provider)
        except Exception:
            return False

        target = str(model or "").strip()
        prefix = str(match_family_prefix or "").strip().lower()
        try:
            if hasattr(provider_impl, "list_models"):
                models = await provider_impl.list_models(timeout_seconds=timeout_seconds)
                for item in models:
                    name = str(item.get("name") or item.get("model") or "").strip()
                    if not name:
                        continue
                    if (target and target in name) or (prefix and prefix in name.lower()):
                        return True
                return False
            if hasattr(provider_impl, "inspect_model"):
                await provider_impl.inspect_model(
                    target,
                    OllamaExecutionOptions(readiness_timeout=timeout_seconds),
                )
                return True
        except Exception:
            return False
        return False

    async def execute(
        self,
        *,
        provider: str,
        model: str,
        operation: str,
        system_prompt: str,
        user_prompt: str,
        conversation_messages: list[dict] | None = None,
        output_format: OutputFormat = OutputFormat.TEXT,
        temperature: float = 0.0,
        max_output_tokens: int = 512,
        timeout_seconds: float = 30.0,
        max_context_tokens: int | None = None,
        streaming: bool | None = None,
        cancellation_check: Callable[[], bool] | None = None,
    ) -> ModelResponse:
        profile = (
            "STRUCTURED_EXTRACTION"
            if output_format
            in {OutputFormat.JSON, OutputFormat.JSON_SCHEMA}
            else "CODE_REASONING"
        )
        effective_num_ctx = max_context_tokens
        if effective_num_ctx is None and provider == "ollama":
            try:
                effective_num_ctx = max(1024, int(os.getenv("OLLAMA_NUM_CTX", "8192")))
            except (TypeError, ValueError):
                effective_num_ctx = 8192
        effective_streaming = (
            bool(streaming)
            if streaming is not None
            else (provider == "ollama" and output_format != OutputFormat.TOOL_CALLS)
        )
        provider_payload = (
            OllamaExecutionOptions(cancellation_check=cancellation_check)
            if provider == "ollama" and cancellation_check is not None
            else None
        )
        request = ModelRequest(
            task_profile=profile,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            expected_output=ExpectedOutput(
                format=output_format
            ),
            temperature=temperature,
            max_context_tokens=effective_num_ctx,
            max_output_tokens=max_output_tokens,
            metadata={
                "consumer": "server",
                "operation": operation,
                "conversation_messages": list(
                    conversation_messages or ()
                ),
            },
            model_preferences=ModelPreferences(
                providers=(provider,),
                models=(model,),
                mode="chat",
            ),
            execution_constraints=ExecutionConstraints(
                max_attempts=1,
                timeout_seconds=timeout_seconds,
                streaming=effective_streaming,
                thinking=False,
                allow_recovery=False,
                stop_on_no_progress=False,
                provider_payload=provider_payload,
            ),
        )
        response = await self._resolve_harness().execute(request)
        if response.status == ModelResponseStatus.SUCCEEDED:
            return response
        if response.provider_exception is not None:
            raise response.provider_exception
        issues = "; ".join(
            issue.message
            for issue in response.validation.issues
        )
        raise RuntimeError(
            issues
            or (
                "ModelHarness terminou com estado "
                f"{response.status.value}."
            )
        )

    async def execute_local(
        self,
        *,
        operation: str,
        system_prompt: str,
        user_prompt: str,
        conversation_messages: list[dict] | None = None,
        output_format: OutputFormat = OutputFormat.TEXT,
        temperature: float = 0.0,
        max_output_tokens: int = 512,
        timeout_seconds: float = 30.0,
    ) -> ModelResponse:
        mode = os.getenv("ORCHESTRATOR_MODE", "local").strip().lower()
        if mode in ("gemini", "cloud") and os.getenv("GEMINI_API_KEY"):
            gemini_model = os.getenv("GEMINI_CREW_MODEL", "gemini-2.5-flash").replace("gemini/", "").strip()
            return await self.execute(
                provider="gemini",
                model=gemini_model,
                operation=operation,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                conversation_messages=conversation_messages,
                output_format=output_format,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                timeout_seconds=timeout_seconds,
            )

        try:
            return await self.execute(
                provider="ollama",
                model=os.getenv("OLLAMA_MODEL", "qwen3.5:9b"),
                operation=operation,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                conversation_messages=conversation_messages,
                output_format=output_format,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                timeout_seconds=timeout_seconds,
            )
        except Exception as e:
            fallback_enabled = os.getenv("ALLOW_EXTERNAL_FALLBACK", "false").strip().lower() in ("true", "1", "yes")
            if (fallback_enabled or mode in ("gemini", "cloud")) and os.getenv("GEMINI_API_KEY"):
                gemini_model = os.getenv("GEMINI_CREW_MODEL", "gemini-2.5-flash").replace("gemini/", "").strip()
                return await self.execute(
                    provider="gemini",
                    model=gemini_model,
                    operation=operation,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    conversation_messages=conversation_messages,
                    output_format=output_format,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    timeout_seconds=timeout_seconds,
                )
            raise RuntimeError(
                f"Erro no modelo local: {e}. O fallback para fornecedores externos está bloqueado por política de segurança e privacidade."
            ) from e
