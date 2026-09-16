"""
JARVIS OS — Phase 56: Human Escalation Manager
Handles the 10 formal escalation reasons, dispatches tickets, and enforces economic safety gates.
"""

from __future__ import annotations

import time
import hashlib
from typing import Dict, Any, List, Optional
from agents.repair_convergence_governance.models import (
    EscalationStatus,
    EscalationTier,
    EscalationTicket,
    TerminationEscalationReason,
)


class HumanEscalationManager:
    """Manages escalation lifecycle, tier assignment, and diagnostic packaging for human review."""

    def __init__(self):
        self.tickets: List[EscalationTicket] = []

    def create_escalation_ticket(
        self,
        mission_id: str,
        repair_plan_id: str,
        reason: TerminationEscalationReason,
        context_summary: Dict[str, Any],
        suggested_resolutions: Optional[List[str]] = None,
        tier: Optional[EscalationTier] = None,
    ) -> EscalationTicket:
        """Creates and records an immutable escalation ticket mapped to specific reasons."""
        ts = time.time()
        ticket_raw = f"{mission_id}:{repair_plan_id}:{reason.value}:{ts}"
        ticket_id = "tkt_" + hashlib.sha256(ticket_raw.encode("utf-8")).hexdigest()[:12]

        assigned_tier = tier or self._derive_tier(reason)
        resolutions = suggested_resolutions or self._generate_default_resolutions(reason)

        ticket = EscalationTicket(
            ticket_id=ticket_id,
            tier=assigned_tier,
            status=EscalationStatus.PENDING,
            created_at=ts,
            mission_id=mission_id,
            repair_plan_id=repair_plan_id,
            reason=reason.value,
            context_summary=context_summary,
            suggested_resolutions=resolutions,
        )
        self.tickets.append(ticket)
        return ticket

    def _derive_tier(self, reason: TerminationEscalationReason) -> EscalationTier:
        if reason in (TerminationEscalationReason.SECURITY_RISK,):
            return EscalationTier.TIER_3_SECURITY_LEAD
        elif reason in (TerminationEscalationReason.ECONOMIC_RISK, TerminationEscalationReason.BUDGET_EXHAUSTED):
            return EscalationTier.TIER_4_HUMAN_IN_THE_LOOP
        elif reason in (TerminationEscalationReason.CYCLE_DETECTED, TerminationEscalationReason.RISK_THRESHOLD):
            return EscalationTier.TIER_2_DEVELOPER_REVIEW
        else:
            return EscalationTier.TIER_1_AUTO_ASSIST

    def _generate_default_resolutions(self, reason: TerminationEscalationReason) -> List[str]:
        mapping = {
            TerminationEscalationReason.REPEATED_FAILURE: [
                "Revert to previous checkpoint and inspect error root cause.",
                "Review patch generation hypotheses for conflicting assumptions."
            ],
            TerminationEscalationReason.CYCLE_DETECTED: [
                "Trigger atomic rollback to stable state pre-cycle.",
                "Partition failure cluster to break circular dependency."
            ],
            TerminationEscalationReason.RISK_THRESHOLD: [
                "Conduct manual security and architecture review before re-attempting.",
                "Isolate repair blast radius to safe sub-modules."
            ],
            TerminationEscalationReason.ECONOMIC_RISK: [
                "Obtain explicit supervisor signature for financial/cost-impacting mutations.",
                "Enforce rollback to baseline; block autonomous auto-commit."
            ],
            TerminationEscalationReason.SECURITY_RISK: [
                "Halt repair loop immediately; inspect unauthorized file mutation.",
                "Restore protected assets from Git baseline."
            ],
            TerminationEscalationReason.BUDGET_EXHAUSTED: [
                "Request manual budget extension from mission operator.",
                "Accept partial repair outcome with remaining unverified issues documented."
            ],
        }
        return mapping.get(reason, ["Review diagnostic context and decide whether to continue, rollback, or abort."])

    def evaluate_economic_safety(
        self,
        is_economic_operation: bool,
        is_diverging_or_stalled_or_cycling: bool,
    ) -> Tuple[bool, Optional[TerminationEscalationReason]]:
        """Sovereign Economic Safety rule: any divergence/stall/cycle in economic operations blocks auto-commit."""
        if is_economic_operation and is_diverging_or_stalled_or_cycling:
            return False, TerminationEscalationReason.ECONOMIC_RISK
        return True, None
