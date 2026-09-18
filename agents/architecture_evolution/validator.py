"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Module: validator.py
System integrity validator enforcing architectural invariants and regression constraints.
"""

from __future__ import annotations

from typing import List, Tuple

from .models import (
    ArchitectureAlternative,
    ArchitectureGovernanceDecision,
    ArchitectureMigrationPlan,
    ArchitectureProblem,
    ArchitectureSnapshot,
    GovernanceDecisionState,
    ReversibilityStatus,
)


class ArchitectureValidator:
    """Validates structural correctness and invariant preservation."""

    def validate_snapshot(self, snapshot: ArchitectureSnapshot) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        if not snapshot.snapshot_id:
            errors.append("Snapshot must have a non-empty snapshot_id.")
        computed = snapshot.compute_hash()
        if snapshot.snapshot_hash and snapshot.snapshot_hash != computed:
            errors.append(f"Snapshot hash mismatch: declared '{snapshot.snapshot_hash}' != computed '{computed}'.")
        return len(errors) == 0, errors

    def validate_problem(self, problem: ArchitectureProblem) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        if not problem.problem_id:
            errors.append("Problem must have a valid problem_id.")
        if not problem.affected_nodes:
            errors.append("Problem must identify at least one affected node.")
        if not problem.evidence:
            errors.append("Problem must contain supporting evidence.")
        if problem.confidence < 0.0 or problem.confidence > 1.0:
            errors.append("Confidence must be bounded between 0.0 and 1.0.")
        return len(errors) == 0, errors

    def validate_migration_plan(self, plan: ArchitectureMigrationPlan) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        seen = set()
        for step in plan.steps:
            for dep in step.dependencies:
                if dep not in seen:
                    errors.append(f"Step '{step.step_id}' references prerequisite '{dep}' that appears later or is missing.")
            seen.add(step.step_id)

            if not step.rollback_action:
                errors.append(f"Step '{step.step_id}' must declare an executable rollback action.")

        return len(errors) == 0, errors

    def validate_governance_decision(
        self,
        decision: ArchitectureGovernanceDecision,
        alternative: ArchitectureAlternative,
    ) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        # Invariant: Irreversible alternatives cannot be APPROVED without HUMAN_REVIEW
        if alternative.reversibility == ReversibilityStatus.IRREVERSIBLE:
            if decision.state == GovernanceDecisionState.APPROVED_FOR_IMPLEMENTATION:
                errors.append("Invariant violation: IRREVERSIBLE alternative cannot be APPROVED_FOR_IMPLEMENTATION autonomously.")

        # Invariant: Failed sentinel cannot be APPROVED
        if not decision.sentinel_passed:
            if decision.state == GovernanceDecisionState.APPROVED_FOR_IMPLEMENTATION:
                errors.append("Invariant violation: Sentinel failure must never result in APPROVED_FOR_IMPLEMENTATION.")

        return len(errors) == 0, errors
