from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import httpx

from backend.model_harness.contracts import (
    ModelRequest,
    ModelRoute,
    ModelUsage,
    OutputFormat,
    ProviderResult,
    ToolCall,
)


ProviderEventCallback = Callable[
    [str, Mapping[str, Any], str],
    None,
]


@dataclass(frozen=True)
class OllamaExecutionOptions:
    """Provider-specific transport controls carried by ModelRequest."""

    connect_timeout: float | None = None
    read_timeout: float | None = None
    write_timeout: float | None = None
    pool_timeout: float | None = None
    readiness_timeout: float | None = None
    keep_alive: str | None = None
    require_readiness: bool = False
    require_done: bool = False
    output_character_limit: int | None = None
    event_callback: ProviderEventCallback | None = None

    def emit(
        self,
        event: str,
        metadata: Mapping[str, Any] | None = None,
        status: str = "OBSERVED",
    ) -> None:
        if self.event_callback is not None:
            self.event_callback(event, dict(metadata or {}), status)


class OllamaProviderResponseError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        partial_response: bool = False,
    ):
        super().__init__(message)
        self.partial_response = partial_response


class OllamaModelNotFoundError(OllamaProviderResponseError):
    pass


class OllamaIncompleteResponseError(OllamaProviderResponseError):
    pass


class OllamaOutputLimitError(OllamaProviderResponseError):
    pass


class OllamaStructuredOutputUnsupportedError(
    OllamaProviderResponseError
):
    pass


