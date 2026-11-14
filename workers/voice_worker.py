"""JARVIS OS — Voice & Audio Pipeline Worker Role (`voice`).

Handles local microphone/Whisper voice service activation and lecture audio capture pipelines.
"""

from __future__ import annotations

from pathlib import Path

from workers.common.domain_bridge import DomainWorkerRuntime
from workers.common.stdio_rpc import WorkerRpcServer


def register_worker_handlers(
    server: WorkerRpcServer,
    *,
    project_root: str | Path | None = None,
) -> DomainWorkerRuntime:
    """Register Voice/Audio domain RPC handlers onto the worker stdio server."""
    runtime = DomainWorkerRuntime("voice", project_root=project_root)
    runtime.register_on_server(server)
    return runtime
