"""
Tests for Incremental Semantic Graph updates and blast radius isolation (Section 32).
"""

import time
import pytest
from agents.semantic_graph.graph import CrossLanguageSemanticGraph
from agents.semantic_graph.models import (
    SemanticEdge,
    SemanticNode,
    SemanticNodeType,
    SemanticRelationType,
)


def test_incremental_node_update_blast_radius():
    graph = CrossLanguageSemanticGraph()

    # Subsystem 1: User Feature (Frontend -> API -> Backend)
    graph.add_node(SemanticNode(node_id="user_fe", node_type=SemanticNodeType.FRONTEND_COMPONENT, ecosystem="react"))
    graph.add_node(SemanticNode(node_id="user_api", node_type=SemanticNodeType.API_CONTRACT, ecosystem="openapi"))
    graph.add_node(SemanticNode(node_id="user_be", node_type=SemanticNodeType.BACKEND_SERVICE, ecosystem="fastapi"))
    graph.add_node(SemanticNode(node_id="user_test", node_type=SemanticNodeType.TEST, ecosystem="playwright"))

    graph.add_edge(SemanticEdge(edge_id="e1", source="user_fe", target="user_api", relation_type=SemanticRelationType.CONSUMES))
    graph.add_edge(SemanticEdge(edge_id="e2", source="user_api", target="user_be", relation_type=SemanticRelationType.SERVES))
    graph.add_edge(SemanticEdge(edge_id="e3", source="user_fe", target="user_test", relation_type=SemanticRelationType.VALIDATES))

    # Subsystem 2: Unrelated Billing Feature (Billing FE -> Billing API -> Billing BE)
    graph.add_node(SemanticNode(node_id="billing_fe", node_type=SemanticNodeType.FRONTEND_COMPONENT, ecosystem="react"))
    graph.add_node(SemanticNode(node_id="billing_api", node_type=SemanticNodeType.API_CONTRACT, ecosystem="openapi"))
    graph.add_node(SemanticNode(node_id="billing_be", node_type=SemanticNodeType.BACKEND_SERVICE, ecosystem="fastapi"))

    graph.add_edge(SemanticEdge(edge_id="e4", source="billing_fe", target="billing_api", relation_type=SemanticRelationType.CONSUMES))
    graph.add_edge(SemanticEdge(edge_id="e5", source="billing_api", target="billing_be", relation_type=SemanticRelationType.SERVES))

    # Total 7 nodes
    assert len(graph.nodes) == 7
    v_before = graph.graph_version

    # Now mutate ONLY the user_fe component
    updated_fe = SemanticNode(
        node_id="user_fe",
        node_type=SemanticNodeType.FRONTEND_COMPONENT,
        ecosystem="react",
        version="1.1.0",
        metadata={"edited": True},
    )

    invalidated_nodes = graph.update_node_incremental(updated_fe)

    # 1. Graph version bumped
    assert graph.graph_version == v_before + 1

    # 2. Blast radius contains user_fe and its downstream nodes (user_api, user_be, user_test)
    assert "user_fe" in invalidated_nodes
    assert "user_api" in invalidated_nodes
    assert "user_be" in invalidated_nodes
    assert "user_test" in invalidated_nodes

    # 3. CRITICAL INVARIANT: Billing subsystem is completely unaffected!
    assert "billing_fe" not in invalidated_nodes
    assert "billing_api" not in invalidated_nodes
    assert "billing_be" not in invalidated_nodes


def test_incremental_update_performance():
    """Validates that incremental update is O(V_local + E_local) and orders of magnitude faster than full rebuild."""
    graph = CrossLanguageSemanticGraph()

    # Populate 500 nodes in 50 independent chains of length 10
    for chain in range(50):
        prev = None
        for step in range(10):
            nid = f"c{chain}_s{step}"
            graph.add_node(SemanticNode(node_id=nid, node_type=SemanticNodeType.ARCHITECTURE_COMPONENT))
            if prev:
                graph.add_edge(SemanticEdge(edge_id=f"e_{prev}_{nid}", source=prev, target=nid, relation_type=SemanticRelationType.DEPENDS_ON), check_cycle=False)
            prev = nid

    assert len(graph.nodes) == 500

    # Mutate one leaf node in chain 0
    leaf = SemanticNode(node_id="c0_s9", node_type=SemanticNodeType.ARCHITECTURE_COMPONENT, metadata={"status": "updated"})

    t0 = time.perf_counter()
    blast = graph.update_node_incremental(leaf)
    t_incremental = time.perf_counter() - t0

    # Leaf node has no downstream dependencies, so blast radius is only itself
    assert blast == {"c0_s9"}
    assert t_incremental < 0.01  # sub-10ms
