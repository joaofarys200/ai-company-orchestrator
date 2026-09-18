"""
JARVIS OS — Phase 65: Safe Self-Modification & Transactional Architecture Implementation
Module: plan.py
Translates approved architectural decisions and migration DAGs into verified,
atomic SelfModificationPlans with ordered steps, preconditions, postconditions,
rollback actions, and convergence budgets.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional

from .models import PlanStep, SelfModificationPlan


class SelfModificationPlanner:
    """Compiles verified execution plans from Phase 64 governance decisions."""

    def create_plan(
        self,
        governance_decision: Dict[str, Any],
        migration_plan: Optional[Dict[str, Any]] = None,
        affected_surface: Optional[Dict[str, Any]] = None,
        contract_analysis: Optional[Dict[str, Any]] = None,
        behavior_analysis: Optional[Dict[str, Any]] = None,
        verification_plan: Optional[Dict[str, Any]] = None,
        budgets: Optional[Dict[str, Any]] = None,
    ) -> SelfModificationPlan:
        """Construct an atomic, sequenced SelfModificationPlan."""
        decision_id = str(governance_decision.get("decision_id", f"dec_{int(time.time())}"))
        problem_id = str(governance_decision.get("problem_id", "prob_unknown"))
        alternative_id = str(governance_decision.get("alternative_id", "alt_unknown"))

        affected_files = list(affected_surface.get("affected_files", [])) if affected_surface else []
        affected_symbols = list(affected_surface.get("affected_symbols", [])) if affected_surface else []

        # Steps derived from migration_plan DAG or synthesized
        steps: List[PlanStep] = []
        if migration_plan and "steps" in migration_plan:
            for raw_step in migration_plan["steps"]:
                steps.append(
                    PlanStep(
                        step_id=raw_step.get("step_id", f"step_{len(steps) + 1}"),
                        step_type=raw_step.get("step_type", "COMPATIBILITY_LAYER"),
                        title=raw_step.get("title", "Migration Step"),
                        description=raw_step.get("description", ""),
                        target_files=affected_files,
                        target_symbols=affected_symbols,
                        preconditions=[f"Preflight and snapshot verified for {raw_step.get('step_id')}"],
                        expected_changes=[f"Apply safe delta for {raw_step.get('step_id')}"],
                        postconditions=["Syntax and contract non-breaking invariants held"],
                        rollback_action=raw_step.get("rollback_action", "Restore snapshot from checkpoint"),
                        is_reversibility_supported=raw_step.get("is_reversibility_supported", True),
                        verification_gates=raw_step.get("verification_gates", ["syntax", "test"]),
                    )
                )

        if not steps:
            # Default 3-stage minimal atomic sequence
            steps = [
                PlanStep(
                    step_id="step_01_prepare_interfaces",
                    step_type="COMPATIBILITY_LAYER",
                    title="Prepare and inject non-breaking interfaces",
                    description="Introduce boundary abstractions without altering public consumers.",
                    target_files=affected_files,
                    target_symbols=affected_symbols,
                    preconditions=["Workspace clean", "Snapshot confirmed"],
                    expected_changes=["Add interface shims"],
                    postconditions=["Existing tests pass 100%"],
                    rollback_action="Revert interface changes",
                    is_reversibility_supported=True,
                    verification_gates=["syntax", "unit_test"],
                ),
                PlanStep(
                    step_id="step_02_atomic_implementation",
                    step_type="CUTOVER",
                    title="Atomic modular refactor",
                    description="Route logic through extracted boundaries.",
                    target_files=affected_files,
                    target_symbols=affected_symbols,
                    preconditions=["Step 1 verified"],
                    expected_changes=["Refactor targeted module"],
                    postconditions=["Contract non-breaking, behavior preserved"],
                    rollback_action="Revert to Step 1 checkpoint",
                    is_reversibility_supported=True,
                    verification_gates=["build", "contract", "behavior"],
                ),
                PlanStep(
                    step_id="step_03_verification_cleanup",
                    step_type="CLEANUP",
                    title="Validate and cleanup legacy shims",
                    description="Run full continuous verification and finalize state.",
                    target_files=affected_files,
                    target_symbols=affected_symbols,
                    preconditions=["Step 2 verified"],
                    expected_changes=["Remove deprecated shims if applicable"],
                    postconditions=["Architecture rescan confirms improvement"],
                    rollback_action="Revert to Step 2 checkpoint",
                    is_reversibility_supported=True,
                    verification_gates=["full_verification", "rescan"],
                ),
            ]

        expected_contract_changes = contract_analysis.get("affected_contracts", []) if contract_analysis else []
        expected_behavior_changes = behavior_analysis.get("observed_properties", []) if behavior_analysis else []
        expected_tests = verification_plan.get("required_tests", []) if verification_plan else []

        plan_id = f"plan_{hashlib.sha256(f'{decision_id}:{problem_id}:{time.time()}'.encode()).hexdigest()[:12]}"

        plan = SelfModificationPlan(
            plan_id=plan_id,
            governance_decision_id=decision_id,
            problem_id=problem_id,
            alternative_id=alternative_id,
            ordered_steps=steps,
            affected_files=affected_files,
            affected_symbols=affected_symbols,
            expected_contract_changes=expected_contract_changes,
            expected_behavior_changes=expected_behavior_changes,
            expected_tests=expected_tests,
            checkpoints=[f"cp_{s.step_id}" for s in steps],
            rollback_points=[f"rb_{s.step_id}" for s in steps],
            budgets=budgets or {
                "max_iterations": 3,
                "max_patches": 10,
                "max_retries": 2,
                "max_wall_time_sec": 300,
                "max_memory_mb": 512,
            },
            security_policy="STRICT_SENTINEL",
            verification_policy="CONTINUOUS_VERIFICATION_REQUIRED",
        )
        plan.plan_hash = plan.compute_hash()
        return plan
