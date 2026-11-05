"""
JARVIS OS — Phase 78: Autonomous Causal Diagnosis & Root-Cause Analysis
Module: confidence.py
Mathematically derives calibrated confidence and uncertainty intervals for causal hypotheses,
rejecting arbitrary static model confidence scores.
"""

from __future__ import annotations

from typing import List, Tuple

from .models import CausalHypothesis, HypothesisStatus


class ConfidenceCalculator:
    """
    Computes calibrated confidence metrics based on evidence completeness,
    contradiction absence, and uncertainty penalties.
    """

    @staticmethod
    def calculate_hypothesis_confidence(
        supporting_evidence_count: int,
        contradicting_evidence_count: int,
        missing_evidence_count: int,
        has_uncertain_timestamps: bool = False,
        is_synthetic_only: bool = False,
    ) -> Tuple[float, float, Tuple[float, float], HypothesisStatus]:
        """
        Calculates calibrated confidence in [0.0, 1.0], uncertainty penalty,
        confidence interval [lower, upper], and recommended HypothesisStatus.
        """
        Ns = max(0, supporting_evidence_count)
        Nc = max(0, contradicting_evidence_count)
        Nm = max(0, missing_evidence_count)

        # Calculate uncertainty penalty
        penalty = 0.0
        if has_uncertain_timestamps:
            penalty += 0.15
        if is_synthetic_only:
            penalty += 0.20

        # If zero supporting evidence, confidence is 0.0
        if Ns == 0:
            return 0.0, penalty, (0.0, 0.1), HypothesisStatus.INCONCLUSIVE

        # Contradictions are heavily penalized (weighted 2x)
        denominator = Ns + (2 * Nc) + Nm
        if denominator == 0:
            raw_confidence = 0.0
        else:
            raw_confidence = Ns / denominator

        # Bayesian evidence scaling: reward multiple corroborating evidence items over single anecdotes
        evidence_scale = 1.0 - (0.3 / (Ns + 1.0))
        calibrated_confidence = max(0.0, min(1.0, raw_confidence * evidence_scale * (1.0 - penalty)))

        # Derive interval
        margin = max(0.05, (penalty + (0.5 / (Ns + 1))) / 2.0)
        lower_bound = max(0.0, round(calibrated_confidence - margin, 3))
        upper_bound = min(1.0, round(calibrated_confidence + margin, 3))

        # Determine status
        if Nc > 0 and Nc >= Ns:
            status = HypothesisStatus.REJECTED
        elif calibrated_confidence >= 0.70 and Nc == 0 and Nm == 0:
            status = HypothesisStatus.CONFIRMED
        elif calibrated_confidence >= 0.45 and Nc == 0:
            status = HypothesisStatus.SUPPORTED
        else:
            status = HypothesisStatus.INCONCLUSIVE

        return round(calibrated_confidence, 3), round(penalty, 3), (lower_bound, upper_bound), status
