"""
JARVIS OS — Phase 48: Contract-Aware Autonomous Change Management
ContractMissionGate: Pre-execution admission gate and Completion Gate (No False Success).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from agents.contract_change_management.models import (
    ContractChangePrediction,
    ContractRiskLevel,
    ContractVerificationResult,
    GateDecision,
)


class ContractMissionGate:
    """
    Authoritative admission and completion gate for contract changes.
    Enforces that breaking changes cannot silently execute without migration/approval,
    and prevents false completion if a contract mismatch exists.
    """

    @classmethod
    def evaluate_preflight_gate(
        cls,
        prediction: ContractChangePrediction,
        human_approved: bool = False,
    ) -> tuple[GateDecision, bool, str]:
        """
        Evaluates pre-execution admission.
        Returns: (decision, allowed_to_execute, reason)
        """
        # 1. Security contract violation check
        for diff in prediction.predicted_diffs:
            if "auth" in diff.field_path.lower() or "security" in diff.field_path.lower():
                if diff.risk_level == ContractRiskLevel.BREAKING:
                    return (
                        GateDecision.BLOCK,
                        False,
                        f"Security contract violation: altering {diff.field_path} threatens authentication invariants.",
                    )

        # 2. Economic contract check
        if any("payment" in c.lower() or "billing" in c.lower() for c in prediction.affected_contracts):
            if prediction.breaking_risk in (ContractRiskLevel.BREAKING, ContractRiskLevel.POTENTIALLY_BREAKING):
                if not human_approved:
                    return (
                        GateDecision.REQUIRE_HUMAN_APPROVAL,
                        False,
                        "Economic contract change detected: mandatory operator sign-off required before execution.",
                    )

        # 3. Breaking changes require migration plan and approval
        if prediction.breaking_risk == ContractRiskLevel.BREAKING:
            if not prediction.migration_plan:
                return (
                    GateDecision.BLOCK,
                    False,
                    "Breaking contract change detected without an established ContractMigrationPlan.",
                )
            if prediction.approval_required and not human_approved:
                return (
                    GateDecision.REQUIRE_HUMAN_APPROVAL,
                    False,
                    f"Breaking contract change on {prediction.affected_contracts} requires explicit human approval of migration plan {prediction.migration_plan.migration_id}.",
                )

        # 4. Potentially breaking changes
        if prediction.breaking_risk == ContractRiskLevel.POTENTIALLY_BREAKING:
            if prediction.approval_required and not human_approved:
                return (
                    GateDecision.REQUIRE_HUMAN_APPROVAL,
                    False,
                    "Potentially breaking contract change requires human approval.",
                )

        return (
            GateDecision.ALLOW,
            True,
            "Contract preflight gate cleared: change is non-breaking or migration plan is approved.",
        )

    @classmethod
    def evaluate_completion_gate(
        cls,
        verification_result: ContractVerificationResult,
    ) -> tuple[bool, str]:
        """
        Evaluates mission completion.
        CRITICAL: Prevents False Success — if build succeeds but contract mismatch exists,
        mission completion is rejected.
        """
        if not verification_result.matches_predicted:
            return (
                False,
                f"Contract mismatch: observed runtime contract does not match predicted contract version for {verification_result.contract_id}.",
            )

        if not verification_result.consumer_compatibility_verified:
            return (
                False,
                f"Consumer incompatibility: one or more registered consumers failed compatibility checks against {verification_result.contract_id}.",
            )

        if not verification_result.tests_verified:
            return (
                False,
                f"Test suite failure: contract verification tests failed for {verification_result.contract_id}.",
            )

        if not verification_result.browser_qa_verified:
            return (
                False,
                f"Browser QA failure: end-to-end visual or contract assertion failed for {verification_result.contract_id}.",
            )

        if not verification_result.all_evidence_verified:
            return (
                False,
                "Incomplete evidence: required proof documents are missing from the verification ledger.",
            )

        return (
            True,
            f"Contract Completion Gate satisfied: all contract, consumer, test, browser, and evidence verifications passed for {verification_result.contract_id}.",
        )
