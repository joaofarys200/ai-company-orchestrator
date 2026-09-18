"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions & Mission-Level Governance
Comprehensive Unit Test Suite covering all 20 required verification dimensions.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
import unittest

from backend.agents.long_horizon_missions import (
    AdaptiveReplanner,
    BudgetExhaustedError,
    BudgetTracker,
    CheckpointManager,
    CheckpointTamperError,
    CheckpointType,
    CompletionEvaluator,
    CompletionResult,
    CrashRecoveryEngine,
    CyclicDependencyError,
    EvidenceLedger,
    FailureType,
    FinalTerminationState,
    InvalidStateTransitionError,
    LongHorizonMission,
    LongHorizonMissionBridge,
    Milestone,
    MilestoneManager,
    MilestoneState,
    MissionBudget,
    MissionCheckpoint,
    MissionCompletionProof,
    MissionCoordinationManager,
    MissionExecutionEngine,
    MissionMetricsTracker,
    MissionObjective,
    MissionPlan,
    MissionPlanner,
    MissionSecuritySentinel,
    MissionState,
    MissionStateMachine,
    MissionValidator,
    MissionVerifier,
    MultiAgentBypassError,
    ObjectiveCategory,
    ObjectiveDriftError,
    ObjectiveState,
    ObjectiveTracker,
    PrematureCompletionError,
    RiskGovernor,
    RiskSeverity,
    SecurityViolationError,
    StallOscillationState,
    UnauthorizedObjectiveModificationError,
    UnverifiedMilestoneError,
    VerificationFailedError,
)


