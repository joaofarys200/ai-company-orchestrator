"""End-to-end stdio JSON-RPC 2.0 tests across all 5 production Python domain workers."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

WORKER_CASES: list[tuple[str, dict[str, Any], str]] = [
    ("ai", {"type": "get_planner_state"}, "planner_state"),
    ("study", {"type": "study_list_documents"}, "study_documents_list"),
    ("knowledge", {"type": "get_queue_status"}, "queue_worker_status"),
    ("mission", {"type": "sentinel_get_status"}, "sentinel_status"),
    ("voice", {"type": "get_lecture_status"}, "lecture_status_response"),
]


def _start_pipe_reader(pipe: Any) -> tuple[queue.Queue[str | None], list[str]]:
    q: queue.Queue[str | None] = queue.Queue()
    lines: list[str] = []

    def _reader() -> None:
        try:
            if pipe is not None:
                for line in pipe:
                    lines.append(line)
                    q.put(line)
        finally:
            q.put(None)

    threading.Thread(target=_reader, daemon=True).start()
    return q, lines


def _drain_pipe(pipe: Any) -> list[str]:
    lines: list[str] = []

    def _reader() -> None:
        if pipe is not None:
            for line in pipe:
                lines.append(line)

    threading.Thread(target=_reader, daemon=True).start()
    return lines


def _read_json_line(
    q: queue.Queue[str | None],
    stderr_lines: list[str],
    timeout_s: float = 20.0,
) -> dict[str, Any]:
    while True:
        try:
            raw = q.get(timeout=timeout_s)
        except queue.Empty as exc:
            stderr_tail = "".join(stderr_lines[-20:])
            raise TimeoutError(f"Timed out waiting for worker NDJSON line; stderr={stderr_tail!r}") from exc
        if raw is None:
            stderr_tail = "".join(stderr_lines[-20:])
            raise AssertionError(f"Worker closed stdout unexpectedly; stderr={stderr_tail!r}")
        line = raw.strip()
        if not line:
            continue
        return json.loads(line)


def _rpc_send(proc: subprocess.Popen[str], req_id: str, method: str, params: dict[str, Any]) -> None:
    payload = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params,
    }
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()


def _read_until_response(
    q: queue.Queue[str | None],
    stderr_lines: list[str],
    expected_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    notifications: list[dict[str, Any]] = []
    while True:
        frame = _read_json_line(q, stderr_lines)
        if frame.get("id") == expected_id:
            return frame, notifications
        notifications.append(frame)


def _read_until_notification(
    q: queue.Queue[str | None],
    stderr_lines: list[str],
    expected_method: str,
) -> dict[str, Any]:
    while True:
        frame = _read_json_line(q, stderr_lines)
        if frame.get("method") == expected_method:
            return frame


def _unwrap_stream_event(payload: dict[str, Any]) -> dict[str, Any]:
    inner = payload.get("event")
    if isinstance(inner, dict):
        return inner
    return payload


class AllDomainWorkersE2ETests(unittest.TestCase):
    def test_all_five_workers_boot_dispatch_and_shutdown_over_stdio_ipc(self) -> None:
        with tempfile.TemporaryDirectory(prefix="jarvis_e2e_workers_") as tmp_dir:
            workspace_root = str(Path(tmp_dir).resolve())
            env = os.environ.copy()
            env["STUDY_DISABLE_LIVE_LLM"] = "1"
            env["PYTHONUTF8"] = "1"
            env["JARVIS_PROJECT_ROOT"] = workspace_root

            for role, client_message, expected_event_type in WORKER_CASES:
                with self.subTest(role=role):
                    proc = subprocess.Popen(
                        [sys.executable, "-u", "-m", "workers.worker_boot", "--worker", role],
                        cwd=str(REPO_ROOT),
                        env=env,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding="utf-8",
                    )
                    try:
                        out_q, _ = _start_pipe_reader(proc.stdout)
                        stderr_lines = _drain_pipe(proc.stderr)

                        # 1. Verify worker.ready banner on stdout
                        ready = _read_json_line(out_q, stderr_lines)
                        self.assertEqual(ready.get("method"), "worker.ready")
                        self.assertEqual(ready.get("params", {}).get("worker_type"), role)

                        # 2. Initialize & verify system.ping -> system.pong notification
                        _rpc_send(proc, f"{role}-init", "worker.init", {"workspace_root": workspace_root})
                        init_resp, _ = _read_until_response(out_q, stderr_lines, f"{role}-init")
                        self.assertEqual(init_resp.get("result", {}).get("status"), "initialized")

                        _rpc_send(proc, f"{role}-ping", "system.ping", {"sequence": 7})
                        pong = _read_until_notification(out_q, stderr_lines, "system.pong")
                        self.assertEqual(pong.get("params", {}).get("sequence"), 7)
                        self.assertIsInstance(pong.get("params", {}).get("rss_memory_mb"), (int, float))

                        # 3. Real domain dispatch with correlated request_id streamed via stream.chunk & result.events
                        req_corr = f"e2e-{role}-req-1"
                        msg = dict(client_message)
                        msg["request_id"] = req_corr
                        _rpc_send(proc, f"{role}-disp", "domain.dispatch", {"message": msg})
                        disp_resp, notes = _read_until_response(out_q, stderr_lines, f"{role}-disp")
                        self.assertIn("result", disp_resp, f"{role} error: {disp_resp!r}")

                        streamed_events: list[dict[str, Any]] = []
                        for note in notes:
                            if note.get("method") == "stream.chunk":
                                delta_raw = note.get("params", {}).get("delta", "")
                                if isinstance(delta_raw, str) and delta_raw.strip():
                                    streamed_events.append(_unwrap_stream_event(json.loads(delta_raw)))

                        matching_stream = [
                            evt
                            for evt in streamed_events
                            if evt.get("type") == expected_event_type
                            and evt.get("request_id") == req_corr
                        ]
                        self.assertTrue(
                            matching_stream,
                            f"Expected {expected_event_type} with request_id={req_corr}, got stream={streamed_events!r}",
                        )

                        result_events = disp_resp.get("result", {}).get("events", [])
                        matching_result = [
                            evt
                            for evt in result_events
                            if isinstance(evt, dict)
                            and evt.get("type") == expected_event_type
                            and evt.get("request_id") == req_corr
                        ]
                        self.assertTrue(
                            matching_result,
                            f"Expected {expected_event_type} in result.events with request_id={req_corr}, got={result_events!r}",
                        )

                        # 4. Verify stdin reader stays responsive after native extension imports
                        _rpc_send(proc, f"{role}-ping2", "system.ping", {"sequence": 8})
                        pong2 = _read_until_notification(out_q, stderr_lines, "system.pong")
                        self.assertEqual(pong2.get("params", {}).get("sequence"), 8)

                        # 5. Graceful shutdown
                        _rpc_send(proc, f"{role}-shut", "worker.shutdown", {})
                        shut_resp, _ = _read_until_response(out_q, stderr_lines, f"{role}-shut")
                        self.assertEqual(shut_resp.get("result", {}).get("status"), "shutting_down")
                        if proc.stdin is not None:
                            proc.stdin.close()
                        rc = proc.wait(timeout=10)
                        self.assertEqual(rc, 0)
                    finally:
                        if proc.poll() is None:
                            proc.kill()
                            proc.wait(timeout=5)
                        for pipe in (proc.stdin, proc.stdout, proc.stderr):
                            if pipe is not None and not pipe.closed:
                                pipe.close()


if __name__ == "__main__":
    unittest.main()
