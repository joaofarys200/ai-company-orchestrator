"""Tests for Phase 47 PolymorphicSchema and SchemaVariant data models."""
import pytest
from agents.polymorphic_schema.models import (
    PolymorphicSchema,
    SchemaVariant,
    ErrorVariant,
    DiscriminatorDefinition,
    PolymorphicSchemaKind,
    VariantStatus,
    DiscriminatorLocation,
    DiscriminatorType,
)


def test_polymorphic_schema_creation():
    disc = DiscriminatorDefinition(
        field="type",
        location=DiscriminatorLocation.BODY,
        type=DiscriminatorType.STRING_ENUM,
        observed_values=["user.created", "user.deleted"],
        is_explicit=True,
        confidence=1.0,
    )
    v1 = SchemaVariant(
        variant_id="var_created",
        label="UserCreated",
        schema={"properties": {"user_id": {"type": "string"}}},
        required_fields=["id", "user_id"],
        forbidden_fields=["deletion_reason"],
        observed_count=100,
        confidence=1.0,
        status=VariantStatus.VALIDATED,
        discriminator_value="user.created",
    )
    v2 = SchemaVariant(
        variant_id="var_deleted",
        label="UserDeleted",
        schema={"properties": {"deletion_reason": {"type": "string"}}},
        required_fields=["id", "deletion_reason"],
        forbidden_fields=["user_id"],
        observed_count=50,
        confidence=1.0,
        status=VariantStatus.VALIDATED,
        discriminator_value="user.deleted",
    )
    poly = PolymorphicSchema(
        schema_id="poly_events",
        route="/events",
        method="POST",
        kind=PolymorphicSchemaKind.DISCRIMINATED_UNION,
        status=VariantStatus.VALIDATED,
        discriminator=disc,
        variants=[v1, v2],
        common_fields=["id"],
        variant_fields=["user_id", "deletion_reason"],
    )

    assert poly.schema_id == "poly_events"
    assert poly.kind == PolymorphicSchemaKind.DISCRIMINATED_UNION
    assert len(poly.variants) == 2
    assert poly.common_fields == ["id"]
    assert "user_id" in poly.variant_fields
    assert "deletion_reason" in poly.variant_fields
    assert poly.get_variant_by_discriminator("user.created") == v1
    assert poly.get_variant_by_discriminator("user.deleted") == v2
    assert poly.get_variant_by_discriminator("unknown") is None


def test_schema_variant_validation_and_requiredness():
    v = SchemaVariant(
        variant_id="var_admin",
        label="AdminUser",
        schema={"properties": {"role": {"type": "string"}}},
        required_fields=["role", "permissions"],
        forbidden_fields=["guest_token"],
        nullable_fields=["avatar_url"],
        observed_count=10,
        status=VariantStatus.INFERRED,
    )
    assert v.status == VariantStatus.INFERRED
    assert "role" in v.required_fields
    assert "guest_token" in v.forbidden_fields
    assert "avatar_url" in v.nullable_fields

    d = v.to_dict()
    assert d["variant_id"] == "var_admin"
    assert d["status"] == "INFERRED"
    assert "permissions" in d["required_fields"]


def test_error_variant_polymorphism():
    err_400 = ErrorVariant(
        status_code=400,
        error_code="VALIDATION_ERROR",
        schema={"properties": {"invalid_fields": {"type": "array"}}},
        required_fields=["error", "invalid_fields"],
        description="Payload schema validation failure",
    )
    err_409 = ErrorVariant(
        status_code=409,
        error_code="CONFLICT_ERROR",
        schema={"properties": {"conflict_id": {"type": "string"}}},
        required_fields=["error", "conflict_id"],
        description="Resource state conflict",
    )
    assert err_400.status_code == 400
    assert err_409.error_code == "CONFLICT_ERROR"
    assert "invalid_fields" in err_400.required_fields
    assert "conflict_id" in err_409.required_fields


def test_polymorphic_schema_serialization_roundtrip():
    poly = PolymorphicSchema(
        schema_id="poly_test",
        route="/test",
        method="GET",
        status=VariantStatus.DETERMINISTIC,
        common_fields=["id", "timestamp"],
    )
    d = poly.to_dict()
    assert d["schema_id"] == "poly_test"
    assert d["status"] == "DETERMINISTIC"
    assert d["common_fields"] == ["id", "timestamp"]
