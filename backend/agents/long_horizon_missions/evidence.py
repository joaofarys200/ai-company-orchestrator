"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
Cryptographic Evidence Ledger & Root Hash Tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    milestone_id: str
    kind: str
    status: str
    details: Dict[str, Any]
    timestamp: float
    sha256_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "milestone_id": self.milestone_id,
            "kind": self.kind,
            "status": self.status,
            "details": dict(self.details),
            "timestamp": self.timestamp,
            "sha256_hash": self.sha256_hash,
        }

    @staticmethod
    def compute_hash(evidence_id: str, milestone_id: str, kind: str, status: str, details: Dict[str, Any]) -> str:
        payload = {
            "evidence_id": evidence_id,
            "milestone_id": milestone_id,
            "kind": kind,
            "status": status,
            "details": details,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


class EvidenceLedger:
    """
    Immutable append-only evidence ledger.
    Maintains a deterministic evidence root hash representing all collected proof.
    """

    def __init__(self, items: Optional[List[EvidenceItem]] = None):
        self._items: List[EvidenceItem] = list(items or [])
        self._index: Dict[str, EvidenceItem] = {it.evidence_id: it for it in self._items}

    def record_evidence(
        self,
        milestone_id: str,
        kind: str,
        status: str,
        details: Dict[str, Any],
        evidence_id: Optional[str] = None,
    ) -> EvidenceItem:
        eid = evidence_id or f"evd_{milestone_id}_{len(self._items)+1:04d}"
        now = time.time()
        sha = EvidenceItem.compute_hash(eid, milestone_id, kind, status, details)

        item = EvidenceItem(
            evidence_id=eid,
            milestone_id=milestone_id,
            kind=kind,
            status=status,
            details=details,
            timestamp=now,
            sha256_hash=sha,
        )
        self._items.append(item)
        self._index[eid] = item
        return item

    def get_evidence(self, evidence_id: str) -> Optional[EvidenceItem]:
        return self._index.get(evidence_id)

    def list_by_milestone(self, milestone_id: str) -> List[EvidenceItem]:
        return [it for it in self._items if it.milestone_id == milestone_id]

    def compute_root_hash(self) -> str:
        if not self._items:
            return hashlib.sha256(b"EMPTY_EVIDENCE_ROOT").hexdigest()

        combined = "".join(it.sha256_hash for it in self._items)
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def to_list(self) -> List[Dict[str, Any]]:
        return [it.to_dict() for it in self._items]
