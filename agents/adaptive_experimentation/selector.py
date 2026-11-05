"""
JARVIS OS — Phase 79: Autonomous Adaptive Experimentation & Scientific Hypothesis Validation
Module: selector.py
Selects and ranks candidate experiments based on Expected Information Gain (EIG)
and cost/risk penalized Net Expected Utility.
"""

from __future__ import annotations

from typing import List, Optional

from .information_theory import InformationTheoreticEngine
from .models import CandidateExperiment, ScientificHypothesis


class AdaptiveExperimentSelector:
    """
    Evaluates candidate experiments for information gain, cost, and operational risk,
    selecting the optimal experiment to execute next.
    """

    @classmethod
    def rank_candidate_experiments(
        cls,
        hypotheses: List[ScientificHypothesis],
        candidates: List[CandidateExperiment],
        lambda_cost: float = 1.0,
        lambda_risk: float = 1.0,
    ) -> List[CandidateExperiment]:
        """
        Calculates EIG and utility for all candidate experiments,
        returning them ranked from highest to lowest utility.
        """
        scored_candidates = []
        for exp in candidates:
            eig = InformationTheoreticEngine.calculate_expected_information_gain(hypotheses, exp)
            utility = InformationTheoreticEngine.calculate_utility(
                eig=eig,
                cost=exp.cost,
                risk=exp.risk,
                lambda_cost=lambda_cost,
                lambda_risk=lambda_risk,
            )
            exp.expected_info_gain = eig
            exp.utility_score = utility
            scored_candidates.append(exp)

        # Sort: utility descending, tie-breaking by lower risk, then lower cost
        ranked = sorted(
            scored_candidates,
            key=lambda e: (-e.utility_score, e.risk, e.cost, e.experiment_id),
        )
        return ranked

    @classmethod
    def select_best_experiment(
        cls,
        hypotheses: List[ScientificHypothesis],
        candidates: List[CandidateExperiment],
        min_eig_threshold: float = 0.05,
        lambda_cost: float = 1.0,
        lambda_risk: float = 1.0,
    ) -> Optional[CandidateExperiment]:
        """
        Selects the top-ranked candidate experiment if its expected utility and EIG meet thresholds.
        Returns None if no candidate experiment is sufficiently informative.
        """
        ranked = cls.rank_candidate_experiments(
            hypotheses=hypotheses,
            candidates=candidates,
            lambda_cost=lambda_cost,
            lambda_risk=lambda_risk,
        )

        if not ranked:
            return None

        best = ranked[0]
        if best.expected_info_gain < min_eig_threshold or best.utility_score <= 0.0:
            return None

        return best
