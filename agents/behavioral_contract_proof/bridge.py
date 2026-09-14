"""
JARVIS OS — Phase 50: Behavioral Contract Preservation & Migration Proof
Bridge Connecting Behavioral Proofs to Phases 42, 44, 48, and 49.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from agents.behavioral_contract_proof.baseline import BehaviorBaselineStore
from agents.behavioral_contract_proof.migration import BehavioralMigrationController
from agents.behavioral_contract_proof.models import (
    BehaviorBaseline,
    CompatibilityCategory,
    ExecutionGateDecision,
    MigrationProof,
    ProofResult,
    RuntimeTrace,
)
from agents.behavioral_contract_proof.proof import MigrationProofEngine


class BehavioralContractProofBridge:
    """
    Coordinates behavioral proofs with contract change management (Phase 48),
    build-time extraction (Phase 49), semantic graph (Phase 44), and experience memory (Phases 42/43).
    """

    def __init__(
        self,
        baseline_store: Optional[BehaviorBaselineStore] = None,
        migration_controller: Optional[BehavioralMigrationController] = None,
    ) -> None:
        self.baseline_store = baseline_store or BehaviorBaselineStore()
        self.migration_controller = migration_controller or BehavioralMigrationController()
        self._experience_records: List[Dict[str, Any]] = []

    def evaluate_dynamic_consumer_proof(
        self,
        consumer_resolution: Dict[str, Any],
        baseline: Optional[BehaviorBaseline],
        observed_trace: Optional[RuntimeTrace],
        migration_id: str,
        before_version: str,
        after_version: str,
    ) -> MigrationProof:
        """
        Evaluates migration proof taking Phase 49 dynamic consumer resolution into account.
        - For UNCERTAIN dynamic consumers: proof is strictly INSUFFICIENT_EVIDENCE (never guess!).
        - For GENERATED/STATIC dynamic consumers with closed exhaustive or open fallback: evaluate proof.
        """
        evidence_state = consumer_resolution.get("evidence_state", "UNCERTAIN")
        resolution_status = consumer_resolution.get("resolution_status", "UNCERTAIN")
        is_closed_exhaustive = consumer_resolution.get("pattern_matching") == "CLOSED_EXHAUSTIVE"

        # 1. Epistemic Invariant: If dynamic consumer is UNCERTAIN, proof must be INSUFFICIENT_EVIDENCE
        if evidence_state == "UNCERTAIN" or resolution_status == "UNCERTAIN":
            return MigrationProof(
                migration_id=migration_id,
                before_version=before_version,
                after_version=after_version,
                consumers=[consumer_resolution.get("consumer_id", "unknown_dynamic_consumer")],
                baseline_hash=baseline.baseline_hash if baseline else "",
                post_change_hash=observed_trace.trace_hash if observed_trace else "",
                invariants_checked=[],
                counterexamples=[],
                confidence=0.0,
                result=ProofResult.INSUFFICIENT_EVIDENCE,
                provenance={
                    "dynamic_consumer": True,
                    "evidence_state": "UNCERTAIN",
                    "reason": "Cannot deterministically prove compatibility for unbounded dynamic consumer without evidence",
                },
                compatibility_category=CompatibilityCategory.BEHAVIOR_UNKNOWN,
            )

        # 2. Evaluate deterministic proof for resolved consumer
        proof = MigrationProofEngine.prove_migration(
            migration_id=migration_id,
            baseline=baseline,
            observed_trace=observed_trace,
            before_version=before_version,
            after_version=after_version,
            consumers=[consumer_resolution.get("consumer_id", "dynamic_consumer")],
            is_closed_exhaustive=is_closed_exhaustive,
            has_sufficient_evidence=True,
            provenance={
                "dynamic_consumer": True,
                "evidence_state": evidence_state,
                "resolution_id": consumer_resolution.get("resolution_id"),
            },
        )
        return proof

    def record_experience_memory(self, proof: MigrationProof) -> None:
        """
        Stores migration proof patterns in experience memory (Phases 42/43).
        CRITICAL INVARIANT: Memory is NOT authority. Past experience never overrides current baseline!
        """
        record = {
            "record_id": f"mem_proof_{proof.migration_id}_{int(time.time() * 1000)}",
            "migration_id": proof.migration_id,
            "result": proof.result.value,
            "counterexamples_count": len(proof.counterexamples),
            "before_version": proof.before_version,
            "after_version": proof.after_version,
            "confidence": proof.confidence,
            "timestamp": time.time(),
            "authority_status": "ADVISORY_ONLY_NOT_AUTHORITATIVE",
        }
        self._experience_records.append(record)

    def list_experience_memories(self) -> List[Dict[str, Any]]:
        """Lists advisory experience memories."""
        return list(self._experience_records)
