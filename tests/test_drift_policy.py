"""
JARVIS OS — Phase 46: Drift Policy Test Suite
Validates policy evaluation across non-breaking, breaking, and noise scenarios.
"""

from agents.contract_governance.engine import ContractDriftEngine
from agents.contract_governance.models import (
    ContractBaseline,
    DriftPolicyAction,
    EnvironmentType,
    ObservationWindow,
    VariationType,
)
from agents.runtime_discovery.models import RuntimeObservation


def test_drift_policy_noise_vs_systematic():
    engine = ContractDriftEngine()
    baseline = ContractBaseline(
        contract_id="ctr_policy",
        version="1.0.0",
        schema_hash="abc123hash",
        route="/api/v1/feed",
        method="GET",
        response_schema={"properties": {"items": {"type": "array"}}},
    )

    # 1 out of 20 requests has an unexpected field (5% freq) -> One-off noise
    win_noise = ObservationWindow(window_id="w_noise", environment=EnvironmentType.PRODUCTION)
    for i in range(19):
        win_noise.add_observation(
            RuntimeObservation(
                observation_id=f"o_{i}",
                source_type="TEST_TRAFFIC",
                method="GET",
                route="/api/v1/feed",
                status_code=200,
                response_payload={"items": []},
            )
        )
    win_noise.add_observation(
        RuntimeObservation(
            observation_id="o_noise_single",
            source_type="TEST_TRAFFIC",
            method="GET",
            route="/api/v1/feed",
            status_code=200,
            response_payload={"items": [], "experimental_tag": "test"},
        )
    )

    rep_noise = engine.detect_drift(baseline, win_noise)
    assert rep_noise.recommended_action == DriftPolicyAction.MONITOR
    assert rep_noise.variation_type in (VariationType.ONE_OFF_VARIATION, VariationType.SYSTEMATIC_DRIFT)


def test_drift_policy_breaking_requires_human():
    engine = ContractDriftEngine()
    baseline = ContractBaseline(
        contract_id="ctr_policy_brk",
        version="1.0.0",
        schema_hash="abc456hash",
        route="/api/v1/checkout",
        method="POST",
        response_schema={"properties": {"order_id": {"type": "string"}}, "required": ["order_id"]},
    )

    win_brk = ObservationWindow(window_id="w_brk")
    for i in range(5):
        win_brk.add_observation(
            RuntimeObservation(
                observation_id=f"o_{i}",
                source_type="TEST_TRAFFIC",
                method="POST",
                route="/api/v1/checkout",
                status_code=200,
                response_payload={"order_number": 12345},  # order_id missing!
            )
        )

    rep = engine.detect_drift(baseline, win_brk)
    assert rep.recommended_action == DriftPolicyAction.REQUEST_HUMAN
    assert rep.variation_type in (VariationType.SYSTEMATIC_DRIFT, VariationType.CONTRACT_CHANGE)
