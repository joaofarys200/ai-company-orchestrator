"""
Phase 72 — Reliability Intelligence Facade
Provides convenience entrypoints for ingestion, risk evaluation, and planning.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .bridge import ReliabilityIntelligenceBridge

_GLOBAL_BRIDGE: Optional[ReliabilityIntelligenceBridge] = None


def get_reliability_bridge(service_id: str = "default-service") -> ReliabilityIntelligenceBridge:
    global _GLOBAL_BRIDGE
    if _GLOBAL_BRIDGE is None or _GLOBAL_BRIDGE.service_id != service_id:
        _GLOBAL_BRIDGE = ReliabilityIntelligenceBridge(service_id=service_id)
    return _GLOBAL_BRIDGE


def record_reliability_observation(payload: Dict[str, Any], service_id: str = "default-service") -> Dict[str, Any]:
    bridge = get_reliability_bridge(service_id)
    obs = bridge.ingest_observation(payload)
    return obs.to_dict()


def run_reliability_governance_cycle(metric: str = "latency", service_id: str = "default-service") -> Dict[str, Any]:
    bridge = get_reliability_bridge(service_id)
    decision = bridge.run_reliability_cycle(metric=metric)
    return decision.to_dict()


def get_reliability_status(service_id: str = "default-service") -> Dict[str, Any]:
    bridge = get_reliability_bridge(service_id)
    return bridge.get_status_summary()
