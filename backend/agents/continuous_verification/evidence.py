"""
JARVIS OS — Phase 62: Continuous Verification & Autonomous Regression Governance
Module: evidence.py
Verification Evidence Ledger building cryptographically chained audit trails.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import time
from typing import Any, Dict, List, Optional


@dataclass
class EvidenceItem:
    stage: str
    data_hash: str
    details: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "data_hash": self.data_hash,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class VerificationEvidenceLedger:
    """
    Maintains an immutable chain of evidence entries for each continuous verification cycle.
    Produces deterministic evidence signatures.
    """

    def __init__(self, run_id: Optional[str] = None) -> None:
        self.run_id = run_id or f"run_{int(time.time() * 1000)}"
        self.entries: List[EvidenceItem] = []

    def record_stage_evidence(self, stage: str, data: Dict[str, Any]) -> str:
        """Hash stage payload and append to ledger."""
        serialized = json.dumps(data, sort_keys=True, default=str)
        data_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        item = EvidenceItem(
            stage=stage,
            data_hash=data_hash,
            details=data,
            timestamp=time.time(),
        )
        self.entries.append(item)
        return data_hash

    def get_ledger_signature(self) -> str:
        """Compute aggregate cryptographic signature of entire evidence chain."""
        combined = "".join(item.data_hash for item in self.entries)
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def export_evidence(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.entries]
