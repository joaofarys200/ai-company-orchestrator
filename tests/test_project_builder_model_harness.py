import json
import os
import unittest
from unittest.mock import patch

import httpx

from agents.orchestrator import project_builder
from backend.model_harness import (
    ModelResponse,
    ModelResponseStatus,
)


MODEL = "harness-test:latest"


def stream_response(content):
    return httpx.Response(
        200,
        content=(json.dumps({
            "message": {"role": "assistant", "content": content},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 11,
            "eval_count": 7,
        }) + "\n").encode("utf-8"),
    )


def readiness(request):
    if request.url.path == "/api/tags":
        return httpx.Response(
            200,
            json={"models": [{"name": MODEL}]},
        )
    if request.url.path == "/api/ps":
        return httpx.Response(
            200,
            json={"models": [{"name": MODEL}]},
        )
    return None


class RecordingHarness:
    def __init__(self, raw_text):
        self.raw_text = raw_text
        self.requests = []

    async def execute(self, request):
        self.requests.append(request)
        return ModelResponse(
            request_id=request.request_id,
            status=ModelResponseStatus.SUCCEEDED,
            raw_text=self.raw_text,
            provider="ollama",
            model=MODEL,
        )


class ProjectBuilderModelHarnessTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {
            "OLLAMA_MODEL": MODEL,
            "PROJECT_BUILDER_PLAN_RETRY_BACKOFF": "0.001",
        })
        self.environment.start()

    def tearDown(self):
        self.environment.stop()

    async def test_default_requester_routes_exact_messages_through_harness(self):
        payloads = []

        def handler(request):
            ready = readiness(request)
            if ready is not None:
                return ready
            payloads.append(json.loads(request.content))
            return stream_response('{"project_name":"demo"}')

        requester = project_builder.OllamaPlanRequester(
            transport=httpx.MockTransport(handler),
        )
        prompt = "Cria projeto demo"
        result = await requester(prompt)

        self.assertIn("project_name", result)
        self.assertEqual(
            payloads[0]["messages"],
            project_builder._ollama_messages(prompt, None, False),
        )
        self.assertEqual(payloads[0]["model"], MODEL)
        self.assertEqual(payloads[0]["options"]["temperature"], 0)
        self.assertEqual(payloads[0]["think"], False)
        telemetry = requester.model_harness.telemetry.snapshot()
        self.assertEqual(len(telemetry), 1)
        self.assertEqual(
            telemetry[0]["task_profile"],
            "STRUCTURED_EXTRACTION",
        )
        self.assertEqual(telemetry[0]["provider"], "ollama")
        self.assertEqual(telemetry[0]["validation_status"], "DEFERRED")
        self.assertEqual(telemetry[0]["input_tokens"], 11)
        self.assertEqual(telemetry[0]["output_tokens"], 7)

    async def test_focal_correction_is_bounded_context_not_an_extra_call(self):
        payloads = []
        correction = '{"errors":["fix"]}'

        def handler(request):
            ready = readiness(request)
            if ready is not None:
                return ready
            payloads.append(json.loads(request.content))
            return stream_response("{}")

        requester = project_builder.OllamaPlanRequester(
            transport=httpx.MockTransport(handler),
        )
        await requester("base")
        await requester("base", correction)

        telemetry = requester.model_harness.telemetry.snapshot()
        self.assertEqual(len(payloads), 2)
        self.assertEqual(len(telemetry), 2)
        self.assertEqual(telemetry[0]["context_items"], 0)
        self.assertEqual(telemetry[1]["context_items"], 1)
        self.assertEqual(
            payloads[1]["format"],
            project_builder._ollama_generation_contract(
                correction
            ).response_format,
        )
        self.assertEqual(requester.attempt_count, 2)

    async def test_injected_harness_intercepts_before_any_provider_transport(self):
        harness = RecordingHarness('{"project_name":"intercepted"}')

        def unexpected_transport(_request):
            raise AssertionError("provider transport should not be called")

        requester = project_builder.OllamaPlanRequester(
            transport=httpx.MockTransport(unexpected_transport),
            model_harness=harness,
        )
        result = await requester("base")

        self.assertIn("intercepted", result)
        self.assertEqual(len(harness.requests), 1)
        model_request = harness.requests[0]
        self.assertEqual(
            model_request.task_profile,
            "STRUCTURED_EXTRACTION",
        )
        self.assertEqual(
            model_request.model_preferences.providers,
            ("ollama",),
        )
        self.assertTrue(model_request.expected_output.defer_validation)
        self.assertEqual(
            model_request.expected_output.validation_owner,
            "ProjectBuilder",
        )
        self.assertEqual(requester.attempt_count, 1)


if __name__ == "__main__":
    unittest.main()
