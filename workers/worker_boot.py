"""JARVIS OS — Specialized Python Sidecar Worker Bootstrapper.

Isolates OS fd 1 BEFORE importing heavy dependencies so stray `print()` calls or C/C++
library banners route strictly to stderr and never corrupt NDJSON JSON-RPC framing.
"""

from __future__ import annotations

import os
import sys

# Ensure repository root is importable regardless of worker invocation CWD.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from workers.common.stdio_rpc import (  # noqa: E402
    ProtocolFrameWriter,
    WorkerContext,
    WorkerRpcServer,
    isolate_protocol_stdout,
)

# Capture real NDJSON protocol stream and hijack sys.stdout -> sys.stderr immediately.
_PROTOCOL_STDOUT = isolate_protocol_stdout()

import argparse  # noqa: E402
import asyncio  # noqa: E402
import importlib  # noqa: E402


_ROLE_WORKER_MODULES = {
    "ai": "workers.ai_worker",
    "study": "workers.study_worker",
    "knowledge": "workers.knowledge_worker",
    "mission": "workers.mission_worker",
    "voice": "workers.voice_worker",
}


async def _handle_echo(ctx: WorkerContext, params: dict) -> dict:
    # Deliberately emit a print() to verify stdout hijacking routes it to stderr safely.
    print(f"[worker-echo-noise] handling request={ctx.request_id}")
    if params.get("stream"):
        batcher = ctx.create_chunk_batcher(max_chunks=2, max_delay_ms=10)
        for token in params.get("tokens", ["hello ", "tauri ", "worker"]):
            ctx.raise_if_cancelled()
            ctx.append_partial(token)
            batcher.push(token)
            await asyncio.sleep(0.005)
        batcher.flush(is_last=True)

    if params.get("require_approval"):
        decision = await ctx.request_approval(
            action=str(params.get("action") or "fs.write"),
            resource=str(params.get("resource") or "workspace/demo.txt"),
            agent_name="WorkerEchoAgent",
            security_level="medium",
            timeout_ms=int(params.get("timeout_ms") or 5000),
        )
        return {"status": "completed", "decision": decision}

    sleep_ms = int(params.get("sleep_ms") or 0)
    if sleep_ms > 0:
        steps = max(1, sleep_ms // 20)
        for idx in range(steps):
            ctx.raise_if_cancelled()
            ctx.emit_progress(
                "sleeping",
                float(idx + 1) / float(steps),
                message=f"step {idx + 1}/{steps}",
            )
            await asyncio.sleep(0.02)
        ctx.raise_if_cancelled()

    return {"status": "ok", "echo": params.get("message", "")}


async def _handle_health(_ctx: WorkerContext, _params: dict) -> dict:
    return {"status": "healthy", "pid": os.getpid()}


def build_worker_server(worker_type: str, writer: ProtocolFrameWriter) -> WorkerRpcServer:
    capabilities_map = {
        "echo": ["echo", "health", "reverse_rpc"],
        "ai": ["ollama", "model_harness", "chat", "coding", "reverse_rpc"],
        "study": ["pymupdf", "ocr", "ffmpeg", "docgen", "study_modes"],
        "knowledge": ["obsidian", "chromadb", "rag", "vault"],
        "mission": ["agents", "missions", "reverse_rpc"],
        "voice": ["whisper", "audio", "lectures", "sentinel"],
    }
    caps = capabilities_map.get(worker_type, [worker_type])
    server = WorkerRpcServer(worker_type=worker_type, capabilities=caps, writer=writer)
    server.register("system.health", _handle_health)
    server.register("worker.echo", _handle_echo)
    module_path = _ROLE_WORKER_MODULES.get(worker_type)
    if module_path is not None:
        mod = importlib.import_module(module_path)
        mod.register_worker_handlers(server)
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="JARVIS OS Python Worker Process")
    parser.add_argument(
        "--worker",
        default="echo",
        choices=["echo", "ai", "study", "knowledge", "mission", "voice"],
        help="Worker pool role identifier",
    )
    args = parser.parse_args(argv)

    writer = ProtocolFrameWriter(_PROTOCOL_STDOUT)
    server = build_worker_server(args.worker, writer)
    try:
        asyncio.run(server.serve())
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

