from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import io
import json
import os
import sys
import threading
import time
import traceback
from typing import Any, Awaitable, Callable, TextIO
import uuid


PROTOCOL_VERSION = "1.0.0"
MAX_FRAME_BYTES = 16 * 1024 * 1024  # 16 MiB

ERROR_PARSE = -32700
ERROR_INVALID_REQUEST = -32600
ERROR_METHOD_NOT_FOUND = -32601
ERROR_INTERNAL = -32603
ERROR_CANCELLED = -32000
ERROR_MODEL_UNAVAILABLE = -32001

RpcHandler = Callable[["WorkerContext", dict[str, Any]], Awaitable[Any]]


class TaskCancelledError(asyncio.CancelledError):
    """Raised when a worker task observes cooperative cancellation from Rust Core."""


def _now_ms() -> int:
    return int(time.time() * 1000)


def _current_rss_mb() -> float:
    try:
        import psutil  # type: ignore

        return round(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024), 2)
    except Exception:
        return 0.0


def isolate_protocol_stdout(injected_stream: TextIO | None = None) -> TextIO:
    """Duplicate genuine fd 1 for NDJSON IPC and redirect sys.stdout to sys.stderr.

    Must run before third-party library imports so rogue C/Python stdout logs never corrupt
    NDJSON message framing.
    """
    if injected_stream is not None:
        return injected_stream

    real_stdout_fd = os.dup(1)
    protocol_stream = os.fdopen(
        real_stdout_fd,
        "w",
        buffering=1,
        encoding="utf-8",
        errors="replace",
        newline="\n",
    )
    sys.stdout = sys.stderr
    return protocol_stream


class ProtocolFrameWriter:
    """Thread-safe NDJSON JSON-RPC 2.0 frame writer with strict 16 MiB frame limit."""

    def __init__(self, stream: TextIO, *, max_frame_bytes: int = MAX_FRAME_BYTES) -> None:
        self._stream = stream
        self._max_frame_bytes = max_frame_bytes
        self._lock = threading.Lock()

    def write_frame(self, payload: dict[str, Any]) -> None:
        envelope = {
            "jsonrpc": "2.0",
            "protocol_version": PROTOCOL_VERSION,
            **payload,
            "timestamp": payload.get("timestamp", _now_ms()),
        }
        encoded = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
        raw_bytes = encoded.encode("utf-8")
        if len(raw_bytes) > self._max_frame_bytes:
            raise ValueError(
                f"Protocol frame byte length {len(raw_bytes)} exceeds limit {self._max_frame_bytes}"
            )
        with self._lock:
            self._stream.write(encoded + "\n")
            self._stream.flush()

    def send_ready(self, worker_type: str, capabilities: list[str] | None = None) -> None:
        self.write_frame(
            {
                "method": "worker.ready",
                "params": {
                    "worker_type": worker_type,
                    "pid": os.getpid(),
                    "version": PROTOCOL_VERSION,
                    "capabilities": capabilities or [],
                },
            }
        )

    def send_response(self, request_id: str, result: Any) -> None:
        self.write_frame({"id": request_id, "result": result})

    def send_error(
        self,
        request_id: str | None,
        code: int,
        message: str,
        *,
        data: dict[str, Any] | None = None,
    ) -> None:
        err_obj: dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            err_obj["data"] = data
        self.write_frame({"id": request_id, "error": err_obj})

    def send_stream_chunk(
        self,
        request_id: str,
        sequence: int,
        delta: str,
        *,
        is_last: bool = False,
    ) -> None:
        self.write_frame(
            {
                "method": "stream.chunk",
                "params": {
                    "request_id": request_id,
                    "sequence": sequence,
                    "delta": delta,
                    "is_last": is_last,
                },
            }
        )

    def send_progress(
        self,
        request_id: str,
        stage: str,
        progress: float,
        *,
        message: str = "",
        eta_seconds: float | None = None,
    ) -> None:
        params: dict[str, Any] = {
            "request_id": request_id,
            "stage": stage,
            "progress": max(0.0, min(1.0, float(progress))),
            "message": message,
        }
        if eta_seconds is not None:
            params["eta_seconds"] = float(eta_seconds)
        self.write_frame({"method": "task.progress", "params": params})

    def send_reverse_request(
        self,
        reverse_id: str,
        method: str,
        params: dict[str, Any],
    ) -> None:
        self.write_frame(
            {
                "id": reverse_id,
                "type": "reverse_request",
                "method": method,
                "params": params,
            }
        )

    def send_pong(self, sequence: int, active_tasks: int) -> None:
        self.write_frame(
            {
                "method": "system.pong",
                "params": {
                    "sequence": sequence,
                    "rss_memory_mb": _current_rss_mb(),
                    "active_tasks": active_tasks,
                },
            }
        )


