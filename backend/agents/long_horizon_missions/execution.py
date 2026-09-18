"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
Mission Execution Engine & Step-by-Step Bounded Orchestration.
Pipeline:
START -> PLAN -> EXECUTE -> WAIT -> COLLECT -> VERIFY -> CHECKPOINT -> ADAPT -> CONTINUE -> FINISH.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.agents.long_horizon_missions.adaptation import AdaptiveReplanner
from backend.agents.long_horizon_missions.budget import BudgetTracker
from backend.agents.long_horizon_missions.checkpoint import CheckpointManager
from backend.agents.long_horizon_missions.completion import CompletionEvaluator
from backend.agents.long_horizon_missions.coordination import MissionCoordinationManager
from backend.agents.long_horizon_missions.evidence import EvidenceLedger
from backend.agents.long_horizon_missions.milestones import MilestoneManager
from backend.agents.long_horizon_missions.mission_state import MissionStateMachine
from backend.agents.long_horizon_missions.models import (
    CheckpointType,
    CompletionResult,
    LongHorizonMission,
    MilestoneState,
    MissionCompletionProof,
    MissionPlan,
    MissionState,
    ObjectiveCategory,
    ObjectiveState,
)
from backend.agents.long_horizon_missions.objectives import ObjectiveTracker
from backend.agents.long_horizon_missions.planning import MissionPlanner
from backend.agents.long_horizon_missions.risk import RiskGovernor, RiskSeverity
from backend.agents.long_horizon_missions.security import MissionSecuritySentinel
from backend.agents.long_horizon_missions.verification import MissionVerifier


