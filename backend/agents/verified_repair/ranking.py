"""
JARVIS OS — Phase 54: Repair Ranking Engine
Multi-criteria ranking engine evaluating confidence, root cause support, risk, blast radius, and minimality.
"""

from __future__ import annotations

from typing import List, Tuple

from agents.verified_repair.models import RepairCandidate, RepairCandidateRanking


class RepairRankingEngine:
    """
    Ranks repair candidates based on multi-dimensional objective criteria.
    Never blindly picks the first available patch.
    Breaks ties deterministically using repair_id.
    """

    def rank_candidates(
        self,
        candidates: List[RepairCandidate],
        root_cause_confidence: float = 0.90,
    ) -> List[Tuple[RepairCandidate, RepairCandidateRanking]]:
        scored: List[Tuple[float, str, RepairCandidate, RepairCandidateRanking]] = []

        for candidate in candidates:
            conf_score = candidate.confidence
            root_support = root_cause_confidence
            risk_pen = candidate.risk * 0.25
            blast_radius_pen = (len(candidate.files) - 1) * 0.10 + (candidate.predicted_impact.predicted_risk * 0.15)
            minimality_bonus = (candidate.minimality.minimality_score * 0.20) if candidate.minimality else 0.10

            # Composite scoring formula
            total_score = (
                (conf_score * 0.35)
                + (root_support * 0.25)
                + minimality_bonus
                - risk_pen
                - blast_radius_pen
            )
            total_score = max(0.01, min(1.0, total_score))

            rationale = (
                f"Estratégia {candidate.strategy_name}: Confiança={conf_score:.2f}, "
                f"Risco={candidate.risk:.2f}, Minimalidade={minimality_bonus:.2f}"
            )

            ranking_meta = RepairCandidateRanking(
                repair_id=candidate.repair_id,
                rank=0,
                score=total_score,
                confidence_score=conf_score,
                root_cause_support=root_support,
                risk_penalty=risk_pen,
                blast_radius_penalty=blast_radius_pen,
                minimality_bonus=minimality_bonus,
                rationale=rationale,
            )

            # Sort tuple: (-total_score, candidate.repair_id) for deterministic descending sort
            scored.append((-total_score, candidate.repair_id, candidate, ranking_meta))

        scored.sort(key=lambda x: (x[0], x[1]))

        ranked_results: List[Tuple[RepairCandidate, RepairCandidateRanking]] = []
        for rank_idx, (_, _, cand, meta) in enumerate(scored, start=1):
            meta.rank = rank_idx
            ranked_results.append((cand, meta))

        return ranked_results
