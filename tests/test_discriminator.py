"""Tests for Phase 47 Discriminator resolution and inference."""
import pytest
from agents.polymorphic_schema.discriminator import DiscriminatorEngine
from agents.polymorphic_schema.models import DiscriminatorLocation, DiscriminatorType


def test_explicit_discriminator_detection_in_body():
    payloads = [
        {"type": "user.created", "user_id": "u1", "email": "u1@test.com"},
        {"type": "user.deleted", "user_id": "u2", "deletion_reason": "gdpr"},
    ]
    disc = DiscriminatorEngine.detect_discriminator(payloads)
    assert disc is not None
    assert disc.is_explicit is True
    assert disc.field == "type"
    assert disc.location == DiscriminatorLocation.BODY
    assert disc.type == DiscriminatorType.STRING_ENUM
    assert set(disc.observed_values) == {"user.created", "user.deleted"}
    assert disc.confidence == 1.0


def test_discriminator_header_and_query_fallback():
    # If explicitly passed in headers
    headers = {"x-event-type": "order.paid"}
    val, loc = DiscriminatorEngine.resolve_value_from_request("x-event-type", body={}, headers=headers)
    assert val == "order.paid"
    assert loc == DiscriminatorLocation.HEADER

    # Query
    val_q, loc_q = DiscriminatorEngine.resolve_value_from_request("action", body={}, query={"action": "export"})
    assert val_q == "export"
    assert loc_q == DiscriminatorLocation.QUERY


def test_inferred_structural_discriminator():
    # When no explicit keyword (type, kind, etc.) exists, but distinct sets of fields exist
    payloads = [
        {"id": "1", "name": "Alice", "email": "alice@ex.com"},
        {"id": "2", "name": "Bob", "permissions": ["admin", "read"]},
    ]
    disc = DiscriminatorEngine.detect_discriminator(payloads)
    assert disc is not None
    assert disc.is_explicit is False
    assert disc.type == DiscriminatorType.INFERRED_STRUCTURAL
    assert "permissions" in disc.field or "email" in disc.field


def test_ambiguity_detection_overlapping_fields():
    # Ambiguous shapes without clear discriminator:
    # A has {name, email}
    # B has {name, email, permissions} where permissions could just be an optional field
    payloads = [
        {"name": "Alice", "email": "alice@ex.com"},
        {"name": "Bob", "email": "bob@ex.com", "permissions": ["read"]},
    ]
    is_ambiguous, reason = DiscriminatorEngine.check_ambiguity(payloads)
    assert is_ambiguous is True
    assert "UNCERTAIN" in reason or "optional" in reason


def test_no_discriminator_single_shape():
    payloads = [
        {"id": "1", "status": "active"},
        {"id": "2", "status": "active"},
    ]
    # Here status has only 1 distinct value, so it's not a discriminator across variants
    disc = DiscriminatorEngine.detect_discriminator(payloads)
    assert disc is None or len(disc.observed_values) <= 1
