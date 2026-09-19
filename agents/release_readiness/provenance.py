"""
Release Provenance Module
Phase 70 — Autonomous Release Readiness & Production Governance

Cryptographic SHA-256 provenance tracking, immutable digest computation,
and tamper-evident verification chains for release artifacts and decisions.
"""

from __future__ import annotations
import hashlib
import json
from typing import Any, Dict


class ReleaseProvenanceTracker:
    """Manages cryptographic hashing and verifiable lineage for release decisions."""

    @staticmethod
    def compute_sha256(data: Any) -> str:
        """Deterministic SHA-256 computation over arbitrary Python data."""
        if isinstance(data, str):
            payload = data.encode("utf-8")
        elif isinstance(data, (bytes, bytearray)):
            payload = bytes(data)
        else:
            try:
                payload = json.dumps(data, sort_keys=True, separators=(',', ':'), default=str).encode("utf-8")
            except Exception:
                payload = str(data).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @classmethod
    def create_provenance_record(
        cls,
        entity_id: str,
        entity_type: str,
        content: Any,
        parent_hash: str = ""
    ) -> Dict[str, Any]:
        """Creates a standardized tamper-evident provenance record."""
        content_hash = cls.compute_sha256(content)
        composite_input = f"{entity_id}:{entity_type}:{content_hash}:{parent_hash}"
        provenance_hash = cls.compute_sha256(composite_input)

        return {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "content_hash": content_hash,
            "parent_hash": parent_hash,
            "provenance_hash": provenance_hash,
            "hash_algorithm": "SHA-256"
        }

    @classmethod
    def verify_provenance(cls, record: Dict[str, Any], original_content: Any) -> bool:
        """Verifies that the content matches the recorded cryptographic hash."""
        computed_content_hash = cls.compute_sha256(original_content)
        if computed_content_hash != record.get("content_hash"):
            return False
        
        composite_input = (
            f"{record.get('entity_id')}:{record.get('entity_type')}:"
            f"{computed_content_hash}:{record.get('parent_hash', '')}"
        )
        return cls.compute_sha256(composite_input) == record.get("provenance_hash")
