"""
JARVIS OS — Phase 53: Universal Project Preflight & Runtime Failure Auto-Recovery
Deterministic Failure Cache & Memory Bridge: Indexes fingerprints and known repairs.
Memory is consultive, never authoritative: current physical evidence is always mandatory.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from agents.project_preflight.models import FailureFingerprint, RepairPlan


class DeterministicFailureCache:
    """
    Stores failure fingerprints and historical repair outcomes.
    Enforces 'Memory is not authority': retrieved patterns must still pass strict preflight checks.
    """

    def __init__(self) -> None:
        self._entries: Dict[str, Dict[str, Any]] = {}

    def record_repair_outcome(
        self,
        fingerprint: FailureFingerprint,
        repair_plan: RepairPlan,
        success: bool,
    ) -> str:
        fp_hash = fingerprint.compute_fingerprint()
        entry = {
            "fingerprint_hash": fp_hash,
            "error_class": fingerprint.error_class,
            "runtime": fingerprint.runtime,
            "symbol": fingerprint.symbol,
            "repair_category": repair_plan.category.value,
            "success": success,
            "success_count": 1 if success else 0,
            "failure_count": 0 if success else 1,
            "recorded_at": time.time(),
        }
        if fp_hash in self._entries:
            prev = self._entries[fp_hash]
            entry["success_count"] += prev.get("success_count", 0)
            entry["failure_count"] += prev.get("failure_count", 0)

        self._entries[fp_hash] = entry
        return fp_hash

    def lookup_known_repair(self, fingerprint: FailureFingerprint) -> Optional[Dict[str, Any]]:
        fp_hash = fingerprint.compute_fingerprint()
        return self._entries.get(fp_hash)
