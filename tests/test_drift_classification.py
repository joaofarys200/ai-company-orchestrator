"""
JARVIS OS — Phase 46: Drift Classification Test Suite
Validates deterministic breakage classification across all drift types.
"""

import pytest

from agents.contract_governance.engine import ContractDriftEngine
from agents.contract_governance.models import (
    ContractBaseline,
    DriftClassification,
    DriftType,
    EnvironmentType,
    ObservationWindow,
)
from agents.runtime_discovery.models import RuntimeObservation


@pytest.fixture
def base_contract() -> ContractBaseline:
    req = {"properties": {"page": {"type": "integer", "is_required": False}}}
    resp = {
        "properties": {
            "title": {"type": "string", "is_required": True, "is_nullable": False},
            "views": {"type": "integer", "is_required": True, "is_nullable": False},
        },
        "required": ["title", "views"],
    }
    h = ContractBaseline.compute_schema_hash(req, resp)
    return ContractBaseline(
        contract_id="ctr_articles",
        version="1.0.0",
        schema_hash=h,
        route="/api/v1/articles",
        method="GET",
        request_schema=req,
        response_schema=resp,
        metadata={"requires_auth": False},
    )


def test_classify_response_field_added(base_contract: ContractBaseline):
    engine = ContractDriftEngine()
    window = ObservationWindow(window_id="w1")
    for i in range(4):
        window.add_observation(
            RuntimeObservation(
                observation_id=f"o_{i}",
                source_type="TEST_TRAFFIC",
                method="GET",
                route="/api/v1/articles",
                status_code=200,
                response_payload={"title": "Article 1", "views": 100, "subtitle": "New Subtitle"},
            )
        )
    rep = engine.detect_drift(base_contract, window)
    assert rep.classification == DriftClassification.NON_BREAKING


def test_classify_nullability_break(base_contract: ContractBaseline):
    engine = ContractDriftEngine()
    window = ObservationWindow(window_id="w2")
    for i in range(4):
        window.add_observation(
            RuntimeObservation(
                observation_id=f"o_{i}",
                source_type="TEST_TRAFFIC",
                method="GET",
                route="/api/v1/articles",
                status_code=200,
                response_payload={"title": None, "views": 100},
            )
        )
    rep = engine.detect_drift(base_contract, window)
    assert rep.classification == DriftClassification.BREAKING
    assert any(c.drift_type == DriftType.NULLABILITY_CHANGED for c in rep.changes)


def test_classify_auth_drift_break(base_contract: ContractBaseline):
    engine = ContractDriftEngine()
    window = ObservationWindow(window_id="w3")
    for i in range(4):
        window.add_observation(
            RuntimeObservation(
                observation_id=f"o_{i}",
                source_type="TEST_TRAFFIC",
                method="GET",
                route="/api/v1/articles",
                status_code=401,
                response_payload={"detail": "Authentication required"},
            )
        )
    rep = engine.detect_drift(base_contract, window)
    assert rep.classification == DriftClassification.BREAKING
    assert any(c.drift_type == DriftType.AUTH_CONTRACT_CHANGED for c in rep.changes)


def test_classify_request_required_field_added(base_contract: ContractBaseline):
    engine = ContractDriftEngine()
    window = ObservationWindow(window_id="w4")
    # Clients sending required tenant_id not in baseline
    for i in range(4):
        window.add_observation(
            RuntimeObservation(
                observation_id=f"o_{i}",
                source_type="TEST_TRAFFIC",
                method="GET",
                route="/api/v1/articles",
                status_code=200,
                request_payload={"page": 1, "tenant_id": "tenant_123"},
                response_payload={"title": "Test", "views": 50},
            )
        )
    rep = engine.detect_drift(base_contract, window)
    assert any(c.drift_type in (DriftType.FIELD_ADDED, DriftType.REQUIREDNESS_CHANGED) and c.is_request for c in rep.changes)
