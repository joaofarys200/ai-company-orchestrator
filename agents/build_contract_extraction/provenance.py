"""
JARVIS OS — Phase 49: Provenance Tracker
Immutable audit trail ensuring no contract entity or dynamic resolution loses its origin.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Optional

from agents.build_contract_extraction.models import ArtifactProvenance, SourceType


class ProvenanceTracker:
    """
    Manages deterministic SHA-256 provenance hashes, pointers, and verification.
    Guarantees the invariant: Never lose or forge origin.
    """

    @classmethod
    def compute_content_hash(cls, content: Any) -> str:
        """Computes a deterministic SHA-256 hash from arbitrary content (str, bytes, dict, or list)."""
        if isinstance(content, bytes):
            payload = content
        elif isinstance(content, str):
            payload = content.encode("utf-8")
        else:
            try:
                payload = json.dumps(content, sort_keys=True, default=str).encode("utf-8")
            except Exception:
                payload = str(content).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @classmethod
    def create_provenance(
        cls,
        source_type: SourceType,
        artifact_path: str,
        json_pointer: str = "",
        content: Any = None,
    ) -> ArtifactProvenance:
        """Constructs an immutable ArtifactProvenance with content hash."""
        h = cls.compute_content_hash(content) if content is not None else ""
        # Normalize artifact path separators for portability
        normalized_path = artifact_path.replace("\\", "/")
        return ArtifactProvenance(
            source_type=source_type,
            artifact_path=normalized_path,
            json_pointer=json_pointer,
            content_hash=h,
            extracted_at=time.time(),
        )

    @classmethod
    def verify_provenance(cls, provenance: ArtifactProvenance, current_content: Any) -> bool:
        """Verifies if the actual current content matches the provenance hash."""
        if not provenance.content_hash:
            return True
        current_hash = cls.compute_content_hash(current_content)
        return current_hash == provenance.content_hash

    @classmethod
    def format_badge(cls, provenance: Optional[ArtifactProvenance]) -> str:
        """Generates a human-readable provenance badge."""
        if not provenance:
            return "[PROVENANCE:UNKNOWN]"
        ptr = f"{provenance.json_pointer}" if provenance.json_pointer else ""
        short_hash = provenance.content_hash[:8] if provenance.content_hash else "nohash"
        return f"[{provenance.source_type.value}:{provenance.artifact_path}{ptr}#{short_hash}]"
