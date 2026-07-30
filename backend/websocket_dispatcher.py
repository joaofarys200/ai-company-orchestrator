from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from backend.message_protocol import WebSocketPayloadError


@dataclass(slots=True)
class WebSocketSessionState:
    selected_project_id: str | None = None


MessageHandler = Callable[
    [Any, dict[str, Any], WebSocketSessionState],
    Awaitable[None],
]


class WebSocketDispatcher:
    """Explicit message-type to handler routing."""

    def __init__(self) -> None:
        self._handlers: dict[str, MessageHandler] = {}
        self._domains: dict[str, str] = {}

    def register(
        self,
        message_type: str,
        handler: MessageHandler,
        *,
        domain: str,
    ) -> None:
        if not message_type:
            raise ValueError("message_type cannot be empty")
        if message_type in self._handlers:
            raise ValueError(
                f"Handler already registered for {message_type}."
            )
        self._handlers[message_type] = handler
        self._domains[message_type] = domain

    def register_many(
        self,
        handlers: dict[str, MessageHandler],
        *,
        domain: str,
    ) -> None:
        for message_type, handler in handlers.items():
            self.register(message_type, handler, domain=domain)

    @property
    def message_types(self) -> frozenset[str]:
        return frozenset(self._handlers)

    def domain_for(self, message_type: str) -> str | None:
        return self._domains.get(message_type)

    async def dispatch(
        self,
        websocket: Any,
        message: dict[str, Any],
        session: WebSocketSessionState,
    ) -> None:
        message_type = str(message.get("type") or "").strip()
        handler = self._handlers.get(message_type)
        if handler is None:
            raise WebSocketPayloadError(
                f"Operacao WebSocket sem handler: "
                f"{message_type or 'sem type'}."
            )
        await handler(websocket, message, session)
