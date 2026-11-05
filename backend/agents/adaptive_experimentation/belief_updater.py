"""
JARVIS OS — Phase 79: Autonomous Adaptive Experimentation & Scientific Hypothesis Validation
Module: belief_updater.py
Bayesian belief updater with likelihood matching, contradiction handling, and Laplace smoothing.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .models import CandidateExperiment, ScientificHypothesis


class BayesianBeliefUpdater:
    """
    Applies Bayes' rule to update the probability distribution across competing hypotheses
    in response to empirical experiment observations.
    """

    @classmethod
    def match_observation_to_outcome(
        cls,
        experiment: CandidateExperiment,
        actual_observation: str,
    ) -> Optional[str]:
        """Matches raw observation string to one of the defined discrete outcomes."""
        obs_lower = actual_observation.lower()
        # Direct key match
        for outcome_name in experiment.outcome_likelihoods:
            if outcome_name.lower() in obs_lower:
                return outcome_name
        # Fallback to first outcome if only 1 exists, else None
        if len(experiment.outcome_likelihoods) == 1:
            return list(experiment.outcome_likelihoods.keys())[0]
        return None

    @classmethod
    def update_beliefs(
        cls,
        hypotheses: List[ScientificHypothesis],
        experiment: CandidateExperiment,
        actual_observation: str,
        is_synthetic: bool = False,
    ) -> Tuple[List[ScientificHypothesis], Optional[str]]:
        """
        Updates posterior probabilities of hypotheses using Bayes' rule:
        P(H_i | o) = (P(o | H_i) * P(H_i)) / P(o)
        """
        matched_outcome = cls.match_observation_to_outcome(experiment, actual_observation)
        if not matched_outcome:
            # If observation cannot be matched, beliefs remain unchanged
            return hypotheses, None

        likelihoods = experiment.outcome_likelihoods.get(matched_outcome, {})
        eps = 1e-4  # Laplace smoothing factor

        unnormalized = []
        for h in hypotheses:
            prior = max(1e-5, h.posterior_probability)
            lh = likelihoods.get(h.hypothesis_id, eps)
            unnormalized.append((h, prior * max(eps, lh)))

        total_mass = sum(weight for _, weight in unnormalized)
        if total_mass <= 0:
            total_mass = 1.0

        for h, weight in unnormalized:
            raw_posterior = weight / total_mass
            if is_synthetic:
                # Synthetic fixtures receive a conservative 50% discount towards prior
                final_posterior = (0.5 * h.posterior_probability) + (0.5 * raw_posterior)
            else:
                final_posterior = raw_posterior

            h.posterior_probability = round(final_posterior, 4)

            # Update status
            if h.posterior_probability >= 0.85:
                h.status = "CONFIRMED"
            elif h.posterior_probability >= 0.50:
                h.status = "SUPPORTED"
            elif h.posterior_probability < 0.10:
                h.status = "REJECTED"
            else:
                h.status = "CANDIDATE"

        return hypotheses, matched_outcome
