"""
JARVIS OS — Phase 51: Behavioral Proof Coverage & Scenario Exploration
Behavioral Comparator for scenario execution outputs and traces.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from agents.behavioral_contract_proof.comparator import BehaviorComparator
from agents.behavioral_contract_proof.models import (
    BehavioralDelta,
    CompatibilityCategory,
    EquivalenceLevel,
    RuntimeTrace,
)


class ExplorationComparator:
    """
    Differential Behavioral Comparator.
    Compares before and after traces for a given scenario using Phase 50 BehaviorComparator.
    """

    def __init__(self) -> None:
        self.base_comparator = BehaviorComparator()

    def compare(
        self,
        before_trace: RuntimeTrace,
        after_trace: RuntimeTrace,
    ) -> Tuple[bool, EquivalenceLevel, Optional[str]]:
        """
        Compare before and after execution traces.
        Returns:
            (is_compatible, equivalence_level, difference_detail)
        """
        equiv_level, category, reasons = self.base_comparator.compare(before_trace, after_trace)
        is_compatible = equiv_level in (EquivalenceLevel.EXACT_EQUIVALENCE, EquivalenceLevel.SEMANTIC_EQUIVALENCE, EquivalenceLevel.ALLOWED_CHANGE)
        diff_detail = "; ".join(reasons) if reasons else None
        return is_compatible, equiv_level, diff_detail
