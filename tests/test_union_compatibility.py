"""Tests for Phase 47 Schema and Variant Compatibility Engine."""
import pytest
from agents.polymorphic_schema.compatibility import PolymorphicCompatibilityEngine
from agents.polymorphic_schema.models import (
    PolymorphicSchema,
    SchemaVariant,
    DiscriminatorDefinition,
    CompatibilityVerdict,
    VariantStatus,
    PolymorphicSchemaKind,
)


def test_pairwise_identical_variants_compatible():
    v_old = SchemaVariant(
        variant_id="v1",
        label="UserV1",
        schema={"properties": {"name": {"type": "string"}}},
        required_fields=["id", "name"],
        discriminator_value="user",
    )
    v_new = SchemaVariant(
        variant_id="v1",
        label="UserV1",
        schema={"properties": {"name": {"type": "string"}}},
        required_fields=["id", "name"],
        discriminator_value="user",
    )
    verdict, reasons = PolymorphicCompatibilityEngine.check_variant_compatibility(v_old, v_new)
    assert verdict == CompatibilityVerdict.COMPATIBLE


def test_pairwise_added_optional_field_compatible():
    v_old = SchemaVariant(
        variant_id="v1",
        label="UserV1",
        schema={"properties": {"name": {"type": "string"}}},
        required_fields=["id", "name"],
        discriminator_value="user",
    )
    v_new = SchemaVariant(
        variant_id="v1",
        label="UserV1",
        schema={"properties": {"name": {"type": "string"}, "nickname": {"type": "string"}}},
        required_fields=["id", "name"],
        optional_fields=["nickname"],
        discriminator_value="user",
    )
    verdict, reasons = PolymorphicCompatibilityEngine.check_variant_compatibility(v_old, v_new)
    assert verdict == CompatibilityVerdict.COMPATIBLE


def test_pairwise_removed_required_field_breaking():
    v_old = SchemaVariant(
        variant_id="v1",
        label="UserV1",
        schema={"properties": {"name": {"type": "string"}}},
        required_fields=["id", "name"],
        discriminator_value="user",
    )
    v_new = SchemaVariant(
        variant_id="v1",
        label="UserV1",
        schema={"properties": {}},
        required_fields=["id"],
        discriminator_value="user",
    )
    verdict, reasons = PolymorphicCompatibilityEngine.check_variant_compatibility(v_old, v_new)
    assert verdict == CompatibilityVerdict.BREAKING


def test_pairwise_different_discriminator_incompatible():
    v_old = SchemaVariant(
        variant_id="v1",
        label="UserV1",
        schema={"properties": {"id": {"type": "string"}}},
        required_fields=["id"],
        discriminator_value="user",
    )
    v_new = SchemaVariant(
        variant_id="v2",
        label="AdminV1",
        schema={"properties": {"id": {"type": "string"}}},
        required_fields=["id"],
        discriminator_value="admin",
    )
    verdict, reasons = PolymorphicCompatibilityEngine.check_variant_compatibility(v_old, v_new)
    assert verdict == CompatibilityVerdict.INCOMPATIBLE


def test_schema_matrix_additive_variant_potentially_compatible():
    disc = DiscriminatorDefinition(field="type", observed_values=["a", "b"])
    v_a = SchemaVariant(variant_id="va", label="A", required_fields=["id"], discriminator_value="a")
    v_b = SchemaVariant(variant_id="vb", label="B", required_fields=["id"], discriminator_value="b")
    v_c = SchemaVariant(variant_id="vc", label="C", required_fields=["id"], discriminator_value="c")

    schema_old = PolymorphicSchema(
        schema_id="poly_test",
        route="/test",
        method="POST",
        discriminator=disc,
        variants=[v_a, v_b],
    )
    schema_new = PolymorphicSchema(
        schema_id="poly_test",
        route="/test",
        method="POST",
        discriminator=disc,
        variants=[v_a, v_b, v_c],
    )

    matrix = PolymorphicCompatibilityEngine.compute_matrix(schema_old, schema_new)
    assert matrix.overall_verdict in (CompatibilityVerdict.POTENTIALLY_BREAKING, CompatibilityVerdict.POTENTIALLY_COMPATIBLE, CompatibilityVerdict.COMPATIBLE)
    assert len(matrix.pairwise_results) >= 2
