"""
Tests for SchemaCompatibilityEngine, type normalization, and contract versioning.
"""

import pytest
from agents.semantic_graph.contracts import ContractRegistry
from agents.semantic_graph.models import (
    ApiSemanticContract,
    ConflictType,
    ContractVersionStatus,
    ValidationStatus,
)


def test_schema_compatibility_success():
    reg = ContractRegistry()

    fe_schema = {
        "properties": {
            "id": "string",
            "name": "string",
            "age": "number",
            "tags": "array",
        },
        "required": ["id", "name"],
    }

    be_schema = {
        "properties": {
            "id": "str",
            "name": "str",
            "age": "int",
            "tags": "list",
        },
        "required": ["id", "name"],
    }

    report = reg.check_compatibility(fe_schema, be_schema, "contract_test_ok")
    assert report.status == ValidationStatus.VALID
    assert len(report.conflicts) == 0
    assert report.version_status == ContractVersionStatus.COMPATIBLE


def test_schema_conflict_type_mismatch():
    """Section 26: Frontend expects string, backend responds object -> SCHEMA_CONFLICT."""
    reg = ContractRegistry()

    fe_schema = {
        "properties": {
            "avatar": "string",  # Expects URL string
        }
    }

    be_schema = {
        "properties": {
            "avatar": "dict",  # Produces nested dictionary/object
        }
    }

    report = reg.check_compatibility(fe_schema, be_schema, "contract_avatar_mismatch")
    assert report.status == ValidationStatus.INVALID
    assert len(report.conflicts) == 1
    diff = report.conflicts[0]
    assert diff.field_name == "avatar"
    assert diff.conflict_type == ConflictType.SCHEMA_CONFLICT
    assert "frontend expects STRING, but backend produces OBJECT" in diff.message


def test_schema_missing_required_field():
    reg = ContractRegistry()

    fe_schema = {
        "properties": {
            "email": "string",
            "department_id": "string",
        },
        "required": ["email", "department_id"],
    }

    be_schema = {
        "properties": {
            "email": "string",
        },
        "required": ["email"],
    }

    report = reg.check_compatibility(fe_schema, be_schema, "contract_missing_field")
    assert report.status == ValidationStatus.INVALID
    assert len(report.conflicts) == 1
    assert report.conflicts[0].field_name == "department_id"
    assert "CRITICAL: Required field" in report.conflicts[0].message


def test_contract_version_compatibility_v1_vs_v2():
    reg = ContractRegistry()

    v1 = ApiSemanticContract(
        contract_id="api_users_v1",
        route="/api/v1/users",
        method="GET",
        response_schema={"properties": {"id": "str", "name": "str"}},
        version="v1.0.0",
    )

    # v2 with breaking change (changed type of id to object)
    v2_breaking = ApiSemanticContract(
        contract_id="api_users_v2",
        route="/api/v1/users",
        method="GET",
        response_schema={"properties": {"id": "dict", "name": "str"}},
        version="v2.0.0",
    )

    status, reasons = reg.check_version_compatibility(v1, v2_breaking)
    assert status == ContractVersionStatus.INCOMPATIBLE
    assert len(reasons) > 0

    # v2 with compatible addition of optional field
    v2_compatible = ApiSemanticContract(
        contract_id="api_users_v2_opt",
        route="/api/v1/users",
        method="GET",
        response_schema={"properties": {"id": "str", "name": "str", "nickname": "str"}},
        version="v2.0.0",
    )

    status_opt, reasons_opt = reg.check_version_compatibility(v1, v2_compatible)
    assert status_opt == ContractVersionStatus.REQUIRES_REVALIDATION
    assert any("New optional fields" in r for r in reasons_opt)
