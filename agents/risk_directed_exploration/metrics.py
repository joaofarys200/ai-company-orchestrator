"""
JARVIS OS — Phase 52: Risk-Directed Behavioral Exploration & Adaptive Proof Search
Observability, Efficiency Metrics, and Telemetry Emitter.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class RiskDirectedTelemetry:
    """
    Structured telemetry emitter for Phase 52 Risk-Directed Behavioral Exploration.
    Maintains append-only audit trail and computes efficiency metrics.
    """

    def __init__(self) -> None:
        self._events: List[Dict[str, Any]] = []

    def emit_event(
        self,
        event_name: str,
        migration_id: str,
        contract_id: Optional[str] = None,
        policy: Optional[str] = None,
        risk_score: Optional[float] = None,
        uncertainty_score: Optional[float] = None,
        priority: Optional[float] = None,
        decision: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Emit and record a structured audit event."""
        payload = {
            "event_name": event_name,
            "phase": 52,
            "migration_id": migration_id,
            "contract_id": contract_id,
            "policy": policy,
            "risk_score": risk_score,
            "uncertainty_score": uncertainty_score,
            "priority": priority,
            "decision": decision,
            "details": details or {},
            "timestamp": time.time(),
        }
        self._events.append(payload)
        return payload

    def compute_efficiency(
        self,
        risk_initial: float,
        risk_final: float,
        cost_spent: float,
        scenarios_total: int,
        scenarios_executed: int,
    ) -> Dict[str, float]:
        """
        Compute evidence efficiency metrics:
        scenario_efficiency = risk_reduction / max(1.0, cost_spent)
        """
        risk_reduction = max(0.0, risk_initial - risk_final)
        scenarios_saved = max(0, scenarios_total - scenarios_executed)
        base_gain = risk_reduction + (scenarios_saved / max(1, scenarios_total)) * 0.10
        efficiency = base_gain / max(1.0, cost_spent)

        return {
            "risk_reduction": round(risk_reduction, 4),
            "scenario_efficiency": round(efficiency, 6),
            "scenarios_saved": scenarios_saved,
            "efficiency_ratio": round(scenarios_saved / max(1, scenarios_total), 4),
        }

    def list_events(self, event_name: Optional[str] = None) -> List[Dict[str, Any]]:
        if event_name:
            return [e for e in self._events if e["event_name"] == event_name]
        return list(self._events)

    def count(self) -> int:
        return len(self._events)

    def clear(self) -> None:
        self._events.clear()
