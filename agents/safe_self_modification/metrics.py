"""
JARVIS OS — Phase 65: Safe Self-Modification & Transactional Architecture Implementation
Module: metrics.py
Collects timing, memory, throughput, and verification coverage metrics
for self-modification operations and benchmark evaluation.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class ModificationMetricsCollector:
    """Collects and summarizes execution latency, resource overhead, and verification metrics."""

    def __init__(self):
        self.stage_timings: Dict[str, List[float]] = {}
        self.counters: Dict[str, int] = {
            "transactions_started": 0,
            "transactions_committed": 0,
            "transactions_rolled_back": 0,
            "patches_applied": 0,
            "checkpoints_created": 0,
            "tests_executed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

    def record_stage_time(self, stage_name: str, duration_ms: float) -> None:
        if stage_name not in self.stage_timings:
            self.stage_timings[stage_name] = []
        self.stage_timings[stage_name].append(duration_ms)

    def increment(self, counter_name: str, by: int = 1) -> None:
        self.counters[counter_name] = self.counters.get(counter_name, 0) + by

    def get_summary(self) -> Dict[str, Any]:
        averages = {
            f"avg_{k}_ms": round(sum(v) / len(v), 3) if v else 0.0
            for k, v in self.stage_timings.items()
        }
        return {
            "counters": self.counters,
            "averages": averages,
            "timestamp": time.time(),
        }
