"""Tests for Phase 47 Polymorphic variant detection and clustering."""
import pytest
from agents.polymorphic_schema.detector import PolymorphicDetector
from agents.polymorphic_schema.models import PolymorphicSchemaKind, VariantStatus


def test_detect_discriminated_union_from_observations():
    observations = [
        {"type": "user", "id": "u1", "name": "Alice", "email": "alice@ex.com"},
        {"type": "user", "id": "u2", "name": "Bob", "email": "bob@ex.com"},
        {"type": "admin", "id": "a1", "name": "Charlie", "permissions": ["sudo"]},
        {"type": "admin", "id": "a2", "name": "David", "permissions": ["root"]},
    ]
    poly = PolymorphicDetector.detect_polymorphism(
        route="/api/users",
        method="POST",
        observations=observations,
    )
    assert poly is not None
    assert poly.kind == PolymorphicSchemaKind.DISCRIMINATED_UNION
    assert poly.status in (VariantStatus.DETERMINISTIC, VariantStatus.VALIDATED)
    assert len(poly.variants) == 2
    # Common fields: type, id, name
    assert "id" in poly.common_fields
    assert "name" in poly.common_fields
    assert "type" in poly.common_fields
    # Variant fields: email, permissions
    assert "email" in poly.variant_fields
    assert "permissions" in poly.variant_fields

    v_user = poly.get_variant_by_discriminator("user")
    assert v_user is not None
    assert "email" in v_user.required_fields
    assert "permissions" in v_user.forbidden_fields

    v_admin = poly.get_variant_by_discriminator("admin")
    assert v_admin is not None
    assert "permissions" in v_admin.required_fields
    assert "email" in v_admin.forbidden_fields


def test_detect_three_variants():
    observations = [
        {"kind": "dog", "name": "Rex", "bark_volume": 80},
        {"kind": "cat", "name": "Luna", "lives_left": 9},
        {"kind": "bird", "name": "Polly", "wingspan": 25},
    ]
    poly = PolymorphicDetector.detect_polymorphism(
        route="/api/pets",
        method="GET",
        observations=observations,
    )
    assert poly is not None
    assert len(poly.variants) == 3
    assert set(poly.common_fields) == {"kind", "name"}
    assert poly.discriminator.field == "kind"


def test_detect_ambiguous_variants_uncertain_status():
    # Subtle overlap without discriminator
    observations = [
        {"id": "1", "title": "Task 1", "completed": True},
        {"id": "2", "title": "Task 2", "completed": False, "priority": "high"},
    ]
    poly = PolymorphicDetector.detect_polymorphism(
        route="/api/tasks",
        method="GET",
        observations=observations,
    )
    # Without discriminator, this should not guess distinct variants authoritatively
    # If returned as union, status must be UNCERTAIN
    if poly:
        assert poly.status == VariantStatus.UNCERTAIN or poly.kind == PolymorphicSchemaKind.UNKNOWN_POLYMORPHIC_RESPONSE


def test_detect_single_schema_when_no_variants():
    observations = [
        {"id": "1", "val": 10},
        {"id": "2", "val": 20},
    ]
    poly = PolymorphicDetector.detect_polymorphism(
        route="/api/item",
        method="GET",
        observations=observations,
    )
    # Either returns None or SINGLE_SCHEMA
    if poly:
        assert poly.kind == PolymorphicSchemaKind.SINGLE_SCHEMA
