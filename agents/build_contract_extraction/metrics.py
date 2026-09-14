"""
JARVIS OS — Phase 49: Build Contract Metrics & Telemetry
Tracks extraction latency, dynamic consumer resolution rates, precision, and audit events.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class BuildContractTelemetry:
    """
    Manages telemetry events and precision/recall statistics for Phase 49.
    """

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.total_contracts_extracted: int = 0
        self.total_dynamic_patterns_detected: int = 0
        self.resolved_consumers_count: int = 0
        self.uncertain_consumers_count: int = 0
        self.unresolved_consumers_count: int = 0

    def record_event(
        self,
        event_type: str,
        mission_id: str = "system",
        artifact: str = "",
        source: str = "",
        provenance: Optional[dict[str, Any]] = None,
        confidence: str = "GENERATED",
        decision: str = "RECORDED",
        details: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Records an auditable telemetry event."""
        ev = {
            "event_id": f"telem_{len(self.events) + 1}_{int(time.time()*1000)}",
            "event_type": event_type,
            "mission_id": mission_id,
            "phase": 49,
            "artifact": artifact,
            "source": source,
            "provenance": provenance,
            "confidence": confidence,
            "timestamp": time.time(),
            "decision": decision,
            "details": details or {},
        }
        self.events.append(ev)

        if event_type == "contract_extracted":
            self.total_contracts_extracted += 1
        elif event_type == "dynamic_consumer_detected":
            self.total_dynamic_patterns_detected += 1
        elif event_type == "dynamic_consumer_resolved":
            self.resolved_consumers_count += 1
        elif event_type == "dynamic_consumer_uncertain":
            self.uncertain_consumers_count += 1
        elif event_type == "consumer_unresolved":
            self.unresolved_consumers_count += 1

        return ev

    @property
    def resolution_rate(self) -> float:
        """Percentage of detected dynamic patterns that were successfully resolved to contracts."""
        total = self.resolved_consumers_count + self.uncertain_consumers_count + self.unresolved_consumers_count
        return round(self.resolved_consumers_count / total, 4) if total > 0 else 0.0

    @property
    def uncertainty_ratio(self) -> float:
        """Ratio of consumers preserved as UNCERTAIN without guessing."""
        total = self.resolved_consumers_count + self.uncertain_consumers_count + self.unresolved_consumers_count
        return round(self.uncertain_consumers_count / total, 4) if total > 0 else 0.0

    def get_summary(self) -> dict[str, Any]:
        return {
            "total_events": len(self.events),
            "contracts_extracted": self.total_contracts_extracted,
            "dynamic_patterns_detected": self.total_dynamic_patterns_detected,
            "resolved_consumers": self.resolved_consumers_count,
            "uncertain_consumers": self.uncertain_consumers_count,
            "unresolved_consumers": self.unresolved_consumers_count,
            "resolution_rate": self.resolution_rate,
            "uncertainty_ratio": self.uncertainty_ratio,
        }
