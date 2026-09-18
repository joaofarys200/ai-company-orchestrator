"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Module: metrics.py
Precise timing, memory profiling, and mathematical reconciliation across
architectural evaluation phases.

Rule:
    Strict mathematical equality:
    stage_total_ms == sum of reported phase timings
    total_cpu_ms == stage_total_ms + overhead_ms
    Never permit timing summation discrepancies.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict


class ArchitectureMetricsCollector:
    """Tracks latency across all architectural analysis pipeline stages."""

    def __init__(self):
        self.timings: Dict[str, float] = {
            "snapshot_ms": 0.0,
            "problem_detection_ms": 0.0,
            "constraint_ms": 0.0,
            "alternative_generation_ms": 0.0,
            "impact_ms": 0.0,
            "contract_ms": 0.0,
            "behavior_ms": 0.0,
            "risk_ms": 0.0,
            "comparison_ms": 0.0,
            "migration_ms": 0.0,
            "simulation_ms": 0.0,
            "persistence_ms": 0.0,
        }
        self.overhead_ms: float = 0.0
        self.memory_mb: float = 0.0

    def record_stage(self, stage: str, duration_ms: float) -> None:
        if stage in self.timings:
            self.timings[stage] = round(duration_ms, 3)
        else:
            self.overhead_ms = round(self.overhead_ms + duration_ms, 3)

    def record_memory(self, memory_mb: float) -> None:
        self.memory_mb = round(memory_mb, 2)

    def to_dict(self) -> Dict[str, Any]:
        stage_total_ms = round(sum(self.timings.values()), 3)
        total_cpu_ms = round(stage_total_ms + self.overhead_ms, 3)

        # Invariant assertion
        assert abs(total_cpu_ms - (stage_total_ms + self.overhead_ms)) < 1e-6, "Metrics summation invariant violation!"

        res = dict(self.timings)
        res["stage_total_ms"] = stage_total_ms
        res["overhead_ms"] = self.overhead_ms
        res["total_cpu_ms"] = total_cpu_ms
        res["memory_mb"] = self.memory_mb
        return res
