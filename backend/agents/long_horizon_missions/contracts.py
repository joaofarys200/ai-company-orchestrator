"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
Contract Consistency & Schema Governance (Integrating F48).
Computes deterministic contract hashes and guards against silent breaking changes.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Tuple


class ContractConsistencyGovernor:
    """Guards contract consistency and verifies schemas across mission milestones."""

    def __init__(self):
        self.contract_history: List[Dict[str, Any]] = []

    def compute_contract_hash(self, contract_definitions: Dict[str, Any]) -> str:
        serialized = json.dumps(contract_definitions, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def verify_contracts(
        self,
        current_contracts: Dict[str, Any],
        baseline_hash: str,
    ) -> Tuple[bool, str, List[str]]:
        """
        Validates that active contracts match baseline or valid evolved contract migrations.
        """
        curr_hash = self.compute_contract_hash(current_contracts)
        breaks: List[str] = []

        if baseline_hash and curr_hash != baseline_hash:
            if not current_contracts.get("__governed_migration__", False):
                breaks.append("UNGOVERNED_CONTRACT_BREAK")

        valid = len(breaks) == 0
        return valid, curr_hash, breaks
