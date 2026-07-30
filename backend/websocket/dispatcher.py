from __future__ import annotations

from typing import Any, Awaitable, Callable

from backend.application_services import ApplicationServices
from backend.websocket.context import (
    WebSocketHandlerContext,
    WebSocketSessionState,
    bind_response_request_id,
    reset_response_request_id,
    resolve_request_id,
)
from backend.websocket.contracts import HandlerResult, MessageHandler
from backend.websocket.errors import UnknownWebSocketMessageError


ResultSender = Callable[[Any, dict[str, Any]], Awaitable[None]]
ResultBroadcaster = Callable[[dict[str, Any]], Awaitable[None]]


class WebSocketDispatcher:
    """Route validated messages through one uniform handler contract."""

    def __init__(
        self,
        *,
        services: ApplicationServices,
        result_sender: ResultSender,
        result_broadcaster: ResultBroadcaster,
    ) -> None:
        self.services = services
        self.result_sender = result_sender
        self.result_broadcaster = result_broadcaster
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

    @property
    def handlers(self) -> dict[str, MessageHandler]:
        return dict(self._handlers)

    def domain_for(self, message_type: str) -> str | None:
        return self._domains.get(message_type)

    async def dispatch(
        self,
        websocket: Any,
        message: dict[str, Any],
        session: WebSocketSessionState,
    ) -> HandlerResult | None:
        message_type = str(message.get("type") or "").strip()
        handler = self._handlers.get(message_type)
        if handler is None:
            raise UnknownWebSocketMessageError(
                "Operacao WebSocket sem handler: "
                f"{message_type or 'sem type'}."
            )

        request_id, response_request_id = resolve_request_id(message)
        context = WebSocketHandlerContext(
            services=self.services,
            runtime=session,
            client=websocket,
            request_id=request_id,
        )
        token = bind_response_request_id(response_request_id)
        try:
            result = await handler(context, message)
            if result is None:
                return None
            if result.broadcast:
                await self.result_broadcaster(result.to_message())
            else:
                await self.result_sender(
                    websocket,
                    result.to_message(),
                )
            return result
        finally:
            reset_response_request_id(token)
