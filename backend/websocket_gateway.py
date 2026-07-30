"""Compatibility facade for the WebSocket transport gateway."""

from backend.websocket.gateway import (
    ConnectionManager,
    InitialConnectionHandler,
    WebSocketGateway,
    extract_ws_token,
    get_ws_headers,
    get_ws_request_path,
    is_ws_authorized,
    is_ws_token_authorized,
    reject_unauthorized_ws,
    resolve_under_base,
    serialize_server_message,
)

__all__ = [
    "ConnectionManager",
    "InitialConnectionHandler",
    "WebSocketGateway",
    "extract_ws_token",
    "get_ws_headers",
    "get_ws_request_path",
    "is_ws_authorized",
    "is_ws_token_authorized",
    "reject_unauthorized_ws",
    "resolve_under_base",
    "serialize_server_message",
]
