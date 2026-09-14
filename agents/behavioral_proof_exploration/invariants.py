"""
JARVIS OS — Phase 51: Behavioral Proof Coverage & Scenario Exploration
Behavioral Invariant Evaluator extending Phase 50 BehavioralInvariantEngine.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from agents.behavioral_contract_proof.invariants import BehavioralInvariantEngine
from agents.behavioral_contract_proof.models import (
    BehaviorBaseline,
    BehavioralInvariantType,
    RuntimeTrace,
)


class EconomicBehaviorMismatchError(Exception):
    """Raised when an economic amount or currency invariant is violated."""
    pass


class ExplorationInvariantEngine:
    """
    Evaluates behavioral invariants across scenario execution traces.
    Strictly prevents economic discrepancies (amount, currency, ledger drift).
    """

    def __init__(self) -> None:
        self.base_engine = BehavioralInvariantEngine()

    def evaluate(
        self,
        before_trace: RuntimeTrace,
        after_trace: RuntimeTrace,
        baseline: Optional[BehaviorBaseline] = None,
        invariants: Optional[List[BehavioralInvariantType]] = None,
    ) -> Tuple[bool, List[BehavioralInvariantType], List[str]]:
        """
        Evaluate invariants across before and after traces.
        Returns:
            (all_passed, violated_invariants, violation_reasons)
        """
        target_invariants = invariants or [
            BehavioralInvariantType.AUTHORIZATION_PRESERVED,
            BehavioralInvariantType.ECONOMIC_VALUE_PRESERVED,
            BehavioralInvariantType.EVENT_SEMANTICS_PRESERVED,
            BehavioralInvariantType.REQUIRED_FIELDS_PRESERVED,
            BehavioralInvariantType.ERROR_SEMANTICS_PRESERVED,
            BehavioralInvariantType.SIDE_EFFECT_ORDER_PRESERVED,
            BehavioralInvariantType.CONSUMER_EXPECTATION_PRESERVED,
        ]

        passed, violated, reasons = self.base_engine.evaluate_all(
            before_trace=before_trace,
            after_trace=after_trace,
            baseline=baseline,
            invariants=target_invariants,
        )

        # Explicit check for economic value preservation
        if BehavioralInvariantType.ECONOMIC_VALUE_PRESERVED in violated:
            reasons.append("ECONOMIC_BEHAVIOR_MISMATCH: Economic amount or currency divergence detected.")

        return passed, violated, reasons
