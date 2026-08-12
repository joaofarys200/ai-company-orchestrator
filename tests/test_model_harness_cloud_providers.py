import json
import unittest
from dataclasses import replace

import httpx

from backend.model_harness import (
    ExecutionConstraints,
    ExpectedOutput,
    GeminiOpenAIProvider,
    ModelPreferences,
    ModelRequest,
    ModelRoute,
    OutputFormat,
)
from backend.model_harness.runtime import create_runtime_model_harness


def tool_request(provider: str, model: str) -> ModelRequest:
    return ModelRequest(
        task_profile="TOOL_SELECTION",
        system_prompt="Usa a ferramenta apropriada.",
        user_prompt="Lista os ficheiros.",
        allowed_tools=("list_files",),
        expected_output=ExpectedOutput(format=OutputFormat.TOOL_CALLS),
        metadata={
            "conversation_messages": [{
                "role": "user",
                "content": "Lista os ficheiros.",
            }],
            "tool_schemas": [{
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "Lista ficheiros.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                        },
                        "required": ["path"],
                    },
                },
            }],
        },
        model_preferences=ModelPreferences(
            providers=(provider,),
            models=(model,),
        ),
        execution_constraints=ExecutionConstraints(
            timeout_seconds=5.0,
            streaming=False,
        ),
    )


class ModelHarnessCloudProviderTest(unittest.IsolatedAsyncioTestCase):
    async def test_gemini_provider_owns_transport_and_parses_tool_call(self):
        observed = {}

        async def handler(request):
            observed["url"] = str(request.url)
            observed["authorization"] = request.headers.get(
                "authorization"
            )
            observed["payload"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "choices": [{
                        "finish_reason": "tool_calls",
                        "message": {
                            "content": "",
                            "tool_calls": [{
                                "id": "g-call",
                                "type": "function",
                                "function": {
                                    "name": "list_files",
                                    "arguments": '{"path":"."}',
                                },
                            }],
                        },
                    }],
                    "usage": {
                        "prompt_tokens": 12,
                        "completion_tokens": 4,
                        "total_tokens": 16,
                    },
                },
            )

        provider = GeminiOpenAIProvider(
            api_key="gemini-test-key",
            base_url="https://gemini.invalid/v1beta/openai",
            transport=httpx.MockTransport(handler),
        )
        result = await provider.generate(
            tool_request("gemini", "gemini-test"),
            ModelRoute(
                provider="gemini",
                model="gemini-test",
                mode="chat",
                streaming=False,
                thinking=False,
            ),
            None,
        )

        self.assertEqual(
            observed["url"],
            "https://gemini.invalid/v1beta/openai/chat/completions",
        )
        self.assertEqual(
            observed["authorization"],
            "Bearer gemini-test-key",
        )
        self.assertEqual(
            observed["payload"]["tools"][0]["function"]["name"],
            "list_files",
        )
        self.assertEqual(result.tool_calls[0].name, "list_files")
        self.assertEqual(
            dict(result.tool_calls[0].arguments),
            {"path": "."},
        )
        self.assertEqual(result.usage.total_tokens, 16)

    def test_shared_runtime_registers_all_productive_providers(self):
        harness = create_runtime_model_harness()
        self.assertEqual(
            harness.providers.names(),
            ("ollama", "gemini"),
        )


if __name__ == "__main__":
    unittest.main()

