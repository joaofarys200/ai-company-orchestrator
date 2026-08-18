from __future__ import annotations

import asyncio
import inspect
import os
import threading
from typing import Any, Mapping

try:
    from crewai.llms.base_llm import BaseLLM
except ImportError:
    class BaseLLM:
        pass

from backend.model_harness import (
    ExecutionConstraints,
    ExpectedOutput,
    ModelPreferences,
    ModelRequest,
    ModelResponseStatus,
    OutputFormat,
    get_model_harness,
)


class ModelHarnessCrewAILLM(BaseLLM):
    """Compatibility adapter that keeps CrewAI behind ModelHarness."""

    llm_type: str = "jarvis_model_harness"
    provider: str = "jarvis"

    def call(
        self,
        messages,
        tools=None,
        callbacks=None,
        available_functions=None,
        from_task=None,
        from_agent=None,
        response_model=None,
    ):
        del callbacks, from_task, from_agent, response_model
        return self._run_sync(self._execute(
            messages,
            tools or [],
            available_functions or {},
        ))

    async def acall(
        self,
        messages,
        tools=None,
        callbacks=None,
        available_functions=None,
        from_task=None,
        from_agent=None,
        response_model=None,
    ):
        del callbacks, from_task, from_agent, response_model
        return await self._execute(
            messages,
            tools or [],
            available_functions or {},
        )

    def supports_function_calling(self) -> bool:
        return True

    async def _execute(
        self,
        messages: str | list[Mapping[str, Any]],
        tools: list[Mapping[str, Any]],
        available_functions: Mapping[str, Any],
    ) -> Any:
        conversation = (
            [{"role": "user", "content": messages}]
            if isinstance(messages, str)
            else [dict(item) for item in messages]
        )
        system_prompt = next(
            (
                str(item.get("content") or "")
                for item in conversation
                if item.get("role") == "system"
            ),
            "Cumpre a tarefa atribuida de forma objetiva.",
        )
        non_system = [
            item
            for item in conversation
            if item.get("role") != "system"
        ]
        user_prompt = next(
            (
                str(item.get("content") or "")
                for item in reversed(non_system)
                if item.get("role") == "user"
            ),
            "Continua a tarefa.",
        )
        tool_schemas = [
            self._normalize_tool_schema(item)
            for item in tools
        ]
        tool_schemas = [item for item in tool_schemas if item]
        tool_names = tuple(
            item["function"]["name"]
            for item in tool_schemas
        )
        request = ModelRequest(
            task_profile=(
                "TOOL_SELECTION" if tool_names else "CODE_REASONING"
            ),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            allowed_tools=tool_names,
            expected_output=ExpectedOutput(
                format=(
                    OutputFormat.TOOL_CALLS
                    if tool_names
                    else OutputFormat.TEXT
                )
            ),
            temperature=(
                float(self.temperature)
                if self.temperature is not None
                else 0.2
            ),
            max_output_tokens=(
                int(self.max_tokens)
                if self.max_tokens is not None
                else 2_048
            ),
            metadata={
                "consumer": "CrewAI",
                "operation": "swarm_agent",
                "conversation_messages": non_system,
                "tool_schemas": tool_schemas,
            },
            model_preferences=ModelPreferences(
                providers=("ollama",),
                models=(self.model,),
                mode="chat",
            ),
            execution_constraints=ExecutionConstraints(
                max_attempts=1,
                timeout_seconds=120.0,
                streaming=False,
                thinking=False,
                allow_recovery=False,
                stop_on_no_progress=False,
            ),
        )
        response = await get_model_harness().execute(request)
        if response.status == ModelResponseStatus.PROVIDER_FAILED:
            if response.provider_exception is not None:
                raise response.provider_exception
            raise RuntimeError("ModelHarness provider failure.")
        if response.tool_calls and available_functions:
            call = response.tool_calls[0]
            function = available_functions.get(call.name)
            if function is not None:
                result = function(**dict(call.arguments))
                if inspect.isawaitable(result):
                    result = await result
                return result
        return response.raw_text

    @staticmethod
    def _normalize_tool_schema(
        raw: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        function = raw.get("function")
        if isinstance(function, Mapping):
            name = str(function.get("name") or "").strip()
            if not name:
                return None
            return {
                "type": "function",
                "function": {
                    "name": name,
                    "description": str(
                        function.get("description") or ""
                    ),
                    "parameters": dict(
                        function.get("parameters") or {
                            "type": "object",
                            "properties": {},
                        }
                    ),
                },
            }
        name = str(raw.get("name") or "").strip()
        if not name:
            return None
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": str(raw.get("description") or ""),
                "parameters": dict(
                    raw.get("parameters")
                    or raw.get("input_schema")
                    or {"type": "object", "properties": {}}
                ),
            },
        }

    @staticmethod
    def _run_sync(coroutine):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coroutine)

        result: list[Any] = []
        errors: list[BaseException] = []

        def runner() -> None:
            try:
                result.append(asyncio.run(coroutine))
            except BaseException as exc:
                errors.append(exc)

        thread = threading.Thread(target=runner)
        thread.start()
        thread.join()
        if errors:
            raise errors[0]
        return result[0]


class OllamaProvider:
    name = "ollama"

    def has_credentials(self) -> bool:
        return True

    def crewai_model(self) -> str:
        return os.getenv("OLLAMA_MODEL", "qwen3.5:9b")

    def build_crewai_llm(
        self,
        _llm_cls,
        temperature: float,
    ) -> ModelHarnessCrewAILLM:
        return ModelHarnessCrewAILLM(
            model=self.crewai_model(),
            temperature=temperature,
        )
