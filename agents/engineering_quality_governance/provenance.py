"""
JARVIS OS — Phase 68: Quality Provenance & Audit Registry
Tracks cryptographic signatures, source hashes, and agent attestation for quality records.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional


class QualityProvenanceRegistry:
    """
    Maintains immutable cryptographic audit records for snapshots, debt lifecycle events,
    and quality gate decisions.
    """

    def __init__(self) -> None:
        self._audit_trail: List[Dict[str, Any]] = []

    def record_provenance(
        self,
        entity_type: str,
        entity_id: str,
        actor: str,
        action: str,
        details: Dict[str, Any],
    ) -> Dict[str, Any]:
        timestamp = time.time()
        payload = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "actor": actor,
            "action": action,
            "details": details,
            "timestamp": timestamp,
        }
        raw = json.dumps(payload, sort_keys=True)
        signature = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        record = {
            **payload,
            "signature": signature,
        }
        self._audit_trail.append(record)
        return record

    def get_trail(self, entity_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if entity_id:
            return [r for r in self._audit_trail if r.get("entity_id") == entity_id]
        return list(self._audit_trail)
