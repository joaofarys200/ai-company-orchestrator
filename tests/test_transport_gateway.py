"""
Tests for StdioTransportGateway and Native IPC Bridge
"""

import sys
import json
import asyncio
from backend.transport_gateway import StdioTransportGateway


class MockDispatcher:
    def __init__(self):
        self.dispatched = []

    async def dispatch(self, websocket, message, session):
        self.dispatched.append((websocket, message, session))
        # Send a response back to the virtual client
        await websocket.send({"type": "response_ok", "original": message.get("type")})


def test_stdio_gateway_handle_valid_json():
    dispatcher = MockDispatcher()
    broadcasts = []

    gateway = StdioTransportGateway(
        dispatcher=dispatcher,
        on_broadcast=lambda msg: broadcasts.append(msg),
    )

    valid_json = json.dumps({"type": "get_status", "param": 42})

    # Execute async line handler
    asyncio.run(gateway._handle_raw_line(valid_json))

    assert len(dispatcher.dispatched) == 1
    client, msg, session = dispatcher.dispatched[0]
    assert msg["type"] == "get_status"
    assert msg["param"] == 42


def test_stdio_gateway_ignores_non_json_logs():
    dispatcher = MockDispatcher()
    gateway = StdioTransportGateway(dispatcher=dispatcher)

    # Standard python log lines or empty lines
    asyncio.run(gateway._handle_raw_line("[INFO] Application started"))
    asyncio.run(gateway._handle_raw_line(""))
    asyncio.run(gateway._handle_raw_line("{not a json}"))
    asyncio.run(gateway._handle_raw_line("12345"))

    assert len(dispatcher.dispatched) == 0


def test_stdio_gateway_broadcast():
    dispatcher = MockDispatcher()
    broadcast_received = []

    gateway = StdioTransportGateway(
        dispatcher=dispatcher,
        on_broadcast=lambda msg: broadcast_received.append(msg),
    )

    test_msg = {"type": "lecture_audio_level", "level": 0.85}
    asyncio.run(gateway.broadcast(test_msg))

    assert len(broadcast_received) == 1
    assert broadcast_received[0]["type"] == "lecture_audio_level"
    assert broadcast_received[0]["level"] == 0.85


def test_connection_manager_broadcast_hooks_invokes_stdio_gateway():
    from backend.websocket.gateway import ConnectionManager

    cm = ConnectionManager()
    received_messages = []

    async def mock_hook(msg):
        received_messages.append(msg)

    cm.add_broadcast_hook(mock_hook)

    test_msg = {"type": "projects_list", "projects": [{"project_id": "dina"}]}
    asyncio.run(cm.broadcast(test_msg))

    assert len(received_messages) == 1
    assert received_messages[0]["type"] == "projects_list"
    assert received_messages[0]["projects"][0]["project_id"] == "dina"
