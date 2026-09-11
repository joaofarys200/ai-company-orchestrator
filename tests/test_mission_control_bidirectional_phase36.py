"""
Comprehensive automated tests for Fase 36 — Bidirectional Mission Control & Human Intervention.

Covers:
1. State machine valid/invalid transitions
2. PAUSE and RESUME semantics (checkpoint-safe, zero duplicate work)
3. CANCEL semantics (irreversible, history preservation, protection against completed missions)
4. Human approval flow (PENDING_APPROVAL -> APPROVED / REJECTED)
5. Priority change (CRITICAL, HIGH, NORMAL, LOW with DAG preservation)
6. Topological reordering (valid move vs. dependency violation rejection)
7. Stale command detection (expected_mission_version mismatch -> STALE)
8. Idempotency deduplication (repeated commands with same idempotency_key/command_id)
9. Security Sentinel rejection (malicious injection payloads -> SECURITY_BLOCK)
10. WebSocket contract bijection and handler dispatch
"""

import pytest
from agents.mission_control_engine import (
    MissionControlEngine,
    MissionControlCommand,
    CommandType,
    CommandStatus,
    MissionControlStatus,
    PriorityLevel,
    validate_state_transition,
)
from backend.websocket.handlers.missions import MissionWebSocketHandler
from backend.websocket.context import WebSocketSessionState


@pytest.fixture(autouse=True)
def reset_engine():
    """Ensure clean scenario state before and after each test."""
    MissionControlEngine.reset_scenarios()
    yield
    MissionControlEngine.reset_scenarios()


# ============================================================================
# 1. STATE TRANSITION MATRIX TESTS
# ============================================================================

def test_state_machine_valid_transitions():
    ok, _ = validate_state_transition(MissionControlStatus.RUNNING, MissionControlStatus.PAUSED)
    assert ok is True
    ok, _ = validate_state_transition(MissionControlStatus.PAUSED, MissionControlStatus.RUNNING)
    assert ok is True
    ok, _ = validate_state_transition(MissionControlStatus.RUNNING, MissionControlStatus.CANCELLING)
    assert ok is True
    ok, _ = validate_state_transition(MissionControlStatus.CANCELLING, MissionControlStatus.CANCELLED)
    assert ok is True
    ok, _ = validate_state_transition(MissionControlStatus.PAUSED, MissionControlStatus.CANCELLING)
    assert ok is True
    ok, _ = validate_state_transition(MissionControlStatus.RUNNING, MissionControlStatus.COMPLETED)
    assert ok is True


def test_state_machine_invalid_transitions():
    # Cancellation is irreversible
    ok, reason = validate_state_transition(MissionControlStatus.CANCELLED, MissionControlStatus.RUNNING)
    assert ok is False
    assert "CANCELLED" in reason

    ok, reason = validate_state_transition(MissionControlStatus.CANCELLED, MissionControlStatus.PAUSED)
    assert ok is False

    # Completed missions cannot be paused or cancelled
    ok, reason = validate_state_transition(MissionControlStatus.COMPLETED, MissionControlStatus.PAUSED)
    assert ok is False
    ok, reason = validate_state_transition(MissionControlStatus.COMPLETED, MissionControlStatus.CANCELLING)
    assert ok is False
    ok, reason = validate_state_transition(MissionControlStatus.COMPLETED, MissionControlStatus.CANCELLED)
    assert ok is False


# ============================================================================
# 2. PAUSE AND RESUME SEMANTICS
# ============================================================================

