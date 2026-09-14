"""Tests for Phase 47 Polymorphic Drift Detection and Classification."""
import pytest
from agents.polymorphic_schema.diff import PolymorphicDiffEngine
from agents.polymorphic_schema.models import (
    PolymorphicSchema,
    SchemaVariant,
    DiscriminatorDefinition,
    VariantDiffType,
    CompatibilityVerdict,
)


def test_polymorphic_drift_classification_new_variant():
    disc = DiscriminatorDefinition(field="type", observed_values=["alpha", "beta"])
    v_a = SchemaVariant(variant_id="va", label="Alpha", discriminator_value="alpha", required_fields=["id"])
    v_b = SchemaVariant(variant_id="vb", label="Beta", discriminator_value="beta", required_fields=["id"])

    baseline = PolymorphicSchema(
        schema_id="poly_test",
        route="/events",
        method="POST",
        discriminator=disc,
        variants=[v_a, v_b],
        common_fields=["id"],
    )

    # Runtime observes a third distinct variant: gamma
    runtime_obs = [
        {"type": "gamma", "id": "g1", "gamma_field": "val1"},
        {"type": "gamma", "id": "g2", "gamma_field": "val2"},
    ]

    report = PolymorphicDiffEngine.generate_drift_report(
        baseline_schema=baseline,
        observed_payloads=runtime_obs,
    )
    assert report.has_drift is True
    assert report.is_polymorphic_variation is True
    assert report.drift_classification == "POLYMORPHIC_VARIANTS"
    assert any(d.diff_type == VariantDiffType.VARIANT_ADDED for d in report.diffs)


def test_polymorphic_drift_discriminator_drift():
    disc = DiscriminatorDefinition(field="type", observed_values=["alpha"])
    v_a = SchemaVariant(variant_id="va", label="Alpha", discriminator_value="alpha", required_fields=["id"])
    baseline = PolymorphicSchema(
        schema_id="poly_test",
        route="/events",
        method="POST",
        discriminator=disc,
        variants=[v_a],
        common_fields=["id"],
    )

    # Runtime payloads suddenly use "event_type" instead of "type"
    runtime_obs = [
        {"event_type": "alpha", "id": "1"},
        {"event_type": "alpha", "id": "2"},
    ]
    report = PolymorphicDiffEngine.generate_drift_report(
        baseline_schema=baseline,
        observed_payloads=runtime_obs,
    )
    assert report.has_drift is True
    assert any(d.diff_type in (VariantDiffType.DISCRIMINATOR_CHANGED, VariantDiffType.DISCRIMINATOR_REMOVED) for d in report.diffs)
