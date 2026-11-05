"""
JARVIS OS — Phase 77: Autonomous Evidence Verification & Engineering Claims Governance
Module: provenance.py
Cryptographic provenance validation, content hash integrity checks, commit alignment,
and origin fidelity verification.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional, Tuple

from .models import (
    EvidenceArtifact,
    EvidenceCategory,
    EvidenceOriginType,
    InvalidEvidenceIntegrityError,
)


class EvidenceProvenanceValidator:
    """
    Validates the cryptographic integrity, revision consistency, and origin authenticity
    of evidence artifacts before they can be used to verify engineering claims.
    """

    @staticmethod
    def compute_payload_hash(payload: Dict[str, Any]) -> str:
        """Compute deterministic SHA-256 hash of a serialized dictionary."""
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def create_artifact(
        cls,
        artifact_id: str,
        category: EvidenceCategory,
        origin_type: EvidenceOriginType,
        commit_sha: str,
        payload: Dict[str, Any],
        source_subsystem: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EvidenceArtifact:
        """Create an immutable, content-hashed evidence artifact."""
        content_hash = cls.compute_payload_hash(payload)
        return EvidenceArtifact(
            artifact_id=artifact_id,
            category=category,
            origin_type=origin_type,
            content_hash=content_hash,
            commit_sha=commit_sha,
            payload=payload,
            source_subsystem=source_subsystem,
            metadata=metadata or {},
        )

    @classmethod
    def validate_integrity(cls, artifact: EvidenceArtifact) -> bool:
        """
        Verify that the artifact's payload has not been tampered with or corrupted.
        Raises InvalidEvidenceIntegrityError if hash does not match.
        """
        expected_hash = cls.compute_payload_hash(artifact.payload)
        if artifact.content_hash != expected_hash:
            raise InvalidEvidenceIntegrityError(
                f"Evidence artifact '{artifact.artifact_id}' corrupted: stored hash "
                f"'{artifact.content_hash}' != recomputed hash '{expected_hash}'."
            )
        return True

    @classmethod
    def validate_commit_alignment(cls, artifact: EvidenceArtifact, expected_commit_sha: Optional[str]) -> bool:
        """
        Validates that the evidence was generated against the exact claimed repository revision.
        """
        if not expected_commit_sha:
            return True
        return artifact.commit_sha == expected_commit_sha

    @classmethod
    def validate_origin_fidelity(
        cls,
        artifact: EvidenceArtifact,
        requires_real_execution: bool = True,
    ) -> Tuple[bool, str]:
        """
        Validates whether the evidence origin meets the required fidelity.
        Rejects synthetic fixtures when real execution proof is mandatory.
        Rejects model-generated text as standalone proof of runtime success.
        """
        if artifact.category == EvidenceCategory.MODEL_GENERATED_EXPLANATION:
            return False, "Model-generated narrative text cannot serve as standalone proof of runtime success."

        if requires_real_execution and artifact.origin_type == EvidenceOriginType.SYNTHETIC_FIXTURE:
            return False, "Claim requires real repository execution, but evidence is from a synthetic fixture."

        return True, "Origin fidelity verified."
