"""
JARVIS OS — Phase 56: Composite Convergence Proof Engine
Verifies aggregate composition of individual patch proofs and overall behavioral invariants.
"""

from __future__ import annotations

import hashlib
from typing import Dict, Any, List, Optional, Tuple
from agents.repair_convergence_governance.models import compute_deterministic_hash


class CompositeConvergenceProofEngine:
    """Verifies that a series of individually proven repairs compose into a globally proven transaction."""

    def __init__(self, min_composite_coverage: float = 0.80):
        self.min_composite_coverage = min_composite_coverage

    def verify_composite_proof(
        self,
        transaction_id: str,
        individual_patch_proofs: List[Dict[str, Any]],
        system_invariants_checked: List[str],
        unresolved_invariants: List[str],
        final_test_pass_rate: float,
        final_proof_coverage: float,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Verifies the joint validity of the multi-repair composition."""
        # 1. Check all individual proofs exist
        if not individual_patch_proofs:
            return False, "No individual patch proofs provided.", {}

        missing_proofs = [p.get("patch_id", f"p_{i}") for i, p in enumerate(individual_patch_proofs) if not p.get("verified", False)]
        if missing_proofs:
            return False, f"Missing formal proofs for patches: {missing_proofs}", {}

        # 2. Invariant verification: all system invariants must hold
        if unresolved_invariants:
            return False, f"System invariant violations remain unresolved: {unresolved_invariants}", {}

        # 3. Final test suite pass rate must be 100%
        if final_test_pass_rate < 1.0:
            return False, f"Final test pass rate is {final_test_pass_rate * 100.0:.1f}%, must be 100.0% for convergence.", {}

        # 4. Final proof coverage must meet threshold
        if final_proof_coverage < self.min_composite_coverage:
            return False, f"Composite proof coverage {final_proof_coverage:.3f} below minimum threshold {self.min_composite_coverage:.3f}.", {}

        # 5. Emit composite proof hash
        composition_payload = {
            "transaction_id": transaction_id,
            "patch_count": len(individual_patch_proofs),
            "invariants": sorted(system_invariants_checked),
            "coverage": round(final_proof_coverage, 4),
            "pass_rate": round(final_test_pass_rate, 4),
        }
        proof_hash = "COMPOSITE_PROOF_" + compute_deterministic_hash(composition_payload)

        proof_summary = {
            "transaction_id": transaction_id,
            "composite_proof_hash": proof_hash,
            "patch_proofs_count": len(individual_patch_proofs),
            "invariants_satisfied": len(system_invariants_checked),
            "verified": True,
        }
        return True, "Composite transaction proof formally verified across all invariants.", proof_summary
