from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.model_harness.providers.ollama import OllamaChatProvider
from backend.model_harness.runtime import create_runtime_model_harness
from backend.services.model_service import ModelExecutionService
from backend.websocket.context import WebSocketSessionState
from backend.websocket.handlers.coding import CodingSessionWebSocketHandler
from backend.websocket.handlers.common import WebSocketResponder
from services.obsidian_graph_engine import ObsidianGraphEngine


class _FakeConnections:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.broadcasts: list[dict] = []

    async def send(self, _ws, payload: dict) -> None:
        self.sent.append(payload)

    async def broadcast(self, payload: dict) -> None:
        self.broadcasts.append(payload)


class ModelServiceComplianceTests(unittest.IsolatedAsyncioTestCase):
    async def test_check_model_available_routes_via_ollama_provider_transport(self) -> None:
        seen_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_urls.append(str(request.url))
            return httpx.Response(
                200,
                json={"models": [{"name": "qwen2.5-coder:7b"}]},
            )

        provider = OllamaChatProvider(
            base_url="http://127.0.0.1:21434",
            transport=httpx.MockTransport(handler),
        )
        harness = create_runtime_model_harness(ollama_provider=provider)
        service = ModelExecutionService(harness)

        self.assertTrue(
            await service.check_model_available(
                provider="ollama",
                model="qwen3.5:9b",
                match_family_prefix="qwen",
            )
        )
        self.assertFalse(
            await service.check_model_available(
                provider="ollama",
                model="llama3.2:latest",
                match_family_prefix=None,
            )
        )
        self.assertEqual(seen_urls, [
            "http://127.0.0.1:21434/api/tags",
            "http://127.0.0.1:21434/api/tags",
        ])

    async def test_check_model_available_handles_provider_connect_failure_gracefully(self) -> None:
        def fail_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused", request=request)

        provider = OllamaChatProvider(
            base_url="http://127.0.0.1:21435",
            transport=httpx.MockTransport(fail_handler),
        )
        harness = create_runtime_model_harness(ollama_provider=provider)
        service = ModelExecutionService(harness)

        self.assertFalse(await service.check_model_available(provider="ollama", model="qwen3.5:9b"))

    async def test_obsidian_graph_engine_check_uses_model_execution_service(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"models": [{"name": "qwen3.5:9b"}]})

        provider = OllamaChatProvider(
            base_url="http://127.0.0.1:21436",
            transport=httpx.MockTransport(handler),
        )
        harness = create_runtime_model_harness(ollama_provider=provider)

        with tempfile.TemporaryDirectory(prefix="jarvis_obs_compliance_") as tmp:
            tmp_path = Path(tmp)
            engine = ObsidianGraphEngine(
                vault_root=tmp_path / "vault",
                data_dir=tmp_path / "data",
            )
            with patch(
                "services.obsidian_graph_engine.ObsidianGraphEngine._get_model_execution_service",
                return_value=ModelExecutionService(harness),
            ), patch(
                "urllib.request.urlopen",
                side_effect=AssertionError("Direct urllib.request.urlopen bypass must not be called"),
            ):
                self.assertTrue(await engine.check_ollama_qwen_available_async())
                # Also verify synchronous compatibility wrapper works safely inside running loop
                self.assertTrue(engine.check_ollama_qwen_available())

    async def test_coding_handler_connection_and_timeout_diagnostics_use_model_service(self) -> None:
        provider = OllamaChatProvider(base_url="http://127.0.0.1:22434")
        harness = create_runtime_model_harness(ollama_provider=provider)
        model_service = ModelExecutionService(harness)

        class _FailingCodingSessions:
            def __init__(self, exc: Exception) -> None:
                self.exc = exc

            async def create_assisted_session(self, _project_id: str, _objective: str):
                raise self.exc

        connections = _FakeConnections()
        responder = WebSocketResponder(None, None, None, connections)
        handler_conn_err = CodingSessionWebSocketHandler(
            _FailingCodingSessions(httpx.ConnectError("refused")),
            responder,
            model_service=model_service,
        )
        session = WebSocketSessionState()
        await handler_conn_err.create_session(
            object(),
            {"project_id": "proj-1", "objective": "refactor"},
            session,
        )
        self.assertEqual(len(connections.sent), 2)
        self.assertEqual(connections.sent[0]["type"], "coding_session_error")
        self.assertIn("http://127.0.0.1:22434", connections.sent[0]["error"])
        self.assertEqual(connections.sent[1]["type"], "system")

        connections.sent.clear()
        handler_timeout = CodingSessionWebSocketHandler(
            _FailingCodingSessions(TimeoutError("timed out")),
            responder,
            model_service=model_service,
        )
        await handler_timeout.create_session(
            object(),
            {"project_id": "proj-1", "objective": "refactor"},
            session,
        )
        self.assertIn("JARVIS_CODING_PLAN_TIMEOUT_SECONDS", connections.sent[0]["error"])


if __name__ == "__main__":
    unittest.main()
