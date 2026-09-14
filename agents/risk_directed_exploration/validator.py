"""
JARVIS OS — Phase 52: Risk-Directed Behavioral Exploration & Adaptive Proof Search
Proof Validator and Finish Gate Decision Authority.
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
    CoverageThresholdPolicy,
)
from agents.risk_directed_exploration.models import (
    AdaptiveProofResult,
    BehavioralExplorationRisk,
    BehavioralUncertainty,
    ExplorationPolicy,
)


class AdaptiveProofValidator:
    """
    Validates proof outcomes, enforces epistemic calibration,
    and governs Mission Gate & Finish Gate clearances for Phase 52.
    """

    def evaluate_adaptive_proof_result(
        self,
        coverage: Optional[BehavioralCoverage],
        counterexamples: List[Counterexample],
        invariants_preserved: bool,
        policy: ExplorationPolicy,
        consumer_uncertainties: Optional[List[str]] = None,
        mandatory_safety_passed: bool = True,
    ) -> Tuple[ProofResult, ExecutionGateDecision, List[str]]:
        """
        Evaluate formal proof state:
        - counterexample found -> PROVEN_INCOMPATIBLE
        - coverage < threshold -> INSUFFICIENT_COVERAGE
        - unresolved dynamic consumer -> INSUFFICIENT_EVIDENCE
        - mandatory safety set failed -> INSUFFICIENT_COVERAGE / BLOCKED
        - all clear -> PROVEN_COMPATIBLE_WITHIN_SCOPE
        """
        reasons: List[str] = []
        uncertainties = consumer_uncertainties or []

        # 1. Counterexamples found -> PROVEN_INCOMPATIBLE
        if counterexamples or not invariants_preserved:
            reasons.append(f"{len(counterexamples)} counterexample(s) detected during risk-directed exploration.")
            return ProofResult.PROVEN_INCOMPATIBLE, ExecutionGateDecision.EXECUTION_BLOCKED, reasons

        # 2. Mandatory safety set failed (e.g. economic/security operations missing mandatory scenarios)
        if not mandatory_safety_passed:
            reasons.append(f"Mandatory safety scenarios required for policy {policy.value} were not satisfied.")
            gate = ExecutionGateDecision.EXECUTION_BLOCKED if policy in (ExplorationPolicy.ECONOMIC_CRITICAL, ExplorationPolicy.CRITICAL) else ExecutionGateDecision.HUMAN_REVIEW_REQUIRED
            return ProofResult.INSUFFICIENT_COVERAGE, gate, reasons

        # 3. Coverage threshold not met -> INSUFFICIENT_COVERAGE
        if not coverage or not coverage.threshold_met:
            cov_pct = (coverage.overall_percentage * 100) if coverage else 0.0
            reasons.append(f"Coverage of {cov_pct:.1f}% below required threshold for policy {policy.value}.")
            gate = ExecutionGateDecision.EXECUTION_BLOCKED if policy in (ExplorationPolicy.ECONOMIC_CRITICAL, ExplorationPolicy.CRITICAL) else ExecutionGateDecision.HUMAN_REVIEW_REQUIRED
            return ProofResult.INSUFFICIENT_COVERAGE, gate, reasons

        # 4. Unresolved consumer uncertainty -> INSUFFICIENT_EVIDENCE
        if uncertainties:
            reasons.append(f"Unresolved structural uncertainty persists for dynamic consumers: {uncertainties}.")
            return ProofResult.INSUFFICIENT_EVIDENCE, ExecutionGateDecision.HUMAN_REVIEW_REQUIRED, reasons

        # 5. All criteria satisfied within explicit scope
        reasons.append(
            f"Verified compatible within explicit risk-bounded scope under {policy.value} policy. "
            f"Coverage: {coverage.overall_percentage*100:.1f}%, 0 counterexamples, invariants preserved."
        )
        return ProofResult.PROVEN_COMPATIBLE_WITHIN_SCOPE, ExecutionGateDecision.GATE_CLEARED, reasons

    def validate_finish_gate(self, proof: AdaptiveProofResult) -> Tuple[bool, ExecutionGateDecision, List[str]]:
        """
        Finish Gate validation: rejects if not PROVEN_COMPATIBLE_WITHIN_SCOPE,
        or if threshold unmet, or if counterexamples exist.
        """
        reasons: List[str] = []

        if proof.result != ProofResult.PROVEN_COMPATIBLE_WITHIN_SCOPE:
            reasons.append(f"Finish Gate rejected: proof result is {proof.result.value}, expected PROVEN_COMPATIBLE_WITHIN_SCOPE.")
            dec = ExecutionGateDecision.EXECUTION_BLOCKED if proof.result == ProofResult.PROVEN_INCOMPATIBLE else ExecutionGateDecision.HUMAN_REVIEW_REQUIRED
            return False, dec, reasons

        if not proof.coverage.threshold_met:
            reasons.append("Finish Gate rejected: coverage threshold unmet.")
            return False, ExecutionGateDecision.HUMAN_REVIEW_REQUIRED, reasons

        if len(proof.counterexamples) > 0:
            reasons.append("Finish Gate rejected: active counterexamples exist.")
            return False, ExecutionGateDecision.EXECUTION_BLOCKED, reasons

        reasons.append("Finish Gate cleared: Risk-directed proof validated within scope.")
        return True, ExecutionGateDecision.GATE_CLEARED, reasons
