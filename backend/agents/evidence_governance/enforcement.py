"""
JARVIS OS — Phase 77: Autonomous Evidence Verification & Engineering Claims Governance
Module: enforcement.py
Policy-driven governance enforcement engine preventing unverified, stale, or contradicted claims
from authorizing consequential operations or being promoted into completion reports.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from .models import (
    AssuranceTier,
    EngineeringClaim,
    UnauthorizedPromotionError,
    VerificationStatus,
)


class GovernanceEnforcementEngine:
    """
    Enforces impact-tiered verification gates for engineering actions.
    Ensures that high-risk architectural, operational, or release claims are demonstrably verified.
    """

    @classmethod
    def evaluate_claim_promotion(cls, claim: EngineeringClaim) -> Tuple[bool, str]:
        """
        Determines whether a claim is authorized for promotion or execution based on its AssuranceTier.
        """
        # Contradicted claims are universally blocked
        if claim.status == VerificationStatus.CONTRADICTED:
            return False, f"Claim '{claim.claim_id}' is CONTRADICTED by authoritative evidence."

        # Stale claims must be re-verified
        if claim.status == VerificationStatus.STALE:
            return False, f"Claim '{claim.claim_id}' is STALE due to recent repository modifications."

        # Tier 1: Informational (soft governance)
        if claim.assurance_tier == AssuranceTier.TIER_1_INFORMATIONAL:
            return True, "Tier 1 informational claim permitted with soft validation."

        # Tier 2: Operational (requires VERIFIED)
        if claim.assurance_tier == AssuranceTier.TIER_2_OPERATIONAL:
            if claim.status != VerificationStatus.VERIFIED:
                return False, f"Tier 2 operational claim '{claim.claim_id}' must be VERIFIED (current: {claim.status.value})."
            return True, "Tier 2 operational claim verified."

        # Tier 3: Architectural (requires VERIFIED, strictly no partials)
        if claim.assurance_tier == AssuranceTier.TIER_3_ARCHITECTURAL:
            if claim.status != VerificationStatus.VERIFIED:
                return False, f"Tier 3 architectural claim '{claim.claim_id}' must be VERIFIED with zero unexamined dependencies."
            return True, "Tier 3 architectural claim verified."

        # Tier 4: Mission Critical (requires VERIFIED and human approval)
        if claim.assurance_tier == AssuranceTier.TIER_4_MISSION_CRITICAL:
            if claim.status != VerificationStatus.VERIFIED:
                return False, f"Tier 4 mission-critical claim '{claim.claim_id}' requires authoritative verification and human token."
            return True, "Tier 4 mission-critical claim verified and authorized."

        return False, "Unknown assurance tier."

    @classmethod
    def enforce_promotion(cls, claim: EngineeringClaim) -> None:
        """
        Enforce promotion policy, raising UnauthorizedPromotionError if claim is not verified.
        """
        allowed, reason = cls.evaluate_claim_promotion(claim)
        if not allowed:
            raise UnauthorizedPromotionError(
                f"Governance gate blocked claim promotion: {reason}"
            )

    @classmethod
    def authorize_release_readiness(cls, claims: List[EngineeringClaim]) -> Tuple[bool, List[str]]:
        """
        Evaluates an entire collection of claims required for a release gate decision.
        """
        rejection_reasons: List[str] = []
        for claim in claims:
            allowed, reason = cls.evaluate_claim_promotion(claim)
            if not allowed:
                rejection_reasons.append(f"[{claim.claim_type.value}] {reason}")

        if rejection_reasons:
            return False, rejection_reasons
        return True, []
