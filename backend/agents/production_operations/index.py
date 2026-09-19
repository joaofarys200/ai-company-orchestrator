"""
Phase 71 — Autonomous Production Operations Facade
Unified high-level entry points for production operations, health checking, and incident management.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from .bridge import ProductionOperationsBridge
from .models import (
    HealthCheckResult,
    ObservationProvenance,
    OperationalState,
    ProductionDecision,
    RecoveryVerification,
    RemediationExecution,
    RollbackCertificate,
    RuntimeObservation,
    SLOEvaluation,
)

_BRIDGES: Dict[str, ProductionOperationsBridge] = {}


def get_production_bridge(service_id: str = "jarvis-service") -> ProductionOperationsBridge:
    """Returns or initializes a singleton ProductionOperationsBridge for a service."""
    if service_id not in _BRIDGES:
        _BRIDGES[service_id] = ProductionOperationsBridge(service_id=service_id)
    return _BRIDGES[service_id]


def run_production_health_check(service_id: str = "jarvis-service") -> List[HealthCheckResult]:
    """Executes all standard health checks for the service."""
    bridge = get_production_bridge(service_id)
    return bridge.execute_healthchecks()


def evaluate_service_slo(
    service_id: str = "jarvis-service",
    metrics_data: Optional[Dict[str, List[float]]] = None,
) -> List[SLOEvaluation]:
    """Evaluates SLO thresholds for the service."""
    bridge = get_production_bridge(service_id)
    data = metrics_data or {
        "availability": [0.995, 0.998, 0.999],
        "error_rate": [0.002, 0.001, 0.003],
        "latency_p95_ms": [85.0, 92.0, 88.0],
        "restart_rate": [0.0],
        "dependency_health_ratio": [1.0],
    }
    return bridge.evaluate_slos(data)


def record_runtime_observation(
    raw_data: Dict[str, Any],
    service_id: str = "jarvis-service",
    provenance: ObservationProvenance = ObservationProvenance.REAL_RUNTIME_OBSERVATION,
) -> RuntimeObservation:
    """Ingests and records runtime observation."""
    bridge = get_production_bridge(service_id)
    return bridge.ingest_runtime_observation(raw_data, provenance=provenance)


def run_operational_governance_cycle(service_id: str = "jarvis-service") -> ProductionDecision:
    """Runs complete detection, diagnosis, planning, and gating cycle."""
    bridge = get_production_bridge(service_id)
    return bridge.run_operational_cycle()


def get_operational_status(service_id: str = "jarvis-service") -> Dict[str, Any]:
    """Returns full operational summary dictionary."""
    bridge = get_production_bridge(service_id)
    return bridge.get_status()
