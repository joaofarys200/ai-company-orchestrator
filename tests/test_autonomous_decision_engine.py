"""
Tests for AutonomousDecisionEngine: observable inputs to deterministic decisions.
"""

import pytest
from agents.autonomous_loop.decision import AutonomousDecisionEngine, AutonomousDecisionResult
from agents.autonomous_loop.models import (
    AdaptationBudget,
    AutonomousLoopState,
    LoopDecisionType,
    LoopObservationOutcome,
    LoopStage,
)
from agents.autonomous_loop.observation import AutonomousLoopObserver


def test_decision_engine_continue_normal():
    mission_id = "m_eng_01"
    state = AutonomousLoopState(mission_id=mission_id)
    budget = AdaptationBudget()

    obs = AutonomousLoopObserver.observe(
        mission_id=mission_id,
        cycle_id="cycle_1",
        task_executions=[
            {"task_id": "t1", "status": "COMPLETED", "exit_code": 0, "files_touched": ["app.py"]},
        ],
        validation_reports=[
            {"validation_type": "TEST", "passed": True, "summary": "All tests pass", "evidence_id": "EVD_1"},
        ],
    )

    res = AutonomousDecisionEngine.evaluate_decision(
        mission_id=mission_id,
        cycle_id="cycle_1",
        loop_state=state,
        budget=budget,
        observation=obs,
    )

    assert res.decision == LoopDecisionType.CONTINUE
    assert res.rule_matched == "RULE_14_NORMAL_PROGRESSION"
    assert "normally" in res.causal_explanation.observation.lower()
    assert res.context_summary["has_failures"] is False


def test_decision_engine_repair_on_syntax_error():
    mission_id = "m_eng_02"
    state = AutonomousLoopState(mission_id=mission_id)
    budget = AdaptationBudget()

    obs = AutonomousLoopObserver.observe(
        mission_id=mission_id,
        cycle_id="cycle_2",
        task_executions=[
            {
                "task_id": "t2",
                "status": "FAILED",
                "exit_code": 1,
                "files_touched": ["main.py"],
                "error_message": "SyntaxError: invalid syntax in line 12",
                "is_repairable": True,
            },
        ],
        validation_reports=[
            {"validation_type": "BUILD", "passed": False, "summary": "SyntaxError in main.py", "is_repairable": True},
        ],
    )

    res = AutonomousDecisionEngine.evaluate_decision(
        mission_id=mission_id,
        cycle_id="cycle_2",
        loop_state=state,
        budget=budget,
        observation=obs,
    )

    assert res.decision == LoopDecisionType.REPAIR
    assert res.rule_matched == "RULE_09_REPAIRABLE_VALIDATION_FAILURE"
    assert "Repairable failure" in res.causal_explanation.observation
    assert res.context_summary["has_failures"] is True
    assert res.context_summary["is_repairable"] is True


def test_decision_engine_finish_gate():
    mission_id = "m_eng_03"
    state = AutonomousLoopState(mission_id=mission_id)
    budget = AdaptationBudget()

    obs = AutonomousLoopObserver.observe(
        mission_id=mission_id,
        cycle_id="cycle_3",
        task_executions=[
            {"task_id": "t3", "status": "COMPLETED", "exit_code": 0, "files_touched": ["done.py"]},
        ],
        validation_reports=[
            {"validation_type": "TEST", "passed": True, "summary": "Full suite passes", "evidence_id": "EVD_FINAL"},
        ],
    )

    res = AutonomousDecisionEngine.evaluate_decision(
        mission_id=mission_id,
        cycle_id="cycle_3",
        loop_state=state,
        budget=budget,
        observation=obs,
        all_requirements_satisfied=True,
    )

    assert res.decision == LoopDecisionType.FINISH
    assert res.rule_matched == "RULE_07_FINISH_GATE_SATISFIED"
    assert "All mission requirements satisfied" in res.causal_explanation.observation
