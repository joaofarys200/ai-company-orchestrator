"""
Phase 72 — Evidence Repository and Audit Ledger
Tracks prediction evidence, calibration checkpoints, and decision audit trails.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from .models import (
    PredictionEvidence,
    ReliabilityDecision,
)


class ReliabilityEvidenceLedger:
    """Immutable ledger of reliability decisions, prediction evidence, and calibration snapshots."""

    def __init__(self):
        self._decisions: List[ReliabilityDecision] = []
        self._evidences: List[PredictionEvidence] = []

    def record_decision(self, decision: ReliabilityDecision) -> None:
        self._decisions.append(decision)

    def record_evidence(self, evidence: PredictionEvidence) -> None:
        self._evidences.append(evidence)

    def list_decisions(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in self._decisions[-limit:]]

    def list_evidence(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._evidences[-limit:]]

    def clear(self) -> None:
        self._decisions.clear()
        self._evidences.clear()
