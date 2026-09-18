"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
Cryptographic Provenance Chain & Audit Trail.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional


class ProvenanceTracker:
    """Tracks immutable chain of custody for all intent, decisions, and modifications."""

    def __init__(self, mission_id: str):
        self.mission_id = mission_id
        self._chain: List[Dict[str, Any]] = []
        self._last_hash: str = hashlib.sha256(f"INIT_{mission_id}".encode("utf-8")).hexdigest()

    def record_event(
        self,
        event_type: str,
        actor: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        now = time.time()
        record_content = {
            "mission_id": self.mission_id,
            "event_type": event_type,
            "actor": actor,
            "payload": payload,
            "previous_hash": self._last_hash,
            "timestamp": now,
        }
        record_hash = hashlib.sha256(
            json.dumps(record_content, sort_keys=True).encode("utf-8")
        ).hexdigest()

        entry = {
            **record_content,
            "record_hash": record_hash,
        }
        self._chain.append(entry)
        self._last_hash = record_hash
        return entry

    def get_latest_hash(self) -> str:
        return self._last_hash

    def get_chain(self) -> List[Dict[str, Any]]:
        return list(self._chain)
