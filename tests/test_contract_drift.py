"""
JARVIS OS — Phase 46: Contract Drift Detection Test Suite
Tests comparing verified immutable baselines against runtime observation windows.
"""

import pytest

from agents.contract_governance.engine import ContractDriftEngine
from agents.contract_governance.models import (
    ContractBaseline,
    ContractDriftStatus,
    DriftClassification,
    DriftType,
    EnvironmentType,
    ObservationWindow,
)
from agents.runtime_discovery.models import RuntimeObservation


@pytest.fixture
def sample_baseline() -> ContractBaseline:
    req_schema = {
        "properties": {
            "query": {"type": "string", "is_required": True},
            "limit": {"type": "integer", "is_required": False},
        },
        "required": ["query"],
    }
    resp_schema = {
        "properties": {
            "id": {"type": "integer", "is_required": True, "is_nullable": False},
            "username": {"type": "string", "is_required": True, "is_nullable": False},
            "email": {"type": "string", "is_required": True, "is_nullable": False},
        },
        "required": ["id", "username", "email"],
    }
    h = ContractBaseline.compute_schema_hash(req_schema, resp_schema)
    return ContractBaseline(
        contract_id="ctr_test_search",
        version="1.0.0",
        schema_hash=h,
        route="/api/v1/users/search",
        method="GET",
        request_schema=req_schema,
        response_schema=resp_schema,
    )


def test_contract_drift_in_sync(sample_baseline: ContractBaseline):
    engine = ContractDriftEngine()
    window = ObservationWindow(window_id="win_sync", environment=EnvironmentType.PRODUCTION)

    # 4 compliant observations
    for i in range(4):
        window.add_observation(
            RuntimeObservation(
                observation_id=f"obs_sync_{i}",
                source_type="TEST_TRAFFIC",
                method="GET",
                route="/api/v1/users/search",
                status_code=200,
                response_payload={"id": i + 1, "username": f"user_{i}", "email": f"u{i}@example.com"},
            )
        )

    report = engine.detect_drift(sample_baseline, window)
    assert report.status == ContractDriftStatus.IN_SYNC
    assert report.classification == DriftClassification.NON_BREAKING
    assert len(report.changes) == 0
    assert report.confidence >= 0.85


def test_contract_drift_non_breaking_field_added(sample_baseline: ContractBaseline):
    engine = ContractDriftEngine()
    window = ObservationWindow(window_id="win_added", environment=EnvironmentType.PRODUCTION)

    # Responses contain extra optional field 'tier'
    for i in range(5):
        window.add_observation(
            RuntimeObservation(
                observation_id=f"obs_added_{i}",
                source_type="TEST_TRAFFIC",
                method="GET",
                route="/api/v1/users/search",
                status_code=200,
                response_payload={"id": i + 1, "username": f"user_{i}", "email": f"u{i}@example.com", "tier": "gold"},
            )
        )

    report = engine.detect_drift(sample_baseline, window)
    assert report.status == ContractDriftStatus.NON_BREAKING_DRIFT
    assert report.classification == DriftClassification.NON_BREAKING
    assert any(c.drift_type == DriftType.FIELD_ADDED and "tier" in c.field_path for c in report.changes)


def test_contract_drift_breaking_field_removed(sample_baseline: ContractBaseline):
    engine = ContractDriftEngine()
    window = ObservationWindow(window_id="win_removed", environment=EnvironmentType.PRODUCTION)

    # Responses miss 'email' which was required in baseline
    for i in range(5):
        window.add_observation(
            RuntimeObservation(
                observation_id=f"obs_removed_{i}",
                source_type="TEST_TRAFFIC",
                method="GET",
                route="/api/v1/users/search",
                status_code=200,
                response_payload={"id": i + 1, "username": f"user_{i}"},
            )
        )

    report = engine.detect_drift(sample_baseline, window)
    assert report.status == ContractDriftStatus.BREAKING_DRIFT
    assert report.classification == DriftClassification.BREAKING
    assert any(c.drift_type == DriftType.FIELD_REMOVED and "email" in c.field_path for c in report.changes)


def test_contract_drift_type_changed(sample_baseline: ContractBaseline):
    engine = ContractDriftEngine()
    window = ObservationWindow(window_id="win_type", environment=EnvironmentType.PRODUCTION)

    # Responses have 'id' as string instead of integer
    for i in range(4):
        window.add_observation(
            RuntimeObservation(
                observation_id=f"obs_type_{i}",
                source_type="TEST_TRAFFIC",
                method="GET",
                route="/api/v1/users/search",
                status_code=200,
                response_payload={"id": f"usr_uuid_{i}", "username": f"user_{i}", "email": f"u{i}@example.com"},
            )
        )

    report = engine.detect_drift(sample_baseline, window)
    assert report.status == ContractDriftStatus.BREAKING_DRIFT
    assert any(c.drift_type == DriftType.TYPE_CHANGED for c in report.changes)
