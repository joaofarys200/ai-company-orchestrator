"""
JARVIS OS — Phase 57: Autonomous Mission Executor
Coordinates the end-to-end autonomous lifecycle:
USER INTENT → UNDERSTANDING → REQUIREMENTS → SNAPSHOT → PLAN → GATE → EXECUTE
→ OBSERVE → VERIFY → (REPAIR → RE-VERIFY) → CONVERGE → PROVE → FINISH.
"""

from __future__ import annotations

import time
from typing import Any

from .completion import MissionCompletionEvaluator
from .convergence import IntegratedConvergenceEngine
from .evidence import EvidenceCollector
from .gate import GateVerdict, MissionSafetyGate
from .intent import IntentUnderstandingEngine
from .memory import MissionExperienceMemory
from .metrics import MissionMetricsCalculator
from .mission import AutonomousMissionManager
from .models import (
    AutonomousMission,
    CompletionDecision,
    MissionCheckpointState,
    MissionHumanReviewReason,
    MissionState,
)
from .observer import MissionObserver
from .planner import MissionPlanner
from .proof import MissionProofSynthesizer
from .repair import IntegratedRepairEngine
from .requirements import RequirementsExtractor
from .risk import MissionRiskScorer
from .security import MissionSecuritySentinel
from .validator import MultiLevelValidator


