"""
JARVIS OS — Phase 63: Cross-Project Engineering Learning & Verification Transfer
Module: conflicts.py
ConflictDetector identifies contradictory or mutually incompatible engineering patterns.
Marks conflicting items as CONFLICTED without automatic merging.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    ConflictRecord,
    EngineeringKnowledgeItem,
    KnowledgeCategory,
    KnowledgeState,
)


class ConflictDetector:
    """Detects mutual contradictions across architecture, contracts, behavior, security, and testing."""

    def __init__(self) -> None:
        self.conflicts: List[ConflictRecord] = []

    def check_conflict(
        self,
        item_a: EngineeringKnowledgeItem,
        item_b: EngineeringKnowledgeItem,
    ) -> Optional[ConflictRecord]:
        """Check if two items have mutually contradictory specifications."""
        if item_a.knowledge_id == item_b.knowledge_id:
            return None

        # 1. Architectural conflict (e.g. monolithic vs microservice on same scope)
        if (
            item_a.category == KnowledgeCategory.ARCHITECTURE_PATTERN
            and item_b.category == KnowledgeCategory.ARCHITECTURE_PATTERN
        ):
            style_a = str(item_a.pattern.get("architecture_style", "")).lower()
            style_b = str(item_b.pattern.get("architecture_style", "")).lower()
            if (
                ("monolith" in style_a and "microservice" in style_b)
                or ("microservice" in style_a and "monolith" in style_b)
            ) and item_a.context.get("domain") == item_b.context.get("domain"):
                return self._record_conflict(
                    item_a,
                    item_b,
                    "ARCHITECTURAL_CONTRADICTION",
                    f"Opposing architecture styles: {style_a} vs {style_b} for same domain",
                )

        # 2. Contract conflict (e.g. conflicting compatibility rules or schema formats)
        if (
            item_a.category == KnowledgeCategory.CONTRACT_PATTERN
            and item_b.category == KnowledgeCategory.CONTRACT_PATTERN
        ):
            proto_a = item_a.pattern.get("protocol", "")
            proto_b = item_b.pattern.get("protocol", "")
            rule_a = item_a.pattern.get("compatibility_rule", "")
            rule_b = item_b.pattern.get("compatibility_rule", "")
            if proto_a == proto_b and rule_a != rule_b and ("strict" in rule_a or "strict" in rule_b):
                return self._record_conflict(
                    item_a,
                    item_b,
                    "CONTRACT_RULE_CONTRADICTION",
                    f"Conflicting compatibility constraints: '{rule_a}' vs '{rule_b}' on {proto_a}",
                )

        # 3. Behavioral conflict (e.g. mutually exclusive FSM transition rules)
        if (
            item_a.category == KnowledgeCategory.BEHAVIOR_PATTERN
            and item_b.category == KnowledgeCategory.BEHAVIOR_PATTERN
        ):
            fsm_a = item_a.pattern.get("state_machine", "")
            fsm_b = item_b.pattern.get("state_machine", "")
            if fsm_a == fsm_b and fsm_a:
                invs_a = set(item_a.pattern.get("transition_invariants", []))
                invs_b = set(item_b.pattern.get("transition_invariants", []))
                # Check for negation
                for ia in invs_a:
                    if f"not_{ia}" in invs_b or f"no_{ia}" in invs_b:
                        return self._record_conflict(
                            item_a,
                            item_b,
                            "BEHAVIORAL_INVARIANT_CONTRADICTION",
                            f"Mutually exclusive invariant: '{ia}' contradicts rival pattern",
                        )

        # 4. Security conflict (e.g. permissive bypass vs zero-trust)
        if item_a.pattern.get("security_override") and not item_b.pattern.get("security_override"):
            return self._record_conflict(
                item_a,
                item_b,
                "SECURITY_POLICY_CONTRADICTION",
                "One pattern demands security bypass while the other enforces strict sentinel",
            )

        return None

    def _record_conflict(
        self,
        item_a: EngineeringKnowledgeItem,
        item_b: EngineeringKnowledgeItem,
        conflict_type: str,
        reason: str,
    ) -> ConflictRecord:
        record = ConflictRecord(
            conflict_id=f"conf_{uuid.uuid4().hex[:8]}",
            pair_item_ids=(item_a.knowledge_id, item_b.knowledge_id),
            conflict_type=conflict_type,
            reason=reason,
            evidence={
                "item_a": item_a.to_dict(),
                "item_b": item_b.to_dict(),
            },
            resolution_status="OPEN",
            timestamp=time.time(),
        )
        self.conflicts.append(record)
        # Mark both as conflicted
        item_a.state = KnowledgeState.CONFLICTED
        item_b.state = KnowledgeState.CONFLICTED
        return record
