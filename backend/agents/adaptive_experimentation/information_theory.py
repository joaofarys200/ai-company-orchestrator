"""
JARVIS OS — Phase 79: Autonomous Adaptive Experimentation & Scientific Hypothesis Validation
Module: information_theory.py
Mathematical implementations of Shannon entropy, conditional entropy,
Expected Information Gain (EIG), and cost/risk penalized net expected utility.
"""

from __future__ import annotations

import math
from typing import Dict, List

from .models import CandidateExperiment, ScientificHypothesis


class InformationTheoreticEngine:
    """
    Computes information-theoretic metrics for hypothesis spaces and candidate experiments.
    """

    @staticmethod
    def calculate_entropy(probabilities: List[float]) -> float:
        """
        Calculates Shannon entropy in bits for a discrete probability distribution.
        H(X) = -sum(p * log2(p)) for p > 0.
        """
        if not probabilities:
            return 0.0

        total = sum(probabilities)
        if total <= 0.0:
            return 0.0

        # Normalize
        normalized = [p / total for p in probabilities if p > 0.0]
        entropy = 0.0
        for p in normalized:
            entropy -= p * math.log2(p)

        return max(0.0, round(entropy, 4))

    @classmethod
    def calculate_expected_conditional_entropy(
        cls,
        hypotheses: List[ScientificHypothesis],
        experiment: CandidateExperiment,
    ) -> float:
        """
        Computes E[H(H | E)] = sum_j P(o_j) * H(H | o_j)
        over all possible discrete outcomes of experiment E.
        """
        priors = {h.hypothesis_id: max(0.0, h.posterior_probability) for h in hypotheses}
        total_prior = sum(priors.values())
        if total_prior > 0:
            priors = {hid: p / total_prior for hid, p in priors.items()}

        hyp_ids = list(priors.keys())
        outcomes_dict = {k: dict(v) for k, v in experiment.outcome_likelihoods.items()}

        # Auto-complement if outcomes do not sum to 1.0
        complement_needed = False
        complement_likelihoods = {}
        for hid in hyp_ids:
            p_sum = sum(outcomes_dict[o].get(hid, 0.0) for o in outcomes_dict)
            if p_sum < 0.999:
                complement_needed = True
                complement_likelihoods[hid] = max(0.0, 1.0 - p_sum)
            else:
                complement_likelihoods[hid] = 0.0

        if complement_needed:
            outcomes_dict["__COMPLEMENT__"] = complement_likelihoods

        expected_cond_entropy = 0.0

        for outcome, likelihoods in outcomes_dict.items():
            # Marginal probability of this outcome: P(o_j) = sum_i P(o_j | H_i) * P(H_i)
            p_outcome = sum(
                likelihoods.get(hid, 0.0) * priors.get(hid, 0.0)
                for hid in priors
            )

            if p_outcome <= 0.0:
                continue

            # Compute posterior for each hypothesis given outcome: P(H_i | o_j)
            posteriors_given_o = []
            for hid in priors:
                p_hi_given_o = (likelihoods.get(hid, 0.0) * priors[hid]) / p_outcome
                posteriors_given_o.append(p_hi_given_o)

            # Entropy of hypothesis space conditioned on this outcome
            h_given_o = cls.calculate_entropy(posteriors_given_o)
            expected_cond_entropy += p_outcome * h_given_o

        return round(expected_cond_entropy, 4)

    @classmethod
    def calculate_expected_information_gain(
        cls,
        hypotheses: List[ScientificHypothesis],
        experiment: CandidateExperiment,
    ) -> float:
        """
        Calculates Expected Information Gain (EIG):
        EIG(E) = H(H) - E[H(H | E)]
        """
        priors = [h.posterior_probability for h in hypotheses]
        prior_entropy = cls.calculate_entropy(priors)
        cond_entropy = cls.calculate_expected_conditional_entropy(hypotheses, experiment)

        eig = max(0.0, prior_entropy - cond_entropy)
        return round(eig, 4)

    @staticmethod
    def calculate_utility(
        eig: float,
        cost: float,
        risk: float,
        lambda_cost: float = 1.0,
        lambda_risk: float = 1.0,
    ) -> float:
        """
        Computes Net Expected Utility balancing Information Gain against Cost and Operational Risk:
        U(E) = EIG(E) / (1.0 + lambda_c * cost + lambda_r * risk)
        """
        c = max(0.0, float(cost))
        r = max(0.0, float(risk))
        denominator = 1.0 + (lambda_cost * c) + (lambda_risk * r)

        if denominator <= 0:
            return 0.0

        utility = max(0.0, eig) / denominator
        return round(utility, 4)
