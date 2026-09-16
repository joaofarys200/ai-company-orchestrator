"""
JARVIS OS — Phase 56: Degradation Detector
Detects performance, resource, or complexity regressions introduced during repair attempts.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from agents.repair_convergence_governance.models import (
    DegradationReport,
    RepairStepSnapshot,
)


class DegradationDetector:
    """Monitors secondary system attributes (latency, memory, cyclomatic complexity) for degradation."""

    def __init__(
        self,
        latency_tolerance_pct: float = 20.0,
        memory_tolerance_pct: float = 25.0,
        complexity_tolerance_pct: float = 30.0,
    ):
        self.latency_tolerance_pct = latency_tolerance_pct
        self.memory_tolerance_pct = memory_tolerance_pct
        self.complexity_tolerance_pct = complexity_tolerance_pct

    def evaluate_degradation(self, history: List[RepairStepSnapshot]) -> DegradationReport:
        """Compares the current step's secondary metrics against the initial or previous baseline."""
        if len(history) < 2:
            return DegradationReport(
                degraded=False,
                degraded_metrics={},
                explanation="Initial repair step; establishing metric baseline."
            )

        baseline = history[0]
        curr = history[-1]

        degraded_metrics: Dict[str, float] = {}
        explanation_parts = []

        # Check Latency
        if baseline.latency_ms > 0 and curr.latency_ms > baseline.latency_ms:
            lat_delta_pct = ((curr.latency_ms - baseline.latency_ms) / baseline.latency_ms) * 100.0
            if lat_delta_pct > self.latency_tolerance_pct:
                degraded_metrics["latency_ms"] = round(lat_delta_pct, 2)
                explanation_parts.append(
                    f"Latency increased by {lat_delta_pct:.1f}% ({baseline.latency_ms:.1f}ms -> {curr.latency_ms:.1f}ms)."
                )

        # Check Memory RSS
        if baseline.memory_mb > 0 and curr.memory_mb > baseline.memory_mb:
            mem_delta_pct = ((curr.memory_mb - baseline.memory_mb) / baseline.memory_mb) * 100.0
            if mem_delta_pct > self.memory_tolerance_pct:
                degraded_metrics["memory_mb"] = round(mem_delta_pct, 2)
                explanation_parts.append(
                    f"Memory increased by {mem_delta_pct:.1f}% ({baseline.memory_mb:.1f}MB -> {curr.memory_mb:.1f}MB)."
                )

        # Check Cyclomatic Complexity
        if baseline.cyclomatic_complexity > 0 and curr.cyclomatic_complexity > baseline.cyclomatic_complexity:
            comp_delta_pct = (
                (curr.cyclomatic_complexity - baseline.cyclomatic_complexity) / baseline.cyclomatic_complexity
            ) * 100.0
            if comp_delta_pct > self.complexity_tolerance_pct:
                degraded_metrics["cyclomatic_complexity"] = round(comp_delta_pct, 2)
                explanation_parts.append(
                    f"Complexity increased by {comp_delta_pct:.1f}% ({baseline.cyclomatic_complexity} -> {curr.cyclomatic_complexity})."
                )

        degraded = len(degraded_metrics) > 0
        if not degraded:
            explanation_parts.append("Secondary metrics remain within acceptable operational tolerances.")

        return DegradationReport(
            degraded=degraded,
            degraded_metrics=degraded_metrics,
            explanation=" ".join(explanation_parts)
        )
