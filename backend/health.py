from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _component(name: str, ok: bool, **details: Any) -> dict[str, Any]:
    return {
        "name": name,
        "ok": bool(ok),
        "checked_at": _utc_now(),
        "details": details,
    }


def check_backend_runtime(project_root: str) -> dict[str, Any]:
    return _component(
        "backend",
        True,
        pid=os.getpid(),
        python=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        workspace=os.path.basename(os.path.abspath(project_root)),
    )


def check_websocket_gateway(host: str, port: int, active_connections_count: int) -> dict[str, Any]:
    return _component(
        "websocket",
        host == "127.0.0.1" and int(port) > 0,
        host=host,
        port=int(port),
        active_connections=int(active_connections_count),
        local_only=(host == "127.0.0.1"),
    )


def check_frontend_static(project_root: str, port: int = 8000) -> dict[str, Any]:
    dist_dir = os.path.join(project_root, "frontend", "dist")
    index_path = os.path.join(dist_dir, "index.html")
    return _component(
        "frontend_static",
        os.path.isdir(dist_dir) and os.path.isfile(index_path),
        port=int(port),
        dist_exists=os.path.isdir(dist_dir),
        index_exists=os.path.isfile(index_path),
    )


def check_sandbox_runtime(sandbox_dir: str, port: int) -> dict[str, Any]:
    index_path = os.path.join(sandbox_dir, "index.html")
    return _component(
        "sandbox",
        os.path.isdir(sandbox_dir),
        port=int(port),
        sandbox_exists=os.path.isdir(sandbox_dir),
        index_exists=os.path.isfile(index_path),
    )


def build_health_snapshot(websocket_host: str, websocket_port: int, active_connections_count: int) -> dict:
    return {
        "websocket_host": websocket_host,
        "websocket_port": websocket_port,
        "active_connections": active_connections_count,
        "websocket": check_websocket_gateway(websocket_host, websocket_port, active_connections_count),
    }


def build_local_health_report(
    project_root: str,
    websocket_host: str,
    websocket_port: int,
    active_connections_count: int,
    sandbox_dir: str,
    sandbox_port: int,
    frontend_port: int = 8000,
) -> dict[str, Any]:
    components = [
        check_backend_runtime(project_root),
        check_websocket_gateway(websocket_host, websocket_port, active_connections_count),
        check_sandbox_runtime(sandbox_dir, sandbox_port),
        check_frontend_static(project_root, frontend_port),
    ]
    return {
        "status": "ok" if all(component["ok"] for component in components) else "degraded",
        "checked_at": _utc_now(),
        "components": components,
    }
