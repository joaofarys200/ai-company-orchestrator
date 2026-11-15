"""JARVIS OS — Knowledge & Obsidian Vault Worker Role (`knowledge`).

Handles Obsidian vault note listing/reading/saving, quality audits, enrichment, rollback,
improvement queue batches, and compounding rules/architecture/decisions synchronization.
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
    """Register Knowledge/Obsidian domain RPC handlers onto the worker stdio server."""
    runtime = DomainWorkerRuntime("knowledge", project_root=project_root)
    runtime.register_on_server(server)
    return runtime
