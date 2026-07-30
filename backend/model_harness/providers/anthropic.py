from __future__ import annotations

import json
import os
from typing import Any, Mapping

import httpx

from backend.model_harness.contracts import (
    ModelRequest,
    ModelRoute,
    ModelUsage,
    ProviderResult,
    ToolCall,
)


class AnthropicProviderError(RuntimeError):
    pass


class AnthropicMessagesProvider:
    """Anthropic Messages API behind the shared ModelHarness boundary."""

    name = "anthropic"

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
            or os.getenv("ANTHROPIC_BASE_URL")
            or "https://api.anthropic.com"
        ).rstrip("/")
        self.default_model = (
            default_model
            or os.getenv("ANTHROPIC_MODEL")
            or "claude-3-5-sonnet-latest"
        ).strip()
        self.transport = transport

    async def generate(
        self,
        request: ModelRequest,
        route: ModelRoute,
        _progress,
    ) -> ProviderResult:
        api_key = self.api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise AnthropicProviderError(
                "ANTHROPIC_API_KEY nao esta configurada."
            )
        timeout = request.execution_constraints.timeout_seconds or 60.0
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
            transport=self.transport,
        ) as client:
            response = await client.post(
                "/v1/messages",
                json=self._payload(request, route),
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
            )
        if response.status_code >= 400:
            raise AnthropicProviderError(
                f"Anthropic devolveu HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )
        return self._provider_result(response.json())

    def _payload(
        self,
        request: ModelRequest,
        route: ModelRoute,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": route.model,
            "max_tokens": request.max_output_tokens or 1_024,
            "system": request.system_prompt,
            "messages": self._messages(request),
            "temperature": request.temperature,
        }
        top_p = request.metadata.get("top_p")
        if isinstance(top_p, (int, float)) and not isinstance(top_p, bool):
            payload["top_p"] = float(top_p)
        tools = self._tools(request)
        if tools:
            payload["tools"] = tools
        return payload

    def _messages(self, request: ModelRequest) -> list[dict[str, Any]]:
        raw_messages = request.metadata.get("conversation_messages")
        messages: list[dict[str, Any]] = []
        if isinstance(raw_messages, (list, tuple)):
            for raw in raw_messages:
                if not isinstance(raw, Mapping):
                    continue
                role = str(raw.get("role") or "").strip().lower()
                content = raw.get("content", "")
                if role == "system":
                    continue
                if role in {"tool", "tool_result"}:
                    call_id = (
                        raw.get("tool_call_id")
                        or raw.get("tool_use_id")
                        or ""
                    )
                    messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": str(call_id),
                            "content": self._tool_result_content(content),
                        }],
                    })
                    continue
                if role not in {"user", "assistant"}:
                    continue
                if role == "assistant":
                    blocks = self._assistant_blocks(raw)
                    messages.append({
                        "role": "assistant",
                        "content": blocks or self._text(content),
                    })
                else:
                    messages.append({
                        "role": "user",
                        "content": self._text(content),
                    })
        if not messages:
            messages.append({
                "role": "user",
                "content": self._user_prompt_with_context(request),
            })
        return messages

    def _assistant_blocks(
        self,
        raw: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        content = raw.get("content", "")
        blocks: list[dict[str, Any]] = []
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, Mapping):
                    continue
                if item.get("type") == "text":
                    blocks.append({
                        "type": "text",
                        "text": str(item.get("text") or ""),
                    })
                elif item.get("type") == "tool_use":
                    blocks.append({
                        "type": "tool_use",
                        "id": str(item.get("id") or ""),
                        "name": str(item.get("name") or ""),
                        "input": dict(item.get("input") or {}),
                    })
        elif content:
            blocks.append({"type": "text", "text": str(content)})
        for raw_call in raw.get("tool_calls") or []:
            if not isinstance(raw_call, Mapping):
                continue
            function = raw_call.get("function") or {}
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
                blocks.append({
                    "type": "tool_use",
                    "id": str(raw_call.get("id") or ""),
                    "name": name,
                    "input": dict(arguments),
                })
        return blocks

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
                function = raw.get("function") or {}
                if not isinstance(function, Mapping):
                    continue
                name = str(function.get("name") or "")
                description = str(function.get("description") or "")
                schema = function.get("parameters") or {}
            else:
                name = str(raw.get("name") or "")
                description = str(raw.get("description") or "")
                schema = raw.get("input_schema") or {}
            if name and name in allowed:
                tools.append({
                    "name": name,
                    "description": description,
                    "input_schema": dict(schema),
                })
        return tools

    @staticmethod
    def _provider_result(envelope: Mapping[str, Any]) -> ProviderResult:
        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for block in envelope.get("content") or []:
            if not isinstance(block, Mapping):
                continue
            if block.get("type") == "text":
                text_parts.append(str(block.get("text") or ""))
            elif block.get("type") == "tool_use":
                name = str(block.get("name") or "")
                arguments = block.get("input") or {}
                if name and isinstance(arguments, Mapping):
                    calls.append(ToolCall(
                        name=name,
                        arguments=dict(arguments),
                        call_id=str(block.get("id") or ""),
                    ))
        usage = envelope.get("usage") or {}
        input_tokens = AnthropicMessagesProvider._optional_int(
            usage.get("input_tokens")
        )
        output_tokens = AnthropicMessagesProvider._optional_int(
            usage.get("output_tokens")
        )
        total_tokens = (
            input_tokens + output_tokens
            if input_tokens is not None and output_tokens is not None
            else None
        )
        return ProviderResult(
            raw_text="".join(text_parts),
            usage=ModelUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            ),
            tool_calls=tuple(calls),
            metadata={
                "stop_reason": envelope.get("stop_reason"),
                "stop_sequence": envelope.get("stop_sequence"),
            },
        )

    @staticmethod
    def _tool_result_content(content: Any) -> Any:
        if not isinstance(content, list):
            return str(content)
        result: list[dict[str, Any]] = []
        for item in content:
            if not isinstance(item, Mapping):
                continue
            if item.get("type") == "text":
                result.append({
                    "type": "text",
                    "text": str(item.get("text") or ""),
                })
            elif item.get("type") == "image":
                source = item.get("source") or {}
                if isinstance(source, Mapping):
                    result.append({
                        "type": "image",
                        "source": dict(source),
                    })
        return result or ""

    @staticmethod
    def _user_prompt_with_context(request: ModelRequest) -> str:
        if not request.context.items:
            return request.user_prompt
        context = [
            {
                "source": item.source,
                "kind": item.kind,
                "content": item.content,
            }
            for item in request.context.items
        ]
        return (
            request.user_prompt
            + "\n\nAUTHORITATIVE_CONTEXT:\n"
            + json.dumps(context, ensure_ascii=False, separators=(",", ":"))
        )

    @staticmethod
    def _text(value: Any) -> str:
        if not isinstance(value, list):
            return str(value)
        return "".join(
            str(item.get("text") or "")
            for item in value
            if isinstance(item, Mapping)
            and item.get("type") == "text"
        )

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
