"""
JARVIS OS — Phase 55: Transactional Multi-Repair Orchestration & Convergence
Transaction Telemetry & Observability.
Captures lifecycle audit events and measures performance latencies, cleanly distinguishing
microbenchmarks from mission-level latencies.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class TransactionTelemetry:
    """
    Manages structured event logging and timing metrics for multi-repair transactions.
    """

    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self.timings: Dict[str, float] = {}

    def record_event(
        self,
        event_name: str,
        mission_id: str,
        transaction_id: str,
        repair_id: Optional[str] = None,
        checkpoint_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        event = {
            "event": event_name,
            "mission_id": mission_id,
            "transaction_id": transaction_id,
            "repair_id": repair_id,
            "checkpoint_id": checkpoint_id,
            "details": details or {},
            "timestamp": time.time(),
        }
        self.events.append(event)
        return event

    def record_latency(self, phase_name: str, duration_seconds: float) -> None:
        self.timings[phase_name] = round(duration_seconds, 6)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_events": len(self.events),
            "events": list(self.events),
            "timings": dict(self.timings),
            "total_measured_latency_ms": round(sum(self.timings.values()) * 1000, 2),
        }
