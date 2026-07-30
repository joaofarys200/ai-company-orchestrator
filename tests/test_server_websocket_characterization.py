import json
import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


class ScriptedWebSocket:
    def __init__(self, messages, token):
        self.request = SimpleNamespace(
            path=f"/?token={token}",
            headers={},
        )
        self._messages = [json.dumps(message) for message in messages]
        self.sent = []
        self.closed = None

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)

    async def send(self, payload):
        self.sent.append(json.loads(payload))

    async def close(self, code=None, reason=None):
        self.closed = (code, reason)


class FakeProjectContextService:
    def __init__(self):
        self.projects = []
        self.preview_calls = []
        self.save_calls = []
        self.payload_calls = []

    def list_projects(self):
        return list(self.projects)

    def project_payload(self, project_id, reindex=False):
        self.payload_calls.append((project_id, reindex))
        return {
            "project_id": project_id,
            "project_name": project_id,
            "root_path": f"workspace/projects/{project_id}",
            "symbols": {"files": []},
        }

    def preview_project(self, project_id, output_callback):
        self.preview_calls.append(project_id)
        output_callback("[preview] ready\n")
        return {
            "running": True,
            "preview_url": "http://127.0.0.1:8123/",
        }

    def save_project_file(
        self,
        project_id,
        filename,
        content,
        expected_sha256,
    ):
        self.save_calls.append(
            (project_id, filename, content, expected_sha256)
        )
        return {
            "project_id": project_id,
            "filename": filename,
            "sha256": "b" * 64,
            "size_bytes": len(content.encode("utf-8")),
        }


class FakeCodingSessionService:
    def __init__(self):
        self.create_calls = []
        self.apply_calls = []

    def latest(self, _project_id):
        return None

    async def create_assisted_session(self, project_id, objective):
        self.create_calls.append((project_id, objective))
        return SimpleNamespace(
            to_dict=lambda: {
                "session_id": "session-1",
                "project_id": project_id,
                "objective": objective,
                "status": "PLANNED",
            }
        )

    def apply_session(self, project_id, session_id):
        self.apply_calls.append((project_id, session_id))
        return SimpleNamespace(
            to_dict=lambda: {
                "session_id": session_id,
                "project_id": project_id,
                "status": "SUCCEEDED",
            }
        )


class FakeMissionPlanner:
    def list_missions(self, _project_id):
        return []


