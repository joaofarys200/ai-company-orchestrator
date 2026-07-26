from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Protocol, runtime_checkable

from backend.logging_config import get_logger, log_event


@dataclass(frozen=True)
class TelemetryRecord:
    timestamp: str
    request_id: str
    request_fingerprint: str
    task_profile: str
    provider: str
    model: str
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    pipeline: tuple[str, ...]
    validation_status: str
    recovery_action: str
    result_status: str
    context_items: int
    allowed_tool_count: int
    progress_conditions: tuple[str, ...]
    metadata_keys: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@runtime_checkable
class TelemetrySink(Protocol):
    def emit(self, record: TelemetryRecord) -> None:
        ...


class InMemoryTelemetrySink:
    def __init__(self):
        self._records: list[TelemetryRecord] = []
        self._lock = Lock()

    def emit(self, record: TelemetryRecord) -> None:
        with self._lock:
            self._records.append(record)

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [item.to_dict() for item in self._records]


class ModelTelemetry:
    def __init__(self, sink: TelemetrySink | None = None):
        self.sink = sink or InMemoryTelemetrySink()
        self.logger = get_logger(__name__)

    def record(self, **values: Any) -> TelemetryRecord:
        record = TelemetryRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            **values,
        )
        self.sink.emit(record)
        log_event(
            self.logger,
            "model_harness.execution",
            request_id=record.request_id,
            request_fingerprint=record.request_fingerprint,
            task_profile=record.task_profile,
            provider=record.provider,
            model=record.model,
            latency_ms=record.latency_ms,
            input_tokens=record.input_tokens,
            output_tokens=record.output_tokens,
            pipeline=list(record.pipeline),
            validation_status=record.validation_status,
            recovery_action=record.recovery_action,
            result_status=record.result_status,
            context_items=record.context_items,
            allowed_tool_count=record.allowed_tool_count,
            progress_conditions=list(record.progress_conditions),
            metadata_keys=list(record.metadata_keys),
        )
        return record

    def snapshot(self) -> list[dict[str, Any]]:
        snapshot = getattr(self.sink, "snapshot", None)
        return snapshot() if callable(snapshot) else []
