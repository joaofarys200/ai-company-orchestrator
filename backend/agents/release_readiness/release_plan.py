"""
Release Plan DAG Module
Phase 70 — Autonomous Release Readiness & Production Governance

Constructs and manages the directed acyclic graph (DAG) of the release rollout.
Crucial invariant: Emits DEPLOYMENT_NOT_AVAILABLE explicitly if deployment
infrastructure is unavailable, rather than faking physical completion.
"""

from __future__ import annotations
import uuid
import time
from typing import Dict, Any, List, Optional
from .models import ReleasePlan, ReleasePlanStep, ReleaseGateDecisionState


class ReleasePlanBuilder:
    """Constructs the canonical 10-phase release execution DAG."""

    STEPS_DEFINITION = [
        ("step-1-prepare", "PREPARE", []),
        ("step-2-verify-pre", "PRE_RELEASE_VERIFY", ["step-1-prepare"]),
        ("step-3-snapshot", "SNAPSHOT", ["step-2-verify-pre"]),
        ("step-4-deploy", "DEPLOY/START", ["step-3-snapshot"]),
        ("step-5-healthcheck", "HEALTHCHECK", ["step-4-deploy"]),
        ("step-6-canary", "CANARY", ["step-5-healthcheck"]),
        ("step-7-observe", "OBSERVE", ["step-6-canary"]),
        ("step-8-verify-post", "VERIFY", ["step-7-observe"]),
        ("step-9-promote", "PROMOTE", ["step-8-verify-post"]),
        ("step-10-rollback", "ROLLBACK", ["step-5-healthcheck", "step-6-canary", "step-7-observe", "step-8-verify-post"])
    ]

    @classmethod
    def build_plan(
        cls,
        candidate_id: str,
        deployment_available: bool = False,
        plan_id: Optional[str] = None
    ) -> ReleasePlan:
        """Constructs the ReleasePlan DAG."""
        p_id = plan_id or f"plan-{uuid.uuid4().hex[:12]}"
        steps: List[ReleasePlanStep] = []

        for step_id, name, deps in cls.STEPS_DEFINITION:
            steps.append(ReleasePlanStep(
                step_id=step_id,
                name=name,
                status="PENDING",
                depends_on=deps,
                metadata={"deployment_available": deployment_available}
            ))

        return ReleasePlan(
            plan_id=p_id,
            candidate_id=candidate_id,
            steps=steps,
            current_step_index=0,
            status="PENDING",
            deployment_available=deployment_available
        )

    @classmethod
    def execute_plan_stage(
        cls,
        plan: ReleasePlan,
        simulate_failure_at_step: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Steps through the DAG. If deployment_available is False when hitting
        step-4-deploy, halts immediately with DEPLOYMENT_NOT_AVAILABLE.
        """
        for i, step in enumerate(plan.steps):
            if step.name == "ROLLBACK":
                continue  # Handled on failure branch

            if step.step_id == simulate_failure_at_step:
                step.status = "FAILED"
                plan.status = "FAILED"
                # Trigger rollback step
                for s in plan.steps:
                    if s.name == "ROLLBACK":
                        s.status = "COMPLETED"
                        plan.status = "ROLLED_BACK"
                return {
                    "outcome": "ROLLED_BACK",
                    "failed_step": step.name,
                    "plan": plan.to_dict()
                }

            if step.name == "DEPLOY/START" and not plan.deployment_available:
                step.status = "BLOCKED"
                plan.status = "DEPLOYMENT_NOT_AVAILABLE"
                return {
                    "outcome": ReleaseGateDecisionState.DEPLOYMENT_NOT_AVAILABLE.value,
                    "reason": "Physical deployment target unavailable; cannot simulate live promotion",
                    "plan": plan.to_dict()
                }

            step.status = "COMPLETED"
            plan.current_step_index = i + 1

        plan.status = "COMPLETED"
        return {
            "outcome": "PROMOTED",
            "plan": plan.to_dict()
        }