def test_pause_and_resume_lifecycle():
    state = MissionControlEngine.get_interactive_state()
    assert state.status == MissionControlStatus.RUNNING
    initial_version = state.mission_version

    # Pause command
    pause_cmd = MissionControlCommand(
        command_id="cmd_pause_01",
        mission_id=state.mission_id,
        command_type=CommandType.PAUSE,
        user_id="operator_joao",
        expected_mission_version=initial_version,
        reason="Suspender para inspecao de schema",
    )
    res_pause = MissionControlEngine.execute_command(pause_cmd)
    assert res_pause.status == CommandStatus.ACCEPTED
    assert res_pause.mission_version == initial_version + 1
    assert res_pause.state_dict["status"] == MissionControlStatus.PAUSED.value

    # Verify audit record
    history = res_pause.state_dict["command_history"]
    assert len(history) == 1
    assert history[0]["command_id"] == "cmd_pause_01"
    assert history[0]["command_type"] == "PAUSE"
    assert history[0]["old_state"] == "RUNNING"
    assert history[0]["new_state"] == "PAUSED"

    # Cannot pause an already paused mission
    duplicate_pause = MissionControlCommand(
        command_id="cmd_pause_02",
        mission_id=state.mission_id,
        command_type=CommandType.PAUSE,
        user_id="operator_joao",
        expected_mission_version=res_pause.mission_version,
    )
    res_dup_pause = MissionControlEngine.execute_command(duplicate_pause)
    assert res_dup_pause.status == CommandStatus.INVALID_STATE

    # Resume command
    resume_cmd = MissionControlCommand(
        command_id="cmd_resume_01",
        mission_id=state.mission_id,
        command_type=CommandType.RESUME,
        user_id="operator_joao",
        expected_mission_version=res_pause.mission_version,
        reason="Retomar execucao apos confirmacao de seguranca",
    )
    res_resume = MissionControlEngine.execute_command(resume_cmd)
    assert res_resume.status == CommandStatus.ACCEPTED
    assert res_resume.mission_version == res_pause.mission_version + 1
    assert res_resume.state_dict["status"] == MissionControlStatus.RUNNING.value

    # Verify audit history has both
    assert len(res_resume.state_dict["command_history"]) == 2


# ============================================================================
# 3. CANCEL SEMANTICS & IMMUTABILITY
# ============================================================================

def test_cancel_cooperative_and_irreversible():
    state = MissionControlEngine.get_interactive_state()
    v = state.mission_version

    cancel_cmd = MissionControlCommand(
        command_id="cmd_cancel_01",
        mission_id=state.mission_id,
        command_type=CommandType.CANCEL,
        user_id="operator_lead",
        expected_mission_version=v,
        reason="Abordar missao para manutencao de emergência",
    )
    res_cancel = MissionControlEngine.execute_command(cancel_cmd)
    assert res_cancel.status == CommandStatus.ACCEPTED
    assert res_cancel.state_dict["status"] == MissionControlStatus.CANCELLED.value
    assert res_cancel.state_dict["current_stage"] == "COMPLETION"

    # Verify history is preserved
    assert len(res_cancel.state_dict["command_history"]) >= 1
    assert res_cancel.state_dict["command_history"][0]["new_state"] == "CANCELLED"

    # Cannot resume or pause a cancelled mission
    resume_cmd = MissionControlCommand(
        command_id="cmd_resume_after_cancel",
        mission_id=state.mission_id,
        command_type=CommandType.RESUME,
        expected_mission_version=res_cancel.mission_version,
    )
    res_after = MissionControlEngine.execute_command(resume_cmd)
    assert res_after.status == CommandStatus.INVALID_STATE


def test_cannot_cancel_completed_mission():
    state = MissionControlEngine.get_interactive_state()
    # Force state to COMPLETED
    state.status = MissionControlStatus.COMPLETED
    state.mission_version += 1

    cancel_cmd = MissionControlCommand(
        command_id="cmd_cancel_completed",
        mission_id=state.mission_id,
        command_type=CommandType.CANCEL,
        expected_mission_version=state.mission_version,
    )
    res = MissionControlEngine.execute_command(cancel_cmd)
    assert res.status == CommandStatus.INVALID_STATE
    assert "COMPLETED" in res.reason


# ============================================================================
# 4. HUMAN APPROVAL GATE (PENDING_APPROVAL -> APPROVED / REJECTED)
# ============================================================================

def test_human_approval_approve():
    state = MissionControlEngine.get_interactive_state()
    v = state.mission_version

    # TSK_03 is in PENDING_APPROVAL
    task_03 = next(t for t in state.tasks if t["id"] == "TSK_03")
    assert task_03["status"] == "PENDING_APPROVAL"
    assert task_03["approval_status"] == "PENDING_APPROVAL"

    approve_cmd = MissionControlCommand(
        command_id="cmd_approve_01",
        mission_id=state.mission_id,
        command_type=CommandType.APPROVE,
        target_task_id="TSK_03",
        expected_mission_version=v,
        payload={"decision": "APPROVE"},
        reason="Validacao de schema aprovada pelo DBA",
    )
    res = MissionControlEngine.execute_command(approve_cmd)
    assert res.status == CommandStatus.ACCEPTED
    updated_task = next(t for t in res.state_dict["tasks"] if t["id"] == "TSK_03")
    assert updated_task["status"] == "DONE"
    assert updated_task["approval_status"] == "APPROVED"
    assert "Aprovado pelo operador humano" in updated_task["evidence"]


