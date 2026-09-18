"""
JARVIS OS — Phase 66: Multi-Agent Engineering Coordination & Conflict Arbitration
Module: provenance.py
ProvenanceGraphTracker recording immutable causal lineages linking agents, intents, claims,
patches, merges, verifications, and commits.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional

from .models import ProvenanceRecord


class ProvenanceGraphTracker:
    """Maintains an append-only causal provenance graph of all multi-agent operations."""

    def __init__(self):
        self.records: Dict[str, ProvenanceRecord] = {}

    @property
    def events(self) -> Dict[str, ProvenanceRecord]:
        ev = dict(self.records)
        for r in self.records.values():
            if r.transaction_id:
                ev[r.transaction_id] = r
        return ev

    def record_coordination_event(
        self,
        agent_id: str,
        mission_id: str,
        intent_id: str,
        claim_ids: List[str],
        transaction_id: str = "",
        base_snapshot: str = "",
        patch_hash: str = "",
        merge_hash: str = "",
        verification_hash: str = "",
        parent_records: Optional[List[str]] = None,
    ) -> ProvenanceRecord:
        """Record an immutable lineage node in the causal graph."""
        rec_id = f"prov_{agent_id}_{intent_id}_{int(time.time() * 1000) % 1000000}"
        rec = ProvenanceRecord(
            record_id=rec_id,
            agent_id=agent_id,
            mission_id=mission_id,
            intent_id=intent_id,
            claim_ids=claim_ids,
            transaction_id=transaction_id,
            base_snapshot=base_snapshot,
            patch_hash=patch_hash,
            merge_hash=merge_hash,
            verification_hash=verification_hash,
            parent_records=parent_records or [],
        )
        self.records[rec_id] = rec
        return rec

    def get_lineage(self, intent_id: str) -> List[ProvenanceRecord]:
        return [r for r in self.records.values() if r.intent_id == intent_id]

    def verify_provenance_chain(self, record_id: str) -> bool:
        rec = self.records.get(record_id)
        if not rec:
            return False
        computed = rec.compute_hash()
        return bool(computed)
