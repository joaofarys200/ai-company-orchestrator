import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from backend.model_harness import (
    ExpectedOutput,
    ModelPreferences,
    ModelRequest,
    ModelRoute,
    OutputFormat,
)

from scripts.model_harness_benchmark import (
    BenchmarkConfig,
    OllamaBenchmarkProvider,
    SYNTHETIC_SECRET,
    _assert_output_location,
    benchmark_cases,
    evaluate,
)


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "request failed",
                request=httpx.Request("GET", "http://ollama.test/api/ps"),
                response=httpx.Response(self.status_code),
            )


class _FakeOllamaClient:
    def __init__(self, *, loaded_models=(), post_error=None):
        self.loaded_models = set(loaded_models)
        self.post_error = post_error
        self.get_calls = []
        self.post_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, path, **_kwargs):
        self.get_calls.append(path)
        if path != "/api/ps":
            raise AssertionError(f"Unexpected GET {path}")
        return _FakeResponse({
            "models": [
                {"name": model}
                for model in sorted(self.loaded_models)
            ],
        })

    async def post(self, path, *, json):
        self.post_calls.append((path, json))
        if self.post_error is not None:
            self.loaded_models.add(json["model"])
            raise self.post_error
        return _FakeResponse({
            "message": {"content": '{"decision":"FINISH"}'},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 10,
            "eval_count": 2,
        })


def _provider_config(*, recycle=False):
    return BenchmarkConfig(
        model="selected-model",
        base_url="http://ollama.test",
        context_tokens=8192,
        output_tokens=128,
        temperature=0.0,
        top_p=0.8,
        seed=42,
        think=False,
        stream=False,
        repetitions=1,
        keep_alive="15m",
        timeout_seconds=30,
        recycle_loaded_model_before_first_request=recycle,
    )


def _provider_request():
    return ModelRequest(
        task_profile="TOOL_SELECTION",
        system_prompt="Return JSON.",
        user_prompt="Select one tool.",
        expected_output=ExpectedOutput(format=OutputFormat.JSON),
        temperature=0.0,
        max_context_tokens=8192,
        max_output_tokens=128,
        model_preferences=ModelPreferences(
            providers=("ollama",),
            models=("selected-model",),
        ),
    )


def _provider_route():
    return ModelRoute(
        provider="ollama",
        model="selected-model",
        mode="chat",
        streaming=False,
        thinking=False,
    )


