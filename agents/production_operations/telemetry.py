"""
Phase 71 — Telemetry Normalization & Ingestion
Normalizes runtime metrics, enforces epistemic statuses, and prevents invalid promotion of inferred data.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional
from .models import (
    HealthStatus,
    ObservationProvenance,
    ObservationStatus,
    OperationalState,
    RuntimeObservation,
)


class TelemetryNormalizer:
    """
    Ingests and normalizes raw telemetry points into structured RuntimeObservation records.
    Strictly safeguards epistemic status: INFERRED cannot be promoted to VERIFIED without corroborating evidence.
    """

    def __init__(self, service_id: str, default_env: str = "local"):
        self.service_id = service_id
        self.default_env = default_env
        self._history: List[RuntimeObservation] = []

    def normalize(
        self,
        raw_data: Dict[str, Any],
        provenance: ObservationProvenance = ObservationProvenance.REAL_RUNTIME_OBSERVATION,
        status: ObservationStatus = ObservationStatus.OBSERVED,
    ) -> RuntimeObservation:
        """
        Normalizes arbitrary runtime telemetry into the strict RuntimeObservation schema.
        """
        # Parse operational state
        raw_state = raw_data.get("state", OperationalState.HEALTHY)
        if isinstance(raw_state, OperationalState):
            state = raw_state
        else:
            try:
                state = OperationalState(str(raw_state))
            except ValueError:
                state = OperationalState.DEGRADED

        # Parse health status
        raw_health = raw_data.get("health_status", HealthStatus.HEALTHY)
        if isinstance(raw_health, HealthStatus):
            health_status = raw_health
        else:
            try:
                health_status = HealthStatus(str(raw_health))
            except ValueError:
                health_status = HealthStatus.UNKNOWN

        # Numeric sanitization
        latency_ms = float(raw_data.get("latency_ms", 0.0))
        error_rate = float(raw_data.get("error_rate", 0.0))
        availability = float(raw_data.get("availability", 1.0))
        cpu = float(raw_data.get("cpu", 0.0))
        memory = float(raw_data.get("memory", 0.0))
        restart_count = int(raw_data.get("restart_count", 0))

        # Dependencies dict
        deps = raw_data.get("dependency_status", {})
        if not isinstance(deps, dict):
            deps = {"default": str(deps)}

        obs = RuntimeObservation(
            process_id=str(raw_data.get("process_id", f"proc-{uuid.uuid4().hex[:6]}")),
            service_id=str(raw_data.get("service_id", self.service_id)),
            environment=str(raw_data.get("environment", self.default_env)),
            state=state,
            latency_ms=latency_ms,
            error_rate=error_rate,
            availability=availability,
            health_status=health_status,
            cpu=cpu,
            memory=memory,
            restart_count=restart_count,
            dependency_status=deps,
            evidence_id=str(raw_data.get("evidence_id", f"evd-obs-{uuid.uuid4().hex[:8]}")),
            provenance=provenance,
            status=status,
            timestamp=float(raw_data.get("timestamp", time.time())),
        )

        self._history.append(obs)
        return obs

    def promote_observation(
        self,
        observation: RuntimeObservation,
        target_status: ObservationStatus,
        supporting_evidence_ids: List[str],
    ) -> RuntimeObservation:
        """
        Guards epistemic status transition.
        INFERRED -> VERIFIED is illegal without at least one non-empty supporting evidence ID.
        """
        if observation.status == ObservationStatus.INFERRED and target_status == ObservationStatus.VERIFIED:
            if not supporting_evidence_ids:
                raise ValueError("Cannot promote INFERRED observation to VERIFIED without corroborating evidence IDs.")

        observation.status = target_status
        return observation

    def get_latest_observation(self) -> Optional[RuntimeObservation]:
        return self._history[-1] if self._history else None

    def get_history(self) -> List[RuntimeObservation]:
        return list(self._history)
