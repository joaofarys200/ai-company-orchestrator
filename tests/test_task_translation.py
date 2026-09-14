"""
Tests for SemanticTaskTranslator and cross-language task dependency ordering.
"""

import pytest
from agents.semantic_graph.adapters import SemanticAdapterRegistry
from agents.semantic_graph.contracts import ContractRegistry
from agents.semantic_graph.graph import CrossLanguageSemanticGraph
from agents.semantic_graph.models import (
    ConfidenceClass,
    SemanticEdge,
    SemanticNode,
    SemanticNodeType,
    SemanticRelationType,
    TranslatedTask,
)
from agents.semantic_graph.translator import SemanticTaskTranslator


def test_task_translation_ordering_and_dependencies():
    """Section 10 & 12: Translates feature intent into ordered tasks with explicit dependency direction."""
    graph = CrossLanguageSemanticGraph()
    contracts = ContractRegistry()
    adapters = SemanticAdapterRegistry()

    # Build semantic graph for search
    graph.add_node(SemanticNode(node_id="arch_search", node_type=SemanticNodeType.ARCHITECTURE_COMPONENT))
    graph.add_node(SemanticNode(node_id="db_search", node_type=SemanticNodeType.PERSISTENCE_OPERATION, ecosystem="postgres"))
    graph.add_node(SemanticNode(node_id="be_search", node_type=SemanticNodeType.BACKEND_SERVICE, ecosystem="fastapi"))
    graph.add_node(SemanticNode(node_id="api_search", node_type=SemanticNodeType.API_CONTRACT, ecosystem="openapi"))
    graph.add_node(SemanticNode(node_id="fe_search", node_type=SemanticNodeType.FRONTEND_COMPONENT, ecosystem="react"))
    graph.add_node(SemanticNode(node_id="qa_search", node_type=SemanticNodeType.BROWSER_SCENARIO, ecosystem="playwright"))

    # Edges from arch to all
    for tgt in ["db_search", "be_search", "api_search", "fe_search", "qa_search"]:
        graph.add_edge(SemanticEdge(edge_id=f"e_{tgt}", source="arch_search", target=tgt, relation_type=SemanticRelationType.IMPLEMENTS))

    # Explicit frontend consumes contract edge
    graph.add_edge(SemanticEdge(edge_id="e_fe_api", source="fe_search", target="api_search", relation_type=SemanticRelationType.CONSUMES))

    translator = SemanticTaskTranslator(graph, contracts, adapters)
    tasks = translator.translate_feature_intent("Implement Fast User Search", "arch_search")

    assert len(tasks) >= 5

    task_map = {t.target_domain: t for t in tasks}

    assert "persistence" in task_map
    assert "backend" in task_map
    assert "api" in task_map
    assert "frontend" in task_map
    assert "browser" in task_map

    # Invariant: backend depends on persistence
    assert task_map["persistence"].task_id in task_map["backend"].dependencies

    # Invariant: API depends on backend
    assert task_map["backend"].task_id in task_map["api"].dependencies

    # Invariant: Frontend depends on API contract
    assert task_map["api"].task_id in task_map["frontend"].dependencies

    # Invariant: Browser depends on Frontend
    assert task_map["frontend"].task_id in task_map["browser"].dependencies

    # Invariant: Confidence class is CONTRACTUAL
    assert task_map["frontend"].confidence_class == ConfidenceClass.CONTRACTUAL
    assert len(task_map["frontend"].evidence) > 0


def test_task_dependency_reversal_rejected():
    """Section 12: Attempting to make an API task depend on a downstream Frontend task is rejected."""
    graph = CrossLanguageSemanticGraph()
    contracts = ContractRegistry()
    translator = SemanticTaskTranslator(graph, contracts)

    fe_task = TranslatedTask(task_id="t_fe", source_task="UI", target_domain="frontend")
    api_task = TranslatedTask(task_id="t_api", source_task="API", target_domain="api")

    # Legal: Frontend depends on API
    ok, msg = translator.translate_task_dependency(fe_task, api_task)
    assert ok is True
    assert "t_api" in fe_task.dependencies

    # Illegal: API depends on Frontend
    illegal_ok, illegal_msg = translator.translate_task_dependency(api_task, fe_task)
    assert illegal_ok is False
    assert "INVALID DEPENDENCY DIRECTION" in illegal_msg