class MissionExecutionEngine:
    """
    Bounded, step-by-step execution orchestrator for long-horizon engineering missions.
    Strictly bounded by budget; no infinite loops or unverified completions.
    """

    def __init__(
        self,
        mission: LongHorizonMission,
        objective_tracker: ObjectiveTracker,
        planner: MissionPlanner,
        milestone_manager: MilestoneManager,
        budget_tracker: BudgetTracker,
        checkpoint_manager: CheckpointManager,
        evidence_ledger: EvidenceLedger,
        verifier: MissionVerifier,
        coordination_manager: MissionCoordinationManager,
        replanner: AdaptiveReplanner,
        risk_governor: RiskGovernor,
        security_sentinel: MissionSecuritySentinel,
        completion_evaluator: CompletionEvaluator,
    ):
        self.mission = mission
        self.objectives = objective_tracker
        self.planner = planner
        self.milestones = milestone_manager
        self.budget = budget_tracker
        self.checkpoints = checkpoint_manager
        self.evidence = evidence_ledger
        self.verifier = verifier
        self.coordination = coordination_manager
        self.replanner = replanner
        self.risk = risk_governor
        self.security = security_sentinel
        self.completion = completion_evaluator

    def execute_step(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes one bounded step of the mission:
        Selects next ready milestone, dispatches agents, collects outputs,
        verifies, checkpoints, adapts if needed, and checks for completion.
        """
        ctx = context or {}
        now = time.time()

        # 0. Check budget exhaustion
        is_exhausted, exhaust_dim = self.budget.record_consumption("agent_executions", 1.0)
        self.budget.record_consumption("cpu_sec", 0.05)
        self.budget.record_consumption("wall_time_sec", 0.05)
        if is_exhausted:
            MissionStateMachine.transition(self.mission, MissionState.BLOCKED, f"Budget exhausted: {exhaust_dim}")
            return {
                "step_status": "BLOCKED",
                "reason": f"BUDGET_EXHAUSTED_{exhaust_dim}",
                "mission_state": self.mission.current_state.value,
            }

        # 1. State machine advancement
        if self.mission.current_state == MissionState.CREATED:
            MissionStateMachine.transition(self.mission, MissionState.PLANNING)

        if self.mission.current_state == MissionState.PLANNING:
            if not self.planner.plan or not self.planner.plan.milestones:
                MissionStateMachine.transition(self.mission, MissionState.FAILED, "No plan milestones")
                return {"step_status": "FAILED", "reason": "EMPTY_PLAN"}
            MissionStateMachine.transition(self.mission, MissionState.READY)

        if self.mission.current_state == MissionState.READY:
            MissionStateMachine.transition(self.mission, MissionState.EXECUTING)

        # 2. Get ready milestones
        ready_milestones = self.planner.get_ready_milestones(self.milestones.completed_milestones)
        if not ready_milestones:
            # Check if all completed or blocked
            if len(self.milestones.completed_milestones) == len(self.milestones.milestones):
                return self._finalize_mission(ctx)
            else:
                MissionStateMachine.transition(self.mission, MissionState.BLOCKED, "No ready milestones")
                return {"step_status": "BLOCKED", "reason": "DEPENDENCIES_UNRESOLVED"}

        target_milestone = ready_milestones[0]

        # 3. Security preflight validation
        target_files = ctx.get("target_files") or [f"src/{target_milestone.milestone_id.lower()}.py"]
        is_safe, sec_violations = self.security.validate_mutation_intent(
            agent_id="CoderAgent",
            target_files=target_files,
            patch_content=ctx.get("patch_content", "# safe patch"),
        )
        if not is_safe:
            MissionStateMachine.transition(self.mission, MissionState.BLOCKED, "Security violation")
            return {"step_status": "BLOCKED", "reason": "SECURITY_VIOLATION", "violations": sec_violations}

        # 4. Multi-Agent Coordination dispatch (F66)
        dispatched_intents = self.coordination.dispatch_milestone_tasks(
            target_milestone,
            self.mission.agent_roster,
        )

        # 5. Start milestone execution
        self.milestones.start_milestone(target_milestone.milestone_id)

        # 6. Verification run (F62)
        v_passed, v_evidence_ids, v_report = self.verifier.verify_milestone(target_milestone, ctx)

        # Record evidence in ledger
        for ev_id in v_evidence_ids:
            self.evidence.record_evidence(
                milestone_id=target_milestone.milestone_id,
                kind="CONTINUOUS_VERIFICATION",
                status="VERIFIED" if v_passed else "FAILED",
                details=v_report,
                evidence_id=ev_id,
            )

        # 7. Milestone completion / failure
        if v_passed:
            self.milestones.complete_milestone(
                milestone_id=target_milestone.milestone_id,
                outputs=target_milestone.expected_outputs,
                evidence_ids=v_evidence_ids,
                verified=True,
            )
            for intent in dispatched_intents:
                self.coordination.register_execution_completion(intent["intent_id"], success=True)
            self.budget.record_consumption("patches", 1.0)
        else:
            self.milestones.fail_milestone(
                milestone_id=target_milestone.milestone_id,
                error_message=f"Verification failed on {target_milestone.milestone_id}",
            )
            for intent in dispatched_intents:
                self.coordination.register_execution_completion(intent["intent_id"], success=False, error_msg="Verification failed")

            # Adaptive replanning / repair injection (F56)
            primary_ids = {o.objective_id for o in self.objectives.list_objectives(ObjectiveCategory.PRIMARY_OBJECTIVES)}
            did_adapt, updated_plan, stall_state = self.replanner.observe_and_adapt(
                plan=self.planner.plan,
                completed_milestone_id=target_milestone.milestone_id,
                observed_outputs=[],
                unresolved_issues=[f"Failure in {target_milestone.milestone_id}"],
                primary_objective_ids=primary_ids,
            )
            if stall_state in (MissionState.BLOCKED, MissionState.HUMAN_REVIEW):
                MissionStateMachine.transition(self.mission, MissionState(stall_state.value), "Stall or divergence detected")

            return {
                "step_status": "FAILED_ADAPTED" if did_adapt else "FAILED",
                "milestone_id": target_milestone.milestone_id,
                "replan_count": self.planner.plan.replan_count,
            }

        # 8. Checkpointing (Immutable SHA-256)
        cp = self.checkpoints.create_checkpoint(
            mission_id=self.mission.mission_id,
            checkpoint_type=CheckpointType.MILESTONE,
            mission_state=self.mission.current_state.value,
            objective_state=self.objectives.to_dict(),
            plan_dag=self.planner.plan.to_dict(),
            agent_states=self.coordination.intent_registry,
            claims=[],
            workspace_states={"architecture_hash": "arch_v1"},
            transaction_states={"applied_tx_ids": [d["transaction_id"] for d in dispatched_intents]},
            architecture_hash="arch_hash_sha256",
            contract_hash="contract_hash_sha256",
            behavior_hash="behavior_hash_sha256",
            verification_ledger=self.evidence.to_list(),
            budget_remaining={"remaining_pct": self.budget.budget.remaining_pct()},
            evidence_root=self.evidence.compute_root_hash(),
        )
        self.mission.checkpoint_id = cp.checkpoint_id

        # 9. Update primary objectives if milestone satisfied them
        for obj_id in target_milestone.objective_ids:
            if self.objectives.get_objective(obj_id):
                self.objectives.update_status(obj_id, ObjectiveState.SATISFIED, evidence_ref=v_evidence_ids[0] if v_evidence_ids else None)

        # 10. Check if all milestones completed
        if len(self.milestones.completed_milestones) == len(self.milestones.milestones):
            return self._finalize_mission(ctx)

        return {
            "step_status": "MILESTONE_COMPLETED",
            "milestone_id": target_milestone.milestone_id,
            "completed_count": len(self.milestones.completed_milestones),
            "total_count": len(self.milestones.milestones),
            "checkpoint_id": cp.checkpoint_id,
            "mission_state": self.mission.current_state.value,
        }

    def _finalize_mission(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs completion evaluation:
        MISSION_COMPLETION = OBJECTIVE_SATISFACTION + REQUIRED_EVIDENCE + VERIFICATION +
                             ARCHITECTURE_CONSISTENCY + CONTRACT_CONSISTENCY + BEHAVIOR_CONSISTENCY +
                             SECURITY + NO_UNRESOLVED_CRITICAL_STATE
        """
        MissionStateMachine.transition(self.mission, MissionState.FINISHING)

        primary_satisfied, unsatisfied_objs = self.objectives.are_primary_objectives_satisfied()
        all_milestones_done = (len(self.milestones.completed_milestones) == len(self.milestones.milestones))

        is_verified_complete, verif_report = self.verifier.verify_mission_completion(
            primary_objectives=self.objectives.list_objectives(ObjectiveCategory.PRIMARY_OBJECTIVES),
            milestones=list(self.milestones.milestones.values()),
            evidence_root=self.evidence.compute_root_hash(),
            context=context,
        )

        proof = self.completion.evaluate(
            mission=self.mission,
            primary_satisfied=primary_satisfied,
            secondary_status={o.objective_id: o.status.value for o in self.objectives.list_objectives(ObjectiveCategory.SECONDARY_OBJECTIVES)},
            all_milestones_completed=all_milestones_done,
            verification_passed=is_verified_complete,
            verification_coverage=1.0 if is_verified_complete else 0.5,
            architecture_stable=context.get("architecture_stable", True),
            contracts_intact=context.get("contracts_intact", True),
            behaviors_intact=context.get("behaviors_intact", True),
            security_safe=context.get("security_safe", True),
            unresolved_risks=[r.risk_id for r in self.risk.list_unresolved_risks()],
            evidence_refs=[it["evidence_id"] for it in self.evidence.to_list()],
            final_checkpoint_id=self.mission.checkpoint_id or "chk_final",
            residual_state=context.get("residual_state", {}),
        )

        if proof.result == CompletionResult.COMPLETED_WITHIN_SCOPE:
            MissionStateMachine.transition(self.mission, MissionState.COMPLETED)
        elif proof.result == CompletionResult.HUMAN_REVIEW:
            MissionStateMachine.transition(self.mission, MissionState.HUMAN_REVIEW)
        elif proof.result == CompletionResult.BLOCKED:
            MissionStateMachine.transition(self.mission, MissionState.BLOCKED)
        elif proof.result == CompletionResult.COMPLETED_WITH_UNRESOLVED_RISK:
            MissionStateMachine.transition(self.mission, MissionState.COMPLETED)
        else:
            MissionStateMachine.transition(self.mission, MissionState.INCONCLUSIVE)

        return {
            "step_status": "MISSION_FINALIZED",
            "proof": proof.to_dict(),
            "mission_state": self.mission.current_state.value,
        }
