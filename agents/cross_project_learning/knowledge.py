"""
JARVIS OS — Phase 63: Cross-Project Engineering Learning & Verification Transfer
Module: knowledge.py
Lifecycle manager for EngineeringKnowledgeItem.
Enforces that OBSERVED items can never be promoted to TRANSFERABLE without explicit validation.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from .models import (
    EngineeringKnowledgeItem,
    KnowledgeCategory,
    KnowledgeProvenance,
    KnowledgeState,
)


class KnowledgeManager:
    """Manages creation, promotion, superseding, and deprecation of engineering knowledge items."""

    def __init__(self) -> None:
        self._items: Dict[str, EngineeringKnowledgeItem] = {}

    def create_observed_item(
        self,
        source_project_id: str,
        source_project_fingerprint: str,
        category: KnowledgeCategory,
        pattern: Dict[str, Any],
        context: Dict[str, Any],
        preconditions: List[str],
        observed_effect: Dict[str, Any],
        evidence_scope: Dict[str, Any],
        confidence: float,
        provenance: Optional[KnowledgeProvenance] = None,
        security_classification: str = "INTERNAL",
        expires_in_seconds: Optional[float] = None,
        item_id: Optional[str] = None,
    ) -> EngineeringKnowledgeItem:
        """Create a new item in OBSERVED state. Never starts as TRANSFERABLE."""
        k_id = item_id or f"k_{category.value.lower()[:4]}_{uuid.uuid4().hex[:8]}"
        now = time.time()
        prov = provenance or KnowledgeProvenance(
            source_project_id=source_project_id,
            created_at=now,
        )

        item = EngineeringKnowledgeItem(
            knowledge_id=k_id,
            source_project_id=source_project_id,
            source_project_fingerprint=source_project_fingerprint,
            category=category,
            pattern=pattern,
            context=context,
            preconditions=preconditions,
            observed_effect=observed_effect,
            evidence_scope=evidence_scope,
            confidence=max(0.0, min(1.0, confidence)),
            provenance=prov,
            created_at=now,
            expires_at=(now + expires_in_seconds) if expires_in_seconds else None,
            security_classification=security_classification,
            state=KnowledgeState.OBSERVED,
        )
        self._items[k_id] = item
        return item

    def promote_to_validated(
        self,
        knowledge_id: str,
        validation_evidence: Dict[str, Any],
    ) -> EngineeringKnowledgeItem:
        """Promote an OBSERVED item to VALIDATED once source project evidence is verified."""
        item = self.get_item(knowledge_id)
        if not item:
            raise KeyError(f"Knowledge item not found: {knowledge_id}")
        if item.state not in (KnowledgeState.OBSERVED, KnowledgeState.VALIDATED):
            raise ValueError(f"Cannot promote item in state {item.state} to VALIDATED")

        item.state = KnowledgeState.VALIDATED
        item.evidence_scope["validation_evidence"] = validation_evidence
        return item

    def qualify_for_transfer(
        self,
        knowledge_id: str,
        min_confidence: float = 0.65,
    ) -> EngineeringKnowledgeItem:
        """
        Qualify a VALIDATED item as TRANSFERABLE.
        Strict invariant: Fails if the item is still in OBSERVED state.
        """
        item = self.get_item(knowledge_id)
        if not item:
            raise KeyError(f"Knowledge item not found: {knowledge_id}")

        if item.state == KnowledgeState.OBSERVED:
            raise PermissionError(
                f"Invariant Violation: Cannot promote OBSERVED knowledge {knowledge_id} "
                "directly to TRANSFERABLE without prior validation!"
            )

        if item.state != KnowledgeState.VALIDATED:
            raise ValueError(f"Only VALIDATED items can become TRANSFERABLE, current: {item.state}")

        if item.confidence < min_confidence:
            raise ValueError(f"Confidence {item.confidence} below threshold {min_confidence}")

        item.state = KnowledgeState.TRANSFERABLE
        return item

    def mark_conflicted(self, knowledge_id: str, reason: str) -> EngineeringKnowledgeItem:
        """Flag item as conflicted with another pattern."""
        item = self.get_item(knowledge_id)
        if item:
            item.state = KnowledgeState.CONFLICTED
            item.context["conflict_reason"] = reason
        return item

    def mark_stale(self, knowledge_id: str, reason: str) -> EngineeringKnowledgeItem:
        """Flag item as stale due to environmental or contract evolution."""
        item = self.get_item(knowledge_id)
        if item:
            item.state = KnowledgeState.STALE
            item.context["staleness_reason"] = reason
        return item

    def supersede_item(
        self,
        old_knowledge_id: str,
        new_knowledge_id: str,
    ) -> None:
        """Chain an obsolete item to its replacement."""
        old_item = self.get_item(old_knowledge_id)
        new_item = self.get_item(new_knowledge_id)
        if old_item and new_item:
            old_item.state = KnowledgeState.STALE
            old_item.context["superseded_by"] = new_knowledge_id
            new_item.supersedes = old_knowledge_id

    def register_feedback(
        self,
        knowledge_id: str,
        is_success: bool,
        is_harm: bool,
        penalty: float = 0.15,
        bonus: float = 0.05,
    ) -> None:
        """Adjust confidence based on observed transfer feedback."""
        item = self.get_item(knowledge_id)
        if not item:
            return
        if is_harm:
            item.harm_count += 1
            item.confidence = max(0.05, item.confidence - penalty)
            if item.confidence < 0.25 or item.harm_count >= 3:
                item.state = KnowledgeState.REJECTED
        elif is_success:
            item.success_count += 1
            item.confidence = min(1.0, item.confidence + bonus)

    def get_item(self, knowledge_id: str) -> Optional[EngineeringKnowledgeItem]:
        return self._items.get(knowledge_id)

    def list_items(
        self,
        category: Optional[KnowledgeCategory] = None,
        state: Optional[KnowledgeState] = None,
    ) -> List[EngineeringKnowledgeItem]:
        res = list(self._items.values())
        if category:
            res = [i for i in res if i.category == category]
        if state:
            res = [i for i in res if i.state == state]
        return res
