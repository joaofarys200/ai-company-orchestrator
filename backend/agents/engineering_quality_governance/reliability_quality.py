"""
JARVIS OS — Phase 68: Reliability Quality Evaluator
Integrates F53–F67 (Preflight, Repair, Convergence, Watchdog, State Partitioning,
Coordination, and Mission Lifecycles).

Measures:
- recovery success rate
- rollback success rate
- residual state count
- crash recovery count
- mission stalls
- oscillations (oscillation index)
- agent failures
- retry count
- human review frequency
- incomplete missions

Tracks trends over historical runs.
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


class ReliabilityQualityEvaluator:
    """
    Evaluates system resilience, recovery mechanics, and stability under faults.
    """

    def __init__(self, thresholds: Optional[Dict[str, float]] = None) -> None:
        self.thresholds = thresholds or {
            "min_recovery_success": 0.90,
            "min_rollback_success": 0.95,
            "max_residual_states": 0,
            "max_mission_stalls": 0,
            "max_oscillations": 0,
            "max_incomplete_missions": 0,
        }

    def evaluate(
        self,
        context: Optional[Dict[str, Any]] = None,
        scope: str = "global",
    ) -> DimensionEvaluation:
        ctx = context or {}
        rel_data = ctx.get("reliability", {})

        rec_success = float(rel_data.get("recovery_success", 1.0))
        rb_success = float(rel_data.get("rollback_success", 1.0))
        residuals = int(rel_data.get("residual_states", 0))
        crash_recoveries = int(rel_data.get("crash_recovery_count", 0))
        stalls = int(rel_data.get("mission_stalls", 0))
        oscillations = int(rel_data.get("oscillations", 0))
        agent_failures = int(rel_data.get("agent_failures", 0))
        retry_count = int(rel_data.get("retry_count", 2))
        human_review_freq = float(rel_data.get("human_review_frequency", 0.05))
        incomplete_missions = int(rel_data.get("incomplete_missions", 0))

        observations = [
            QualityObservation(
                dimension=QualityDimension.RELIABILITY,
                metric_name="recovery_success",
                measured_value=rec_success,
                evidence={"successful_recoveries_ratio": rec_success},
                uncertainty=0.02,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.RELIABILITY,
                metric_name="rollback_success",
                measured_value=rb_success,
                evidence={"successful_rollbacks_ratio": rb_success},
                uncertainty=0.01,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.RELIABILITY,
                metric_name="residual_states",
                measured_value=residuals,
                evidence={"orphaned_resources_or_locks": residuals},
                uncertainty=0.01,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.RELIABILITY,
                metric_name="crash_recovery_count",
                measured_value=crash_recoveries,
                evidence={"watchdog_crash_recoveries": crash_recoveries},
                uncertainty=0.01,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.RELIABILITY,
                metric_name="mission_stalls",
                measured_value=stalls,
                evidence={"watchdog_stalls_flagged": stalls},
                uncertainty=0.01,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.RELIABILITY,
                metric_name="oscillations",
                measured_value=oscillations,
                evidence={"ping_pong_repair_or_plan_loops": oscillations},
                uncertainty=0.01,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.RELIABILITY,
                metric_name="agent_failures",
                measured_value=agent_failures,
                evidence={"subagent_abnormal_terminations": agent_failures},
                uncertainty=0.02,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.RELIABILITY,
                metric_name="retry_count",
                measured_value=retry_count,
                evidence={"automated_retries_executed": retry_count},
                uncertainty=0.02,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.RELIABILITY,
                metric_name="human_review_frequency",
                measured_value=human_review_freq,
                evidence={"human_escalations_per_mission": human_review_freq},
                uncertainty=0.03,
                scope=scope,
                observation_type=ObservationType.ESTIMATED,
            ),
            QualityObservation(
                dimension=QualityDimension.RELIABILITY,
                metric_name="incomplete_missions",
                measured_value=incomplete_missions,
                evidence={"aborted_or_budget_exhausted_missions": incomplete_missions},
                uncertainty=0.01,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
        ]

        is_degraded = (
            rec_success < self.thresholds["min_recovery_success"]
            or rb_success < self.thresholds["min_rollback_success"]
            or residuals > self.thresholds["max_residual_states"]
            or stalls > self.thresholds["max_mission_stalls"]
            or oscillations > self.thresholds["max_oscillations"]
            or incomplete_missions > self.thresholds["max_incomplete_missions"]
        )

        status = DimensionStatus.DEGRADED if is_degraded else DimensionStatus.HEALTHY
        summary = (
            f"Reliability status {status.value}: recovery={rec_success:.1%}, "
            f"rollback={rb_success:.1%}, residuals={residuals}, "
            f"stalls={stalls}, oscillations={oscillations}, failures={agent_failures}"
        )

        return DimensionEvaluation(
            dimension=QualityDimension.RELIABILITY,
            observations=observations,
            evidence=[{
                "evaluator": "ReliabilityQualityEvaluator",
                "recovery_success": rec_success,
                "stalls": stalls,
                "oscillations": oscillations,
            }],
            uncertainty=0.03,
            scope=scope,
            status=status,
            summary=summary,
        )

    def compare_reliability(
        self,
        baseline_eval: DimensionEvaluation,
        after_eval: DimensionEvaluation,
    ) -> Tuple[DimensionChange, List[Dict[str, Any]], List[Dict[str, Any]]]:
        base_obs = {o.metric_name: o.measured_value for o in baseline_eval.observations}
        after_obs = {o.metric_name: o.measured_value for o in after_eval.observations}

        degradations = []
        improvements = []

        b_stalls = int(base_obs.get("mission_stalls", 0))
        a_stalls = int(after_obs.get("mission_stalls", 0))
        if a_stalls > b_stalls:
            degradations.append({"metric": "mission_stalls", "from": b_stalls, "to": a_stalls, "reason": "mission stalls emerged"})
        elif a_stalls < b_stalls:
            improvements.append({"metric": "mission_stalls", "from": b_stalls, "to": a_stalls, "reason": "mission stalls resolved"})

        b_osc = int(base_obs.get("oscillations", 0))
        a_osc = int(after_obs.get("oscillations", 0))
        if a_osc > b_osc:
            degradations.append({"metric": "oscillations", "from": b_osc, "to": a_osc, "reason": "repair oscillations detected"})
        elif a_osc < b_osc:
            improvements.append({"metric": "oscillations", "from": b_osc, "to": a_osc, "reason": "oscillations dampened"})

        b_res = int(base_obs.get("residual_states", 0))
        a_res = int(after_obs.get("residual_states", 0))
        if a_res > b_res:
            degradations.append({"metric": "residual_states", "from": b_res, "to": a_res, "reason": "residual states accumulated"})
        elif a_res < b_res:
            improvements.append({"metric": "residual_states", "from": b_res, "to": a_res, "reason": "residual states cleaned"})

        if degradations and not improvements:
            return DimensionChange.DEGRADED, degradations, improvements
        if improvements and not degradations:
            return DimensionChange.IMPROVED, degradations, improvements
        if degradations and improvements:
            return DimensionChange.UNCERTAIN, degradations, improvements

        return DimensionChange.UNCHANGED, degradations, improvements
