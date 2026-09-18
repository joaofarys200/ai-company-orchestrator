"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Module: migration.py
Synthesizes staged DAG migration plans with explicit rollback actions at each step.

Pipeline DAG:
    PREPARATION -> COMPATIBILITY_LAYER -> DUAL_PATH -> VALIDATION -> CUTOVER
    -> OBSERVATION -> CLEANUP
"""

from __future__ import annotations

import hashlib
from typing import List

from .models import (
    AlternativeType,
    ArchitectureAlternative,
    ArchitectureMigrationPlan,
    MigrationStep,
    MigrationStepType,
    ReversibilityStatus,
)


class ArchitectureMigrationPlanner:
    """Constructs verifiable staged migration DAGs for architectural evolution."""

    def plan_migration(self, alternative: ArchitectureAlternative) -> ArchitectureMigrationPlan:
        plan_id = f"plan_{hashlib.sha256(alternative.alternative_id.encode()).hexdigest()[:8]}"

        if alternative.alternative_type == AlternativeType.KEEP_CURRENT:
            # Trivial observation plan
            step = MigrationStep(
                step_id=f"{plan_id}_step1",
                step_type=MigrationStepType.OBSERVATION,
                title="Continuous Architecture Invariant Monitoring",
                description="Monitor coupling metrics against regression alert thresholds.",
                dependencies=[],
                rollback_action="None required",
                is_reversibility_supported=True,
                verification_gates=["verify_no_external_contract_drift"],
            )
            return ArchitectureMigrationPlan(
                plan_id=plan_id,
                alternative_id=alternative.alternative_id,
                steps=[step],
                total_steps=1,
                reversibility_status=ReversibilityStatus.EASILY_REVERSIBLE,
                rollback_strategy="Zero-downtime rollback; no migration executed.",
                rollback_complexity="LOW",
                rollback_evidence="Verified baseline",
            )

        # Standard 7-stage DAG for architectural refactoring
        s1 = MigrationStep(
            step_id=f"{plan_id}_s1_prep",
            step_type=MigrationStepType.PREPARATION,
            title="Baseline Snapshot & Feature Flag Provisioning",
            description="Capture pre-migration state, configure dynamic routing flag, and establish telemetry.",
            dependencies=[],
            rollback_action="Disable feature flag and drop telemetry probes",
            is_reversibility_supported=True,
            verification_gates=["verify_baseline_snapshot", "verify_telemetry_health"],
        )

        s2 = MigrationStep(
            step_id=f"{plan_id}_s2_compat",
            step_type=MigrationStepType.COMPATIBILITY_LAYER,
            title="Deploy Compatibility Shim / Adapter Interface",
            description="Deploy non-breaking translation shim to preserve consumer contracts during evolution.",
            dependencies=[s1.step_id],
            rollback_action="De-register shim and restore legacy direct bindings",
            is_reversibility_supported=True,
            verification_gates=["verify_contract_non_breaking", "verify_consumer_smoke_test"],
        )

        s3 = MigrationStep(
            step_id=f"{plan_id}_s3_dual",
            step_type=MigrationStepType.DUAL_PATH,
            title="Dual-Execution / Shadow Traffic Shadowing",
            description="Route transactions to new architectural component in shadow mode alongside legacy path.",
            dependencies=[s2.step_id],
            rollback_action="Set shadow traffic sample rate to 0%",
            is_reversibility_supported=True,
            verification_gates=["verify_shadow_differential_accuracy"],
        )

        s4 = MigrationStep(
            step_id=f"{plan_id}_s4_valid",
            step_type=MigrationStepType.VALIDATION,
            title="Continuous Verification & Invariant Proof",
            description="Execute automated regression suite and verify absence of behavioral drift (F62).",
            dependencies=[s3.step_id],
            rollback_action="Revert shadow comparison listener",
            is_reversibility_supported=True,
            verification_gates=["verify_zero_behavioral_regressions", "verify_latency_budget"],
        )

        s5 = MigrationStep(
            step_id=f"{plan_id}_s5_cutover",
            step_type=MigrationStepType.CUTOVER,
            title="Incremental Canary Traffic Cutover",
            description="Incrementally promote new architectural component from 10% to 100% active traffic.",
            dependencies=[s4.step_id],
            rollback_action="Trigger automated canary rollback to 100% legacy path on anomaly",
            is_reversibility_supported=True,
            verification_gates=["verify_canary_error_rate_sub_0_1_percent"],
        )

        s6 = MigrationStep(
            step_id=f"{plan_id}_s6_obs",
            step_type=MigrationStepType.OBSERVATION,
            title="Post-Cutover Soak & Boundary Audit",
            description="Observe 24-hour soak period, confirming decoupled SCC metrics and zero memory leaks.",
            dependencies=[s5.step_id],
            rollback_action="Execute full blue-green cutback to legacy fallback container",
            is_reversibility_supported=True,
            verification_gates=["verify_soak_stability", "verify_scc_decoupling_realized"],
        )

        s7 = MigrationStep(
            step_id=f"{plan_id}_s7_clean",
            step_type=MigrationStepType.CLEANUP,
            title="Legacy Path Decommissioning & Contract Purge",
            description="Remove obsolete legacy classes, deprecated methods, and transitional adapters.",
            dependencies=[s6.step_id],
            rollback_action="Restore legacy source code from git commit checkpoint",
            is_reversibility_supported=True,
            verification_gates=["verify_clean_codebase_build", "verify_final_package_graph"],
        )

        steps = [s1, s2, s3, s4, s5, s6, s7]

        return ArchitectureMigrationPlan(
            plan_id=plan_id,
            alternative_id=alternative.alternative_id,
            steps=steps,
            total_steps=len(steps),
            reversibility_status=alternative.reversibility,
            rollback_strategy="Automated stage-by-stage compensation with instant feature flag fallback.",
            rollback_complexity="LOW" if alternative.reversibility == ReversibilityStatus.EASILY_REVERSIBLE else "MEDIUM",
            rollback_evidence="All 7 steps contain executable rollback actions with zero state loss.",
        )
