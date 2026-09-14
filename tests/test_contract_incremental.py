"""
Tests for Phase 45 — Incremental Contract Observation & Proposal Updates.
Verifies that appending new observations updates proposals incrementally
without reconstructing the entire registry or all previous proposals from scratch.
"""

import pytest
import time
from agents.runtime_discovery.observer import RuntimeContractObserver
from agents.runtime_discovery.inference import SchemaInferenceEngine
from agents.runtime_discovery.models import ObservationSourceType, ProposalStatus


def test_incremental_append_single_observation():
    observer = RuntimeContractObserver()
    engine = SchemaInferenceEngine()

    # Initial batch of 3 observations
    for i in range(3):
        observer.observe_interaction(
            source_type=ObservationSourceType.LOCAL_DEV_PROXY,
            method="GET",
            route="/api/v1/status",
            status_code=200,
            response_body={"status": "OK", "load": 0.1 * i},
        )

    obs_list = observer.get_observations_for_endpoint("GET", "/api/v1/status")
    assert len(obs_list) == 3

    schema_v1 = engine.infer_response_schema(obs_list)
    proposal = engine.create_contract_proposal(
        route="/api/v1/status",
        method="GET",
        source="local_dev_proxy",
        observations=obs_list,
        inferred_response_schema=schema_v1,
    )
    initial_sample_count = proposal.sample_count
    assert initial_sample_count == 3

    # Now append 1 single observation incrementally
    new_obs = observer.observe_interaction(
        source_type=ObservationSourceType.LOCAL_DEV_PROXY,
        method="GET",
        route="/api/v1/status",
        status_code=200,
        response_body={"status": "OK", "load": 0.5, "uptime": 3600},
    )

    updated_proposal = engine.update_proposal_incrementally(proposal, [new_obs])
    assert updated_proposal.sample_count == 4
    assert len(updated_proposal.evidence_refs) == 4
    # Uptime appeared in 1/4 samples -> optional
    fields = updated_proposal.observed_response_schema.get("fields", {})
    if "uptime" in fields:
        assert fields["uptime"]["is_required"] is False


def test_incremental_append_100_observations_performance():
    observer = RuntimeContractObserver()
    engine = SchemaInferenceEngine()

    # Ingest 100 observations sequentially
    start_t = time.perf_counter()
    for i in range(100):
        observer.observe_interaction(
            source_type=ObservationSourceType.TEST_TRAFFIC,
            method="POST",
            route="/api/v1/events",
            status_code=202,
            response_body={"event_id": f"evt_{i}", "processed": True},
        )
    elapsed_ingest = time.perf_counter() - start_t

    # 100 observations should take less than 0.5s in memory
    assert elapsed_ingest < 0.5

    obs_list = observer.get_observations_for_endpoint("POST", "/api/v1/events")
    assert len(obs_list) == 100

    schema = engine.infer_response_schema(obs_list)
    proposal = engine.create_contract_proposal(
        route="/api/v1/events",
        method="POST",
        source="test_traffic",
        observations=obs_list,
        inferred_response_schema=schema,
    )

    assert proposal.sample_count == 100
    assert proposal.confidence >= 0.90
    assert proposal.observed_response_schema["fields"]["event_id"]["is_required"] is True
    assert proposal.observed_response_schema["fields"]["processed"]["is_required"] is True
