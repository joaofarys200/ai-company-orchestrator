"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Module: provenance.py
Maintains an immutable cryptographic provenance ledger for architectural observations,
proposals, simulations, and governance decisions.
"""

from __future__ import annotations

import hashlib
import time
from typing import Dict, List, Optional

from .models import ArchitectureProvenanceRecord


class ArchitectureProvenanceManager:
    """Manages cryptographic hash chain for all architectural evolution events."""

    def __init__(self):
        self._records: Dict[str, ArchitectureProvenanceRecord] = {}
        self._latest_hash: str = "0" * 64

    def record_event(
        self,
        target_id: str,
        source_type: str,
        action: str,
        actor: str = "ArchitectureEvolutionSystem",
        parent_hashes: Optional[List[str]] = None,
    ) -> ArchitectureProvenanceRecord:
        record_id = f"prov_{hashlib.sha256(f'{target_id}:{action}:{time.time()}'.encode()).hexdigest()[:8]}"
        parents = parent_hashes if parent_hashes is not None else [self._latest_hash]

        rec = ArchitectureProvenanceRecord(
            record_id=record_id,
            target_id=target_id,
            source_type=source_type,
            action=action,
            actor=actor,
            timestamp=time.time(),
            parent_hashes=parents,
        )
        rec.hash_signature = rec.compute_signature()

        self._records[record_id] = rec
        self._latest_hash = rec.hash_signature
        return rec

    def get_record(self, record_id: str) -> Optional[ArchitectureProvenanceRecord]:
        return self._records.get(record_id)

    def get_all_records(self) -> List[ArchitectureProvenanceRecord]:
        return list(self._records.values())

    def verify_integrity(self) -> bool:
        """Verifies the unbroken cryptographic chain across all recorded events."""
        for rec in self._records.values():
            expected = rec.compute_signature()
            if rec.hash_signature != expected:
                return False
        return True
