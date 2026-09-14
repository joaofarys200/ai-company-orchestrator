"""
JARVIS OS — Phase 46: Consumer Impact Test Suite
Validates contract consumer registry and semantic graph downstream discovery.
"""

from agents.contract_governance.consumers import ContractConsumerRegistry
from agents.contract_governance.models import ConsumerImpact, ConsumerImpactLevel
from agents.semantic_graph.graph import CrossLanguageSemanticGraph
from agents.semantic_graph.models import (
    ConfidenceClass,
    SemanticEdge,
    SemanticNode,
    SemanticNodeType,
    SemanticRelationType,
)


def test_consumer_registry_direct():
    registry = ContractConsumerRegistry()
    c1 = ConsumerImpact(
        consumer_id="SearchBox.tsx",
        consumer_type="FRONTEND_COMPONENT",
        impact_level=ConsumerImpactLevel.DIRECT,
        description="Search input component",
    )
    registry.register_consumer("contract_search", c1)
    # Register again (idempotent)
    registry.register_consumer("contract_search", c1)

    consumers = registry.get_consumers("contract_search")
    assert len(consumers) == 1
    assert consumers[0].consumer_id == "SearchBox.tsx"


def test_consumer_discovery_from_semantic_graph():
    graph = CrossLanguageSemanticGraph()
    registry = ContractConsumerRegistry()

    # Add API contract node
    graph.add_node(
        SemanticNode(
            node_id="api_users_search",
            name="GET /api/v1/users/search",
            type=SemanticNodeType.API_CONTRACT,
            ecosystem="API",
            metadata={"contract_id": "contract_users_search"},
        )
    )

    # Add Frontend consumer
    graph.add_node(
        SemanticNode(
            node_id="fe_searchbox",
            name="SearchBox.tsx",
            type=SemanticNodeType.FRONTEND_COMPONENT,
            ecosystem="TS_REACT",
        )
    )
    graph.add_edge(
        SemanticEdge(
            edge_id="e_fe_api",
            source_id="fe_searchbox",
            target_id="api_users_search",
            relation=SemanticRelationType.CONSUMES,
            confidence=ConfidenceClass.CONTRACTUAL,
        )
    )

    # Add Test consumer
    graph.add_node(
        SemanticNode(
            node_id="test_users",
            name="test_users.py",
            type=SemanticNodeType.TEST,
            ecosystem="PY_FASTAPI",
        )
    )
    graph.add_edge(
        SemanticEdge(
            edge_id="e_test_api",
            source_id="test_users",
            target_id="api_users_search",
            relation=SemanticRelationType.TESTS,
            confidence=ConfidenceClass.DIRECT,
        )
    )

    discovered = registry.discover_consumers_from_graph(graph, contract_id="contract_users_search")
    assert len(discovered) >= 2
    consumer_ids = [d.consumer_id for d in discovered]
    assert "fe_searchbox" in consumer_ids
    assert "test_users" in consumer_ids
