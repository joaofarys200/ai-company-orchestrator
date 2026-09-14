"""
JARVIS OS — Phase 51: Behavioral Proof Coverage & Scenario Exploration
Proof Validator, Decision Gate Evaluator, and Finish Gate Authority.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from agents.behavioral_contract_proof.models import (
    BehavioralInvariantType,
    Counterexample,
    ExecutionGateDecision,
    ProofResult,
)
from agents.behavioral_proof_exploration.models import (
    BehavioralCoverage,
    BoundedExplorationProof,
    CoverageThresholdPolicy,
    ProofScope,
    ShrunkCounterexample,
)


class ExplorationValidator:
    """
    Validates proof outcomes, enforces the distinction between Coverage and Evidence,
    and governs Mission Gate & Finish Gate clearances.
    """

    def evaluate_proof_result(
        self,
        scope: ProofScope,
        coverage: BehavioralCoverage,
        counterexamples: List[Counterexample],
        invariants_violated: List[BehavioralInvariantType],
        consumer_uncertainties: Optional[List[str]] = None,
        is_economic_operation: bool = False,
    ) -> Tuple[ProofResult, ExecutionGateDecision, List[str]]:
        """
        Synthesize proof outcome and gate decision.
        """
        reasons: List[str] = []
        uncertainties = consumer_uncertainties or []

        # 1. Counterexamples found -> PROVEN_INCOMPATIBLE
        if counterexamples or invariants_violated:
            if counterexamples:
                reasons.append(f"{len(counterexamples)} counterexample(s) detected during scenario exploration.")
            if invariants_violated:
                reasons.append(f"Invariants violated: {[i.value for i in invariants_violated]}")
            return ProofResult.PROVEN_INCOMPATIBLE, ExecutionGateDecision.EXECUTION_BLOCKED, reasons

        # 2. Coverage threshold NOT reached -> INSUFFICIENT_COVERAGE
        if not coverage.threshold_met:
            reasons.append(
                f"Behavioral coverage {coverage.overall_percentage*100:.1f}% below required threshold "
                f"for policy {coverage.threshold_policy.value}."
            )
            gate = ExecutionGateDecision.EXECUTION_BLOCKED if is_economic_operation else ExecutionGateDecision.HUMAN_REVIEW_REQUIRED
            return ProofResult.INSUFFICIENT_COVERAGE, gate, reasons

        # 3. Unresolved dynamic consumer / structural epistemic uncertainty -> INSUFFICIENT_EVIDENCE
        if uncertainties:
            reasons.append(
                f"Unresolved structural uncertainty persists for consumers: {uncertainties}. "
                "100% coverage does not eliminate structural dynamic consumer ambiguity."
            )
            return ProofResult.INSUFFICIENT_EVIDENCE, ExecutionGateDecision.HUMAN_REVIEW_REQUIRED, reasons

        # 4. Scope defined, threshold met, 0 counterexamples, invariants intact, no uncertainties
        # -> PROVEN_COMPATIBLE_WITHIN_SCOPE
        reasons.append(
            f"All {coverage.overall_percentage*100:.1f}% covered within explicit scope {scope.scope_id} "
            f"with zero counterexamples and all invariants preserved."
        )
        return ProofResult.PROVEN_COMPATIBLE_WITHIN_SCOPE, ExecutionGateDecision.GATE_CLEARED, reasons

    def validate_finish_gate(self, proof: BoundedExplorationProof) -> Tuple[bool, ExecutionGateDecision, List[str]]:
        """
        Finish Gate validation rule:
        Accepts PROVEN_COMPATIBLE_WITHIN_SCOPE only when:
        - scope defined
        - coverage threshold reached
        - invariants preserved
        - zero counterexamples
        - zero unresolved blocking evidence
        """
        reasons: List[str] = []

        if proof.result != ProofResult.PROVEN_COMPATIBLE_WITHIN_SCOPE:
            reasons.append(f"Finish Gate rejected: proof result is {proof.result.value}, expected PROVEN_COMPATIBLE_WITHIN_SCOPE.")
            decision = ExecutionGateDecision.EXECUTION_BLOCKED if proof.result == ProofResult.PROVEN_INCOMPATIBLE else ExecutionGateDecision.HUMAN_REVIEW_REQUIRED
            return False, decision, reasons

        if not proof.coverage.threshold_met:
            reasons.append("Finish Gate rejected: coverage threshold was not reached.")
            return False, ExecutionGateDecision.HUMAN_REVIEW_REQUIRED, reasons

        if not proof.invariants_preserved or len(proof.counterexamples) > 0:
            reasons.append("Finish Gate rejected: counterexamples or invariant violations exist.")
            return False, ExecutionGateDecision.EXECUTION_BLOCKED, reasons

        if proof.consumer_uncertainties:
            reasons.append(f"Finish Gate rejected: unresolved consumer uncertainties: {proof.consumer_uncertainties}.")
            return False, ExecutionGateDecision.HUMAN_REVIEW_REQUIRED, reasons

        reasons.append("Finish Gate cleared: Bounded proof verified within scope.")
        return True, ExecutionGateDecision.GATE_CLEARED, reasons
