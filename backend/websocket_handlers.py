"""Compatibility facade for the domain-split WebSocket handlers."""

from backend.websocket.handlers.chat import ChatWebSocketHandler
from backend.websocket.handlers.coding import (
    CodingSessionWebSocketHandler,
)
from backend.websocket.handlers.common import (
    InitialSyncHandler,
    WebSocketResponder,
    WebSocketRuntimeCallbacks,
    notes_from_output,
)
from backend.websocket.handlers.knowledge import (
    KnowledgeWebSocketHandler,
)
from backend.websocket.handlers.missions import (
    MissionWebSocketHandler,
    message_type,
)
from backend.websocket.handlers.projects import ProjectWebSocketHandler
from backend.websocket.handlers.sentinel import SentinelWebSocketHandler
from backend.websocket.handlers.system import SystemWebSocketHandler
from backend.websocket.handlers.voice import VoiceWebSocketHandler
from backend.websocket.registry import create_websocket_handlers

_notes_from_output = notes_from_output

__all__ = [
    "ChatWebSocketHandler",
    "CodingSessionWebSocketHandler",
    "InitialSyncHandler",
    "KnowledgeWebSocketHandler",
    "MissionWebSocketHandler",
    "ProjectWebSocketHandler",
    "SentinelWebSocketHandler",
    "SystemWebSocketHandler",
    "VoiceWebSocketHandler",
    "WebSocketResponder",
    "WebSocketRuntimeCallbacks",
    "create_websocket_handlers",
    "message_type",
]
