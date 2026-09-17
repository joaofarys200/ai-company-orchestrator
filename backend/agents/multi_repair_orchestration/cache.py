"""
JARVIS OS — Phase 55: Transactional Multi-Repair Orchestration & Convergence
Multi-Repair Experience Cache.
Caches transaction outcomes, successful/failed sequences, and revealed failures.
Enforces the core principle: Memory is not authority.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class MultiRepairExperienceCache:
    """
    Maintains historical memory of multi-repair transactions to accelerate future planning,
    while treating current live verification as the sole source of ground truth.
    """

    def __init__(self):
        self._entries: Dict[str, Dict[str, Any]] = {}

    def record_transaction(
        self,
        cluster_signature: str,
        transaction_id: str,
        repair_sequence: List[str],
        convergence_status: str,
        success: bool,
        revealed_failures: List[str] | None = None,
    ) -> None:
        self._entries[cluster_signature] = {
            "transaction_id": transaction_id,
            "repair_sequence": repair_sequence,
            "convergence_status": convergence_status,
            "success": success,
            "revealed_failures": revealed_failures or [],
            "timestamp": time.time(),
        }

    def get_experience(self, cluster_signature: str) -> Optional[Dict[str, Any]]:
        return self._entries.get(cluster_signature)

    def clear(self) -> None:
        self._entries.clear()
