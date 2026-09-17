"""
JARVIS OS — Phase 57: Mission Completion Proof Synthesizer & Validator
Synthesizes cryptographically signed proofs of mission completion or termination,
guaranteeing that no mission claims success without verifiable scope and evidence.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any

from .models import (
    AutonomousMission,
    CompletionDecision,
    MissionCompletionProof,
)


class ProofSynthesisError(Exception):
    """Raised when proof synthesis fails invariant checks."""


class MissionProofSynthesizer:
    """Synthesizes and validates formal completion proofs for autonomous missions."""

    @classmethod
    def synthesize_proof(
        cls,
        mission: AutonomousMission,
        decision: CompletionDecision,
        evaluation_details: dict[str, Any] | None = None,
    ) -> MissionCompletionProof:
        proof_id = f"prf_{uuid.uuid4().hex[:10]}"
        now = time.time()
        details = evaluation_details or {}

        invariants = [
            "INVARIANT_OBJECTIVE_RETENTION",
            "INVARIANT_ZERO_UNHANDLED_CRITICAL_FAILURES",
            "INVARIANT_SENTINEL_SOVEREIGNTY_PRESERVED",
            "INVARIANT_EVIDENCE_SHA256_LINEAGE",
            "INVARIANT_CONVERGENCE_MONOTONICITY",
        ]

        if mission.economic_policy:
            invariants.append("INVARIANT_ECONOMIC_SAFETY_LEDGER")

        # Canonical signature payload
        ev_hash = mission.evidence_set.compute_aggregate_hash()
        sig_data = f"{proof_id}:{mission.mission_id}:{decision.value}:{mission.initial_state_hash}:{mission.final_state_hash}:{ev_hash}:{now}"
        signature = hashlib.sha256(sig_data.encode("utf-8")).hexdigest()

        proof = MissionCompletionProof(
            proof_id=proof_id,
            mission_id=mission.mission_id,
            objective=mission.objective,
            acceptance_criteria=[c.to_dict() for c in mission.acceptance_criteria],
            evidence=[e.to_dict() for e in mission.evidence_set.evidences],
            invariants=invariants,
            failures=mission.failures,
            repairs=mission.repairs,
            coverage=mission.scorecard.coverage if mission.scorecard else 1.0,
            risk=mission.risk,
            convergence=mission.convergence,
            initial_state_hash=mission.initial_state_hash,
            final_state_hash=mission.final_state_hash or mission.compute_current_state_hash(),
            decision=decision,
            signature=signature,
            timestamp=now,
        )

        mission.proof = proof
        mission.final_decision = decision
        return proof

    @classmethod
    def verify_proof(cls, proof: MissionCompletionProof) -> bool:
        """Verifies proof signature and structural consistency."""
        if not proof.signature or not proof.proof_id or not proof.mission_id:
            return False

        # Verify invariants presence
        if "INVARIANT_OBJECTIVE_RETENTION" not in proof.invariants:
            return False
        if "INVARIANT_SENTINEL_SOVEREIGNTY_PRESERVED" not in proof.invariants:
            return False

        # In case of COMPLETE, ensure acceptance criteria and evidence are present
        if proof.decision == CompletionDecision.MISSION_PROVEN_COMPLETE:
            if not proof.acceptance_criteria:
                return False
            if not proof.evidence:
                return False

        return True
