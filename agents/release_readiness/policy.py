"""
Release Policy Engine
Phase 70 — Autonomous Release Readiness & Production Governance

Defines governance policy levels and evaluates policy compliance.
Crucial invariant: Sentinel security authority is invariant and cannot be reduced in any policy.
"""

from __future__ import annotations
from enum import Enum
from typing import Dict, Any, List
from .models import ReleaseGateDecisionState, ReleaseBlocker, BlockerCategory


class ReleasePolicyLevel(str, Enum):
    """Governance rigor policies."""
    STRICT = "STRICT"
    GOVERNED = "GOVERNED"
    LENIENT = "LENIENT"


class ReleasePolicyEngine:
    """Evaluates release evaluations against configured governance policies."""

    def __init__(self, policy_level: ReleasePolicyLevel = ReleasePolicyLevel.GOVERNED):
        self.policy_level = policy_level

    def evaluate_decision_state(
        self,
        blockers: List[ReleaseBlocker],
        human_review_required: bool,
        deployment_available: bool,
        has_risks: bool = False
    ) -> ReleaseGateDecisionState:
        """
        Calculates the canonical ReleaseGateDecisionState:
        - RELEASE_READY
        - RELEASE_READY_WITH_RISK
        - HUMAN_REVIEW
        - NOT_READY
        - BLOCKED
        - DEPLOYMENT_NOT_AVAILABLE
        - INSUFFICIENT_EVIDENCE
        """
        # Hard blockers always block release across all policies
        if blockers:
            # Check if missing evidence is the sole blocker
            if all(b.category == BlockerCategory.MISSING_MANDATORY_EVIDENCE for b in blockers):
                return ReleaseGateDecisionState.INSUFFICIENT_EVIDENCE
            return ReleaseGateDecisionState.BLOCKED

        # If human review is triggered
        if human_review_required:
            return ReleaseGateDecisionState.HUMAN_REVIEW

        # If physical deployment is unavailable
        if not deployment_available:
            return ReleaseGateDecisionState.DEPLOYMENT_NOT_AVAILABLE

        # If strict policy and any risk present
        if self.policy_level == ReleasePolicyLevel.STRICT and has_risks:
            return ReleaseGateDecisionState.HUMAN_REVIEW

        # If risks present under GOVERNED/LENIENT
        if has_risks:
            return ReleaseGateDecisionState.RELEASE_READY_WITH_RISK

        return ReleaseGateDecisionState.RELEASE_READY
