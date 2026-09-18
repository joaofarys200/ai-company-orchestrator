"""
JARVIS OS — Phase 66: Multi-Agent Engineering Coordination & Conflict Arbitration
Module: metrics.py
Collects operational metrics: coordination throughput, parallel/serial wave ratios,
conflict rates, merge durations, and deadlock frequencies.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List


class CoordinationMetricsCollector:
    """Aggregates telemetry and timing metrics for multi-agent coordination."""

    def __init__(self):
        self.metrics: Dict[str, Any] = {
            "total_intents_processed": 0,
            "parallel_waves_count": 0,
            "serial_waves_count": 0,
            "conflicts_detected": 0,
            "conflicts_arbitrated": 0,
            "merges_executed": 0,
            "rebases_executed": 0,
            "deadlocks_detected": 0,
            "starvation_boosts": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

    def record_intent(self):
        self.metrics["total_intents_processed"] += 1

    def record_wave(self, is_parallel: bool):
        if is_parallel:
            self.metrics["parallel_waves_count"] += 1
        else:
            self.metrics["serial_waves_count"] += 1

    def record_conflict(self, count: int = 1):
        self.metrics["conflicts_detected"] += count

    def record_arbitration(self):
        self.metrics["conflicts_arbitrated"] += 1

    def record_merge(self):
        self.metrics["merges_executed"] += 1

    def record_rebase(self):
        self.metrics["rebases_executed"] += 1

    def record_deadlock(self):
        self.metrics["deadlocks_detected"] += 1

    def record_starvation_boost(self):
        self.metrics["starvation_boosts"] += 1

    def record_cache_hit(self):
        self.metrics["cache_hits"] += 1

    def record_cache_miss(self):
        self.metrics["cache_misses"] += 1

    def get_summary(self) -> Dict[str, Any]:
        return dict(self.metrics)
