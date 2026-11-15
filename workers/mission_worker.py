"""JARVIS OS — Autonomous Missions & Governance Worker Role (`mission`).

Handles all 143 mission lifecycle, CrewAI execution, autonomous loop, contract governance,
long-horizon missions, quality governance, sentinel watchdog, and permission operations.
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
    """Register Mission/Governance/Sentinel domain RPC handlers onto the stdio server."""
    runtime = DomainWorkerRuntime("mission", project_root=project_root)
    runtime.register_on_server(server)
    return runtime
