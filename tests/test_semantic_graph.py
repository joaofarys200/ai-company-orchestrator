"""
Tests for CrossLanguageSemanticGraph core data structure, Kahn's algorithm, and DAG validation.
"""

import pytest
from agents.semantic_graph.models import (
    SemanticNode,
    SemanticEdge,
    SemanticNodeType,
    SemanticRelationType,
    ConfidenceClass,
)
from agents.semantic_graph.graph import (
    CrossLanguageSemanticGraph,
    SemanticGraphCycleError,
    SemanticGraphError,
)


def test_graph_node_and_edge_addition():
    graph = CrossLanguageSemanticGraph()

    n1 = SemanticNode(
        node_id="node_req_01",
        node_type=SemanticNodeType.REQUIREMENT,
        language="agnostic",
        ecosystem="agnostic",
        semantic_role="search_capability",
    )
    n2 = SemanticNode(
        node_id="node_arch_01",
        node_type=SemanticNodeType.ARCHITECTURE_COMPONENT,
        language="agnostic",
        ecosystem="agnostic",
        semantic_role="search_service_arch",
    )
    graph.add_node(n1)
    graph.add_node(n2)

    assert graph.get_node("node_req_01") is not None
    assert graph.get_node("node_arch_01") is not None

    edge = SemanticEdge(
        edge_id="edge_01",
        source="node_req_01",
        target="node_arch_01",
        relation_type=SemanticRelationType.IMPLEMENTS,
        confidence_class=ConfidenceClass.CONTRACTUAL,
    )
    graph.add_edge(edge)

    assert graph.get_edge("edge_01") is not None
    assert len(graph.get_out_edges("node_req_01")) == 1
    assert len(graph.get_in_edges("node_arch_01")) == 1


def test_kahn_topological_sort_and_cycle_detection():
    graph = CrossLanguageSemanticGraph()

    # Create linear chain: A -> B -> C
    for nid in ["A", "B", "C"]:
        graph.add_node(SemanticNode(node_id=nid, node_type=SemanticNodeType.ARCHITECTURE_COMPONENT))

    graph.add_edge(SemanticEdge(edge_id="e1", source="A", target="B", relation_type=SemanticRelationType.DEPENDS_ON))
    graph.add_edge(SemanticEdge(edge_id="e2", source="B", target="C", relation_type=SemanticRelationType.DEPENDS_ON))

    order = graph.topological_sort()
    assert order == ["A", "B", "C"]

    # Try introducing a cycle C -> A
    with pytest.raises(SemanticGraphCycleError):
        graph.add_edge(SemanticEdge(edge_id="e3_cycle", source="C", target="A", relation_type=SemanticRelationType.DEPENDS_ON))

    # Invariant: the illegal edge must have been rolled back
    assert graph.get_edge("e3_cycle") is None
    assert graph.topological_sort() == ["A", "B", "C"]


def test_blast_radius_computation():
    graph = CrossLanguageSemanticGraph()

    # Tree:
    #      R
    #    /   \
    #   A     B
    #   |     |
    #   A1    B1
    for nid in ["R", "A", "B", "A1", "B1"]:
        graph.add_node(SemanticNode(node_id=nid, node_type=SemanticNodeType.ARCHITECTURE_COMPONENT))

    graph.add_edge(SemanticEdge(edge_id="e1", source="R", target="A", relation_type=SemanticRelationType.IMPLEMENTS))
    graph.add_edge(SemanticEdge(edge_id="e2", source="R", target="B", relation_type=SemanticRelationType.IMPLEMENTS))
    graph.add_edge(SemanticEdge(edge_id="e3", source="A", target="A1", relation_type=SemanticRelationType.IMPLEMENTS))
    graph.add_edge(SemanticEdge(edge_id="e4", source="B", target="B1", relation_type=SemanticRelationType.IMPLEMENTS))

    # Blast radius of A should be {A, A1}
    br_a = graph.calculate_blast_radius(["A"])
    assert br_a == {"A", "A1"}

    # Blast radius of R should be all nodes
    br_r = graph.calculate_blast_radius(["R"])
    assert br_r == {"R", "A", "B", "A1", "B1"}


def test_version_info_and_serialization():
    graph = CrossLanguageSemanticGraph(graph_version=2)
    n = SemanticNode(node_id="n1", node_type=SemanticNodeType.REQUIREMENT)
    graph.add_node(n)

    v = graph.version_info()
    assert v.graph_version == 2
    assert v.node_count == 1
    assert len(v.version_hash) == 64

    # Serialization roundtrip
    data = graph.to_dict()
    reconstructed = CrossLanguageSemanticGraph.from_dict(data)
    assert reconstructed.graph_version == 2
    assert reconstructed.get_node("n1") is not None
