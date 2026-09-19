"""
JARVIS OS — Phase 68: Performance Quality Evaluator
Explicitly categorizes observations as:
- OBSERVED
- ESTIMATED
- INFERRED

Measures:
- latency (p50, p95, p99 ms)
- throughput (ops/sec)
- CPU utilization (ms or %)
- memory footprint (MB)
- I/O operations
- cache efficiency
- verification overhead

Invariant:
Never consider a performance improvement automatically positive if it increases
risk, operational cost, or loss of verification evidence (e.g. skipping assertions
or suppressing logs to artificially reduce latency).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .models import (
    DimensionChange,
    DimensionEvaluation,
    DimensionStatus,
    ObservationType,
    QualityDimension,
    QualityObservation,
)


class PerformanceQualityEvaluator:
    """
    Evaluates system performance across observed, estimated, and inferred metrics.
    """

    def __init__(self, thresholds: Optional[Dict[str, float]] = None) -> None:
        self.thresholds = thresholds or {
            "max_p95_latency_ms": 250.0,
            "min_throughput_ops": 100.0,
            "max_memory_mb": 1024.0,
            "min_cache_efficiency": 0.60,
            "max_verification_overhead_ms": 500.0,
        }

    def evaluate(
        self,
        context: Optional[Dict[str, Any]] = None,
        scope: str = "global",
    ) -> DimensionEvaluation:
        ctx = context or {}
        perf_data = ctx.get("performance", {})

        p95_latency = float(perf_data.get("p95_latency_ms", 45.0))
        throughput = float(perf_data.get("throughput_ops", 450.0))
        cpu_util = float(perf_data.get("cpu_ms", 120.0))
        memory_mb = float(perf_data.get("memory_mb", 180.0))
        io_ops = int(perf_data.get("io_ops", 24))
        cache_eff = float(perf_data.get("cache_efficiency", 0.88))
        verif_overhead = float(perf_data.get("verification_overhead_ms", 35.0))
        evidence_loss_detected = bool(perf_data.get("evidence_loss_detected", False))

        observations = [
            QualityObservation(
                dimension=QualityDimension.PERFORMANCE,
                metric_name="p95_latency_ms",
                measured_value=p95_latency,
                evidence={"measured_p95_ms": p95_latency},
                uncertainty=0.03,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.PERFORMANCE,
                metric_name="throughput_ops",
                measured_value=throughput,
                evidence={"benchmark_ops_per_sec": throughput},
                uncertainty=0.04,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.PERFORMANCE,
                metric_name="cpu_ms",
                measured_value=cpu_util,
                evidence={"cpu_active_duration_ms": cpu_util},
                uncertainty=0.05,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.PERFORMANCE,
                metric_name="memory_mb",
                measured_value=memory_mb,
                evidence={"resident_set_size_mb": memory_mb},
                uncertainty=0.02,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.PERFORMANCE,
                metric_name="io_ops",
                measured_value=io_ops,
                evidence={"disk_or_network_io_calls": io_ops},
                uncertainty=0.05,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.PERFORMANCE,
                metric_name="cache_efficiency",
                measured_value=cache_eff,
                evidence={"cache_hits_over_requests": cache_eff},
                uncertainty=0.05,
                scope=scope,
                observation_type=ObservationType.ESTIMATED,
            ),
            QualityObservation(
                dimension=QualityDimension.PERFORMANCE,
                metric_name="verification_overhead_ms",
                measured_value=verif_overhead,
                evidence={"time_spent_in_verification_ms": verif_overhead},
                uncertainty=0.08,
                scope=scope,
                observation_type=ObservationType.INFERRED,
            ),
        ]

        is_degraded = (
            p95_latency > self.thresholds["max_p95_latency_ms"]
            or memory_mb > self.thresholds["max_memory_mb"]
            or cache_eff < self.thresholds["min_cache_efficiency"]
            or verif_overhead > self.thresholds["max_verification_overhead_ms"]
            or evidence_loss_detected
        )

        status = DimensionStatus.DEGRADED if is_degraded else DimensionStatus.HEALTHY
        summary = (
            f"Performance status {status.value}: p95={p95_latency:.1f}ms, "
            f"throughput={throughput:.1f}ops/s, memory={memory_mb:.1f}MB, "
            f"cache_eff={cache_eff:.1%}, overhead={verif_overhead:.1f}ms"
        )

        return DimensionEvaluation(
            dimension=QualityDimension.PERFORMANCE,
            observations=observations,
            evidence=[{
                "evaluator": "PerformanceQualityEvaluator",
                "p95": p95_latency,
                "evidence_loss_detected": evidence_loss_detected,
            }],
            uncertainty=0.04,
            scope=scope,
            status=status,
            summary=summary,
        )

    def compare_performance(
        self,
        baseline_eval: DimensionEvaluation,
        after_eval: DimensionEvaluation,
    ) -> Tuple[DimensionChange, List[Dict[str, Any]], List[Dict[str, Any]]]:
        base_obs = {o.metric_name: o.measured_value for o in baseline_eval.observations}
        after_obs = {o.metric_name: o.measured_value for o in after_eval.observations}

        degradations = []
        improvements = []

        b_lat = float(base_obs.get("p95_latency_ms", 0.0))
        a_lat = float(after_obs.get("p95_latency_ms", 0.0))

        # Check evidence for artificial performance "gain" via evidence loss
        evidence_loss = after_eval.evidence[0].get("evidence_loss_detected", False) if after_eval.evidence else False

        if a_lat > b_lat * 1.25 and (a_lat - b_lat) > 20.0:
            degradations.append({"metric": "p95_latency_ms", "from": b_lat, "to": a_lat, "reason": "latency regressed by >25%"})
        elif a_lat < b_lat * 0.80 and (b_lat - a_lat) > 20.0:
            if evidence_loss:
                # Invariant: Performance gain coupled with evidence loss is a DEGRADATION
                degradations.append({
                    "metric": "p95_latency_ms",
                    "from": b_lat,
                    "to": a_lat,
                    "reason": "apparent latency improvement gained via suppression of verification evidence",
                })
            else:
                improvements.append({"metric": "p95_latency_ms", "from": b_lat, "to": a_lat, "reason": "latency improved without evidence sacrifice"})

        b_mem = float(base_obs.get("memory_mb", 0.0))
        a_mem = float(after_obs.get("memory_mb", 0.0))
        if a_mem > b_mem * 1.30 and (a_mem - b_mem) > 50.0:
            degradations.append({"metric": "memory_mb", "from": b_mem, "to": a_mem, "reason": "memory footprint regressed"})
        elif a_mem < b_mem * 0.80:
            improvements.append({"metric": "memory_mb", "from": b_mem, "to": a_mem, "reason": "memory footprint reduced"})

        if degradations and not improvements:
            return DimensionChange.DEGRADED, degradations, improvements
        if improvements and not degradations:
            return DimensionChange.IMPROVED, degradations, improvements
        if degradations and improvements:
            return DimensionChange.UNCERTAIN, degradations, improvements

        return DimensionChange.UNCHANGED, degradations, improvements
