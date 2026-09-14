"""
Tests for SemanticAdapter contracts, validation rules, and SemanticAdapterRegistry.
"""

import pytest
from agents.semantic_graph.adapters import SemanticAdapter, SemanticAdapterRegistry
from agents.semantic_graph.models import (
    ConfidenceClass,
    SemanticNode,
    SemanticNodeType,
    SemanticRelationType,
    ValidationStatus,
)


def test_default_adapters_registration():
    reg = SemanticAdapterRegistry()
    adapters = reg.list_adapters()
    assert len(adapters) >= 8

    # Verify key adapters exist
    assert reg.get_adapter("TS_FRONTEND_TO_API") is not None
    assert reg.get_adapter("API_TO_FASTAPI_BACKEND") is not None
    assert reg.get_adapter("BACKEND_TO_PERSISTENCE") is not None
    assert reg.get_adapter("TEST_TO_TARGET") is not None
    assert reg.get_adapter("BROWSER_TO_FRONTEND") is not None


def test_frontend_to_api_adapter_validation():
    reg = SemanticAdapterRegistry()

    fe_node = SemanticNode(
        node_id="fe_search",
        node_type=SemanticNodeType.FRONTEND_COMPONENT,
        ecosystem="react",
        language="typescript",
    )
    api_node = SemanticNode(
        node_id="api_search",
        node_type=SemanticNodeType.API_CONTRACT,
        ecosystem="openapi",
    )

    # Valid CONSUMES relation
    adapter, status, reason = reg.resolve_adapter(fe_node, api_node, SemanticRelationType.CONSUMES)
    assert adapter is not None
    assert adapter.adapter_id == "TS_FRONTEND_TO_API"
    assert status == ValidationStatus.VALID

    # Invalid relation for this pair (e.g. PERSISTS)
    adapter, status, reason = reg.resolve_adapter(fe_node, api_node, SemanticRelationType.PERSISTS)
    assert status == ValidationStatus.UNCERTAIN or status == ValidationStatus.INVALID


def test_multi_ecosystem_matrix():
    reg = SemanticAdapterRegistry()

    api_node = SemanticNode(node_id="api", node_type=SemanticNodeType.API_CONTRACT, ecosystem="openapi")

    matrix = [
        ("fastapi", "API_TO_FASTAPI_BACKEND"),
        ("django", "API_TO_DJANGO_BACKEND"),
        ("node", "API_TO_NODE_BACKEND"),
        ("express", "API_TO_EXPRESS_BACKEND"),
        ("java", "API_TO_JAVA_BACKEND"),
        ("python", "API_TO_PYTHON_GENERIC"),
    ]

    for eco, expected_adapter in matrix:
        be_node = SemanticNode(node_id=f"be_{eco}", node_type=SemanticNodeType.BACKEND_SERVICE, ecosystem=eco)
        adapter, status, _ = reg.resolve_adapter(api_node, be_node, SemanticRelationType.SERVES)
        assert adapter is not None, f"Expected adapter for {eco}"
        assert adapter.adapter_id == expected_adapter
        assert status == ValidationStatus.VALID


def test_unsupported_adapter_returns_uncertain():
    reg = SemanticAdapterRegistry()

    # Weird unsupported combo: React frontend directly 'PERSISTS' to a legacy cobol service
    fe_node = SemanticNode(node_id="fe", node_type=SemanticNodeType.FRONTEND_COMPONENT, ecosystem="react")
    cobol_node = SemanticNode(node_id="cobol", node_type=SemanticNodeType.BACKEND_SERVICE, ecosystem="cobol")

    adapter, status, reason = reg.resolve_adapter(fe_node, cobol_node, SemanticRelationType.PERSISTS)
    # Must NOT hallucinate or pretend it's valid
    assert status == ValidationStatus.UNCERTAIN
    assert "No formal adapter exists" in reason
