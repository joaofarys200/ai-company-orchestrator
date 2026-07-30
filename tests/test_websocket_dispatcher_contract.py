import inspect
import json
import unittest
from dataclasses import MISSING, fields
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from backend.application_services import ApplicationServices
from backend.websocket.context import WebSocketSessionState
from backend.websocket.contracts import (
    EXPECTED_MESSAGE_TYPES,
    HandlerResult,
)
from backend.websocket.dispatcher import WebSocketDispatcher
from backend.websocket.errors import UnknownWebSocketMessageError
from backend.websocket.gateway import (
    ConnectionManager,
    WebSocketGateway,
    serialize_server_message,
)
from backend.websocket.handlers.chat import (
    CHAT_HANDLERS,
    ChatWebSocketHandler,
)
from backend.websocket.handlers.coding import (
    CODING_HANDLERS,
    CodingSessionWebSocketHandler,
)
from backend.websocket.handlers.common import WebSocketRuntimeCallbacks
from backend.websocket.handlers.knowledge import (
    KNOWLEDGE_HANDLERS,
    KnowledgeWebSocketHandler,
)
from backend.websocket.handlers.missions import (
    MISSION_HANDLERS,
    MissionWebSocketHandler,
)
from backend.websocket.handlers.projects import (
    PROJECT_HANDLERS,
    ProjectWebSocketHandler,
)
from backend.websocket.handlers.system import (
    SYSTEM_HANDLERS,
    SystemWebSocketHandler,
)
from backend.websocket.handlers.voice import (
    VOICE_HANDLERS,
    VoiceWebSocketHandler,
)
from backend.websocket.registry import create_websocket_handlers
from websocket_schema import CLIENT_MESSAGE_TYPES


DOMAIN_HANDLER_MAPS = {
    "chat": CHAT_HANDLERS,
    "voice": VOICE_HANDLERS,
    "project": PROJECT_HANDLERS,
    "coding": CODING_HANDLERS,
    "knowledge": KNOWLEDGE_HANDLERS,
    "system": SYSTEM_HANDLERS,
    "mission": MISSION_HANDLERS,
}

DOMAIN_HANDLER_CLASSES = (
    ChatWebSocketHandler,
    VoiceWebSocketHandler,
    ProjectWebSocketHandler,
    CodingSessionWebSocketHandler,
    KnowledgeWebSocketHandler,
    SystemWebSocketHandler,
    MissionWebSocketHandler,
)


def fake_services() -> ApplicationServices:
    placeholder = SimpleNamespace()
    return ApplicationServices(
        database=placeholder,
        agents=placeholder,
        sandbox=placeholder,
        model_harness=placeholder,
        project_context=placeholder,
        coding_sessions=placeholder,
        mission_planner=placeholder,
        mission_executor=placeholder,
        mission_autonomy=placeholder,
    )


def fake_callbacks() -> WebSocketRuntimeCallbacks:
    return WebSocketRuntimeCallbacks(
        handle_slash_command=AsyncMock(),
        parse_file_context=lambda prompt: prompt,
        run_orchestration_task=AsyncMock(),
        broadcast_state=AsyncMock(),
        run_in_main_loop=lambda _awaitable: None,
        normalize_template_name=lambda value: str(value),
        build_template_payload=lambda value: {
            "type": "template_changed",
            "template_name": value,
        },
        read_persistent_plan_state=lambda: {},
        get_voice_service=lambda: None,
        conversation_history=[],
    )


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


