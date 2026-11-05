"""
JARVIS OS — Phase 73: Autonomous Macro-Refactoring Engine
Module: planner.py
Decomposes large architectural refactoring objectives into bounded, ordered, verifiable migration DAGs.
Supports compatibility shims, dual paths, staged consumer migrations, cutover, and cleanup.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any, Dict, List, Optional

from .graph import MigrationGraph
from .models import (
    MacroMigration,
    MigrationState,
    MigrationStep,
    MigrationStepType,
    StepState,
)


class MacroRefactoringPlanner:
    """
    Decomposes high-blast-radius architectural objectives (>15 nodes)
    into structured, safe, and individually verifiable migration steps.
    """

    def plan_macro_migration(
        self,
        objective: str,
        project_id: str,
        producers: List[str],
        consumers: List[str],
        affected_files: List[str],
        is_security_sensitive: bool = False,
        has_persistence_boundary: bool = False,
        custom_steps: Optional[List[MigrationStep]] = None,
        max_nodes_per_step: int = 15,
    ) -> MacroMigration:
        migration_id = f"mig_{uuid.uuid4().hex[:8]}"
        total_nodes = len(producers) + len(consumers) + len(affected_files)

        if custom_steps:
            # Custom migration topology
            steps_dict = {s.step_id: s for s in custom_steps}
            graph = MigrationGraph(steps_dict)
            order = graph.topological_sort()

            return MacroMigration(
                migration_id=migration_id,
                objective=objective,
                project_id=project_id,
                status=MigrationState.PLANNED,
                blast_radius_nodes=total_nodes,
                steps=steps_dict,
                execution_order=order,
                target_invariants=[
                    "zero_build_errors",
                    "all_tests_pass",
                    "contract_hashes_match_or_compatible",
                    "zero_behavioral_drift",
                ],
                risk_score=0.3 if not is_security_sensitive else 0.8,
                metadata={"is_security_sensitive": is_security_sensitive, "has_persistence_boundary": has_persistence_boundary},
            )

        # Standard Staged Decomposition for Cross-System Transformations
        steps: List[MigrationStep] = []

        # 1. PREPARATION
        s1 = MigrationStep(
            step_id=f"{migration_id}_s1_prep",
            step_type=MigrationStepType.PREPARATION,
            title="Baseline Snapshot & Invariant Probes",
            description="Capture pre-migration git/file snapshot, verify baseline tests pass, setup telemetry.",
            affected_files=[],
            dependencies=[],
            state=StepState.READY,
            preconditions=["repository_clean", "baseline_tests_pass"],
            postconditions=["baseline_snapshot_saved"],
            verification_gates=["verify_baseline_snapshot"],
            compensation_action="restore_pre_migration_snapshot",
        )
        steps.append(s1)
        prev_dep = s1.step_id

        # 2. COMPATIBILITY LAYER
        s2 = MigrationStep(
            step_id=f"{migration_id}_s2_compat",
            step_type=MigrationStepType.COMPATIBILITY_LAYER,
            title="Deploy Non-Breaking Compatibility Interface / Shim",
            description="Introduce new modular interface alongside existing legacy API to prevent breaking consumers.",
            affected_files=producers[:5] if producers else affected_files[:2],
            dependencies=[prev_dep],
            state=StepState.PENDING,
            preconditions=["baseline_snapshot_saved"],
            postconditions=["shim_available_and_importable"],
            verification_gates=["verify_shim_compiles", "verify_legacy_contracts_unbroken"],
            compensation_action="revert_shim_creation",
        )
        steps.append(s2)
        prev_dep = s2.step_id

        # 3. CONSUMER MIGRATION (Staged in batches if > max_nodes_per_step)
        consumer_batches: List[List[str]] = []
        batch_size = max(1, max_nodes_per_step - 2)
        for i in range(0, len(consumers), batch_size):
            consumer_batches.append(consumers[i:i + batch_size])

        if not consumer_batches:
            consumer_batches = [["default_consumer"]]

        for idx, batch in enumerate(consumer_batches, start=1):
            s_consumer = MigrationStep(
                step_id=f"{migration_id}_s3_consumer_batch_{idx}",
                step_type=MigrationStepType.CONSUMER_MIGRATION,
                title=f"Migrate Consumer Batch {idx} ({len(batch)} consumers)",
                description=f"Rewire consumers to target new interface: {', '.join(batch[:3])}",
                affected_files=batch,
                dependencies=[prev_dep],
                state=StepState.PENDING,
                preconditions=["shim_available_and_importable"],
                postconditions=[f"batch_{idx}_migrated"],
                verification_gates=["verify_batch_consumers_pass_tests"],
                compensation_action=f"revert_consumer_batch_{idx}",
            )
            steps.append(s_consumer)
            prev_dep = s_consumer.step_id

        # 4. DUAL_PATH / SHADOW VALIDATION
        s4 = MigrationStep(
            step_id=f"{migration_id}_s4_dual_path",
            step_type=MigrationStepType.DUAL_PATH,
            title="Dual-Path Semantic Equivalence Verification",
            description="Verify that new and legacy implementations produce identical behavioral proof outcomes.",
            affected_files=[],
            dependencies=[prev_dep],
            state=StepState.PENDING,
            preconditions=["all_consumers_rewired"],
            postconditions=["dual_path_verified"],
            verification_gates=["verify_semantic_contract_equivalence"],
            compensation_action="disable_dual_path",
        )
        steps.append(s4)
        prev_dep = s4.step_id

        # 5. CUTOVER
        s5 = MigrationStep(
            step_id=f"{migration_id}_s5_cutover",
            step_type=MigrationStepType.CUTOVER,
            title="Complete Traffic & Binding Cutover",
            description="Make the new architectural component authoritative across all entry points.",
            affected_files=producers,
            dependencies=[prev_dep],
            state=StepState.PENDING,
            preconditions=["dual_path_verified"],
            postconditions=["cutover_authoritative"],
            verification_gates=["verify_full_system_integration_tests"],
            compensation_action="fallback_cutover_to_shim",
        )
        steps.append(s5)
        prev_dep = s5.step_id

        # 6. OBSERVATION
        s6 = MigrationStep(
            step_id=f"{migration_id}_s6_obs",
            step_type=MigrationStepType.OBSERVATION,
            title="Post-Cutover Invariant Audit & Soak Check",
            description="Audit architecture graph to confirm decoupled SCCs and zero behavioral regression.",
            affected_files=[],
            dependencies=[prev_dep],
            state=StepState.PENDING,
            preconditions=["cutover_authoritative"],
            postconditions=["invariants_confirmed"],
            verification_gates=["verify_zero_behavioral_drift", "verify_latency_budget"],
            compensation_action="none_read_only",
        )
        steps.append(s6)
        prev_dep = s6.step_id

        # 7. CLEANUP
        s7 = MigrationStep(
            step_id=f"{migration_id}_s7_clean",
            step_type=MigrationStepType.CLEANUP,
            title="Decommission Legacy Implementation & Deprecated Shims",
            description="Safely delete old unreferenced classes and transition adapters.",
            affected_files=producers[:2] if producers else [],
            dependencies=[prev_dep],
            state=StepState.PENDING,
            preconditions=["invariants_confirmed"],
            postconditions=["legacy_code_purged"],
            verification_gates=["verify_clean_codebase_build", "verify_no_dangling_references"],
            compensation_action="restore_legacy_files_from_snapshot",
        )
        steps.append(s7)

        steps_dict = {s.step_id: s for s in steps}
        graph = MigrationGraph(steps_dict)
        execution_order = graph.topological_sort()

        risk = 0.25
        if total_nodes > 15:
            risk += 0.2
        if is_security_sensitive:
            risk += 0.5
        if has_persistence_boundary:
            risk += 0.15

        return MacroMigration(
            migration_id=migration_id,
            objective=objective,
            project_id=project_id,
            status=MigrationState.PLANNED,
            blast_radius_nodes=total_nodes,
            steps=steps_dict,
            execution_order=execution_order,
            target_invariants=[
                "zero_build_errors",
                "all_tests_pass",
                "contract_hashes_match_or_compatible",
                "zero_behavioral_drift",
            ],
            risk_score=round(min(1.0, risk), 3),
            metadata={"is_security_sensitive": is_security_sensitive, "has_persistence_boundary": has_persistence_boundary},
        )
