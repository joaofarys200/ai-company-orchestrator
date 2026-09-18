"""
JARVIS OS — Phase 61: Autonomous Test Synthesis & Coverage-Guided Validation
Module: metrics.py
Telemetry collector tracking test candidate counts, acceptance rates, execution costs, and RAM usage.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False


class TestSynthesisMetrics:
    """Collects telemetry and performance benchmarks for Phase 61."""

    def __init__(self) -> None:
        if _HAS_PSUTIL:
            try:
                self.process = psutil.Process(os.getpid())
            except Exception:
                self.process = None
        else:
            self.process = None

        self.records: List[Dict[str, Any]] = []

    def measure_memory_mb(self) -> float:
        if self.process:
            try:
                return round(self.process.memory_info().rss / (1024 * 1024), 2)
            except Exception:
                pass
        return 0.0

    def record_run(
        self,
        total_candidates: int,
        accepted: int,
        rejected: int,
        duration_ms: float,
        composite_coverage: float,
        mutation_score: float,
        total_cost: float,
    ) -> Dict[str, Any]:
        rec = {
            "timestamp": time.time(),
            "total_candidates": total_candidates,
            "accepted": accepted,
            "rejected": rejected,
            "acceptance_rate": round(accepted / max(1, total_candidates), 4),
            "duration_ms": round(duration_ms, 2),
            "composite_coverage": composite_coverage,
            "mutation_score": mutation_score,
            "total_cost": round(total_cost, 4),
            "ram_mb": self.measure_memory_mb(),
        }
        self.records.append(rec)
        return rec
