"""
JARVIS OS — Phase 51: Behavioral Proof Coverage & Scenario Exploration
Observability, Structured Audit Events, and Telemetry.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class ExplorationTelemetry:
    """
    Structured telemetry emitter for Phase 51 Behavioral Proof Exploration.
    Maintains append-only audit trail of scenario exploration events.
    """

    def __init__(self) -> None:
        self._events: List[Dict[str, Any]] = []

    def emit_event(
        self,
        event_name: str,
        mission_id: Optional[str] = None,
        migration_id: Optional[str] = None,
        scenario_id: Optional[str] = None,
        consumer_id: Optional[str] = None,
        contract_id: Optional[str] = None,
        seed: int = 42,
        coverage: Optional[Dict[str, Any]] = None,
        budget: Optional[Dict[str, Any]] = None,
        decision: Optional[str] = None,
        provenance: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Emit and record a structured audit event."""
        effective_mission_id = mission_id or migration_id or "default_mission"
        payload = {
            "event_name": event_name,
            "phase": 51,
            "mission_id": effective_mission_id,
            "migration_id": migration_id or effective_mission_id,
            "scenario_id": scenario_id,
            "consumer_id": consumer_id,
            "contract_id": contract_id,
            "seed": seed,
            "coverage": coverage or {},
            "budget": budget or {},
            "decision": decision,
            "provenance": provenance or {"component": "behavioral_proof_exploration"},
            "details": details or {},
            "timestamp": time.time(),
        }
        self._events.append(payload)
        return payload

    def list_events(self, event_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """List recorded events with optional filter."""
        if event_name:
            return [e for e in self._events if e["event_name"] == event_name]
        return list(self._events)

    def count(self) -> int:
        return len(self._events)

    def clear(self) -> None:
        self._events.clear()
