"""
Rollback Readiness Module
Phase 70 — Autonomous Release Readiness & Production Governance

Integrates Phase 65 Safe Self-Modification & Transactional Engine.
Verifies rollback snapshots, migration reversibility, and recovery checkpoints.
Rule: Never permits RELEASE_READY when rollback is mandatory and unverified.
"""

from __future__ import annotations
from typing import Dict, Any, List
from .models import RollbackReadinessStatus, BlockerCategory, ReleaseBlocker


class RollbackReadinessEvaluator:
    """Evaluates transactional revert paths, migration rollback, and snapshot availability."""

    @classmethod
    def evaluate(
        cls,
        rollback_data: Dict[str, Any],
        rollback_mandatory: bool = True
    ) -> Dict[str, Any]:
        """
        Verifies:
        - rollback snapshot
        - artifact availability
        - database rollback strategy
        - configuration rollback
        - migration rollback
        - verification rollback
        - recovery checkpoints
        Results:
        - ROLLBACK_READY
        - ROLLBACK_PARTIAL
        - ROLLBACK_UNVERIFIED
        - ROLLBACK_BLOCKED
        """
        if not rollback_data:
            blocker = ReleaseBlocker(
                blocker_id="blocker-rb-missing",
                category=BlockerCategory.MISSING_ROLLBACK,
                description="Rollback procedure and snapshot completely unverified",
                evidence="No rollback manifest provided."
            )
            return {
                "status": RollbackReadinessStatus.ROLLBACK_BLOCKED,
                "blockers": [blocker] if rollback_mandatory else [],
                "requires_human_review": True,
                "review_reasons": ["Missing rollback manifest"]
            }

        snapshot_available = rollback_data.get("snapshot_available", True)
        artifacts_available = rollback_data.get("artifacts_available", True)
        db_rollback_strategy = rollback_data.get("db_rollback_strategy", "AVAILABLE")  # AVAILABLE, NONE, IRREVERSIBLE
        config_rollback_supported = rollback_data.get("config_rollback_supported", True)
        migration_reversible = rollback_data.get("migration_reversible", True)
        checkpoint_verified = rollback_data.get("checkpoint_verified", True)
        drill_tested = rollback_data.get("drill_tested", True)

        blockers: List[ReleaseBlocker] = []
        requires_human_review = False
        review_reasons: List[str] = []

        if not snapshot_available or not artifacts_available:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-rb-snapshot-missing",
                category=BlockerCategory.MISSING_ROLLBACK,
                description="Previous immutable release snapshot or artifact bundle is missing",
                evidence=f"Snapshot: {snapshot_available}, Artifacts: {artifacts_available}."
            ))

        if not migration_reversible or db_rollback_strategy == "IRREVERSIBLE":
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-rb-irreversible-migration",
                category=BlockerCategory.MISSING_ROLLBACK,
                description="Irreversible schema or state migration detected without safe rollback plan",
                evidence=f"Migration reversible: {migration_reversible}, DB strategy: {db_rollback_strategy}."
            ))

        if not checkpoint_verified:
            if rollback_mandatory:
                blockers.append(ReleaseBlocker(
                    blocker_id="blocker-rb-unverified-checkpoint",
                    category=BlockerCategory.MISSING_ROLLBACK,
                    description="Mandatory rollback recovery checkpoint is unverified",
                    evidence="Pre-release state checkpoint has not been validated for restoration."
                ))
            else:
                requires_human_review = True
                review_reasons.append("Rollback recovery checkpoint has not been verified")

        if not config_rollback_supported:
            requires_human_review = True
            review_reasons.append("Configuration change lacks automated reversion mechanism")

        if not drill_tested:
            requires_human_review = True
            review_reasons.append("Rollback execution has not undergone a rehearsal/drill test")

        status = RollbackReadinessStatus.ROLLBACK_READY
        if blockers:
            status = RollbackReadinessStatus.ROLLBACK_BLOCKED
        elif not checkpoint_verified:
            status = RollbackReadinessStatus.ROLLBACK_UNVERIFIED
        elif requires_human_review or not config_rollback_supported or not drill_tested:
            status = RollbackReadinessStatus.ROLLBACK_PARTIAL

        return {
            "status": status,
            "snapshot_available": snapshot_available,
            "artifacts_available": artifacts_available,
            "db_rollback_strategy": db_rollback_strategy,
            "config_rollback_supported": config_rollback_supported,
            "migration_reversible": migration_reversible,
            "checkpoint_verified": checkpoint_verified,
            "drill_tested": drill_tested,
            "blockers": blockers,
            "requires_human_review": requires_human_review,
            "review_reasons": review_reasons
        }
