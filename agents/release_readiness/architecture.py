"""
Architecture Readiness Module
Phase 70 — Autonomous Release Readiness & Production Governance

Integrates Phase 64 Architecture Evolution & Refactoring governance.
Validates structural integrity, forbidden boundaries, and circular cycles.
"""

from __future__ import annotations
from typing import Dict, Any, List
from .models import ArchitectureClassification, BlockerCategory, ReleaseBlocker


class ArchitectureReadinessEvaluator:
    """Evaluates architectural boundaries, cycle condensation, and modular drift."""

    @classmethod
    def evaluate(
        cls,
        architecture_snapshot: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validates:
        - forbidden boundaries
        - unresolved SCCs (strongly connected components)
        - dynamic boundaries
        - architecture debt
        - migration state
        - architecture drift
        Classifications: HEALTHY, DEGRADED_ACCEPTABLE, REVIEW_REQUIRED, BLOCKED, UNKNOWN
        """
        if not architecture_snapshot:
            return {
                "classification": ArchitectureClassification.UNKNOWN,
                "blockers": [
                    ReleaseBlocker(
                        blocker_id="blocker-arch-missing-snapshot",
                        category=BlockerCategory.MISSING_MANDATORY_EVIDENCE,
                        description="Architecture snapshot missing from baseline",
                        evidence="Empty architecture snapshot provided."
                    )
                ],
                "requires_human_review": True,
                "review_reasons": ["Missing architecture snapshot"]
            }

        forbidden_boundary_violations = architecture_snapshot.get("forbidden_boundary_violations", 0)
        unresolved_sccs = architecture_snapshot.get("unresolved_sccs", 0)
        architecture_drift_pct = architecture_snapshot.get("architecture_drift_pct", 0.0)
        architecture_debt_score = architecture_snapshot.get("architecture_debt_score", 0.0)
        migration_in_progress = architecture_snapshot.get("migration_in_progress", False)
        migration_state = architecture_snapshot.get("migration_state", "COMPLETED")

        blockers: List[ReleaseBlocker] = []
        requires_human_review = False
        review_reasons: List[str] = []

        if forbidden_boundary_violations > 0:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-arch-forbidden-boundary",
                category=BlockerCategory.INCOMPATIBLE_BEHAVIOR,
                description=f"Forbidden architectural boundary violations detected: {forbidden_boundary_violations}",
                evidence=f"{forbidden_boundary_violations} cross-boundary dependency rule violations detected."
            ))

        if unresolved_sccs > 2:  # Critical cyclic entanglements
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-arch-unresolved-sccs",
                category=BlockerCategory.QUALITY_GATE_BLOCKED,
                description=f"Candidate has {unresolved_sccs} unresolved strongly connected component cycles",
                evidence="Cyclic dependency condensation exceeds permissible threshold."
            ))
        elif unresolved_sccs > 0:
            requires_human_review = True
            review_reasons.append(f"{unresolved_sccs} cyclic SCCs remain present in dependency graph")

        if migration_in_progress and migration_state != "COMPLETED":
            requires_human_review = True
            review_reasons.append(f"Incomplete architectural migration: state is '{migration_state}'")

        if architecture_drift_pct > 25.0:
            requires_human_review = True
            review_reasons.append(f"Architectural drift is high ({architecture_drift_pct:.1f}%)")

        classification = ArchitectureClassification.HEALTHY
        if blockers:
            classification = ArchitectureClassification.BLOCKED
        elif requires_human_review:
            classification = ArchitectureClassification.REVIEW_REQUIRED
        elif architecture_debt_score > 0.3 or unresolved_sccs > 0:
            classification = ArchitectureClassification.DEGRADED_ACCEPTABLE

        return {
            "classification": classification,
            "forbidden_boundary_violations": forbidden_boundary_violations,
            "unresolved_sccs": unresolved_sccs,
            "architecture_drift_pct": architecture_drift_pct,
            "architecture_debt_score": architecture_debt_score,
            "migration_state": migration_state,
            "blockers": blockers,
            "requires_human_review": requires_human_review,
            "review_reasons": review_reasons
        }
