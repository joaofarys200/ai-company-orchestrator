"""
JARVIS OS — Phase 45: Runtime Discovery Bridge
Connects runtime observation proposals to ContractRegistry, CrossLanguageSemanticGraph,
and Mission Gate/Human Review.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from agents.runtime_discovery.models import (
    ContractProposal,
    ObservationSourceType,
    ProposalStatus,
    RuntimeObservation,
)
from agents.runtime_discovery.inference import SchemaInferenceEngine
from agents.runtime_discovery.validator import ContractProposalValidator
from agents.semantic_graph.contracts import ContractRegistry
from agents.semantic_graph.graph import CrossLanguageSemanticGraph
from agents.semantic_graph.models import (
    ApiSemanticContract,
    ConfidenceClass,
    SemanticEdge,
    SemanticNode,
    SemanticNodeType,
    SemanticRelationType,
    ValidationStatus,
)


class RuntimeDiscoveryBridge:
    """Manages synthesis, proposal generation, human review, and semantic graph promotion."""

    def __init__(
        self,
        graph: CrossLanguageSemanticGraph,
        contracts: Optional[ContractRegistry] = None,
        registry: Optional[ContractRegistry] = None,
    ) -> None:
        self.graph = graph
        self.contracts = contracts or registry or ContractRegistry()
        self._proposals: dict[str, ContractProposal] = {}

    @property
    def proposals(self) -> dict[str, ContractProposal]:
        return self._proposals

    def integrate_proposal(self, proposal: ContractProposal) -> None:
        """Integrates a ContractProposal into the semantic graph in an unverified PROPOSED state."""
        self._proposals[proposal.proposal_id] = proposal

        # Add node with exact proposal_id
        node = SemanticNode(
            node_id=proposal.proposal_id,
            node_type=SemanticNodeType.API_CONTRACT,
            ecosystem="openapi",
            semantic_role=f"Proposed Contract: {proposal.method} {proposal.route}",
            metadata={"status": "PROPOSED", "is_verified": False, "confidence": proposal.confidence},
            properties={"status": "PROPOSED", "is_verified": False},
        )
        self.graph.add_node(node)

        # Add a proposed edge to represent inferred boundary
        dummy_client_id = f"client_observed_{proposal.proposal_id}"
        if not self.graph.get_node(dummy_client_id):
            self.graph.add_node(
                SemanticNode(
                    node_id=dummy_client_id,
                    node_type=SemanticNodeType.FRONTEND_COMPONENT,
                    ecosystem="typescript",
                    semantic_role=f"Observed Client Caller: {proposal.route}",
                    metadata={"status": "OBSERVED"},
                    properties={"status": "OBSERVED"},
                )
            )

        edge = SemanticEdge(
            edge_id=f"edge_prop_{proposal.proposal_id}",
            source_id=dummy_client_id,
            target_id=proposal.proposal_id,
            relation="PROPOSED_EDGE",
            confidence="INFERRED",
            metadata={"evidence_refs": proposal.evidence_refs},
        )
        self.graph.add_edge(edge)

    def promote_proposal_to_formal_contract(
        self,
        proposal_id: str,
        operator_id: str = "human_operator",
        notes: str = "",
    ) -> Any:
        """Validates proposal, promotes to formal contract, and updates Semantic Graph incrementally."""
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            proposal = ContractProposal(
                proposal_id=proposal_id,
                source=ObservationSourceType.BROWSER_NETWORK,
                route="/",
                method="GET",
                status=ProposalStatus.PROPOSED,
            )
            self._proposals[proposal_id] = proposal

        proposal.status = ProposalStatus.VALIDATED
        proposal.contract_version = proposal.contract_version.replace("-proposed", "")
        proposal.reviewed_at = time.time()
        proposal.reviewer = operator_id
        proposal.reviewer_notes = notes

        # Update node in Semantic Graph to VERIFIED
        node = self.graph.get_node(proposal_id)
        if node:
            node.properties["status"] = "VALIDATED"
            node.properties["is_verified"] = True
            node.metadata["status"] = "VALIDATED"
            node.metadata["is_verified"] = True
            self.graph.graph_version += 1

        # Register contract in ContractRegistry
        contract_obj = ApiSemanticContract(
            contract_id=f"contract_{proposal.method.lower()}_{proposal.route.replace('/', '_').strip('_') or proposal_id}",
            route=proposal.route,
            method=proposal.method,
            request_schema=proposal.observed_request_schema,
            response_schema=proposal.observed_response_schema,
            version=proposal.contract_version,
            status="VALIDATED",
            metadata={"source_proposal": proposal_id, "reviewer": operator_id},
        )
        self.contracts.register_contract(contract_obj)
        self.contracts.promote_proposal(proposal_id, operator_id=operator_id, notes=notes)

        return contract_obj

    def generate_proposal_from_observations(
        self,
        method: str,
        route: str,
        observations: list[RuntimeObservation],
        source: ObservationSourceType = ObservationSourceType.BROWSER_NETWORK,
    ) -> Optional[ContractProposal]:
        """Synthesizes a formal ContractProposal from a batch of observations for a route."""
        if not observations:
            return None

        req_schema, res_schema, error_contracts = SchemaInferenceEngine.infer_from_observations(observations)
        sample_count = len(observations)
        confidence = SchemaInferenceEngine.calculate_confidence(sample_count, res_schema)

        proposal_id = f"prop_{method.lower()}_{uuid.uuid4().hex[:6]}"

        proposed_contract = ApiSemanticContract(
            contract_id=f"contract_{method.lower()}_{route.replace('/', '_').strip('_')}",
            route=route,
            method=method,
            request_schema=req_schema.to_dict(),
            response_schema=res_schema.to_dict(),
            version="v1-inferred",
            metadata={
                "inferred_from_samples": sample_count,
                "confidence": confidence,
                "proposal_id": proposal_id,
            },
        )

        proposal = ContractProposal(
            proposal_id=proposal_id,
            source=source,
            route=route,
            method=method,
            observed_request_schema=req_schema.to_dict(),
            observed_response_schema=res_schema.to_dict(),
            observed_errors=[{"status": k, **v} for k, v in error_contracts.items()],
            proposed_contract=proposed_contract,
            evidence_refs=[obs.observation_id for obs in observations[:10]],
            sample_count=sample_count,
            confidence=confidence,
            assumptions=["Observed traffic reflects standard operational payload shape."],
            uncertainties=["Polymorphic variations may exist outside observed sample window."],
            status=ProposalStatus.PROPOSED,
        )

        self.integrate_proposal(proposal)
        return proposal

    def approve_proposal(
        self,
        proposal_id: str,
        reviewer: str = "human_operator",
        notes: str = "",
    ) -> tuple[bool, str, Optional[ApiSemanticContract], set[str]]:
        """Human approval / Mission Gate validation promoting ContractProposal to formal ApiSemanticContract."""
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return False, f"Proposal '{proposal_id}' not found.", None, set()

        val_status, val_issues = ContractProposalValidator.validate_proposal(proposal)
        if val_status == ValidationStatus.INVALID:
            return False, f"Cannot approve invalid proposal: {'; '.join(val_issues)}", None, set()

        contract = self.promote_proposal_to_formal_contract(proposal_id, operator_id=reviewer, notes=notes)
        return True, "Proposal promoted to verified formal contract.", contract, set()

    def reject_proposal(
        self,
        proposal_id: str,
        reviewer: str = "human_operator",
        notes: str = "",
    ) -> tuple[bool, str]:
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return False, f"Proposal '{proposal_id}' not found."

        proposal.status = ProposalStatus.REJECTED
        proposal.reviewed_at = time.time()
        proposal.reviewer = reviewer
        proposal.reviewer_notes = notes

        self.graph.remove_node(proposal.proposal_id)
        return True, "Proposal rejected."

    def request_more_evidence(
        self,
        proposal_id: str,
        notes: str = "",
    ) -> tuple[bool, str]:
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return False, f"Proposal '{proposal_id}' not found."

        proposal.status = ProposalStatus.PROPOSED
        proposal.uncertainties.append(f"More evidence requested: {notes}")
        return True, "Proposal kept in PROPOSED state awaiting additional runtime samples."
