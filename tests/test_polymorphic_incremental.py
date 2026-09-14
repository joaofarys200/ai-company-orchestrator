"""Tests for Phase 47 Incremental Polymorphic Schema Updates."""
import pytest
from agents.polymorphic_schema.detector import PolymorphicDetector
from agents.polymorphic_schema.models import PolymorphicSchema, SchemaVariant, DiscriminatorDefinition


def test_incremental_update_single_family_blast_radius():
    disc = DiscriminatorDefinition(field="type", observed_values=["alpha", "beta"])
    v_a = SchemaVariant(variant_id="va", label="Alpha", discriminator_value="alpha", required_fields=["id"])
    v_b = SchemaVariant(variant_id="vb", label="Beta", discriminator_value="beta", required_fields=["id"])

    family_events = PolymorphicSchema(
        schema_id="poly_events",
        route="/api/events",
        method="POST",
        discriminator=disc,
        variants=[v_a, v_b],
    )
    family_payments = PolymorphicSchema(
        schema_id="poly_payments",
        route="/api/payments",
        method="POST",
        common_fields=["charge_id"],
    )

    all_schemas = {
        "poly_events": family_events,
        "poly_payments": family_payments,
    }

    # New observation arrived for /api/events
    new_obs = {"type": "alpha", "id": "123", "extra": "data"}

    # Process incrementally
    updated_family_id, blast_radius = PolymorphicDetector.process_incremental_observation(
        schemas=all_schemas,
        target_route="/api/events",
        method="POST",
        observation=new_obs,
    )

    assert updated_family_id == "poly_events"
    assert blast_radius == 1
    # Ensure payments schema remains completely untouched
    assert all_schemas["poly_payments"].common_fields == ["charge_id"]
