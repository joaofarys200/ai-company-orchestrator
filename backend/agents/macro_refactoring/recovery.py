"""
JARVIS OS — Phase 73: Autonomous Macro-Refactoring Engine
Module: recovery.py
Durable checkpointing, corruption detection, crash recovery resumption,
backwards compensation orchestrator, and adaptive replanning engine.
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from .graph import MigrationGraph
from .models import (
    CheckpointCorruptError,
    CompensationPlan,
    MacroMigration,
    MigrationCheckpoint,
    MigrationState,
    MigrationStep,
    StepState,
)


class CheckpointManager:
    """
    Creates, stores, verifies, and restores migration checkpoints.
    Detects tampering or corrupted checkpoints via SHA256 checksum validation.
    """

    def create_checkpoint(
        self,
        migration: MacroMigration,
        current_step_id: Optional[str] = None,
    ) -> MigrationCheckpoint:
        """
        Creates a new immutable checkpoint of the current migration state.
        """
        seq = len(migration.checkpoints) + 1
        chk_id = f"chk_{migration.migration_id}_{seq:04d}"

        # Serialize state snapshot
        state_dict = migration.to_dict()
        # Exclude checkpoints from snapshot to avoid infinite recursion
        state_dict.pop("checkpoints", None)

        raw_bytes = json.dumps(state_dict, sort_keys=True).encode("utf-8")
        checksum = hashlib.sha256(raw_bytes).hexdigest()

        chk = MigrationCheckpoint(
            checkpoint_id=chk_id,
            sequence=seq,
            migration_id=migration.migration_id,
            current_step_id=current_step_id,
            state_snapshot=state_dict,
            checksum=checksum,
            created_at=time.time(),
        )
        migration.checkpoints.append(chk)
        return chk

    def verify_checkpoint(self, checkpoint: MigrationCheckpoint) -> bool:
        """
        Validates the checksum of a checkpoint against its state snapshot.
        """
        raw_bytes = json.dumps(checkpoint.state_snapshot, sort_keys=True).encode("utf-8")
        computed_hash = hashlib.sha256(raw_bytes).hexdigest()
        return computed_hash == checkpoint.checksum

    def restore_from_checkpoint(
        self,
        checkpoint: MigrationCheckpoint,
        migration: MacroMigration,
    ) -> MacroMigration:
        """
        Restores migration state from a verified checkpoint.
        Raises CheckpointCorruptError if checksum does not match.
        """
        if not self.verify_checkpoint(checkpoint):
            raise CheckpointCorruptError(
                f"Checkpoint '{checkpoint.checkpoint_id}' is corrupted or tampered! "
                f"Checksum mismatch."
            )

        snap = checkpoint.state_snapshot
        migration.status = MigrationState(snap.get("status", MigrationState.EXECUTING.value))
        migration.current_step_index = snap.get("current_step_index", 0)
        migration.blast_radius_nodes = snap.get("blast_radius_nodes", migration.blast_radius_nodes)
        migration.consumed_budget = snap.get("consumed_budget", migration.consumed_budget)

        # Restore step states
        steps_data = snap.get("steps", {})
        for s_id, s_data in steps_data.items():
            if s_id in migration.steps:
                migration.steps[s_id].state = StepState(s_data.get("state", StepState.PENDING.value))
                migration.steps[s_id].retry_count = s_data.get("retry_count", 0)
                migration.steps[s_id].error = s_data.get("error")

        return migration


class CompensationOrchestrator:
    """
    Builds and executes backwards compensation plans when a step or invariant fails.
    Reverts accepted steps in reverse topological order.
    """

    def build_compensation_plan(self, migration: MacroMigration) -> CompensationPlan:
        """
        Builds a reverse topological rollback plan for all currently accepted steps.
        Enforces that steps marked irreversible block automated rollback.
        """
        plan_id = f"cmp_plan_{uuid.uuid4().hex[:8]}"

        # Find all accepted steps
        accepted_ids = [
            s_id for s_id, s in migration.steps.items()
            if s.state in (StepState.ACCEPTED, StepState.LOCALLY_VERIFIED, StepState.APPLIED)
        ]

        if not accepted_ids:
            return CompensationPlan(
                plan_id=plan_id,
                migration_id=migration.migration_id,
                steps_to_revert=[],
                rollback_actions={},
                is_safe=True,
            )

        # Order them in reverse topological order based on migration.execution_order
        ordered_revert: List[str] = []
        for s_id in reversed(migration.execution_order):
            if s_id in accepted_ids:
                ordered_revert.append(s_id)

        rollback_actions: Dict[str, str] = {}
        for s_id in ordered_revert:
            step = migration.steps[s_id]
            if step.metadata.get("is_irreversible"):
                return CompensationPlan(
                    plan_id=plan_id,
                    migration_id=migration.migration_id,
                    steps_to_revert=ordered_revert,
                    rollback_actions=rollback_actions,
                    is_safe=False,
                    blocking_reason=f"Step '{s_id}' involves irreversible mutations. Automated rollback unsafe.",
                )
            action = step.compensation_action or f"revert_{s_id}"
            rollback_actions[s_id] = action

        return CompensationPlan(
            plan_id=plan_id,
            migration_id=migration.migration_id,
            steps_to_revert=ordered_revert,
            rollback_actions=rollback_actions,
            is_safe=True,
        )

    def execute_compensation(
        self,
        migration: MacroMigration,
        compensation_fn: Optional[Callable[[str, str], Tuple[bool, str]]] = None,
    ) -> Tuple[bool, str]:
        """
        Executes rollback in reverse topological order.
        Verifies that all steps are restored to ROLLED_BACK.
        """
        plan = self.build_compensation_plan(migration)
        if not plan.is_safe:
            migration.status = MigrationState.BLOCKED
            migration.unresolved_blockers.append(plan.blocking_reason or "Unsafe compensation plan")
            return False, f"Compensation aborted: {plan.blocking_reason}"

        migration.status = MigrationState.ROLLING_BACK

        for s_id in plan.steps_to_revert:
            action = plan.rollback_actions.get(s_id, "")
            if compensation_fn:
                comp_ok, comp_msg = compensation_fn(s_id, action)
                if not comp_ok:
                    migration.status = MigrationState.BLOCKED
                    err = f"Failed to compensate step '{s_id}' using action '{action}': {comp_msg}"
                    migration.unresolved_blockers.append(err)
                    return False, err

            migration.steps[s_id].state = StepState.ROLLED_BACK

        migration.status = MigrationState.ROLLED_BACK
        return True, f"Successfully rolled back {len(plan.steps_to_revert)} steps in reverse topological order."


class AdaptiveReplanEngine:
    """
    Dynamically recalculates the remaining migration DAG when architectural drift,
    new consumers, or interface changes are observed during execution.
    """

    def replan_remaining_steps(
        self,
        migration: MacroMigration,
        newly_discovered_consumers: List[str],
        reason: str,
    ) -> MacroMigration:
        """
        Preserves accepted steps.
        Replaces remaining consumer migration steps with newly batched steps.
        Reconstructs the DAG and validates it.
        """
        # Find which steps are already accepted
        accepted_step_ids = {
            s_id for s_id, s in migration.steps.items()
            if s.state == StepState.ACCEPTED
        }

        # Keep accepted steps and prep/compat if accepted
        kept_steps: Dict[str, MigrationStep] = {
            s_id: s for s_id, s in migration.steps.items()
            if s_id in accepted_step_ids
        }

        # Identify latest accepted step as the new anchor dependency
        last_accepted_id = None
        for s_id in migration.execution_order:
            if s_id in accepted_step_ids:
                last_accepted_id = s_id

        # Create new consumer migration step for newly discovered consumers
        new_step_id = f"{migration.migration_id}_replan_cons_{uuid.uuid4().hex[:6]}"
        new_step = MigrationStep(
            step_id=new_step_id,
            step_type=migration.steps[migration.execution_order[-1]].step_type,
            title=f"Adaptive Migration: {len(newly_discovered_consumers)} newly discovered consumers",
            description=f"Replanned due to drift: {reason}",
            affected_files=newly_discovered_consumers,
            dependencies=[last_accepted_id] if last_accepted_id else [],
            state=StepState.PENDING,
            verification_gates=["verify_batch_consumers_pass_tests"],
            compensation_action="revert_replanned_consumers",
        )
        kept_steps[new_step_id] = new_step

        # Add remaining un-executed post-consumer steps (cutover, obs, clean)
        for s_id in migration.execution_order:
            step = migration.steps[s_id]
            if s_id not in accepted_step_ids and step.step_type.value in ("CUTOVER", "OBSERVATION", "CLEANUP"):
                step_copy = copy.deepcopy(step)
                step_copy.dependencies = [new_step_id]
                step_copy.state = StepState.PENDING
                kept_steps[s_id] = step_copy
                new_step_id = s_id

        # Re-validate graph and compute new topological order
        graph = MigrationGraph(kept_steps)
        new_order = graph.topological_sort()

        migration.steps = kept_steps
        migration.execution_order = new_order
        migration.blast_radius_nodes += len(newly_discovered_consumers)
        migration.metadata["last_replan_reason"] = reason

        return migration
