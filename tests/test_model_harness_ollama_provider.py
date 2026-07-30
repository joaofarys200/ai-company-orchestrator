import json
import unittest

import httpx

from backend.model_harness import (
    ExecutionConstraints,
    ExpectedOutput,
    ModelRequest,
    ModelRoute,
    OllamaChatProvider,
    OutputFormat,
    TaskContext,
    ContextItem,
)


class OllamaChatProviderTest(unittest.IsolatedAsyncioTestCase):
    async def test_translates_provider_neutral_request_and_usage(self):
        captured = {}

        async def handler(request):
            captured["path"] = request.url.path
            captured["payload"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "message": {
                        "content": '{"status":"ok"}',
                        "tool_calls": [{
                            "id": "call-1",
                            "function": {
                                "name": "read_file",
                                "arguments": {"path": "app.js"},
                            },
                        }],
                    },
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 20,
                    "eval_count": 5,
                },
            )

        provider = OllamaChatProvider(
            base_url="http://ollama.invalid",
            default_model="local-model",
            transport=httpx.MockTransport(handler),
        )
        request = ModelRequest(
            task_profile="STRUCTURED_EXTRACTION",
            system_prompt="system",
            user_prompt="user",
            context=TaskContext(items=(ContextItem(
                source="file:app.js",
                kind="source",
                content="const value = 1;",
                inclusion_reason="selected",
            ),)),
            allowed_tools=("read_file",),
            expected_output=ExpectedOutput(
                format=OutputFormat.JSON_SCHEMA,
                schema={
                    "type": "object",
                    "required": ["status"],
                    "properties": {"status": {"type": "string"}},
                },
            ),
            temperature=0.0,
            max_context_tokens=8_192,
            max_output_tokens=1_024,
            metadata={
                "top_p": 0.8,
                "tool_schemas": [{
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "parameters": {"type": "object"},
                    },
                }, {
                    "type": "function",
                    "function": {
                        "name": "write_file",
                        "parameters": {"type": "object"},
                    },
                }],
            },
            execution_constraints=ExecutionConstraints(
                timeout_seconds=5,
                streaming=False,
                thinking=False,
            ),
        )
        result = await provider.generate(
            request,
            ModelRoute(
                provider="ollama",
                model="local-model",
                mode="chat",
                streaming=False,
                thinking=False,
            ),
            None,
        )

        self.assertEqual(captured["path"], "/api/chat")
        payload = captured["payload"]
        self.assertEqual(payload["model"], "local-model")
        self.assertEqual(payload["format"]["type"], "object")
        self.assertEqual(
            [item["function"]["name"] for item in payload["tools"]],
            ["read_file"],
        )
        self.assertIn("AUTHORITATIVE_CONTEXT", payload["messages"][1]["content"])
        self.assertEqual(result.raw_text, '{"status":"ok"}')
        self.assertEqual(result.tool_calls[0].name, "read_file")
        self.assertEqual(result.usage.total_tokens, 25)

    async def test_preserves_conversation_and_streams_through_provider(self):
        captured = {}
        events = []

        async def handler(request):
            captured["payload"] = json.loads(request.content)
            chunks = [
                {
                    "message": {
                        "content": "done",
                        "tool_calls": [],
                    },
                    "done": True,
                    "done_reason": "stop",
                    "prompt_eval_count": 9,
                    "eval_count": 2,
                }
            ]
            return httpx.Response(
                200,
                content=(
                    "\n".join(json.dumps(item) for item in chunks)
                    + "\n"
                ).encode("utf-8"),
            )

        from backend.model_harness import OllamaExecutionOptions

        provider = OllamaChatProvider(
            base_url="http://ollama.invalid",
            default_model="local-model",
            transport=httpx.MockTransport(handler),
        )
        request = ModelRequest(
            task_profile="CODE_REASONING",
            system_prompt="system",
            user_prompt="second",
            expected_output=ExpectedOutput(
                format=OutputFormat.TEXT,
            ),
            metadata={
                "conversation_messages": [
                    {"role": "user", "content": "first"},
                    {
                        "role": "assistant",
                        "content": "answer",
                    },
                    {"role": "user", "content": "second"},
                ],
            },
            execution_constraints=ExecutionConstraints(
                timeout_seconds=5,
                streaming=True,
                thinking=False,
                provider_payload=OllamaExecutionOptions(
                    require_done=True,
                    event_callback=lambda event, metadata, status:
                        events.append((event, status)),
                ),
            ),
        )
        result = await provider.generate(
            request,
            ModelRoute(
                provider="ollama",
                model="local-model",
                mode="chat",
                streaming=True,
                thinking=False,
            ),
            None,
        )

        self.assertEqual(
            captured["payload"]["messages"],
            [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "first"},
                {"role": "assistant", "content": "answer"},
                {"role": "user", "content": "second"},
            ],
        )
        self.assertEqual(result.raw_text, "done")
        self.assertEqual(result.usage.total_tokens, 11)
        self.assertIn(("stream_completed", "COMPLETED"), events)


if __name__ == "__main__":
    unittest.main()