class StreamChunkBatcher:
    """Micro-batches fast token deltas (16 ms or >= 3 chunks) before emitting NDJSON frames."""

    def __init__(
        self,
        writer: ProtocolFrameWriter,
        request_id: str,
        *,
        max_chunks: int = 3,
        max_delay_ms: float = 16.0,
    ) -> None:
        self._writer = writer
        self._request_id = request_id
        self._max_chunks = max(1, max_chunks)
        self._max_delay_s = max(0.001, max_delay_ms / 1000.0)
        self._buf: list[str] = []
        self._sequence = 0
        self._last_flush = time.monotonic()

    def push(self, delta: str) -> None:
        if not delta:
            return
        self._buf.append(delta)
        elapsed = time.monotonic() - self._last_flush
        if len(self._buf) >= self._max_chunks or elapsed >= self._max_delay_s:
            self.flush(is_last=False)

    def flush(self, *, is_last: bool = False) -> None:
        if not self._buf and not is_last:
            return
        joined = "".join(self._buf)
        self._buf.clear()
        self._last_flush = time.monotonic()
        self._writer.send_stream_chunk(
            self._request_id,
            self._sequence,
            joined,
            is_last=is_last,
        )
        self._sequence += 1


@dataclass
class _ActiveTask:
    request_id: str
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    cancel_reason: str | None = None
    partial_parts: list[str] = field(default_factory=list)


class WorkerContext:
    """Execution context exposed to each Python worker RPC handler."""

    def __init__(
        self,
        *,
        request_id: str,
        server: "WorkerRpcServer",
        active_task: _ActiveTask,
    ) -> None:
        self.request_id = request_id
        self._server = server
        self._active_task = active_task

    @property
    def cancel_event(self) -> asyncio.Event:
        return self._active_task.cancel_event

    @property
    def is_cancelled(self) -> bool:
        return self._active_task.cancel_event.is_set()

    def raise_if_cancelled(self) -> None:
        if self._active_task.cancel_event.is_set():
            raise TaskCancelledError(self._active_task.cancel_reason or "user_cancelled")

    def append_partial(self, delta: str) -> None:
        if delta:
            self._active_task.partial_parts.append(delta)

    def stream_chunk(self, sequence: int, delta: str, *, is_last: bool = False) -> None:
        self.append_partial(delta)
        self._server.writer.send_stream_chunk(
            self.request_id,
            sequence,
            delta,
            is_last=is_last,
        )

    def create_chunk_batcher(
        self, *, max_chunks: int = 3, max_delay_ms: float = 16.0
    ) -> StreamChunkBatcher:
        return StreamChunkBatcher(
            self._server.writer,
            self.request_id,
            max_chunks=max_chunks,
            max_delay_ms=max_delay_ms,
        )

    def emit_progress(
        self,
        stage: str,
        progress: float,
        *,
        message: str = "",
        eta_seconds: float | None = None,
    ) -> None:
        self._server.writer.send_progress(
            self.request_id,
            stage,
            progress,
            message=message,
            eta_seconds=eta_seconds,
        )

    async def request_approval(
        self,
        *,
        action: str,
        resource: str,
        agent_name: str = "",
        security_level: str = "medium",
        timeout_ms: int = 60_000,
    ) -> dict[str, Any]:
        """Issue non-blocking Reverse RPC HITL request without stalling the reader loop."""
        return await self._server.send_reverse_request(
            "permission.request_approval",
            {
                "parent_task_id": self.request_id,
                "action": action,
                "resource": resource,
                "agent_name": agent_name,
                "security_level": security_level,
                "timeout_ms": timeout_ms,
            },
            timeout_ms=timeout_ms,
        )


