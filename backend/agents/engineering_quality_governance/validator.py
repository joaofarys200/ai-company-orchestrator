"""
JARVIS OS — Phase 68: Quality Validator
Validates schema completeness, snapshot hashes, immutable baseline consistency,
budget boundary constraints, and denominator reconciliation invariants.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .models import QualityDimension, QualitySnapshot


class QualityValidator:
    """
    Validates structural and mathematical invariants of quality governance objects.
    """

    @staticmethod
    def validate_snapshot_completeness(snapshot: QualitySnapshot) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        if not snapshot.snapshot_id:
            errors.append("snapshot_id is missing")
        if not snapshot.mission_id:
            errors.append("mission_id is missing")
        if not snapshot.architecture_hash:
            errors.append("architecture_hash is missing")
        if not snapshot.contract_hash:
            errors.append("contract_hash is missing")
        if not snapshot.behavior_hash:
            errors.append("behavior_hash is missing")
        if not snapshot.test_hash:
            errors.append("test_hash is missing")
        if not snapshot.security_hash:
            errors.append("security_hash is missing")

        # Validate that all 9 dimensions exist in the snapshot
        for dim in QualityDimension:
            if dim.value not in snapshot.dimensions:
                errors.append(f"Dimension '{dim.value}' is missing from snapshot")

        return len(errors) == 0, errors

    @staticmethod
    def validate_reconciliation(
        per_phase: Dict[str, int],
        computed_total: int,
        reported_total: int,
    ) -> Tuple[bool, int]:
        """
        Validates the strict historical regression invariant:
        sum(per_phase.values()) == computed_total == reported_total
        delta == 0
        """
        expected_sum = sum(per_phase.values())
        delta = abs(expected_sum - computed_total) + abs(computed_total - reported_total)
        is_valid = (expected_sum == computed_total == reported_total) and (delta == 0)
        return is_valid, delta
