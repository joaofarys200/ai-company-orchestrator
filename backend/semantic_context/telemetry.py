from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True)
class SemanticContextTelemetryRecord:
    timestamp: str
    event: str
    duration_ms: float
    items_considered: int
    items_rejected: int
    duplicate_items: int
    ranked_items: int
    source_counts: Mapping[str, int]
    final_chars: int
    final_bytes: int
    snapshot_version: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_counts",
            MappingProxyType(dict(sorted(self.source_counts.items()))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "event": self.event,
            "duration_ms": self.duration_ms,
            "items_considered": self.items_considered,
            "items_rejected": self.items_rejected,
            "duplicate_items": self.duplicate_items,
            "ranked_items": self.ranked_items,
            "source_counts": dict(self.source_counts),
            "final_chars": self.final_chars,
            "final_bytes": self.final_bytes,
            "snapshot_version": self.snapshot_version,
        }


class SemanticContextTelemetry:
    """In-memory metrics only. Context content and prompts are never recorded."""

    def __init__(self, clock: Callable[[], str] | None = None):
        self._clock = clock or (
            lambda: datetime.now(timezone.utc).isoformat()
        )
        self._records: list[SemanticContextTelemetryRecord] = []

    def record_build(
        self,
        *,
        duration_ms: float,
        items_considered: int,
        items_rejected: int,
        duplicate_items: int,
        ranked_items: int,
        source_counts: Mapping[str, int],
        final_chars: int,
        final_bytes: int,
        snapshot_version: str,
    ) -> SemanticContextTelemetryRecord:
        record = SemanticContextTelemetryRecord(
            timestamp=self._clock(),
            event="semantic_context_built",
            duration_ms=round(float(duration_ms), 3),
            items_considered=int(items_considered),
            items_rejected=int(items_rejected),
            duplicate_items=int(duplicate_items),
            ranked_items=int(ranked_items),
            source_counts=source_counts,
            final_chars=int(final_chars),
            final_bytes=int(final_bytes),
            snapshot_version=str(snapshot_version),
        )
        self._records.append(record)
        return record

    def snapshot(self) -> tuple[dict[str, Any], ...]:
        return tuple(record.to_dict() for record in self._records)
