from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from backend.application_services import ApplicationServices


_response_request_id: ContextVar[str | None] = ContextVar(
    "websocket_response_request_id",
    default=None,
)


@dataclass(slots=True)
class WebSocketSessionState:
    selected_project_id: str | None = None


@dataclass(frozen=True, slots=True)
class WebSocketHandlerContext:
    services: "ApplicationServices"
    runtime: WebSocketSessionState
    client: Any
    request_id: str


def resolve_request_id(message: dict[str, Any]) -> tuple[str, str | None]:
    supplied = str(message.get("request_id") or "").strip()
    return supplied or uuid4().hex, supplied or None


def bind_response_request_id(request_id: str | None) -> Token:
    return _response_request_id.set(request_id)


def reset_response_request_id(token: Token) -> None:
    _response_request_id.reset(token)


def current_response_request_id() -> str | None:
    return _response_request_id.get()
