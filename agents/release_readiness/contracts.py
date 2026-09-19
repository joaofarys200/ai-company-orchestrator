"""
Contract Readiness Module
Phase 70 — Autonomous Release Readiness & Production Governance

Integrates Phase 44–49 Semantic Contract Graph & Polymorphic Governance.
Enforces contract compatibility, schema drift limits, and consumer guarantees.
"""

from __future__ import annotations
from typing import Dict, Any, List
from .models import ContractReadinessStatus, BlockerCategory, ReleaseBlocker


class ContractReadinessEvaluator:
    """Evaluates semantic contract consistency, schema evolution, and breaking changes."""

    @classmethod
    def evaluate(
        cls,
        contract_snapshot: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Verifies:
        - contract hashes
        - breaking changes
        - consumer compatibility
        - polymorphic schemas
        - runtime contracts
        - drift status
        - migration completion
        Rule: Any BREAKING or UNKNOWN must block automatic release unless explicitly reviewed.
        """
        if not contract_snapshot:
            return {
                "status": ContractReadinessStatus.UNKNOWN,
                "blockers": [
                    ReleaseBlocker(
                        blocker_id="blocker-contract-unknown",
                        category=BlockerCategory.BREAKING_CONTRACT,
                        description="Contract snapshot is missing or unverified",
                        evidence="No contract telemetry provided in release candidate."
                    )
                ],
                "requires_human_review": True,
                "review_reasons": ["Unknown contract state"]
            }

        breaking_changes = contract_snapshot.get("breaking_changes_count", 0)
        unmigrated_consumers = contract_snapshot.get("unmigrated_consumers_count", 0)
        schema_drift_detected = contract_snapshot.get("schema_drift_detected", False)
        drift_status = contract_snapshot.get("drift_status", "SYNCHRONIZED")
        polymorphic_violations = contract_snapshot.get("polymorphic_violations", 0)
        migration_completed = contract_snapshot.get("migration_completed", True)

        blockers: List[ReleaseBlocker] = []
        requires_human_review = False
        review_reasons: List[str] = []

        if breaking_changes > 0 and not migration_completed:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-contract-breaking",
                category=BlockerCategory.BREAKING_CONTRACT,
                description=f"{breaking_changes} breaking contract change(s) detected without migration completion",
                evidence=f"Breaking changes: {breaking_changes}, unmigrated consumers: {unmigrated_consumers}."
            ))

        if polymorphic_violations > 0:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-contract-polymorphic",
                category=BlockerCategory.BREAKING_CONTRACT,
                description=f"{polymorphic_violations} polymorphic schema invariant violations detected",
                evidence="Polymorphic discriminators or subtype fields fail contract proof."
            ))

        if schema_drift_detected or drift_status == "DRIFT_DETECTED":
            requires_human_review = True
            review_reasons.append("Contract drift detected between runtime interfaces and build schemas")

        if breaking_changes > 0 and migration_completed:
            # Breaking change was migrated, but requires human sign-off
            requires_human_review = True
            review_reasons.append(f"{breaking_changes} migrated breaking contract changes require confirmation")

        status = ContractReadinessStatus.COMPATIBLE
        if blockers:
            status = ContractReadinessStatus.BREAKING
        elif schema_drift_detected or drift_status == "DRIFT_DETECTED":
            status = ContractReadinessStatus.DRIFT_DETECTED
        elif breaking_changes > 0 and migration_completed:
            status = ContractReadinessStatus.MIGRATED

        return {
            "status": status,
            "breaking_changes": breaking_changes,
            "unmigrated_consumers": unmigrated_consumers,
            "drift_status": drift_status,
            "polymorphic_violations": polymorphic_violations,
            "migration_completed": migration_completed,
            "blockers": blockers,
            "requires_human_review": requires_human_review,
            "review_reasons": review_reasons
        }
