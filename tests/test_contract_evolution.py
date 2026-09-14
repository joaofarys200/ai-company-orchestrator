"""
JARVIS OS — Phase 46: Contract Evolution Test Suite
Validates version progression v1 -> v2, immutable baselines, and approval gates.
"""

import pytest

from agents.contract_governance.evolution import ContractEvolutionManager
from agents.contract_governance.models import (
    ContractBaseline,
    ContractDriftReport,
    DriftClassification,
    DriftPolicyAction,
)


@pytest.fixture
def manager_with_v1() -> ContractEvolutionManager:
    mgr = ContractEvolutionManager()
    req = {"properties": {"id": {"type": "string"}}}
    resp = {"properties": {"status": {"type": "string"}}}
    h = ContractBaseline.compute_schema_hash(req, resp)
    v1 = ContractBaseline(
        contract_id="ctr_order",
        version="1.0.0",
        schema_hash=h,
        route="/api/v1/orders",
        method="POST",
        request_schema=req,
        response_schema=resp,
    )
    mgr.register_baseline(v1)
    return mgr


def test_baseline_immutability(manager_with_v1: ContractEvolutionManager):
    active = manager_with_v1.get_active_baseline("ctr_order")
    assert active is not None
    # Frozen dataclass raises FrozenInstanceError if modified
    with pytest.raises(Exception):
        active.version = "1.0.1"


def test_propose_and_approve_v2(manager_with_v1: ContractEvolutionManager):
    drift_rep = ContractDriftReport(
        drift_id="drift_order_01",
        contract_id="ctr_order",
        baseline_version="1.0.0",
        observed_version="2.0.0-obs",
        classification=DriftClassification.BREAKING,
        recommended_action=DriftPolicyAction.REQUEST_HUMAN,
    )

    prop = manager_with_v1.propose_version_evolution(
        drift_report=drift_rep,
        new_version_tag="2.0.0",
        updated_response_schema={"properties": {"status": {"type": "integer"}}},
    )

    assert prop.parent_version == "1.0.0"
    assert prop.new_version == "2.0.0"
    assert prop.status == "PENDING_APPROVAL"

    # Unauthorized operator approval blocked
    res_fail = manager_with_v1.review_proposal(prop.proposal_id, action="APPROVE", operator_id="anonymous")
    assert res_fail["success"] is False

    # Valid human approval
    res_ok = manager_with_v1.review_proposal(prop.proposal_id, action="APPROVE", operator_id="lead_architect")
    assert res_ok["success"] is True
    assert res_ok["active_version"] == "2.0.0"

    # Confirm v2 is now active
    new_active = manager_with_v1.get_active_baseline("ctr_order")
    assert new_active.version == "2.0.0"
    assert new_active.parent_version == "1.0.0"

    # Confirm v1 is preserved in history
    history = manager_with_v1.get_version_history("ctr_order")
    assert len(history) == 2
    assert [b.version for b in history] == ["1.0.0", "2.0.0"]
