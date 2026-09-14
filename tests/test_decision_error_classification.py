"""
JARVIS OS — Phase 41: Decision Error Taxonomy Classification Tests
"""

import pytest
from agents.autonomous_loop.models import AutonomousLoopState, LoopDecisionType, OscillationStatus
from agents.autonomous_loop.policy import PolicyEvaluationContext
from agents.decision_calibration.evaluator import DecisionOutcomeEvaluator
from agents.decision_calibration.models import (
    DecisionCorrectness,
    DecisionErrorTaxonomy,
    DecisionSeverity,
    MissedObservationType,
)


def test_classify_observation_gap():
    ctx = PolicyEvaluationContext(
        mission_id="m_osc",
        cycle_id="c_osc",
        loop_state=AutonomousLoopState(mission_id="m_osc", cycle_id="c_osc"),
        budget=0,
        oscillation_status=OscillationStatus.CONFIRMED_OSCILLATION,
    )
    outcome, _ = DecisionOutcomeEvaluator.evaluate_decision_outcome(
        mission_id="m_osc",
        cycle_id="c_osc",
        decision_id="dec_osc",
        decision_type=LoopDecisionType.CONTINUE,
        policy_version="40.1.0",
        rule_matched_id="RULE_14_NORMAL_PROGRESSION",
        rules_evaluated=[],
        ctx=ctx,
        observed_outcome="Loop progressed despite oscillation",
        expected_decision=LoopDecisionType.REQUEST_HUMAN,
        available_unused_observations=["oscillation_status"],
    )

    assert outcome.decision_correctness == DecisionCorrectness.INCORRECT
    assert outcome.root_cause == DecisionErrorTaxonomy.OBSERVATION_GAP
    assert outcome.missed_observations == MissedObservationType.OBSERVATION_AVAILABLE_BUT_UNUSED


def test_classify_security_priority_error():
    ctx = PolicyEvaluationContext(
        mission_id="m_sec",
        cycle_id="c_sec",
        loop_state=AutonomousLoopState(mission_id="m_sec", cycle_id="c_sec"),
        budget=0,
        security_violation=True,
        security_reason="Sentinel breach",
    )
    outcome, _ = DecisionOutcomeEvaluator.evaluate_decision_outcome(
        mission_id="m_sec",
        cycle_id="c_sec",
        decision_id="dec_sec",
        decision_type=LoopDecisionType.CONTINUE,  # Unsafe continue!
        policy_version="40.1.0",
        rule_matched_id="RULE_14_NORMAL_PROGRESSION",
        rules_evaluated=[],
        ctx=ctx,
        observed_outcome="Security block bypassed",
        expected_decision=LoopDecisionType.BLOCK,
    )

    assert outcome.decision_correctness == DecisionCorrectness.INCORRECT
    assert outcome.severity == DecisionSeverity.CRITICAL
    assert outcome.root_cause == DecisionErrorTaxonomy.POLICY_PRIORITY_ERROR


def test_classify_prediction_error():
    ctx = PolicyEvaluationContext(
        mission_id="m_pred",
        cycle_id="c_pred",
        loop_state=AutonomousLoopState(mission_id="m_pred", cycle_id="c_pred"),
        budget=0,
        prediction_deviation=True,
    )
    outcome, _ = DecisionOutcomeEvaluator.evaluate_decision_outcome(
        mission_id="m_pred",
        cycle_id="c_pred",
        decision_id="dec_pred",
        decision_type=LoopDecisionType.CONTINUE,
        policy_version="40.1.0",
        rule_matched_id="RULE_14",
        rules_evaluated=[],
        ctx=ctx,
        observed_outcome="Discrepancy due to underprediction",
        expected_decision=LoopDecisionType.ADAPT,
        prediction_error=True,
    )

    assert outcome.root_cause == DecisionErrorTaxonomy.PREDICTION_ERROR
    assert outcome.severity == DecisionSeverity.LOW


def test_classify_execution_error_not_decision_flaw():
    ctx = PolicyEvaluationContext(
        mission_id="m_exec",
        cycle_id="c_exec",
        loop_state=AutonomousLoopState(mission_id="m_exec", cycle_id="c_exec"),
        budget=0,
    )
    outcome, _ = DecisionOutcomeEvaluator.evaluate_decision_outcome(
        mission_id="m_exec",
        cycle_id="c_exec",
        decision_id="dec_exec",
        decision_type=LoopDecisionType.CONTINUE,
        policy_version="40.1.0",
        rule_matched_id="RULE_14",
        rules_evaluated=[],
        ctx=ctx,
        observed_outcome="Process killed by external OOM",
        expected_decision=LoopDecisionType.REQUEST_HUMAN,
        execution_crash=True,
    )

    assert outcome.root_cause == DecisionErrorTaxonomy.EXECUTION_ERROR
    assert outcome.severity == DecisionSeverity.HIGH
