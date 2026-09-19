"""
Phase 72 — Preventive Governance and Autonomous Execution Gates
Enforces strict gating: HIGH_RISK, UNKNOWN, or INSUFFICIENT_EVIDENCE actions are never executed autonomously.
Guarantees PREDICTION != DECISION != EXECUTION != RECOVERY.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from .models import (
    GovernanceDecision,
    PreventiveAction,
    PreventiveActionStatus,
    PreventiveActionType,
    PreventivePlan,
    RiskLevel,
)


class UnauthorizedPreventiveExecutionError(RuntimeError):
    """Raised when an action violates the autonomous remediation safety policy."""
    pass


class PreventiveGovernanceGate:
    """Governance gate that authorizes or blocks autonomous preventive actions."""

    def __init__(self, autonomous_execution_enabled: bool = True):
        self.autonomous_enabled = autonomous_execution_enabled

    def can_execute_autonomously(
        self,
        action: PreventiveAction,
        plan: PreventivePlan,
    ) -> tuple[bool, str]:
        # Invariant 1: If autonomous execution is globally disabled, block
        if not self.autonomous_enabled:
            return False, "Autonomous remediation globally disabled."

        # Invariant 2: High Risk actions REQUIRE human / governance approval
        if action.risk_level == RiskLevel.HIGH:
            return False, f"Action '{action.action_type.value}' is HIGH_RISK and requires explicit approval."

        # Invariant 3: Unknown risk actions can NEVER be executed automatically
        if action.risk_level in (RiskLevel.UNKNOWN, RiskLevel.INSUFFICIENT_EVIDENCE):
            return False, f"Action '{action.action_type.value}' has UNKNOWN risk level; autonomous execution blocked."

        # Invariant 4: Destructive or rollback actions require explicit authorization
        if action.action_type in (
            PreventiveActionType.ROLLBACK_BEFORE_FAILURE,
            PreventiveActionType.INFRASTRUCTURE_REQUIRED,
        ):
            return False, f"Action '{action.action_type.value}' requires infrastructure or human intervention."

        return True, "Authorized for autonomous preventive execution."

    def gate_plan(
        self,
        plan: PreventivePlan,
        has_human_approval: bool = False,
    ) -> GovernanceDecision:
        if not plan.actions:
            plan.governance_decision = GovernanceDecision.APPROVED
            return GovernanceDecision.APPROVED

        # Check if any action requires human review
        requires_approval = False
        for act in plan.actions:
            can_run, reason = self.can_execute_autonomously(act, plan)
            if not can_run:
                act.status = PreventiveActionStatus.GATED
                requires_approval = True
            else:
                act.status = PreventiveActionStatus.APPROVED

        if requires_approval:
            if has_human_approval:
                for act in plan.actions:
                    act.status = PreventiveActionStatus.APPROVED
                plan.governance_decision = GovernanceDecision.APPROVED
                return GovernanceDecision.APPROVED
            else:
                plan.governance_decision = GovernanceDecision.BLOCKED
                return GovernanceDecision.BLOCKED

        plan.governance_decision = GovernanceDecision.APPROVED
        return GovernanceDecision.APPROVED

    def execute_action(
        self,
        action: PreventiveAction,
        plan: PreventivePlan,
        handler: Optional[Callable[[], bool]] = None,
        force_approved: bool = False,
    ) -> PreventiveActionStatus:
        if not force_approved:
            can_run, reason = self.can_execute_autonomously(action, plan)
            if not can_run:
                action.status = PreventiveActionStatus.REJECTED
                raise UnauthorizedPreventiveExecutionError(f"Autonomous execution blocked: {reason}")

        action.status = PreventiveActionStatus.EXECUTED
        action.executed_at = time.time()

        if handler:
            try:
                success = handler()
                if not success:
                    action.status = PreventiveActionStatus.FAILED
            except Exception:
                action.status = PreventiveActionStatus.FAILED

        return action.status
