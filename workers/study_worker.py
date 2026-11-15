"""JARVIS OS — Study & Lecture Document Worker Role (`study`).

Handles Study Engine document parsing (PyMuPDF/OCR), Cornell notes, flashcards, quizzes,
video intelligence, study coordination, and lecture synthesis/lesson generation.
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
    """Register Study/Lecture domain RPC handlers onto the worker stdio server."""
    runtime = DomainWorkerRuntime("study", project_root=project_root)
    runtime.register_on_server(server)
    return runtime