class TestLongHorizonMissions(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="jarvis_phase67_test_")
        LongHorizonMissionBridge.reset_instance()
        self.bridge = LongHorizonMissionBridge.get_instance(db_path=":memory:")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # 1. Mission Creation & Illegal Leap Prevention
    def test_01_mission_creation(self):
        mission = self.bridge.create_mission(
            objective="Develop autonomous distributed payment gateway",
            success_criteria=["Payment endpoint responsive", "100% test coverage"],
            milestone_count=5,
        )
        self.assertEqual(mission.current_state, MissionState.CREATED)
        self.assertEqual(len(mission.plan.milestones), 5)

        # Illegal leap directly from CREATED -> COMPLETED must raise InvalidStateTransitionError
        with self.assertRaises(InvalidStateTransitionError):
            MissionStateMachine.transition(mission, MissionState.COMPLETED)

    # 2. Objective Tracking & Secondary Priority Invariant
    def test_02_objective_tracking(self):
        primary = MissionObjective(
            objective_id="OBJ_PRIM_01",
            description="Process payments with zero data loss",
            category=ObjectiveCategory.PRIMARY_OBJECTIVES,
            measurable_conditions=["loss_rate == 0.0"],
        )
        secondary = MissionObjective(
            objective_id="OBJ_SEC_01",
            description="Optimize button color gradient",
            category=ObjectiveCategory.SECONDARY_OBJECTIVES,
            measurable_conditions=["contrast_ratio >= 4.5"],
            status=ObjectiveState.SATISFIED,
        )
        tracker = ObjectiveTracker([primary, secondary])

        # Secondary is satisfied, but primary is not -> primary satisfaction must be False
        all_sat, unsatisfied = tracker.are_primary_objectives_satisfied()
        self.assertFalse(all_sat)
        self.assertIn("OBJ_PRIM_01", unsatisfied)

        # Satisfy primary with evidence
        tracker.update_status("OBJ_PRIM_01", ObjectiveState.SATISFIED, evidence_ref="evd_test_01")
        all_sat, unsatisfied = tracker.are_primary_objectives_satisfied()
        self.assertTrue(all_sat)
        self.assertEqual(len(unsatisfied), 0)

    # 3. Objective Drift Guard (Integrating F57)
    def test_03_objective_drift(self):
        original = MissionObjective(
            objective_id="OBJ_PERF_01",
            description="Reduce latency of API calls to under 50ms",
            category=ObjectiveCategory.PRIMARY_OBJECTIVES,
            measurable_conditions=["p99_latency_ms < 50"],
            evidence_requirements=["BENCHMARK"],
            verification_requirements=["PERFORMANCE_TEST"],
        )
        tracker = ObjectiveTracker([original])

        # Candidate drifting to "Reduce number of components"
        drifted = MissionObjective(
            objective_id="OBJ_PERF_01",
            description="Reduce number of components in microservice architecture",
            category=ObjectiveCategory.PRIMARY_OBJECTIVES,
            measurable_conditions=["component_count < 10"],
        )

        has_drift, score, reason = tracker.evaluate_objective_drift(drifted)
        self.assertTrue(has_drift)
        self.assertGreater(score, 0.35)

        with self.assertRaises(ObjectiveDriftError):
            tracker.enforce_no_unauthorized_drift(drifted)

    # 4. Milestone DAG Construction & Cycle Detection
    def test_04_milestone_dag(self):
        planner = MissionPlanner()
        m1 = Milestone(milestone_id="M1", title="Spec")
        m2 = Milestone(milestone_id="M2", title="Impl", dependencies=["M1"])
        m3 = Milestone(milestone_id="M3", title="Test", dependencies=["M2"])

        plan = planner.create_plan("m_dag_test", [m1, m2, m3])
        self.assertEqual(plan.topological_order, ["M1", "M2", "M3"])

        # Create cyclic dependencies M1 -> M2 -> M1
        m_cycle_1 = Milestone(milestone_id="CA", title="A", dependencies=["CB"])
        m_cycle_2 = Milestone(milestone_id="CB", title="B", dependencies=["CA"])
        with self.assertRaises(CyclicDependencyError):
            planner.create_plan("m_cycle_test", [m_cycle_1, m_cycle_2])

    # 5. Multi-Agent Coordination Integration (F66)
    def test_05_agent_coordination(self):
        coord = MissionCoordinationManager(self.tmp_dir)
        m = Milestone(
            milestone_id="M_COORD_01",
            title="Database Schema Migration",
            agent_tasks=[{
                "task_id": "tsk_schema_1",
                "role": "ArchitectAgent",
                "target_files": ["backend/models.py"],
                "target_symbols": ["UserTable"],
            }],
        )
        dispatched = coord.dispatch_milestone_tasks(m, ["ArchitectAgent", "CoderAgent"])
        self.assertEqual(len(dispatched), 1)
        intent = dispatched[0]
        self.assertEqual(intent["milestone_id"], "M_COORD_01")
        self.assertEqual(intent["agent_id"], "ArchitectAgent")
        self.assertIn("claim_backend/models.py", intent["claim_ids"])

        coord.register_execution_completion(intent["intent_id"], success=True)
        self.assertEqual(coord.intent_registry[intent["intent_id"]]["status"], "COMMITTED")

    # 6. Resource Budget Enforcement (11 Dimensions)
    def test_06_budget_enforcement(self):
        budget = MissionBudget(
            wall_time_sec=100.0,
            cpu_sec=50.0,
            memory_mb=1024.0,
            agent_executions=2,
            patches=5,
        )
        tracker = BudgetTracker(budget)

        # Consuming 1 agent execution -> OK
        exh, dim = tracker.record_consumption("agent_executions", 1.0)
        self.assertFalse(exh)

        # Consuming 2nd agent execution -> Limit reached (2/2)
        exh, dim = tracker.record_consumption("agent_executions", 1.0)
        self.assertTrue(exh)
        self.assertEqual(dim, "agent_executions")

        # Further consumption must raise BudgetExhaustedError
        with self.assertRaises(BudgetExhaustedError):
            tracker.assert_available("agent_executions", 1.0)

    # 7. Checkpoint Creation & Immutability (SHA-256)
    def test_07_checkpoint(self):
        mgr = CheckpointManager()
        cp = mgr.create_checkpoint(
            mission_id="m_chk_01",
            checkpoint_type=CheckpointType.FULL,
            mission_state="EXECUTING",
            objective_state={"OBJ_1": "IN_PROGRESS"},
            plan_dag={"nodes": ["M1", "M2"]},
            agent_states={},
            claims=[],
            workspace_states={"git_rev": "c606327"},
            transaction_states={"active": []},
            architecture_hash="arch_sha_123",
            contract_hash="contract_sha_456",
            behavior_hash="behavior_sha_789",
            verification_ledger=[],
            budget_remaining={"pct": 95.0},
            evidence_root="evd_root_abc",
        )
        self.assertTrue(mgr.validate_integrity(cp))
        self.assertEqual(len(cp.sha256_hash), 64)

        # Tampering with checkpoint fields must be detected
        tampered = MissionCheckpoint(
            checkpoint_id=cp.checkpoint_id,
            mission_id=cp.mission_id,
            checkpoint_type=cp.checkpoint_type,
            timestamp=cp.timestamp,
            mission_state="COMPLETED",  # tampered state
            objective_state=cp.objective_state,
            plan_dag=cp.plan_dag,
            agent_states=cp.agent_states,
            claims=cp.claims,
            workspace_states=cp.workspace_states,
            transaction_states=cp.transaction_states,
            architecture_hash=cp.architecture_hash,
            contract_hash=cp.contract_hash,
            behavior_hash=cp.behavior_hash,
            verification_ledger=cp.verification_ledger,
            budget_remaining=cp.budget_remaining,
            evidence_root=cp.evidence_root,
            sha256_hash=cp.sha256_hash,
        )
        with self.assertRaises(CheckpointTamperError):
            mgr.validate_integrity(tampered)

    # 8. Crash Interruption Simulation
    def test_08_crash_recovery(self):
        engine = CrashRecoveryEngine()
        mission = self.bridge.create_mission("Crash Test Mission", milestone_count=3)
        mission.current_state = MissionState.EXECUTING

        crash_event = engine.simulate_crash(mission, interruption_stage="patch")
        self.assertEqual(mission.current_state, MissionState.RECOVERING)
        self.assertEqual(crash_event["interruption_stage"], "patch")

    # 9. Resume State Reconciliation
    def test_09_resume(self):
        rec = CrashRecoveryEngine()
        mission = self.bridge.create_mission("Resume Test", milestone_count=3)
        cp_mgr = CheckpointManager()
        cp = cp_mgr.create_checkpoint(
            mission_id=mission.mission_id,
            checkpoint_type=CheckpointType.MILESTONE,
            mission_state="EXECUTING",
            objective_state={},
            plan_dag={"milestones": {}},
            agent_states={},
            claims=[],
            workspace_states={"architecture_hash": "arch_valid"},
            transaction_states={"applied_tx_ids": ["tx_1", "tx_2"]},
            architecture_hash="arch_valid",
            contract_hash="c_hash",
            behavior_hash="b_hash",
            verification_ledger=[],
            budget_remaining={"pct": 90.0},
            evidence_root="evd_root",
        )

        decision, report = rec.reconcile_and_resume(
            mission=mission,
            checkpoint=cp,
            current_workspace_state={"architecture_hash": "arch_valid"},
            applied_transaction_ids={"tx_1", "tx_2"},
        )
        self.assertEqual(decision, "RESUME")
        self.assertEqual(mission.current_state, MissionState.READY)

    # 10. Duplicate Side-Effect Prevention
    def test_10_duplicate_side_effect_prevention(self):
        rec = CrashRecoveryEngine()
        mission = self.bridge.create_mission("Duplicate Side Effect Test", milestone_count=2)
        cp_mgr = CheckpointManager()
        cp = cp_mgr.create_checkpoint(
            mission_id=mission.mission_id,
            checkpoint_type=CheckpointType.MILESTONE,
            mission_state="EXECUTING",
            objective_state={},
            plan_dag={},
            agent_states={},
            claims=[],
            workspace_states={"architecture_hash": "arch_1"},
            transaction_states={"applied_tx_ids": ["tx_100"]},
            architecture_hash="arch_1",
            contract_hash="c_1",
            behavior_hash="b_1",
            verification_ledger=[],
            budget_remaining={},
            evidence_root="root",
        )

        # Workspace has uncommitted transaction tx_ghost
        decision, report = rec.reconcile_and_resume(
            mission=mission,
            checkpoint=cp,
            current_workspace_state={"architecture_hash": "arch_1", "corrupted": False},
            applied_transaction_ids={"tx_100", "tx_ghost"},
        )
        # Residuals detected
        self.assertTrue(any("tx_ghost" in res for res in report["residuals"]))
        self.assertEqual(report["safe_transactions"], ["tx_100"])

    # 11. Failure Recovery & Classification
    def test_11_failure_recovery(self):
        m_mgr = MilestoneManager()
        m1 = Milestone(milestone_id="M_FAIL_01", title="Flaky Build")
        m_mgr.register_milestones([m1])
        m_mgr.start_milestone("M_FAIL_01")
        m_mgr.fail_milestone("M_FAIL_01", error_message="BUILD_FAILURE: Syntax error on line 42")
        self.assertIn("M_FAIL_01", m_mgr.failed_milestones)
        self.assertEqual(m1.status, MilestoneState.FAILED)

    # 12. Adaptive Replanning (REPLAN != OBJECTIVE_CHANGE)
    def test_12_adaptive_replanning(self):
        replanner = AdaptiveReplanner()
        planner = MissionPlanner()
        plan = planner.create_plan("plan_adapt", [
            Milestone(milestone_id="M1", title="Step 1"),
            Milestone(milestone_id="M2", title="Step 2", dependencies=["M1"]),
        ])
        primary_ids = {"OBJ_CORE"}

        did_adapt, new_plan, stall = replanner.observe_and_adapt(
            plan=plan,
            completed_milestone_id="M1",
            observed_outputs=[],
            unresolved_issues=["Test gap in M1"],
            primary_objective_ids=primary_ids,
        )
        self.assertTrue(did_adapt)
        self.assertEqual(new_plan.replan_count, 1)
        self.assertIn("M_REPAIR_M1_1", new_plan.milestones)

    # 13. Stall Detection
    def test_13_stall_detection(self):
        replanner = AdaptiveReplanner()
        for _ in range(4):
            replanner.record_action("PATCH_RETRY_SAME_FILE", "state_hash_same")
        state = replanner.detect_stall_or_oscillation()
        self.assertEqual(state, StallOscillationState.STALLED)

    # 14. Oscillation Detection (A -> B -> A -> B)
    def test_14_oscillation_detection(self):
        replanner = AdaptiveReplanner()
        replanner.record_action("APPLY_PATCH_A", "hash_A")
        replanner.record_action("ROLLBACK_TO_B", "hash_B")
        replanner.record_action("APPLY_PATCH_A", "hash_A")
        replanner.record_action("ROLLBACK_TO_B", "hash_B")
        state = replanner.detect_stall_or_oscillation()
        self.assertEqual(state, StallOscillationState.OSCILLATING)

    # 15. Mission Completion Proof & Zero False Success
    def test_15_mission_completion_proof(self):
        evaluator = CompletionEvaluator()
        mission = self.bridge.create_mission("Completion Proof Test", milestone_count=2)

        # All milestones done, but primary objectives NOT satisfied -> INSUFFICIENT_EVIDENCE
        proof_invalid = evaluator.evaluate(
            mission=mission,
            primary_satisfied=False,
            secondary_status={},
            all_milestones_completed=True,
            verification_passed=True,
            verification_coverage=1.0,
            architecture_stable=True,
            contracts_intact=True,
            behaviors_intact=True,
            security_safe=True,
            unresolved_risks=[],
            evidence_refs=["evd_1"],
            final_checkpoint_id="chk_final",
        )
        self.assertEqual(proof_invalid.result, CompletionResult.INSUFFICIENT_EVIDENCE)

        # Fully verified and satisfied -> COMPLETED_WITHIN_SCOPE
        proof_valid = evaluator.evaluate(
            mission=mission,
            primary_satisfied=True,
            secondary_status={},
            all_milestones_completed=True,
            verification_passed=True,
            verification_coverage=1.0,
            architecture_stable=True,
            contracts_intact=True,
            behaviors_intact=True,
            security_safe=True,
            unresolved_risks=[],
            evidence_refs=["evd_1", "evd_2"],
            final_checkpoint_id="chk_final",
        )
        self.assertEqual(proof_valid.result, CompletionResult.COMPLETED_WITHIN_SCOPE)

    # 16. Human Review Timeout -> BLOCKED
    def test_16_human_review_timeout(self):
        gov = RiskGovernor(review_timeout_sec=10.0)
        t_id = gov.create_review_ticket("m_timeout_test", ["security_uncertainty"])
        now = time.time()
        is_timeout = gov.check_review_timeout(t_id, simulated_current_time=now + 15.0)
        self.assertTrue(is_timeout)

    # 17. Security Sentinel Mutation Block
    def test_17_security_block(self):
        sentinel = MissionSecuritySentinel()
        is_safe, violations = sentinel.validate_mutation_intent(
            agent_id="CoderAgent",
            target_files=[".env", "../../etc/passwd"],
            patch_content="subprocess.Popen('rm -rf /', shell=True)",
        )
        self.assertFalse(is_safe)
        self.assertTrue(any("FORBIDDEN_TARGET_FILE" in v for v in violations))
        self.assertTrue(any("UNSAFE_PATH_TRAVERSAL" in v for v in violations))
        self.assertTrue(any("MALICIOUS_PATTERN_DETECTED" in v for v in violations))

    # 18. Unseen Long-Horizon Mission Execution
    def test_18_unseen_mission(self):
        mission = self.bridge.create_mission(
            objective="Migrate legacy authentication to OAuth2/OIDC",
            milestone_count=6,
        )
        res = self.bridge.run_bounded(mission.mission_id, max_steps=10)
        self.assertIn(mission.current_state, (MissionState.COMPLETED, MissionState.FINISHING))
        self.assertIsNotNone(mission.completion_proof)

    # 19. Denominator Reconciliation & Timing Invariant
    def test_19_denominator_reconciliation(self):
        metrics = MissionMetricsTracker()
        metrics.add_timing("planning_ms", 12.5)
        metrics.add_timing("scheduling_ms", 5.0)
        metrics.add_timing("verification_ms", 30.0)
        metrics.add_timing("checkpoint_ms", 7.5)
        metrics.total_cpu_ms = 60.0

        rec = metrics.reconcile_timing()
        self.assertTrue(rec["timing_invariant_valid"])
        self.assertEqual(rec["delta"], 0.0)
        self.assertEqual(rec["stage_total_ms"], 55.0)
        self.assertEqual(rec["overhead_ms"], 5.0)

    # 20. Final Termination State Validation
    def test_20_final_termination_state(self):
        evaluator = CompletionEvaluator()
        mission = self.bridge.create_mission("Terminal State Mission", milestone_count=2)
        proof = evaluator.evaluate(
            mission=mission,
            primary_satisfied=True,
            secondary_status={},
            all_milestones_completed=True,
            verification_passed=True,
            verification_coverage=1.0,
            architecture_stable=True,
            contracts_intact=True,
            behaviors_intact=True,
            security_safe=True,
            unresolved_risks=["LOW_PRIORITY_OPT_RISK"],
            evidence_refs=["evd_done"],
            final_checkpoint_id="chk_final",
        )
        self.assertEqual(proof.result, CompletionResult.COMPLETED_WITH_UNRESOLVED_RISK)


if __name__ == "__main__":
    unittest.main()
