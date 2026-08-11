from __future__ import annotations

import json
import os
from typing import Any, Mapping

import httpx

from backend.model_harness.contracts import (
    ModelRequest,
    ModelRoute,
    ModelUsage,
    OutputFormat,
    ProviderResult,
    ToolCall,
)


class OpenRouterProviderError(RuntimeError):
    pass


class OpenRouterProvider:
    """OpenRouter transport for cloud LLM inference under the shared ModelHarness boundary."""

    name = "openrouter"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.api_key = api_key
        self.base_url = (
            base_url
            or os.getenv("OPENROUTER_BASE_URL")
            or "https://openrouter.ai/api/v1"
        ).rstrip("/")
        self.default_model = (
            default_model
            or os.getenv("OPENROUTER_MODEL")
            or "openrouter/free"
        ).strip()
        self.transport = transport

    async def generate(
        self,
        request: ModelRequest,
        route: ModelRoute,
        _progress,
    ) -> ProviderResult:
        api_key = self.api_key or os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise OpenRouterProviderError("OPENROUTER_API_KEY nao esta configurada.")
        payload = self._payload(request, route)
        timeout = request.execution_constraints.timeout_seconds or 60.0
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
            transport=self.transport,
        ) as client:
            response = await client.post(
                "/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/joaofarys200/ai-company-orchestrator",
                    "X-Title": "JARVIS OS",
                },
            )
        if response.status_code >= 400:
            raise OpenRouterProviderError(
                f"OpenRouter devolveu HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )
        return self._provider_result(response.json())

    def _payload(
        self,
        request: ModelRequest,
        route: ModelRoute,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": route.model or self.default_model,
            "messages": self._messages(request),
            "temperature": request.temperature,
        }
        if request.max_output_tokens:
            payload["max_tokens"] = request.max_output_tokens
        top_p = request.metadata.get("top_p")
        if isinstance(top_p, (int, float)) and not isinstance(top_p, bool):
            payload["top_p"] = float(top_p)
        tools = self._tools(request)
        if tools:
            payload["tools"] = tools
        expected = request.expected_output
        if expected is not None:
            if expected.format == OutputFormat.JSON:
                payload["response_format"] = {"type": "json_object"}
            elif (
                expected.format == OutputFormat.JSON_SCHEMA
                and expected.schema is not None
            ):
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "model_response",
                        "strict": True,
                        "schema": dict(expected.schema),
                    },
                }
        return payload

    def _messages(self, request: ModelRequest) -> list[dict[str, Any]]:
        raw_messages = request.metadata.get("conversation_messages")
        messages: list[dict[str, Any]] = []
        if request.system_prompt:
            messages.append({
                "role": "system",
                "content": request.system_prompt,
            })
        if isinstance(raw_messages, (list, tuple)):
            for raw in raw_messages:
                if not isinstance(raw, Mapping):
                    continue
                role = str(raw.get("role") or "").strip().lower()
                if role == "tool_result":
                    role = "tool"
                if role not in {"user", "assistant", "tool"}:
                    continue
                message: dict[str, Any] = {
                    "role": role,
                    "content": self._text(raw.get("content", "")),
                }
                raw_calls = raw.get("tool_calls")
                if role == "assistant" and isinstance(raw_calls, list):
                    message["tool_calls"] = raw_calls
                if role == "tool":
                    call_id = (
                        raw.get("tool_call_id")
                        or raw.get("tool_use_id")
                    )
                    if call_id:
                        message["tool_call_id"] = str(call_id)
                    name = raw.get("name") or raw.get("tool_name")
                    if name:
                        message["name"] = str(name)
                messages.append(message)
        if len(messages) == (1 if request.system_prompt else 0):
            messages.append({
                "role": "user",
                "content": self._user_prompt_with_context(request),
            })
        return messages

    def _tools(self, request: ModelRequest) -> list[dict[str, Any]]:
        raw_tools = request.metadata.get("tool_schemas")
        if not isinstance(raw_tools, (list, tuple)):
            return []
        allowed = set(request.allowed_tools)
        tools: list[dict[str, Any]] = []
        for raw in raw_tools:
            if not isinstance(raw, Mapping):
                continue
            if raw.get("type") == "function":
                function = raw.get("function")
                if not isinstance(function, Mapping):
                    continue
                name = str(function.get("name") or "")
                normalized = {
                    "type": "function",
                    "function": dict(function),
                }
            else:
                name = str(raw.get("name") or "")
                normalized = {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": str(raw.get("description") or ""),
                        "parameters": dict(
                            raw.get("input_schema") or {}
                        ),
                    },
                }
            if name and (not allowed or name in allowed or "*" in allowed):
                tools.append(normalized)
        return tools

    @staticmethod
    def _provider_result(envelope: Mapping[str, Any]) -> ProviderResult:
        choices = envelope.get("choices") or []
        message = (
            choices[0].get("message") or {}
            if choices and isinstance(choices[0], Mapping)
            else {}
        )
        usage = envelope.get("usage") or {}
        calls: list[ToolCall] = []
        for raw in message.get("tool_calls") or []:
            if not isinstance(raw, Mapping):
                continue
            function = raw.get("function") or {}
            if not isinstance(function, Mapping):
                continue
            arguments = function.get("arguments") or {}
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except ValueError:
                    arguments = {}
            if not isinstance(arguments, Mapping):
                arguments = {}
            name = str(function.get("name") or "")
            if name:
                calls.append(ToolCall(
                    name=name,
                    arguments=dict(arguments),
                    call_id=str(raw.get("id") or ""),
                ))
        input_tokens = OpenRouterProvider._optional_int(
            usage.get("prompt_tokens")
        )
        output_tokens = OpenRouterProvider._optional_int(
            usage.get("completion_tokens")
        )
        total_tokens = OpenRouterProvider._optional_int(
            usage.get("total_tokens")
        )
        return ProviderResult(
            raw_text=str(message.get("content") or ""),
            usage=ModelUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            ),
            tool_calls=tuple(calls),
            metadata={
                "finish_reason": (
                    choices[0].get("finish_reason")
                    if choices and isinstance(choices[0], Mapping)
                    else None
                ),
            },
        )

    @staticmethod
    def _user_prompt_with_context(request: ModelRequest) -> str:
        if not request.context.items:
            return request.user_prompt
        context_payload = [
            {
                "source": item.source,
                "kind": item.kind,
                "content": item.content,
                "inclusion_reason": item.inclusion_reason,
            }
            for item in request.context.items
        ]
        return (
            request.user_prompt
            + "\n\nAUTHORITATIVE_CONTEXT:\n"
            + json.dumps(
                context_payload,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )

    @staticmethod
    def _text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, (list, tuple)):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, Mapping) and item.get("type") == "text":
                    parts.append(str(item.get("text") or ""))
            return "".join(parts)
        return str(content or "")

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None