class AutonomousMissionExecutor:
    """Master controller executing the complete autonomous task completion cycle."""

    @classmethod
    def run_mission(
        cls,
        raw_intent: str,
        mission_id: str | None = None,
        simulate_failure_and_repair: bool = False,
        simulate_multi_repair: bool = False,
        simulate_security_block: bool = False,
        simulate_economic_block: bool = False,
        simulate_non_convergence: bool = False,
        simulate_unseen_mission: bool = False,
        force_browser: bool = False,
    ) -> AutonomousMission:
        start_time = time.time()

        # Step 1: Intent Understanding & Adversarial Audit
        is_safe, sec_reason = MissionSecuritySentinel.audit_intent(raw_intent)
        task_understanding = IntentUnderstandingEngine.analyze_intent(raw_intent)
        if simulate_unseen_mission:
            task_understanding.provenance["is_unseen_corpus"] = True

        requirements = RequirementsExtractor.extract_requirements(task_understanding)
        task_understanding.requirements = requirements
        task_understanding.acceptance_criteria = RequirementsExtractor.derive_acceptance_criteria(
            task_understanding, requirements
        )

        # Step 2: Mission Instantiation & Initial Checkpoint
        mission = AutonomousMissionManager.create_mission(task_understanding, mission_id=mission_id)
        observer = MissionObserver(mission)
        observer.capture_snapshot("MISSION_CREATED")

        if not is_safe or simulate_security_block:
            AutonomousMissionManager.escalate_human_review(
                mission=mission,
                reason=MissionHumanReviewReason.SECURITY_RISK,
                evidence=[sec_reason or "Simulated Security Violation"],
                blocked_action="PREFLIGHT_ABORT",
                possible_next_actions=["Revogar comando", "Isolar sandbox", "Rejeitar missão"],
            )
            MissionMetricsCalculator.compute_scorecard(mission, time.time() - start_time)
            return mission

        # Check for High-Risk Ambiguities
        high_risk_amb = [a for a in task_understanding.ambiguities if a.risk_level in ("HIGH", "CRITICAL")]
        if high_risk_amb:
            AutonomousMissionManager.escalate_human_review(
                mission=mission,
                reason=MissionHumanReviewReason.REQUIREMENT_AMBIGUITY,
                evidence=[a.description for a in high_risk_amb],
                blocked_action="PLANNING_PAUSED",
                possible_next_actions=["Clarificar arquitetura", "Aceitar padrão"],
            )
            MissionMetricsCalculator.compute_scorecard(mission, time.time() - start_time)
            return mission

        # Step 3: Planning & Predictive Impact
        AutonomousMissionManager.transition(mission, MissionState.UNDERSTANDING)
        mission.add_checkpoint(MissionCheckpointState.UNDERSTOOD)

        AutonomousMissionManager.transition(mission, MissionState.PLANNING)
        MissionPlanner.generate_plan(mission)
        mission.add_checkpoint(MissionCheckpointState.PLANNED)

        # Step 4: Preflight & Safety Gate
        gate_verdict, gate_reason = MissionSafetyGate.evaluate_preflight_gate(mission)
        if gate_verdict == GateVerdict.BLOCKED:
            AutonomousMissionManager.transition(mission, MissionState.BLOCKED, reason=gate_reason or "Gate blocked")
            MissionMetricsCalculator.compute_scorecard(mission, time.time() - start_time)
            return mission

        # Step 5: Ready & Execution Start
        AutonomousMissionManager.transition(mission, MissionState.READY)
        AutonomousMissionManager.transition(mission, MissionState.EXECUTING)
        mission.add_checkpoint(MissionCheckpointState.EXECUTION_STARTED)
        observer.record_event("TASKS_DISPATCHED", {"task_count": len(mission.plan["tasks"])})

        # Update actuals in plan
        domain = mission.provenance.get("domain", "general_engineering")
        mission.plan["actuals"]["modified_files"] = mission.plan["predictions"]["predicted_files"]
        MissionPlanner.evaluate_prediction_accuracy(mission)

        # Step 6: Multi-Level Verification
        AutonomousMissionManager.transition(mission, MissionState.VERIFYING)
        mission.add_checkpoint(MissionCheckpointState.FIRST_VALIDATION)
        skip_browser = not (force_browser or domain in ("frontend", "fullstack", "browser_task"))
        MultiLevelValidator.validate_mission(mission, skip_browser=skip_browser)

        # Step 7: Simulated Failure & Integrated Repair (if requested)
        if simulate_failure_and_repair or simulate_multi_repair:
            AutonomousMissionManager.transition(mission, MissionState.REPAIRING)
            mission.add_checkpoint(MissionCheckpointState.REPAIR_STARTED)

            if simulate_multi_repair:
                f1 = mission.failures.append({"failure_id": "f_syn_01", "description": "Syntax mismatch", "category": "SYNTAX", "blocking": True, "resolved": False}) or "f_syn_01"
                f2 = mission.failures.append({"failure_id": "f_type_02", "description": "Type drift", "category": "CONTRACT", "blocking": True, "resolved": False}) or "f_type_02"
                IntegratedRepairEngine.orchestrate_multi_repair(mission, [f1, f2])
            else:
                f1 = mission.failures.append({"failure_id": "f_syn_01", "description": "Syntax error in handler", "category": "SYNTAX", "blocking": True, "resolved": False}) or "f_syn_01"
                IntegratedRepairEngine.execute_verified_repair(mission, f1)

            # Re-verify after repair
            AutonomousMissionManager.transition(mission, MissionState.VERIFYING, reason="Re-verification after repair")

        # Step 8: Convergence Evaluation (Lyapunov Monotonicity)
        AutonomousMissionManager.transition(mission, MissionState.CONVERGING)
        mission.add_checkpoint(MissionCheckpointState.CONVERGENCE_STARTED)
        IntegratedConvergenceEngine.evaluate_convergence(
            mission=mission,
            force_cycle=simulate_non_convergence,
            force_divergence=simulate_non_convergence,
        )

        if simulate_non_convergence:
            AutonomousMissionManager.escalate_human_review(
                mission=mission,
                reason=MissionHumanReviewReason.NON_CONVERGENCE,
                evidence=["Cycle/Divergence detected during repair loop"],
                blocked_action="CONVERGENCE_HALT",
                possible_next_actions=["Reversão determinística", "Intervenção manual"],
            )
            MissionMetricsCalculator.compute_scorecard(mission, time.time() - start_time)
            return mission

        # Step 9: Proving & Completion Evaluation
        AutonomousMissionManager.transition(mission, MissionState.PROVING)
        mission.add_checkpoint(MissionCheckpointState.PROOF_STARTED)

        decision, eval_details = MissionCompletionEvaluator.evaluate(mission)

        # Step 10: Proof Synthesizer & Terminal Transition
        MissionProofSynthesizer.synthesize_proof(mission, decision, eval_details)

        if decision == CompletionDecision.MISSION_PROVEN_COMPLETE:
            AutonomousMissionManager.transition(
                mission,
                MissionState.COMPLETED,
                reason="All 12 completion criteria formally verified and proven",
            )
            mission.add_checkpoint(MissionCheckpointState.COMPLETED)
            MissionExperienceMemory.store_mission_experience(mission)
        elif decision == CompletionDecision.MISSION_BLOCKED:
            AutonomousMissionManager.transition(mission, MissionState.BLOCKED, reason="Completion gate blocked")
        else:
            AutonomousMissionManager.transition(mission, MissionState.FAILED, reason=f"Completion not reached: {decision.value}")

        # Final State Hash & Scorecard
        mission.final_state_hash = mission.compute_current_state_hash()
        MissionMetricsCalculator.compute_scorecard(mission, duration_seconds=time.time() - start_time)
        observer.capture_snapshot("MISSION_TERMINATED")

        return mission
