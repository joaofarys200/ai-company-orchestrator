import asyncio
import json
import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from agents import tools as ag_tools
from agents.orchestrator import project_builder


TEST_ROOT_REL = f"workspace/projects/_ollama_planning_{os.getpid()}"
MODEL = "test-planner:latest"


def valid_plan_text():
    return json.dumps({
        "project_name": "Resilient plan",
        "stack": "Node.js",
        "components": [],
        "dependencies": [],
        "files": [{"path": "app.js", "content": "console.log('ok');\n"}],
        "component_files": {},
        "setup_commands": [],
        "validation_commands": ["node --check app.js"],
        "entrypoints": ["app.js"],
        "preview_strategy": {},
        "preview_command": "",
        "rationale": "Syntax validation.",
    })


def correction_plan_text(error_code):
    return json.dumps({
        "corrected_plan": json.loads(valid_plan_text()),
        "correction_manifest": [{
            "error_code": error_code,
            "changed_artifacts": [],
            "resolution": "Returned a complete valid plan using the required envelope.",
        }],
    })


def stream_response(content, *, done_reason="stop"):
    chunk = {
        "message": {"role": "assistant", "content": content},
        "done": True,
        "done_reason": done_reason,
        "eval_count": 100,
    }
    return httpx.Response(200, content=(json.dumps(chunk) + "\n").encode("utf-8"))


def readiness_response(path, *, model_exists=True, model_loaded=True):
    if path == "/api/tags":
        models = []
        if model_exists:
            models = [{
                "name": MODEL,
                "size": 1234,
                "details": {
                    "family": "test",
                    "parameter_size": "9B",
                    "quantization_level": "Q4",
                },
            }]
        return httpx.Response(200, json={"models": models})
    if path == "/api/ps":
        models = [{"name": MODEL}] if model_loaded else []
        return httpx.Response(200, json={"models": models})
    return None


async def no_sleep(_seconds):
    await asyncio.sleep(0)


class OllamaPlanningResilienceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.projects_root = Path(ag_tools.resolve_workspace_path(TEST_ROOT_REL))
        shutil.rmtree(self.projects_root, ignore_errors=True)
        self.environment = patch.dict(os.environ, {
            "OLLAMA_MODEL": MODEL,
            "PROJECT_BUILDER_PLAN_CONNECT_TIMEOUT": "1.5",
            "PROJECT_BUILDER_PLAN_READ_TIMEOUT": "240",
            "PROJECT_BUILDER_PLAN_WRITE_TIMEOUT": "7",
            "PROJECT_BUILDER_PLAN_POOL_TIMEOUT": "2",
            "PROJECT_BUILDER_PLAN_RETRY_BACKOFF": "0.001",
            "PROJECT_BUILDER_PLAN_MAX_OUTPUT_TOKENS": "4096",
            "PROJECT_BUILDER_PLAN_CONTEXT_TOKENS": "16384",
        })
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        shutil.rmtree(self.projects_root, ignore_errors=True)

    def requester(self, handler):
        return project_builder.OllamaPlanRequester(
            transport=httpx.MockTransport(handler),
            sleep=no_sleep,
        )

    async def test_a_first_attempt_succeeds(self):
        chat_calls = 0

        def handler(request):
            nonlocal chat_calls
            ready = readiness_response(request.url.path)
            if ready is not None:
                return ready
            chat_calls += 1
            return stream_response(valid_plan_text())

        requester = self.requester(handler)
        plan = await project_builder.get_valid_project_plan("Cria app.js", requester)

        self.assertEqual(plan.project_name, "Resilient plan")
        self.assertEqual(chat_calls, 1)
        self.assertEqual(requester.attempt_count, 1)
        self.assertEqual(requester.attempts[0].status, "SUCCEEDED")

    async def test_b_first_read_timeout_second_attempt_succeeds(self):
        chat_calls = 0

        def handler(request):
            nonlocal chat_calls
            ready = readiness_response(request.url.path)
            if ready is not None:
                return ready
            chat_calls += 1
            if chat_calls == 1:
                raise httpx.ReadTimeout("slow generation", request=request)
            return stream_response(valid_plan_text())

        requester = self.requester(handler)
        plan = await project_builder.get_valid_project_plan("Cria app.js", requester)

        self.assertEqual(plan.project_name, "Resilient plan")
        self.assertEqual(chat_calls, 2)
        self.assertEqual([item.status for item in requester.attempts], ["FAILED", "SUCCEEDED"])
        self.assertEqual(requester.first_error["category"], "PLAN_READ_TIMEOUT")
        self.assertIsNone(requester.final_error)

    async def test_c_two_read_timeouts_stop_after_exactly_two_attempts(self):
        chat_calls = 0

        def handler(request):
            nonlocal chat_calls
            ready = readiness_response(request.url.path)
            if ready is not None:
                return ready
            chat_calls += 1
            raise httpx.ReadTimeout("still slow", request=request)

        requester = self.requester(handler)
        with self.assertRaises(project_builder.ProjectBuilderPlanningError) as ctx:
            await project_builder.get_valid_project_plan("Cria app.js", requester)

        self.assertEqual(ctx.exception.category, "PLAN_READ_TIMEOUT")
        self.assertEqual(chat_calls, 2)
        self.assertEqual(ctx.exception.diagnostics["attempt_count"], 2)
        self.assertEqual(ctx.exception.diagnostics["first_error"]["category"], "PLAN_READ_TIMEOUT")

    async def test_d_connect_timeout_retries_and_preserves_final_error(self):
        chat_calls = 0

        def handler(request):
            nonlocal chat_calls
            ready = readiness_response(request.url.path)
            if ready is not None:
                return ready
            chat_calls += 1
            raise httpx.ConnectTimeout("connect", request=request)

        requester = self.requester(handler)
        with self.assertRaises(project_builder.ProjectBuilderPlanningError) as ctx:
            await project_builder.get_valid_project_plan("Cria app.js", requester)

        self.assertEqual(chat_calls, 2)
        self.assertEqual(ctx.exception.category, "OLLAMA_UNAVAILABLE")
        diagnostics = ctx.exception.diagnostics
        self.assertEqual(diagnostics["first_error"]["error_type"], "ConnectTimeout")
        self.assertEqual(diagnostics["final_error"]["error_type"], "ConnectTimeout")

    async def test_e_http_500_is_retried(self):
        chat_calls = 0

        def handler(request):
            nonlocal chat_calls
            ready = readiness_response(request.url.path)
            if ready is not None:
                return ready
            chat_calls += 1
            if chat_calls == 1:
                return httpx.Response(500, json={"error": "temporary"})
            return stream_response(valid_plan_text())

        requester = self.requester(handler)
        await project_builder.get_valid_project_plan("Cria app.js", requester)

        self.assertEqual(chat_calls, 2)
        self.assertEqual(requester.first_error["category"], "PLAN_HTTP_ERROR")

    async def test_f_http_400_is_not_retried(self):
        chat_calls = 0

        def handler(request):
            nonlocal chat_calls
            ready = readiness_response(request.url.path)
            if ready is not None:
                return ready
            chat_calls += 1
            return httpx.Response(400, json={"error": "bad request"})

        requester = self.requester(handler)
        with self.assertRaises(project_builder.ProjectBuilderPlanningError) as ctx:
            await project_builder.get_valid_project_plan("Cria app.js", requester)

        self.assertEqual(chat_calls, 1)
        self.assertEqual(ctx.exception.category, "PLAN_HTTP_ERROR")

    async def test_g_invalid_json_uses_existing_single_correction(self):
        chat_calls = 0
        payloads = []

        def handler(request):
            nonlocal chat_calls
            ready = readiness_response(request.url.path)
            if ready is not None:
                return ready
            chat_calls += 1
            payloads.append(json.loads(request.content))
            if chat_calls == 1:
                return stream_response("not json")
            return stream_response(correction_plan_text("INVALID_JSON"))

        requester = self.requester(handler)
        plan = await project_builder.get_valid_project_plan("Cria app.js", requester)

        self.assertEqual(plan.project_name, "Resilient plan")
        self.assertEqual(chat_calls, 2)
        self.assertEqual(requester.attempts[0].error_category, "PLAN_JSON_INVALID")
        self.assertEqual(requester.attempts[1].phase, "plan_correction")
        self.assertNotIn("timeout", requester.attempts[0].error_category.lower())
        self.assertIn("Schema correction required", payloads[1]["messages"][1]["content"])

    async def test_h_no_project_directory_is_written_before_valid_plan(self):
        def handler(request):
            ready = readiness_response(request.url.path)
            if ready is not None:
                return ready
            raise httpx.ReadTimeout("slow", request=request)

        requester = self.requester(handler)
        with self.assertRaises(project_builder.ProjectBuilderPlanningError):
            await project_builder.build_project(
                "Cria app.js",
                plan_requester=requester,
                projects_root_rel=TEST_ROOT_REL,
                start_preview=False,
            )

        self.assertFalse(self.projects_root.exists())

    async def test_i_constraints_are_preserved_in_compact_second_attempt(self):
        chat_calls = 0
        payloads = []

        def handler(request):
            nonlocal chat_calls
            ready = readiness_response(request.url.path)
            if ready is not None:
                return ready
            chat_calls += 1
            payloads.append(json.loads(request.content))
            if chat_calls == 1:
                raise httpx.ReadTimeout("slow", request=request)
            return stream_response(valid_plan_text())

        requester = self.requester(handler)
        await project_builder.get_valid_project_plan(
            "Cria uma app. N\u00e3o uses Obsidian.",
            requester,
        )

        second_prompt = payloads[1]["messages"][1]["content"]
        self.assertIn("N\u00e3o uses Obsidian", second_prompt)
        self.assertIn('"excluded_targets": ["Obsidian"]', second_prompt)
        self.assertIn("Authoritative schema used by the validator", second_prompt)
        self.assertIn(project_builder.project_plan_schema_prompt(), second_prompt)

    def test_j_timeout_configuration_is_read_from_environment(self):
        config = project_builder.project_builder_plan_timeout_config()

        self.assertEqual(config.connect, 1.5)
        self.assertEqual(config.read, 240.0)
        self.assertEqual(config.write, 7.0)
        self.assertEqual(config.pool, 2.0)

    async def test_k_logs_do_not_expose_prompt_or_sensitive_values(self):
        secret = "SECRET_API_TOKEN_123"
        sensitive_path = "C:\\private\\project"

        def handler(request):
            ready = readiness_response(request.url.path)
            if ready is not None:
                return ready
            return stream_response(valid_plan_text())

        requester = self.requester(handler)
        with self.assertLogs(project_builder.logger, level="INFO") as captured:
            await requester(f"Create app {secret} {sensitive_path}")

        logs = "\n".join(captured.output)
        self.assertNotIn(secret, logs)
        self.assertNotIn(sensitive_path, logs)
        self.assertNotIn("Create app", logs)
        self.assertIn("prompt_length", logs)

    async def test_l_missing_model_is_distinct_and_not_retried(self):
        chat_calls = 0

        def handler(request):
            nonlocal chat_calls
            ready = readiness_response(request.url.path, model_exists=False)
            if ready is not None:
                return ready
            chat_calls += 1
            return stream_response(valid_plan_text())

        requester = self.requester(handler)
        with self.assertRaises(project_builder.ProjectBuilderPlanningError) as ctx:
            await project_builder.get_valid_project_plan("Cria app.js", requester)

        self.assertEqual(ctx.exception.category, "MODEL_NOT_FOUND")
        self.assertEqual(ctx.exception.diagnostics["attempt_count"], 1)
        self.assertEqual(chat_calls, 0)

    async def test_output_limit_is_controlled_and_not_retried(self):
        def handler(request):
            ready = readiness_response(request.url.path)
            if ready is not None:
                return ready
            return stream_response("{}", done_reason="length")

        requester = self.requester(handler)
        with self.assertRaises(project_builder.ProjectBuilderPlanningError) as ctx:
            await project_builder.get_valid_project_plan("Cria app.js", requester)

        self.assertEqual(ctx.exception.category, "PLAN_OUTPUT_LIMIT_EXCEEDED")
        self.assertEqual(ctx.exception.diagnostics["attempt_count"], 1)


if __name__ == "__main__":
    unittest.main()
