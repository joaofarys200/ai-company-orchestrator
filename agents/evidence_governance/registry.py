"""
JARVIS OS — Phase 77: Autonomous Evidence Verification & Engineering Claims Governance
Module: registry.py
Central repository for registering, indexing, and querying engineering claims and evidence artifacts.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from .models import (
    AssuranceTier,
    ClaimType,
    EngineeringClaim,
    EvidenceArtifact,
    EvidenceCategory,
    EvidenceOriginType,
    VerificationStatus,
)
from .provenance import EvidenceProvenanceValidator


class EvidenceClaimsRegistry:
    """
    Thread-safe in-memory index for engineering claims and evidence artifacts.
    Prevents duplicate evidence ingestion and manages associative relationships.
    """

    def __init__(self):
        # Key: claim_id -> EngineeringClaim
        self._claims: Dict[str, EngineeringClaim] = {}
        # Key: artifact_id -> EvidenceArtifact
        self._artifacts: Dict[str, EvidenceArtifact] = {}
        # Key: content_hash -> artifact_id (deduplication)
        self._hash_to_artifact: Dict[str, str] = {}

    def register_claim(self, claim: EngineeringClaim) -> EngineeringClaim:
        """Register or update an engineering claim."""
        self._claims[claim.claim_id] = claim
        return claim

    def register_artifact(self, artifact: EvidenceArtifact) -> EvidenceArtifact:
        """
        Register an evidence artifact with integrity validation and deduplication.
        """
        # 1. Validate cryptographic hash integrity
        EvidenceProvenanceValidator.validate_integrity(artifact)

        # 2. Check for duplicate content hash
        if artifact.content_hash in self._hash_to_artifact:
            existing_id = self._hash_to_artifact[artifact.content_hash]
            return self._artifacts[existing_id]

        self._artifacts[artifact.artifact_id] = artifact
        self._hash_to_artifact[artifact.content_hash] = artifact.artifact_id
        return artifact

    def attach_evidence_to_claim(self, claim_id: str, artifact_id: str) -> bool:
        """Attach an existing artifact to a claim."""
        claim = self._claims.get(claim_id)
        if not claim or artifact_id not in self._artifacts:
            return False
        if artifact_id not in claim.evidence_refs:
            claim.evidence_refs.append(artifact_id)
        return True

    def get_claim(self, claim_id: str) -> Optional[EngineeringClaim]:
        """Retrieve claim by ID."""
        return self._claims.get(claim_id)

    def get_artifact(self, artifact_id: str) -> Optional[EvidenceArtifact]:
        """Retrieve artifact by ID."""
        return self._artifacts.get(artifact_id)

    def get_artifacts_for_claim(self, claim: EngineeringClaim) -> List[EvidenceArtifact]:
        """Retrieve all evidence artifacts associated with a claim."""
        artifacts: List[EvidenceArtifact] = []
        for ref_id in claim.evidence_refs:
            art = self._artifacts.get(ref_id)
            if art:
                artifacts.append(art)
        return artifacts

    def list_claims(
        self,
        claim_type: Optional[ClaimType] = None,
        status: Optional[VerificationStatus] = None,
        assurance_tier: Optional[AssuranceTier] = None,
    ) -> List[EngineeringClaim]:
        """Query claims by type, status, or tier."""
        res = list(self._claims.values())
        if claim_type:
            res = [c for c in res if c.claim_type == claim_type]
        if status:
            res = [c for c in res if c.status == status]
        if assurance_tier:
            res = [c for c in res if c.assurance_tier == assurance_tier]
        return res
