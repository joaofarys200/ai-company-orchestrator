"""
Tests for Oscillation Detection, Mission Drift, Requirement Retention and State Consistency.
"""

import pytest
from agents.autonomous_loop.models import (
    DriftClassification,
    LoopCycleFingerprint,
    OscillationStatus,
)
from agents.autonomous_loop.state import AutonomousLoopStateManager


def test_oscillation_repeated_fingerprint():
    mgr = AutonomousLoopStateManager(mission_id="m_osc_01")
    mgr.initialize_baselines("Goal 1", [{"id": "REQ_1", "title": "Req 1"}])

    # Register cycle 1
    fp1 = mgr.register_fingerprint("c1", "plan_A", "REPAIR", "SyntaxError", "t1:FAILED")
    assert fp1.state_repetition_count == 0
    status, reason = mgr.check_oscillation(fp1, max_repetitions=2)
    assert status == OscillationStatus.NORMAL

    # Register cycle 2 (same signature)
    fp2 = mgr.register_fingerprint("c2", "plan_A", "REPAIR", "SyntaxError", "t1:FAILED")
    assert fp2.state_repetition_count == 1
    status, reason = mgr.check_oscillation(fp2, max_repetitions=2)
    assert status == OscillationStatus.SUSPECTED

    # Register cycle 3 (third repetition -> threshold exceeded)
    fp3 = mgr.register_fingerprint("c3", "plan_A", "REPAIR", "SyntaxError", "t1:FAILED")
    assert fp3.state_repetition_count == 2
    status, reason = mgr.check_oscillation(fp3, max_repetitions=2)
    assert status == OscillationStatus.CONFIRMED_OSCILLATION
    assert "exceeded threshold" in reason


def test_oscillation_alternating_cycles():
    mgr = AutonomousLoopStateManager(mission_id="m_osc_02")
    mgr.initialize_baselines("Goal 2", [{"id": "REQ_2", "title": "Req 2"}])

    # Pattern: A -> B -> A -> B
    mgr.register_fingerprint("c1", "plan_A", "REPLAN", "None", "t1:PENDING")
    mgr.register_fingerprint("c2", "plan_B", "REPLAN", "None", "t1:PENDING")
    mgr.register_fingerprint("c3", "plan_A", "REPLAN", "None", "t1:PENDING")
    fp4 = mgr.register_fingerprint("c4", "plan_B", "REPLAN", "None", "t1:PENDING")

    status, reason = mgr.check_oscillation(fp4, max_repetitions=5)
    assert status == OscillationStatus.CONFIRMED_OSCILLATION
    assert "Alternating oscillation detected" in reason


def test_mission_drift_detection():
    mgr = AutonomousLoopStateManager(mission_id="m_drift_01")
    mgr.initialize_baselines(
        intent="Criar dashboard de monitorização financeiro",
        requirements=[
            {"id": "REQ_FIN_1", "title": "Cálculo de Margem"},
            {"id": "REQ_FIN_2", "title": "Exportação PDF"},
        ],
    )

    # 1. No drift
    status, reason = mgr.detect_mission_drift(
        current_intent="Criar dashboard de monitorização financeiro",
        current_requirements=[
            {"id": "REQ_FIN_1", "title": "Cálculo de Margem"},
            {"id": "REQ_FIN_2", "title": "Exportação PDF"},
        ],
    )
    assert status == DriftClassification.NO_DRIFT

    # 2. Unexpected drift: requirement dropped without formal intent delta
    status, reason = mgr.detect_mission_drift(
        current_intent="Criar dashboard de monitorização financeiro",
        current_requirements=[
            {"id": "REQ_FIN_1", "title": "Cálculo de Margem"},
        ],
        formal_intent_changed=False,
    )
    assert status == DriftClassification.UNEXPECTED_DRIFT
    assert "Requirements dropped" in reason

    # 3. Controlled drift with formal intent change
    status, reason = mgr.detect_mission_drift(
        current_intent="Criar dashboard de monitorização financeiro com relatórios CSV",
        current_requirements=[
            {"id": "REQ_FIN_1", "title": "Cálculo de Margem"},
            {"id": "REQ_FIN_3", "title": "Exportação CSV"},
        ],
        formal_intent_changed=True,
    )
    assert status == DriftClassification.CONTROLLED_DRIFT


def test_requirement_retention_audit():
    mgr = AutonomousLoopStateManager(mission_id="m_ret_01")
    initial = [
        {"id": "REQ_01", "title": "Auth"},
        {"id": "REQ_02", "title": "DB"},
        {"id": "REQ_03", "title": "UI"},
    ]
    mgr.initialize_baselines("Goal", initial)

    # Planner accidentally drops REQ_02
    current = [
        {"id": "REQ_01", "title": "Auth"},
        {"id": "REQ_03", "title": "UI"},
    ]
    passed, rate, dropped = mgr.audit_requirement_retention(current)
    assert passed is False
    assert round(rate, 2) == 0.67
    assert dropped == ["REQ_02"]

    # All requirements retained
    passed, rate, dropped = mgr.audit_requirement_retention(initial)
    assert passed is True
    assert rate == 1.0
    assert dropped == []


def test_state_consistency_verification():
    mgr = AutonomousLoopStateManager(mission_id="m_consist_01")

    # Consistent: all validated and evidence present
    consistent, reason = mgr.verify_state_consistency(
        mission_status="COMPLETED",
        requirements=[{"id": "REQ_1", "status": "VALIDATED"}],
        evidence=[{"id": "EVD_1"}],
        active_blocks=False,
    )
    assert consistent is True

    # Inconsistent: completed but no evidence (Zero False Success violation)
    consistent, reason = mgr.verify_state_consistency(
        mission_status="COMPLETED",
        requirements=[{"id": "REQ_1", "status": "VALIDATED"}],
        evidence=[],
        active_blocks=False,
    )
    assert consistent is False
    assert "Zero False Success violated" in reason

    # Inconsistent: completed but active block exists
    consistent, reason = mgr.verify_state_consistency(
        mission_status="COMPLETED",
        requirements=[{"id": "REQ_1", "status": "VALIDATED"}],
        evidence=[{"id": "EVD_1"}],
        active_blocks=True,
    )
    assert consistent is False
    assert "active security/policy blocks exist" in reason