def test_human_approval_reject():
    state = MissionControlEngine.get_interactive_state()
    v = state.mission_version

    reject_cmd = MissionControlCommand(
        command_id="cmd_reject_01",
        mission_id=state.mission_id,
        command_type=CommandType.APPROVE,
        target_task_id="TSK_03",
        expected_mission_version=v,
        payload={"decision": "REJECT"},
        reason="Migracao viola restricao de dados legados",
    )
    res = MissionControlEngine.execute_command(reject_cmd)
    assert res.status == CommandStatus.ACCEPTED
    updated_task = next(t for t in res.state_dict["tasks"] if t["id"] == "TSK_03")
    assert updated_task["status"] == "FAILED"
    assert updated_task["approval_status"] == "REJECTED"


def test_approval_on_non_pending_task_fails():
    state = MissionControlEngine.get_interactive_state()
    # TSK_01 is DONE, not PENDING_APPROVAL
    cmd = MissionControlCommand(
        command_id="cmd_approve_done",
        mission_id=state.mission_id,
        command_type=CommandType.APPROVE,
        target_task_id="TSK_01",
        expected_mission_version=state.mission_version,
    )
    res = MissionControlEngine.execute_command(cmd)
    assert res.status == CommandStatus.INVALID_STATE


# ============================================================================
# 5. PRIORITY ALTERATION & DAG PRESERVATION
# ============================================================================

def test_change_priority_preserves_dag():
    state = MissionControlEngine.get_interactive_state()
    v = state.mission_version

    cmd = MissionControlCommand(
        command_id="cmd_prio_01",
        mission_id=state.mission_id,
        command_type=CommandType.CHANGE_PRIORITY,
        target_task_id="TSK_04",
        expected_mission_version=v,
        payload={"new_priority": "CRITICAL"},
        reason="Priorizar execucao de suite de calculo",
    )
    res = MissionControlEngine.execute_command(cmd)
    assert res.status == CommandStatus.ACCEPTED
    tsk4 = next(t for t in res.state_dict["tasks"] if t["id"] == "TSK_04")
    assert tsk4["priority"] == PriorityLevel.CRITICAL.value

    # Check that dependencies remain strictly intact
    assert tsk4["dependencies"] == ["TSK_03"]


# ============================================================================
# 6. TOPOLOGICAL REORDERING & DEPENDENCY INTEGRITY
# ============================================================================

def test_topological_reorder_valid_within_independence_frontier():
    state = MissionControlEngine.get_interactive_state()
    v = state.mission_version

    # Current order: [TSK_01, TSK_02, TSK_03, TSK_04, TSK_05]
    # TSK_04 and TSK_05 are independent of each other (TSK_04 depends on TSK_03, TSK_05 depends on TSK_02).
    # Moving TSK_05 up to index 3 (swapping with TSK_04) is topographically valid.
    cmd = MissionControlCommand(
        command_id="cmd_reorder_valid",
        mission_id=state.mission_id,
        command_type=CommandType.REORDER,
        target_task_id="TSK_05",
        expected_mission_version=v,
        payload={"direction": "UP"},
        reason="Adiantar validacao de browser enquanto backend calcula",
    )
    res = MissionControlEngine.execute_command(cmd)
    assert res.status == CommandStatus.ACCEPTED
    task_ids = [t["id"] for t in res.state_dict["tasks"]]
    assert task_ids == ["TSK_01", "TSK_02", "TSK_03", "TSK_05", "TSK_04"]


def test_topological_reorder_rejects_dependency_violation():
    state = MissionControlEngine.get_interactive_state()
    v = state.mission_version

    # TSK_03 depends on TSK_02.
    # Moving TSK_03 up (before TSK_02) violates causal ordering and must be rejected!
    cmd = MissionControlCommand(
        command_id="cmd_reorder_invalid",
        mission_id=state.mission_id,
        command_type=CommandType.REORDER,
        target_task_id="TSK_03",
        expected_mission_version=v,
        payload={"direction": "UP"},
        reason="Tentativa de mover tarefa antes de sua dependencia",
    )
    res = MissionControlEngine.execute_command(cmd)
    assert res.status in (CommandStatus.REJECTED, CommandStatus.INVALID_STATE)
    assert "topológica" in res.reason.lower() or "dependência" in res.reason.lower()


