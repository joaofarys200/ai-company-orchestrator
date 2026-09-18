"""
JARVIS OS — Phase 63: Cross-Project Engineering Learning & Verification Transfer
Module: retrieval.py
Hybrid retrieval engine combining structural fingerprints, contract graphs, and historical memory.
Selects and ranks CandidateKnowledge items using multi-axis scoring.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Sequence

from .knowledge import KnowledgeManager
from .models import (
    CandidateKnowledge,
    EngineeringKnowledgeItem,
    KnowledgeCategory,
    KnowledgeState,
    ProjectFingerprint,
)
from .similarity import SimilarityEngine


class HybridKnowledgeRetriever:
    """Retrieves and ranks candidate engineering knowledge items against a target project."""

    def __init__(self, knowledge_manager: KnowledgeManager) -> None:
        self.km = knowledge_manager

    def retrieve(
        self,
        target_fingerprint: ProjectFingerprint,
        category: Optional[KnowledgeCategory] = None,
        query_intent: str = "",
        min_score: float = 0.25,
        limit: int = 10,
    ) -> List[CandidateKnowledge]:
        """
        Perform hybrid retrieval across structural, domain, and experience dimensions.
        Strict rule: Never rank solely by textual similarity.
        """
        all_items = self.km.list_items(category=category)
        candidates: List[CandidateKnowledge] = []

        query_keywords = [w.lower() for w in query_intent.split() if len(w) > 3]

        for item in all_items:
            # Filter out rejected or conflicted items
            if item.state in (KnowledgeState.REJECTED, KnowledgeState.CONFLICTED):
                continue

            # Invariant: Never retrieve unvalidated OBSERVED items for transfer
            if item.state == KnowledgeState.OBSERVED:
                continue

            # Calculate multidimensional structural similarity
            sim_score, matching_dims, missing_dims = SimilarityEngine.evaluate_item_similarity(
                item=item,
                target_fp=target_fingerprint,
            )

            # Intent keyword alignment (only auxiliary bonus, never primary!)
            pattern_text = str(item.pattern) + " " + str(item.context) + " " + " ".join(item.preconditions)
            pattern_lower = pattern_text.lower()
            keyword_hits = sum(1 for kw in query_keywords if kw in pattern_lower)
            if query_keywords:
                intent_ratio = keyword_hits / len(query_keywords)
                if intent_ratio > 0.3:
                    matching_dims.append(f"intent_alignment_{intent_ratio:.2f}")
                sim_score = (sim_score * 0.85) + (0.15 * intent_ratio)

            # Contradiction checks
            contradictions: List[str] = []
            if item.state == KnowledgeState.STALE:
                contradictions.append("Item is marked STALE due to environment drift")
            if item.harm_count > 0:
                contradictions.append(f"Observed {item.harm_count} historical harm events")
                sim_score *= max(0.2, 1.0 - (0.25 * item.harm_count))

            # Check if source and target are completely incompatible
            if "language_mismatch" in missing_dims and not any("language_overlap" in m for m in matching_dims):
                # Only keep as low confidence hypothesis if cross-language adapter applies
                contradictions.append("Direct language mismatch requiring semantic translation")

            if sim_score >= min_score:
                cand = CandidateKnowledge(
                    item=item,
                    score=round(sim_score, 4),
                    matching_dimensions=matching_dims,
                    missing_dimensions=missing_dims,
                    contradictions=contradictions,
                    provenance=item.provenance,
                    applicability_confidence=round(min(1.0, sim_score * item.confidence), 4),
                )
                candidates.append(cand)

        # Sort descending by composite score
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[:limit]
