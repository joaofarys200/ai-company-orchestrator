"""
JARVIS OS — Phase 56: Convergence Telemetry
Emits structured audit events for observability across the repair convergence lifecycle.
"""

from __future__ import annotations

import time
from typing import Dict, Any, List, Optional


class ConvergenceTelemetry:
    """Emits the 11 canonical audit events for convergence governance."""

    CANONICAL_EVENTS = {
        "convergence_started",
        "progress_recorded",
        "stall_detected",
        "divergence_detected",
        "cycle_detected",
        "oscillation_detected",
        "termination_triggered",
        "human_review_required",
        "transaction_committed",
        "transaction_rolled_back",
        "convergence_certificate_created",
    }

    def __init__(self):
        self.events: List[Dict[str, Any]] = []

    def emit_event(
        self,
        event_name: str,
        mission_id: str,
        transaction_id: str,
        state: str,
        risk: float,
        coverage: float,
        proof: str,
        budget: Dict[str, Any],
        reason: str,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Emits an audit event complying with the 11-event canonical schema."""
        event = {
            "event_name": event_name,
            "mission_id": mission_id,
            "transaction_id": transaction_id,
            "state": state,
            "risk": round(risk, 4),
            "coverage": round(coverage, 4),
            "proof": proof,
            "budget": budget,
            "reason": reason,
            "provenance": provenance or {"source": "ConvergenceGovernanceEngine"},
            "timestamp": time.time(),
        }
        self.events.append(event)
        return event

    def get_events_for_transaction(self, transaction_id: str) -> List[Dict[str, Any]]:
        return [e for e in self.events if e["transaction_id"] == transaction_id]
