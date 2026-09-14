"""
JARVIS OS — Phase 46: Environment Isolation Test Suite
Validates strict separation between DEVELOPMENT, STAGING, and PRODUCTION observation windows.
"""

import pytest

from agents.contract_governance.engine import ContractDriftEngine
from agents.contract_governance.models import (
    ContractBaseline,
    EnvironmentType,
    ObservationWindow,
)
from agents.runtime_discovery.models import RuntimeObservation


def test_environment_window_rejection():
    prod_window = ObservationWindow(window_id="win_prod", environment=EnvironmentType.PRODUCTION)

    dev_obs = RuntimeObservation(
        observation_id="obs_dev_01",
        source_type="TEST_TRAFFIC",
        method="GET",
        route="/api/v1/test",
        status_code=200,
        metadata={"environment": "DEVELOPMENT"},
    )

    with pytest.raises(ValueError, match="Environment mismatch"):
        prod_window.add_observation(dev_obs)


def test_environment_isolated_drift_reports():
    engine = ContractDriftEngine()
    baseline = ContractBaseline(
        contract_id="ctr_env_test",
        version="1.0.0",
        schema_hash="hash123",
        route="/api/v1/data",
        method="GET",
        response_schema={"properties": {"value": {"type": "string"}}},
    )

    dev_window = ObservationWindow(window_id="w_dev", environment=EnvironmentType.DEVELOPMENT)
    prod_window = ObservationWindow(window_id="w_prod", environment=EnvironmentType.PRODUCTION)

    # In dev: breaking change
    for i in range(4):
        dev_window.add_observation(
            RuntimeObservation(
                observation_id=f"dev_{i}",
                source_type="TEST_TRAFFIC",
                method="GET",
                route="/api/v1/data",
                status_code=200,
                response_payload={"value": 12345},  # integer
                metadata={"environment": "DEVELOPMENT"},
            )
        )

    # In prod: in-sync
    for i in range(4):
        prod_window.add_observation(
            RuntimeObservation(
                observation_id=f"prod_{i}",
                source_type="TEST_TRAFFIC",
                method="GET",
                route="/api/v1/data",
                status_code=200,
                response_payload={"value": "standard_string"},
                metadata={"environment": "PRODUCTION"},
            )
        )

    dev_report = engine.detect_drift(baseline, dev_window)
    prod_report = engine.detect_drift(baseline, prod_window)

    assert dev_report.environment == "DEVELOPMENT"
    assert dev_report.classification.value == "BREAKING"

    assert prod_report.environment == "PRODUCTION"
    assert prod_report.classification.value == "NON_BREAKING"
    assert prod_report.status.value == "IN_SYNC"
