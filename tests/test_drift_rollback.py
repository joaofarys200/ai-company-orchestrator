"""
JARVIS OS — Phase 46: Contract Rollback Test Suite
Validates deterministic rollback v2 -> v1 while preserving full version history.
"""

from agents.contract_governance.evolution import ContractEvolutionManager
from agents.contract_governance.models import (
    ContractBaseline,
    ContractDriftReport,
    DriftClassification,
    DriftPolicyAction,
)


def test_rollback_preserves_history():
    mgr = ContractEvolutionManager()

    # Step 1: Register v1.0.0
    req = {"properties": {"id": {"type": "integer"}}}
    resp = {"properties": {"name": {"type": "string"}}}
    h1 = ContractBaseline.compute_schema_hash(req, resp)
    v1 = ContractBaseline(
        contract_id="ctr_rb_demo",
        version="1.0.0",
        schema_hash=h1,
        route="/api/v1/items",
        method="GET",
        request_schema=req,
        response_schema=resp,
    )
    mgr.register_baseline(v1)

    # Step 2: Evolve to v2.0.0
    drift_rep = ContractDriftReport(
        drift_id="drift_rb_01",
        contract_id="ctr_rb_demo",
        baseline_version="1.0.0",
        observed_version="2.0.0",
        classification=DriftClassification.BREAKING,
        recommended_action=DriftPolicyAction.REQUEST_HUMAN,
    )
    prop = mgr.propose_version_evolution(
        drift_report=drift_rep,
        new_version_tag="2.0.0",
        updated_response_schema={"properties": {"name": {"type": "string"}, "description": {"type": "string"}}},
    )
    mgr.review_proposal(prop.proposal_id, action="APPROVE", operator_id="lead_architect")

    assert mgr.get_active_baseline("ctr_rb_demo").version == "2.0.0"

    # Step 3: Rollback to v1.0.0
    rb_res = mgr.rollback(
        contract_id="ctr_rb_demo",
        target_version="1.0.0",
        operator_id="lead_architect",
        notes="Production regression detected in downstream consumers",
    )
    assert rb_res["success"] is True
    assert rb_res["active_version"] == "1.0.0"
    assert rb_res["previous_version"] == "2.0.0"

    # Confirm active baseline is now v1.0.0
    active = mgr.get_active_baseline("ctr_rb_demo")
    assert active.version == "1.0.0"

    # Confirm history preserves BOTH v1.0.0 and v2.0.0
    history = mgr.get_version_history("ctr_rb_demo")
    assert len(history) == 2
    assert {b.version for b in history} == {"1.0.0", "2.0.0"}

    # Confirm audit resolution is registered
    resolutions = mgr.list_resolutions()
    assert any(r.action.value == "ROLLBACK" for r in resolutions)
