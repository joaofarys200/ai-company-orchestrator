"""
JARVIS OS — Phase 68: Behavior Quality Evaluator
Integrates F50 (Behavioral Contract Proof) and F51 (Bounded Behavioral Exploration).

Measures:
- invariant coverage
- counterexamples
- behavioral drift
- retry behavior
- ordering guarantees
- concurrency safety
- idempotency
- state transitions

Invariant:
Never treat absence of counterexamples as universal proof of correctness.
Always assign non-zero uncertainty proportional to unreached state space.
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


class BehaviorQualityEvaluator:
    """
    Evaluates behavioral contracts, temporal state invariants, and counterexamples.
    """

    def __init__(self) -> None:
        pass

    def evaluate(
        self,
        context: Optional[Dict[str, Any]] = None,
        scope: str = "global",
    ) -> DimensionEvaluation:
        ctx = context or {}
        b_data = ctx.get("behavior", {})

        invariant_cov = float(b_data.get("invariant_coverage", 0.82))
        counterexamples = int(b_data.get("counterexamples", 0))
        behavioral_drift = int(b_data.get("behavioral_drift", 0))
        retry_behavior_ok = bool(b_data.get("retry_behavior_ok", True))
        ordering_ok = bool(b_data.get("ordering_ok", True))
        concurrency_ok = bool(b_data.get("concurrency_ok", True))
        idempotency_ok = bool(b_data.get("idempotency_ok", True))
        valid_transitions_pct = float(b_data.get("state_transitions_valid_pct", 0.98))
        state_space_explored = float(b_data.get("state_space_explored_pct", 0.70))

        # Explicit non-zero uncertainty: unreached state space yields uncertainty
        behavioral_uncertainty = max(0.08, float(1.0 - state_space_explored))

        observations = [
            QualityObservation(
                dimension=QualityDimension.BEHAVIOR,
                metric_name="invariant_coverage",
                measured_value=invariant_cov,
                evidence={"invariant_pct": invariant_cov},
                uncertainty=0.03,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.BEHAVIOR,
                metric_name="counterexamples",
                measured_value=counterexamples,
                evidence={"counterexample_traces": counterexamples},
                uncertainty=0.01,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.BEHAVIOR,
                metric_name="behavioral_drift",
                measured_value=behavioral_drift,
                evidence={"divergent_temporal_properties": behavioral_drift},
                uncertainty=0.05,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.BEHAVIOR,
                metric_name="idempotency",
                measured_value=idempotency_ok,
                evidence={"idempotency_verified": idempotency_ok},
                uncertainty=0.04,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.BEHAVIOR,
                metric_name="concurrency",
                measured_value=concurrency_ok,
                evidence={"race_conditions_absent": concurrency_ok},
                uncertainty=0.10,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.BEHAVIOR,
                metric_name="state_transitions_valid_pct",
                measured_value=valid_transitions_pct,
                evidence={"valid_transitions_ratio": valid_transitions_pct},
                uncertainty=0.02,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.BEHAVIOR,
                metric_name="state_space_explored_pct",
                measured_value=state_space_explored,
                evidence={"explored_state_fraction": state_space_explored},
                uncertainty=0.05,
                scope=scope,
                observation_type=ObservationType.ESTIMATED,
            ),
        ]

        if counterexamples > 0 or not concurrency_ok or not ordering_ok:
            status = DimensionStatus.DEGRADED
        elif behavioral_drift > 0 or valid_transitions_pct < 0.90:
            status = DimensionStatus.DEGRADED
        else:
            status = DimensionStatus.HEALTHY

        summary = (
            f"Behavior status {status.value}: counterexamples={counterexamples}, "
            f"drift={behavioral_drift}, invariant_cov={invariant_cov:.1%}, "
            f"explored={state_space_explored:.1%}, uncertainty={behavioral_uncertainty:.2f}"
        )

        return DimensionEvaluation(
            dimension=QualityDimension.BEHAVIOR,
            observations=observations,
            evidence=[{
                "evaluator": "BehaviorQualityEvaluator",
                "counterexamples": counterexamples,
                "state_space_explored": state_space_explored,
            }],
            uncertainty=behavioral_uncertainty,
            scope=scope,
            status=status,
            summary=summary,
        )

    def compare_behavior(
        self,
        baseline_eval: DimensionEvaluation,
        after_eval: DimensionEvaluation,
    ) -> Tuple[DimensionChange, List[Dict[str, Any]], List[Dict[str, Any]]]:
        base_obs = {o.metric_name: o.measured_value for o in baseline_eval.observations}
        after_obs = {o.metric_name: o.measured_value for o in after_eval.observations}

        degradations = []
        improvements = []

        b_ce = int(base_obs.get("counterexamples", 0))
        a_ce = int(after_obs.get("counterexamples", 0))
        if a_ce > b_ce:
            degradations.append({"metric": "counterexamples", "from": b_ce, "to": a_ce, "reason": "new behavioral counterexamples found"})
        elif a_ce < b_ce:
            improvements.append({"metric": "counterexamples", "from": b_ce, "to": a_ce, "reason": "counterexamples eliminated"})

        b_drift = int(base_obs.get("behavioral_drift", 0))
        a_drift = int(after_obs.get("behavioral_drift", 0))
        if a_drift > b_drift:
            degradations.append({"metric": "behavioral_drift", "from": b_drift, "to": a_drift, "reason": "behavioral drift detected"})
        elif a_drift < b_drift:
            improvements.append({"metric": "behavioral_drift", "from": b_drift, "to": a_drift, "reason": "behavioral drift converged"})

        if degradations and not improvements:
            return DimensionChange.DEGRADED, degradations, improvements
        if improvements and not degradations:
            return DimensionChange.IMPROVED, degradations, improvements
        if degradations and improvements:
            return DimensionChange.UNCERTAIN, degradations, improvements

        return DimensionChange.UNCHANGED, degradations, improvements
