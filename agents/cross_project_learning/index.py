"""
JARVIS OS — Phase 63: Cross-Project Engineering Learning & Verification Transfer
Module: index.py
Inverted indices for rapid multi-axis filtering.
Provides O(1) key lookup and O(k) candidate enumeration for k matching items.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Set

from .models import EngineeringKnowledgeItem, KnowledgeCategory


class KnowledgeReverseIndex:
    """Maintains inverted key-to-item indexes across structural and engineering dimensions."""

    def __init__(self) -> None:
        # Inverted index mappings: key -> set of knowledge_ids
        self.by_language: Dict[str, Set[str]] = defaultdict(set)
        self.by_framework: Dict[str, Set[str]] = defaultdict(set)
        self.by_architecture: Dict[str, Set[str]] = defaultdict(set)
        self.by_contract_type: Dict[str, Set[str]] = defaultdict(set)
        self.by_risk: Dict[str, Set[str]] = defaultdict(set)
        self.by_test_framework: Dict[str, Set[str]] = defaultdict(set)
        self.by_failure_type: Dict[str, Set[str]] = defaultdict(set)
        self.by_behavior_type: Dict[str, Set[str]] = defaultdict(set)

        self._items: Dict[str, EngineeringKnowledgeItem] = {}

    def index_item(self, item: EngineeringKnowledgeItem) -> None:
        """Add item to inverted indices. O(1) hash map operations per dimension."""
        k_id = item.knowledge_id
        self._items[k_id] = item
        ctx = item.context
        pattern = item.pattern

        # Languages
        langs = ctx.get("languages", [ctx.get("language", "")])
        for l in langs:
            if l:
                self.by_language[l.lower()].add(k_id)

        # Frameworks
        fws = ctx.get("frameworks", [ctx.get("framework", "")])
        for f in fws:
            if f:
                self.by_framework[f.lower()].add(k_id)

        # Architecture
        arch = ctx.get("architecture_style", "") or pattern.get("architecture_style", "")
        if arch:
            self.by_architecture[arch.lower()].add(k_id)

        # Contract Type
        proto = pattern.get("protocol", "") or ctx.get("contract_type", "")
        if proto:
            self.by_contract_type[proto.lower()].add(k_id)

        # Risk
        risk = pattern.get("risk_class", "") or ctx.get("risk_class", "")
        if risk:
            self.by_risk[risk.lower()].add(k_id)

        # Test Framework
        tfw = ctx.get("test_framework", "") or pattern.get("test_type", "")
        if tfw:
            self.by_test_framework[tfw.lower()].add(k_id)

        # Failure Type
        symptom = pattern.get("root_cause_class", "") or pattern.get("symptom", "")
        if symptom:
            self.by_failure_type[symptom.lower()].add(k_id)

        # Behavior Type
        fsm = pattern.get("state_machine", "")
        if fsm:
            self.by_behavior_type[fsm.lower()].add(k_id)

    def remove_item(self, knowledge_id: str) -> None:
        """Remove item from all inverted indices."""
        self._items.pop(knowledge_id, None)
        for idx in [
            self.by_language,
            self.by_framework,
            self.by_architecture,
            self.by_contract_type,
            self.by_risk,
            self.by_test_framework,
            self.by_failure_type,
            self.by_behavior_type,
        ]:
            for key in list(idx.keys()):
                idx[key].discard(knowledge_id)
                if not idx[key]:
                    idx.pop(key, None)

    def query_by_keys(
        self,
        language: str = "",
        framework: str = "",
        architecture: str = "",
        risk: str = "",
        contract_type: str = "",
    ) -> List[EngineeringKnowledgeItem]:
        """
        Query inverted indices. Key lookup is O(1); returns k items in O(k).
        """
        candidate_sets: List[Set[str]] = []

        if language and language.lower() in self.by_language:
            candidate_sets.append(self.by_language[language.lower()])
        if framework and framework.lower() in self.by_framework:
            candidate_sets.append(self.by_framework[framework.lower()])
        if architecture and architecture.lower() in self.by_architecture:
            candidate_sets.append(self.by_architecture[architecture.lower()])
        if risk and risk.lower() in self.by_risk:
            candidate_sets.append(self.by_risk[risk.lower()])
        if contract_type and contract_type.lower() in self.by_contract_type:
            candidate_sets.append(self.by_contract_type[contract_type.lower()])

        if not candidate_sets:
            return []

        # Intersect or union candidates
        intersection = set.intersection(*candidate_sets) if candidate_sets else set()
        return [self._items[k_id] for k_id in intersection if k_id in self._items]

    def size(self) -> int:
        return len(self._items)
