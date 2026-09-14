"""
Tests for Phase 45 — ContractDiffEngine.
Verifies detection of schema differences:
ADDED_FIELD, REMOVED_FIELD, TYPE_CHANGED, NULLABILITY_CHANGED, REQUIRED_CHANGED,
and breakage classification: NON_BREAKING, POTENTIALLY_BREAKING, BREAKING.
"""

import pytest
from agents.runtime_discovery.diff import ContractDiffEngine
from agents.runtime_discovery.models import (
    FieldDiffType,
    DiffSeverity,
    InferredSchema,
)


def test_contract_diff_non_breaking_added_optional_field():
    engine = ContractDiffEngine()

    base_schema = InferredSchema(
        schema_name="User",
        fields={
            "id": {"type": "integer", "is_required": True, "is_nullable": False},
            "name": {"type": "string", "is_required": True, "is_nullable": False},
        },
    )

    new_schema = InferredSchema(
        schema_name="User",
        fields={
            "id": {"type": "integer", "is_required": True, "is_nullable": False},
            "name": {"type": "string", "is_required": True, "is_nullable": False},
            "bio": {"type": "string", "is_required": False, "is_nullable": True},  # added optional
        },
    )

    diff = engine.compare_schemas(base_schema, new_schema)
    assert diff.severity == DiffSeverity.NON_BREAKING
    assert len(diff.differences) == 1
    assert diff.differences[0].diff_type == FieldDiffType.ADDED_FIELD
    assert diff.differences[0].field_path == "bio"


def test_contract_diff_breaking_type_change():
    engine = ContractDiffEngine()

    base_schema = InferredSchema(
        schema_name="Payload",
        fields={"count": {"type": "integer", "is_required": True, "is_nullable": False}},
    )

    new_schema = InferredSchema(
        schema_name="Payload",
        fields={"count": {"type": "string", "is_required": True, "is_nullable": False}},  # int -> string
    )

    diff = engine.compare_schemas(base_schema, new_schema)
    assert diff.severity == DiffSeverity.BREAKING
    assert any(d.diff_type == FieldDiffType.TYPE_CHANGED for d in diff.differences)


def test_contract_diff_breaking_removed_field():
    engine = ContractDiffEngine()

    base_schema = InferredSchema(
        schema_name="Product",
        fields={
            "id": {"type": "integer", "is_required": True, "is_nullable": False},
            "price": {"type": "float", "is_required": True, "is_nullable": False},
        },
    )

    new_schema = InferredSchema(
        schema_name="Product",
        fields={
            "id": {"type": "integer", "is_required": True, "is_nullable": False},
        },
    )

    diff = engine.compare_schemas(base_schema, new_schema)
    # Removing a required field from a response schema is BREAKING
    assert diff.severity == DiffSeverity.BREAKING
    assert any(d.diff_type == FieldDiffType.REMOVED_FIELD for d in diff.differences)


def test_contract_diff_potentially_breaking_nullability():
    engine = ContractDiffEngine()

    base_schema = InferredSchema(
        schema_name="Order",
        fields={"total": {"type": "float", "is_required": True, "is_nullable": False}},
    )

    new_schema = InferredSchema(
        schema_name="Order",
        fields={"total": {"type": "float", "is_required": True, "is_nullable": True}},  # became nullable
    )

    diff = engine.compare_schemas(base_schema, new_schema)
    assert diff.severity == DiffSeverity.POTENTIALLY_BREAKING
    assert any(d.diff_type == FieldDiffType.NULLABILITY_CHANGED for d in diff.differences)