class ServerWebSocketCharacterizationTest(
    unittest.IsolatedAsyncioTestCase
):
    def setUp(self):
        import server

        self.server = server
        self.projects = FakeProjectContextService()
        self.coding = FakeCodingSessionService()
        self.planner = FakeMissionPlanner()
        server.active_connections.clear()

        self.patches = [
            patch.object(
                server,
                "project_context_service",
                self.projects,
            ),
            patch.object(
                server,
                "coding_session_service",
                self.coding,
            ),
            patch.object(server, "mission_planner", self.planner),
            patch.object(
                server.database,
                "get_compounding_rules",
                return_value=[],
            ),
            patch.object(
                server.database,
                "get_architecture_memory",
                return_value=[],
            ),
            patch.object(
                server.database,
                "get_engineering_decisions",
                return_value=[],
            ),
            patch.object(
                server.agents,
                "run_obsidian_list_notes",
                AsyncMock(return_value="(Nenhuma nota)"),
            ),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()
        self.server.active_connections.clear()

    async def run_messages(self, *messages):
        websocket = ScriptedWebSocket(
            messages,
            self.server.WS_AUTH_TOKEN,
        )
        gateway = self.server._create_websocket_gateway()
        await gateway.handle_client(websocket)
        return websocket

    async def test_slash_directive_routes_to_command_handler(self):
        command_handler = AsyncMock()
        with patch.object(
            self.server,
            "handle_slash_command",
            command_handler,
        ):
            websocket = await self.run_messages(
                {"type": "directive", "text": "/help"}
            )

        command_handler.assert_awaited_once_with(
            "/help",
            websocket,
            1,
        )

    async def test_open_project_calls_project_services_and_emits_snapshot(self):
        websocket = await self.run_messages(
            {"type": "open_project", "project_id": "demo"}
        )

        self.assertEqual(self.projects.payload_calls, [("demo", False)])
        message_types = [message["type"] for message in websocket.sent]
        self.assertIn("project_context", message_types)
        self.assertIn("ast_state", message_types)
        self.assertIn("coding_session", message_types)
        self.assertIn("mission_list", message_types)

    async def test_run_project_calls_selected_project_preview(self):
        websocket = await self.run_messages(
            {"type": "run_project", "project_id": "demo"}
        )

        self.assertEqual(self.projects.preview_calls, ["demo"])
        status = [
            message
            for message in websocket.sent
            if message["type"] == "project_status"
        ][-1]
        self.assertEqual(
            status,
            {
                "type": "project_status",
                "running": True,
                "preview_url": "http://127.0.0.1:8123/",
            },
        )

    async def test_save_project_file_calls_service_and_emits_result(self):
        digest = "a" * 64
        websocket = await self.run_messages(
            {
                "type": "save_project_file",
                "project_id": "demo",
                "filename": "app.js",
                "content": "const ok = true;\n",
                "expected_sha256": digest,
            }
        )

        self.assertEqual(
            self.projects.save_calls,
            [
                (
                    "demo",
                    "app.js",
                    "const ok = true;\n",
                    digest,
                )
            ],
        )
        result = [
            message
            for message in websocket.sent
            if message["type"] == "project_file_save_result"
        ][-1]
        self.assertTrue(result["ok"])
        self.assertEqual(result["filename"], "app.js")

    async def test_create_coding_session_calls_service_and_emits_session(self):
        websocket = await self.run_messages(
            {
                "type": "create_coding_session",
                "project_id": "demo",
                "objective": "Corrigir o filtro",
            }
        )

        self.assertEqual(
            self.coding.create_calls,
            [("demo", "Corrigir o filtro")],
        )
        session_message = [
            message
            for message in websocket.sent
            if message["type"] == "coding_session"
            and message.get("data")
        ][-1]
        self.assertEqual(
            session_message["data"]["status"],
            "PLANNED",
        )

    async def test_toggle_voice_calls_runtime_voice_service(self):
        voice = SimpleNamespace(
            start=unittest.mock.Mock(),
            stop=unittest.mock.Mock(),
        )
        with patch.object(
            self.server.voice_runtime.state,
            "service",
            voice,
        ):
            websocket = await self.run_messages(
                {"type": "toggle_voice", "active": True},
                {"type": "toggle_voice", "active": False},
            )

        voice.start.assert_called_once_with()
        voice.stop.assert_called_once_with()
        statuses = [
            message["status"]
            for message in websocket.sent
            if message["type"] == "voice_status"
        ]
        self.assertEqual(statuses[-2:], ["idle", "offline"])

    def test_dispatcher_has_one_domain_handler_for_every_protocol_type(self):
        from websocket_schema import CLIENT_MESSAGE_TYPES

        dispatcher, _initial_sync = (
            self.server.create_websocket_handlers(
                services=self.server._current_application_services(),
                connections=self.server.connection_manager,
                callbacks=self.server._websocket_callbacks(),
                logger=self.server.logger,
            )
        )

        self.assertEqual(
            dispatcher.message_types,
            frozenset(CLIENT_MESSAGE_TYPES),
        )
        self.assertEqual(
            dispatcher.domain_for("directive"),
            "chat",
        )
        self.assertEqual(
            dispatcher.domain_for("open_project"),
            "project",
        )
        self.assertEqual(
            dispatcher.domain_for("create_coding_session"),
            "coding",
        )
        self.assertEqual(
            dispatcher.domain_for("mission_create"),
            "mission",
        )

    def test_server_handle_client_is_transport_composition_only(self):
        source = inspect.getsource(self.server.handle_client)

        self.assertIn("websocket_gateway.handle_client", source)
        self.assertNotIn("msg.get", source)
        self.assertNotIn("elif", source)


if __name__ == "__main__":
    unittest.main()
