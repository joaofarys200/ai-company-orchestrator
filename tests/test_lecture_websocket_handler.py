import asyncio
try:
    import pytest
except ImportError:
    pytest = None
from backend.websocket.context import WebSocketSessionState
from backend.websocket.handlers.lectures import LectureWebSocketHandler
from services.lecture_recorder import LectureRecorderService
from services.lecture_synthesizer import CornellNoteSynthesizer


class MockWebSocket:
    def __init__(self):
        self.sent_messages = []

    async def send(self, message):
        self.sent_messages.append(message)


class MockConnectionManager:
    def __init__(self):
        self.sent = []
        self.broadcasted = []

    async def send(self, websocket, message):
        self.sent.append((websocket, message))

    async def broadcast(self, message):
        self.broadcasted.append(message)


async def test_lecture_websocket_workflow(tmp_path):
    connections = MockConnectionManager()
    recorder = LectureRecorderService(output_dir=str(tmp_path / "audio"))
    synthesizer = CornellNoteSynthesizer(vault_root=str(tmp_path / "vault"))

    handler = LectureWebSocketHandler(
        connections=connections,
        recorder_service=recorder,
        synthesizer_service=synthesizer,
    )

    ws = MockWebSocket()
    session_state = WebSocketSessionState()

    # 1. Start recording
    await handler.start_lecture_recording(
        ws,
        {"subject": "Redes de Computadores", "title": "Protocolos TCP e UDP", "professor": "Prof. Lima"},
        session_state,
    )

    assert recorder.is_recording
    assert len(connections.broadcasted) >= 1
    assert connections.broadcasted[0]["type"] == "lecture_recording_started"
    assert connections.broadcasted[0]["session"]["subject"] == "Redes de Computadores"

    # 2. Get status
    await handler.get_lecture_status(ws, {}, session_state)
    assert len(connections.sent) >= 1
    status_msg = connections.sent[0][1]
    assert status_msg["type"] == "lecture_status_response"
    assert status_msg["is_recording"] is True

    # 3. Stop recording
    await handler.stop_lecture_recording(ws, {}, session_state)
    assert not recorder.is_recording

    # Allow async synthesis task to run
    await asyncio.sleep(0.2)

    # 4. List history
    await handler.list_lecture_history(ws, {}, session_state)
    assert len(connections.sent) >= 2
    history_msg = connections.sent[-1][1]
    assert history_msg["type"] == "lecture_history_response"
    assert len(history_msg["history"]) == 1
