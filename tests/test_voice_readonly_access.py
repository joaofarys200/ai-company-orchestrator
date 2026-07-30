import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import server
from gemini_live import GeminiLiveService


class VoiceReadOnlyAccessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        server.voice_runtime.state.pending_directive = None

    async def asyncTearDown(self):
        server.voice_runtime.state.pending_directive = None

    def test_gemini_exposes_observation_but_not_writes_by_default(self):
        with patch.dict(
            os.environ,
            {
                "VOICE_ALLOW_TOOLS": "false",
                "VOICE_ALLOW_READONLY_TOOLS": "true",
                "VOICE_CONFIRMATION_MODE": "true",
            },
            clear=False,
        ):
            service = GeminiLiveService("")
            self.assertTrue(service.is_tool_allowed("list_active_windows"))
            self.assertTrue(service.is_tool_allowed("capture_screen"))
            self.assertTrue(service.is_tool_allowed("read_file"))
            self.assertFalse(service.is_tool_allowed("write_file"))
            self.assertFalse(service.is_tool_allowed("execute_command"))

            declarations = service.get_gemini_tools()[0]["functionDeclarations"]
            names = {item["name"] for item in declarations}
            self.assertIn("list_active_windows", names)
            self.assertIn("capture_screen", names)
            self.assertNotIn("write_file", names)
            self.assertNotIn("execute_command", names)

    async def test_read_only_voice_requests_start_without_pending_confirmation(self):
        with patch.dict(os.environ, {"VOICE_AUTO_READONLY": "true"}, clear=False):
            with patch.object(
                server.voice_runtime,
                "start_orchestration",
                new=AsyncMock(),
            ) as start:
                result = await server.handle_voice_directive_candidate(
                    "vagas de emprego", source="test"
                )

            self.assertEqual(result, "Consulta read-only iniciada.")
            start.assert_awaited_once_with("vagas de emprego")
            self.assertIsNone(server.voice_runtime.pending_directive)

    async def test_opening_an_application_still_requires_confirmation(self):
        with patch.dict(os.environ, {"VOICE_AUTO_READONLY": "true"}, clear=False):
            with patch.object(
                server.voice_runtime,
                "connections",
                SimpleNamespace(broadcast=AsyncMock()),
            ):
                result = await server.handle_voice_directive_candidate(
                    "abre o Excel", source="test"
                )

            self.assertIn("aguardar confirmacao", result)
            self.assertEqual(
                server.voice_runtime.pending_directive["prompt"],
                "abre o Excel",
            )

    async def test_confirmed_application_is_opened_without_llm_round_trip(self):
        server.voice_runtime.state.pending_directive = {
            "prompt": "abre o Excel",
            "source": "test",
            "created_at": time.time(),
        }
        with patch.object(
            server.voice_runtime,
            "connections",
            SimpleNamespace(broadcast=AsyncMock()),
        ), patch.object(
            server, "broadcast_state", new=AsyncMock()
        ), patch.object(
            server,
            "open_local_application",
            new=AsyncMock(return_value=(True, "")),
        ) as open_app, patch.object(
            server, "start_directive_orchestration", new=AsyncMock()
        ) as start:
            result = await server.confirm_pending_voice_directive("confirmo", source="test")

        self.assertEqual(result, "Aplicacao aberta.")
        open_app.assert_awaited_once()
        start.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
