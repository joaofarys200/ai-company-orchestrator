"""
JARVIS OS — Phase 57: Mission Observer & Telemetry Collector
Observes execution progress, records runtime telemetry, logs, and system snapshots.
"""

from __future__ import annotations

import time
from typing import Any

from .models import AutonomousMission


class MissionObserver:
    """Observes execution events and captures runtime metrics."""

    def __init__(self, mission: AutonomousMission) -> None:
        self.mission = mission
        self.events: list[dict[str, Any]] = []

    def record_event(self, event_type: str, details: dict[str, Any]) -> None:
        event = {
            "mission_id": self.mission.mission_id,
            "event_type": event_type,
            "timestamp": time.time(),
            "details": details,
        }
        self.events.append(event)
        self.mission.metadata.setdefault("telemetry_events", []).append(event)

    def capture_snapshot(self, stage: str) -> dict[str, Any]:
        snapshot = {
            "mission_id": self.mission.mission_id,
            "stage": stage,
            "state": self.mission.state.value,
            "timestamp": time.time(),
            "risk": self.mission.risk,
            "evidence_count": len(self.mission.evidence_set.evidences),
            "state_hash": self.mission.compute_current_state_hash(),
        }
        self.record_event("SYSTEM_SNAPSHOT", snapshot)
        return snapshot
