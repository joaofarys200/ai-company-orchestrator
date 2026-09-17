from __future__ import annotations

import time
from typing import Any, Dict, List

from .models import SCCTelemetryEvent


class SCCTelemetryMetrics:
    """Collects and aggregates structured observability metrics for SCC operations."""

    def __init__(self) -> None:
        self.events: List[SCCTelemetryEvent] = []

    def record(
        self,
        event_type: str,
        repository_id: str = "jarvis_os",
        mission_id: str = "",
        graph_revision: int = 1,
        scc_id: str = "",
        node_count: int = 0,
        edge_count: int = 0,
        latency_ms: float = 0.0,
        confidence: str = "FULL",
        provenance: Dict[str, Any] | None = None,
    ) -> SCCTelemetryEvent:
        event = SCCTelemetryEvent(
            event_type=event_type,
            repository_id=repository_id,
            mission_id=mission_id,
            graph_revision=graph_revision,
            scc_id=scc_id,
            node_count=node_count,
            edge_count=edge_count,
            latency_ms=latency_ms,
            confidence=confidence,
            provenance=provenance or {},
            timestamp=time.time(),
        )
        self.events.append(event)
        return event

    def get_summary(self) -> Dict[str, Any]:
        by_type: Dict[str, int] = {}
        total_lat = 0.0
        for e in self.events:
            by_type[e.event_type] = by_type.get(e.event_type, 0) + 1
            total_lat += e.latency_ms

        avg_lat = (total_lat / len(self.events)) if self.events else 0.0
        return {
            "total_events": len(self.events),
            "events_by_type": by_type,
            "avg_latency_ms": round(avg_lat, 3),
            "recent_events": [e.to_dict() for e in self.events[-10:]],
        }

    def clear(self) -> None:
        self.events.clear()
