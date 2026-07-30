from backend.message_protocol import WebSocketPayloadError


class WebSocketDispatchError(WebSocketPayloadError):
    """Base error for a message rejected at the dispatch boundary."""


class UnknownWebSocketMessageError(WebSocketDispatchError):
    """Raised when a validated operation has no registered handler."""
