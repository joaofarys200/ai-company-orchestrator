from __future__ import annotations

import os
from typing import Any

from backend.model_harness import (
    ExecutionConstraints,
    ExpectedOutput,
    ModelPreferences,
    ModelRequest,
    ModelResponse,
    ModelResponseStatus,
    OutputFormat,
)


class ModelExecutionService:
    """Productive model boundary backed by the shared ModelHarness."""

    def __init__(self, harness: Any) -> None:
        self.harness = harness

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
    ) -> ModelResponse:
        profile = (
            "STRUCTURED_EXTRACTION"
            if output_format
            in {OutputFormat.JSON, OutputFormat.JSON_SCHEMA}
            else "CODE_REASONING"
        )
        request = ModelRequest(
            task_profile=profile,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            expected_output=ExpectedOutput(
                format=output_format
            ),
            temperature=temperature,
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
                streaming=False,
                thinking=False,
                allow_recovery=False,
                stop_on_no_progress=False,
            ),
        )
        response = await self.harness.execute(request)
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
