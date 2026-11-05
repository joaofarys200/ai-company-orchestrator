import asyncio
import logging
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from backend.application_services import ApplicationServices
from backend.model_harness.contracts import (
    ExecutionConstraints,
    ExpectedOutput,
    ModelRequest,
    ModelRoute,
    OutputFormat,
    ProviderResult,
)
from backend.model_harness.providers.ollama import (
    OllamaChatProvider,
    OllamaExecutionOptions,
)
from backend.services.local_app_service import (
    find_folder_request,
    find_local_app_request,
)
from backend.services.voice_runtime import (
    VoiceDirectiveService,
    VoiceRuntimeCallbacks,
)


class TestVoiceLocalAppsAndFolders(unittest.TestCase):
    def test_find_folder_request_resolves_dina_project(self):
        result = find_folder_request("abrir a pasta Dina")
        self.assertIsNotNone(result)
        self.assertEqual(result["source"], "folder")
        self.assertIn("dina", result["path"].lower())
        self.assertTrue(os.path.isdir(result["path"]))

    def test_find_folder_request_variations(self):
        for phrase in (
            "abre pasta dina",
            "abrir a pasta do projeto dina",
            "abre a pasta dina",
        ):
            res = find_folder_request(phrase)
            self.assertIsNotNone(res, f"Failed for phrase: {phrase}")
            self.assertIn("dina", res["path"].lower())

    def test_find_folder_request_projects_root(self):
        res = find_folder_request("abre a pasta de projetos")
        self.assertIsNotNone(res)
        self.assertTrue(os.path.isdir(res["path"]))

    def test_find_folder_request_downloads(self):
        res = find_folder_request("abrir a pasta downloads")
        self.assertIsNotNone(res)
        self.assertTrue(os.path.isdir(res["path"]))

    def test_find_local_app_request_includes_google_and_folder(self):
        google_app = find_local_app_request("abrir o Google")
        self.assertIsNotNone(google_app)
        self.assertEqual(google_app["id"], "google")

        dina_folder = find_local_app_request("abrir a pasta Dina")
        self.assertIsNotNone(dina_folder)
        self.assertEqual(dina_folder["source"], "folder")
        self.assertIn("dina", dina_folder["path"].lower())


class TestVoiceDirectiveAutoExecution(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_broadcast = AsyncMock()
        self.mock_connections = SimpleNamespace(
            broadcast=self.mock_broadcast,
            send=AsyncMock(),
        )
        self.mock_open_app = AsyncMock(return_value=(True, ""))
        self.mock_broadcast_state = AsyncMock()
        self.mock_orchestration = AsyncMock()
        self.callbacks = VoiceRuntimeCallbacks(
            run_in_main_loop=lambda coro: None,
            broadcast_state=self.mock_broadcast_state,
            run_orchestration_task=self.mock_orchestration,
            open_local_application=self.mock_open_app,
        )
        self.service = VoiceDirectiveService(
            services=SimpleNamespace(database=SimpleNamespace(create_session=lambda p: SimpleNamespace(id=1))),
            connections=self.mock_connections,
            callbacks=self.callbacks,
            conversation_history=[],
            logger=logging.getLogger("test"),
        )

    async def test_auto_execute_local_app_google(self):
        with patch.dict(
            os.environ,
            {
                "VOICE_CONFIRMATION_MODE": "true",
                "VOICE_AUTO_EXECUTE_LOCAL_APPS": "true",
            },
            clear=False,
        ):
            res = await self.service.handle_candidate("abrir o Google")
            self.assertEqual(res, "Aplicacao aberta.")
            self.mock_open_app.assert_awaited_once()
            self.assertIsNone(self.service.pending_directive)

    async def test_auto_execute_folder_dina(self):
        with patch.dict(
            os.environ,
            {
                "VOICE_CONFIRMATION_MODE": "true",
                "VOICE_AUTO_EXECUTE_LOCAL_APPS": "true",
            },
            clear=False,
        ):
            res = await self.service.handle_candidate("abrir a pasta Dina")
            self.assertEqual(res, "Aplicacao aberta.")
            self.mock_open_app.assert_awaited_once()
            called_arg = self.mock_open_app.call_args[0][0]
            self.assertEqual(called_arg["source"], "folder")
            self.assertIn("dina", called_arg["path"].lower())
            self.assertIsNone(self.service.pending_directive)

    async def test_confirmation_mode_without_auto_execute_waits(self):
        with patch.dict(
            os.environ,
            {
                "VOICE_CONFIRMATION_MODE": "true",
                "VOICE_AUTO_EXECUTE_LOCAL_APPS": "false",
            },
            clear=False,
        ):
            res = await self.service.handle_candidate("abrir a pasta Dina")
            self.assertIn("aguardar confirmacao", res)
            self.assertIsNotNone(self.service.pending_directive)
            self.assertEqual(
                self.service.pending_directive["prompt"],
                "abrir a pasta Dina",
            )


class TestOllamaRecoveryFrom500(unittest.IsolatedAsyncioTestCase):
    async def test_ollama_retries_with_reduced_context_on_500(self):
        provider = OllamaChatProvider()

        call_count = 0
        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            body = request.read().decode("utf-8")
            if call_count == 1:
                # First attempt with num_ctx=8192 fails with 500 (VRAM crash)
                return httpx.Response(500, text="Internal Server Error: CUDA out of memory")
            # Second attempt with num_ctx=4096 succeeds
            self.assertTrue('"num_ctx":4096' in body or '"num_ctx": 4096' in body)
            return httpx.Response(
                200,
                json={
                    "model": "qwen3.5:9b",
                    "message": {"role": "assistant", "content": "Sucesso apos recovery!"},
                    "done": True,
                },
            )

        transport = httpx.MockTransport(handler)
        provider.transport = transport

        events = []
        options = OllamaExecutionOptions(event_callback=lambda evt, meta, st: events.append(evt))
        req = ModelRequest(
            task_profile="GENERAL",
            system_prompt="sys",
            user_prompt="ola",
            allowed_tools=(),
            expected_output=ExpectedOutput(format=OutputFormat.TEXT),
            temperature=0.0,
            max_context_tokens=8192,
            metadata={},
            execution_constraints=ExecutionConstraints(provider_payload=options),
        )
        route = ModelRoute(
            provider="ollama",
            model="qwen3.5:9b",
            mode="chat",
            streaming=False,
            thinking=False,
        )

        result = await provider.generate(req, route, None)
        self.assertEqual(result.raw_text, "Sucesso apos recovery!")
        self.assertEqual(call_count, 2)
        self.assertIn("ollama_500_retry_with_reduced_context", events)


if __name__ == "__main__":
    unittest.main()
