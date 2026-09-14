"""Tests for Phase 47 Polymorphic Consumer Impact Analysis."""
import pytest
from agents.polymorphic_schema.consumers import PolymorphicConsumerAnalyzer
from agents.polymorphic_schema.models import (
    PolymorphicSchema,
    SchemaVariant,
    DiscriminatorDefinition,
    ConsumerVariantStance,
)


def test_consumer_already_tolerates_common_fields():
    # Consumer only consumes common fields ("id", "type"), ignores payload
    consumer_meta = {
        "consumer_id": "audit_logger",
        "consumed_fields": ["id", "type"],
        "strict_types": False,
    }
    new_variant = SchemaVariant(
        variant_id="var_new",
        label="NewVariant",
        discriminator_value="new_type",
        required_fields=["id", "type", "special_data"],
    )
    schema = PolymorphicSchema(
        schema_id="p1",
        route="/events",
        method="POST",
        common_fields=["id", "type"],
        discriminator=DiscriminatorDefinition(field="type"),
    )
    impact = PolymorphicConsumerAnalyzer.assess_consumer_impact(
        consumer_metadata=consumer_meta,
        polymorphic_schema=schema,
        new_variant=new_variant,
    )
    assert impact.stance == ConsumerVariantStance.ALREADY_TOLERATES


def test_consumer_explicitly_rejects_unknown_types():
    consumer_meta = {
        "consumer_id": "strict_worker",
        "consumed_fields": ["id", "type", "payload"],
        "strict_types": True,
        "supported_discriminators": ["alpha", "beta"],
    }
    new_variant = SchemaVariant(
        variant_id="var_gamma",
        label="Gamma",
        discriminator_value="gamma",
        required_fields=["id", "type", "gamma_val"],
    )
    schema = PolymorphicSchema(
        schema_id="p1",
        route="/events",
        method="POST",
        common_fields=["id", "type"],
        discriminator=DiscriminatorDefinition(field="type"),
    )
    impact = PolymorphicConsumerAnalyzer.assess_consumer_impact(
        consumer_metadata=consumer_meta,
        polymorphic_schema=schema,
        new_variant=new_variant,
    )
    assert impact.stance in (ConsumerVariantStance.EXPLICITLY_REJECTS, ConsumerVariantStance.UNCERTAIN)


def test_consumer_ignores_unrelated_events():
    consumer_meta = {
        "consumer_id": "billing_svc",
        "consumed_fields": ["invoice_id"],
        "target_filter": "billing.*",
    }
    new_variant = SchemaVariant(
        variant_id="var_auth",
        label="AuthEvent",
        discriminator_value="auth.login",
        required_fields=["id", "session_id"],
    )
    schema = PolymorphicSchema(
        schema_id="p1",
        route="/events",
        method="POST",
        common_fields=["id"],
        discriminator=DiscriminatorDefinition(field="type"),
    )
    impact = PolymorphicConsumerAnalyzer.assess_consumer_impact(
        consumer_metadata=consumer_meta,
        polymorphic_schema=schema,
        new_variant=new_variant,
    )
    assert impact.stance == ConsumerVariantStance.IGNORES
