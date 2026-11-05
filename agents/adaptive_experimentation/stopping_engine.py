"""
JARVIS OS — Phase 79: Autonomous Adaptive Experimentation & Scientific Hypothesis Validation
Module: stopping_engine.py
Evaluates multi-criteria evidence-grounded stopping rules for adaptive investigations.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from .information_theory import InformationTheoreticEngine
from .models import CandidateExperiment, ScientificHypothesis, StoppingReason


class AdaptiveStoppingEvaluator:
    """
    Evaluates evidence-based stopping criteria for adaptive investigations.
    """

    CONFIRMATION_THRESHOLD = 0.85
    MINIMAL_ENTROPY_THRESHOLD = 0.25
    MINIMAL_EIG_THRESHOLD = 0.05

    @classmethod
    def evaluate_stopping_criteria(
        cls,
        hypotheses: List[ScientificHypothesis],
        remaining_candidates: List[CandidateExperiment],
        accumulated_cost: float,
        cost_budget: float,
    ) -> Tuple[bool, Optional[StoppingReason], str]:
        """
        Determines whether the investigation should terminate or continue.
        Returns (should_stop, stopping_reason, rationale).
        """
        if not hypotheses:
            return True, StoppingReason.CONTRADICTED_INCONCLUSIVE, "No hypotheses in space."

        # 1. Hypothesis Confirmation: check if leading hypothesis meets threshold
        top_h = max(hypotheses, key=lambda h: h.posterior_probability)
        if top_h.posterior_probability >= cls.CONFIRMATION_THRESHOLD:
            return (
                True,
                StoppingReason.HYPOTHESIS_CONFIRMED,
                f"Hypothesis '{top_h.hypothesis_id}' confirmed with probability {top_h.posterior_probability:.3f} >= {cls.CONFIRMATION_THRESHOLD}.",
            )

        # 2. Minimal Uncertainty: entropy is negligible
        probs = [h.posterior_probability for h in hypotheses]
        current_entropy = InformationTheoreticEngine.calculate_entropy(probs)
        if current_entropy <= cls.MINIMAL_ENTROPY_THRESHOLD:
            return (
                True,
                StoppingReason.MINIMAL_UNCERTAINTY,
                f"Remaining entropy {current_entropy:.3f} bits <= {cls.MINIMAL_ENTROPY_THRESHOLD} bits.",
            )

        # 3. Budget Exhausted
        if accumulated_cost >= cost_budget:
            return (
                True,
                StoppingReason.BUDGET_EXHAUSTED,
                f"Accumulated cost {accumulated_cost:.2f} reached or exceeded budget {cost_budget:.2f}.",
            )

        # 4. No safe candidate experiments remain
        safe_candidates = [e for e in remaining_candidates if e.is_read_only or not e.requires_authorization]
        if not safe_candidates:
            return (
                True,
                StoppingReason.NO_SAFE_EXPERIMENTS_REMAIN,
                "No safe or authorized experiments remain in the candidate pool.",
            )

        # 5. Diminishing Information Gain
        max_eig = max((e.expected_info_gain for e in safe_candidates), default=0.0)
        if max_eig < cls.MINIMAL_EIG_THRESHOLD:
            return (
                True,
                StoppingReason.DIMINISHING_INFORMATION_GAIN,
                f"Maximum remaining EIG {max_eig:.3f} bits is below threshold {cls.MINIMAL_EIG_THRESHOLD} bits.",
            )

        # Investigation continues
        return False, None, "Investigation continues: informative safe experiments remain within budget."
