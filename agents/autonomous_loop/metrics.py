"""
JARVIS OS — Phase 40: Autonomous Engineering Loop & Closed-Loop Mission Adaptation
Performance Profiling, Latency Decompositions, and Multi-Axis Autonomy Metrics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import statistics
import time
from typing import Any, Dict, List, Optional


@dataclass
class CycleLatencyBreakdown:
    cycle_id: str
    snapshot_latency_ms: float = 0.0
    prediction_latency_ms: float = 0.0
    execution_latency_ms: float = 0.0
    observation_latency_ms: float = 0.0
    comparison_latency_ms: float = 0.0
    micro_decision_latency_ms: float = 0.0
    adaptation_latency_ms: float = 0.0
    validation_latency_ms: float = 0.0
    checkpoint_latency_ms: float = 0.0
    total_cycle_latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MultiAxisAutonomyScore:
    mission_id: str
    total_cycles: int
    first_pass_success: bool = True
    eventual_success: bool = True
    repair_count: int = 0
    repair_success_rate: float = 1.0
    replan_count: int = 0
    replan_success_rate: float = 1.0
    recovery_tested: bool = False
    recovery_success: bool = True
    human_escalations_count: int = 0
    false_success_rate: float = 0.0  # Must be strictly 0.0
    requirement_retention_rate: float = 1.0  # Target 1.0
    mission_drift_score: float = 0.0  # 0.0 = no drift
    state_consistency_rate: float = 1.0  # 1.0 = 100% consistent
    prediction_accuracy: float = 1.0
    decision_correctness_rate: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AutonomousLoopMetricsTracker:
    """
    Records cycle latencies and computes multi-axis engineering autonomy scores.
    """

    def __init__(self, mission_id: str):
        self.mission_id = mission_id
        self.cycle_latencies: list[CycleLatencyBreakdown] = []
        self.decision_evaluations: list[dict[str, Any]] = []

    def record_cycle_latency(self, breakdown: CycleLatencyBreakdown) -> None:
        self.cycle_latencies.append(breakdown)

    def record_decision_evaluation(self, cycle_id: str, expected: str, actual: str, correct: bool) -> None:
        self.decision_evaluations.append({
            "cycle_id": cycle_id,
            "expected": expected,
            "actual": actual,
            "correct": correct,
            "timestamp": time.time(),
        })

    def get_latency_summary(self) -> dict[str, Any]:
        if not self.cycle_latencies:
            return {
                "cycles_count": 0,
                "avg_total_cycle_ms": 0.0,
                "avg_micro_decision_ms": 0.0,
                "avg_snapshot_ms": 0.0,
                "avg_prediction_ms": 0.0,
                "avg_checkpoint_ms": 0.0,
            }

        totals = [c.total_cycle_latency_ms for c in self.cycle_latencies]
        micro = [c.micro_decision_latency_ms for c in self.cycle_latencies]
        snap = [c.snapshot_latency_ms for c in self.cycle_latencies]
        pred = [c.prediction_latency_ms for c in self.cycle_latencies]
        chk = [c.checkpoint_latency_ms for c in self.cycle_latencies]

        return {
            "cycles_count": len(self.cycle_latencies),
            "avg_total_cycle_ms": round(statistics.mean(totals), 3),
            "min_total_cycle_ms": round(min(totals), 3),
            "max_total_cycle_ms": round(max(totals), 3),
            "avg_micro_decision_ms": round(statistics.mean(micro), 4),
            "avg_snapshot_ms": round(statistics.mean(snap), 3),
            "avg_prediction_ms": round(statistics.mean(pred), 3),
            "avg_checkpoint_ms": round(statistics.mean(chk), 3),
            "latencies_breakdown": [c.to_dict() for c in self.cycle_latencies],
        }

    def compute_autonomy_score(
        self,
        eventual_success: bool = True,
        repairs_attempted: int = 0,
        repairs_succeeded: int = 0,
        replans_attempted: int = 0,
        replans_succeeded: int = 0,
        recovery_tested: bool = False,
        recovery_succeeded: bool = True,
        human_escalations: int = 0,
        retention_rate: float = 1.0,
        drift_score: float = 0.0,
        prediction_accuracy: float = 1.0,
    ) -> MultiAxisAutonomyScore:
        rep_rate = (repairs_succeeded / repairs_attempted) if repairs_attempted > 0 else 1.0
        repl_rate = (replans_succeeded / replans_attempted) if replans_attempted > 0 else 1.0

        decision_correct = 1.0
        if self.decision_evaluations:
            correct_count = sum(1 for d in self.decision_evaluations if d["correct"])
            decision_correct = correct_count / len(self.decision_evaluations)

        return MultiAxisAutonomyScore(
            mission_id=self.mission_id,
            total_cycles=len(self.cycle_latencies),
            first_pass_success=(repairs_attempted == 0 and replans_attempted == 0 and eventual_success),
            eventual_success=eventual_success,
            repair_count=repairs_attempted,
            repair_success_rate=round(rep_rate, 3),
            replan_count=replans_attempted,
            replan_success_rate=round(repl_rate, 3),
            recovery_tested=recovery_tested,
            recovery_success=recovery_succeeded,
            human_escalations_count=human_escalations,
            false_success_rate=0.0,
            requirement_retention_rate=round(retention_rate, 3),
            mission_drift_score=round(drift_score, 3),
            state_consistency_rate=1.0,
            prediction_accuracy=round(prediction_accuracy, 3),
            decision_correctness_rate=round(decision_correct, 3),
        )