# ============================================================================
# 7. OPTIMISTIC CONCURRENCY / STALE COMMAND DETECTION
# ============================================================================

def test_stale_command_rejection():
    state = MissionControlEngine.get_interactive_state()
    current_version = state.mission_version

    # Send a command expecting version 999 (mismatch)
    stale_cmd = MissionControlCommand(
        command_id="cmd_stale_01",
        mission_id=state.mission_id,
        command_type=CommandType.PAUSE,
        expected_mission_version=999,
        reason="Comando enviado com versao desatualizada",
    )
    res = MissionControlEngine.execute_command(stale_cmd)
    assert res.status == CommandStatus.STALE
    assert "999" in res.reason and str(current_version) in res.reason


# ============================================================================
# 8. IDEMPOTENCY & DEDUPLICATION BENCHMARK
# ============================================================================

def test_idempotency_single_and_burst_duplicates():
    state = MissionControlEngine.get_interactive_state()
    v = state.mission_version

    cmd = MissionControlCommand(
        command_id="cmd_idempotent_test",
        mission_id=state.mission_id,
        command_type=CommandType.PAUSE,
        idempotency_key="unique_idem_key_777",
        expected_mission_version=v,
    )

    # First execution
    res1 = MissionControlEngine.execute_command(cmd)
    assert res1.status == CommandStatus.ACCEPTED
    v_after = res1.mission_version

    # Second execution with same command_id / idempotency_key
    res2 = MissionControlEngine.execute_command(cmd)
    assert res2.status == CommandStatus.ACCEPTED
    assert res2.mission_version == v_after  # Did not increment again!

    # 10 duplicate bursts
    for _ in range(10):
        res_burst = MissionControlEngine.execute_command(cmd)
        assert res_burst.status == CommandStatus.ACCEPTED
        assert res_burst.mission_version == v_after


# ============================================================================
# 9. SECURITY SENTINEL ENFORCEMENT ON MALICIOUS PAYLOADS
# ============================================================================

def test_security_sentinel_blocks_destructive_payload():
    state = MissionControlEngine.get_interactive_state()
    v = state.mission_version

    malicious_cmd = MissionControlCommand(
        command_id="cmd_malicious_01",
        mission_id=state.mission_id,
        command_type=CommandType.CHANGE_PRIORITY,
        target_task_id="TSK_02",
        expected_mission_version=v,
        payload={"attack": "rm -rf /", "bypass_sentinel": True},
        reason="Tentativa maliciosa de injecao de comando",
    )
    res = MissionControlEngine.execute_command(malicious_cmd)
    assert res.status == CommandStatus.SECURITY_BLOCK
    assert "Security Sentinel" in res.reason
    # Ensure mission state was NOT modified
    current_state = MissionControlEngine.get_interactive_state()
    assert current_state.mission_version == v


# ============================================================================
# 10. WEBSOCKET DISPATCHER INTEGRATION
# ============================================================================

@pytest.mark.anyio
async def test_websocket_handler_dispatches_mission_control_command():
    class MockConnections:
        def __init__(self):
            self.sent = []
            self.broadcasted = []

        async def send(self, ws, msg):
            self.sent.append(msg)

        async def broadcast(self, msg):
            self.broadcasted.append(msg)

    class MockResponder:
        def __init__(self):
            self.connections = MockConnections()

    responder = MockResponder()
    handler = MissionWebSocketHandler(
        mission_planner=None,
        mission_executor=None,
        mission_autonomy=None,
        responder=responder,
    )

    class MockWs:
        pass

    ws = MockWs()
    session = WebSocketSessionState()
    session.selected_project_id = "proj_test"

    message = {
        "type": "mission_control_command",
        "command_id": "ws_cmd_pause_01",
        "mission_id": "m_p36_interactive",
        "command_type": "PAUSE",
        "user_id": "operator_ws",
        "expected_mission_version": 1,
        "reason": "Pausa via websocket dispatcher",
    }

    await handler.handle(ws, message, session)

    # Verify response sent back to client
    assert len(responder.connections.sent) == 1
    resp = responder.connections.sent[0]
    assert resp["type"] == "mission_control_command_result"
    assert resp["status"] == "ACCEPTED"
    assert resp["mission_version"] == 2

    # Verify state update was broadcast
    assert len(responder.connections.broadcasted) == 1
    broadcast_msg = responder.connections.broadcasted[0]
    assert broadcast_msg["type"] == "mission_control_state"
    assert broadcast_msg["data"]["status"] == "PAUSED"
