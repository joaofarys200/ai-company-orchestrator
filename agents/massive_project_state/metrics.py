from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .models import StateTelemetryEvent


class StateFabricMetrics:
    """Collects and aggregates structured observability metrics for project state operations."""

    def __init__(self) -> None:
        self.events: List[StateTelemetryEvent] = []

    def record(
        self,
        event_type: str,
        repository_id: str = "jarvis_os",
        mission_id: str = "",
        partition: str = "",
        state_hash: str = "",
        index_version: int = 1,
        memory_bytes: int = 0,
        latency_ms: float = 0.0,
        decision: str = "OK",
    ) -> StateTelemetryEvent:
        evt = StateTelemetryEvent(
            event_type=event_type,
            repository_id=repository_id,
            mission_id=mission_id,
            partition=partition,
            state_hash=state_hash,
            index_version=index_version,
            memory_bytes=memory_bytes,
            latency_ms=latency_ms,
            decision=decision,
            timestamp=time.time(),
        )
        self.events.append(evt)
        return evt

    def get_summary(self) -> Dict[str, Any]:
        by_type: Dict[str, int] = {}
        total_latency = 0.0
        for e in self.events:
            by_type[e.event_type] = by_type.get(e.event_type, 0) + 1
            total_latency += e.latency_ms

        avg_latency = (total_latency / len(self.events)) if self.events else 0.0
        return {
            "total_events": len(self.events),
            "events_by_type": by_type,
            "avg_latency_ms": round(avg_latency, 3),
            "recent_events": [e.to_dict() for e in self.events[-10:]],
        }

    def clear(self) -> None:
        self.events.clear()
