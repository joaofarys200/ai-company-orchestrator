from __future__ import annotations

from typing import Any

from backend.errors import safe_user_error
from backend.websocket.context import WebSocketSessionState
from backend.websocket.contracts import MessageHandler
from backend.websocket.gateway import ConnectionManager
from backend.websocket.handlers import bind_handler_methods
from backend.websocket.handlers.common import WebSocketRuntimeCallbacks


VOICE_HANDLERS = {"toggle_voice": "toggle_voice"}


class VoiceWebSocketHandler:
    def __init__(
        self,
        connections: ConnectionManager,
        callbacks: WebSocketRuntimeCallbacks,
    ) -> None:
        self.connections = connections
        self.callbacks = callbacks

    def routes(self) -> dict[str, MessageHandler]:
        return bind_handler_methods(self, VOICE_HANDLERS)

    async def toggle_voice(
        self,
        websocket: Any,
        message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        voice_service = self.callbacks.get_voice_service()
        active = bool(message.get("active", False))
        if active:
            try:
                if voice_service:
                    voice_service.start()
                    await self.connections.send(
                        websocket,
                        {
                            "type": "system",
                            "content": (
                                "Reconhecimento de Voz Jarvis OS "
                                "(VAD Python) ativado no Servidor."
                            ),
                        },
                    )
                    await self.connections.broadcast(
                        {
                            "type": "voice_status",
                            "status": "idle",
                        }
                    )
                else:
                    await self.connections.send(
                        websocket,
                        {
                            "type": "system",
                            "content": (
                                "Reconhecimento de Voz está "
                                "desativado no .env "
                                "(VOICE_MODE=none)."
                            ),
                        },
                    )
            except Exception as voice_error:
                await self.connections.send(
                    websocket,
                    {
                        "type": "system",
                        "content": safe_user_error(
                            "Erro ao ativar voz",
                            voice_error,
                        ),
                    },
                )
            return

        if voice_service:
            voice_service.stop()
        await self.connections.send(
            websocket,
            {
                "type": "system",
                "content": (
                    "Reconhecimento de Voz Jarvis OS "
                    "(VAD Python) desativado."
                ),
            },
        )
        await self.connections.broadcast(
            {"type": "voice_status", "status": "offline"}
        )
