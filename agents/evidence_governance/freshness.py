"""
JARVIS OS — Phase 77: Autonomous Evidence Verification & Engineering Claims Governance
Module: freshness.py
Dependency-aware evidence freshness monitor and invalidation tracker.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Set

from .models import EngineeringClaim, VerificationResult, VerificationStatus


class EvidenceFreshnessMonitor:
    """
    Monitors repository file modifications and commit changes to invalidate stale evidence,
    ensuring that previously verified claims do not silently mask regressions after code alters.
    """

    def __init__(self):
        # Claim dependency graph: upstream_claim_id -> set of downstream_claim_ids
        self._claim_dependencies: Dict[str, Set[str]] = {}

    def link_claim_dependency(self, parent_claim_id: str, child_claim_id: str) -> None:
        """Record that child_claim depends on the validity of parent_claim."""
        if parent_claim_id not in self._claim_dependencies:
            self._claim_dependencies[parent_claim_id] = set()
        self._claim_dependencies[parent_claim_id].add(child_claim_id)

    def evaluate_freshness_against_modified_files(
        self,
        claims: List[EngineeringClaim],
        modified_files: Set[str],
        modification_timestamp: Optional[float] = None,
    ) -> List[str]:
        """
        Invalidates claims whose dependency files have been altered.
        Returns list of invalidated claim IDs.
        """
        mod_time = modification_timestamp or time.time()
        invalidated_ids: List[str] = []

        for claim in claims:
            if claim.status != VerificationStatus.VERIFIED:
                continue

            # Check if any dependency file was modified
            touched = set(claim.dependency_files).intersection(modified_files)
            if touched:
                claim.status = VerificationStatus.STALE
                if claim.verification_result:
                    claim.verification_result.status = VerificationStatus.STALE
                    claim.verification_result.discrepancies.append(
                        f"EVIDENCE_STALE_FILE_MODIFIED_{list(touched)}"
                    )
                    claim.verification_result.explanation = (
                        f"Previously verified evidence invalidated by modifications to {list(touched)}."
                    )
                invalidated_ids.append(claim.claim_id)

        # Propagate invalidation down the claim dependency tree
        for claim_id in list(invalidated_ids):
            self._propagate_invalidation(claim_id, claims, invalidated_ids)

        return invalidated_ids

    def _propagate_invalidation(
        self,
        parent_id: str,
        claims: List[EngineeringClaim],
        invalidated_ids: List[str],
    ) -> None:
        """Cascades invalidation down dependent claims."""
        downstream = self._claim_dependencies.get(parent_id, set())
        claim_map = {c.claim_id: c for c in claims}

        for child_id in downstream:
            child = claim_map.get(child_id)
            if child and child.status == VerificationStatus.VERIFIED:
                child.status = VerificationStatus.STALE
                if child.verification_result:
                    child.verification_result.status = VerificationStatus.STALE
                    child.verification_result.discrepancies.append(
                        f"EVIDENCE_STALE_UPSTREAM_CLAIM_{parent_id}"
                    )
                    child.verification_result.explanation = (
                        f"Evidence invalidated due to upstream dependency '{parent_id}' becoming stale."
                    )
                invalidated_ids.append(child_id)
                self._propagate_invalidation(child_id, claims, invalidated_ids)
