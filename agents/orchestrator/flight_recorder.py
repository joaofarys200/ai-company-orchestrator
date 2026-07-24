"""Low-risk, incremental observability for ProjectBuilder executions."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

try:
    import psutil
except ImportError:  # pragma: no cover - optional at runtime
    psutil = None


SCHEMA_VERSION = "project_builder_flight_recorder_v1"
DEFAULT_HEARTBEAT_SECONDS = 5.0
MAX_SAMPLE_BYTES = 4096
CRITICAL_EVENTS = {
    "span_failed",
    "span_interrupted",
    "build_failed",
    "build_interrupted",
    "journal_write_completed",
    "process_timeout",
    "healthcheck_failed",
}
_SECRET_KEY = re.compile(
    r"(?i)(authorization|api[_-]?key|access[_-]?token|password|passwd|secret|cookie|token)"
)
_SECRET_VALUE = re.compile(
    r"(?i)(bearer\s+|api[_-]?key\s*[=:]\s*|access[_-]?token\s*[=:]\s*|"
    r"password\s*[=:]\s*|passwd\s*[=:]\s*|secret\s*[=:]\s*|token\s*[=:]\s*)\S+"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_text(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _sanitize_text(value: Any, limit: int = MAX_SAMPLE_BYTES) -> str:
    text = str(value or "")
    text = _SECRET_VALUE.sub(lambda match: f"{match.group(0).split('=')[0] if '=' in match.group(0) else match.group(0).split()[0]}[REDACTED]", text)
    return text[:limit]


def sanitize_metadata(value: Any, *, limit: int = MAX_SAMPLE_BYTES) -> Any:
    """Keep diagnostics useful without persisting secrets or unbounded content."""
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _SECRET_KEY.search(key_text):
                clean[key_text] = "[REDACTED]"
            elif key_text.lower() in {"prompt", "response", "content", "stdout", "stderr"}:
                text = _sanitize_text(item, limit)
                clean[key_text] = {
                    "sha256": _hash_text(item),
                    "bytes": len(str(item or "").encode("utf-8")),
                    "sample": text,
                }
            else:
                clean[key_text] = sanitize_metadata(item, limit=limit)
        return clean
    if isinstance(value, (list, tuple)):
        return [sanitize_metadata(item, limit=limit) for item in list(value)[:50]]
    if isinstance(value, str):
        return _sanitize_text(value, limit)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _sanitize_text(value, limit)


class _NoopSpan:
    span_id = ""

    def progress(self, **_metadata: Any) -> None:
        return None

    def complete(self, **_metadata: Any) -> None:
        return None

    def fail(self, _error: BaseException | None = None, **_metadata: Any) -> None:
        return None

    def interrupted(self, _error: BaseException | None = None, **_metadata: Any) -> None:
        return None

    def __enter__(self) -> "_NoopSpan":
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> bool:
        return False


class NoOpFlightRecorder:
    """Drop-in recorder used when observability is explicitly disabled."""

    enabled = False
    run_id = ""

    def set_context(self, **_values: Any) -> None:
        return None

    def event(self, *_args: Any, **_kwargs: Any) -> str:
        return ""

    def start_span(self, *_args: Any, **_kwargs: Any) -> _NoopSpan:
        return _NoopSpan()

    @contextmanager
    def span(self, *_args: Any, **_kwargs: Any) -> Iterator[_NoopSpan]:
        yield _NoopSpan()

    def write_payload_metrics(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def write_raw_artifact(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def close(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class FlightRecorderSpan:
    def __init__(
        self,
        recorder: "ProjectBuilderFlightRecorder",
        name: str,
        phase: str,
        span_id: str,
        parent_span_id: str,
        attempt: int,
    ):
        self.recorder = recorder
        self.name = name
        self.phase = phase
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.attempt = attempt
        self.started = time.monotonic()
        self._finished = False

    def progress(self, **metadata: Any) -> None:
        if self._finished:
            return
        self.recorder.event(
            "progress",
            phase=self.phase,
            status="RUNNING",
            span_id=self.span_id,
            parent_span_id=self.parent_span_id,
            attempt=self.attempt,
            progress_counter=self.recorder.next_progress(),
            metadata=metadata,
        )

    def complete(self, **metadata: Any) -> None:
        if self._finished:
            return
        self._finished = True
        self.recorder._finish_span(self, "span_completed", "COMPLETED", metadata, None)

    def fail(self, error: BaseException | None = None, **metadata: Any) -> None:
        if self._finished:
            return
        self._finished = True
        self.recorder._finish_span(self, "span_failed", "FAILED", metadata, error)

    def interrupted(self, error: BaseException | None = None, **metadata: Any) -> None:
        if self._finished:
            return
        self._finished = True
        self.recorder._finish_span(self, "span_interrupted", "INTERRUPTED", metadata, error)

    def __enter__(self) -> "FlightRecorderSpan":
        return self

    def __exit__(self, exc_type: Any, exc: Any, _tb: Any) -> bool:
        if exc is None:
            self.complete()
        elif exc_type in {KeyboardInterrupt, SystemExit}:
            self.interrupted(exc)
        else:
            self.fail(exc)
        return False


class ProjectBuilderFlightRecorder:
    """Persistent event recorder with bounded diagnostics and no functional policy."""

    enabled = True

    def __init__(
        self,
        directory: str | os.PathLike[str],
        *,
        run_id: str | None = None,
        project_id: str = "",
        mission_id: str = "",
        execution_id: str = "",
        build_run_id: str = "",
        diagnostics_enabled: bool = False,
        heartbeat_interval: float = DEFAULT_HEARTBEAT_SECONDS,
    ):
        self.run_id = run_id or uuid.uuid4().hex
        self.project_id = project_id
        self.mission_id = mission_id
        self.execution_id = execution_id
        self.build_run_id = build_run_id
        self.diagnostics_enabled = bool(diagnostics_enabled)
        self.directory = Path(directory).resolve() / self.run_id
        self.directory.mkdir(parents=True, exist_ok=True)
        self.events_path = self.directory / "events.jsonl"
        self.summary_path = self.directory / "summary.json"
        self.timeline_path = self.directory / "timeline.md"
        self.errors_path = self.directory / "errors.json"
        self.resources_path = self.directory / "resource_samples.jsonl"
        self.payload_metrics_path = self.directory / "payload_metrics.json"
        self.final_state_path = self.directory / "final_state.json"
        self._lock = threading.RLock()
        self._started = time.monotonic()
        self._last_progress = self._started
        self._progress_counter = 0
        self._events: list[dict[str, Any]] = []
        self._active_spans: dict[str, FlightRecorderSpan] = {}
        self._errors: list[dict[str, Any]] = []
        self._payload_metrics: list[dict[str, Any]] = []
        self._closed = False
        self._stop = threading.Event()
        self._heartbeat_interval = max(1.0, float(heartbeat_interval))
        self._events_handle = open(self.events_path, "a", encoding="utf-8", newline="\n")
        self._resources_handle = open(self.resources_path, "a", encoding="utf-8", newline="\n")
        self._write_json(self.payload_metrics_path, {"schema_version": SCHEMA_VERSION, "attempts": []})
        self._write_json(self.final_state_path, {"status": "RUNNING", "run_id": self.run_id})
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name=f"project-builder-flight-recorder-{self.run_id[:8]}",
            daemon=True,
        )
        self._heartbeat_thread.start()

    def set_context(self, **values: Any) -> None:
        with self._lock:
            for key in ("project_id", "mission_id", "execution_id", "build_run_id"):
                if values.get(key):
                    setattr(self, key, str(values[key]))

    def next_progress(self) -> int:
        with self._lock:
            self._progress_counter += 1
            self._last_progress = time.monotonic()
            return self._progress_counter

    def _event_record(
        self,
        event: str,
        *,
        phase: str = "",
        status: str = "OBSERVED",
        duration_ms: float | None = None,
        parent_span_id: str = "",
        span_id: str = "",
        attempt: int = 0,
        metadata: dict[str, Any] | None = None,
        error: BaseException | None = None,
        progress_counter: int | None = None,
    ) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "project_id": self.project_id,
            "mission_id": self.mission_id,
            "execution_id": self.execution_id,
            "build_run_id": self.build_run_id,
            "phase": phase,
            "event": event,
            "status": status,
            "wall_clock_timestamp": _utc_now(),
            "monotonic_offset_ms": round((time.monotonic() - self._started) * 1000, 3),
            "duration_ms": round(duration_ms, 3) if duration_ms is not None else None,
            "parent_span_id": parent_span_id,
            "span_id": span_id,
            "attempt": attempt,
            "thread_id": threading.get_ident(),
            "process_id": os.getpid(),
            "metadata": sanitize_metadata(metadata or {}),
            "error_type": type(error).__name__ if error else "",
            "error_message": _sanitize_text(error, 1000) if error else "",
            "progress_counter": progress_counter,
        }

    def event(
        self,
        event: str,
        *,
        phase: str = "",
        status: str = "OBSERVED",
        duration_ms: float | None = None,
        parent_span_id: str = "",
        span_id: str = "",
        attempt: int = 0,
        metadata: dict[str, Any] | None = None,
        error: BaseException | None = None,
        progress_counter: int | None = None,
    ) -> str:
        if self._closed:
            return ""
        try:
            record = self._event_record(
                event,
                phase=phase,
                status=status,
                duration_ms=duration_ms,
                parent_span_id=parent_span_id,
                span_id=span_id,
                attempt=attempt,
                metadata=metadata,
                error=error,
                progress_counter=progress_counter,
            )
            with self._lock:
                self._events.append(record)
                if error is not None or status in {"FAILED", "INTERRUPTED"}:
                    self._errors.append(record)
                self._append_jsonl(self.events_path, record, critical=event in CRITICAL_EVENTS)
            return str(record["span_id"] or record["event"])
        except Exception:
            # Observability must never change the pipeline result.
            return ""

    def start_span(
        self,
        name: str,
        *,
        phase: str = "",
        parent_span_id: str = "",
        attempt: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> FlightRecorderSpan:
        with self._lock:
            parent = parent_span_id or next(reversed(self._active_spans), "")
            span = FlightRecorderSpan(
                self,
                name,
                phase or name,
                uuid.uuid4().hex,
                parent,
                attempt,
            )
            self._active_spans[span.span_id] = span
        self.event(
            "span_started",
            phase=span.phase,
            status="RUNNING",
            parent_span_id=span.parent_span_id,
            span_id=span.span_id,
            attempt=attempt,
            metadata={"operation": name, **(metadata or {})},
        )
        return span

    @contextmanager
    def span(
        self,
        name: str,
        *,
        phase: str = "",
        parent_span_id: str = "",
        attempt: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> Iterator[FlightRecorderSpan]:
        current = self.start_span(
            name,
            phase=phase,
            parent_span_id=parent_span_id,
            attempt=attempt,
            metadata=metadata,
        )
        try:
            yield current
        except KeyboardInterrupt as exc:
            current.interrupted(exc)
            raise
        except SystemExit as exc:
            current.interrupted(exc)
            raise
        except BaseException as exc:
            current.fail(exc)
            raise
        else:
            current.complete()

    def _finish_span(
        self,
        span: FlightRecorderSpan,
        event: str,
        status: str,
        metadata: dict[str, Any],
        error: BaseException | None,
    ) -> None:
        with self._lock:
            self._active_spans.pop(span.span_id, None)
        self.event(
            event,
            phase=span.phase,
            status=status,
            duration_ms=(time.monotonic() - span.started) * 1000,
            parent_span_id=span.parent_span_id,
            span_id=span.span_id,
            attempt=span.attempt,
            metadata=metadata,
            error=error,
        )

    def _append_jsonl(self, path: Path, value: dict[str, Any], *, critical: bool = False) -> None:
        persistent = None
        if path == self.events_path:
            persistent = self._events_handle
        elif path == self.resources_path:
            persistent = self._resources_handle
        if persistent is not None:
            persistent.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")
            persistent.flush()
            if critical:
                os.fsync(persistent.fileno())
            return
        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            if critical:
                os.fsync(handle.fileno())

    def _write_json(self, path: Path, value: Any) -> None:
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(sanitize_metadata(value), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def write_payload_metrics(self, metrics: dict[str, Any]) -> None:
        clean = sanitize_metadata(metrics)
        with self._lock:
            self._payload_metrics.append(clean)
            self._write_json(
                self.payload_metrics_path,
                {"schema_version": SCHEMA_VERSION, "attempts": self._payload_metrics},
            )

    def write_raw_artifact(self, name: str, content: str) -> None:
        if not self.diagnostics_enabled:
            return
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", str(name))[:100]
        path = self.directory / safe_name
        try:
            path.write_text(_sanitize_text(content, 1_000_000), encoding="utf-8")
        except OSError:
            return

    def _heartbeat_loop(self) -> None:
        while not self._stop.wait(self._heartbeat_interval):
            try:
                with self._lock:
                    active = list(self._active_spans.values())
                    last_progress = self._last_progress
                    counter = self._progress_counter
                process_data: dict[str, Any] = {}
                if psutil is not None:
                    try:
                        process = psutil.Process(os.getpid())
                        process_data = {
                            "cpu_percent": process.cpu_percent(interval=None),
                            "memory_rss_bytes": process.memory_info().rss,
                        }
                    except (OSError, psutil.Error):
                        process_data = {}
                now = time.monotonic()
                sample = {
                    "wall_clock_timestamp": _utc_now(),
                    "monotonic_offset_ms": round((now - self._started) * 1000, 3),
                    "active_span": active[-1].name if active else "",
                    "idle_duration_ms": round((now - last_progress) * 1000, 3),
                    "progress_counter": counter,
                    **process_data,
                }
                with self._lock:
                    self._append_jsonl(self.resources_path, sanitize_metadata(sample))
                self.event(
                    "heartbeat",
                    phase=active[-1].phase if active else "",
                    status="RUNNING",
                    metadata=sample,
                    progress_counter=counter,
                )
            except Exception:
                return

    def _classify_gap(self, previous: dict[str, Any], current: dict[str, Any]) -> str:
        text = f"{previous.get('event')} {current.get('event')} {current.get('phase')}".lower()
        if "request" in text or "model" in text or "stream" in text:
            return "modelo"
        if "command" in text or "process" in text or "healthcheck" in text:
            return "subprocesso"
        if "journal" in text or "persist" in text or "write" in text:
            return "I/O"
        if "progress" in text or "heartbeat" in text:
            return "sem progresso"
        return "desconhecido"

    def _summary(self, final_state: dict[str, Any] | None, status: str) -> dict[str, Any]:
        starts = [item for item in self._events if item["event"] == "span_started"]
        ends = {item["span_id"]: item for item in self._events if item["event"] in {
            "span_completed", "span_failed", "span_interrupted",
        }}
        durations: list[dict[str, Any]] = []
        for start in starts:
            end = ends.get(start["span_id"])
            if end is None:
                continue
            durations.append({
                "phase": start["phase"],
                "operation": start["metadata"].get("operation", start["phase"]),
                "duration_ms": end.get("duration_ms"),
                "status": end.get("status"),
                "span_id": start["span_id"],
            })
        gaps: list[dict[str, Any]] = []
        for previous, current in zip(self._events, self._events[1:]):
            gap = float(current["monotonic_offset_ms"]) - float(previous["monotonic_offset_ms"])
            gaps.append({
                "previous_event": previous["event"],
                "next_event": current["event"],
                "gap_ms": round(gap, 3),
                "classification": self._classify_gap(previous, current),
            })
        slowest = max(durations, key=lambda item: float(item.get("duration_ms") or 0), default=None)
        max_gap = max(gaps, key=lambda item: float(item.get("gap_ms") or 0), default=None)
        completed_events = [item for item in self._events if item["event"] in {
            "span_completed", "requester_completed", "build_completed", "journal_write_completed",
        }]
        started_events = [item for item in self._events if item["event"] in {
            "span_started", "build_project_entered", "requester_started",
        }]
        return {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "project_id": self.project_id,
            "mission_id": self.mission_id,
            "execution_id": self.execution_id,
            "build_run_id": self.build_run_id,
            "status": status,
            "event_count": len(self._events),
            "error_count": len(self._errors),
            "slowest_phase": slowest,
            "largest_gap": max_gap,
            "last_progress": next((item for item in reversed(self._events) if item["event"] == "progress"), None),
            "last_phase_started": started_events[-1] if started_events else None,
            "last_phase_completed": completed_events[-1] if completed_events else None,
            "max_period_without_progress_ms": max((
                float(item.get("metadata", {}).get("idle_duration_ms") or 0)
                for item in self._events if item["event"] == "heartbeat"
            ), default=0.0),
            "partial_response": any(bool(item.get("metadata", {}).get("partial_response")) for item in self._events),
            "retry_observed": any("retry" in str(item.get("event", "")) or item.get("metadata", {}).get("retry_reason") for item in self._events),
            "second_attempt_started": any(int(item.get("attempt") or 0) == 2 for item in self._events),
            "orphan_process_observed": any(item["event"] == "process_cleanup_completed" and not item.get("metadata", {}).get("cleanup_completed", True) for item in self._events),
            "materialization_partial": any(item["event"] == "file_write_completed" for item in self._events) and status != "SUCCEEDED",
            "journal_persisted": any(item["event"] == "journal_write_completed" for item in self._events),
            "mission_state_updated": any("mission_state_update_completed" == item["event"] for item in self._events),
            "false_success": status == "SUCCEEDED" and any(item["event"] == "span_failed" for item in self._events),
            "durations": durations,
            "gaps": gaps,
            "final_state": sanitize_metadata(final_state or {}),
        }

    def _write_timeline(self, summary: dict[str, Any]) -> None:
        lines = [
            "# ProjectBuilder Flight Recorder Timeline",
            "",
            "| Ordem | Fase | Evento | Inicio | Duracao ms | Estado | Progresso |",
            "|---:|---|---|---:|---:|---|---:|",
        ]
        for index, item in enumerate(self._events, start=1):
            lines.append(
                f"| {index} | {item['phase']} | {item['event']} | "
                f"{item['monotonic_offset_ms']} | {item.get('duration_ms') or ''} | "
                f"{item['status']} | {item.get('progress_counter') or ''} |"
            )
        lines.extend(["", "## Duracoes agregadas", "", "| Fase | Operacao | Duracao ms | Estado |", "|---|---|---:|---|"])
        for item in summary["durations"]:
            lines.append(f"| {item['phase']} | {item['operation']} | {item['duration_ms']} | {item['status']} |")
        lines.extend(["", "## Gaps", "", "| Evento anterior | Evento seguinte | Gap ms | Classificacao |", "|---|---|---:|---|"])
        for item in summary["gaps"]:
            lines.append(f"| {item['previous_event']} | {item['next_event']} | {item['gap_ms']} | {item['classification']} |")
        self.timeline_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def close(self, *, status: str = "INTERRUPTED", final_state: dict[str, Any] | None = None) -> None:
        with self._lock:
            if self._closed:
                return
            active = list(self._active_spans.values())
        for span in active:
            span.interrupted(metadata={"reason": "recorder_closed"})
        self._stop.set()
        if self._heartbeat_thread is not threading.current_thread():
            self._heartbeat_thread.join(timeout=self._heartbeat_interval + 1.0)
        try:
            summary = self._summary(final_state, status)
            self._write_json(self.summary_path, summary)
            self._write_json(self.errors_path, self._errors)
            self._write_json(self.final_state_path, final_state or {"status": status})
            self._write_timeline(summary)
        except Exception:
            return
        finally:
            with self._lock:
                for handle in (self._events_handle, self._resources_handle):
                    try:
                        handle.flush()
                        handle.close()
                    except OSError:
                        pass
                self._closed = True


def recorder_directory(workspace_path: str | os.PathLike[str]) -> Path:
    return Path(workspace_path).resolve() / "diagnostics" / "project_builder_flight_recorder"
