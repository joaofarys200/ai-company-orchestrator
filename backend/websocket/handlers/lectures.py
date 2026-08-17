"""
JARVIS OS - Lecture WebSocket Handler
Processa mensagens de início/fim de gravação de aulas, consulta de status e lista de histórico.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from backend.logging_config import log_event
from backend.websocket.context import WebSocketSessionState
from backend.websocket.contracts import MessageHandler
try:
    from backend.websocket.gateway import ConnectionManager
except ImportError:
    ConnectionManager = Any
from backend.websocket.handlers import bind_handler_methods
from services.lecture_recorder import LectureRecorderService, LectureSession
from services.lecture_synthesizer import CornellNoteSynthesizer


LECTURE_HANDLERS = {
    "start_lecture_recording": "start_lecture_recording",
    "stop_lecture_recording": "stop_lecture_recording",
    "get_lecture_status": "get_lecture_status",
    "list_lecture_history": "list_lecture_history",
}


class LectureWebSocketHandler:
    def __init__(
        self,
        connections: ConnectionManager,
        logger: Any = None,
        recorder_service: Optional[LectureRecorderService] = None,
        synthesizer_service: Optional[CornellNoteSynthesizer] = None,
    ) -> None:
        self.connections = connections
        self.logger = logger
        self.recorder = recorder_service or LectureRecorderService(
            on_audio_level=self._on_audio_level,
            on_status_change=self._on_status_change,
        )
        self.synthesizer = synthesizer_service or CornellNoteSynthesizer()

    def routes(self) -> dict[str, MessageHandler]:
        return bind_handler_methods(self, LECTURE_HANDLERS)

    def _on_audio_level(self, level: float) -> None:
        """Transmite o nível de áudio em tempo real para a UI."""
        # Apenas se estiver gravando
        if self.recorder.is_recording:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    self.connections.broadcast({
                        "type": "lecture_audio_level",
                        "level": round(level, 3),
                    })
                )
            except RuntimeError:
                pass

    def _on_status_change(self, session: LectureSession) -> None:
        """Transmite alteração de estado da sessão."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                self.connections.broadcast({
                    "type": "lecture_session_update",
                    "session": session.to_dict(),
                })
            )
        except RuntimeError:
            pass

    async def start_lecture_recording(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        subject = message.get("subject", "Geral")
        title = message.get("title", "Nova Aula")
        professor = message.get("professor", "")

        try:
            session = self.recorder.start_recording(
                subject=subject,
                title=title,
                professor=professor,
            )
            if self.logger:
                log_event(self.logger, "lecture.recording.started", session_id=session.session_id)

            await self.connections.broadcast({
                "type": "lecture_recording_started",
                "session": session.to_dict(),
            })
        except Exception as e:
            await self.connections.send(websocket, {
                "type": "lecture_error",
                "message": str(e),
            })

    async def stop_lecture_recording(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        try:
            session = self.recorder.stop_recording()
            if self.logger:
                log_event(self.logger, "lecture.recording.stopped", session_id=session.session_id)

            await self.connections.broadcast({
                "type": "lecture_transcribing_started",
                "session": session.to_dict(),
            })

            # Executar transcrição e síntese em background
            asyncio.create_task(self._async_synthesize(session))

        except Exception as e:
            await self.connections.send(websocket, {
                "type": "lecture_error",
                "message": str(e),
            })

    async def _async_synthesize(self, session: LectureSession) -> None:
        """Executa a transcrição e geração de Cornell Notes de forma assíncrona."""
        try:
            loop = asyncio.get_running_loop()
            # Rodar síntese em thread pool para não bloquear o event loop
            markdown_path = await loop.run_in_executor(
                None,
                self.synthesizer.process_lecture,
                session,
            )

            await self.connections.broadcast({
                "type": "lecture_synthesis_completed",
                "session": session.to_dict(),
                "markdown_path": markdown_path,
            })
        except Exception as e:
            session.status = "FAILED"
            session.error_message = str(e)
            await self.connections.broadcast({
                "type": "lecture_error",
                "message": f"Erro na síntese da aula: {e}",
                "session": session.to_dict(),
            })

    async def get_lecture_status(
        self,
        websocket: Any,
        _message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        status_data = self.recorder.get_status()
        await self.connections.send(websocket, {
            "type": "lecture_status_response",
            **status_data,
        })

    async def list_lecture_history(
        self,
        websocket: Any,
        _message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        history = self.recorder.list_history()
        await self.connections.send(websocket, {
            "type": "lecture_history_response",
            "history": history,
        })
