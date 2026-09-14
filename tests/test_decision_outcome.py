"""
JARVIS OS — Phase 41: Decision Outcome Model & Evaluator Tests
"""

import pytest
from agents.autonomous_loop.models import AutonomousLoopState, LoopDecisionType, OscillationStatus
from agents.autonomous_loop.policy import PolicyEvaluationContext
from agents.decision_calibration.evaluator import DecisionOutcomeEvaluator
from agents.decision_calibration.models import (
    DecisionCorrectness,
    DecisionErrorTaxonomy,
    DecisionOutcome,
    DecisionSeverity,
    RuleEvaluationRecord,
)


def test_decision_outcome_correct_evaluation():
    ctx = PolicyEvaluationContext(
        mission_id="m_test_1",
        cycle_id="c_1",
        loop_state=AutonomousLoopState(mission_id="m_test_1", cycle_id="c_1"),
        budget=0,
        execution_success=True,
    )
    rules = [
        RuleEvaluationRecord(
            rule_id="RULE_14_NORMAL_PROGRESSION",
            priority=14,
            condition_name="normal_progression",
            evaluated=True,
            matched=True,
            rule_decision="CONTINUE",
        )
    ]

    outcome, trace = DecisionOutcomeEvaluator.evaluate_decision_outcome(
        mission_id="m_test_1",
        cycle_id="c_1",
        decision_id="dec_1",
        decision_type=LoopDecisionType.CONTINUE,
        policy_version="40.1.0",
        rule_matched_id="RULE_14_NORMAL_PROGRESSION",
        rules_evaluated=rules,
        ctx=ctx,
        observed_outcome="Task executed cleanly",
        expected_decision=LoopDecisionType.CONTINUE,
    )

    assert outcome.decision_correctness == DecisionCorrectness.CORRECT
    assert outcome.severity == DecisionSeverity.INFO
    assert outcome.decision_type == LoopDecisionType.CONTINUE
    assert trace.matched_rule_id == "RULE_14_NORMAL_PROGRESSION"


def test_decision_outcome_false_finish_is_critical():
    ctx = PolicyEvaluationContext(
        mission_id="m_test_2",
        cycle_id="c_2",
        loop_state=AutonomousLoopState(mission_id="m_test_2", cycle_id="c_2"),
        budget=0,
        all_requirements_satisfied=False,  # Unmet requirement!
        evidence_complete=False,
    )

    outcome, trace = DecisionOutcomeEvaluator.evaluate_decision_outcome(
        mission_id="m_test_2",
        cycle_id="c_2",
        decision_id="dec_2",
        decision_type=LoopDecisionType.FINISH,  # Premature FINISH
        policy_version="40.1.0",
        rule_matched_id="RULE_07_FINISH_GATE_SATISFIED",
        rules_evaluated=[],
        ctx=ctx,
        observed_outcome="Premature termination attempt",
        expected_decision=LoopDecisionType.CONTINUE,
    )

    assert outcome.decision_correctness == DecisionCorrectness.INCORRECT
    assert outcome.severity == DecisionSeverity.CRITICAL
    assert outcome.counterfactual is not None
    assert outcome.counterfactual.alternative_decision in [LoopDecisionType.CONTINUE, LoopDecisionType.ADAPT]


def test_decision_outcome_metrics_computation():
    outcomes = []
    # 3 correct CONTINUE
    for i in range(3):
        outcomes.append(DecisionOutcome(
            outcome_id=f"o_{i}",
            mission_id="m",
            cycle_id=f"c_{i}",
            decision_id=f"d_{i}",
            decision_type=LoopDecisionType.CONTINUE,
            policy_version="40.1.0",
            rule_id="RULE_14",
            expected_outcome="CONTINUE",
            observed_outcome="OK",
            decision_correctness=DecisionCorrectness.CORRECT,
        ))
    # 1 incorrect false finish
    outcomes.append(DecisionOutcome(
        outcome_id="o_err",
        mission_id="m",
        cycle_id="c_err",
        decision_id="d_err",
        decision_type=LoopDecisionType.FINISH,
        policy_version="40.1.0",
        rule_id="RULE_07",
        expected_outcome="CONTINUE",
        observed_outcome="Incomplete evidence",
        decision_correctness=DecisionCorrectness.INCORRECT,
        severity=DecisionSeverity.CRITICAL,
    ))

    metrics = DecisionOutcomeEvaluator.compute_quality_metrics(outcomes)
    assert metrics.total_decisions == 4
    assert metrics.correct_decisions == 3
    assert metrics.incorrect_decisions == 1
    assert metrics.accuracy == 0.75
    assert metrics.false_finish_count == 1
    assert metrics.false_finish_rate == 0.25
