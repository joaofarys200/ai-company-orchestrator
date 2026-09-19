"""
Behavior Readiness Module
Phase 70 — Autonomous Release Readiness & Production Governance

Integrates Phase 50–52 Behavioral Contract Proof & Risk-Directed Exploration.
Verifies invariants, concurrency bounds, idempotency, and counterexamples.
"""

from __future__ import annotations
from typing import Dict, Any, List
from .models import BehaviorReadinessStatus, BlockerCategory, ReleaseBlocker


class BehaviorReadinessEvaluator:
    """Evaluates runtime behavioral contracts, state transitions, and idempotency."""

    @classmethod
    def evaluate(
        cls,
        behavior_snapshot: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Verifies:
        - invariants
        - behavioral baselines
        - ordering
        - retries
        - concurrency
        - idempotency
        - state transitions
        - counterexamples
        Results:
        - PRESERVED_WITHIN_SCOPE
        - POTENTIAL_DRIFT -> HUMAN_REVIEW
        - INCOMPATIBLE -> BLOCKED
        - INSUFFICIENT_EVIDENCE
        """
        if not behavior_snapshot:
            return {
                "status": BehaviorReadinessStatus.INSUFFICIENT_EVIDENCE,
                "blockers": [
                    ReleaseBlocker(
                        blocker_id="blocker-behavior-no-evidence",
                        category=BlockerCategory.MISSING_MANDATORY_EVIDENCE,
                        description="Behavioral proof evidence is completely absent",
                        evidence="Empty behavior snapshot provided."
                    )
                ],
                "requires_human_review": True,
                "review_reasons": ["Insufficient behavioral evidence"]
            }

        counterexamples_count = behavior_snapshot.get("counterexamples_count", 0)
        invariants_violated = behavior_snapshot.get("invariants_violated_count", 0)
        idempotency_failures = behavior_snapshot.get("idempotency_failures_count", 0)
        concurrency_hazards = behavior_snapshot.get("concurrency_hazards_count", 0)
        potential_drift = behavior_snapshot.get("potential_drift_detected", False)
        evidence_depth = behavior_snapshot.get("evidence_depth", "SUFFICIENT")

        blockers: List[ReleaseBlocker] = []
        requires_human_review = False
        review_reasons: List[str] = []

        if invariants_violated > 0 or counterexamples_count > 0:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-behavior-invariant-violated",
                category=BlockerCategory.INCOMPATIBLE_BEHAVIOR,
                description=f"Behavioral proof found {invariants_violated} invariant violations and {counterexamples_count} counterexamples",
                evidence=f"Active counterexamples: {counterexamples_count}. Violations: {invariants_violated}."
            ))

        if idempotency_failures > 0 or concurrency_hazards > 0:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-behavior-concurrency-hazard",
                category=BlockerCategory.INCOMPATIBLE_BEHAVIOR,
                description=f"Concurrency or idempotency failure detected (hazards: {concurrency_hazards}, failures: {idempotency_failures})",
                evidence="Transactional retries or concurrent state transitions produce non-deterministic results."
            ))

        if potential_drift:
            requires_human_review = True
            review_reasons.append("Potential behavioral state transition drift detected against baseline")

        if evidence_depth == "INSUFFICIENT":
            requires_human_review = True
            review_reasons.append("Behavioral test exploration depth is insufficient to prove invariant safety")

        status = BehaviorReadinessStatus.PRESERVED_WITHIN_SCOPE
        if blockers:
            status = BehaviorReadinessStatus.INCOMPATIBLE
        elif potential_drift:
            status = BehaviorReadinessStatus.POTENTIAL_DRIFT
        elif evidence_depth == "INSUFFICIENT":
            status = BehaviorReadinessStatus.INSUFFICIENT_EVIDENCE

        return {
            "status": status,
            "invariants_violated": invariants_violated,
            "counterexamples_count": counterexamples_count,
            "concurrency_hazards": concurrency_hazards,
            "idempotency_failures": idempotency_failures,
            "potential_drift": potential_drift,
            "evidence_depth": evidence_depth,
            "blockers": blockers,
            "requires_human_review": requires_human_review,
            "review_reasons": review_reasons
        }
