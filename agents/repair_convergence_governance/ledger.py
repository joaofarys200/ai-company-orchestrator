"""
JARVIS OS — Phase 56: Progress Ledger
Append-only, cryptographically chained tamper-evident ledger for repair transitions.
"""

from __future__ import annotations

import time
import hashlib
from typing import Dict, Any, List, Optional
from agents.repair_convergence_governance.models import (
    GovernanceLedgerEntry,
    compute_deterministic_hash,
)


class ProgressLedger:
    """Tamper-evident append-only ledger that records every state transition, step, and decision."""

    GENESIS_HASH = "0000000000000000"

    def __init__(self):
        self.entries: List[GovernanceLedgerEntry] = []

    def append_entry(self, event_type: str, payload: Dict[str, Any]) -> GovernanceLedgerEntry:
        """Appends a new immutable ledger entry chained cryptographically to the previous entry."""
        seq = len(self.entries)
        prev_hash = self.entries[-1].entry_hash if self.entries else self.GENESIS_HASH
        ts = time.time()
        entry_id = f"led_{seq}_{hashlib.sha256(f'{seq}:{event_type}:{ts}'.encode('utf-8')).hexdigest()[:8]}"

        entry = GovernanceLedgerEntry(
            entry_id=entry_id,
            sequence=seq,
            timestamp=ts,
            event_type=event_type,
            payload=payload,
            previous_hash=prev_hash,
        )
        self.entries.append(entry)
        return entry

    def verify_integrity(self) -> bool:
        """Traverses the ledger from genesis to tail and verifies all cryptographic link hashes."""
        for i, entry in enumerate(self.entries):
            # Check sequence ordering
            if entry.sequence != i:
                return False

            # Check previous hash link
            expected_prev = self.GENESIS_HASH if i == 0 else self.entries[i - 1].entry_hash
            if entry.previous_hash != expected_prev:
                return False

            # Recompute entry hash
            data = {
                "entry_id": entry.entry_id,
                "sequence": entry.sequence,
                "timestamp": entry.timestamp,
                "event_type": entry.event_type,
                "payload": entry.payload,
                "previous_hash": entry.previous_hash
            }
            if entry.entry_hash != compute_deterministic_hash(data):
                return False

        return True

    def get_entries(self) -> List[GovernanceLedgerEntry]:
        return list(self.entries)

    def to_list(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.entries]
