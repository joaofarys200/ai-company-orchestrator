"""JARVIS OS — AI & Coding Worker Role (`ai`).

Handles LLM/Ollama execution (`ModelExecutionService` + `ModelHarness`), chat directives,
coding sessions, project file/AST workflows, and planner/AST state RPCs.
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
    """Register AI/Coding domain RPC handlers onto the worker stdio server."""
    runtime = DomainWorkerRuntime("ai", project_root=project_root)
    runtime.register_on_server(server)
    return runtime
