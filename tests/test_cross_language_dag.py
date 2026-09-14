"""
Tests for Full-Stack Cross-Language DAG traversal, topological ordering, and cycle prevention.
"""

import pytest
from agents.semantic_graph.graph import (
    CrossLanguageSemanticGraph,
    SemanticGraphCycleError,
)
from agents.semantic_graph.models import (
    ConfidenceClass,
    SemanticEdge,
    SemanticNode,
    SemanticNodeType,
    SemanticRelationType,
)


def test_full_stack_cross_language_dag():
    graph = CrossLanguageSemanticGraph()

    # Define nodes across all architectural layers
    nodes = [
        SemanticNode(node_id="req_search", node_type=SemanticNodeType.REQUIREMENT, language="agnostic"),
        SemanticNode(node_id="arch_search", node_type=SemanticNodeType.ARCHITECTURE_COMPONENT, language="agnostic"),
        SemanticNode(node_id="model_user", node_type=SemanticNodeType.DATA_MODEL, language="sql", ecosystem="postgres"),
        SemanticNode(node_id="op_query", node_type=SemanticNodeType.PERSISTENCE_OPERATION, language="sql", ecosystem="postgres"),
        SemanticNode(node_id="be_service", node_type=SemanticNodeType.BACKEND_SERVICE, language="python", ecosystem="fastapi"),
        SemanticNode(node_id="contract_api", node_type=SemanticNodeType.API_CONTRACT, language="json", ecosystem="openapi"),
        SemanticNode(node_id="fe_searchbox", node_type=SemanticNodeType.FRONTEND_COMPONENT, language="typescript", ecosystem="react"),
        SemanticNode(node_id="test_api", node_type=SemanticNodeType.TEST, language="python", ecosystem="pytest"),
        SemanticNode(node_id="browser_qa", node_type=SemanticNodeType.BROWSER_SCENARIO, language="python", ecosystem="playwright"),
    ]

    for n in nodes:
        graph.add_node(n)

    # Wire up edges across technical domains
    edges = [
        # Requirement -> Architecture
        SemanticEdge(edge_id="e1", source="req_search", target="arch_search", relation_type=SemanticRelationType.IMPLEMENTS),
        # Architecture -> Persistence Model & Operations
        SemanticEdge(edge_id="e2", source="arch_search", target="model_user", relation_type=SemanticRelationType.IMPLEMENTS),
        SemanticEdge(edge_id="e3", source="model_user", target="op_query", relation_type=SemanticRelationType.PERSISTS),
        # Operations -> Backend Service
        SemanticEdge(edge_id="e4", source="op_query", target="be_service", relation_type=SemanticRelationType.SERVES),
        # Backend Service -> API Contract
        SemanticEdge(edge_id="e5", source="be_service", target="contract_api", relation_type=SemanticRelationType.EXPOSES),
        # API Contract -> Frontend Component
        SemanticEdge(edge_id="e6", source="contract_api", target="fe_searchbox", relation_type=SemanticRelationType.CONSUMES),
        # Backend & Frontend -> Testing
        SemanticEdge(edge_id="e7", source="be_service", target="test_api", relation_type=SemanticRelationType.TESTS),
        # Frontend -> Browser QA
        SemanticEdge(edge_id="e8", source="fe_searchbox", target="browser_qa", relation_type=SemanticRelationType.VALIDATES),
    ]

    for e in edges:
        graph.add_edge(e)

    # 1. Structural validation
    is_valid, issues = graph.validate_graph()
    assert is_valid, f"Graph issues: {issues}"

    # 2. Topological sort (Kahn's algorithm)
    topo = graph.topological_sort()
    assert len(topo) == 9
    assert topo[0] == "req_search"
    # Frontend and browser must appear after API contract
    assert topo.index("contract_api") < topo.index("fe_searchbox")
    assert topo.index("fe_searchbox") < topo.index("browser_qa")
    assert topo.index("model_user") < topo.index("be_service")


def test_cross_language_cycle_rejection():
    graph = CrossLanguageSemanticGraph()

    # React component consumes FastAPI -> FastAPI calls React (cycle!)
    graph.add_node(SemanticNode(node_id="react_ui", node_type=SemanticNodeType.FRONTEND_COMPONENT, ecosystem="react"))
    graph.add_node(SemanticNode(node_id="api_route", node_type=SemanticNodeType.API_CONTRACT, ecosystem="openapi"))
    graph.add_node(SemanticNode(node_id="fastapi_service", node_type=SemanticNodeType.BACKEND_SERVICE, ecosystem="fastapi"))

    graph.add_edge(SemanticEdge(edge_id="e1", source="fastapi_service", target="api_route", relation_type=SemanticRelationType.EXPOSES))
    graph.add_edge(SemanticEdge(edge_id="e2", source="api_route", target="react_ui", relation_type=SemanticRelationType.CONSUMES))

    # Attempting to add an edge from react_ui back to fastapi_service creates a cross-language cycle
    with pytest.raises(SemanticGraphCycleError):
        graph.add_edge(SemanticEdge(edge_id="e3_bad", source="react_ui", target="fastapi_service", relation_type=SemanticRelationType.CALLS))

    assert graph.get_edge("e3_bad") is None
