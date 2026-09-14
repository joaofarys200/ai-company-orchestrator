"""
JARVIS OS — Phase 42: Deterministic Causal Experience Retriever
Retrieves and ranks relevant operational experiences based on structured similarity,
enforcing the Anti-Leakage Guarantee and generating verifiable explanations.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from agents.experience_memory.index import ExperienceIndex
from agents.experience_memory.models import (
    ExperienceApplicabilityRating,
    ExperienceRecord,
    MemoryInfluenceType,
    RelevantExperience,
    TemporalValidity,
)
from agents.experience_memory.signature import IntentNormalizer
from agents.experience_memory.storage import ExperienceStorage


class ExperienceRetriever:
    """Retrieves operational experiences matching current mission context without vector embeddings."""

    def __init__(self, storage: ExperienceStorage, index: ExperienceIndex):
        self.storage = storage
        self.index = index

    def retrieve(
        self,
        current_intent: str,
        current_observation: dict[str, Any],
        current_mission_state: dict[str, Any],
        architecture_context: dict[str, Any],
        current_decision_context: Optional[str] = None,
        current_mission_timestamp: Optional[float] = None,
        min_relevance_threshold: float = 0.35,
        max_results: int = 5,
    ) -> list[RelevantExperience]:
        """
        Retrieves relevant experiences.
        Enforces strict Anti-Leakage Guarantee:
        created_at must be strictly less than current_mission_timestamp.
        """
        now = current_mission_timestamp or time.time()
        intent_cat, _ = IntentNormalizer.normalize_intent(current_intent)
        tech_list = architecture_context.get("technology", ["vanilla_ts", "python"])
        failure_class = current_observation.get("failure_class", current_observation.get("error_type"))

        # Step 1: Query candidate IDs from index with temporal cut-off
        candidate_ids = self.index.query_candidates(
            intent_category=intent_cat,
            technology=tech_list,
            failure_class=str(failure_class) if failure_class else None,
            decision_context=current_decision_context,
            max_timestamp=now,
        )

        results: list[RelevantExperience] = []

        for exp_id in candidate_ids:
            rec = self.storage.get_experience(exp_id)
            if not rec:
                continue

            # Anti-leakage double check: NEVER allow future records
            if rec.created_at >= now:
                continue

            # Skip hidden experiences
            if rec.curation_status == "HIDE_EXPERIENCE":
                continue

            # Step 2: Compute multi-factor deterministic score
            score, matched_factors, explanation = self._score_experience(
                rec=rec,
                current_intent_cat=intent_cat,
                tech_list=tech_list,
                failure_class=str(failure_class) if failure_class else "NONE",
                decision_context=current_decision_context,
                now=now,
            )

            if score < min_relevance_threshold:
                continue

            # Determine initial applicability rating
            rating = ExperienceApplicabilityRating.RELEVANT
            if rec.temporal_validity == TemporalValidity.STALE or rec.curation_status == "MARK_STALE":
                rating = ExperienceApplicabilityRating.STALE
            elif score < 0.6:
                rating = ExperienceApplicabilityRating.POSSIBLY_RELEVANT

            # Determine allowed influence type
            influence = MemoryInfluenceType.DIAGNOSTIC
            if "repair" in rec.tags or rec.decision == "REPAIR":
                influence = MemoryInfluenceType.REPAIR_HINT
            elif "planning" in rec.tags or rec.decision == "REPLAN":
                influence = MemoryInfluenceType.PLANNING_HINT
            elif "prediction" in rec.tags:
                influence = MemoryInfluenceType.PREDICTION_HINT
            elif rec.decision == "REQUEST_HUMAN":
                influence = MemoryInfluenceType.ESCALATION_HINT

            results.append(
                RelevantExperience(
                    experience=rec,
                    relevance_score=score,
                    applicability=rating,
                    why_relevant=explanation,
                    matched_factors=matched_factors,
                    influence_type=influence,
                )
            )

        # Sort by relevance score descending (pinned experiences get top priority)
        results.sort(
            key=lambda item: (
                1 if item.experience.curation_status == "PIN_EXPERIENCE" else 0,
                item.relevance_score,
            ),
            reverse=True,
        )

        return results[:max_results]

    def _score_experience(
        self,
        rec: ExperienceRecord,
        current_intent_cat: str,
        tech_list: list[str],
        failure_class: str,
        decision_context: Optional[str],
        now: float,
    ) -> tuple[float, list[str], str]:
        score = 0.0
        factors = []
        sig = rec.intent_signature

        # 1. Intent Category Match (35%)
        if sig.intent_category.upper() == current_intent_cat.upper():
            score += 0.35
            factors.append(f"same requirement category ({sig.intent_category})")

        # 2. Technology Stack Overlap (25%)
        cur_tech_set = {t.lower() for t in tech_list}
        rec_tech_set = {t.lower() for t in sig.technology}
        overlap = cur_tech_set.intersection(rec_tech_set)
        if overlap:
            overlap_ratio = len(overlap) / max(len(cur_tech_set), 1)
            tech_score = 0.25 * overlap_ratio
            score += tech_score
            factors.append(f"matching technology stack ({', '.join(sorted(overlap))})")

        # 3. Failure Class Match (20%)
        if failure_class != "NONE" and sig.observed_failure.upper() == failure_class.upper():
            score += 0.20
            factors.append(f"same failure class ({failure_class})")

        # 4. Decision Context Match (10%)
        if decision_context and sig.decision.upper() == decision_context.upper():
            score += 0.10
            factors.append(f"same decision context ({decision_context})")

        # 5. Outcome Proof / Causal Success (10%)
        if rec.outcome and "success" in rec.outcome.lower():
            score += 0.10
            factors.append("validated successful historical outcome")

        # Penalize if stale or old policy version
        if rec.temporal_validity == TemporalValidity.STALE:
            score *= 0.6
            factors.append("marked STALE (penalized)")

        why_text = f"Matched because: {'; '.join(factors)}."
        return min(score, 1.0), factors, why_text
