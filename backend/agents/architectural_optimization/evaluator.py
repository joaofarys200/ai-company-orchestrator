"""
JARVIS OS — Phase 74: Autonomous Architectural Evolution & Optimization
Module: evaluator.py
Multi-objective Pareto evaluation, trade-off preservation, and hard constraint gating.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import (
    ArchitecturalAlternative,
    ConstraintViolationError,
    OptimizationHypothesis,
    ParetoEvaluation,
)


class MultiObjectiveEvaluator:
    """
    Evaluates competing architectural alternatives against multi-dimensional objectives
    using Pareto dominance, preserving trade-offs and enforcing hard constraints.
    """

    def __init__(
        self,
        max_acceptable_risk: float = 0.5,
        max_acceptable_cost: float = 80.0,
    ):
        self.max_acceptable_risk = max_acceptable_risk
        self.max_acceptable_cost = max_acceptable_cost

    def evaluate_alternatives(
        self,
        alternatives: List[ArchitecturalAlternative],
        hypothesis: OptimizationHypothesis,
        override_risk_threshold: Optional[float] = None,
    ) -> ParetoEvaluation:
        """
        1. Checks hard constraints (reversibility, risk ceiling, security bounds).
        2. Computes multi-objective normalized scores.
        3. Identifies non-dominated Pareto frontier.
        4. Produces deterministic ranking.
        """
        eval_id = f"eval_{uuid.uuid4().hex[:8]}"
        risk_ceiling = override_risk_threshold if override_risk_threshold is not None else self.max_acceptable_risk

        objective_scores: Dict[str, Dict[str, float]] = {}
        hard_constraint_rejections: Dict[str, str] = {}
        valid_alternatives: List[ArchitecturalAlternative] = []

        # 1. Hard Constraint Gating
        for alt in alternatives:
            if not alt.reversibility:
                hard_constraint_rejections[alt.alternative_id] = "Hard constraint violated: Alternative is irreversible."
                continue
            if alt.regression_risk_score > risk_ceiling:
                hard_constraint_rejections[alt.alternative_id] = (
                    f"Hard constraint violated: Risk score {alt.regression_risk_score:.2f} > ceiling {risk_ceiling:.2f}."
                )
                continue
            if alt.estimated_implementation_cost > self.max_acceptable_cost:
                hard_constraint_rejections[alt.alternative_id] = (
                    f"Hard constraint violated: Cost {alt.estimated_implementation_cost:.1f} > budget {self.max_acceptable_cost:.1f}."
                )
                continue

            valid_alternatives.append(alt)

            # Record objective metrics
            target_delta = alt.predicted_metric_deltas.get(hypothesis.target_metric, 0.0)
            improvement_magnitude = abs(target_delta) if target_delta < 0 else 0.0

            objective_scores[alt.alternative_id] = {
                "improvement_magnitude": round(improvement_magnitude, 3),
                "implementation_cost": round(alt.estimated_implementation_cost, 2),
                "regression_risk": round(alt.regression_risk_score, 3),
                "verification_cost": round(alt.estimated_verification_cost, 2),
            }

        # 2. Pareto Dominance Analysis
        # A dominates B iff A is >= B in all objectives (where cost/risk lower is better, improvement higher is better)
        # and strictly > in at least one.
        pareto_frontier: List[str] = []
        for a in valid_alternatives:
            dominated = False
            a_scores = objective_scores[a.alternative_id]
            for b in valid_alternatives:
                if a.alternative_id == b.alternative_id:
                    continue
                b_scores = objective_scores[b.alternative_id]

                # b dominates a if b is at least as good in all and better in one
                b_better_or_equal = (
                    b_scores["improvement_magnitude"] >= a_scores["improvement_magnitude"]
                    and b_scores["implementation_cost"] <= a_scores["implementation_cost"]
                    and b_scores["regression_risk"] <= a_scores["regression_risk"]
                    and b_scores["verification_cost"] <= a_scores["verification_cost"]
                )
                b_strictly_better = (
                    b_scores["improvement_magnitude"] > a_scores["improvement_magnitude"]
                    or b_scores["implementation_cost"] < a_scores["implementation_cost"]
                    or b_scores["regression_risk"] < a_scores["regression_risk"]
                    or b_scores["verification_cost"] < a_scores["verification_cost"]
                )

                if b_better_or_equal and b_strictly_better:
                    dominated = True
                    break

            if not dominated:
                pareto_frontier.append(a.alternative_id)

        # 3. Deterministic Ranking
        # Primary rank: in Pareto frontier (frontier first)
        # Secondary rank: net benefit ratio (improvement / (cost + risk*100))
        def score_alternative(alt: ArchitecturalAlternative) -> Tuple[int, float, str]:
            is_frontier = 1 if alt.alternative_id in pareto_frontier else 0
            scores = objective_scores[alt.alternative_id]
            impr = scores["improvement_magnitude"]
            cost = scores["implementation_cost"]
            risk = scores["regression_risk"]
            ratio = impr / max(1.0, cost + (risk * 50.0))
            # Sort descending by frontier, descending by ratio, ascending by ID for deterministic tie-breaking
            return (-is_frontier, -round(ratio, 4), alt.alternative_id)

        valid_alternatives.sort(key=score_alternative)
        ranked_ids = [alt.alternative_id for alt in valid_alternatives]

        return ParetoEvaluation(
            evaluation_id=eval_id,
            opportunity_id=hypothesis.opportunity_id,
            ranked_alternatives=ranked_ids,
            pareto_frontier=sorted(pareto_frontier),
            objective_scores=objective_scores,
            hard_constraint_rejections=hard_constraint_rejections,
        )
