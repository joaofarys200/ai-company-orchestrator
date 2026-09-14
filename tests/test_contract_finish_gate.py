"""
Tests for Phase 48 Contract Completion Gate (No False Success):
- Enforces: Backend build PASS + Contract Mismatch -> Mission NOT completed!
- ContractMissionGate.evaluate_completion_gate blocks completion on contract mismatch or consumer failure.
- Policy finish gate blocks FINISH decision when contract_mismatch_detected is True.
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
from agents.contract_change_management.gate import ContractMissionGate
from agents.contract_change_management.models import ContractVerificationResult


def test_finish_gate_blocks_false_completion_on_contract_mismatch():
    state = AutonomousLoopState(mission_id="m_finish_gate_test")
    ctx = PolicyEvaluationContext(
        mission_id="m_finish_gate_test",
        cycle_id="cycle_final",
        loop_state=state,
        budget=AdaptationBudget(),
    )
    # Build passed, requirements satisfied, zero test failures
    ctx.execution_success = True
    ctx.all_requirements_satisfied = True
    ctx.required_validation_passed = True
    ctx.evidence_complete = True
    ctx.state_consistent = True
    ctx.no_active_blocks = True
    ctx.active_failures = []

    # BUT contract mismatch detected!
    ctx.contract_mismatch_detected = True
    ctx.contract_validation_passed = False

    decision, explanation, rule = AutonomousDecisionPolicy.evaluate(ctx)

    # Must NOT conclude mission as FINISH
    assert decision != LoopDecisionType.FINISH
    assert rule.rule_id != "RULE_07_FINISH_GATE_SATISFIED"


def test_finish_gate_permits_completion_when_contract_verified():
    state = AutonomousLoopState(mission_id="m_finish_gate_test")
    ctx = PolicyEvaluationContext(
        mission_id="m_finish_gate_test",
        cycle_id="cycle_final",
        loop_state=state,
        budget=AdaptationBudget(),
    )
    ctx.execution_success = True
    ctx.all_requirements_satisfied = True
    ctx.required_validation_passed = True
    ctx.evidence_complete = True
    ctx.state_consistent = True
    ctx.no_active_blocks = True
    ctx.active_failures = []
    ctx.contract_validation_passed = True
    ctx.contract_mismatch_detected = False

    decision, explanation, rule = AutonomousDecisionPolicy.evaluate(ctx)

    # Successfully completes with proof
    assert decision == LoopDecisionType.FINISH
    assert rule.rule_id == "RULE_07_FINISH_GATE_SATISFIED"
    assert "contract compatibility confirmed" in explanation.observation


def test_contract_mission_gate_evaluate_completion():
    # 1. Mismatched version
    mismatched = ContractVerificationResult(
        contract_id="contract_users_v1",
        baseline_version="2.0.0",
        observed_version="1.0.0",
        matches_predicted=False,
        consumer_compatibility_verified=True,
        tests_verified=True,
        browser_qa_verified=True,
        all_evidence_verified=True,
        passed=False,
    )
    allowed, reason = ContractMissionGate.evaluate_completion_gate(mismatched)
    assert allowed is False
    assert "Contract mismatch" in reason

    # 2. Consumer compatibility failure
    consumer_fail = ContractVerificationResult(
        contract_id="contract_users_v1",
        baseline_version="2.0.0",
        observed_version="2.0.0",
        matches_predicted=True,
        consumer_compatibility_verified=False,
        tests_verified=True,
        browser_qa_verified=True,
        all_evidence_verified=True,
        passed=False,
    )
    allowed, reason = ContractMissionGate.evaluate_completion_gate(consumer_fail)
    assert allowed is False
    assert "Consumer incompatibility" in reason

    # 3. All verified
    all_ok = ContractVerificationResult(
        contract_id="contract_users_v1",
        baseline_version="2.0.0",
        observed_version="2.0.0",
        matches_predicted=True,
        consumer_compatibility_verified=True,
        tests_verified=True,
        browser_qa_verified=True,
        all_evidence_verified=True,
        passed=True,
    )
    allowed, reason = ContractMissionGate.evaluate_completion_gate(all_ok)
    assert allowed is True
    assert "Contract Completion Gate satisfied" in reason
