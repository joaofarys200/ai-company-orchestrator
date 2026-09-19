"""
Phase 71 — Deterministic Escalation Engine
Creates human review and infrastructure escalation tickets when autonomous recovery boundaries are reached.
"""

from __future__ import annotations

import time
import uuid
from typing import List, Optional
from .models import EscalationState, EscalationTicket, Incident, SeverityLevel


class EscalationManager:
    """
    Manages operational escalations to human operators or infrastructure provisioning queues.
    """

    def __init__(self, service_id: str):
        self.service_id = service_id
        self._tickets: List[EscalationTicket] = []

    def escalate(
        self,
        incident: Incident,
        state: EscalationState,
        reason: str,
        risk_level: str = "HIGH",
        suggested_actions: Optional[List[str]] = None,
    ) -> EscalationTicket:
        """Issues an escalation ticket."""
        ticket = EscalationTicket(
            ticket_id=f"tkt-esc-{uuid.uuid4().hex[:8]}",
            incident_id=incident.incident_id,
            state=state,
            reason=reason,
            risk_level=risk_level,
            suggested_actions=suggested_actions or ["Manual diagnosis required by on-call engineer."],
            created_at=time.time(),
        )
        self._tickets.append(ticket)
        return ticket

    def check_and_escalate(
        self,
        incident: Incident,
        confidence: float,
        recovery_attempts: int,
        infrastructure_available: bool = True,
        evidence_sufficient: bool = True,
    ) -> Optional[EscalationTicket]:
        """
        Evaluates deterministic escalation rules:
        1. Absent infrastructure -> INFRASTRUCTURE_REQUIRED
        2. Insufficient evidence -> INSUFFICIENT_EVIDENCE
        3. Recovery exhausted (>= 3 attempts) -> RECOVERY_EXHAUSTED
        4. Low confidence (< 0.7) -> HUMAN_REVIEW
        """
        if not infrastructure_available:
            return self.escalate(
                incident=incident,
                state=EscalationState.INFRASTRUCTURE_REQUIRED,
                reason="Target deployment infrastructure is absent or unreachable.",
                risk_level="HIGH",
                suggested_actions=["Provision local Docker/Kubernetes runner or execute via local runtime."],
            )

        if not evidence_sufficient:
            return self.escalate(
                incident=incident,
                state=EscalationState.INSUFFICIENT_EVIDENCE,
                reason="Incident telemetry lacks conclusive supporting evidence for autonomous recovery.",
                risk_level="MEDIUM",
                suggested_actions=["Inspect raw process stdout/stderr logs."],
            )

        if recovery_attempts >= 3:
            return self.escalate(
                incident=incident,
                state=EscalationState.RECOVERY_EXHAUSTED,
                reason=f"Recovery failed {recovery_attempts} consecutive times; autonomous options exhausted.",
                risk_level="CRITICAL",
                suggested_actions=["Execute manual database/process rollback and engage team lead."],
            )

        if confidence < 0.70:
            return self.escalate(
                incident=incident,
                state=EscalationState.HUMAN_REVIEW,
                reason=f"Diagnosis confidence ({confidence:.2f}) below autonomous threshold (0.70).",
                risk_level="MEDIUM",
                suggested_actions=["Verify hypothesis before applying speculative patch."],
            )

        return None

    def get_tickets(self) -> List[EscalationTicket]:
        return list(self._tickets)
