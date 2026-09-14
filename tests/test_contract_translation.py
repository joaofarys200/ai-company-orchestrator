"""
Tests for ApiSemanticContract registry and contract-first cross-language translation.
"""

import pytest
from agents.semantic_graph.contracts import ContractRegistry
from agents.semantic_graph.models import (
    ApiSemanticContract,
    ConfidenceClass,
    ValidationStatus,
)


def test_contract_registration_and_lookup():
    reg = ContractRegistry()

    contract = ApiSemanticContract(
        contract_id="contract_users_search",
        route="/api/v1/users/search",
        method="GET",
        request_schema={
            "type": "object",
            "properties": {
                "q": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["q"],
        },
        response_schema={
            "type": "object",
            "properties": {
                "items": {"type": "array"},
                "total": {"type": "integer"},
            },
        },
        version="v1",
        producer="backend_users_service",
        consumers=["frontend_search_box"],
    )

    reg.register_contract(contract)

    # Lookup by ID
    fetched = reg.get_contract("contract_users_search")
    assert fetched is not None
    assert fetched.route == "/api/v1/users/search"
    assert fetched.method == "GET"

    # Lookup by route
    matches = reg.find_by_route("GET", "/api/v1/users/search")
    assert len(matches) == 1
    assert matches[0].contract_id == "contract_users_search"


def test_contract_missing_yields_uncertain():
    reg = ContractRegistry()

    # Empty schemas representing uncontracted entities
    fe_schema = {}
    be_schema = {}

    report = reg.check_compatibility(fe_schema, be_schema, "missing_contract")
    assert report.status == ValidationStatus.UNCERTAIN
    assert report.confidence == ConfidenceClass.UNCERTAIN
    assert "Missing frontend or backend schema definition" in report.details


def test_name_similarity_never_proves_equivalence():
    """Invariant 14: Name similarity never proves equivalence without contractual or direct evidence."""
    reg = ContractRegistry()

    # Two components named "SearchService" but with incompatible or missing schemas
    fe_service_name = "SearchService.ts"
    be_service_name = "SearchService.py"

    # Both have the same name, but no explicit schema or contract is registered
    contracts = reg.find_by_route("GET", "/search_service")
    assert len(contracts) == 0

    # Checking compatibility without registered schemas must be UNCERTAIN, never VALID
    report = reg.check_compatibility({}, {}, "uncontracted_pair")
    assert report.status == ValidationStatus.UNCERTAIN
