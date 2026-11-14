"""Tests for Increment 3.4 specialized Python domain workers (`ai`, `study`, `knowledge`, `mission`, `voice`)."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.websocket.context import WebSocketSessionState
from backend.websocket.dispatcher import WebSocketDispatcher
from backend.websocket.gateway import ConnectionManager
from workers.common.domain_bridge import WORKER_ROLE_DOMAINS, DomainWorkerRuntime
from workers.common.stdio_rpc import ProtocolFrameWriter, WorkerContext


class _RecordingStream:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, data: str) -> None:
        for line in data.splitlines():
            if line.strip():
                self.lines.append(line)

    def flush(self) -> None:
        return None


def _fake_ctx(request_id: str = "req-test-1") -> tuple[WorkerContext, _RecordingStream]:
    stream = _RecordingStream()
    writer = ProtocolFrameWriter(stream)  # type: ignore[arg-type]

    class _FakeServer:
        def __init__(self, w: ProtocolFrameWriter) -> None:
            self.writer = w

    active_task = SimpleNamespace(
        request_id=request_id,
        cancel_event=asyncio.Event(),
        cancel_reason=None,
        partial_parts=[],
    )
    ctx = WorkerContext(
        request_id=request_id,
        server=_FakeServer(writer),  # type: ignore[arg-type]
        active_task=active_task,
    )
    return ctx, stream


class DomainWorkersPhase3Tests(unittest.TestCase):
    def test_all_domain_worker_subprocesses_boot_and_isolate_stdout(self) -> None:
        boot_script = REPO_ROOT / "workers" / "worker_boot.py"
        for role in ("ai", "study", "knowledge", "mission", "voice"):
            with self.subTest(role=role):
                proc = subprocess.Popen(
                    [sys.executable, str(boot_script), "--worker", role],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                )
                try:
                    assert proc.stdin is not None
                    assert proc.stdout is not None
                    ready_line = proc.stdout.readline()
                    self.assertTrue(ready_line, f"{role} worker produced no ready line")
                    ready = json.loads(ready_line)
                    self.assertEqual(ready["method"], "worker.ready")
                    self.assertEqual(ready["params"]["worker_type"], role)

                    # Send worker.init, system.health, and worker.shutdown sequentially over JSON-RPC
                    responses = []
                    for idx, (method, params) in enumerate(
                        [
                            ("worker.init", {"workspace_root": str(REPO_ROOT)}),
                            ("system.health", {}),
                            ("worker.shutdown", {}),
                        ],
                        start=1,
                    ):
                        proc.stdin.write(
                            json.dumps(
                                {
                                    "jsonrpc": "2.0",
                                    "id": f"r-{role}-{idx}",
                                    "method": method,
                                    "params": params,
                                }
                            )
                            + "\n"
                        )
                        proc.stdin.flush()
                        reply_line = proc.stdout.readline()
                        self.assertTrue(reply_line, f"{role} worker gave no reply for {method}")
                        responses.append(json.loads(reply_line))
                    proc.stdin.close()

                    rc = proc.wait(timeout=10)
                    self.assertEqual(rc, 0)
                    by_id = {frame.get("id"): frame for frame in responses if "id" in frame}
                    self.assertEqual(by_id[f"r-{role}-1"]["result"]["status"], "initialized")
                    self.assertEqual(by_id[f"r-{role}-2"]["result"]["status"], "healthy")
                    self.assertEqual(by_id[f"r-{role}-3"]["result"]["status"], "shutting_down")
                finally:
                    if proc.poll() is None:
                        proc.kill()
                        proc.wait(timeout=5)

    def test_domain_bridge_streams_events_and_preserves_request_id(self) -> None:
        connections = ConnectionManager()
        dispatcher = WebSocketDispatcher(
            services=SimpleNamespace(),
            result_sender=connections.send,
            result_broadcaster=connections.broadcast,
        )

        async def _fake_study_list(ctx, _msg) -> None:
            await connections.send(
                ctx.client,
                {
                    "type": "study_documents_list",
                    "documents": [{"document_id": "doc_1", "title": "Clean Architecture"}],
                },
            )
            await connections.broadcast({"type": "study_progress_updated", "document_id": "doc_1", "progress": 0.5})

        dispatcher.register("study_list_documents", _fake_study_list, domain="study")

        runtime = DomainWorkerRuntime("study", dispatcher=dispatcher, connections=connections)

        async def _run() -> None:
            ctx, stream = _fake_ctx("corr-study-42")
            result = await runtime.rpc_domain_dispatch(
                ctx,
                {
                    "message": {
                        "type": "study_list_documents",
                        "request_id": "corr-study-42",
                    }
                },
            )
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["worker_type"], "study")
            self.assertEqual(result["events_emitted"], 2)
            self.assertEqual(len(stream.lines), 2)

            streamed_events = [
                json.loads(json.loads(line)["params"]["delta"])["event"]
                for line in stream.lines
            ]
            self.assertEqual(streamed_events[0]["type"], "study_documents_list")
            self.assertEqual(streamed_events[0]["request_id"], "corr-study-42")
            self.assertEqual(streamed_events[1]["type"], "study_progress_updated")
            self.assertEqual(streamed_events[1]["request_id"], "corr-study-42")

        asyncio.run(_run())

    def test_domain_bridge_validates_invalid_messages_cleanly(self) -> None:
        connections = ConnectionManager()
        dispatcher = WebSocketDispatcher(
            services=SimpleNamespace(),
            result_sender=connections.send,
            result_broadcaster=connections.broadcast,
        )
        runtime = DomainWorkerRuntime("study", dispatcher=dispatcher, connections=connections)

        async def _run() -> None:
            ctx, stream = _fake_ctx("corr-invalid-1")
            result = await runtime.rpc_domain_dispatch(
                ctx,
                {
                    "message": {
                        "type": "study_nonexistent_op",
                        "request_id": "corr-invalid-1",
                    }
                },
            )
            self.assertEqual(result["status"], "validation_error")
            self.assertEqual(result["events_emitted"], 1)
            event = json.loads(json.loads(stream.lines[0])["params"]["delta"])["event"]
            self.assertEqual(event["type"], "study_error")
            self.assertEqual(event["request_id"], "corr-invalid-1")

        asyncio.run(_run())

    def test_study_worker_real_study_service_dispatch_in_isolated_temp_dir(self) -> None:
        import tempfile

        async def _run() -> None:
            ctx, stream = _fake_ctx("corr-real-study")
            with tempfile.TemporaryDirectory() as tmp:
                runtime = DomainWorkerRuntime("study", project_root=tmp)
                result = await runtime.rpc_domain_dispatch(
                    ctx,
                    {
                        "message": {
                            "type": "study_list_documents",
                            "request_id": "corr-real-study",
                        }
                    },
                )
                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["events_emitted"], 1)
                event = json.loads(json.loads(stream.lines[0])["params"]["delta"])["event"]
                self.assertEqual(event["type"], "study_documents_list")
                self.assertEqual(event["documents"], [])
                self.assertEqual(event["request_id"], "corr-real-study")

        asyncio.run(_run())

    def test_worker_role_domains_map_covers_all_production_roles(self) -> None:
        self.assertEqual(
            set(WORKER_ROLE_DOMAINS.keys()),
            {"ai", "study", "knowledge", "mission", "voice"},
        )


if __name__ == "__main__":
    unittest.main()
