"""
JARVIS OS — Phase 50: Behavioral Contract Preservation & Migration Proof
Audit Telemetry, Counters, and Event Ledger.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class BehavioralTelemetryEvent:
    """Standardized audit event recorded during proof lifecycle."""
    event_type: str
    mission_id: str
    contract_id: str
    consumer_id: str
    migration_id: str
    confidence: float
    decision: str
    provenance: Dict[str, Any] = field(default_factory=dict)
    phase: int = 50
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "mission_id": self.mission_id,
            "contract_id": self.contract_id,
            "consumer_id": self.consumer_id,
            "migration_id": self.migration_id,
            "confidence": self.confidence,
            "decision": self.decision,
            "provenance": self.provenance,
            "phase": self.phase,
            "timestamp": self.timestamp,
        }


class BehavioralProofTelemetry:
    """
    Central telemetry recorder for behavioral proof events and gate metrics.
    """

    def __init__(self) -> None:
        self._events: List[BehavioralTelemetryEvent] = []
        self._counters: Dict[str, int] = {
            "behavior_baseline_created": 0,
            "behavior_trace_observed": 0,
            "behavior_delta_detected": 0,
            "behavior_proof_started": 0,
            "behavior_proof_passed": 0,
            "behavior_proof_failed": 0,
            "behavior_proof_uncertain": 0,
            "counterexample_created": 0,
            "behavior_gate_blocked": 0,
            "behavior_gate_cleared": 0,
        }

    def record_event(
        self,
        event_type: str,
        mission_id: str,
        contract_id: str,
        consumer_id: str,
        migration_id: str,
        confidence: float,
        decision: str,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> BehavioralTelemetryEvent:
        """Records a new telemetry event and increments category counter."""
        event = BehavioralTelemetryEvent(
            event_type=event_type,
            mission_id=mission_id,
            contract_id=contract_id,
            consumer_id=consumer_id,
            migration_id=migration_id,
            confidence=confidence,
            decision=decision,
            provenance=provenance or {},
        )
        self._events.append(event)
        self._counters[event_type] = self._counters.get(event_type, 0) + 1
        return event

    def get_counters(self) -> Dict[str, int]:
        """Returns snapshot of event counters."""
        return dict(self._counters)

    def list_events(self, event_type: Optional[str] = None) -> List[BehavioralTelemetryEvent]:
        """Lists events with optional filtering."""
        if event_type:
            return [e for e in self._events if e.event_type == event_type]
        return list(self._events)

    def clear(self) -> None:
        """Resets telemetry."""
        self._events.clear()
        for k in self._counters:
            self._counters[k] = 0
