"""
JARVIS OS — Phase 41: Decision Replay Engine Tests
"""

import pytest
from agents.autonomous_loop.models import LoopDecisionType
from agents.decision_calibration.replay import DecisionReplayEngine, HistoricalDecisionRecord


def test_decision_replay_pure_read_only():
    corpus = [
        HistoricalDecisionRecord(
            cycle_id="c_1",
            mission_id="m_1",
            context_dict={"execution_success": True, "security_violation": False},
            original_decision=LoopDecisionType.CONTINUE,
            original_rule_id="RULE_14_NORMAL_PROGRESSION",
            observed_outcome="Clean progress",
        ),
        HistoricalDecisionRecord(
            cycle_id="c_2",
            mission_id="m_1",
            context_dict={"security_violation": True, "security_reason": "Banned privilege"},
            original_decision=LoopDecisionType.BLOCK,
            original_rule_id="RULE_01_SECURITY_BLOCK",
            observed_outcome="Security block",
        ),
    ]

    results = DecisionReplayEngine.replay_corpus(corpus)

    assert len(results) == 2
    assert results[0].replayed_decision == LoopDecisionType.CONTINUE
    assert results[0].matched is True
    assert results[1].replayed_decision == LoopDecisionType.BLOCK
    assert results[1].matched is True


def test_decision_replay_with_custom_policy_function():
    corpus = [
        HistoricalDecisionRecord(
            cycle_id="c_osc",
            mission_id="m_osc",
            context_dict={"oscillation_status": "CONFIRMED_OSCILLATION"},
            original_decision=LoopDecisionType.CONTINUE,
            original_rule_id="RULE_14_NORMAL_PROGRESSION",
            observed_outcome="Missed oscillation in v40.1.0",
        )
    ]

    # In baseline AutonomousDecisionPolicy, confirmed oscillation triggers RULE_03 -> REQUEST_HUMAN
    results = DecisionReplayEngine.replay_corpus(corpus)
    assert len(results) == 1
    assert results[0].replayed_decision == LoopDecisionType.REQUEST_HUMAN
    # It caught the divergence between the original error (CONTINUE) and replayed policy (REQUEST_HUMAN)
    assert results[0].matched is False
