"""
Tests for Phase 45 — RuntimeContractObserver.
Verifies passive runtime observation, dynamic route parameterization,
redaction of credentials, and aggregation by (method, route).
"""

import pytest
from agents.runtime_discovery.models import (
    ObservationSourceType,
    RuntimeObservation,
)
from agents.runtime_discovery.observer import RuntimeContractObserver


def test_observer_passive_ingestion():
    observer = RuntimeContractObserver()
    
    obs = observer.observe_interaction(
        source_type=ObservationSourceType.BROWSER_NETWORK_LOGS,
        method="GET",
        route="/api/v1/users",
        status_code=200,
        request_headers={"Accept": "application/json", "User-Agent": "JarvisQA/1.0"},
        response_headers={"Content-Type": "application/json"},
        query_params={"page": "1", "limit": "10"},
        response_body=[{"id": 1, "name": "Joao"}, {"id": 2, "name": "Maria"}],
        duration_ms=25.4,
    )

    assert obs.observation_id.startswith("obs_")
    assert obs.route == "/api/v1/users"
    assert obs.method == "GET"
    assert obs.status_code == 200
    assert obs.source_type == ObservationSourceType.BROWSER_NETWORK_LOGS
    assert len(observer.get_observations()) == 1


def test_observer_route_parameterization():
    observer = RuntimeContractObserver()

    # Route with integer ID
    route_int = observer.parameterize_route("/api/v1/users/42")
    assert route_int == "/api/v1/users/{id}"

    # Route with UUID
    route_uuid = observer.parameterize_route("/api/v1/orders/123e4567-e89b-12d3-a456-426614174000")
    assert route_uuid == "/api/v1/orders/{id}"

    # Route with multiple segments
    route_multi = observer.parameterize_route("/api/v1/tenants/99/items/abc-def")
    assert route_multi == "/api/v1/tenants/{id}/items/abc-def"


def test_observer_credential_redaction():
    observer = RuntimeContractObserver()

    obs = observer.observe_interaction(
        source_type=ObservationSourceType.BACKEND_HTTP_MIDDLEWARE,
        method="POST",
        route="/api/v1/auth/login",
        status_code=200,
        request_headers={
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.secret",
            "Cookie": "session_id=super_secret_session_cookie",
            "X-API-Key": "my-secret-key-12345",
        },
        request_body={
            "username": "admin",
            "password": "ClearTextPassword123!",
            "token": "sensitive_token_payload",
        },
        response_body={
            "access_token": "another_bearer_token",
            "token_type": "bearer",
            "expires_in": 3600,
        },
        duration_ms=45.0,
    )

    # Invariant: Sensitive headers and payloads must be redacted
    assert obs.request_headers["Authorization"] == "[REDACTED_CREDENTIAL]"
    assert obs.request_headers["Cookie"] == "[REDACTED_CREDENTIAL]"
    assert obs.request_headers["X-API-Key"] == "[REDACTED_CREDENTIAL]"
    assert obs.request_body["password"] == "[REDACTED_CREDENTIAL]"
    assert obs.request_body["token"] == "[REDACTED_CREDENTIAL]"
    assert obs.response_body["access_token"] == "[REDACTED_CREDENTIAL]"
    assert obs.redacted_items_count >= 5


def test_observer_query_and_aggregation():
    observer = RuntimeContractObserver()

    observer.observe_interaction(
        source_type=ObservationSourceType.LOCAL_DEV_PROXY,
        method="GET",
        route="/api/v1/products/1",
        status_code=200,
        response_body={"id": 1, "title": "Widget"},
    )
    observer.observe_interaction(
        source_type=ObservationSourceType.LOCAL_DEV_PROXY,
        method="GET",
        route="/api/v1/products/2",
        status_code=200,
        response_body={"id": 2, "title": "Gadget"},
    )
    observer.observe_interaction(
        source_type=ObservationSourceType.LOCAL_DEV_PROXY,
        method="POST",
        route="/api/v1/products",
        status_code=201,
        response_body={"id": 3, "title": "New Item"},
    )

    # Both GET /api/v1/products/1 and /2 parameterize to /api/v1/products/{id}
    product_get_obs = observer.get_observations_for_endpoint("GET", "/api/v1/products/{id}")
    assert len(product_get_obs) == 2

    product_post_obs = observer.get_observations_for_endpoint("POST", "/api/v1/products")
    assert len(product_post_obs) == 1
