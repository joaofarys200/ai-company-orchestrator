"""
Phase 71 — Append-Only Operational Ledger
Cryptographically chained event ledger recording all observations, decisions, and remediations.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any, Dict, List, Optional
from .models import LedgerEntry


class OperationalLedger:
    """
    Append-only SHA-256 cryptographically chained ledger.
    """

    GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

    def __init__(self, service_id: str):
        self.service_id = service_id
        self._entries: List[LedgerEntry] = []
        self._last_hash: str = self.GENESIS_HASH

    def append_event(
        self,
        event_type: str,
        state_before: str,
        action: str,
        state_after: str,
        evidence_ids: Optional[List[str]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> LedgerEntry:
        """
        Appends a new event and updates the hash chain.
        """
        event_id = f"evt-{uuid.uuid4().hex[:12]}"
        now = time.time()
        parent_event = self._entries[-1].event_id if self._entries else None

        raw_payload = payload or {}
        # Deterministic payload representation
        payload_str = json.dumps(raw_payload, sort_keys=True, default=str)

        raw_content = (
            f"{self._last_hash}:{event_id}:{event_type}:{state_before}:"
            f"{action}:{state_after}:{','.join(evidence_ids or [])}:{now}:{payload_str}"
        )
        entry_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()

        entry = LedgerEntry(
            event_id=event_id,
            parent_event=parent_event,
            event_type=event_type,
            evidence_ids=evidence_ids or [],
            state_before=state_before,
            action=action,
            state_after=state_after,
            entry_hash=entry_hash,
            timestamp=now,
            payload=raw_payload,
        )

        self._entries.append(entry)
        self._last_hash = entry_hash
        return entry

    def verify_integrity(self) -> bool:
        """
        Validates that the ledger hash chain is intact and untampered.
        """
        prev_hash = self.GENESIS_HASH
        for entry in self._entries:
            payload_str = json.dumps(entry.payload, sort_keys=True, default=str)
            raw_content = (
                f"{prev_hash}:{entry.event_id}:{entry.event_type}:{entry.state_before}:"
                f"{entry.action}:{entry.state_after}:{','.join(entry.evidence_ids)}:{entry.timestamp}:{payload_str}"
            )
            expected_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()
            if entry.entry_hash != expected_hash:
                return False
            prev_hash = entry.entry_hash
        return True

    def get_entries(self) -> List[LedgerEntry]:
        return list(self._entries)
