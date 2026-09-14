"""
JARVIS OS — Phase 42: Experience Metrics & Cross-Mission Quality Evaluation
Computes quantitative indicators of experience quality, retrieval precision/recall,
and performs rigorous comparative evaluations between Cold and Warm missions.
"""

from __future__ import annotations

from typing import Any

from agents.experience_memory.models import (
    ExperienceQualityMetrics,
    ExperienceReuseRecord,
)


class ExperienceMetricsCollector:
    """Collects reuse telemetry and computes multi-axis quality metrics."""

    def __init__(self):
        self._reuse_records: list[ExperienceReuseRecord] = []
        self._cold_missions: list[dict[str, Any]] = []
        self._warm_missions: list[dict[str, Any]] = []

    def record_reuse(self, record: ExperienceReuseRecord) -> None:
        self._reuse_records.append(record)

    def record_mission_benchmark(self, mission_profile: str, is_warm: bool, metrics: dict[str, Any]) -> None:
        entry = {"profile": mission_profile, "metrics": metrics}
        if is_warm:
            self._warm_missions.append(entry)
        else:
            self._cold_missions.append(entry)

    def compute_quality_metrics(self, total_retrievals: int = 0, relevant_retrieved: int = 0, ground_truth_relevant: int = 0) -> ExperienceQualityMetrics:
        reuse_cnt = len(self._reuse_records)
        succ_cnt = sum(1 for r in self._reuse_records if r.successful_reuse)
        fail_cnt = reuse_cnt - succ_cnt

        precision = (relevant_retrieved / max(total_retrievals, 1)) if total_retrievals > 0 else 1.0
        recall = (relevant_retrieved / max(ground_truth_relevant, 1)) if ground_truth_relevant > 0 else 1.0

        return ExperienceQualityMetrics(
            reuse_count=reuse_cnt,
            successful_reuse_count=succ_cnt,
            failed_reuse_count=fail_cnt,
            contradicted_count=0,
            stale_count=0,
            applicability_accuracy=round(succ_cnt / max(reuse_cnt, 1), 4) if reuse_cnt > 0 else 1.0,
            outcome_consistency=round(succ_cnt / max(reuse_cnt, 1), 4) if reuse_cnt > 0 else 1.0,
            precision=round(precision, 4),
            recall=round(recall, 4),
        )

    def compare_cold_vs_warm(self) -> dict[str, Any]:
        """Compares operational efficiency between Cold missions and Warm missions."""
        def _avg(lst: list[dict[str, Any]], key: str) -> float:
            vals = [m["metrics"].get(key, 0.0) for m in lst if key in m["metrics"]]
            return sum(vals) / max(len(vals), 1)

        cold_summary = {
            "first_pass_success_rate": _avg(self._cold_missions, "first_pass_success_rate"),
            "avg_repairs": _avg(self._cold_missions, "repair_count"),
            "avg_replans": _avg(self._cold_missions, "replan_count"),
            "decision_accuracy": _avg(self._cold_missions, "decision_accuracy"),
            "prediction_accuracy": _avg(self._cold_missions, "prediction_accuracy"),
            "human_escalations": _avg(self._cold_missions, "human_escalation_count"),
            "avg_resolution_seconds": _avg(self._cold_missions, "resolution_seconds"),
        }

        warm_summary = {
            "first_pass_success_rate": _avg(self._warm_missions, "first_pass_success_rate"),
            "avg_repairs": _avg(self._warm_missions, "repair_count"),
            "avg_replans": _avg(self._warm_missions, "replan_count"),
            "decision_accuracy": _avg(self._warm_missions, "decision_accuracy"),
            "prediction_accuracy": _avg(self._warm_missions, "prediction_accuracy"),
            "human_escalations": _avg(self._warm_missions, "human_escalation_count"),
            "avg_resolution_seconds": _avg(self._warm_missions, "resolution_seconds"),
        }

        # Calculate improvement delta
        delta = {}
        for k, v_warm in warm_summary.items():
            v_cold = cold_summary.get(k, 0.0)
            delta[f"{k}_delta"] = round(v_warm - v_cold, 4)

        return {
            "cold_missions_count": len(self._cold_missions),
            "warm_missions_count": len(self._warm_missions),
            "cold": cold_summary,
            "warm": warm_summary,
            "delta": delta,
        }
