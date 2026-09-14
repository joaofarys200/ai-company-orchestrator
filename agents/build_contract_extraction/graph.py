"""
JARVIS OS — Phase 49: Build Contract Graph Integrator
Extends CrossLanguageSemanticGraph with build-extracted contract schemas, generated types, and dynamic consumers.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from agents.build_contract_extraction.models import (
    DynamicConsumerResolution,
    EvidenceState,
    ExtractedContractBundle,
    ResolutionStatus,
)
from agents.build_contract_extraction.provenance import ProvenanceTracker
from agents.semantic_graph.graph import CrossLanguageSemanticGraph
from agents.semantic_graph.models import (
    ConfidenceClass,
    SemanticEdge,
    SemanticNode,
    SemanticNodeType,
    SemanticRelationType,
)


class BuildContractGraphIntegrator:
    """
    Integrates build-extracted endpoints, schemas, and resolved dynamic consumers
    into the CrossLanguageSemanticGraph, establishing end-to-end type traceability.
    """

    @classmethod
    def integrate_bundle(
        cls,
        bundle: ExtractedContractBundle,
        graph: CrossLanguageSemanticGraph,
    ) -> dict[str, int]:
        """Adds nodes and edges for all bundle elements into the semantic graph."""
        nodes_added = 0
        edges_added = 0

        # 1. Integrate Endpoints & Response Schemas
        for ep_id, ep in bundle.endpoints.items():
            ep_node_id = f"endpoint::{ep_id}"
            graph.add_node(SemanticNode(
                node_id=ep_node_id,
                node_type=SemanticNodeType.API_ENDPOINT,
                name=f"{ep.method} {ep.path}",
                language="python",
                metadata={"version": ep.version, "provenance": ep.provenance.to_dict() if ep.provenance else None},
            ))
            nodes_added += 1

            if ep.response_schema:
                schema_node_id = f"schema::{ep_id}_response"
                graph.add_node(SemanticNode(
                    node_id=schema_node_id,
                    node_type=SemanticNodeType.DATA_MODEL,
                    name=f"{ep.path} Response Schema",
                    metadata={"provenance": ep.provenance.to_dict() if ep.provenance else None},
                ))
                nodes_added += 1

                # Edge: BACKEND_ENDPOINT -> RESPONSE_SCHEMA
                e_id = f"edge::{ep_node_id}__serves__{schema_node_id}"
                graph.add_edge(SemanticEdge(
                    edge_id=e_id,
                    source=ep_node_id,
                    target=schema_node_id,
                    relation_type=SemanticRelationType.SERVES,
                    confidence=ConfidenceClass.CONTRACTUAL,
                ), check_cycle=False)
                edges_added += 1

        # 2. Integrate Canonical Types
        for type_id, ctype in bundle.types.items():
            t_node_id = f"type::{type_id}"
            graph.add_node(SemanticNode(
                node_id=t_node_id,
                node_type=SemanticNodeType.DATA_MODEL,
                name=ctype.name,
                language=ctype.language,
                metadata={"kind": ctype.kind.value, "provenance": ctype.provenance.to_dict() if ctype.provenance else None},
            ))
            nodes_added += 1

            # Fields
            for fname, fdef in ctype.properties.items():
                f_node_id = f"field::{type_id}::{fname}"
                graph.add_node(SemanticNode(
                    node_id=f_node_id,
                    node_type=SemanticNodeType.DATA_MODEL,
                    name=f"{ctype.name}.{fname}",
                    metadata={"field_type": fdef.field_type, "required": fdef.required},
                ))
                nodes_added += 1

                e_id = f"edge::{t_node_id}__has_field__{f_node_id}"
                graph.add_edge(SemanticEdge(
                    edge_id=e_id,
                    source=t_node_id,
                    target=f_node_id,
                    relation_type=SemanticRelationType.IMPLEMENTS,
                    confidence=ConfidenceClass.CONTRACTUAL,
                ), check_cycle=False)
                edges_added += 1

        # 3. Integrate Events
        for evt_id, evt in bundle.events.items():
            evt_node_id = f"event::{evt_id}"
            graph.add_node(SemanticNode(
                node_id=evt_node_id,
                node_type=SemanticNodeType.DATA_MODEL,
                name=evt.topic_or_type,
                metadata={"discriminator": evt.discriminator_value},
            ))
            nodes_added += 1

        # 4. Integrate Resolved & Uncertain Dynamic Consumers
        for res in bundle.dynamic_resolutions:
            c_node_id = f"consumer::{res.consumer_id}"
            c_type = SemanticNodeType.FRONTEND_COMPONENT if res.pattern.language == "TypeScript" else SemanticNodeType.BACKEND_SERVICE
            graph.add_node(SemanticNode(
                node_id=c_node_id,
                node_type=c_type,
                name=res.consumer_name,
                source_ref=f"{res.pattern.source_file}:{res.pattern.line_number}",
                language=res.pattern.language,
                metadata={
                    "resolution_status": res.resolution_status.value,
                    "evidence_state": res.evidence_state.value,
                    "uncertainty_reason": res.uncertainty_reason.value,
                    "pattern_type": res.pattern.pattern_type.value,
                },
            ))
            nodes_added += 1

            # Edge: CONSUMER -> CONTRACT / EVENT (if resolved)
            if res.resolution_status == ResolutionStatus.RESOLVED and res.resolved_contract_id:
                # Find matching target node
                target_node_id = None
                for potential in (f"endpoint::{res.resolved_contract_id}", f"type::{res.resolved_contract_id}", f"event::{res.resolved_contract_id}"):
                    if potential in graph.nodes:
                        target_node_id = potential
                        break

                if target_node_id:
                    conf = ConfidenceClass.CONTRACTUAL if res.evidence_state == EvidenceState.GENERATED else ConfidenceClass.INFERRED
                    e_id = f"edge::{c_node_id}__consumes__{target_node_id}"
                    graph.add_edge(SemanticEdge(
                        edge_id=e_id,
                        source=c_node_id,
                        target=target_node_id,
                        relation_type=SemanticRelationType.CONSUMES,
                        confidence=conf,
                    ), check_cycle=False)
                    edges_added += 1

        return {
            "nodes_added": nodes_added,
            "edges_added": edges_added,
            "total_nodes": len(graph.nodes),
            "total_edges": len(graph.edges),
            "is_acyclic": graph.is_acyclic() if hasattr(graph, "is_acyclic") else True,
        }
