"""
JARVIS OS — Phase 69: Autonomous Quality Debt Remediation
Governance engine. Enforces quality budgets, gates compliance, and authorizes remediation missions.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .debt import IngestedDebtItem
from .models import DebtRemediationOption, RemediationPlan, RemediationPriorityVector


class GovernanceDecision(str, Enum):
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"
    DEFERRED = "DEFERRED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


@dataclass
class GovernanceReport:
    decision_id: str
    debt_id: str
    decision: GovernanceDecision
    authorized: bool
    budget_allocated: Dict[str, Any]
    block_reasons: List[str] = field(default_factory=list)
    compliance_checks: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "debt_id": self.debt_id,
            "decision": self.decision.value if isinstance(self.decision, GovernanceDecision) else str(self.decision),
            "authorized": self.authorized,
            "budget_allocated": self.budget_allocated,
            "block_reasons": self.block_reasons,
            "compliance_checks": self.compliance_checks,
        }


class RemediationGovernanceEngine:
    """
    Enforces quality budget gates and compliance rules before remediation execution begins.
    """

    def __init__(self, max_autonomous_cost: float = 8.0, max_autonomous_risk: float = 0.50):
        self.max_autonomous_cost = max_autonomous_cost
        self.max_autonomous_risk = max_autonomous_risk

    def evaluate_gate(
        self,
        debt_item: IngestedDebtItem,
        chosen_option: DebtRemediationOption,
        human_approval_granted: bool = False,
        quality_budget_exhausted: bool = False,
    ) -> GovernanceReport:
        decision_id = f"gov_{uuid.uuid4().hex[:8]}"
        block_reasons = []

        checks = {
            "budget_available": not quality_budget_exhausted,
            "cost_within_limit": chosen_option.estimated_cost <= self.max_autonomous_cost,
            "risk_within_limit": chosen_option.risk <= self.max_autonomous_risk,
            "security_hard_block": not ("CRITICAL_SECURITY" in debt_item.category and not human_approval_granted),
            "contract_approved": not (bool(chosen_option.affected_contracts) and not human_approval_granted),
        }

        if quality_budget_exhausted:
            block_reasons.append("Quality budget for current epoch is exhausted.")
        if chosen_option.estimated_cost > self.max_autonomous_cost and not human_approval_granted:
            block_reasons.append(f"Estimated cost ({chosen_option.estimated_cost}) exceeds autonomous threshold ({self.max_autonomous_cost}).")
        if chosen_option.risk > self.max_autonomous_risk and not human_approval_granted:
            block_reasons.append(f"Remediation risk ({chosen_option.risk:.2f}) exceeds autonomous threshold ({self.max_autonomous_risk:.2f}).")
        if "CRITICAL_SECURITY" in debt_item.category and not human_approval_granted:
            block_reasons.append("Critical security debt remediation requires explicit human authorization.")
        if bool(chosen_option.affected_contracts) and not human_approval_granted:
            block_reasons.append("Remediation touches public contracts without explicit governance approval.")

        if block_reasons:
            if any("requires explicit human authorization" in r or "public contracts" in r for r in block_reasons):
                decision = GovernanceDecision.HUMAN_REVIEW_REQUIRED
            elif quality_budget_exhausted:
                decision = GovernanceDecision.DEFERRED
            else:
                decision = GovernanceDecision.BLOCKED
            authorized = False
            budget = {}
        else:
            decision = GovernanceDecision.APPROVED
            authorized = True
            budget = {
                "max_cost": chosen_option.estimated_cost,
                "max_files": max(1, len(chosen_option.affected_files)),
                "max_retries": 1,
            }

        return GovernanceReport(
            decision_id=decision_id,
            debt_id=debt_item.debt_id,
            decision=decision,
            authorized=authorized,
            budget_allocated=budget,
            block_reasons=block_reasons,
            compliance_checks=checks,
        )
