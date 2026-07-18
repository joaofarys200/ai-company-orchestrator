import asyncio
import hashlib
import json
import os
import unittest
from unittest.mock import patch

import httpx
from jsonschema import Draft202012Validator

from agents.orchestrator import project_builder


MODEL = "focal-schema-test:latest"
EXPECTED_COMPONENTS = ["frontend", "backend", "persistence", "tests", "preview"]
ALLOWED_REPLACEMENTS = ["backend/server.js", "package.json", "tests/run-tests.js"]
ERROR_CODES = ["MISSING_REQUESTED_COMPONENTS", "COMMAND_TARGET_INVALID"]


def focal_request():
    return {
        "protocol": project_builder.FOCAL_CORRECTION_PROTOCOL,
        "allowed_plan_updates": ["components"],
        "plan_update_context": {
            "components": {
                "original_complete_value": ["frontend", "backend", "persistence", "tests"],
                "missing_requested_components": ["preview"],
                "expected_final_complete_value": EXPECTED_COMPONENTS,
            },
        },
        "allowed_replacements": ALLOWED_REPLACEMENTS,
        "errors": [{"error_code": code} for code in ERROR_CODES],
    }


def valid_response(*, replacements=None):
    return {
        "plan_updates": {"components": EXPECTED_COMPONENTS},
        "replacements": list(replacements or []),
    }


def validator():
    schema = project_builder._focal_correction_response_schema(focal_request())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema), schema


def stream_response(content):
    chunk = {
        "message": {"role": "assistant", "content": content},
        "done": True,
        "done_reason": "stop",
    }
    return httpx.Response(200, content=(json.dumps(chunk) + "\n").encode("utf-8"))


def readiness_response(path):
    if path == "/api/tags":
        return httpx.Response(200, json={"models": [{"name": MODEL}]})
    if path == "/api/ps":
        return httpx.Response(200, json={"models": [{"name": MODEL}]})
    return None


async def no_sleep(_seconds):
    await asyncio.sleep(0)


class FocalCorrectionSchemaTest(unittest.TestCase):
    def test_01_v2_requires_only_plan_updates_and_replacements(self):
        _, schema = validator()

        self.assertEqual(
            set(schema["required"]),
            {"plan_updates", "replacements"},
        )
        self.assertEqual(set(schema["properties"]), {"plan_updates", "replacements"})

    def test_02_top_level_additional_properties_are_forbidden(self):
        _, schema = validator()

        self.assertIs(schema["additionalProperties"], False)

    def test_03_correction_manifest_from_model_is_rejected(self):
        check, _ = validator()
        response = valid_response()
        response["correction_manifest"] = [{
            "error_code": "COMMAND_TARGET_INVALID",
            "changed_artifacts": ["package.json"],
            "resolution": "Wrong location.",
        }]

        self.assertFalse(check.is_valid(response))

    def test_04_replacement_without_path_is_rejected(self):
        check, _ = validator()

        self.assertFalse(check.is_valid(valid_response(replacements=[{"content": "fixed"}])))

    def test_05_replacement_without_content_is_rejected(self):
        check, _ = validator()

        self.assertFalse(check.is_valid(valid_response(replacements=[{"path": "package.json"}])))

    def test_05b_empty_replacement_content_is_rejected_locally(self):
        response = valid_response(replacements=[{"path": "package.json", "content": ""}])

        _updates, _replacements, errors = project_builder._strict_focal_correction_envelope(
            response
        )

        self.assertIn("CORRECTION_REPLACEMENT_INVALID", {item.code for item in errors})

    def test_06_missing_replacements_is_rejected(self):
        check, _ = validator()
        response = valid_response()
        del response["replacements"]

        self.assertFalse(check.is_valid(response))

    def test_07_replacement_path_outside_allowlist_is_rejected(self):
        check, _ = validator()
        response = valid_response(replacements=[{
            "path": "frontend/index.html",
            "content": "<!doctype html>",
        }])

        self.assertFalse(check.is_valid(response))

    def test_08_changed_artifacts_from_model_is_rejected(self):
        check, _ = validator()
        response = valid_response()
        response["changed_artifacts"] = ["components"]

        self.assertFalse(check.is_valid(response))

    def test_09_components_uses_const_with_complete_final_value(self):
        _, schema = validator()

        self.assertEqual(
            schema["properties"]["plan_updates"]["properties"]["components"],
            {"const": EXPECTED_COMPONENTS},
        )

    def test_10_components_delta_only_is_rejected(self):
        check, _ = validator()
        response = valid_response()
        response["plan_updates"]["components"] = ["preview"]

        self.assertFalse(check.is_valid(response))

    def test_11_replacements_accepts_an_allowed_subset(self):
        check, _ = validator()
        response = valid_response(
            replacements=[{"path": "tests/run-tests.js", "content": "fixed test"}],
        )

        self.assertTrue(check.is_valid(response))

    def test_12_empty_replacements_is_valid_for_plan_update_only(self):
        check, _ = validator()

        self.assertTrue(check.is_valid(valid_response(replacements=[])))


class FocalCorrectionOllamaContractTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {
            "OLLAMA_MODEL": MODEL,
            "PROJECT_BUILDER_PLAN_RETRY_BACKOFF": "0.001",
        })
        self.environment.start()

    def tearDown(self):
        self.environment.stop()

    def requester(self, handler):
        return project_builder.OllamaPlanRequester(
            transport=httpx.MockTransport(handler),
            sleep=no_sleep,
        )

    async def test_13_focal_call_sends_dynamic_schema_and_telemetry(self):
        payloads = []

        def handler(request):
            ready = readiness_response(request.url.path)
            if ready is not None:
                return ready
            payloads.append(json.loads(request.content))
            if len(payloads) == 1:
                return stream_response("{}")
            return stream_response(json.dumps(valid_response()))

        requester = self.requester(handler)
        await requester("base objective")
        await requester("base objective", json.dumps(focal_request()))

        focal_payload = payloads[1]
        expected_schema = project_builder._focal_correction_response_schema(focal_request())
        self.assertEqual(focal_payload["format"], expected_schema)
        self.assertIs(focal_payload["stream"], True)
        record = requester.attempts[1]
        encoded = json.dumps(
            expected_schema,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.assertTrue(record.structured_output_enabled)
        self.assertEqual(record.correction_schema_sha256, hashlib.sha256(encoded).hexdigest())
        self.assertEqual(record.correction_schema_length, len(encoded))
        self.assertEqual(
            record.correction_schema_version,
            project_builder.FOCAL_CORRECTION_SCHEMA_VERSION,
        )
        self.assertTrue(record.streaming_enabled)
        self.assertNotIn("response_format", requester.diagnostics()["attempts"][1])

    async def test_14_first_call_keeps_plain_json_format_and_streaming(self):
        payloads = []

        def handler(request):
            ready = readiness_response(request.url.path)
            if ready is not None:
                return ready
            payloads.append(json.loads(request.content))
            return stream_response("{}")

        requester = self.requester(handler)
        await requester("base objective")

        self.assertEqual(payloads[0]["format"], "json")
        self.assertIs(payloads[0]["stream"], True)
        self.assertFalse(requester.attempts[0].structured_output_enabled)
        self.assertEqual(requester.attempts[0].correction_schema_sha256, "")

    async def test_15_provider_schema_rejection_has_no_free_json_fallback(self):
        chat_calls = 0

        def handler(request):
            nonlocal chat_calls
            ready = readiness_response(request.url.path)
            if ready is not None:
                return ready
            chat_calls += 1
            if chat_calls == 1:
                return stream_response("{}")
            return httpx.Response(400, json={"error": "JSON Schema format is not supported"})

        requester = self.requester(handler)
        await requester("base objective")
        with self.assertRaises(project_builder.ProjectBuilderPlanningError) as captured:
            await requester("base objective", json.dumps(focal_request()))

        self.assertEqual(
            captured.exception.category,
            "CORRECTION_STRUCTURED_OUTPUT_UNSUPPORTED",
        )
        self.assertEqual(chat_calls, 2)
        self.assertEqual(requester.attempt_count, 2)
        self.assertTrue(requester.attempts[1].structured_output_enabled)
        self.assertEqual(requester.attempts[1].retry_reason, "")

    async def test_16_requester_still_allows_at_most_two_calls(self):
        chat_calls = 0

        def handler(request):
            nonlocal chat_calls
            ready = readiness_response(request.url.path)
            if ready is not None:
                return ready
            chat_calls += 1
            return stream_response("{}")

        requester = self.requester(handler)
        await requester("base objective")
        await requester("base objective", json.dumps(focal_request()))
        with self.assertRaises(project_builder.ProjectBuilderPlanningError):
            await requester("base objective", json.dumps(focal_request()))

        self.assertEqual(chat_calls, 2)
        self.assertEqual(requester.attempt_count, project_builder.PLAN_MAX_ATTEMPTS)


if __name__ == "__main__":
    unittest.main()
