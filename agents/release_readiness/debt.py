"""
Technical Debt Readiness Gate
Phase 70 — Autonomous Release Readiness & Production Governance

Evaluates technical debt items from Phase 68/69 against release safety policies.
"""

from __future__ import annotations
from typing import Dict, Any, List
from .models import BlockerCategory, ReleaseBlocker


class TechnicalDebtGate:
    """Gates releases based on technical debt posture and unresolved liabilities."""

    @classmethod
    def evaluate(
        cls,
        technical_debt_snapshot: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluates technical debt snapshot:
        - CRITICAL_SECURITY_DEBT -> BLOCKED
        - CRITICAL_QUALITY_DEGRADATION -> BLOCKED
        - UNRESOLVED_UNKNOWN -> HUMAN_REVIEW
        - ACCEPTED_WITH_DEBT -> does not imply automatically RELEASE_READY
        """
        critical_security_debts = technical_debt_snapshot.get("critical_security_debt_count", 0)
        critical_quality_debts = technical_debt_snapshot.get("critical_quality_debt_count", 0)
        unresolved_unknowns = technical_debt_snapshot.get("unresolved_unknown_count", 0)
        deferred_debt_count = technical_debt_snapshot.get("deferred_debt_count", 0)
        accepted_with_debt = technical_debt_snapshot.get("accepted_with_debt", False)

        blockers: List[ReleaseBlocker] = []
        requires_human_review = False
        review_reasons: List[str] = []

        if critical_security_debts > 0:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-debt-critical-security",
                category=BlockerCategory.CRITICAL_SECURITY,
                description=f"Candidate blocked by {critical_security_debts} critical security technical debts",
                evidence=f"Active security debt items: {critical_security_debts} require remediation before release."
            ))

        if critical_quality_debts > 0:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-debt-critical-quality",
                category=BlockerCategory.QUALITY_GATE_BLOCKED,
                description=f"Candidate blocked by {critical_quality_debts} critical quality debts",
                evidence=f"Active quality debt items: {critical_quality_debts} breach release budget thresholds."
            ))

        if unresolved_unknowns > 0:
            requires_human_review = True
            review_reasons.append(
                f"{unresolved_unknowns} debt items with unclassified or unknown root causes require human engineering review"
            )

        status = "READY"
        if blockers:
            status = "BLOCKED"
        elif requires_human_review:
            status = "HUMAN_REVIEW"
        elif accepted_with_debt or deferred_debt_count > 0:
            status = "READY_WITH_RISK"

        return {
            "status": status,
            "critical_security_debts": critical_security_debts,
            "critical_quality_debts": critical_quality_debts,
            "unresolved_unknowns": unresolved_unknowns,
            "deferred_debt_count": deferred_debt_count,
            "accepted_with_debt": accepted_with_debt,
            "blockers": blockers,
            "requires_human_review": requires_human_review,
            "review_reasons": review_reasons
        }
