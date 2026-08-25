import asyncio
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.realpath(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

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


def test_lecture_websocket_workflow(tmp_path):
    async def _run():
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

        # 4. Generate lesson directly
        await handler.generate_lecture_lesson(
            ws,
            {
                "topic": "Sistemas Multiagente e Arquiteturas RAG",
                "subject": "Inteligência Artificial",
                "professor": "Prof. JARVIS",
            },
            session_state,
        )

        assert any(m.get("type") == "lecture_lesson_generated" for m in connections.broadcasted)
        lesson_msg = next(m for m in connections.broadcasted if m.get("type") == "lecture_lesson_generated")
        assert lesson_msg["lesson"]["topic"] == "Sistemas Multiagente e Arquiteturas RAG"
        assert len(lesson_msg["lesson"]["quiz"]) >= 3

        # 5. Submit quiz
        await handler.submit_lecture_quiz(
            ws,
            {
                "topic": "Sistemas Multiagente e Arquiteturas RAG",
                "answers": {"q1": 0, "q2": 0, "q3": 0},
                "transfer_answer": "Aplicando isolamento de nós e idempotência.",
            },
            session_state,
        )

        quiz_msg = next(m for m in connections.broadcasted if m.get("type") == "lecture_quiz_evaluated")
        assert quiz_msg["type"] == "lecture_quiz_evaluated"
        assert quiz_msg["score"] == 100.0
        assert quiz_msg["transfer_passed"] is True

        # 6. List history
        await handler.list_lecture_history(ws, {}, session_state)
        history_msg = connections.sent[-1][1]
        assert history_msg["type"] == "lecture_history_response"
        assert len(history_msg["history"]) >= 1

    asyncio.run(_run())
