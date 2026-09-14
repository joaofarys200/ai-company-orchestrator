"""
Tests for Phase 40 Autonomous Decision Policy, Adaptation Budget and Finish Gate.
"""

import pytest
from agents.autonomous_loop.models import (
    AdaptationBudget,
    AutonomousLoopState,
    DriftClassification,
    LoopDecisionType,
    LoopStage,
    OscillationStatus,
)
from agents.autonomous_loop.policy import (
    AutonomousDecisionPolicy,
    PolicyEvaluationContext,
)


def create_base_ctx(mission_id="m_test_pol"):
    state = AutonomousLoopState(mission_id=mission_id)
    budget = AdaptationBudget()
    return PolicyEvaluationContext(
        mission_id=mission_id,
        cycle_id="cycle_1",
        loop_state=state,
        budget=budget,
    )


def test_rule_01_security_violation():
    ctx = create_base_ctx()
    ctx.security_violation = True
    ctx.security_reason = "Unauthorized root path traversal attempt"

    decision, explanation, rule = AutonomousDecisionPolicy.evaluate(ctx)
    assert decision == LoopDecisionType.BLOCK
    assert rule.rule_id == "RULE_01_SECURITY_BLOCK"
    assert "Security Sentinel" in explanation.observation


def test_rule_02_economic_approval():
    ctx = create_base_ctx()
    ctx.economic_approval_required = True
    ctx.economic_reason = "Cloud infrastructure spin-up costs $25"

    decision, explanation, rule = AutonomousDecisionPolicy.evaluate(ctx)
    assert decision == LoopDecisionType.REQUEST_HUMAN
    assert rule.rule_id == "RULE_02_ECONOMIC_APPROVAL"


def test_rule_03_oscillation_detected():
    ctx = create_base_ctx()
    ctx.oscillation_status = OscillationStatus.CONFIRMED_OSCILLATION
    ctx.oscillation_reason = "Loop between plan A and B repeated 3 times"

    decision, explanation, rule = AutonomousDecisionPolicy.evaluate(ctx)
    assert decision == LoopDecisionType.REQUEST_HUMAN
    assert rule.rule_id == "RULE_03_OSCILLATION_DETECTED"


def test_rule_04_unexpected_drift():
    ctx = create_base_ctx()
    ctx.drift_classification = DriftClassification.UNEXPECTED_DRIFT
    ctx.drift_reason = "Key security requirement was omitted by planner"

    decision, explanation, rule = AutonomousDecisionPolicy.evaluate(ctx)
    assert decision == LoopDecisionType.REQUEST_HUMAN
    assert rule.rule_id == "RULE_04_UNEXPECTED_DRIFT"


def test_rule_05_adaptation_budget_exhausted():
    ctx = create_base_ctx()
    ctx.loop_state.adaptation_count = 16  # max is 15
    decision, explanation, rule = AutonomousDecisionPolicy.evaluate(ctx)
    assert decision == LoopDecisionType.REQUEST_HUMAN
    assert rule.rule_id == "RULE_05_ADAPTATION_BUDGET_EXHAUSTED"


def test_rule_06_consecutive_failures_exhausted():
    ctx = create_base_ctx()
    ctx.loop_state.consecutive_failures = 4  # max is 3
    decision, explanation, rule = AutonomousDecisionPolicy.evaluate(ctx)
    assert decision == LoopDecisionType.REQUEST_HUMAN
    assert rule.rule_id == "RULE_06_CONSECUTIVE_FAILURES_EXHAUSTED"


def test_rule_07_finish_gate_satisfied():
    ctx = create_base_ctx()
    ctx.execution_success = True
    ctx.all_requirements_satisfied = True
    ctx.required_validation_passed = True
    ctx.evidence_complete = True
    ctx.state_consistent = True
    ctx.no_active_blocks = True
    ctx.active_failures = []

    decision, explanation, rule = AutonomousDecisionPolicy.evaluate(ctx)
    assert decision == LoopDecisionType.FINISH
    assert rule.rule_id == "RULE_07_FINISH_GATE_SATISFIED"
    assert "All mission requirements satisfied" in explanation.observation


def test_rule_09_repairable_failure():
    ctx = create_base_ctx()
    ctx.active_failures = [{"error": "TypeError: null reference in sort", "is_repairable": True}]
    ctx.failure_is_repairable = True
    ctx.failure_reason = "Null pointer in sort"

    decision, explanation, rule = AutonomousDecisionPolicy.evaluate(ctx)
    assert decision == LoopDecisionType.REPAIR
    assert rule.rule_id == "RULE_09_REPAIRABLE_VALIDATION_FAILURE"


def test_rule_10_unrepairable_failure():
    ctx = create_base_ctx()
    ctx.active_failures = [{"error": "Hardware NIC dropped", "is_repairable": False}]
    ctx.failure_is_repairable = False
    ctx.failure_reason = "Fatal hardware drop"

    decision, explanation, rule = AutonomousDecisionPolicy.evaluate(ctx)
    assert decision == LoopDecisionType.REQUEST_HUMAN
    assert rule.rule_id == "RULE_10_UNREPAIRABLE_FAILURE"


def test_rule_11_plan_invalid_or_new_dependency():
    ctx = create_base_ctx()
    ctx.plan_invalid_or_new_dependency = True
    ctx.plan_invalid_reason = "Circular dependency detected between TSK_02 and TSK_04"

    decision, explanation, rule = AutonomousDecisionPolicy.evaluate(ctx)
    assert decision == LoopDecisionType.REPLAN
    assert rule.rule_id == "RULE_11_PLAN_INVALID_OR_NEW_DEPENDENCY"


def test_rule_12_prediction_deviation_satisfiable():
    ctx = create_base_ctx()
    ctx.prediction_deviation = True
    ctx.prediction_deviation_satisfiable = True
    ctx.deviation_reason = "1 unexpected file created by coder"

    decision, explanation, rule = AutonomousDecisionPolicy.evaluate(ctx)
    assert decision == LoopDecisionType.ADAPT
    assert rule.rule_id == "RULE_12_PREDICTION_DEVIATION_SATISFIABLE"


def test_rule_13_agent_reassignment():
    ctx = create_base_ctx()
    ctx.task_owner_unavailable = True
    ctx.alternative_agent_available = True
    ctx.reassignment_reason = "Worker timed out"

    decision, explanation, rule = AutonomousDecisionPolicy.evaluate(ctx)
    assert decision == LoopDecisionType.REASSIGN
    assert rule.rule_id == "RULE_13_AGENT_UNAVAILABLE_COMPATIBLE_EXISTS"


def test_rule_14_normal_progression():
    ctx = create_base_ctx()
    # clean state, progressing normally
    decision, explanation, rule = AutonomousDecisionPolicy.evaluate(ctx)
    assert decision == LoopDecisionType.CONTINUE
    assert rule.rule_id == "RULE_14_NORMAL_PROGRESSION"
