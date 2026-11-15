"""Decoupled runtime bridge preventing circular `import server` from agents and voice."""

from __future__ import annotations

import sys
from typing import Any, Awaitable, Callable

_broadcast_fn: Callable[[dict[str, Any]], Awaitable[None]] | None = None
_broadcast_state_fn: Callable[[str], Awaitable[None]] | None = None
_on_file_update_fn: Callable[[str, str], None] | None = None
_get_services_fn: Callable[[], Any] | None = None


def register_runtime_hooks(
    *,
    broadcast: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    broadcast_state: Callable[[str], Awaitable[None]] | None = None,
    on_file_update: Callable[[str, str], None] | None = None,
    get_application_services: Callable[[], Any] | None = None,
) -> None:
    """Register active runtime hooks for agent and voice modules without importing server.py."""
    global _broadcast_fn, _broadcast_state_fn, _on_file_update_fn, _get_services_fn
    if broadcast is not None:
        _broadcast_fn = broadcast
    if broadcast_state is not None:
        _broadcast_state_fn = broadcast_state
    if on_file_update is not None:
        _on_file_update_fn = on_file_update
    if get_application_services is not None:
        _get_services_fn = get_application_services


def _loaded_server_module() -> Any | None:
    return sys.modules.get("server")


async def emit_broadcast(message: dict[str, Any]) -> None:
    """Broadcast a structured event via active runtime hook or already-loaded compat facade."""
    if _broadcast_fn is not None:
        await _broadcast_fn(message)
        return
    server_mod = _loaded_server_module()
    if server_mod is not None and callable(getattr(server_mod, "broadcast", None)):
        await server_mod.broadcast(message)


async def emit_broadcast_state(value: str) -> None:
    """Broadcast a runtime state update via active runtime hook or already-loaded compat facade."""
    if _broadcast_state_fn is not None:
        await _broadcast_state_fn(value)
        return
    server_mod = _loaded_server_module()
    if server_mod is not None and callable(getattr(server_mod, "broadcast_state", None)):
        await server_mod.broadcast_state(value)


def emit_file_update(filename: str, content: str) -> None:
    """Emit a file update notification via active runtime hook or already-loaded compat facade."""
    if _on_file_update_fn is not None:
        _on_file_update_fn(filename, content)
        return
    server_mod = _loaded_server_module()
    if server_mod is not None and callable(getattr(server_mod, "on_file_update", None)):
        server_mod.on_file_update(filename, content)


def get_application_services() -> Any | None:
    """Resolve current ApplicationServices without importing server.py."""
    if _get_services_fn is not None:
        return _get_services_fn()
    server_mod = _loaded_server_module()
    if server_mod is not None and callable(getattr(server_mod, "_current_application_services", None)):
        return server_mod._current_application_services()
    return None
