"""
Release Readiness Metrics Module
Phase 70 — Autonomous Release Readiness & Production Governance

Collects and reconciles granular performance metrics, timing stages,
and cache accounting across evaluation phases.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class StageTimingBreakdown:
    """Stage timings in milliseconds."""
    baseline_ms: float = 0.0
    quality_ms: float = 0.0
    contract_ms: float = 0.0
    behavior_ms: float = 0.0
    security_ms: float = 0.0
    performance_ms: float = 0.0
    runtime_ms: float = 0.0
    observability_ms: float = 0.0
    dependency_ms: float = 0.0
    rollback_ms: float = 0.0
    gate_ms: float = 0.0
    persistence_ms: float = 0.0

    @property
    def stage_total_ms(self) -> float:
        """Sum of all 12 evaluation stage timings."""
        return (
            self.baseline_ms + self.quality_ms + self.contract_ms +
            self.behavior_ms + self.security_ms + self.performance_ms +
            self.runtime_ms + self.observability_ms + self.dependency_ms +
            self.rollback_ms + self.gate_ms + self.persistence_ms
        )


@dataclass
class EvaluationBenchmarkMetrics:
    """Comprehensive benchmark measurement with strict CPU reconciliation."""
    scale: int
    timings: StageTimingBreakdown = field(default_factory=StageTimingBreakdown)
    overhead_ms: float = 0.0
    total_cpu_ms: float = 0.0
    memory_mb: float = 0.0
    observations_processed: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    full_scan: int = 0
    incremental_scan: int = 0

    def reconcile_cpu(self) -> None:
        """Strictly ensures total_cpu_ms == stage_total_ms + overhead_ms."""
        self.total_cpu_ms = round(self.timings.stage_total_ms + self.overhead_ms, 4)

    def to_dict(self) -> Dict[str, Any]:
        self.reconcile_cpu()
        return {
            "scale": self.scale,
            "baseline_ms": round(self.timings.baseline_ms, 4),
            "quality_ms": round(self.timings.quality_ms, 4),
            "contract_ms": round(self.timings.contract_ms, 4),
            "behavior_ms": round(self.timings.behavior_ms, 4),
            "security_ms": round(self.timings.security_ms, 4),
            "performance_ms": round(self.timings.performance_ms, 4),
            "runtime_ms": round(self.timings.runtime_ms, 4),
            "observability_ms": round(self.timings.observability_ms, 4),
            "dependency_ms": round(self.timings.dependency_ms, 4),
            "rollback_ms": round(self.timings.rollback_ms, 4),
            "gate_ms": round(self.timings.gate_ms, 4),
            "persistence_ms": round(self.timings.persistence_ms, 4),
            "stage_total_ms": round(self.timings.stage_total_ms, 4),
            "overhead_ms": round(self.overhead_ms, 4),
            "total_cpu_ms": round(self.total_cpu_ms, 4),
            "memory_mb": round(self.memory_mb, 2),
            "observations_processed": self.observations_processed,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "full_scan": self.full_scan,
            "incremental_scan": self.incremental_scan
        }
