from __future__ import annotations

from typing import Any, Awaitable, Callable, Mapping

from backend.websocket.context import (
    WebSocketHandlerContext,
    WebSocketSessionState,
)
from backend.websocket.contracts import MessageHandler


DomainMethod = Callable[
    [Any, dict[str, Any], WebSocketSessionState],
    Awaitable[None],
]


def bind_handler(method: DomainMethod) -> MessageHandler:
    async def handle_message(
        context: WebSocketHandlerContext,
        payload: dict[str, Any],
    ):
        await method(
            context.client,
            payload,
            context.runtime,
        )
        return None

    handle_message.__name__ = method.__name__
    handle_message.__qualname__ = method.__qualname__
    return handle_message


def bind_handler_methods(
    owner: Any,
    handler_methods: Mapping[str, str],
) -> dict[str, MessageHandler]:
    return {
        message_type: bind_handler(getattr(owner, method_name))
        for message_type, method_name in handler_methods.items()
    }


__all__ = ["bind_handler", "bind_handler_methods"]
