"""
JARVIS OS — Phase 46: Incremental Drift Check Test Suite
Validates that new observations are evaluated incrementally per contract without global rebuilds.
"""

import time

from agents.contract_governance.engine import ContractDriftEngine
from agents.contract_governance.models import (
    ContractBaseline,
    ObservationWindow,
)
from agents.runtime_discovery.models import RuntimeObservation


def test_incremental_drift_check_performance():
    engine = ContractDriftEngine()
    
    # 5 different contract baselines
    baselines = []
    for i in range(5):
        req = {"properties": {"q": {"type": "string"}}}
        resp = {"properties": {"id": {"type": "integer"}}}
        h = ContractBaseline.compute_schema_hash(req, resp)
        b = ContractBaseline(
            contract_id=f"ctr_{i}",
            version="1.0.0",
            schema_hash=h,
            route=f"/api/v1/resource_{i}",
            method="GET",
            request_schema=req,
            response_schema=resp,
        )
        baselines.append(b)

    # Window with observations targeting ONLY resource_0
    win = ObservationWindow(window_id="w_inc")
    for j in range(10):
        win.add_observation(
            RuntimeObservation(
                observation_id=f"obs_inc_{j}",
                source_type="TEST_TRAFFIC",
                method="GET",
                route="/api/v1/resource_0",
                status_code=200,
                response_payload={"id": j, "extra_field": "val"},
            )
        )

    # Measure incremental check for single contract ctr_0
    t0 = time.perf_counter()
    rep_0 = engine.detect_drift(baselines[0], win)
    dt_inc = (time.perf_counter() - t0) * 1000.0

    # Incremental check should finish in < 5 milliseconds
    assert dt_inc < 5.0
    assert len(rep_0.changes) >= 1

    # Check that another contract (ctr_1) remains unaffected
    rep_1 = engine.detect_drift(baselines[1], win)
    assert rep_1.status.value == "IN_SYNC"
    assert len(rep_1.changes) == 0
