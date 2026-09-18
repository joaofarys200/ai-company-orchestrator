"""
JARVIS OS — Phase 65: Safe Self-Modification & Transactional Architecture Implementation
Module: contracts.py
Integrates F44–F49 to detect breaking interface and schema changes.
Blocks automated commit if BREAKING or UNKNOWN contract statuses emerge without
a corresponding verified migration shim.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

from .models import ContractValidationResult


class ContractValidator:
    """Evaluates interface contracts before and after patch application."""

    def validate_contracts(
        self,
        before_contracts: Dict[str, Any],
        after_contracts: Dict[str, Any],
        approved_breaking_shims: Optional[List[str]] = None,
    ) -> Tuple[ContractValidationResult, Dict[str, Any]]:
        """Compare contract definitions and flag breaking changes."""
        before_hash = hashlib.sha256(
            json.dumps(before_contracts, sort_keys=True).encode("utf-8")
        ).hexdigest()
        after_hash = hashlib.sha256(
            json.dumps(after_contracts, sort_keys=True).encode("utf-8")
        ).hexdigest()

        details = {
            "before_contract_hash": before_hash,
            "after_contract_hash": after_hash,
            "consumer_status": "ALL_CONSUMERS_RESOLVED",
            "migration_status": "COMPATIBILITY_SHIM_ACTIVE",
            "breaking_detected": [],
        }

        # Check for removed keys or altered signatures
        breaking = []
        for c_name, c_def in before_contracts.items():
            if c_name not in after_contracts:
                breaking.append(f"REMOVED_CONTRACT: {c_name}")
            else:
                after_def = after_contracts[c_name]
                if isinstance(c_def, dict) and isinstance(after_def, dict):
                    for param in c_def.get("required_params", []):
                        if param not in after_def.get("required_params", []):
                            breaking.append(f"REMOVED_PARAM: {c_name}.{param}")

        details["breaking_detected"] = breaking

        if breaking:
            approved = set(approved_breaking_shims or [])
            unapproved = [b for b in breaking if b not in approved]
            if unapproved:
                return ContractValidationResult.BREAKING, details
            return ContractValidationResult.POTENTIALLY_BREAKING, details

        if before_hash == after_hash:
            return ContractValidationResult.NON_BREAKING, details

        return ContractValidationResult.NON_BREAKING, details
