import hmac
import json
import os
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs, urlparse

import websockets

from backend.errors import safe_user_error
from backend.logging_config import log_event
from backend.message_protocol import (
    normalize_ws_message,
    system_message,
    validate_client_message,
)
from backend.websocket_dispatcher import (
    WebSocketDispatcher,
    WebSocketSessionState,
)


def resolve_under_base(base_dir: str, requested_path: str):
    base = os.path.realpath(os.path.abspath(base_dir))
    candidate = os.path.realpath(os.path.abspath(os.path.join(base, requested_path)))
    try:
        if os.path.commonpath([base, candidate]) != base:
            return None
    except ValueError:
        return None
    return candidate


def get_ws_request_path(websocket, args) -> str:
    if args:
        return args[0] or ""
    request = getattr(websocket, "request", None)
    if request is not None:
        return getattr(request, "path", "") or ""
    return getattr(websocket, "path", "") or ""


def get_ws_headers(websocket):
    request = getattr(websocket, "request", None)
    if request is not None and getattr(request, "headers", None) is not None:
        return request.headers
    return getattr(websocket, "request_headers", {}) or {}


def extract_ws_token(websocket, args) -> str:
    path = get_ws_request_path(websocket, args)
    query_token = parse_qs(urlparse(path).query).get("token", [None])[0]
    if query_token:
        return query_token

    headers = get_ws_headers(websocket)
    auth_header = headers.get("Authorization") or headers.get("authorization") or ""
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return headers.get("X-Jarvis-Token") or headers.get("x-jarvis-token") or ""


def is_ws_token_authorized(token: str, expected_token: str) -> bool:
    return bool(token) and hmac.compare_digest(token, expected_token)


def is_ws_authorized(websocket, args, expected_token: str) -> bool:
    return is_ws_token_authorized(extract_ws_token(websocket, args), expected_token)


async def reject_unauthorized_ws(websocket) -> None:
    try:
        await websocket.send(json.dumps(system_message("WebSocket authentication failed.")))
    except Exception:
        pass
    await websocket.close(code=1008, reason="Invalid local token")


def serialize_server_message(message: dict) -> str:
    return json.dumps(normalize_ws_message(message))


@dataclass(slots=True)
class ConnectionManager:
    connections: set[Any] = field(default_factory=set)

    @property
    def count(self) -> int:
        return len(self.connections)

    def connect(self, websocket: Any) -> None:
        self.connections.add(websocket)

    def disconnect(self, websocket: Any) -> None:
        self.connections.discard(websocket)

    async def send(self, websocket: Any, message: dict) -> None:
        await websocket.send(serialize_server_message(message))

    async def broadcast(self, message: dict) -> None:
        if not self.connections:
            return
        payload = serialize_server_message(message)
        for connection in list(self.connections):
            try:
                await connection.send(payload)
            except Exception:
                self.disconnect(connection)


InitialConnectionHandler = Callable[
    [Any, WebSocketSessionState],
    Awaitable[None],
]


class WebSocketGateway:
    """Own authentication, connection lifecycle and message dispatch."""

    def __init__(
        self,
        *,
        auth_token: str,
        connections: ConnectionManager,
        dispatcher: WebSocketDispatcher,
        on_connect: InitialConnectionHandler,
        logger: Any,
    ) -> None:
        self.auth_token = auth_token
        self.connections = connections
        self.dispatcher = dispatcher
        self.on_connect = on_connect
        self.logger = logger

    async def handle_client(self, websocket: Any, *args: Any) -> None:
        if not is_ws_authorized(
            websocket,
            args,
            self.auth_token,
        ):
            log_event(
                self.logger,
                "websocket.auth.rejected",
                level="warning",
            )
            await reject_unauthorized_ws(websocket)
            return

        session = WebSocketSessionState()
        self.connections.connect(websocket)
        log_event(
            self.logger,
            "websocket.client.connected",
            active_connections=self.connections.count,
        )
        try:
            await self.on_connect(websocket, session)
            async for raw_message in websocket:
                try:
                    payload = validate_client_message(
                        json.loads(raw_message)
                    )
                    await self.dispatcher.dispatch(
                        websocket,
                        payload,
                        session,
                    )
                except Exception as message_error:
                    log_event(
                        self.logger,
                        "websocket.message.parse_error",
                        level="error",
                        error=str(message_error),
                    )
                    await self.connections.send(
                        websocket,
                        system_message(
                            safe_user_error(
                                "Mensagem WebSocket invalida",
                                message_error,
                            )
                        ),
                    )
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.connections.disconnect(websocket)
            log_event(
                self.logger,
                "websocket.client.disconnected",
                active_connections=self.connections.count,
            )
