"""
JARVIS OS — Phase 54: Repair Experience Cache
Consultative failure and repair memory. Memory is never authority; past patches must be verified every time.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents.verified_repair.models import (
    RepairCandidate,
    RepairProof,
    RootCauseHypothesis,
    compute_deterministic_hash,
)


class RepairExperienceCache:
    """
    Stores historical repair executions for consultative acceleration.
    Invariant: Memory is strictly consultative and holds zero autonomous authority.
    """

    def __init__(self) -> None:
        self._entries: Dict[str, Dict[str, Any]] = {}

    def store_experience(
        self,
        hypothesis: RootCauseHypothesis,
        selected_candidate: RepairCandidate,
        proof: RepairProof,
    ) -> None:
        sig = compute_deterministic_hash(
            {"cat": hypothesis.category.value, "sym": hypothesis.source_locations},
            prefix="sig_",
        )
        self._entries[sig] = {
            "hypothesis": hypothesis.to_dict(),
            "candidate": selected_candidate.to_dict(),
            "proof": proof.to_dict(),
            "proof_result": proof.proof_result.value if hasattr(proof.proof_result, "value") else str(proof.proof_result),
        }

    def consult_experience(self, hypothesis: RootCauseHypothesis) -> Optional[Dict[str, Any]]:
        sig = compute_deterministic_hash(
            {"cat": hypothesis.category.value, "sym": hypothesis.source_locations},
            prefix="sig_",
        )
        return self._entries.get(sig)

    def size(self) -> int:
        return len(self._entries)
