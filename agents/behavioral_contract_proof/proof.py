"""
JARVIS OS — Phase 50: Behavioral Contract Preservation & Migration Proof
Migration Proof Engine & Certificate Generator.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from agents.behavioral_contract_proof.comparator import BehaviorComparator
from agents.behavioral_contract_proof.counterexample import CounterexampleGenerator
from agents.behavioral_contract_proof.invariants import BehavioralInvariantEngine
from agents.behavioral_contract_proof.models import (
    BehaviorBaseline,
    BehavioralInvariantType,
    CompatibilityCategory,
    Counterexample,
    EquivalenceLevel,
    MigrationProof,
    ProofResult,
    RuntimeTrace,
)


class MigrationProofEngine:
    """
    Computes deterministic behavioral proofs for contract migrations.
    """

    @classmethod
    def prove_migration(
        cls,
        migration_id: str,
        baseline: Optional[BehaviorBaseline],
        observed_trace: Optional[RuntimeTrace],
        before_version: str,
        after_version: str,
        consumers: List[str],
        invariants_to_check: Optional[List[BehavioralInvariantType]] = None,
        is_closed_exhaustive: bool = False,
        has_sufficient_evidence: bool = True,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> MigrationProof:
        """
        Executes formal proof workflow.
        Returns a MigrationProof with PROVEN_COMPATIBLE, PROVEN_INCOMPATIBLE, or INSUFFICIENT_EVIDENCE.
        """
        target_invariants = invariants_to_check or list(BehavioralInvariantType)

        # 1. Check for Insufficient Evidence
        if (
            not has_sufficient_evidence
            or baseline is None
            or observed_trace is None
            or not observed_trace.output_payload
        ):
            return MigrationProof(
                migration_id=migration_id,
                before_version=before_version,
                after_version=after_version,
                consumers=consumers,
                baseline_hash=baseline.baseline_hash if baseline else "",
                post_change_hash=observed_trace.trace_hash if observed_trace else "",
                invariants_checked=target_invariants,
                counterexamples=[],
                confidence=0.0,
                result=ProofResult.INSUFFICIENT_EVIDENCE,
                provenance=provenance or {},
                compatibility_category=CompatibilityCategory.BEHAVIOR_UNKNOWN,
                equivalence_level=EquivalenceLevel.UNKNOWN,
            )

        # 2. Run Behavioral Comparison
        comparison = BehaviorComparator.compare(baseline, observed_trace)

        # 3. Evaluate Formal Invariants
        invariant_results = BehavioralInvariantEngine.evaluate_invariants(
            baseline, observed_trace, target_invariants, is_closed_exhaustive
        )
        failed_invariants = [res for res in invariant_results if not res.satisfied]

        # 4. Check If Incompatible
        if not comparison.is_compatible or failed_invariants:
            # Build Counterexample
            diff_reasons = list(comparison.differences)
            for f_inv in failed_invariants:
                diff_reasons.append(f"Invariant [{f_inv.invariant.value}] violated: {f_inv.violation_reason}")

            combined_diff = "; ".join(diff_reasons)
            counterexample = CounterexampleGenerator.generate(
                baseline=baseline,
                observed=observed_trace,
                difference_summary=combined_diff,
                specific_evidence={
                    "failed_invariants": [f.to_dict() for f in failed_invariants],
                    "equivalence_level": comparison.equivalence_level.value,
                },
            )

            # Distinguish type compatible vs contract compatible vs behaviorally incompatible
            return MigrationProof(
                migration_id=migration_id,
                before_version=before_version,
                after_version=after_version,
                consumers=consumers,
                baseline_hash=baseline.baseline_hash,
                post_change_hash=observed_trace.trace_hash,
                invariants_checked=target_invariants,
                counterexamples=[counterexample],
                confidence=1.0,
                result=ProofResult.PROVEN_INCOMPATIBLE,
                provenance=provenance or {},
                compatibility_category=CompatibilityCategory.BEHAVIORALLY_INCOMPATIBLE,
                equivalence_level=comparison.equivalence_level,
            )

        # 5. Proven Compatible
        return MigrationProof(
            migration_id=migration_id,
            before_version=before_version,
            after_version=after_version,
            consumers=consumers,
            baseline_hash=baseline.baseline_hash,
            post_change_hash=observed_trace.trace_hash,
            invariants_checked=target_invariants,
            counterexamples=[],
            confidence=1.0,
            result=ProofResult.PROVEN_COMPATIBLE,
            provenance=provenance or {},
            compatibility_category=CompatibilityCategory.BEHAVIORALLY_COMPATIBLE,
            equivalence_level=comparison.equivalence_level,
        )
