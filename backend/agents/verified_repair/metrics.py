"""
JARVIS OS — Phase 54: Repair Telemetry & Latency Profiler
Measures discrete stage latencies and separates microbenchmarks from end-to-end mission-level recovery.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List


class RepairTelemetry:
    """
    Detailed telemetry and audit event emitter for verified repair synthesis.
    Strictly separates microbenchmark latencies from full mission-level recovery times.
    """

    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []

    def record_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        entry = {
            "event_name": event_name,
            "timestamp": time.time(),
            "payload": payload,
        }
        self.events.append(entry)

    def compute_benchmarks(self, run_records: List[Dict[str, float]]) -> Dict[str, Any]:
        if not run_records:
            return {
                "avg_diagnosis_ms": 0.0,
                "avg_candidate_gen_ms": 0.0,
                "avg_ranking_ms": 0.0,
                "avg_patch_apply_ms": 0.0,
                "avg_preflight_ms": 0.0,
                "avg_healthcheck_ms": 0.0,
                "avg_regression_ms": 0.0,
                "avg_rollback_ms": 0.0,
                "avg_microbenchmark_total_ms": 0.0,
                "avg_mission_level_recovery_ms": 0.0,
            }

        n = len(run_records)
        avg_diag = sum(r.get("diagnosis_ms", 0.0) for r in run_records) / n
        avg_gen = sum(r.get("candidate_gen_ms", 0.0) for r in run_records) / n
        avg_rank = sum(r.get("ranking_ms", 0.0) for r in run_records) / n
        avg_apply = sum(r.get("patch_apply_ms", 0.0) for r in run_records) / n
        avg_preflight = sum(r.get("preflight_ms", 0.0) for r in run_records) / n
        avg_hc = sum(r.get("healthcheck_ms", 0.0) for r in run_records) / n
        avg_reg = sum(r.get("regression_ms", 0.0) for r in run_records) / n
        avg_roll = sum(r.get("rollback_ms", 0.0) for r in run_records) / n

        micro_total = avg_diag + avg_gen + avg_rank + avg_apply + avg_preflight + avg_reg
        mission_total = micro_total + avg_hc + sum(r.get("startup_ms", 0.0) for r in run_records) / n

        return {
            "avg_diagnosis_ms": round(avg_diag, 2),
            "avg_candidate_gen_ms": round(avg_gen, 2),
            "avg_ranking_ms": round(avg_rank, 2),
            "avg_patch_apply_ms": round(avg_apply, 2),
            "avg_preflight_ms": round(avg_preflight, 2),
            "avg_healthcheck_ms": round(avg_hc, 2),
            "avg_regression_ms": round(avg_reg, 2),
            "avg_rollback_ms": round(avg_roll, 2),
            "avg_microbenchmark_total_ms": round(micro_total, 2),
            "avg_mission_level_recovery_ms": round(mission_total, 2),
        }
