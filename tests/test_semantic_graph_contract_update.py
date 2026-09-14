"""
Tests for Phase 45 — Semantic Graph Incremental Contract Update.
Verifies that ContractProposal integrates safely with CrossLanguageSemanticGraph:
- PROPOSED proposals generate PROPOSED / OBSERVED edges, NOT VERIFIED edges.
- Validated proposals (VALIDATED) are promoted to formal CONTRACTUAL relationships.
- Semantic graph updates incrementally with versioning, without global rebuilds.
"""

import pytest
from agents.runtime_discovery.models import (
    ObservationSourceType,
    ProposalStatus,
    ContractProposal,
    InferredSchema,
)
from agents.runtime_discovery.bridge import RuntimeDiscoveryBridge
from agents.semantic_graph.graph import CrossLanguageSemanticGraph
from agents.semantic_graph.contracts import ContractRegistry


def test_proposal_to_semantic_graph_unverified():
    graph = CrossLanguageSemanticGraph()
    registry = ContractRegistry()
    bridge = RuntimeDiscoveryBridge(graph=graph, registry=registry)

    # Initial graph state
    initial_version = graph.graph_version

    proposal = ContractProposal(
        proposal_id="prop_fe_to_be_01",
        source="browser_network_logs",
        route="/api/v1/search",
        method="GET",
        observed_request_schema={},
        observed_response_schema={"fields": {"results": {"type": "array"}}},
        observed_errors=[],
        proposed_contract={"openapi": "3.0.0"},
        evidence_refs=["obs_qa_01", "obs_qa_02"],
        sample_count=2,
        confidence=0.75,
        assumptions=["Frontend queries /api/v1/search"],
        uncertainties=["Pagination not observed"],
        contract_version="1.0.0-proposed",
        status=ProposalStatus.PROPOSED,
    )

    # Register proposal
    bridge.integrate_proposal(proposal)

    # Invariant: A proposal must NOT create a VERIFIED edge
    node = graph.get_node(proposal.proposal_id)
    assert node is not None
    assert node.properties.get("status") == "PROPOSED"
    assert node.properties.get("is_verified") is False

    edges = graph.get_edges_for_node(proposal.proposal_id)
    for edge in edges:
        # Proposed edge or observed edge, never contractual / verified
        assert edge.relation in ("PROPOSED_EDGE", "OBSERVED_EDGE")
        assert edge.confidence != "CONTRACTUAL"


def test_proposal_validation_promotes_edge_and_bumps_version():
    graph = CrossLanguageSemanticGraph()
    registry = ContractRegistry()
    bridge = RuntimeDiscoveryBridge(graph=graph, registry=registry)

    proposal = ContractProposal(
        proposal_id="prop_fe_to_be_02",
        source="backend_http_middleware",
        route="/api/v1/auth/session",
        method="GET",
        observed_request_schema={},
        observed_response_schema={"fields": {"authenticated": {"type": "boolean"}}},
        observed_errors=[],
        proposed_contract={"openapi": "3.0.0"},
        evidence_refs=["obs_01", "obs_02", "obs_03"],
        sample_count=3,
        confidence=0.92,
        assumptions=["Standard session check"],
        uncertainties=[],
        contract_version="1.0.0-proposed",
        status=ProposalStatus.PROPOSED,
    )

    bridge.integrate_proposal(proposal)
    v_before = graph.graph_version

    # Promote to VALIDATED
    promoted_contract = bridge.promote_proposal_to_formal_contract(
        proposal_id=proposal.proposal_id,
        operator_id="human_qa_engineer",
        notes="Validated against backend auth session implementation",
    )

    assert promoted_contract is not None
    assert promoted_contract.status == "VALIDATED"
    assert graph.graph_version > v_before

    # Node is now verified
    node = graph.get_node(proposal.proposal_id)
    assert node.properties.get("status") == "VALIDATED"
    assert node.properties.get("is_verified") is True
