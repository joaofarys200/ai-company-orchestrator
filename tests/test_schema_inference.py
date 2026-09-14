"""
Tests for Phase 45 — SchemaInferenceEngine.
Verifies safe schema inference: primitive types, missing != null distinction,
requiredness threshold (100% presence AND >= 3 samples), enum candidate detection,
and error contract tracking.
"""

import pytest
from agents.runtime_discovery.inference import SchemaInferenceEngine
from agents.runtime_discovery.models import ObservationSourceType, RuntimeObservation


def test_schema_inference_primitives():
    engine = SchemaInferenceEngine()

    observations = [
        RuntimeObservation(
            observation_id=f"obs_{i}",
            source_type=ObservationSourceType.TEST_TRAFFIC,
            method="GET",
            route="/api/v1/user",
            status_code=200,
            response_body={
                "id": 100 + i,
                "name": f"User {i}",
                "score": 98.5,
                "is_active": True,
                "tags": ["alpha", "beta"],
                "profile": {"location": "Lisbon"},
            },
        )
        for i in range(4)
    ]

    schema = engine.infer_response_schema(observations)
    assert schema.schema_name == "UserResponse"
    assert schema.fields["id"]["type"] == "integer"
    assert schema.fields["name"]["type"] == "string"
    assert schema.fields["score"]["type"] == "float"
    assert schema.fields["is_active"]["type"] == "boolean"
    assert schema.fields["tags"]["type"] == "array"
    assert schema.fields["profile"]["type"] == "object"


def test_schema_inference_missing_vs_null_and_requiredness():
    engine = SchemaInferenceEngine()

    # Sample 1: has all fields
    # Sample 2: has email, but bio is null, and avatar is missing
    # Sample 3: has email, bio is string, and avatar is missing
    # Sample 4: has email, bio is null, and avatar is present
    observations = [
        RuntimeObservation(
            observation_id="obs_1",
            source_type=ObservationSourceType.TEST_TRAFFIC,
            method="GET",
            route="/api/v1/users/me",
            status_code=200,
            response_body={"email": "u1@test.com", "bio": "Hello", "avatar": "pic1.png"},
        ),
        RuntimeObservation(
            observation_id="obs_2",
            source_type=ObservationSourceType.TEST_TRAFFIC,
            method="GET",
            route="/api/v1/users/me",
            status_code=200,
            response_body={"email": "u2@test.com", "bio": None},  # avatar missing!
        ),
        RuntimeObservation(
            observation_id="obs_3",
            source_type=ObservationSourceType.TEST_TRAFFIC,
            method="GET",
            route="/api/v1/users/me",
            status_code=200,
            response_body={"email": "u3@test.com", "bio": "Dev", "avatar": None},
        ),
        RuntimeObservation(
            observation_id="obs_4",
            source_type=ObservationSourceType.TEST_TRAFFIC,
            method="GET",
            route="/api/v1/users/me",
            status_code=200,
            response_body={"email": "u4@test.com", "bio": None, "avatar": "pic4.png"},
        ),
    ]

    schema = engine.infer_response_schema(observations)

    # Invariant: email present in 4/4 samples -> required = True, nullable = False
    assert schema.fields["email"]["is_required"] is True
    assert schema.fields["email"]["is_nullable"] is False
    assert schema.fields["email"]["presence_ratio"] == 1.0

    # Invariant: bio present in 4/4 samples but had null values -> required = True, nullable = True
    assert schema.fields["bio"]["is_required"] is True
    assert schema.fields["bio"]["is_nullable"] is True

    # Invariant: avatar missing in 1 sample -> required = False (OPTIONAL)
    assert schema.fields["avatar"]["is_required"] is False
    assert schema.fields["avatar"]["is_nullable"] is True


def test_schema_inference_single_sample_never_required():
    engine = SchemaInferenceEngine()

    # Single observation: appearing once must NEVER mark field as required!
    single_obs = [
        RuntimeObservation(
            observation_id="obs_single",
            source_type=ObservationSourceType.TEST_TRAFFIC,
            method="GET",
            route="/api/v1/item",
            status_code=200,
            response_body={"name": "SingleSample"},
        )
    ]

    schema = engine.infer_response_schema(single_obs)
    # Even though presence_ratio is 1.0 (1/1), sample count < 3 => is_required MUST be False
    assert schema.fields["name"]["is_required"] is False


def test_schema_inference_enum_candidates():
    engine = SchemaInferenceEngine()

    observations = [
        RuntimeObservation(
            observation_id=f"obs_{i}",
            source_type=ObservationSourceType.TEST_TRAFFIC,
            method="GET",
            route="/api/v1/orders",
            status_code=200,
            response_body={"order_id": str(i), "status": ["PENDING", "COMPLETED", "FAILED"][i % 3]},
        )
        for i in range(6)
    ]

    schema = engine.infer_response_schema(observations)
    assert schema.fields["status"]["is_enum_candidate"] is True
    assert set(schema.fields["status"]["enum_values"]) == {"PENDING", "COMPLETED", "FAILED"}


def test_error_contract_aggregation():
    engine = SchemaInferenceEngine()

    observations = [
        RuntimeObservation(
            observation_id="obs_err_1",
            source_type=ObservationSourceType.TEST_TRAFFIC,
            method="POST",
            route="/api/v1/login",
            status_code=401,
            response_body={"detail": "Bad password"},
        ),
        RuntimeObservation(
            observation_id="obs_err_2",
            source_type=ObservationSourceType.TEST_TRAFFIC,
            method="POST",
            route="/api/v1/login",
            status_code=401,
            response_body={"detail": "Bad password"},
        ),
        RuntimeObservation(
            observation_id="obs_err_3",
            source_type=ObservationSourceType.TEST_TRAFFIC,
            method="POST",
            route="/api/v1/login",
            status_code=422,
            response_body={"detail": "Invalid JSON format"},
        ),
    ]

    error_contracts = engine.infer_error_contracts(observations)
    assert len(error_contracts) == 2

    status_401 = next(e for e in error_contracts if e["status_code"] == 401)
    assert status_401["sample_count"] == 2
    assert "detail" in status_401["error_shape"]

    status_422 = next(e for e in error_contracts if e["status_code"] == 422)
    assert status_422["sample_count"] == 1
