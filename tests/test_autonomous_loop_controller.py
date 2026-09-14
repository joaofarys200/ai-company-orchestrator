"""
Tests for AutonomousLoopController: 12-step lifecycle coordination, events and Gate validation.
"""

import pytest
from agents.autonomous_loop.controller import AutonomousLoopController
from agents.autonomous_loop.models import (
    AdaptationBudget,
    AdaptationType,
    LoopDecisionType,
    LoopStage,
)


def test_controller_step_cycle_continue():
    events_captured = []

    def sink(event_type, payload):
        events_captured.append((event_type, payload))

    ctrl = AutonomousLoopController(
        mission_id="m_ctrl_01",
        user_intent="Construir micro-serviço com endpoints REST e testes",
        initial_requirements=[{"id": "REQ_01", "title": "Endpoints REST", "status": "IN_PROGRESS"}],
        initial_tasks=[
            {"id": "t1", "agent": "coder", "status": "PENDING", "files": ["server.py"]},
        ],
        event_sink=sink,
    )

    state, decision = ctrl.step_cycle()

    assert decision.decision == LoopDecisionType.CONTINUE
    assert state.cycle_id == "cycle_1"
    assert state.current_stage == LoopStage.NEXT_CYCLE
    assert state.loop_version == 2
    assert state.consecutive_successes == 1

    # Verify event types emitted
    emitted_types = [e[0] for e in events_captured]
    assert "LOOP_CYCLE_STARTED" in emitted_types
    assert "LOOP_PREDICTION_READY" in emitted_types
    assert "LOOP_EXECUTION_STARTED" in emitted_types
    assert "LOOP_OBSERVATION_RECORDED" in emitted_types
    assert "LOOP_COMPARISON_READY" in emitted_types
    assert "LOOP_DECISION_MADE" in emitted_types


def test_controller_step_cycle_repair_and_adaptation():
    events_captured = []

    def sink(event_type, payload):
        events_captured.append((event_type, payload))

    ctrl = AutonomousLoopController(
        mission_id="m_ctrl_02",
        user_intent="Desenvolver módulo com tolerância a falhas",
        initial_requirements=[{"id": "REQ_02", "title": "Parser", "status": "IN_PROGRESS"}],
        initial_tasks=[
            {"id": "t2", "agent": "coder", "status": "PENDING", "files": ["parser.py"]},
        ],
        event_sink=sink,
    )

    # Inject repairable failure
    sim_executions = [
        {
            "task_id": "t2",
            "status": "FAILED",
            "exit_code": 1,
            "files_touched": ["parser.py"],
            "error_message": "IndentationError: unexpected indent in parser.py line 4",
            "is_repairable": True,
        }
    ]
    sim_validations = [
        {"validation_type": "BUILD", "passed": False, "summary": "IndentationError in parser.py", "is_repairable": True}
    ]

    state, decision = ctrl.step_cycle(
        simulated_executions=sim_executions,
        simulated_validations=sim_validations,
    )

    assert decision.decision == LoopDecisionType.REPAIR
    assert ctrl.latest_proposal is not None
    assert ctrl.latest_proposal.adaptation_type == AdaptationType.REPAIR
    assert ctrl.latest_proposal.status == "APPLIED"
    assert len(state.active_repairs) == 1

    emitted_types = [e[0] for e in events_captured]
    assert "LOOP_ADAPTATION_PROPOSED" in emitted_types
    assert "LOOP_ADAPTATION_APPLIED" in emitted_types
    assert "LOOP_REPAIR_STARTED" in emitted_types


def test_controller_finish_gate():
    events_captured = []

    def sink(event_type, payload):
        events_captured.append((event_type, payload))

    ctrl = AutonomousLoopController(
        mission_id="m_ctrl_03",
        user_intent="Completar entrega validada",
        initial_requirements=[{"id": "REQ_03", "title": "Docs", "status": "VALIDATED"}],
        initial_tasks=[
            {"id": "t3", "agent": "coder", "status": "COMPLETED", "files": ["docs.md"]},
        ],
        event_sink=sink,
    )

    state, decision = ctrl.step_cycle(
        simulated_executions=[
            {"task_id": "t3", "status": "COMPLETED", "exit_code": 0, "files_touched": ["docs.md"]}
        ],
        simulated_validations=[
            {"validation_type": "TEST", "passed": True, "summary": "Docs pass", "evidence_id": "EVD_DOCS"}
        ],
    )

    assert decision.decision == LoopDecisionType.FINISH
    assert state.current_stage == LoopStage.FINISHED

    emitted_types = [e[0] for e in events_captured]
    assert "LOOP_FINISHED" in emitted_types


def test_controller_security_block():
    events_captured = []

    def sink(event_type, payload):
        events_captured.append((event_type, payload))

    ctrl = AutonomousLoopController(
        mission_id="m_ctrl_04",
        user_intent="Executar comando bloqueado",
        initial_requirements=[{"id": "REQ_04", "title": "Sys", "status": "IN_PROGRESS"}],
        initial_tasks=[{"id": "t4", "agent": "coder", "status": "PENDING"}],
        event_sink=sink,
    )

    state, decision = ctrl.step_cycle(sentinel_violation=True)

    assert decision.decision == LoopDecisionType.BLOCK
    assert state.current_stage == LoopStage.BLOCKED

    emitted_types = [e[0] for e in events_captured]
    assert "LOOP_BLOCKED" in emitted_types
