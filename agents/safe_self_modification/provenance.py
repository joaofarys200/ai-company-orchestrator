"""
JARVIS OS — Phase 65: Safe Self-Modification & Transactional Architecture Implementation
Module: provenance.py
Maintains immutable SHA-256 cryptographic provenance audit trails for all
transactional modification events, linking decisions, snapshots, patches, and commits.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional

from .models import TransactionProvenanceRecord


class ProvenanceLedger:
    """Immutable audit trail manager for self-modification operations."""

    def __init__(self):
        self.records: List[TransactionProvenanceRecord] = []
        self._last_hash: str = "GENESIS_PHASE65_HASH"

    def record_action(
        self,
        transaction_id: str,
        action: str,
        actor: str = "SafeSelfModificationEngine",
    ) -> TransactionProvenanceRecord:
        """Append an action record linked to the previous cryptographic hash."""
        record_id = f"prov_{len(self.records) + 1}_{int(time.time() * 1000) % 1000000}"
        record = TransactionProvenanceRecord(
            record_id=record_id,
            transaction_id=transaction_id,
            action=action,
            actor=actor,
            timestamp=time.time(),
            parent_hash=self._last_hash,
        )
        record.hash_signature = record.compute_signature()
        self._last_hash = record.hash_signature
        self.records.append(record)
        return record

    def verify_chain_integrity(self) -> bool:
        """Verify the integrity of the cryptographic chain."""
        expected_parent = "GENESIS_PHASE65_HASH"
        for rec in self.records:
            if rec.parent_hash != expected_parent:
                return False
            if rec.compute_signature() != rec.hash_signature:
                return False
            expected_parent = rec.hash_signature
        return True

    def get_records_for_transaction(self, transaction_id: str) -> List[TransactionProvenanceRecord]:
        return [r for r in self.records if r.transaction_id == transaction_id]