class ModelHarnessBenchmarkDefinitionTest(unittest.TestCase):
    def test_cases_are_unique_synthetic_and_side_effect_free(self):
        cases = benchmark_cases()

        self.assertEqual(len(cases), 8)
        self.assertEqual(
            len({item.case_id for item in cases}),
            len(cases),
        )
        for case in cases:
            self.assertTrue(case.schema)
            self.assertTrue(case.system_prompt)
            self.assertTrue(case.user_prompt)
            self.assertNotIn("workspace/projects", case.user_prompt)
            self.assertNotIn("MissionState", case.user_prompt)

    def test_output_is_restricted_to_diagnostics_area(self):
        allowed = Path(
            "diagnostics",
            "model_harness_benchmark",
            "test-run",
        )
        _assert_output_location(allowed)

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError):
                _assert_output_location(Path(temp_dir))

    def test_security_evaluator_requires_refusal_without_secret(self):
        passed = evaluate(
            "instruction_hierarchy",
            {"refused": True, "reason": "Cannot disclose it."},
            '{"refused":true,"reason":"Cannot disclose it."}',
        )
        failed = evaluate(
            "instruction_hierarchy",
            {"refused": True, "reason": SYNTHETIC_SECRET},
            SYNTHETIC_SECRET,
        )

        self.assertTrue(all(item["passed"] for item in passed))
        self.assertFalse(all(item["passed"] for item in failed))

    def test_code_evaluator_accepts_equivalent_empty_array_guards(self):
        explicit = evaluate(
            "code_reasoning",
            {
                "bug_code": "EMPTY_COLLECTION_DIVISION",
                "minimal_fix": (
                    "if (values.length === 0) return 0; "
                    "return values.reduce((sum, n) => sum + n, 0) "
                    "/ values.length;"
                ),
            },
            "",
        )
        fallback = evaluate(
            "code_reasoning",
            {
                "bug_code": "EMPTY_COLLECTION_DIVISION",
                "minimal_fix": (
                    "return values.reduce((sum, n) => sum + n, 0) "
                    "/ (values.length || 1);"
                ),
            },
            "",
        )

        self.assertTrue(all(item["passed"] for item in explicit))
        self.assertTrue(all(item["passed"] for item in fallback))

    def test_bounded_v1_does_not_recycle_loaded_runner(self):
        client = _FakeOllamaClient(loaded_models=("selected-model",))
        provider = OllamaBenchmarkProvider(_provider_config())

        with (
            patch(
                "scripts.model_harness_benchmark.httpx.AsyncClient",
                return_value=client,
            ),
            patch(
                "scripts.model_harness_benchmark.subprocess.run",
            ) as stop,
        ):
            asyncio.run(provider.generate(
                _provider_request(),
                _provider_route(),
                None,
            ))

        self.assertFalse(
            provider.config.recycle_loaded_model_before_first_request
        )
        self.assertEqual(len(client.post_calls), 1)
        self.assertEqual(client.get_calls, ["/api/ps"])
        self.assertIn("selected-model", client.loaded_models)
        stop.assert_not_called()

    def test_stateful_guard_recycles_only_selected_loaded_runner(self):
        client = _FakeOllamaClient(
            loaded_models=("selected-model", "unrelated-model"),
        )
        provider = OllamaBenchmarkProvider(
            _provider_config(recycle=True)
        )
        stop_commands = []

        def fake_stop(command, **_kwargs):
            stop_commands.append(command)
            client.loaded_models.discard(command[-1])
            return SimpleNamespace(returncode=0)

        with (
            patch(
                "scripts.model_harness_benchmark.httpx.AsyncClient",
                return_value=client,
            ),
            patch(
                "scripts.model_harness_benchmark.subprocess.run",
                side_effect=fake_stop,
            ),
        ):
            result = asyncio.run(provider.generate(
                _provider_request(),
                _provider_route(),
                None,
            ))

        self.assertEqual(
            stop_commands,
            [["ollama", "stop", "selected-model"]],
        )
        self.assertEqual(len(client.post_calls), 1)
        self.assertNotIn("selected-model", client.loaded_models)
        self.assertIn("unrelated-model", client.loaded_models)
        self.assertEqual(
            result.metadata["runner_guard"][-1]["status"],
            "RECYCLED",
        )

    def test_stateful_timeout_cleans_runner_without_retry(self):
        request = httpx.Request(
            "POST",
            "http://ollama.test/api/chat",
        )
        timeout_error = httpx.ReadTimeout(
            "no response bytes",
            request=request,
        )
        client = _FakeOllamaClient(post_error=timeout_error)
        provider = OllamaBenchmarkProvider(
            _provider_config(recycle=True)
        )
        stop_commands = []

        def fake_stop(command, **_kwargs):
            stop_commands.append(command)
            client.loaded_models.discard(command[-1])
            return SimpleNamespace(returncode=0)

        with (
            patch(
                "scripts.model_harness_benchmark.httpx.AsyncClient",
                return_value=client,
            ),
            patch(
                "scripts.model_harness_benchmark.subprocess.run",
                side_effect=fake_stop,
            ),
            self.assertRaises(httpx.ReadTimeout) as captured,
        ):
            asyncio.run(provider.generate(
                _provider_request(),
                _provider_route(),
                None,
            ))

        self.assertIs(captured.exception, timeout_error)
        self.assertEqual(len(client.post_calls), 1)
        self.assertEqual(
            stop_commands,
            [["ollama", "stop", "selected-model"]],
        )
        self.assertFalse(provider._runner_guard_completed)
        self.assertEqual(
            provider.runner_guard_events[-1]["reason"],
            "zero_byte_read_timeout",
        )
        self.assertEqual(
            provider.runner_guard_events[-1]["status"],
            "RECYCLED",
        )


if __name__ == "__main__":
    unittest.main()
