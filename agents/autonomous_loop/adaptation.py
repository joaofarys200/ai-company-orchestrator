"""
JARVIS OS — Phase 40: Autonomous Engineering Loop & Closed-Loop Mission Adaptation
Adaptation Engine: Proposal Formulation, Gate Validation, and Atomic Application.

Rule:
An adaptation is never executed automatically merely because it was proposed.
It strictly traverses: PROPOSAL -> VALIDATION -> MISSION GATE -> APPLICATION.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import time
from typing import Any, Dict, List, Optional, Tuple

from agents.autonomous_loop.models import (
    AdaptationProposal,
    AdaptationType,
    LoopDecisionType,
)
from agents.autonomous_loop.decision import AutonomousDecisionResult
from agents.autonomous_loop.observation import LoopObservation


class AutonomousAdaptationEngine:
    """
    Formulates AdaptationProposals, routes them through Mission Gate & Sentinel,
    and applies approved mutations atomically.
    """

    @classmethod
    def formulate_proposal(
        cls,
        decision_result: AutonomousDecisionResult,
        observation: LoopObservation,
        previous_plan_version: int,
        details: Optional[dict[str, Any]] = None,
    ) -> AdaptationProposal:
        cycle_id = decision_result.cycle_id
        adapt_id = f"adapt_{cycle_id}_{int(time.time() * 1000) % 100000}"
        decision = decision_result.decision
        details = details or {}

        adapt_type = AdaptationType.MODIFY_TASK
        risk = "LOW"
        requires_approval = False
        proposed_change: dict[str, Any] = {}

        if decision == LoopDecisionType.REPAIR:
            adapt_type = AdaptationType.REPAIR
            risk = "LOW"
            proposed_change = {
                "action": "TRIGGER_AST_REPAIR",
                "failures": observation.active_failures,
                "target_files": observation.files_changed,
            }
        elif decision == LoopDecisionType.REPLAN:
            adapt_type = AdaptationType.REPLAN
            risk = "MEDIUM"
            proposed_change = {
                "action": "COMPUTE_PLAN_DELTA",
                "trigger": "NEW_DEPENDENCY_OR_INVALID_DAG",
                "preserve_completed_tasks": True,
            }
        elif decision == LoopDecisionType.ADAPT:
            adapt_type = AdaptationType.ADD_VALIDATION
            risk = "LOW"
            proposed_change = {
                "action": "INJECT_VALIDATION_TASK",
                "reason": "Reconcile prediction deviation with empirical test suite",
                "priority": "HIGH",
            }
        elif decision == LoopDecisionType.REASSIGN:
            adapt_type = AdaptationType.REASSIGN
            risk = "LOW"
            proposed_change = {
                "action": "REASSIGN_AGENT",
                "failed_agent": details.get("failed_agent", "coder"),
                "target_agent": details.get("target_agent", "swarm_worker_backup"),
            }
        elif decision == LoopDecisionType.REQUEST_HUMAN:
            adapt_type = AdaptationType.REQUEST_HUMAN
            risk = "HIGH"
            requires_approval = True
            proposed_change = {
                "action": "SUSPEND_AND_ESCALATE",
                "escalation_reason": decision_result.causal_explanation.observation,
            }
        else:
            adapt_type = AdaptationType.MODIFY_TASK
            proposed_change = {"action": "CONTINUE_CYCLE"}

        return AdaptationProposal(
            adaptation_id=adapt_id,
            cycle_id=cycle_id,
            adaptation_type=adapt_type,
            reason=decision_result.causal_explanation.observation,
            source_observation=observation.to_dict(),
            previous_plan_version=previous_plan_version,
            proposed_change=proposed_change,
            predicted_impact={"risk": risk, "scope": "LOCAL" if risk == "LOW" else "CROSS_MODULE"},
            risk=risk,
            requires_approval=requires_approval,
            status="PROPOSED",
        )

    @classmethod
    def evaluate_gate(
        cls,
        proposal: AdaptationProposal,
        sentinel_blocked: bool = False,
        economic_blocked: bool = False,
        human_approved: bool = False,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Validates adaptation proposal through Mission Gate & Security Sentinel.
        Returns: (is_approved, gate_result_dict)
        """
        if sentinel_blocked:
            gate_res = {
                "status": "REJECTED_SECURITY",
                "passed": False,
                "reason": "Security Sentinel rejected adaptation: disallowed permission or unsafe operation.",
                "evaluated_at": time.time(),
            }
            proposal.status = "REJECTED"
            proposal.gate_result = gate_res
            return False, gate_res

        if economic_blocked and not human_approved:
            gate_res = {
                "status": "REQUIRES_APPROVAL_ECONOMIC",
                "passed": False,
                "reason": "Economic invariant gate requires explicit operator authorization.",
                "evaluated_at": time.time(),
            }
            proposal.status = "PENDING_APPROVAL"
            proposal.gate_result = gate_res
            return False, gate_res

        if proposal.requires_approval and not human_approved:
            gate_res = {
                "status": "REQUIRES_APPROVAL",
                "passed": False,
                "reason": "High-risk adaptation requires operator confirmation.",
                "evaluated_at": time.time(),
            }
            proposal.status = "PENDING_APPROVAL"
            proposal.gate_result = gate_res
            return False, gate_res

        gate_res = {
            "status": "APPROVED",
            "passed": True,
            "reason": "Mission Gate authorized adaptation.",
            "evaluated_at": time.time(),
        }
        proposal.status = "APPROVED"
        proposal.gate_result = gate_res
        return True, gate_res

    @classmethod
    def apply_proposal(
        cls,
        proposal: AdaptationProposal,
        tasks_list: list[dict[str, Any]],
        current_plan_version: int,
    ) -> tuple[bool, int, list[dict[str, Any]]]:
        """
        Applies approved adaptation mutation to tasks list and increments plan_version.
        Returns: (success, new_plan_version, updated_tasks)
        """
        if proposal.status != "APPROVED":
            return False, current_plan_version, tasks_list

        new_version = current_plan_version + 1
        updated = [dict(t) for t in tasks_list]

        if proposal.adaptation_type == AdaptationType.ADD_VALIDATION:
            updated.append({
                "id": f"task_val_{proposal.adaptation_id[-6:]}",
                "title": f"Validação Empírica pós-Adaptação ({proposal.adaptation_id[-6:]})",
                "agent": "test_engineer",
                "priority": "HIGH",
                "status": "PENDING",
            })
        elif proposal.adaptation_type == AdaptationType.REASSIGN:
            target_ag = proposal.proposed_change.get("target_agent", "swarm_worker_backup")
            for t in updated:
                if t.get("status") in ("PENDING", "RUNNING"):
                    t["agent"] = target_ag

        proposal.status = "APPLIED"
        proposal.applied_at = time.time()
        return True, new_version, updated