class WorkerRpcServer:
    """Bidirectional NDJSON JSON-RPC 2.0 server with Reverse RPC and Windows-safe stdin reader."""

    def __init__(
        self,
        *,
        worker_type: str,
        capabilities: list[str] | None = None,
        writer: ProtocolFrameWriter,
        stdin_stream: TextIO | None = None,
    ) -> None:
        self.worker_type = worker_type
        self.capabilities = list(capabilities or [])
        self.writer = writer
        self._stdin = stdin_stream if stdin_stream is not None else sys.stdin
        self._handlers: dict[str, RpcHandler] = {}
        self._active_tasks: dict[str, _ActiveTask] = {}
        self._reverse_futures: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._config: dict[str, Any] = {}
        self._initialized = False
        self._loop: asyncio.AbstractEventLoop | None = None

        self.register("worker.init", self._handle_worker_init)

    def register(self, method: str, handler: RpcHandler) -> None:
        self._handlers[method] = handler

    async def _handle_worker_init(
        self, _ctx: WorkerContext, params: dict[str, Any]
    ) -> dict[str, Any]:
        self._config = dict(params or {})
        self._initialized = True
        return {
            "status": "initialized",
            "worker_type": self.worker_type,
            "capabilities": self.capabilities,
        }

    async def send_reverse_request(
        self,
        method: str,
        params: dict[str, Any],
        *,
        timeout_ms: int = 60_000,
    ) -> dict[str, Any]:
        assert self._loop is not None
        reverse_id = f"rev-{uuid.uuid4().hex[:12]}"
        fut: asyncio.Future[dict[str, Any]] = self._loop.create_future()
        self._reverse_futures[reverse_id] = fut
        self.writer.send_reverse_request(reverse_id, method, params)
        try:
            timeout_s = max(0.05, float(timeout_ms) / 1000.0)
            return await asyncio.wait_for(fut, timeout=timeout_s)
        finally:
            self._reverse_futures.pop(reverse_id, None)

    async def serve(self) -> None:
        self._loop = asyncio.get_running_loop()
        line_queue: asyncio.Queue[str | None] = asyncio.Queue()
        loop = self._loop

        def _push_pipe_lines_win32(fd: int, handle: int) -> None:
            """Non-blocking PeekNamedPipe reader preventing Win32 synchronous pipe deadlocks on DLL load."""
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.PeekNamedPipe.argtypes = [
                wintypes.HANDLE,
                wintypes.LPVOID,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
                ctypes.POINTER(wintypes.DWORD),
                ctypes.POINTER(wintypes.DWORD),
            ]
            kernel32.PeekNamedPipe.restype = wintypes.BOOL

            buf = bytearray()
            avail = wintypes.DWORD(0)
            poll_s = 0.001
            h_void = wintypes.HANDLE(handle)
            while True:
                ok = kernel32.PeekNamedPipe(h_void, None, 0, None, ctypes.byref(avail), None)
                if not ok:
                    if buf:
                        tail = bytes(buf).decode("utf-8", errors="replace").replace("\r\n", "\n")
                        loop.call_soon_threadsafe(line_queue.put_nowait, tail)
                        buf.clear()
                    loop.call_soon_threadsafe(line_queue.put_nowait, None)
                    break
                if avail.value > 0:
                    chunk = os.read(fd, min(65536, int(avail.value)))
                    if not chunk:
                        if buf:
                            tail = bytes(buf).decode("utf-8", errors="replace").replace("\r\n", "\n")
                            loop.call_soon_threadsafe(line_queue.put_nowait, tail)
                            buf.clear()
                        loop.call_soon_threadsafe(line_queue.put_nowait, None)
                        break
                    buf.extend(chunk)
                    while b"\n" in buf:
                        nl_idx = buf.index(b"\n")
                        raw_line = bytes(buf[: nl_idx + 1])
                        del buf[: nl_idx + 1]
                        decoded = raw_line.decode("utf-8", errors="replace").replace("\r\n", "\n")
                        loop.call_soon_threadsafe(line_queue.put_nowait, decoded)
                    poll_s = 0.001
                else:
                    time.sleep(poll_s)
                    if poll_s < 0.008:
                        poll_s = min(0.008, poll_s * 2.0)

        def _stdin_reader_thread() -> None:
            try:
                if sys.platform == "win32":
                    try:
                        import ctypes
                        from ctypes import wintypes
                        import msvcrt

                        fd = self._stdin.fileno()
                        handle = msvcrt.get_osfhandle(fd)
                        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                        kernel32.GetFileType.argtypes = [wintypes.HANDLE]
                        kernel32.GetFileType.restype = wintypes.DWORD
                        if kernel32.GetFileType(wintypes.HANDLE(handle)) == 3:
                            _push_pipe_lines_win32(fd, handle)
                            return
                    except (OSError, ValueError, io.UnsupportedOperation, AttributeError):
                        pass

                while True:
                    line = self._stdin.readline()
                    if not line:
                        loop.call_soon_threadsafe(line_queue.put_nowait, None)
                        break
                    loop.call_soon_threadsafe(line_queue.put_nowait, line)
            except Exception as exc:
                sys.stderr.write(f"[worker:{self.worker_type}] stdin reader stopped: {exc}\n")
                sys.stderr.flush()
                loop.call_soon_threadsafe(line_queue.put_nowait, None)

        reader_thread = threading.Thread(
            target=_stdin_reader_thread,
            name=f"jarvis-worker-stdin-{self.worker_type}",
            daemon=True,
        )
        reader_thread.start()

        self.writer.send_ready(self.worker_type, self.capabilities)

        pending_jobs: set[asyncio.Task[None]] = set()
        while True:
            raw_line = await line_queue.get()
            if raw_line is None:
                break
            stripped = raw_line.strip()
            if not stripped:
                continue

            if len(raw_line.encode("utf-8")) > MAX_FRAME_BYTES:
                self.writer.send_error(None, ERROR_INVALID_REQUEST, "Frame exceeds 16 MiB limit")
                continue

            try:
                frame = json.loads(stripped)
            except json.JSONDecodeError as exc:
                self.writer.send_error(None, ERROR_PARSE, f"Invalid JSON frame: {exc}")
                continue

            if not isinstance(frame, dict):
                self.writer.send_error(None, ERROR_INVALID_REQUEST, "Frame must be a JSON object")
                continue

            # Reverse response resolution (non-blocking)
            if frame.get("type") == "reverse_response":
                rev_id = frame.get("id")
                fut = self._reverse_futures.get(str(rev_id)) if rev_id is not None else None
                if fut is not None and not fut.done():
                    if "error" in frame and isinstance(frame["error"], dict):
                        fut.set_exception(
                            PermissionError(frame["error"].get("message", "Reverse RPC denied"))
                        )
                    else:
                        fut.set_result(dict(frame.get("result") or {}))
                continue

            method = frame.get("method")
            request_id = frame.get("id")
            params = frame.get("params")
            if not isinstance(params, dict):
                params = {}

            # Notification handling (heartbeat & cooperative cancellation)
            if method == "system.ping":
                seq = int(params.get("sequence") or 0)
                self.writer.send_pong(seq, len(self._active_tasks))
                continue

            if method == "task.cancel":
                target_id = str(params.get("request_id") or "")
                reason = str(params.get("reason") or "user_cancelled")
                active = self._active_tasks.get(target_id)
                if active is not None:
                    active.cancel_reason = reason
                    active.cancel_event.set()
                if request_id is not None:
                    self.writer.send_response(
                        str(request_id),
                        {"cancelled": active is not None, "request_id": target_id},
                    )
                continue

            if method == "worker.shutdown":
                if request_id is not None:
                    self.writer.send_response(str(request_id), {"status": "shutting_down"})
                break

            if not isinstance(method, str) or request_id is None:
                self.writer.send_error(
                    str(request_id) if request_id is not None else None,
                    ERROR_INVALID_REQUEST,
                    "Missing required method or request id",
                )
                continue

            handler = self._handlers.get(method)
            if handler is None:
                self.writer.send_error(
                    str(request_id),
                    ERROR_METHOD_NOT_FOUND,
                    f"Unknown worker method: {method}",
                )
                continue

            job = asyncio.create_task(
                self._run_request(str(request_id), method, handler, params)
            )
            pending_jobs.add(job)
            job.add_done_callback(pending_jobs.discard)

        for job in list(pending_jobs):
            job.cancel()
        if pending_jobs:
            await asyncio.gather(*pending_jobs, return_exceptions=True)

    async def _run_request(
        self,
        request_id: str,
        method: str,
        handler: RpcHandler,
        params: dict[str, Any],
    ) -> None:
        active_task = _ActiveTask(request_id=request_id)
        self._active_tasks[request_id] = active_task
        ctx = WorkerContext(request_id=request_id, server=self, active_task=active_task)
        try:
            result = await handler(ctx, params)
            if active_task.cancel_event.is_set() and not isinstance(result, dict):
                result = {
                    "status": "cancelled",
                    "partial_content": "".join(active_task.partial_parts),
                }
            self.writer.send_response(request_id, result)
        except TaskCancelledError:
            self.writer.send_response(
                request_id,
                {
                    "status": "cancelled",
                    "partial_content": "".join(active_task.partial_parts),
                },
            )
        except Exception as exc:
            self.writer.send_error(
                request_id,
                ERROR_INTERNAL,
                str(exc),
                data={
                    "subsystem": f"worker.{self.worker_type}.{method}",
                    "retryable": False,
                    "traceback": traceback.format_exc(),
                },
            )
        finally:
            self._active_tasks.pop(request_id, None)

