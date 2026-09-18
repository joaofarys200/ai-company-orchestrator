"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Module: governance.py
Enforces the mandatory Architecture Governance Gate.

Invariants:
    PROPOSAL != APPROVAL
    APPROVAL != IMPLEMENTATION
    External knowledge (F63) requires local validation.
    Irreversible or high-risk transformations require HUMAN_REVIEW.
    Sentinel violations result in instant BLOCKED status.
"""

from __future__ import annotations

import hashlib
import time
from typing import List, Optional

from .models import (
    AlternativeType,
    ArchitectureAlternative,
    ArchitectureGovernanceDecision,
    ArchitectureProblem,
    ContractBreakStatus,
    GovernanceDecisionState,
    ReversibilityStatus,
    RiskCriticality,
    SimulationStatus,
)


class ArchitectureGovernanceEngine:
    """Enforces strict governance gates on proposed architectural changes."""

    def evaluate_governance(
        self,
        problem: ArchitectureProblem,
        alternative: Optional[ArchitectureAlternative],
        simulation_status: SimulationStatus = SimulationStatus.SIMULATION_SAFE,
        risk_criticality: RiskCriticality = RiskCriticality.LOW,
        contract_status: ContractBreakStatus = ContractBreakStatus.NON_BREAKING,
        sentinel_passed: bool = True,
        policy_mode: str = "STANDARD",
    ) -> ArchitectureGovernanceDecision:
        decision_id = f"gov_{hashlib.sha256(f'{problem.problem_id}:{time.time()}'.encode()).hexdigest()[:8]}"
        conditions: List[str] = []

        # 1. Check Sentinel Violations (Absolute Security Block)
        if not sentinel_passed:
            return ArchitectureGovernanceDecision(
                decision_id=decision_id,
                problem_id=problem.problem_id,
                alternative_id=alternative.alternative_id if alternative else None,
                state=GovernanceDecisionState.BLOCKED,
                reason="Sentinel security audit failed: unauthorized privilege elevation or secret exposure attempt.",
                conditions=["Remediate security sentinel violations before re-submitting proposal."],
                sentinel_passed=False,
                provenance_hash=hashlib.sha256(decision_id.encode()).hexdigest(),
            )

        # 2. No alternative provided or baseline keep_current
        if not alternative or alternative.alternative_type == AlternativeType.KEEP_CURRENT:
            return ArchitectureGovernanceDecision(
                decision_id=decision_id,
                problem_id=problem.problem_id,
                alternative_id=alternative.alternative_id if alternative else None,
                state=GovernanceDecisionState.OBSERVATION_ONLY,
                reason="Architectural observation logged. Baseline retained with zero active refactoring.",
                conditions=["Monitor coupling and regression metrics during regular operations."],
                sentinel_passed=True,
                provenance_hash=hashlib.sha256(decision_id.encode()).hexdigest(),
            )

        # 3. Simulation failures
        if simulation_status == SimulationStatus.SIMULATION_INCOMPLETE:
            return ArchitectureGovernanceDecision(
                decision_id=decision_id,
                problem_id=problem.problem_id,
                alternative_id=alternative.alternative_id,
                state=GovernanceDecisionState.REJECTED,
                reason="Pre-execution architectural simulation failed or proved incomplete.",
                conditions=["Refactor migration plan DAG and ensure 100% rollback coverage."],
                sentinel_passed=True,
                provenance_hash=hashlib.sha256(decision_id.encode()).hexdigest(),
            )

        # 4. Irreversible changes or Critical Risk -> Mandatory HUMAN_REVIEW
        if alternative.reversibility == ReversibilityStatus.IRREVERSIBLE or risk_criticality == RiskCriticality.CRITICAL:
            conditions.append("Human architect sign-off required for irreversible transformation.")
            conditions.append("Multi-party security authorization required.")
            return ArchitectureGovernanceDecision(
                decision_id=decision_id,
                problem_id=problem.problem_id,
                alternative_id=alternative.alternative_id,
                state=GovernanceDecisionState.HUMAN_REVIEW,
                reason="High-risk or irreversible transformation exceeds autonomous approval threshold.",
                conditions=conditions,
                sentinel_passed=True,
                provenance_hash=hashlib.sha256(decision_id.encode()).hexdigest(),
            )

        # 5. Breaking contracts -> Requires compatibility verification or human review
        if contract_status == ContractBreakStatus.BREAKING:
            conditions.append("Explicit consumer migration shim must be verified in shadow mode.")
            return ArchitectureGovernanceDecision(
                decision_id=decision_id,
                problem_id=problem.problem_id,
                alternative_id=alternative.alternative_id,
                state=GovernanceDecisionState.VALIDATION_REQUIRED,
                reason="Proposal introduces breaking contract changes; dual-path validation required.",
                conditions=conditions,
                sentinel_passed=True,
                provenance_hash=hashlib.sha256(decision_id.encode()).hexdigest(),
            )

        # 6. F63 Transferred Knowledge -> Requires local validation
        if alternative.is_hypothesis_from_f63:
            conditions.append("Execute newly synthesized local test suite to prove hypothesis validity.")
            conditions.append("Record local evidence before promoting proposal to approved.")
            return ArchitectureGovernanceDecision(
                decision_id=decision_id,
                problem_id=problem.problem_id,
                alternative_id=alternative.alternative_id,
                state=GovernanceDecisionState.VALIDATION_REQUIRED,
                reason="External engineering pattern from Phase 63 requires local empirical validation.",
                conditions=conditions,
                sentinel_passed=True,
                provenance_hash=hashlib.sha256(decision_id.encode()).hexdigest(),
            )

        # 7. Standard Approved / Proposal Ready
        conditions.append("Execute staged migration DAG with automated rollback probes.")
        conditions.append("Continuous verification suite (F62) must remain 100% green.")

        if policy_mode == "STRICT":
            state = GovernanceDecisionState.PROPOSAL_READY
        else:
            state = GovernanceDecisionState.APPROVED_FOR_IMPLEMENTATION

        return ArchitectureGovernanceDecision(
            decision_id=decision_id,
            problem_id=problem.problem_id,
            alternative_id=alternative.alternative_id,
            state=state,
            reason="Proposal verified in simulation with safe reversibility, zero contract breaks, and Sentinel approval.",
            conditions=conditions,
            sentinel_passed=True,
            provenance_hash=hashlib.sha256(decision_id.encode()).hexdigest(),
        )
