"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
Performance Metrics, Telemetry, and Invariant Timing Reconciliation.
Verifies: total_cpu_ms == stage_total_ms + overhead_ms.
"""

from __future__ import annotations

import time
from typing import Any, Dict


class MissionMetricsTracker:
    """Measures execution latency across all mission stages and enforces timing reconciliation."""

    def __init__(self):
        self.stage_timings: Dict[str, float] = {
            "planning_ms": 0.0,
            "scheduling_ms": 0.0,
            "checkpoint_ms": 0.0,
            "recovery_ms": 0.0,
            "verification_ms": 0.0,
            "adaptation_ms": 0.0,
            "persistence_ms": 0.0,
            "completion_ms": 0.0,
        }
        self.overhead_ms: float = 0.0
        self.total_cpu_ms: float = 0.0
        self.memory_mb: float = 0.0

    def add_timing(self, stage: str, duration_ms: float) -> None:
        if stage in self.stage_timings:
            self.stage_timings[stage] += duration_ms
        else:
            self.overhead_ms += duration_ms

    def reconcile_timing(self) -> Dict[str, Any]:
        stage_total = sum(self.stage_timings.values())
        if self.total_cpu_ms <= 0.0:
            self.total_cpu_ms = stage_total + self.overhead_ms
        else:
            self.overhead_ms = max(0.0, self.total_cpu_ms - stage_total)

        delta = round(self.total_cpu_ms - (stage_total + self.overhead_ms), 6)
        valid = (delta == 0.0)

        return {
            "stage_timings": dict(self.stage_timings),
            "stage_total_ms": round(stage_total, 4),
            "overhead_ms": round(self.overhead_ms, 4),
            "total_cpu_ms": round(self.total_cpu_ms, 4),
            "delta": delta,
            "timing_invariant_valid": valid,
            "memory_mb": round(self.memory_mb, 2),
        }
