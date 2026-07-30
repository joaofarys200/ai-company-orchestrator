"""Compatibility facade for the WebSocket dispatcher contract."""

from backend.websocket.context import (
    WebSocketHandlerContext,
    WebSocketSessionState,
)
from backend.websocket.contracts import HandlerResult, MessageHandler
from backend.websocket.dispatcher import WebSocketDispatcher

__all__ = [
    "HandlerResult",
    "MessageHandler",
    "WebSocketDispatcher",
    "WebSocketHandlerContext",
    "WebSocketSessionState",
]
