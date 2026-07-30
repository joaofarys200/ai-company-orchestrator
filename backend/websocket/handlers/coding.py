from __future__ import annotations

import asyncio
from typing import Any

from backend.message_protocol import system_message
from backend.websocket.context import WebSocketSessionState
from backend.websocket.contracts import MessageHandler
from backend.websocket.handlers import bind_handler_methods
from backend.websocket.handlers.common import WebSocketResponder
from intelligence.coding_session import CodingSessionError
from intelligence.project_context import ProjectContextError


CODING_HANDLERS = {
    "create_coding_session": "create_session",
    "apply_coding_session": "apply_session",
    "rollback_coding_session": "rollback_session",
    "get_coding_session": "get_session",
}


class CodingSessionWebSocketHandler:
    def __init__(
        self,
        coding_sessions: Any,
        responder: WebSocketResponder,
    ) -> None:
        self.coding_sessions = coding_sessions
        self.responder = responder
        self.connections = responder.connections

    def routes(self) -> dict[str, MessageHandler]:
        return bind_handler_methods(self, CODING_HANDLERS)

    async def create_session(
        self,
        websocket: Any,
        message: dict,
        session: WebSocketSessionState,
    ) -> None:
        project_id = (
            message.get("project_id")
            or session.selected_project_id
        )
        objective = str(message.get("objective") or "").strip()
        if not project_id or not objective:
            await self.connections.send(
                websocket,
                system_message(
                    "Selecione um projeto e indique o objetivo "
                    "da alteracao."
                ),
            )
            return
        try:
            coding_session = (
                await self.coding_sessions
                .create_assisted_session(project_id, objective)
            )
            session.selected_project_id = project_id
            await self.connections.send(
                websocket,
                {
                    "type": "coding_session",
                    "data": coding_session.to_dict(),
                },
            )
        except (
            CodingSessionError,
            ProjectContextError,
        ) as coding_error:
            await self.connections.send(
                websocket,
                system_message(str(coding_error)),
            )

    async def apply_session(
        self,
        websocket: Any,
        message: dict,
        session: WebSocketSessionState,
    ) -> None:
        project_id = (
            message.get("project_id")
            or session.selected_project_id
        )
        try:
            coding_session = await asyncio.to_thread(
                self.coding_sessions.apply_session,
                project_id,
                message.get("session_id"),
            )
            await self.connections.send(
                websocket,
                {
                    "type": "coding_session",
                    "data": coding_session.to_dict(),
                },
            )
            await self.responder.send_project_context(
                websocket,
                project_id,
            )
        except (
            CodingSessionError,
            ProjectContextError,
        ) as coding_error:
            await self.connections.send(
                websocket,
                system_message(str(coding_error)),
            )

    async def rollback_session(
        self,
        websocket: Any,
        message: dict,
        session: WebSocketSessionState,
    ) -> None:
        project_id = (
            message.get("project_id")
            or session.selected_project_id
        )
        try:
            coding_session = await asyncio.to_thread(
                self.coding_sessions.rollback_session,
                project_id,
                message.get("session_id"),
                bool(message.get("confirmed")),
            )
            await self.connections.send(
                websocket,
                {
                    "type": "coding_session",
                    "data": coding_session.to_dict(),
                },
            )
            await self.responder.send_project_context(
                websocket,
                project_id,
            )
        except (
            CodingSessionError,
            ProjectContextError,
        ) as coding_error:
            await self.connections.send(
                websocket,
                system_message(str(coding_error)),
            )

    async def get_session(
        self,
        websocket: Any,
        message: dict,
        session: WebSocketSessionState,
    ) -> None:
        project_id = (
            message.get("project_id")
            or session.selected_project_id
        )
        if project_id:
            await self.responder.send_latest_coding_session(
                websocket,
                project_id,
            )
