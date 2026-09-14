"""
JARVIS OS — Phase 41: Policy Sandbox & A/B Comparison Tests
"""

import pytest
from agents.autonomous_loop.models import CausalExplanation, LoopDecisionType
from agents.autonomous_loop.policy import AutonomousDecisionPolicy, PolicyEvaluationContext, PolicyRuleDefinition
from agents.decision_calibration.replay import HistoricalDecisionRecord
from agents.decision_calibration.sandbox import PolicySandbox


def test_sandbox_compare_policies():
    corpus = [
        HistoricalDecisionRecord(
            cycle_id="c_1",
            mission_id="m_1",
            context_dict={"execution_success": True},
            original_decision=LoopDecisionType.CONTINUE,
            original_rule_id="RULE_14",
            observed_outcome="Normal",
        ),
        HistoricalDecisionRecord(
            cycle_id="c_2",
            mission_id="m_1",
            context_dict={"security_violation": True},
            original_decision=LoopDecisionType.BLOCK,
            original_rule_id="RULE_01",
            observed_outcome="Security block",
        ),
    ]
    expected = [LoopDecisionType.CONTINUE, LoopDecisionType.BLOCK]

    report = PolicySandbox.compare_policies(
        corpus=corpus,
        expected_decisions=expected,
        active_eval_fn=AutonomousDecisionPolicy.evaluate,
        proposed_eval_fn=AutonomousDecisionPolicy.evaluate,
        active_version="40.1.0",
        proposed_version="41.0.0",
    )

    assert report.corpus_size == 2
    assert report.active_accuracy == 1.0
    assert report.proposed_accuracy == 1.0
    assert report.safety_report.verdict == "PASSED"
    assert report.recommendation == "RECOMMENDED_FOR_HUMAN_REVIEW"
