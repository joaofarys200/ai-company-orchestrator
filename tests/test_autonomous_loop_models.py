"""
Tests for Phase 40 Autonomous Loop Data Models, Hashing, and Fingerprints.
"""

import pytest
import time
from agents.autonomous_loop.models import (
    AdaptationBudget,
    AdaptationProposal,
    AdaptationType,
    AutonomousLoopState,
    CausalExplanation,
    DriftClassification,
    LoopCycleFingerprint,
    LoopDecisionType,
    LoopObservationOutcome,
    LoopSnapshot,
    LoopStage,
    OscillationStatus,
)


def test_autonomous_loop_state_hashing_and_roundtrip():
    state = AutonomousLoopState(
        mission_id="m_test_01",
        loop_version=1,
        cycle_id="cycle_1",
        mission_version=2,
        intent_version=1,
        plan_version=3,
        current_stage=LoopStage.DECIDE,
        current_decision=LoopDecisionType.CONTINUE,
        latest_prediction_id="pred_123",
        latest_outcome_id="out_456",
        latest_evidence_ids=["EVD_01", "EVD_02"],
        adaptation_count=2,
        consecutive_successes=3,
        consecutive_failures=0,
    )

    h1 = state.compute_state_hash()
    assert len(h1) == 16
    assert state.state_hash == h1

    # Roundtrip serialization
    d = state.to_dict()
    assert d["current_stage"] == "DECIDE"
    assert d["current_decision"] == "CONTINUE"

    restored = AutonomousLoopState.from_dict(d)
    assert restored.mission_id == "m_test_01"
    assert restored.current_stage == LoopStage.DECIDE
    assert restored.current_decision == LoopDecisionType.CONTINUE
    assert restored.compute_state_hash() == h1


def test_loop_snapshot_deterministic_hashing():
    snap1 = LoopSnapshot(
        snapshot_id="snap_c1_01",
        cycle_id="cycle_1",
        mission_id="m_test_01",
        intent_version=1,
        plan_version=1,
        mission_state_hash="state_abc",
        dag_hash="dag_123",
        active_tasks=[{"id": "task_1", "status": "COMPLETED"}],
        requirements=[{"id": "REQ_01", "title": "Auth"}],
        constraints=[],
        evidence=[{"id": "EVD_01"}],
    )
    h1 = snap1.compute_deterministic_hash()
    assert len(h1) == 16

    # Same content must produce identical hash
    snap2 = LoopSnapshot(
        snapshot_id="snap_c1_01",
        cycle_id="cycle_1",
        mission_id="m_test_01",
        intent_version=1,
        plan_version=1,
        mission_state_hash="state_abc",
        dag_hash="dag_123",
        active_tasks=[{"id": "task_1", "status": "COMPLETED"}],
        requirements=[{"id": "REQ_01", "title": "Auth"}],
        constraints=[],
        evidence=[{"id": "EVD_01"}],
    )
    h2 = snap2.compute_deterministic_hash()
    assert h1 == h2

    # Different content produces different hash
    snap3 = LoopSnapshot(
        snapshot_id="snap_c1_02",
        cycle_id="cycle_2",
        mission_id="m_test_01",
        intent_version=2,
        plan_version=1,
        mission_state_hash="state_diff",
        dag_hash="dag_123",
    )
    h3 = snap3.compute_deterministic_hash()
    assert h1 != h3


def test_loop_cycle_fingerprint_hashing():
    fp1 = LoopCycleFingerprint(
        cycle_id="cycle_1",
        plan_hash="plan_hash_1",
        adaptation_signature="ADD_VALIDATION",
        failure_signature="CLEAN",
        task_states_signature="t1:COMPLETED;t2:PENDING",
    )
    h1 = fp1.compute_hash()
    assert len(h1) == 16
    assert fp1.fingerprint_hash == h1

    # Deserialization check
    d = fp1.to_dict()
    restored = LoopCycleFingerprint.from_dict(d)
    assert restored.fingerprint_hash == h1


def test_adaptation_proposal_lifecycle():
    proposal = AdaptationProposal(
        adaptation_id="adapt_01",
        cycle_id="cycle_1",
        adaptation_type=AdaptationType.ADD_VALIDATION,
        reason="Empirical test validation needed after code change",
        source_observation={"observation_id": "obs_01"},
        previous_plan_version=1,
        proposed_change={"action": "ADD_TASK", "target": "task_val_01"},
        risk="LOW",
        requires_approval=False,
    )
    assert proposal.status == "PROPOSED"
    d = proposal.to_dict()
    assert d["adaptation_type"] == "ADD_VALIDATION"

    restored = AdaptationProposal.from_dict(d)
    assert restored.adaptation_type == AdaptationType.ADD_VALIDATION
    assert restored.reason == proposal.reason


def test_causal_explanation_structure():
    expl = CausalExplanation(
        observation="Build failed with syntax error in module x.py",
        rule="RULE_09_REPAIRABLE_VALIDATION_FAILURE",
        decision="REPAIR",
        consequence="Dispatch AST diagnostic repair without declaring premature success",
        evidence_refs=["ast_ast.log", "compiler_stderr.txt"],
    )
    d = expl.to_dict()
    assert d["decision"] == "REPAIR"
    assert len(d["evidence_refs"]) == 2
    restored = CausalExplanation.from_dict(d)
    assert restored.rule == expl.rule
