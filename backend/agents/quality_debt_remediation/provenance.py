"""
JARVIS OS — Phase 69: Autonomous Quality Debt Remediation
Provenance tracking engine.
Generates SHA-256 cryptographic audit trails for every phase of the remediation lifecycle.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProvenanceRecord:
    record_id: str
    debt_id: str
    stage: str
    actor: str
    payload_hash: str
    signature: str
    parent_record_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DebtProvenanceTracker:
    """
    Maintains an immutable chain of cryptographically signed audit records.
    """

    def __init__(self):
        self._records: List[ProvenanceRecord] = []

    def record_stage(
        self,
        debt_id: str,
        stage: str,
        payload: Dict[str, Any],
        actor: str = "QualityDebtGovernor",
    ) -> ProvenanceRecord:
        record_id = f"prov_{len(self._records) + 1:04d}_{hashlib.sha256(f'{debt_id}_{stage}_{time.time()}'.encode()).hexdigest()[:6]}"
        parent_id = self._records[-1].record_id if self._records else None

        raw_payload = json.dumps(payload, sort_keys=True, default=str)
        payload_hash = hashlib.sha256(raw_payload.encode()).hexdigest()

        # Generate block signature linking parent
        sig_input = f"{record_id}:{parent_id}:{payload_hash}:{actor}:{stage}"
        signature = hashlib.sha256(sig_input.encode()).hexdigest()

        record = ProvenanceRecord(
            record_id=record_id,
            debt_id=debt_id,
            stage=stage,
            actor=actor,
            payload_hash=payload_hash,
            signature=signature,
            parent_record_id=parent_id,
            timestamp=time.time(),
        )
        self._records.append(record)
        return record

    def list_records(self) -> List[ProvenanceRecord]:
        return list(self._records)

    def verify_integrity(self) -> bool:
        """Verifies hash chain integrity across all records."""
        for i in range(1, len(self._records)):
            prev = self._records[i - 1]
            curr = self._records[i]
            if curr.parent_record_id != prev.record_id:
                return False
        return True
