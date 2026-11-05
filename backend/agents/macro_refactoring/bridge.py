"""
JARVIS OS — Phase 73: Autonomous Macro-Refactoring Engine
Module: bridge.py
Central orchestrator implementing the 9-stage lifecycle:
OBSERVE -> DEFINE OBJECTIVE -> BUILD MIGRATION GRAPH -> VALIDATE PLAN ->
EXECUTE STEP -> VERIFY STEP -> RECONCILE GLOBAL STATE ->
CONTINUE / REPLAN / ROLLBACK -> VERIFY FINAL STATE.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from .governance import MacroRefactoringGovernance
from .graph import MigrationGraph
from .invalidation import EvidenceInvalidator
from .models import (
    BudgetExceededError,
    InvariantViolationError,
    MacroMigration,
    MacroRefactoringError,
    MigrationCheckpoint,
    MigrationState,
    MigrationStep,
    StepState,
)
from .persistence import MacroRefactoringStore
from .planner import MacroRefactoringPlanner
from .recovery import (
    AdaptiveReplanEngine,
    CheckpointManager,
    CompensationOrchestrator,
)
from .step_executor import StepExecutor
from .verification import GlobalVerificationReport, MacroRefactoringVerifier


class MacroRefactoringBridge:
    """
    Main engine orchestrating large-scale cross-component architectural migrations.
    """

    def __init__(
        self,
        store_dir: str = ".jarvis/macro_migrations",
        planner: Optional[MacroRefactoringPlanner] = None,
        executor: Optional[StepExecutor] = None,
        verifier: Optional[MacroRefactoringVerifier] = None,
        invalidator: Optional[EvidenceInvalidator] = None,
        checkpoint_mgr: Optional[CheckpointManager] = None,
        compensation_orch: Optional[CompensationOrchestrator] = None,
        replan_engine: Optional[AdaptiveReplanEngine] = None,
        governance: Optional[MacroRefactoringGovernance] = None,
    ):
        self.invalidator = invalidator or EvidenceInvalidator()
        self.planner = planner or MacroRefactoringPlanner()
        self.executor = executor or StepExecutor(invalidator=self.invalidator)
        self.verifier = verifier or MacroRefactoringVerifier(invalidator=self.invalidator)
        self.checkpoint_mgr = checkpoint_mgr or CheckpointManager()
        self.compensation_orch = compensation_orch or CompensationOrchestrator()
        self.replan_engine = replan_engine or AdaptiveReplanEngine()
        self.governance = governance or MacroRefactoringGovernance()
        self.store = MacroRefactoringStore(base_dir=store_dir)

    def plan_migration(
        self,
        objective: str,
        project_id: str,
        producers: List[str],
        consumers: List[str],
        affected_files: List[str],
        is_security_sensitive: bool = False,
        has_persistence_boundary: bool = False,
        custom_steps: Optional[List[MigrationStep]] = None,
    ) -> MacroMigration:
        """Stage 1-4: OBSERVE -> DEFINE OBJECTIVE -> BUILD GRAPH -> VALIDATE PLAN."""
        migration = self.planner.plan_macro_migration(
            objective=objective,
            project_id=project_id,
            producers=producers,
            consumers=consumers,
            affected_files=affected_files,
            is_security_sensitive=is_security_sensitive,
            has_persistence_boundary=has_persistence_boundary,
            custom_steps=custom_steps,
        )
        self.store.save_migration(migration)
        return migration

    def execute_migration(
        self,
        migration: MacroMigration,
        human_approval_token: Optional[str] = None,
        mutation_fn: Optional[Callable[[MigrationStep], Tuple[bool, str, Dict[str, Any]]]] = None,
        verification_fn: Optional[Callable[[MigrationStep], Tuple[bool, str, Dict[str, Any]]]] = None,
        compensation_fn: Optional[Callable[[str, str], Tuple[bool, str]]] = None,
        simulate_failure_step_id: Optional[str] = None,
        behavior_drift_detected: bool = False,
        build_errors_detected: bool = False,
        test_failures_detected: bool = False,
        max_steps: Optional[int] = None,
    ) -> MacroMigration:
        """
        Stage 5-9: EXECUTE STEP -> VERIFY STEP -> RECONCILE GLOBAL STATE ->
        CONTINUE / REPLAN / ROLLBACK -> VERIFY FINAL STATE.
        """
        migration.status = MigrationState.EXECUTING
        graph = MigrationGraph(migration.steps)

        # 1. Initial Governance Gate Evaluation
        sec_ok, sec_msg = self.governance.evaluate_security_gate(
            migration, human_approval_token=human_approval_token
        )
        if not sec_ok:
            self.store.save_migration(migration)
            return migration

        steps_executed = 0
        for step_id in list(migration.execution_order):
            if max_steps is not None and steps_executed >= max_steps:
                break

            step = migration.steps[step_id]

            # If already accepted or rolled back, skip
            if step.state in (StepState.ACCEPTED, StepState.SKIPPED):
                continue

            # Invariant: Predecessor steps must be ACCEPTED
            if not graph.is_step_ready_to_execute(step_id):
                step.state = StepState.BLOCKED
                migration.status = MigrationState.BLOCKED
                migration.unresolved_blockers.append(
                    f"Predecessor steps for '{step_id}' are not accepted."
                )
                self.store.save_migration(migration)
                return migration

            # Step Governance: Security & Budget
            sec_step_ok, sec_step_msg = self.governance.evaluate_security_gate(
                migration, step=step, human_approval_token=human_approval_token
            )
            if not sec_step_ok:
                self.store.save_migration(migration)
                return migration

            try:
                self.governance.check_and_consume_budget(migration, step)
            except BudgetExceededError as e:
                self.store.save_migration(migration)
                return migration

            # Pre-step Checkpoint
            chk = self.checkpoint_mgr.create_checkpoint(migration, current_step_id=step_id)
            self.store.save_checkpoint(chk)

            # Execution with simulated failure support
            def wrapped_mutation_fn(s: MigrationStep) -> Tuple[bool, str, Dict[str, Any]]:
                if simulate_failure_step_id and s.step_id == simulate_failure_step_id:
                    return False, f"Injected simulated failure on step {s.step_id}", {}
                if mutation_fn:
                    return mutation_fn(s)
                return True, "Executed successfully", {}

            exec_ok, exec_msg = self.executor.execute_step(
                step=step,
                migration=migration,
                mutation_fn=wrapped_mutation_fn,
                verification_fn=verification_fn,
            )

            if not exec_ok:
                # Handle failure: Attempt retry if configured
                if step.retry_count < step.max_retries:
                    step.retry_count += 1
                    # Retry once
                    exec_ok, exec_msg = self.executor.execute_step(
                        step=step,
                        migration=migration,
                        mutation_fn=wrapped_mutation_fn,
                        verification_fn=verification_fn,
                    )

                if not exec_ok:
                    # Rollback or abort
                    rollback_ok, rollback_msg = self.compensation_orch.execute_compensation(
                        migration, compensation_fn=compensation_fn
                    )
                    self.store.save_migration(migration)
                    return migration

            # Step acceptance: APPLIED -> LOCALLY_VERIFIED -> ACCEPTED
            self.executor.accept_step(step, migration)
            steps_executed += 1

            # Post-step Checkpoint
            post_chk = self.checkpoint_mgr.create_checkpoint(migration, current_step_id=step_id)
            self.store.save_checkpoint(post_chk)

        # Stage 9: VERIFY FINAL STATE
        # If all steps are accepted, evaluate global invariants
        all_accepted = all(
            s.state in (StepState.ACCEPTED, StepState.SKIPPED)
            for s in migration.steps.values()
        )

        if all_accepted:
            ver_report = self.verifier.verify_global_invariants(
                migration=migration,
                behavior_drift_detected=behavior_drift_detected,
                build_errors_detected=build_errors_detected,
                test_failures_detected=test_failures_detected,
            )

            if ver_report.passed:
                migration.status = MigrationState.COMPLETED
                migration.completed_at = time.time()
                # Compute final provenance hash
                prov_str = f"{migration.migration_id}:{migration.status}:{len(migration.evidence_ledger)}"
                migration.provenance_hash = hashlib.sha256(prov_str.encode("utf-8")).hexdigest()
            else:
                migration.status = MigrationState.BLOCKED
                migration.unresolved_blockers.extend(ver_report.violations)
        else:
            if migration.status not in (MigrationState.BLOCKED, MigrationState.ROLLED_BACK, MigrationState.HUMAN_REVIEW_REQUIRED):
                migration.status = MigrationState.PARTIALLY_COMPLETED

        self.store.save_migration(migration)
        return migration

    def resume_migration(
        self,
        checkpoint_id: str,
        human_approval_token: Optional[str] = None,
    ) -> MacroMigration:
        """
        Resumes an interrupted migration from a persistent checkpoint.
        """
        checkpoint = self.store.load_checkpoint(checkpoint_id)
        if not checkpoint:
            raise MacroRefactoringError(f"Checkpoint '{checkpoint_id}' not found.")

        migration_id = checkpoint.migration_id
        migration = self.store.load_migration(migration_id)
        if not migration:
            raise MacroRefactoringError(f"Migration '{migration_id}' not found.")

        # Restore state
        self.checkpoint_mgr.restore_from_checkpoint(checkpoint, migration)

        # Continue execution
        return self.execute_migration(
            migration=migration,
            human_approval_token=human_approval_token,
        )

    def rollback_migration(
        self,
        migration: MacroMigration,
        compensation_fn: Optional[Callable[[str, str], Tuple[bool, str]]] = None,
    ) -> MacroMigration:
        """
        Manually triggers a safe backwards compensation rollback.
        """
        self.compensation_orch.execute_compensation(migration, compensation_fn=compensation_fn)
        self.store.save_migration(migration)
        return migration

    def replan_migration(
        self,
        migration: MacroMigration,
        newly_discovered_consumers: List[str],
        reason: str,
    ) -> MacroMigration:
        """
        Adapts the migration DAG when unexpected consumers or drift are observed.
        """
        self.replan_engine.replan_remaining_steps(migration, newly_discovered_consumers, reason)
        self.store.save_migration(migration)
        return migration