class WebSocketDispatcherStructureTest(unittest.TestCase):
    def setUp(self):
        self.services = fake_services()
        self.connections = ConnectionManager()
        self.dispatcher, _ = create_websocket_handlers(
            services=self.services,
            connections=self.connections,
            callbacks=fake_callbacks(),
            logger=SimpleNamespace(),
        )

    def test_canonical_types_match_protocol_and_every_type_is_unique(self):
        registered = [
            message_type
            for mapping in DOMAIN_HANDLER_MAPS.values()
            for message_type in mapping
        ]

        self.assertEqual(len(registered), len(set(registered)))
        self.assertEqual(
            frozenset(registered),
            EXPECTED_MESSAGE_TYPES,
        )
        self.assertEqual(
            EXPECTED_MESSAGE_TYPES,
            frozenset(CLIENT_MESSAGE_TYPES),
        )
        self.assertEqual(
            self.dispatcher.message_types,
            EXPECTED_MESSAGE_TYPES,
        )

    def test_every_registered_handler_has_uniform_async_signature(self):
        for message_type, handler in self.dispatcher.handlers.items():
            with self.subTest(message_type=message_type):
                self.assertTrue(
                    inspect.iscoroutinefunction(handler)
                )
                parameters = list(
                    inspect.signature(handler).parameters.values()
                )
                self.assertEqual(
                    [parameter.name for parameter in parameters],
                    ["context", "payload"],
                )

    def test_duplicate_registration_is_rejected(self):
        async def handler(_context, _payload):
            return None

        dispatcher = WebSocketDispatcher(
            services=self.services,
            result_sender=self.connections.send,
            result_broadcaster=self.connections.broadcast,
        )
        dispatcher.register("directive", handler, domain="chat")

        with self.assertRaisesRegex(
            ValueError,
            "already registered",
        ):
            dispatcher.register(
                "directive",
                handler,
                domain="system",
            )

    def test_unknown_message_has_a_typed_dispatch_error(self):
        with self.assertRaises(UnknownWebSocketMessageError):
            self._run_dispatch({"type": "not_registered"})

    def test_domain_handlers_receive_explicit_dependencies(self):
        for handler_class in DOMAIN_HANDLER_CLASSES:
            with self.subTest(handler=handler_class.__name__):
                parameters = inspect.signature(
                    handler_class.__init__
                ).parameters
                self.assertNotIn("services", parameters)

        for service_field in fields(ApplicationServices):
            self.assertIs(service_field.default, MISSING)
            self.assertIs(service_field.default_factory, MISSING)

    def test_messages_without_request_id_keep_the_existing_protocol(self):
        payload = json.loads(
            serialize_server_message(
                {"type": "system", "content": "ok"}
            )
        )
        self.assertEqual(
            payload,
            {"type": "system", "content": "ok"},
        )

    def _run_dispatch(self, message):
        import asyncio

        return asyncio.run(
            self.dispatcher.dispatch(
                SimpleNamespace(),
                message,
                WebSocketSessionState(),
            )
        )


class WebSocketDispatcherRuntimeTest(
    unittest.IsolatedAsyncioTestCase
):
    async def test_handler_result_preserves_request_id(self):
        connections = ConnectionManager()
        dispatcher = WebSocketDispatcher(
            services=fake_services(),
            result_sender=connections.send,
            result_broadcaster=connections.broadcast,
        )

        async def handler(context, payload):
            self.assertEqual(context.request_id, "request-42")
            self.assertEqual(payload["type"], "directive")
            return HandlerResult(
                "system",
                {"content": "completed"},
            )

        dispatcher.register("directive", handler, domain="chat")
        websocket = ScriptedWebSocket([], "unused")
        await dispatcher.dispatch(
            websocket,
            {
                "type": "directive",
                "text": "status",
                "request_id": "request-42",
            },
            WebSocketSessionState(),
        )

        self.assertEqual(
            websocket.sent,
            [
                {
                    "type": "system",
                    "content": "completed",
                    "request_id": "request-42",
                }
            ],
        )

    async def test_unknown_message_returns_normalized_error(self):
        websocket, calls = await self._run_gateway(
            [
                {
                    "type": "unknown_operation",
                    "request_id": "unknown-request",
                }
            ]
        )

        self.assertEqual(calls, [])
        self.assertIsNone(websocket.closed)
        self.assertEqual(websocket.sent[0]["type"], "system")
        self.assertIn(
            "Mensagem WebSocket invalida",
            websocket.sent[0]["content"],
        )
        self.assertEqual(
            websocket.sent[0]["request_id"],
            "unknown-request",
        )

    async def test_handler_exception_does_not_close_connection(self):
        websocket, calls = await self._run_gateway(
            [
                {"type": "directive", "text": "fail"},
                {
                    "type": "directive",
                    "text": "continue",
                    "request_id": "request-after-error",
                },
            ]
        )

        self.assertEqual(calls, ["fail", "continue"])
        self.assertIsNone(websocket.closed)
        self.assertEqual(websocket.sent[0]["type"], "system")
        self.assertEqual(
            websocket.sent[-1],
            {
                "type": "system",
                "content": "continue",
                "request_id": "request-after-error",
            },
        )

    async def _run_gateway(self, messages):
        token = "contract-test-token"
        connections = ConnectionManager()
        dispatcher = WebSocketDispatcher(
            services=fake_services(),
            result_sender=connections.send,
            result_broadcaster=connections.broadcast,
        )
        calls = []

        async def handler(_context, payload):
            text = payload.get("text")
            calls.append(text)
            if text == "fail":
                raise RuntimeError("controlled handler failure")
            return HandlerResult(
                "system",
                {"content": str(text)},
            )

        dispatcher.register("directive", handler, domain="chat")

        async def on_connect(_websocket, _session):
            return None

        gateway = WebSocketGateway(
            auth_token=token,
            connections=connections,
            dispatcher=dispatcher,
            on_connect=on_connect,
            logger=Mock(),
        )
        websocket = ScriptedWebSocket(messages, token)
        await gateway.handle_client(websocket)
        return websocket, calls


if __name__ == "__main__":
    unittest.main()
