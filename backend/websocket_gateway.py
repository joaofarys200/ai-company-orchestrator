import hmac
import json
import os
from urllib.parse import parse_qs, urlparse

from backend.message_protocol import normalize_ws_message, system_message


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
