"""
JARVIS OS — Phase 73: Autonomous Macro-Refactoring Engine
Module: governance.py
Budget tracking, security boundary enforcement, human-in-the-loop review gating,
and release-readiness boundary separation.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    BudgetExceededError,
    MacroMigration,
    MigrationState,
    MigrationStep,
)


class MacroRefactoringGovernance:
    """
    Enforces architectural governance gates, execution budgets, security boundaries,
    and release-readiness decoupling.
    """

    def __init__(
        self,
        default_step_cost: float = 10.0,
        high_risk_threshold: float = 0.7,
    ):
        self.default_step_cost = default_step_cost
        self.high_risk_threshold = high_risk_threshold

    def check_and_consume_budget(
        self,
        migration: MacroMigration,
        step: MigrationStep,
        custom_cost: Optional[float] = None,
    ) -> float:
        """
        Calculates and records execution cost.
        Raises BudgetExceededError if consumed budget exceeds authorized budget.
        """
        cost = custom_cost if custom_cost is not None else self.default_step_cost

        if migration.consumed_budget + cost > migration.execution_cost_budget:
            migration.status = MigrationState.BLOCKED
            err = (
                f"Execution budget exceeded! Consumed: {migration.consumed_budget:.1f}, "
                f"Requested: {cost:.1f}, Budget: {migration.execution_cost_budget:.1f}"
            )
            migration.unresolved_blockers.append(err)
            raise BudgetExceededError(err)

        migration.consumed_budget += cost
        return migration.consumed_budget

    def evaluate_security_gate(
        self,
        migration: MacroMigration,
        step: Optional[MigrationStep] = None,
        human_approval_token: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Enforces human review on high-risk, security-sensitive, or protected migrations.
        If approval is missing, transitions migration to HUMAN_REVIEW_REQUIRED.
        """
        is_security_step = False
        if step:
            is_security_step = any(
                "auth" in f.lower() or "secret" in f.lower() or "security" in f.lower()
                for f in step.affected_files
            )

        requires_review = (
            migration.risk_score >= self.high_risk_threshold
            or migration.metadata.get("is_security_sensitive", False)
            or is_security_step
        )

        if requires_review:
            if not human_approval_token:
                migration.status = MigrationState.HUMAN_REVIEW_REQUIRED
                msg = (
                    f"Migration '{migration.migration_id}' requires explicit human approval. "
                    f"Risk score: {migration.risk_score:.2f} >= {self.high_risk_threshold}. "
                    f"Stop at approval boundary."
                )
                if msg not in migration.unresolved_blockers:
                    migration.unresolved_blockers.append(msg)
                return False, msg
            else:
                migration.unresolved_blockers = [
                    b for b in migration.unresolved_blockers if "explicit human approval" not in b
                ]

        return True, "Security gate passed or authorized by human approval."

    def evaluate_release_boundary(
        self,
        migration: MacroMigration,
    ) -> Tuple[bool, str]:
        """
        Enforces the invariant: MIGRATION_COMPLETED != RELEASE_READY.
        A macro-refactoring engine can complete code transformations, but
        CANNOT automatically authorize production release or deployment.
        """
        if migration.status != MigrationState.COMPLETED and migration.status != MigrationState.COMPLETED_WITH_ACCEPTED_RISK:
            return False, f"Migration not completed (status: {migration.status}). Cannot assess release."

        # Explicitly declare that migration completion does NOT imply release promotion
        msg = (
            f"Migration '{migration.migration_id}' is structurally COMPLETED. "
            f"Release readiness and deployment must be independently authorized by Phase 70 Release Gate."
        )
        return True, msg
