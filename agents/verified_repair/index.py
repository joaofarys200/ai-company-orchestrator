"""
JARVIS OS — Phase 54: Verified Repair Index & Audit Ledger
Maintains in-memory and persistent ledgers of hypotheses, candidate repairs, rankings, proofs, and counterexamples.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents.verified_repair.models import (
    Counterexample,
    RepairCandidate,
    RepairCandidateRanking,
    RepairProof,
    RootCauseHypothesis,
)


class VerifiedRepairIndex:
    """
    Central repository and audit registry for Phase 54.
    """

    def __init__(self) -> None:
        self.root_causes: Dict[str, RootCauseHypothesis] = {}
        self.candidates: Dict[str, RepairCandidate] = {}
        self.rankings: Dict[str, List[RepairCandidateRanking]] = {}
        self.proofs: Dict[str, RepairProof] = {}
        self.counterexamples: List[Counterexample] = []

    def record_hypothesis(self, hypothesis: RootCauseHypothesis) -> None:
        self.root_causes[hypothesis.cause_id] = hypothesis

    def record_candidates(self, candidates: List[RepairCandidate]) -> None:
        for c in candidates:
            self.candidates[c.repair_id] = c

    def record_rankings(self, cause_id: str, rankings: List[RepairCandidateRanking]) -> None:
        self.rankings[cause_id] = rankings

    def record_proof(self, proof: RepairProof) -> None:
        self.proofs[proof.proof_id] = proof
        for cex in proof.counterexamples:
            self.counterexamples.append(cex)

    def get_proof(self, proof_id: str) -> Optional[RepairProof]:
        return self.proofs.get(proof_id)

    def get_hypothesis(self, cause_id: str) -> Optional[RootCauseHypothesis]:
        return self.root_causes.get(cause_id)
