"""
JARVIS OS — Phase 50: Behavioral Contract Preservation & Migration Proof
Behavioral Migration Controller, Gate Evaluator, Simulation & Rollback.
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agents.behavioral_contract_proof.models import (
    BehaviorBaseline,
    BehavioralDelta,
    BehavioralInvariantType,
    ExecutionGateDecision,
    MigrationProof,
    ProofResult,
    RuntimeTrace,
)
from agents.behavioral_contract_proof.proof import MigrationProofEngine


@dataclass
class FinishGateStatus:
    """Finish Gate evaluation report."""
    cleared: bool
    contract_verified: bool
    behavior_verified: bool
    invariants_preserved: bool
    blocking_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cleared": self.cleared,
            "contract_verified": self.contract_verified,
            "behavior_verified": self.behavior_verified,
            "invariants_preserved": self.invariants_preserved,
            "blocking_reasons": self.blocking_reasons,
        }


@dataclass
class RollbackRecord:
    """Audit lineage for an automated or manual rollback."""
    rollback_id: str
    migration_id: str
    contract_id: str
    reverted_to_version: str
    reason: str
    counterexamples: List[Dict[str, Any]]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rollback_id": self.rollback_id,
            "migration_id": self.migration_id,
            "contract_id": self.contract_id,
            "reverted_to_version": self.reverted_to_version,
            "reason": self.reason,
            "counterexamples": self.counterexamples,
            "timestamp": self.timestamp,
        }


class BehavioralMigrationController:
    """
    Controls behavioral gate evaluations, preflight counterfactual simulation,
    and rollback preservation.
    """

    def __init__(self) -> None:
        self._proofs: Dict[str, MigrationProof] = {}
        self._deltas: Dict[str, BehavioralDelta] = {}
        self._rollbacks: List[RollbackRecord] = []

    def evaluate_mission_gate(
        self,
        proof: MigrationProof,
        is_breaking_classification: bool,
    ) -> ExecutionGateDecision:
        """
        Applies formal Mission Gate rules:
        - BREAKING_CHANGE + PROVEN_INCOMPATIBLE -> EXECUTION_BLOCKED
        - BREAKING_CHANGE + INSUFFICIENT_EVIDENCE -> HUMAN_REVIEW_REQUIRED
        - NON_BREAKING + PROVEN_COMPATIBLE -> GATE_CLEARED
        - NON_BREAKING + INSUFFICIENT_EVIDENCE -> HUMAN_REVIEW_REQUIRED
        """
        if is_breaking_classification:
            if proof.result == ProofResult.PROVEN_INCOMPATIBLE:
                return ExecutionGateDecision.EXECUTION_BLOCKED
            else:
                return ExecutionGateDecision.HUMAN_REVIEW_REQUIRED
        else:
            if proof.result == ProofResult.PROVEN_COMPATIBLE:
                return ExecutionGateDecision.GATE_CLEARED
            else:
                # Any insufficient evidence or incompatibility requires human review
                return ExecutionGateDecision.HUMAN_REVIEW_REQUIRED

    def evaluate_finish_gate(
        self,
        proof: MigrationProof,
        contract_verified: bool,
        has_economic_delta: bool = False,
        has_auth_change: bool = False,
        unknown_required_consumer: bool = False,
    ) -> FinishGateStatus:
        """
        Strict Finish Gate: Only clears if:
        contract verified AND behavior verified AND required invariants preserved.
        """
        blocking_reasons: List[str] = []

        if not contract_verified:
            blocking_reasons.append("Contract verification failed or incomplete")

        behavior_verified = proof.result == ProofResult.PROVEN_COMPATIBLE
        if not behavior_verified:
            blocking_reasons.append(f"Behavior verification incomplete or failed: {proof.result.value}")

        invariants_preserved = len(proof.counterexamples) == 0
        if not invariants_preserved:
            blocking_reasons.append(f"Behavioral invariants violated ({len(proof.counterexamples)} counterexample(s))")

        if has_economic_delta:
            blocking_reasons.append("Unexpected economic delta observed in financial operations")

        if has_auth_change:
            blocking_reasons.append("Unauthorized authorization state modification detected")

        if unknown_required_consumer:
            blocking_reasons.append("Required consumer behavior remains UNKNOWN / UNCERTAIN")

        cleared = len(blocking_reasons) == 0
        return FinishGateStatus(
            cleared=cleared,
            contract_verified=contract_verified,
            behavior_verified=behavior_verified,
            invariants_preserved=invariants_preserved,
            blocking_reasons=blocking_reasons,
        )

    def simulate_counterfactual_migration(
        self,
        baseline: BehaviorBaseline,
        hypothetical_trace: RuntimeTrace,
        migration_id: str,
        invariants_to_check: Optional[List[BehavioralInvariantType]] = None,
    ) -> MigrationProof:
        """
        Performs read-only preflight simulation of a migration without side effects.
        """
        proof = MigrationProofEngine.prove_migration(
            migration_id=migration_id,
            baseline=baseline,
            observed_trace=hypothetical_trace,
            before_version=baseline.contract_version,
            after_version="hypothetical_v2",
            consumers=[baseline.consumer_id],
            invariants_to_check=invariants_to_check,
            has_sufficient_evidence=True,
            provenance={"simulation": True, "read_only": True},
        )
        return proof

    def execute_rollback(
        self,
        proof: MigrationProof,
        contract_id: str,
        revert_to_version: str,
        policy_permits: bool = True,
    ) -> Optional[RollbackRecord]:
        """
        Executes rollback if proof fails and policy permits.
        Never erases failure evidence or counterexamples.
        """
        if not policy_permits:
            return None

        if proof.result != ProofResult.PROVEN_INCOMPATIBLE:
            return None

        rollback_record = RollbackRecord(
            rollback_id=f"rb_{int(time.time() * 1000)}",
            migration_id=proof.migration_id,
            contract_id=contract_id,
            reverted_to_version=revert_to_version,
            reason=f"Post-change proof failed with {len(proof.counterexamples)} counterexample(s)",
            counterexamples=[c.to_dict() for c in proof.counterexamples],
            timestamp=time.time(),
        )
        self._rollbacks.append(rollback_record)
        return rollback_record

    def list_rollbacks(self) -> List[RollbackRecord]:
        """Returns all recorded rollbacks for audit lineage."""
        return list(self._rollbacks)
