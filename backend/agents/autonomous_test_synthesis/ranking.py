"""
JARVIS OS — Phase 61: Autonomous Test Synthesis & Coverage-Guided Validation
Module: ranking.py
Deterministic, multi-objective ranking of test candidates guided by risk, impact,
coverage gain, cost, and historical failure relevance.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import TestCandidate, TestCandidateStatus


class RiskGuidedTestRanker:
    """
    Ranks candidates using a weighted scoring formula:
    Score = w1*Risk + w2*CovGain + w3*Impact + w4*InvRelevance + w5*FailHistory - w6*Cost + w7*Novelty
    Critical Rule: Never deprioritize critical economic or security tests!
    Tie-breaking is strictly deterministic on test_id.
    """

    def __init__(
        self,
        weight_risk: float = 0.35,
        weight_cov_gain: float = 0.25,
        weight_impact: float = 0.15,
        weight_inv_relevance: float = 0.10,
        weight_fail_history: float = 0.10,
        weight_cost: float = 0.05,
    ) -> None:
        self.w_risk = weight_risk
        self.w_cov = weight_cov_gain
        self.w_impact = weight_impact
        self.w_inv = weight_inv_relevance
        self.w_fail = weight_fail_history
        self.w_cost = weight_cost

    def compute_score(
        self,
        candidate: TestCandidate,
        failure_history: Optional[Dict[str, int]] = None,
        impact_weights: Optional[Dict[str, float]] = None,
    ) -> float:
        fails = failure_history or {}
        impacts = impact_weights or {}

        # 1. Base components
        risk_term = candidate.risk
        cov_term = min(1.0, candidate.predicted_coverage_gain)
        impact_term = impacts.get(candidate.target, 0.5)

        # 2. Invariant relevance
        inv_term = min(1.0, len(candidate.invariants) * 0.5)

        # 3. Failure history term
        fail_count = fails.get(candidate.target, 0)
        fail_term = min(1.0, fail_count * 0.25)

        # 4. Normalized cost penalty
        cost_term = min(1.0, candidate.estimated_cost.total_cost / 0.50)

        # 5. Security & Economic Criticality Override
        is_security_or_economic = (
            "security" in candidate.provenance.lower()
            or "economic" in candidate.provenance.lower()
            or candidate.risk >= 0.95
        )

        score = (
            self.w_risk * risk_term
            + self.w_cov * cov_term
            + self.w_impact * impact_term
            + self.w_inv * inv_term
            + self.w_fail * fail_term
            - self.w_cost * cost_term
        )

        if is_security_or_economic:
            # Critical boost ensuring top tier ranking
            score += 2.0

        return round(score, 5)

    def rank_candidates(
        self,
        candidates: List[TestCandidate],
        failure_history: Optional[Dict[str, int]] = None,
        impact_weights: Optional[Dict[str, float]] = None,
    ) -> List[TestCandidate]:
        """Sort candidates descending by score with deterministic test_id tie-breaking."""

        def sort_key(cand: TestCandidate) -> tuple:
            score = self.compute_score(cand, failure_history, impact_weights)
            # Tuple for sorting: (-score, candidate.test_id)
            # In Python, string comparison on test_id provides strict determinism
            return (-score, cand.test_id)

        ranked = sorted(candidates, key=sort_key)
        for c in ranked:
            c.status = TestCandidateStatus.RANKED
        return ranked
