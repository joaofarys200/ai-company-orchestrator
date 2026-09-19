"""
Canary Policy Module
Phase 70 — Autonomous Release Readiness & Production Governance

Evaluates canary routing and progressive delivery policies.
Crucial invariant: Never presents SIMULATED canary execution as REAL.
"""

from __future__ import annotations
from typing import Dict, Any, List
from .models import CanaryPolicyType, BlockerCategory, ReleaseBlocker


class CanaryEvaluator:
    """Evaluates canary delivery safety, traffic routing, and rollout verification."""

    @classmethod
    def evaluate(
        cls,
        canary_config: Dict[str, Any],
        runtime_available: bool = False
    ) -> Dict[str, Any]:
        """
        Supports: DISABLED, SIMULATED, LOCAL, REAL.
        Rule: Real canary requires real runtime. Simulated must not masquerade as real.
        """
        policy_str = canary_config.get("policy", CanaryPolicyType.DISABLED.value)
        try:
            policy = CanaryPolicyType(policy_str)
        except ValueError:
            policy = CanaryPolicyType.DISABLED

        traffic_pct = float(canary_config.get("traffic_pct", 0.0))
        error_threshold_pct = float(canary_config.get("error_threshold_pct", 1.0))
        duration_seconds = float(canary_config.get("duration_seconds", 300.0))
        claimed_real = canary_config.get("claimed_real", False)

        blockers: List[ReleaseBlocker] = []
        requires_human_review = False
        review_reasons: List[str] = []

        # Anti-deception invariant: claiming REAL when runtime is unavailable or mode is SIMULATED
        if policy == CanaryPolicyType.REAL and not runtime_available:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-canary-simulated-claimed-real",
                category=BlockerCategory.MISSING_MANDATORY_EVIDENCE,
                description="REAL canary policy requested but physical runtime environment is unavailable",
                evidence="Cannot execute real canary traffic routing without live production nodes."
            ))

        if claimed_real and policy == CanaryPolicyType.SIMULATED:
            blockers.append(ReleaseBlocker(
                blocker_id="blocker-canary-policy-deception",
                category=BlockerCategory.QUALITY_GATE_BLOCKED,
                description="Canary configuration falsely labeled SIMULATED execution as REAL",
                evidence="Epistemic integrity violation: simulation masquerading as physical verification."
            ))

        if policy == CanaryPolicyType.REAL:
            if traffic_pct > 25.0:
                requires_human_review = True
                review_reasons.append(f"Canary initial traffic percentage is aggressive ({traffic_pct}%)")

        if policy == CanaryPolicyType.SIMULATED:
            requires_human_review = True
            review_reasons.append("Canary verification is purely simulated; live production verification unperformed")

        return {
            "policy": policy.value,
            "traffic_pct": traffic_pct,
            "error_threshold_pct": error_threshold_pct,
            "duration_seconds": duration_seconds,
            "runtime_available": runtime_available,
            "is_real_execution": (policy == CanaryPolicyType.REAL and runtime_available),
            "blockers": blockers,
            "requires_human_review": requires_human_review,
            "review_reasons": review_reasons
        }
