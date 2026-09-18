"""
JARVIS OS — Phase 62: Continuous Verification & Autonomous Regression Governance
Module: planner.py
Verification Planner converting VerificationSurface and Policy into an actionable VerificationPlan.
Enforces Central Invariants:
NO_CHANGE -> NO_VERIFICATION
CHANGE_WITH_NO_IMPACT_EVIDENCE -> UNCERTAIN
CHANGE_WITH_IMPACT -> VERIFICATION_REQUIRED
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional

from .models import VerificationPolicy, VerificationPolicyName, VerificationSurface
from .policy import VerificationPolicyEngine


@dataclass
class VerificationPlan:
    plan_id: str
    surface: VerificationSurface
    policy: VerificationPolicy
    verification_required: bool
    status_signal: str  # NO_VERIFICATION, UNCERTAIN, VERIFICATION_REQUIRED
    target_requirements: List[str] = field(default_factory=list)
    budget_tests: int = 50
    budget_runtime_s: float = 60.0
    browser_verification_required: bool = False
    synthesis_permitted: bool = True
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "surface": self.surface.to_dict(),
            "policy": self.policy.to_dict(),
            "verification_required": self.verification_required,
            "status_signal": self.status_signal,
            "target_requirements": self.target_requirements,
            "budget_tests": self.budget_tests,
            "budget_runtime_s": self.budget_runtime_s,
            "browser_verification_required": self.browser_verification_required,
            "synthesis_permitted": self.synthesis_permitted,
            "created_at": self.created_at,
        }


class ContinuousVerificationPlanner:
    """Plans verification scope, budgets, and requirements based on surface and policy."""

    def __init__(self, default_policy: Optional[VerificationPolicy] = None) -> None:
        self.default_policy = default_policy or VerificationPolicyEngine.get_policy(VerificationPolicyName.STANDARD)

    def create_plan(
        self,
        surface: VerificationSurface,
        policy: Optional[VerificationPolicy] = None,
        has_change: bool = True,
    ) -> VerificationPlan:
        active_policy = policy or self.default_policy
        plan_id = f"vplan_{int(time.time() * 1000)}"

        # Central Invariant 1: NO_CHANGE -> NO_VERIFICATION
        if not has_change or (not surface.affected_files and not surface.affected_symbols):
            return VerificationPlan(
                plan_id=plan_id,
                surface=surface,
                policy=active_policy,
                verification_required=False,
                status_signal="NO_VERIFICATION",
                target_requirements=[],
                budget_tests=0,
                budget_runtime_s=0.0,
                browser_verification_required=False,
                synthesis_permitted=False,
            )

        # Central Invariant 2: CHANGE_WITH_NO_IMPACT_EVIDENCE -> UNCERTAIN
        if surface.uncertainty >= 0.8 or (len(surface.affected_files) > 0 and surface.uncertainty > 0.6 and not surface.affected_symbols and not surface.affected_contracts):
            return VerificationPlan(
                plan_id=plan_id,
                surface=surface,
                policy=active_policy,
                verification_required=True,
                status_signal="UNCERTAIN",
                target_requirements=["DYNAMIC_BOUNDARY_VERIFICATION", "REFLECTION_AUDIT"],
                budget_tests=min(15, active_policy.max_tests),
                budget_runtime_s=min(20.0, active_policy.max_runtime),
                browser_verification_required=len(surface.browser_surfaces) > 0,
                synthesis_permitted=active_policy.allow_synthesis,
            )

        # Central Invariant 3: CHANGE_WITH_IMPACT -> VERIFICATION_REQUIRED
        requirements: List[str] = []
        if surface.affected_symbols:
            requirements.append("SYMBOL_PRECISION_TEST")
        if surface.affected_contracts:
            requirements.append("CONTRACT_CONFORMANCE_TEST")
        if surface.affected_consumers:
            requirements.append("CONSUMER_REGRESSION_TEST")
        if surface.affected_behaviors:
            requirements.append("BEHAVIORAL_INVARIANT_TEST")
        if surface.browser_surfaces and active_policy.max_browser_tests > 0:
            requirements.append("BROWSER_SURFACE_TEST")
        if surface.risk_level in ("HIGH", "CRITICAL"):
            requirements.append("HIGH_RISK_DEFENSIVE_TEST")

        browser_required = bool(surface.browser_surfaces and active_policy.max_browser_tests > 0)

        return VerificationPlan(
            plan_id=plan_id,
            surface=surface,
            policy=active_policy,
            verification_required=True,
            status_signal="VERIFICATION_REQUIRED",
            target_requirements=requirements,
            budget_tests=active_policy.max_tests,
            budget_runtime_s=active_policy.max_runtime,
            browser_verification_required=browser_required,
            synthesis_permitted=active_policy.allow_synthesis,
        )
