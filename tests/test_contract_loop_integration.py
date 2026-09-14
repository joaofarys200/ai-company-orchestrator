"""
Tests for Phase 48 Autonomous Loop & Decision Trace Integration:
- PolicyEvaluationContext contract change fields
- AutonomousDecisionPolicy evaluation of unapproved contract change
- DecisionTrace enrichment with contract intelligence
"""

import pytest
from agents.autonomous_loop.models import (
    AdaptationBudget,
    AutonomousLoopState,
    LoopDecisionType,
)
from agents.autonomous_loop.policy import (
    AutonomousDecisionPolicy,
    PolicyEvaluationContext,
)
from agents.contract_change_management.bridge import ContractAwareChangeBridge
from agents.contract_change_management.models import (
    ContractChangePrediction,
    ContractRiskLevel,
    GateDecision,
)
from agents.decision_calibration.models import DecisionTrace


def test_autonomous_policy_contract_change_enforcement():
    state = AutonomousLoopState(mission_id="m_contract_test")
    ctx = PolicyEvaluationContext(
        mission_id="m_contract_test",
        cycle_id="cycle_1",
        loop_state=state,
        budget=AdaptationBudget(),
    )
    ctx.contract_change_detected = True
    ctx.contract_change_risk = "BREAKING"
    ctx.contract_migration_approved = False
    ctx.contract_reason = "Avatar object conversion breaks UserCard"

    decision, explanation, rule = AutonomousDecisionPolicy.evaluate(ctx)

    # Must require human intervention
    assert decision == LoopDecisionType.REQUEST_HUMAN
    assert rule.rule_id == "RULE_08_HUMAN_APPROVAL_PENDING"
    assert "Breaking contract change" in explanation.observation


def test_decision_trace_enrichment():
    trace = DecisionTrace(
        trace_id="tr_test_01",
        mission_id="m_contract_test",
        cycle_id="cycle_1",
        observations_summary={},
        rules_evaluated=[],
        matched_rule_id="RULE_08_HUMAN_APPROVAL_PENDING",
        decision="REQUEST_HUMAN",
        gate_status="REQUIRE_HUMAN_APPROVAL",
        action_executed="NONE",
        result_observed="PENDING",
        evaluation_summary="Contract change requires operator approval",
    )

    pred = ContractChangePrediction(
        prediction_id="pred_test_enrich",
        task_id="tsk_test_01",
        affected_contracts=["contract_users_v1"],
        breaking_risk=ContractRiskLevel.BREAKING,
        migration_required=True,
        approval_required=True,
    )

    ContractAwareChangeBridge.enrich_decision_trace(
        decision_trace=trace,
        prediction=pred,
        gate_decision=GateDecision.REQUIRE_HUMAN_APPROVAL,
    )

    assert trace.contract_analysis is not None
    assert trace.contract_analysis["breaking_risk"] == "BREAKING"
    assert trace.contract_risk == "BREAKING"
    assert trace.gate_result == "REQUIRE_HUMAN_APPROVAL"
