"""
JARVIS OS — Phase 41: Shadow Policy Engine Tests
"""

import pytest
from agents.autonomous_loop.models import AutonomousLoopState, LoopDecisionType, OscillationStatus
from agents.autonomous_loop.policy import AutonomousDecisionPolicy, PolicyEvaluationContext
from agents.decision_calibration.shadow import ShadowPolicyEngine


def test_shadow_policy_evaluation_and_agreement():
    engine = ShadowPolicyEngine(shadow_version="41.0.0-shadow")
    ctx = PolicyEvaluationContext(
        mission_id="m_shd",
        cycle_id="c_1",
        loop_state=AutonomousLoopState(mission_id="m_shd", cycle_id="c_1"),
        budget=0,
        execution_success=True,
    )

    rec = engine.evaluate_shadow(
        cycle_id="c_1",
        active_version="40.1.0",
        active_decision=LoopDecisionType.CONTINUE,
        ctx=ctx,
        shadow_eval_fn=AutonomousDecisionPolicy.evaluate,
    )

    assert rec is not None
    assert rec.agreement is True
    assert rec.shadow_decision == LoopDecisionType.CONTINUE


def test_shadow_policy_disagreement_logging():
    engine = ShadowPolicyEngine(shadow_version="41.0.0-shadow")
    ctx = PolicyEvaluationContext(
        mission_id="m_shd",
        cycle_id="c_2",
        loop_state=AutonomousLoopState(mission_id="m_shd", cycle_id="c_2"),
        budget=0,
        oscillation_status=OscillationStatus.CONFIRMED_OSCILLATION,
    )

    # Active made mistake: CONTINUE, shadow evaluated correctly: REQUEST_HUMAN
    rec = engine.evaluate_shadow(
        cycle_id="c_2",
        active_version="40.1.0",
        active_decision=LoopDecisionType.CONTINUE,
        ctx=ctx,
        shadow_eval_fn=AutonomousDecisionPolicy.evaluate,
    )

    assert rec is not None
    assert rec.agreement is False
    assert rec.active_decision == LoopDecisionType.CONTINUE
    assert rec.shadow_decision == LoopDecisionType.REQUEST_HUMAN
    assert "Shadow version" in rec.disagreement_reason or "Shadow chose REQUEST_HUMAN" in rec.disagreement_reason

    summary = engine.get_summary()
    assert summary["disagreements"] == 1
    assert len(summary["recent_disagreements"]) == 1
