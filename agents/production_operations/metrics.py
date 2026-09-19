"""
Phase 71 — Production Operations Internal Telemetry & Metrics
Records counters and timings for engine operations.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class OperationsTelemetry:
    """Internal performance and operational counters."""
    observations_processed: int = 0
    incidents_detected: int = 0
    sev0_count: int = 0
    sev1_count: int = 0
    sev2_count: int = 0
    sev3_count: int = 0
    sev4_count: int = 0
    plans_created: int = 0
    remediations_succeeded: int = 0
    remediations_failed: int = 0
    rollbacks_executed: int = 0
    escalations_issued: int = 0
    total_cpu_ms: float = 0.0
    stage_timings_ms: Dict[str, float] = field(default_factory=dict)

    def record_stage_time(self, stage: str, duration_ms: float) -> None:
        self.stage_timings_ms[stage] = self.stage_timings_ms.get(stage, 0.0) + duration_ms
        self.total_cpu_ms += duration_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observations_processed": self.observations_processed,
            "incidents_detected": self.incidents_detected,
            "sev_distribution": {
                "SEV0": self.sev0_count,
                "SEV1": self.sev1_count,
                "SEV2": self.sev2_count,
                "SEV3": self.sev3_count,
                "SEV4": self.sev4_count,
            },
            "plans_created": self.plans_created,
            "remediations_succeeded": self.remediations_succeeded,
            "remediations_failed": self.remediations_failed,
            "rollbacks_executed": self.rollbacks_executed,
            "escalations_issued": self.escalations_issued,
            "total_cpu_ms": round(self.total_cpu_ms, 3),
            "stage_timings_ms": {k: round(v, 3) for k, v in self.stage_timings_ms.items()},
        }
