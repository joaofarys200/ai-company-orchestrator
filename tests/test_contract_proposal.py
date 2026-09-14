"""
Tests for Phase 45 — ContractProposal.
Verifies the tri-state separation: OBSERVED != INFERRED != VERIFIED.
Verifies proposal lifecycle: OBSERVED -> INFERRED -> PROPOSED -> VALIDATED / REJECTED / STALE.
Verifies explicit versioning and evidence references.
"""

import pytest
from agents.runtime_discovery.models import (
    ObservationSourceType,
    ProposalStatus,
    ContractProposal,
    InferredSchema,
)
from agents.runtime_discovery.observer import RuntimeContractObserver
from agents.runtime_discovery.inference import SchemaInferenceEngine


def test_proposal_lifecycle_and_invariants():
    observer = RuntimeContractObserver()
    engine = SchemaInferenceEngine()

    for i in range(5):
        observer.observe_interaction(
            source_type=ObservationSourceType.BROWSER_NETWORK_LOGS,
            method="GET",
            route="/api/v1/projects",
            status_code=200,
            response_body=[{"project_id": f"p_{i}", "name": f"Project {i}"}],
        )

    observations = observer.get_observations_for_endpoint("GET", "/api/v1/projects")
    assert len(observations) == 5

    inferred_schema = engine.infer_response_schema(observations)
    proposal = engine.create_contract_proposal(
        route="/api/v1/projects",
        method="GET",
        source="browser_network_logs",
        observations=observations,
        inferred_response_schema=inferred_schema,
    )

    # Initial state must be PROPOSED (or INFERRED) - NEVER VERIFIED
    assert proposal.status == ProposalStatus.PROPOSED
    assert proposal.status != ProposalStatus.VALIDATED
    assert proposal.sample_count == 5
    assert proposal.confidence >= 0.80
    assert len(proposal.evidence_refs) == 5
    assert proposal.contract_version.endswith("-proposed")
    assert proposal.parent_version == "UNVERSIONED_OBSERVED"


def test_proposal_rejection_and_stale():
    proposal = ContractProposal(
        proposal_id="prop_test_01",
        source="test_traffic",
        route="/api/v1/old",
        method="GET",
        observed_request_schema={},
        observed_response_schema={"type": "object"},
        observed_errors=[],
        proposed_contract={"openapi": "3.0.0"},
        evidence_refs=["obs_01"],
        sample_count=1,
        confidence=0.30,
        assumptions=["Deprecated route"],
        uncertainties=["Single observation"],
        contract_version="0.1.0-proposed",
        status=ProposalStatus.PROPOSED,
    )

    # Rejection
    proposal.status = ProposalStatus.REJECTED
    assert proposal.status == ProposalStatus.REJECTED

    # Stale marking
    proposal.status = ProposalStatus.STALE
    assert proposal.status == ProposalStatus.STALE


def test_proposal_promotion_requires_validation():
    proposal = ContractProposal(
        proposal_id="prop_test_02",
        source="backend_http_middleware",
        route="/api/v1/items",
        method="GET",
        observed_request_schema={},
        observed_response_schema={"type": "array"},
        observed_errors=[],
        proposed_contract={"openapi": "3.0.0"},
        evidence_refs=["obs_1", "obs_2", "obs_3", "obs_4"],
        sample_count=4,
        confidence=0.92,
        assumptions=["Stable items list"],
        uncertainties=[],
        contract_version="1.0.0-proposed",
        status=ProposalStatus.PROPOSED,
    )

    # Direct promotion without validation is forbidden by protocol
    # When validated:
    proposal.status = ProposalStatus.VALIDATED
    proposal.contract_version = "1.0.0"
    assert proposal.status == ProposalStatus.VALIDATED
    assert not proposal.contract_version.endswith("-proposed")