class OllamaChatProvider:
    """The only production HTTP transport for local Ollama inference."""

    name = "ollama"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        default_model: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        keep_alive: str | None = None,
    ):
        self.base_url = (
            base_url
            or os.getenv("OLLAMA_BASE_URL")
            or "http://127.0.0.1:11434"
        ).rstrip("/")
        self.default_model = (
            default_model
            or os.getenv("OLLAMA_MODEL")
            or "qwen3.5:9b"
        ).strip()
        self.transport = transport
        self.keep_alive = (
            keep_alive
            or os.getenv("OLLAMA_KEEP_ALIVE")
            or "30m"
        )

    async def warmup(self, model: str | None = None) -> bool:
        """Sends a lightweight warmup probe to preload model weights into memory/VRAM."""
        target_model = (model or self.default_model).strip()
        try:
            timeout = httpx.Timeout(connect=5.0, read=30.0, write=5.0, pool=5.0)
            async with self._client(timeout) as client:
                resp = await client.post(
                    "/api/generate",
                    json={
                        "model": target_model,
                        "prompt": "ping",
                        "keep_alive": self.keep_alive,
                        "options": {"num_predict": 1},
                    },
                )
                return resp.status_code < 400
        except Exception:
            return False

    async def generate(
        self,
        request: ModelRequest,
        route: ModelRoute,
        _progress,
    ) -> ProviderResult:
        options = self._execution_options(request)
        readiness: dict[str, Any] = {}
        if options.require_readiness:
            readiness = await self.inspect_model(route.model, options)

        payload = self._payload(request, route, options)
        timeout = self._timeout(request, options)
        async with self._client(timeout) as client:
            if route.streaming:
                result = await self._generate_streaming(
                    client,
                    payload,
                    options,
                )
            else:
                result = await self._generate_buffered(
                    client,
                    payload,
                    options,
                )
        if readiness:
            return ProviderResult(
                raw_text=result.raw_text,
                usage=result.usage,
                tool_calls=result.tool_calls,
                warnings=result.warnings,
                metadata={**dict(result.metadata), "readiness": readiness},
            )
        return result

    async def inspect_model(
        self,
        model: str,
        options: OllamaExecutionOptions | None = None,
    ) -> dict[str, Any]:
        options = options or OllamaExecutionOptions()
        started = time.perf_counter()
        result: dict[str, Any] = {
            "service_available": False,
            "model_exists": False,
            "model_loaded": None,
        }
        options.emit(
            "readiness_check_started",
            {"model": model},
        )
        timeout_seconds = options.readiness_timeout or min(
            options.read_timeout or 120.0,
            15.0,
        )
        timeout = httpx.Timeout(
            connect=options.connect_timeout or min(15.0, timeout_seconds),
            read=timeout_seconds,
            write=options.write_timeout or min(30.0, timeout_seconds),
            pool=options.pool_timeout or min(15.0, timeout_seconds),
        )
        status = "FAILED"
        try:
            async with self._client(timeout) as client:
                response = await client.get("/api/tags")
                response.raise_for_status()
                result["service_available"] = True
                models = (response.json() or {}).get("models") or []
                selected = next(
                    (
                        item
                        for item in models
                        if str(
                            item.get("name")
                            or item.get("model")
                            or ""
                        )
                        == model
                    ),
                    None,
                )
                if selected is None:
                    raise OllamaModelNotFoundError(
                        f"O modelo configurado '{model}' nao existe."
                    )
                result["model_exists"] = True
                details = selected.get("details") or {}
                result["model_metadata"] = {
                    "family": details.get("family"),
                    "parameter_size": details.get("parameter_size"),
                    "quantization_level": details.get(
                        "quantization_level"
                    ),
                    "size_bytes": selected.get("size"),
                }
                try:
                    running = await client.get("/api/ps")
                    running.raise_for_status()
                    loaded = (running.json() or {}).get("models") or []
                    result["model_loaded"] = any(
                        str(
                            item.get("name")
                            or item.get("model")
                            or ""
                        )
                        == model
                        for item in loaded
                    )
                except httpx.HTTPError:
                    result["model_loaded"] = None
            status = "COMPLETED"
            return result
        finally:
            result["duration"] = round(
                time.perf_counter() - started,
                4,
            )
            options.emit(
                "readiness_check_completed",
                result,
                status,
            )

    def _client(self, timeout: httpx.Timeout) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            transport=self.transport,
        )

    def _timeout(
        self,
        request: ModelRequest,
        options: OllamaExecutionOptions,
    ) -> httpx.Timeout:
        total = (
            options.read_timeout
            or request.execution_constraints.timeout_seconds
            or 120.0
        )
        return httpx.Timeout(
            connect=options.connect_timeout or min(15.0, total),
            read=total,
            write=options.write_timeout or min(30.0, total),
            pool=options.pool_timeout or min(15.0, total),
        )

    async def _generate_buffered(
        self,
        client: httpx.AsyncClient,
        payload: Mapping[str, Any],
        options: OllamaExecutionOptions,
    ) -> ProviderResult:
        options.emit("http_request_started", {"stream": False})
        response = await client.post("/api/chat", json=dict(payload))
        options.emit(
            "response_headers_received",
            {"status_code": response.status_code},
            "COMPLETED" if response.status_code < 400 else "FAILED",
        )
        self._raise_for_status(response, payload)
        envelope = response.json()
        return self._provider_result(envelope)

    async def _generate_streaming(
        self,
        client: httpx.AsyncClient,
        payload: Mapping[str, Any],
        options: OllamaExecutionOptions,
    ) -> ProviderResult:
        started = time.perf_counter()
        parts: list[str] = []
        calls: list[Mapping[str, Any]] = []
        metrics: dict[str, Any] = {}
        first_chunk_at: float | None = None
        first_content_at: float | None = None
        first_valid_json_at: float | None = None
        last_chunk_at: float | None = None
        max_chunk_gap = 0.0
        chunk_count = 0
        response_bytes = 0
        done = False
        done_reason = ""

        options.emit("http_request_started", {"stream": True})
        async with client.stream(
            "POST",
            "/api/chat",
            json=dict(payload),
        ) as response:
            options.emit(
                "response_headers_received",
                {"status_code": response.status_code},
                "COMPLETED" if response.status_code < 400 else "FAILED",
            )
            if response.status_code >= 400:
                await response.aread()
                self._raise_for_status(response, payload)
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                now = time.perf_counter()
                chunk_count += 1
                response_bytes += len(line.encode("utf-8"))
                if first_chunk_at is None:
                    first_chunk_at = now
                    options.emit("first_response_byte")
                    options.emit("first_http_chunk")
                if last_chunk_at is not None:
                    max_chunk_gap = max(
                        max_chunk_gap,
                        now - last_chunk_at,
                    )
                last_chunk_at = now
                try:
                    chunk = json.loads(line)
                except ValueError as exc:
                    raise OllamaProviderResponseError(
                        "Ollama devolveu um chunk de streaming invalido.",
                        partial_response=bool(parts),
                    ) from exc
                if chunk.get("error"):
                    raise OllamaProviderResponseError(
                        "Ollama devolveu erro durante a geracao.",
                        partial_response=bool(parts),
                    )
                message = chunk.get("message") or {}
                content = str(message.get("content") or "")
                if content:
                    if first_content_at is None:
                        first_content_at = now
                        options.emit("first_nonempty_content")
                    parts.append(content)
                    if first_valid_json_at is None:
                        try:
                            json.loads("".join(parts))
                        except (TypeError, ValueError):
                            pass
                        else:
                            first_valid_json_at = now
                            options.emit("first_valid_json_object")
                raw_calls = message.get("tool_calls")
                if isinstance(raw_calls, list):
                    calls.extend(
                        item
                        for item in raw_calls
                        if isinstance(item, Mapping)
                    )
                output_length = sum(len(part) for part in parts)
                options.emit(
                    "stream_progress",
                    {
                        "chunks": chunk_count,
                        "content_chars": output_length,
                    },
                )
                if (
                    options.output_character_limit is not None
                    and output_length > options.output_character_limit
                ):
                    raise OllamaOutputLimitError(
                        "A resposta excedeu o limite configurado.",
                        partial_response=True,
                    )
                if chunk.get("done") is True:
                    done = True
                    done_reason = str(chunk.get("done_reason") or "")
                    metrics = {
                        key: chunk.get(key)
                        for key in (
                            "prompt_eval_count",
                            "prompt_eval_duration",
                            "eval_count",
                            "eval_duration",
                            "load_duration",
                            "total_duration",
                        )
                        if key in chunk
                    }
                    break

        if options.require_done and not done:
            raise OllamaIncompleteResponseError(
                "O streaming terminou sem done=true.",
                partial_response=bool(parts),
            )
        if done_reason.casefold() == "length":
            raise OllamaOutputLimitError(
                "O modelo terminou por atingir o limite de output.",
                partial_response=bool(parts),
            )
        stream_metrics = {
            "first_response_byte_ms": (
                round((first_chunk_at - started) * 1000, 3)
                if first_chunk_at is not None
                else None
            ),
            "first_chunk_ms": (
                round((first_chunk_at - started) * 1000, 3)
                if first_chunk_at is not None
                else None
            ),
            "first_content_ms": (
                round((first_content_at - started) * 1000, 3)
                if first_content_at is not None
                else None
            ),
            "first_valid_json_ms": (
                round((first_valid_json_at - started) * 1000, 3)
                if first_valid_json_at is not None
                else None
            ),
            "max_chunk_gap_ms": round(max_chunk_gap * 1000, 3),
            "chunk_count": chunk_count,
            "bytes_received": response_bytes,
            "content_characters": sum(len(part) for part in parts),
            "done": done,
            "done_reason": done_reason,
            **metrics,
        }
        options.emit("stream_completed", stream_metrics, "COMPLETED")
        envelope = {
            "message": {
                "content": "".join(parts),
                "tool_calls": calls,
            },
            **stream_metrics,
        }
        return self._provider_result(envelope)

    @staticmethod
    def _raise_for_status(
        response: httpx.Response,
        payload: Mapping[str, Any],
    ) -> None:
        if response.status_code < 400:
            return
        body = response.text
        has_schema = isinstance(payload.get("format"), Mapping)
        lowered = body.casefold()
        if has_schema and (
            "schema" in lowered
            and (
                "not supported" in lowered
                or "unsupported" in lowered
                or "invalid format" in lowered
            )
        ):
            raise OllamaStructuredOutputUnsupportedError(
                "O provider rejeitou structured output com JSON Schema."
            )
        response.raise_for_status()

    def _provider_result(
        self,
        envelope: Mapping[str, Any],
    ) -> ProviderResult:
        message = envelope.get("message") or {}
        raw_text = str(message.get("content") or "")
        input_tokens = self._optional_int(
            envelope.get("prompt_eval_count")
        )
        output_tokens = self._optional_int(envelope.get("eval_count"))
        total_tokens = (
            input_tokens + output_tokens
            if input_tokens is not None and output_tokens is not None
            else None
        )
        warnings: list[str] = []
        if envelope.get("done") is False:
            warnings.append("ollama_response_not_done")
        return ProviderResult(
            raw_text=raw_text,
            usage=ModelUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            ),
            tool_calls=self._tool_calls(message.get("tool_calls")),
            warnings=tuple(warnings),
            metadata={
                "done": envelope.get("done"),
                "done_reason": envelope.get("done_reason"),
                "total_duration": envelope.get("total_duration"),
                "load_duration": envelope.get("load_duration"),
                "prompt_eval_duration": envelope.get(
                    "prompt_eval_duration"
                ),
                "eval_duration": envelope.get("eval_duration"),
                "chunk_count": envelope.get("chunk_count"),
                "bytes_received": envelope.get("bytes_received"),
                "first_response_byte_ms": envelope.get(
                    "first_response_byte_ms"
                ),
                "first_chunk_ms": envelope.get("first_chunk_ms"),
                "first_content_ms": envelope.get("first_content_ms"),
                "first_valid_json_ms": envelope.get(
                    "first_valid_json_ms"
                ),
                "max_chunk_gap_ms": envelope.get("max_chunk_gap_ms"),
            },
        )

    def _payload(
        self,
        request: ModelRequest,
        route: ModelRoute,
        options: OllamaExecutionOptions | None = None,
    ) -> dict[str, Any]:
        user_prompt = self._user_prompt_with_context(request)
        messages = self._conversation_messages(request, user_prompt)
        payload: dict[str, Any] = {
            "model": route.model,
            "messages": messages,
            "stream": route.streaming,
            "think": route.thinking,
            "keep_alive": (
                options.keep_alive
                if options is not None and options.keep_alive
                else self.keep_alive
            ),
            "options": {
                "temperature": request.temperature,
                "num_ctx": request.max_context_tokens,
                "num_predict": request.max_output_tokens,
                "num_batch": int(os.getenv("OLLAMA_NUM_BATCH", "512")),
            },
        }
        thread_cfg = os.getenv("OLLAMA_NUM_THREAD")
        if thread_cfg and thread_cfg.isdigit():
            payload["options"]["num_thread"] = int(thread_cfg)
        else:
            payload["options"]["num_thread"] = min(8, max(2, (os.cpu_count() or 4) - 1))

        top_p = request.metadata.get("top_p")
        if isinstance(top_p, (int, float)) and not isinstance(top_p, bool):
            payload["options"]["top_p"] = float(top_p)
        seed = request.metadata.get("seed")
        if isinstance(seed, int) and not isinstance(seed, bool):
            payload["options"]["seed"] = seed

        expected = request.expected_output
        if expected is not None:
            if (
                expected.format == OutputFormat.JSON_SCHEMA
                and expected.schema is not None
            ):
                payload["format"] = dict(expected.schema)
            elif expected.format == OutputFormat.JSON:
                payload["format"] = "json"

        tool_schemas = request.metadata.get("tool_schemas")
        if request.allowed_tools and isinstance(tool_schemas, (list, tuple)):
            allowed = set(request.allowed_tools)
            selected = [
                dict(item)
                for item in tool_schemas
                if isinstance(item, Mapping)
                and self._tool_schema_name(item) in allowed
            ]
            if selected:
                payload["tools"] = selected
        return payload

    def _user_prompt_with_context(self, request: ModelRequest) -> str:
        user_prompt = request.user_prompt
        if not request.context.items:
            return user_prompt
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
            user_prompt
            + "\n\nAUTHORITATIVE_CONTEXT:\n"
            + json.dumps(
                context_payload,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )

    def _conversation_messages(
        self,
        request: ModelRequest,
        user_prompt: str,
    ) -> list[dict[str, Any]]:
        raw_messages = request.metadata.get("conversation_messages")
        if not isinstance(raw_messages, (list, tuple)):
            return [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": user_prompt},
            ]

        normalized: list[dict[str, Any]] = []
        if request.system_prompt:
            normalized.append({
                "role": "system",
                "content": request.system_prompt,
            })
        for raw in raw_messages:
            if not isinstance(raw, Mapping):
                continue
            message = self._normalize_conversation_message(raw)
            if message is not None:
                normalized.append(message)
        if request.context.items:
            for message in reversed(normalized):
                if message.get("role") == "user":
                    message["content"] = user_prompt
                    break
            else:
                normalized.append({
                    "role": "user",
                    "content": user_prompt,
                })
        if not normalized or all(
            item.get("role") == "system" for item in normalized
        ):
            normalized.append({"role": "user", "content": user_prompt})
        return normalized

    @staticmethod
    def _normalize_conversation_message(
        raw: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        role = str(raw.get("role") or "").strip().lower()
        if role == "tool_result":
            role = "tool"
        if role not in {"system", "user", "assistant", "tool"}:
            return None
        content = raw.get("content", "")
        message: dict[str, Any] = {
            "role": role,
            "content": (
                OllamaChatProvider._text_content(content)
                if isinstance(content, list)
                else str(content)
            ),
        }
        if role == "assistant":
            raw_calls = raw.get("tool_calls")
            if not isinstance(raw_calls, list) and isinstance(content, list):
                raw_calls = [
                    {
                        "type": "function",
                        "function": {
                            "name": item.get("name"),
                            "arguments": item.get("input") or {},
                        },
                    }
                    for item in content
                    if isinstance(item, Mapping)
                    and item.get("type") == "tool_use"
                ]
            if isinstance(raw_calls, list) and raw_calls:
                message["tool_calls"] = raw_calls
        if role == "tool":
            tool_name = raw.get("name") or raw.get("tool_name")
            if tool_name:
                message["name"] = str(tool_name)
            call_id = raw.get("tool_call_id") or raw.get("tool_use_id")
            if call_id:
                message["tool_call_id"] = str(call_id)
        return message

    @staticmethod
    def _text_content(content: list[Any]) -> str:
        return "".join(
            str(item.get("text") or "")
            for item in content
            if isinstance(item, Mapping)
            and item.get("type") == "text"
        )

    @staticmethod
    def _execution_options(
        request: ModelRequest,
    ) -> OllamaExecutionOptions:
        value = request.execution_constraints.provider_payload
        return (
            value
            if isinstance(value, OllamaExecutionOptions)
            else OllamaExecutionOptions()
        )

    @staticmethod
    def _tool_schema_name(schema: Mapping[str, Any]) -> str:
        function = schema.get("function")
        if isinstance(function, Mapping):
            return str(function.get("name") or "")
        return str(schema.get("name") or "")

    @staticmethod
    def _tool_calls(raw_calls: Any) -> tuple[ToolCall, ...]:
        calls: list[ToolCall] = []
        for index, item in enumerate(
            raw_calls if isinstance(raw_calls, list) else ()
        ):
            if not isinstance(item, Mapping):
                continue
            function = item.get("function")
            if not isinstance(function, Mapping):
                continue
            name = str(function.get("name") or "").strip()
            arguments = function.get("arguments")
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except (TypeError, ValueError):
                    arguments = {}
            if not name or not isinstance(arguments, Mapping):
                continue
            calls.append(ToolCall(
                name=name,
                arguments=dict(arguments),
                call_id=str(item.get("id") or f"ollama-{index}"),
            ))
        return tuple(calls)

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
