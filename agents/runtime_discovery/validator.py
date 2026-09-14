"""
JARVIS OS — Phase 45: Contract Proposal Validator & Policy Engine
Evaluates ContractProposal integrity, determines validation status (VALID, INVALID, UNCERTAIN),
and enforces deterministic discovery policies (AUTO_OBSERVE, PROPOSE_CONTRACT, REQUEST_HUMAN, BLOCK).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from agents.runtime_discovery.models import (
    ContractProposal,
    DiscoveryPolicyAction,
    ProposalStatus,
)
from agents.semantic_graph.models import ValidationStatus


class ContractProposalValidator:
    """Validates contract proposals against formal consistency rules and assigns policy actions."""

    MIN_CONFIDENCE_THRESHOLD = 0.50
    HUMAN_REVIEW_CONFIDENCE_THRESHOLD = 0.80

    @classmethod
    def validate_proposal(cls, proposal: ContractProposal) -> tuple[ValidationStatus, list[str]]:
        """Evaluates whether a proposal is technically well-formed and sufficiently evidenced."""
        issues: list[str] = []

        if not proposal.route or not proposal.method:
            issues.append("Proposal lacks valid HTTP method or route.")
            return ValidationStatus.INVALID, issues

        if proposal.sample_count <= 0:
            issues.append("Proposal has 0 observed samples.")
            return ValidationStatus.INVALID, issues

        if proposal.confidence < cls.MIN_CONFIDENCE_THRESHOLD:
            issues.append(f"Confidence {proposal.confidence} is below minimum threshold {cls.MIN_CONFIDENCE_THRESHOLD}: marked UNCERTAIN.")
            return ValidationStatus.UNCERTAIN, issues

        # Check if response schema was extracted
        if not proposal.observed_response_schema or not proposal.observed_response_schema.get("properties"):
            issues.append("Response schema is empty or could not be inferred.")
            return ValidationStatus.UNCERTAIN, issues

        return ValidationStatus.VALID, ["Proposal satisfies all empirical validation rules."]

    @classmethod
    def evaluate_discovery_policy(
        cls,
        proposal: ContractProposal,
        has_breaking_changes: bool = False,
        is_security_sensitive: bool = False,
    ) -> tuple[DiscoveryPolicyAction, str]:
        """Deterministic policy decision for runtime contract proposals."""
        if is_security_sensitive:
            return DiscoveryPolicyAction.BLOCK, "Endpoint is security-sensitive: auto-promotion blocked."

        if has_breaking_changes:
            return DiscoveryPolicyAction.REQUEST_HUMAN, "Detected breaking changes against formal contract: requires human review."

        status, issues = cls.validate_proposal(proposal)

        if status == ValidationStatus.INVALID:
            return DiscoveryPolicyAction.BLOCK, f"Proposal invalid: {'; '.join(issues)}"

        if status == ValidationStatus.UNCERTAIN or proposal.confidence < cls.HUMAN_REVIEW_CONFIDENCE_THRESHOLD:
            return DiscoveryPolicyAction.REQUEST_HUMAN, f"Confidence {proposal.confidence} warrants human review: {'; '.join(issues)}"

        return DiscoveryPolicyAction.PROPOSE_CONTRACT, "Proposal well-formed and ready for human/gate review."

    def evaluate_policy(
        self,
        proposal: ContractProposal,
        diff: Optional[Any] = None,
        is_security_sensitive: bool = False,
    ) -> DiscoveryPolicyAction:
        """Deterministic policy evaluator returning DiscoveryPolicyAction enum directly."""
        route_lower = proposal.route.lower()
        if (
            is_security_sensitive
            or "eval" in route_lower
            or "cmd" in route_lower
            or "exec" in route_lower
            or any("command" in str(u).lower() for u in proposal.uncertainties)
        ):
            return DiscoveryPolicyAction.BLOCK

        if diff is not None:
            sev = getattr(diff, "severity", None)
            if sev and str(getattr(sev, "value", sev)) == "BREAKING":
                return DiscoveryPolicyAction.REQUEST_HUMAN
            if getattr(diff, "is_breaking", False):
                return DiscoveryPolicyAction.REQUEST_HUMAN

        if proposal.sample_count < 2 or proposal.confidence < 0.50:
            return DiscoveryPolicyAction.AUTO_OBSERVE

        if proposal.confidence >= 0.80 and proposal.sample_count >= 3:
            return DiscoveryPolicyAction.PROPOSE_CONTRACT

        return DiscoveryPolicyAction.REQUEST_HUMAN

