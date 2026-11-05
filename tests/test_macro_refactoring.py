"""
JARVIS OS — Phase 73: Autonomous Macro-Refactoring Engine
Deterministic Test Suite covering all 20 required scenarios from Section 9.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
import pytest

from backend.agents.macro_refactoring import (
    BudgetExceededError,
    CheckpointCorruptError,
    DependencyCycleError,
    EvidenceInvalidator,
    MacroMigration,
    MacroRefactoringBridge,
    MacroRefactoringGovernance,
    MacroRefactoringPlanner,
    MigrationCheckpoint,
    MigrationGraph,
    MigrationState,
    MigrationStep,
    MigrationStepType,
    StepExecutor,
    StepState,
    UnauthorizedMutationError,
    UnresolvedDependencyError,
)
from backend.agents.macro_refactoring.recovery import (
    AdaptiveReplanEngine,
    CheckpointManager,
    CompensationOrchestrator,
)
from backend.agents.macro_refactoring.verification import MacroRefactoringVerifier


class TestMacroRefactoringEngine:

    @pytest.fixture(autouse=True)
    def setup_temp_store(self):
        self.temp_dir = tempfile.mkdtemp(prefix="jarvis_macro_refactoring_test_")
        self.bridge = MacroRefactoringBridge(store_dir=self.temp_dir)
        yield
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Scenario 1: Successful multi-module migration
    # -------------------------------------------------------------------------
    def test_01_successful_multi_module_migration(self):
        migration = self.bridge.plan_migration(
            objective="Decouple Core Orchestrator from Legacy Telemetry across 3 modules",
            project_id="test_project_multi_module",
            producers=["backend/core/orchestrator.py", "backend/core/telemetry_emitter.py"],
            consumers=["backend/services/worker.py", "backend/api/routes.py", "backend/cli/main.py"],
            affected_files=["backend/core/orchestrator.py", "backend/services/worker.py"],
        )
        assert migration.status == MigrationState.PLANNED
        assert len(migration.steps) >= 7

        executed_migration = self.bridge.execute_migration(migration)
        assert executed_migration.status == MigrationState.COMPLETED
        assert executed_migration.completed_at is not None
        assert executed_migration.provenance_hash != ""
        assert all(s.state == StepState.ACCEPTED for s in executed_migration.steps.values())
        assert len(executed_migration.evidence_ledger) > 0

    # -------------------------------------------------------------------------
    # Scenario 2: Migration affecting more than 15 dependency nodes
    # -------------------------------------------------------------------------
    def test_02_migration_affecting_more_than_15_nodes(self):
        # 22 consumers + 2 producers = 24 total nodes (>15 limit from Phase 69)
        consumers = [f"backend/consumers/module_{i:02d}.py" for i in range(1, 23)]
        producers = ["backend/core/engine.py", "backend/core/interfaces.py"]

        migration = self.bridge.plan_migration(
            objective="Cross-System Transformation across 24 dependency nodes",
            project_id="test_large_blast_radius",
            producers=producers,
            consumers=consumers,
            affected_files=consumers + producers,
        )
        assert migration.blast_radius_nodes >= 24
        # Planner should batch consumers into multiple steps so each step <= 15 nodes
        consumer_steps = [
            s for s in migration.steps.values()
            if s.step_type == MigrationStepType.CONSUMER_MIGRATION
        ]
        assert len(consumer_steps) >= 2
        for cs in consumer_steps:
            assert len(cs.affected_files) <= 15

        res = self.bridge.execute_migration(migration)
        assert res.status == MigrationState.COMPLETED

    # -------------------------------------------------------------------------
    # Scenario 3: Producer-consumer migration requiring intermediate compatibility layer
    # -------------------------------------------------------------------------
    def test_03_producer_consumer_intermediate_compatibility_layer(self):
        migration = self.bridge.plan_migration(
            objective="Migrate Payment Provider with Backward-Compatible Shim",
            project_id="test_compat_shim",
            producers=["backend/payment/provider.py"],
            consumers=["backend/api/checkout.py", "backend/api/orders.py"],
            affected_files=["backend/payment/provider.py"],
        )
        compat_step = next(s for s in migration.steps.values() if s.step_type == MigrationStepType.COMPATIBILITY_LAYER)
        consumer_steps = [s for s in migration.steps.values() if s.step_type == MigrationStepType.CONSUMER_MIGRATION]

        # Invariant: consumer steps must depend on the compatibility step
        for cs in consumer_steps:
            assert compat_step.step_id in cs.dependencies

        res = self.bridge.execute_migration(migration)
        assert res.status == MigrationState.COMPLETED

    # -------------------------------------------------------------------------
    # Scenario 4: Dependency cycle detected during planning
    # -------------------------------------------------------------------------
    def test_04_dependency_cycle_detected_during_planning(self):
        s1 = MigrationStep(
            step_id="step_a",
            step_type=MigrationStepType.PREPARATION,
            title="Step A",
            description="Cycle node A",
            dependencies=["step_c"],
        )
        s2 = MigrationStep(
            step_id="step_b",
            step_type=MigrationStepType.COMPATIBILITY_LAYER,
            title="Step B",
            description="Cycle node B",
            dependencies=["step_a"],
        )
        s3 = MigrationStep(
            step_id="step_c",
            step_type=MigrationStepType.CUTOVER,
            title="Step C",
            description="Cycle node C",
            dependencies=["step_b"],
        )

        with pytest.raises(DependencyCycleError) as exc_info:
            MigrationGraph({"step_a": s1, "step_b": s2, "step_c": s3}).topological_sort()

        assert "Dependency cycle detected" in str(exc_info.value)

    # -------------------------------------------------------------------------
    # Scenario 5: Undiscovered or unresolved consumer dependency
    # -------------------------------------------------------------------------
    def test_05_undiscovered_or_unresolved_consumer_dependency(self):
        s1 = MigrationStep(
            step_id="step_orphan",
            step_type=MigrationStepType.CONSUMER_MIGRATION,
            title="Orphan Step",
            description="Depends on missing phantom step",
            dependencies=["step_nonexistent_phantom"],
        )
        with pytest.raises(UnresolvedDependencyError) as exc_info:
            MigrationGraph({"step_orphan": s1})

        assert "undiscovered or unresolved step 'step_nonexistent_phantom'" in str(exc_info.value)

    # -------------------------------------------------------------------------
    # Scenario 6: Failure in an early migration step
    # -------------------------------------------------------------------------
    def test_06_failure_in_early_migration_step(self):
        migration = self.bridge.plan_migration(
            objective="Early Step Failure Test",
            project_id="test_early_fail",
            producers=["backend/module_a.py"],
            consumers=["backend/module_b.py"],
            affected_files=["backend/module_a.py"],
        )
        first_step_id = migration.execution_order[0]

        res = self.bridge.execute_migration(
            migration,
            simulate_failure_step_id=first_step_id,
        )
        assert res.status == MigrationState.ROLLED_BACK
        assert res.steps[first_step_id].state in (StepState.FAILED, StepState.ROLLED_BACK)
        # Downstream steps should remain PENDING or not executed
        for step_id in migration.execution_order[1:]:
            assert res.steps[step_id].state == StepState.PENDING

    # -------------------------------------------------------------------------
    # Scenario 7: Failure after multiple accepted steps (backwards compensation)
    # -------------------------------------------------------------------------
    def test_07_failure_after_multiple_accepted_steps(self):
        migration = self.bridge.plan_migration(
            objective="Late Step Failure Test",
            project_id="test_late_fail",
            producers=["backend/core.py"],
            consumers=["backend/c1.py", "backend/c2.py"],
            affected_files=["backend/core.py"],
        )
        fail_step_id = migration.execution_order[3]  # Fail on 4th step

        res = self.bridge.execute_migration(
            migration,
            simulate_failure_step_id=fail_step_id,
        )
        assert res.status == MigrationState.ROLLED_BACK
        # The first 3 steps must have been rolled back in reverse topological order
        for idx in range(3):
            s_id = migration.execution_order[idx]
            assert res.steps[s_id].state == StepState.ROLLED_BACK

    # -------------------------------------------------------------------------
    # Scenario 8: Downstream evidence invalidation
    # -------------------------------------------------------------------------
    def test_08_downstream_evidence_invalidation(self):
        migration = self.bridge.plan_migration(
            objective="Evidence Invalidation Test",
            project_id="test_invalidation",
            producers=["backend/a.py"],
            consumers=["backend/b.py"],
            affected_files=["backend/a.py"],
        )
        # Execute 3 steps
        res = self.bridge.execute_migration(migration, max_steps=3)
        s1_id = migration.execution_order[0]
        s2_id = migration.execution_order[1]
        assert res.steps[s2_id].state == StepState.ACCEPTED

        # Mutate upstream s1, which must invalidate downstream s2
        invalidator = EvidenceInvalidator()
        inv_records = invalidator.invalidate_downstream_evidence(
            migration=res,
            mutating_step_id=s1_id,
            reason="Upstream API signature unexpectedly modified.",
        )
        assert len(inv_records) > 0
        assert res.steps[s2_id].state == StepState.INVALIDATED

        # Freshness audit must detect stale evidence
        is_fresh, stale_reasons = invalidator.check_evidence_freshness(res)
        assert not is_fresh
        assert any(s2_id in r for r in stale_reasons)

    # -------------------------------------------------------------------------
    # Scenario 9: Process interruption followed by recovery
    # -------------------------------------------------------------------------
    def test_09_process_interruption_followed_by_recovery(self):
        migration = self.bridge.plan_migration(
            objective="Crash Recovery Test",
            project_id="test_crash_recovery",
            producers=["backend/p.py"],
            consumers=["backend/c.py"],
            affected_files=["backend/p.py"],
        )
        # Partially execute up to step 2
        partial = self.bridge.execute_migration(migration, max_steps=2)
        assert partial.status == MigrationState.PARTIALLY_COMPLETED
        assert len(partial.checkpoints) >= 2

        latest_chk_id = partial.checkpoints[-1].checkpoint_id

        # Resume from checkpoint
        resumed = self.bridge.resume_migration(latest_chk_id)
        assert resumed.status == MigrationState.COMPLETED
        assert all(s.state == StepState.ACCEPTED for s in resumed.steps.values())

    # -------------------------------------------------------------------------
    # Scenario 10: Corrupted or stale migration checkpoint
    # -------------------------------------------------------------------------
    def test_10_corrupted_or_stale_migration_checkpoint(self):
        migration = self.bridge.plan_migration(
            objective="Corrupt Checkpoint Test",
            project_id="test_corrupt_chk",
            producers=["backend/p.py"],
            consumers=["backend/c.py"],
            affected_files=["backend/p.py"],
        )
        chk_mgr = CheckpointManager()
        chk = chk_mgr.create_checkpoint(migration)
        # Tamper with snapshot payload
        chk.state_snapshot["tampered_key"] = "malicious_injection"

        with pytest.raises(CheckpointCorruptError) as exc_info:
            chk_mgr.restore_from_checkpoint(chk, migration)

        assert "corrupted or tampered" in str(exc_info.value)

    # -------------------------------------------------------------------------
    # Scenario 11: Conflicting concurrent modifications
    # -------------------------------------------------------------------------
    def test_11_conflicting_concurrent_modifications(self):
        class MockConflictingClaimManager:
            def acquire_claim(self, *args, **kwargs):
                return False, None, "File is locked by concurrent agent 'refactor_worker_2'"
            def release_claim(self, *args, **kwargs):
                pass

        step = MigrationStep(
            step_id="step_locked",
            step_type=MigrationStepType.CUTOVER,
            title="Locked Step",
            description="Attempts to edit locked file",
            affected_files=["backend/locked_file.py"],
        )
        migration = MacroMigration(
            migration_id="mig_conflict",
            objective="Conflict Test",
            project_id="p1",
            steps={"step_locked": step},
        )
        executor = StepExecutor(claim_manager=MockConflictingClaimManager())
        ok, msg = executor.execute_step(step, migration)

        assert not ok
        assert "Resource conflict" in msg
        assert step.state == StepState.FAILED

    # -------------------------------------------------------------------------
    # Scenario 12: Idempotent retry of a failed step
    # -------------------------------------------------------------------------
    def test_12_idempotent_retry_of_failed_step(self):
        migration = self.bridge.plan_migration(
            objective="Idempotent Retry Test",
            project_id="test_retry",
            producers=["backend/p.py"],
            consumers=["backend/c.py"],
            affected_files=["backend/p.py"],
        )
        first_step = migration.steps[migration.execution_order[0]]
        first_step.max_retries = 1

        attempts = 0
        def flakey_mutation(s: MigrationStep):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                return False, "Transient network socket timeout", {}
            return True, "Success on retry", {}

        res = self.bridge.execute_migration(migration, mutation_fn=flakey_mutation)
        assert res.status == MigrationState.COMPLETED
        assert first_step.retry_count == 1
        assert first_step.state == StepState.ACCEPTED

    # -------------------------------------------------------------------------
    # Scenario 13: Replanning after unexpected architectural drift
    # -------------------------------------------------------------------------
    def test_13_replanning_after_unexpected_architectural_drift(self):
        migration = self.bridge.plan_migration(
            objective="Drift Replan Test",
            project_id="test_drift",
            producers=["backend/service.py"],
            consumers=["backend/c1.py"],
            affected_files=["backend/service.py"],
        )
        # Execute 2 steps
        self.bridge.execute_migration(migration, max_steps=2)

        # Discover 3 new un-registered consumers
        new_consumers = ["backend/c2_discovered.py", "backend/c3_discovered.py", "backend/c4_discovered.py"]
        replanned = self.bridge.replan_migration(
            migration,
            newly_discovered_consumers=new_consumers,
            reason="Static analysis identified 3 dynamic import consumers.",
        )
        assert any("replan_cons" in s_id for s_id in replanned.steps.keys())
        assert replanned.blast_radius_nodes >= 5

        # Execute replanned migration to completion
        final = self.bridge.execute_migration(replanned)
        assert final.status == MigrationState.COMPLETED

    # -------------------------------------------------------------------------
    # Scenario 14: Insufficient execution budget
    # -------------------------------------------------------------------------
    def test_14_insufficient_execution_budget(self):
        migration = self.bridge.plan_migration(
            objective="Budget Exceeded Test",
            project_id="test_budget",
            producers=["backend/p.py"],
            consumers=["backend/c.py"],
            affected_files=["backend/p.py"],
        )
        migration.execution_cost_budget = 15.0  # Allow only 1.5 steps (each default 10.0)

        res = self.bridge.execute_migration(migration)
        assert res.status == MigrationState.BLOCKED
        assert any("budget exceeded" in b.lower() for b in res.unresolved_blockers)

    # -------------------------------------------------------------------------
    # Scenario 15: Security-sensitive change requiring approval
    # -------------------------------------------------------------------------
    def test_15_security_sensitive_change_requiring_approval(self):
        migration = self.bridge.plan_migration(
            objective="Security Gated Migration",
            project_id="test_security",
            producers=["backend/auth/jwt_keys.py"],
            consumers=["backend/api/auth.py"],
            affected_files=["backend/auth/jwt_keys.py"],
            is_security_sensitive=True,
        )
        assert migration.risk_score >= 0.7

        # Without human approval, stops at boundary
        blocked_res = self.bridge.execute_migration(migration, human_approval_token=None)
        assert blocked_res.status == MigrationState.HUMAN_REVIEW_REQUIRED
        assert any("human approval" in b.lower() for b in blocked_res.unresolved_blockers)

        # With explicit human approval token, executes to completion
        approved_res = self.bridge.execute_migration(
            blocked_res, human_approval_token="HUMAN_TOKEN_AUTHORIZED_2026"
        )
        assert approved_res.status == MigrationState.COMPLETED

    # -------------------------------------------------------------------------
    # Scenario 16: Failed behavioral invariant despite passing unit tests
    # -------------------------------------------------------------------------
    def test_16_failed_behavioral_invariant_despite_passing_unit_tests(self):
        migration = self.bridge.plan_migration(
            objective="Behavioral Drift Test",
            project_id="test_drift_invariants",
            producers=["backend/p.py"],
            consumers=["backend/c.py"],
            affected_files=["backend/p.py"],
        )
        # Tests pass locally, but dual-path shadow probe detects behavioral divergence
        res = self.bridge.execute_migration(migration, behavior_drift_detected=True)
        assert res.status == MigrationState.BLOCKED
        assert any("Behavioral drift detected" in b for b in res.unresolved_blockers)

    # -------------------------------------------------------------------------
    # Scenario 17: Attempted rollback with an unsafe compensation plan
    # -------------------------------------------------------------------------
    def test_17_attempted_rollback_with_unsafe_compensation_plan(self):
        migration = self.bridge.plan_migration(
            objective="Unsafe Rollback Test",
            project_id="test_unsafe_rollback",
            producers=["backend/p.py"],
            consumers=["backend/c.py"],
            affected_files=["backend/p.py"],
        )
        # Mark an intermediate step as irreversible (e.g. database schema drop)
        step_2 = migration.steps[migration.execution_order[1]]
        step_2.metadata["is_irreversible"] = True

        # Execute 2 steps, then fail on step 3
        fail_step_id = migration.execution_order[2]
        res = self.bridge.execute_migration(migration, simulate_failure_step_id=fail_step_id)

        assert res.status == MigrationState.BLOCKED
        assert any("irreversible" in b.lower() for b in res.unresolved_blockers)

    # -------------------------------------------------------------------------
    # Scenario 18: Attempted completion with unresolved blockers
    # -------------------------------------------------------------------------
    def test_18_attempted_completion_with_unresolved_blockers(self):
        migration = self.bridge.plan_migration(
            objective="Unresolved Blockers Test",
            project_id="test_unresolved",
            producers=["backend/p.py"],
            consumers=["backend/c.py"],
            affected_files=["backend/p.py"],
        )
        migration.unresolved_blockers.append("Critical external microservice unreachable")
        res = self.bridge.execute_migration(migration)
        assert res.status == MigrationState.BLOCKED
        assert "Critical external microservice unreachable" in res.unresolved_blockers

    # -------------------------------------------------------------------------
    # Scenario 19: Attempted release promotion without release-readiness approval
    # -------------------------------------------------------------------------
    def test_19_attempted_release_promotion_without_release_approval(self):
        migration = self.bridge.plan_migration(
            objective="Release Gate Decoupling Test",
            project_id="test_release_gate",
            producers=["backend/p.py"],
            consumers=["backend/c.py"],
            affected_files=["backend/p.py"],
        )
        res = self.bridge.execute_migration(migration)
        assert res.status == MigrationState.COMPLETED

        gov = MacroRefactoringGovernance()
        ok, msg = gov.evaluate_release_boundary(res)
        assert ok
        assert "Phase 70 Release Gate" in msg
        # Completion must not alter deployment environment
        assert res.metadata.get("deployed_to_prod") is not True

    # -------------------------------------------------------------------------
    # Scenario 20: An unseen migration topology not hardcoded in the test suite
    # -------------------------------------------------------------------------
    def test_20_unseen_migration_topology_not_hardcoded(self):
        r"""
        Tests a complex diamond-and-tree DAG topology:
                 root
                /    \
              left   right
                \    /    \
                 mid     side
                   \      /
                    final
        """
        root = MigrationStep(
            step_id="step_root",
            step_type=MigrationStepType.PREPARATION,
            title="Root Node",
            description="Preparation",
            dependencies=[],
        )
        left = MigrationStep(
            step_id="step_left",
            step_type=MigrationStepType.COMPATIBILITY_LAYER,
            title="Left Branch",
            description="Compat Left",
            dependencies=["step_root"],
        )
        right = MigrationStep(
            step_id="step_right",
            step_type=MigrationStepType.COMPATIBILITY_LAYER,
            title="Right Branch",
            description="Compat Right",
            dependencies=["step_root"],
        )
        mid = MigrationStep(
            step_id="step_mid",
            step_type=MigrationStepType.CONSUMER_MIGRATION,
            title="Middle Join",
            description="Joins Left and Right",
            dependencies=["step_left", "step_right"],
        )
        side = MigrationStep(
            step_id="step_side",
            step_type=MigrationStepType.CONSUMER_MIGRATION,
            title="Side Consumer",
            description="Consumer from Right only",
            dependencies=["step_right"],
        )
        final = MigrationStep(
            step_id="step_final",
            step_type=MigrationStepType.CUTOVER,
            title="Final Cutover",
            description="Cutover joining Middle and Side",
            dependencies=["step_mid", "step_side"],
        )

        custom_steps = [root, left, right, mid, side, final]
        migration = self.bridge.plan_migration(
            objective="Unseen Diamond-Tree Topology",
            project_id="test_unseen_topo",
            producers=["backend/root.py"],
            consumers=["backend/final.py"],
            affected_files=["backend/root.py"],
            custom_steps=custom_steps,
        )

        # Invariant: root before left and right, left and right before mid, mid and side before final
        order = migration.execution_order
        assert order.index("step_root") < order.index("step_left")
        assert order.index("step_root") < order.index("step_right")
        assert order.index("step_left") < order.index("step_mid")
        assert order.index("step_right") < order.index("step_mid")
        assert order.index("step_right") < order.index("step_side")
        assert order.index("step_mid") < order.index("step_final")
        assert order.index("step_side") < order.index("step_final")

        res = self.bridge.execute_migration(migration)
        assert res.status == MigrationState.COMPLETED
        assert all(s.state == StepState.ACCEPTED for s in res.steps.values())
