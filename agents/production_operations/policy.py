"""
Phase 71 — Operational Governance Policy & Decision Gate
Determines CONTINUE, RECOVER, ROLLBACK, ESCALATE decisions and evaluates AUTONOMOUS_REMEDIATION_ALLOWED gate.
"""

from __future__ import annotations

import time
import uuid
from typing import List, Optional
from .models import (
    Incident,
    OperationalState,
    ProductionDecision,
    RecoveryPlan,
    RemediationSafety,
    SeverityLevel,
)


class OperationalGovernancePolicy:
    """
    Evaluates system state and active incidents to emit formal production decisions.
    """

    def __init__(self, service_id: str):
        self.service_id = service_id
        self._decisions: List[ProductionDecision] = []

    def evaluate_decision(
        self,
        current_state: OperationalState,
        active_incidents: List[Incident],
        proposed_plan: Optional[RecoveryPlan] = None,
        operator_override: bool = False,
    ) -> ProductionDecision:
        """
        Determines the recommended operational action:
        - CONTINUE: Healthy, no active incidents
        - RECOVER: Active incident with an approved autonomous recovery plan
        - ROLLBACK: SEV0, catastrophic outage, or repeated recovery failures
        - ESCALATE: Unmapped incident, low confidence, absent infrastructure, or unapproved high risk
        """
        decision_id = f"dec-ops-{uuid.uuid4().hex[:8]}"

        if not active_incidents and current_state in {OperationalState.HEALTHY, OperationalState.READY_FOR_OPERATIONS}:
            rec_action = "CONTINUE"
            allowed = True
            rationale = "System is operating normally within established SLO boundaries. Zero active incidents."
            plan_id = None
            esc_id = None

        elif any(inc.severity == SeverityLevel.SEV0 for inc in active_incidents):
            rec_action = "ROLLBACK"
            allowed = True
            rationale = "SEV0 incident detected. Governance policy mandates immediate rollback to halt corruption or outage."
            plan_id = proposed_plan.plan_id if proposed_plan else None
            esc_id = None

        elif proposed_plan is not None:
            if proposed_plan.safety == RemediationSafety.FORBIDDEN:
                rec_action = "ESCALATE"
                allowed = False
                rationale = "Proposed recovery plan strategy is classified as FORBIDDEN by policy."
                plan_id = proposed_plan.plan_id
                esc_id = f"esc-policy-{decision_id[:8]}"

            elif proposed_plan.safety == RemediationSafety.HIGH_RISK_WITHOUT_APPROVAL and not operator_override:
                rec_action = "ESCALATE"
                allowed = False
                rationale = "Proposed recovery action entails high operational risk and requires human operator authorization."
                plan_id = proposed_plan.plan_id
                esc_id = f"esc-auth-{decision_id[:8]}"

            else:
                rec_action = "RECOVER"
                allowed = True
                rationale = f"Authorized autonomous recovery plan ready: {proposed_plan.strategy.value}."
                plan_id = proposed_plan.plan_id
                esc_id = None

        else:
            rec_action = "ESCALATE"
            allowed = False
            rationale = "Active incidents present without a formulated autonomous recovery plan."
            plan_id = None
            esc_id = f"esc-unplanned-{decision_id[:8]}"

        dec = ProductionDecision(
            decision_id=decision_id,
            service_id=self.service_id,
            current_state=current_state,
            recommended_action=rec_action,
            active_incidents=[i.incident_id for i in active_incidents],
            autonomous_remediation_allowed=allowed,
            remediation_plan_id=plan_id,
            escalation_ticket_id=esc_id,
            rationale=rationale,
            timestamp=time.time(),
        )
        self._decisions.append(dec)
        return dec

    def get_decisions(self) -> List[ProductionDecision]:
        return list(self._decisions)
