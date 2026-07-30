from __future__ import annotations

from typing import Any

from backend.websocket.context import WebSocketSessionState
from backend.websocket.contracts import MessageHandler
from backend.websocket.gateway import ConnectionManager
from backend.websocket.handlers import bind_handler_methods
from backend.websocket.handlers.common import WebSocketRuntimeCallbacks


SYSTEM_HANDLERS = {
    "get_planner_state": "get_planner_state",
    "get_ast_state": "get_ast_state",
}


class SystemWebSocketHandler:
    def __init__(
        self,
        project_context: Any,
        connections: ConnectionManager,
        callbacks: WebSocketRuntimeCallbacks,
    ) -> None:
        self.project_context = project_context
        self.connections = connections
        self.callbacks = callbacks

    def routes(self) -> dict[str, MessageHandler]:
        return bind_handler_methods(self, SYSTEM_HANDLERS)

    async def get_planner_state(
        self,
        websocket: Any,
        _message: dict,
        _session: WebSocketSessionState,
    ) -> None:
        await self.connections.send(
            websocket,
            {
                "type": "planner_state",
                "data": (
                    self.callbacks.read_persistent_plan_state()
                ),
            },
        )

    async def get_ast_state(
        self,
        websocket: Any,
        message: dict,
        session: WebSocketSessionState,
    ) -> None:
        project_id = (
            message.get("project_id")
            or session.selected_project_id
        )
        ast_data = (
            self.project_context.load_index(project_id)
            if project_id
            else {}
        )
        await self.connections.send(
            websocket,
            {
                "type": "ast_state",
                "data": ast_data or None,
            },
        )
