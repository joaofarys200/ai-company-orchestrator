"""Tests for Phase 47 Polymorphic Diff Engine."""
import pytest
from agents.polymorphic_schema.diff import PolymorphicDiffEngine
from agents.polymorphic_schema.models import (
    PolymorphicSchema,
    SchemaVariant,
    DiscriminatorDefinition,
    VariantDiffType,
    CompatibilityVerdict,
)


def test_diff_variant_added():
    disc = DiscriminatorDefinition(field="type", observed_values=["user", "admin"])
    v_user = SchemaVariant(variant_id="vu", label="User", discriminator_value="user", required_fields=["id", "name"])
    v_admin = SchemaVariant(variant_id="va", label="Admin", discriminator_value="admin", required_fields=["id", "perms"])

    old_schema = PolymorphicSchema(
        schema_id="poly_1",
        route="/events",
        method="POST",
        discriminator=disc,
        variants=[v_user],
        common_fields=["id"],
    )
    new_schema = PolymorphicSchema(
        schema_id="poly_1",
        route="/events",
        method="POST",
        discriminator=disc,
        variants=[v_user, v_admin],
        common_fields=["id"],
    )

    diffs = PolymorphicDiffEngine.diff_schemas(old_schema, new_schema)
    assert any(d.diff_type == VariantDiffType.VARIANT_ADDED for d in diffs)
    added_diff = next(d for d in diffs if d.diff_type == VariantDiffType.VARIANT_ADDED)
    assert added_diff.variant_id == "va"
    assert added_diff.classification in (CompatibilityVerdict.NON_BREAKING, CompatibilityVerdict.POTENTIALLY_BREAKING)


def test_diff_variant_removed_is_breaking():
    disc = DiscriminatorDefinition(field="type", observed_values=["user", "admin"])
    v_user = SchemaVariant(variant_id="vu", label="User", discriminator_value="user", required_fields=["id", "name"])
    v_admin = SchemaVariant(variant_id="va", label="Admin", discriminator_value="admin", required_fields=["id", "perms"])

    old_schema = PolymorphicSchema(
        schema_id="poly_1",
        route="/events",
        method="POST",
        discriminator=disc,
        variants=[v_user, v_admin],
        common_fields=["id"],
    )
    new_schema = PolymorphicSchema(
        schema_id="poly_1",
        route="/events",
        method="POST",
        discriminator=disc,
        variants=[v_user],
        common_fields=["id"],
    )

    diffs = PolymorphicDiffEngine.diff_schemas(old_schema, new_schema)
    assert any(d.diff_type == VariantDiffType.VARIANT_REMOVED for d in diffs)
    removed_diff = next(d for d in diffs if d.diff_type == VariantDiffType.VARIANT_REMOVED)
    assert removed_diff.variant_id == "va"
    assert removed_diff.classification == CompatibilityVerdict.BREAKING


def test_diff_discriminator_changed_is_breaking():
    disc1 = DiscriminatorDefinition(field="type", observed_values=["a"])
    disc2 = DiscriminatorDefinition(field="kind", observed_values=["a"])
    v = SchemaVariant(variant_id="v1", label="A", discriminator_value="a")

    old_schema = PolymorphicSchema(schema_id="p", route="/r", method="POST", discriminator=disc1, variants=[v])
    new_schema = PolymorphicSchema(schema_id="p", route="/r", method="POST", discriminator=disc2, variants=[v])

    diffs = PolymorphicDiffEngine.diff_schemas(old_schema, new_schema)
    assert any(d.diff_type == VariantDiffType.DISCRIMINATOR_CHANGED for d in diffs)
    disc_diff = next(d for d in diffs if d.diff_type == VariantDiffType.DISCRIMINATOR_CHANGED)
    assert disc_diff.classification == CompatibilityVerdict.BREAKING


def test_diff_common_field_changed():
    disc = DiscriminatorDefinition(field="type", observed_values=["a"])
    v = SchemaVariant(variant_id="v1", label="A", discriminator_value="a")

    old_schema = PolymorphicSchema(schema_id="p", route="/r", method="POST", discriminator=disc, variants=[v], common_fields=["id", "created_at"])
    new_schema = PolymorphicSchema(schema_id="p", route="/r", method="POST", discriminator=disc, variants=[v], common_fields=["id"])

    diffs = PolymorphicDiffEngine.diff_schemas(old_schema, new_schema)
    assert any(d.diff_type == VariantDiffType.COMMON_FIELD_CHANGED for d in diffs)
