"""
JARVIS OS — Phase 53: Universal Project Preflight & Runtime Failure Auto-Recovery
Telemetry and Metrics Engine: Records audit events, preflight latency, and time to recovery.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class PreflightTelemetry:
    """
    Central telemetry tracker for preflight events, diagnostics, and recovery latencies.
    """

    def __init__(self) -> None:
        self._events: List[Dict[str, Any]] = []

    def emit_event(
        self,
        event_name: str,
        project_id: str,
        mission_id: Optional[str] = None,
        runtime: Optional[str] = None,
        diagnostic_id: Optional[str] = None,
        repair_id: Optional[str] = None,
        confidence: Optional[str] = None,
        risk: Optional[float] = None,
        decision: Optional[str] = None,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = {
            "event_name": event_name,
            "phase": 53,
            "project_id": project_id,
            "mission_id": mission_id,
            "runtime": runtime,
            "diagnostic_id": diagnostic_id,
            "repair_id": repair_id,
            "confidence": confidence,
            "risk": risk,
            "decision": decision,
            "provenance": provenance or {},
            "timestamp": time.time(),
        }
        self._events.append(payload)
        return payload

    def get_events(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if not project_id:
            return list(self._events)
        return [e for e in self._events if e.get("project_id") == project_id]

    def compute_benchmarks(self, runs: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculates latency aggregates for benchmark reporting."""
        if not runs:
            return {
                "avg_preflight_ms": 0.0,
                "avg_diagnostic_ms": 0.0,
                "avg_recovery_ms": 0.0,
                "time_to_first_diagnosis": 0.0,
            }

        preflights = [r.get("preflight_ms", 0.0) for r in runs]
        diagnostics = [r.get("diagnostic_ms", 0.0) for r in runs]
        recoveries = [r.get("recovery_ms", 0.0) for r in runs]

        return {
            "avg_preflight_ms": round(sum(preflights) / max(1, len(preflights)), 2),
            "avg_diagnostic_ms": round(sum(diagnostics) / max(1, len(diagnostics)), 2),
            "avg_recovery_ms": round(sum(recoveries) / max(1, len(recoveries)), 2),
            "time_to_first_diagnosis": round(diagnostics[0], 2) if diagnostics else 0.0,
        }
