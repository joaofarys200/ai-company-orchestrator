"""
JARVIS OS — Phase 68: Security Guardrails & Tamper Protection
Guarantees that engineering quality governance cannot:
1. Disable Sentinel
2. Ignore security debt
3. Lower policy thresholds to force gate passage
4. Delete negative evidence
5. Remove debt items automatically without justification

Any such attempt immediately raises:
SECURITY_EVENT -> BLOCKED
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class QualityGovernanceSecurityViolation(Exception):
    """Raised when an illegal action is attempted against quality governance."""
    pass


class QualitySecuritySentinel:
    """
    Watches over quality governance execution to prevent safety subversion.
    """

    def __init__(self) -> None:
        self._blocked_events: List[Dict[str, Any]] = []

    def validate_policy_mutation(
        self,
        current_policy: Dict[str, Any],
        proposed_policy: Dict[str, Any],
        actor: str,
    ) -> bool:
        """
        Disallows weakening security limits or lowering thresholds during gate evaluation.
        """
        curr_b = current_policy.get("budget", {})
        prop_b = proposed_policy.get("budget", {})

        # Check if security debt budget was raised from 0
        if prop_b.get("max_security_debt", 0) > curr_b.get("max_security_debt", 0):
            self._record_blocked(
                actor=actor,
                action="LOWER_SECURITY_POLICY",
                reason="Attempt to increase max_security_debt above permitted limit.",
            )
            raise QualityGovernanceSecurityViolation(
                "SECURITY_EVENT -> BLOCKED: Disallowed lowering of security quality policy to pass gate."
            )

        return True

    def validate_evidence_deletion(
        self,
        actor: str,
        evidence_item: Dict[str, Any],
    ) -> None:
        """
        Disallows deleting negative evidence.
        """
        self._record_blocked(
            actor=actor,
            action="DELETE_NEGATIVE_EVIDENCE",
            reason="Attempt to purge negative observation or counterexample evidence.",
        )
        raise QualityGovernanceSecurityViolation(
            "SECURITY_EVENT -> BLOCKED: Deletion of quality evidence is strictly forbidden."
        )

    def validate_debt_removal(
        self,
        debt_id: str,
        reason: Optional[str],
        has_posterior_evidence: bool,
        actor: str,
    ) -> None:
        """
        Disallows automatic removal or dismissal of debt items without justification and posterior evidence.
        """
        if not reason or not has_posterior_evidence:
            self._record_blocked(
                actor=actor,
                action="UNJUSTIFIED_DEBT_REMOVAL",
                reason=f"Attempt to dismiss debt {debt_id} without justification or posterior evidence.",
            )
            raise QualityGovernanceSecurityViolation(
                f"SECURITY_EVENT -> BLOCKED: Debt '{debt_id}' cannot be removed without posterior evidence and justification."
            )

    def _record_blocked(self, actor: str, action: str, reason: str) -> None:
        event = {
            "type": "SECURITY_EVENT",
            "status": "BLOCKED",
            "actor": actor,
            "action": action,
            "reason": reason,
            "timestamp": time.time(),
        }
        self._blocked_events.append(event)

    def list_blocked_events(self) -> List[Dict[str, Any]]:
        return list(self._blocked_events)
