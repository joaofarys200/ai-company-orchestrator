"""
Tests for Phase 45 — ContractProposalValidator.
Verifies validation logic, confidence scoring thresholds, and
deterministic discovery policies:
AUTO_OBSERVE, PROPOSE_CONTRACT, REQUEST_HUMAN, BLOCK.
"""

import pytest
from agents.runtime_discovery.models import (
    ContractProposal,
    DiscoveryPolicyAction,
    ProposalStatus,
    DiffSeverity,
    ContractDiff,
    FieldDifference,
    FieldDiffType,
)
from agents.runtime_discovery.validator import ContractProposalValidator


def test_validator_propose_contract_on_stable_schema():
    validator = ContractProposalValidator()

    proposal = ContractProposal(
        proposal_id="prop_val_01",
        source="browser_network_logs",
        route="/api/v1/metrics",
        method="GET",
        observed_request_schema={},
        observed_response_schema={
            "fields": {"latency": {"type": "float", "is_required": True}}
        },
        observed_errors=[],
        proposed_contract={},
        evidence_refs=["o1", "o2", "o3", "o4"],
        sample_count=4,
        confidence=0.88,
        assumptions=[],
        uncertainties=[],
        status=ProposalStatus.PROPOSED,
    )

    action = validator.evaluate_policy(proposal)
    assert action == DiscoveryPolicyAction.PROPOSE_CONTRACT


def test_validator_request_human_on_breaking_diff():
    validator = ContractProposalValidator()

    proposal = ContractProposal(
        proposal_id="prop_val_02",
        source="local_dev_proxy",
        route="/api/v1/users",
        method="POST",
        observed_request_schema={},
        observed_response_schema={},
        observed_errors=[],
        proposed_contract={},
        evidence_refs=["o1"],
        sample_count=2,
        confidence=0.60,
        assumptions=[],
        uncertainties=["Polymorphic structure detected"],
        status=ProposalStatus.PROPOSED,
    )

    diff = ContractDiff(
        severity=DiffSeverity.BREAKING,
        differences=[
            FieldDifference(
                field_path="id",
                diff_type=FieldDiffType.TYPE_CHANGED,
                severity=DiffSeverity.BREAKING,
                description="Changed from int to string",
            )
        ],
    )

    action = validator.evaluate_policy(proposal, diff=diff)
    assert action == DiscoveryPolicyAction.REQUEST_HUMAN


def test_validator_block_on_security_sensitive_or_malicious():
    validator = ContractProposalValidator()

    proposal = ContractProposal(
        proposal_id="prop_val_03",
        source="test_traffic",
        route="/admin/eval_cmd",
        method="POST",
        observed_request_schema={},
        observed_response_schema={},
        observed_errors=[],
        proposed_contract={},
        evidence_refs=["o1"],
        sample_count=1,
        confidence=0.20,
        assumptions=[],
        uncertainties=["Command execution endpoint"],
        status=ProposalStatus.PROPOSED,
    )

    action = validator.evaluate_policy(proposal)
    assert action == DiscoveryPolicyAction.BLOCK


def test_validator_auto_observe_on_few_samples():
    validator = ContractProposalValidator()

    proposal = ContractProposal(
        proposal_id="prop_val_04",
        source="test_traffic",
        route="/api/v1/health",
        method="GET",
        observed_request_schema={},
        observed_response_schema={},
        observed_errors=[],
        proposed_contract={},
        evidence_refs=["o1"],
        sample_count=1,
        confidence=0.45,
        assumptions=[],
        uncertainties=["Few samples"],
        status=ProposalStatus.PROPOSED,
    )

    action = validator.evaluate_policy(proposal)
    assert action == DiscoveryPolicyAction.AUTO_OBSERVE
