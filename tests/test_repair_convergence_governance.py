"""
JARVIS OS — Phase 56: Unit & Integration Test Suite
Tests for Autonomous Repair Termination & Convergence Governance (24 Mandatory Scenarios).
"""

import time
import pytest
from typing import Dict, Any, List

from agents.repair_convergence_governance.models import (
    AdaptiveBudgetConfig,
    ConvergenceCertificate,
    ConvergenceState,
    ConvergenceVerdict,
    CycleReport,
    CycleType,
    DivergenceReport,
    DivergenceScore,
    DivergenceType,
    EscalationStatus,
    EscalationTier,
    EscalationTicket,
    ProgressDelta,
    ProgressVector,
    RepairStepSnapshot,
    StallReport,
    StallType,
    TerminationBudget,
    TerminationEscalationReason,
    TerminationReason,
    TerminationState,
    compute_deterministic_hash,
    compute_vector_delta,
)
from agents.repair_convergence_governance.cycle_detector import CycleDetector
from agents.repair_convergence_governance.oscillation_detector import OscillationDetector
from agents.repair_convergence_governance.stall_detector import StallDetector
from agents.repair_convergence_governance.divergence_detector import DivergenceDetector
from agents.repair_convergence_governance.progress_tracker import ProgressVectorTracker
from agents.repair_convergence_governance.budget_manager import TerminationBudgetManager
from agents.repair_convergence_governance.escalation import HumanEscalationManager
from agents.repair_convergence_governance.certificate import ConvergenceCertificateEngine
from agents.repair_convergence_governance.ledger import ProgressLedger
from agents.repair_convergence_governance.replay import DeterministicReplayEngine
from agents.repair_convergence_governance.recovery import CrashRecoveryEngine
from agents.repair_convergence_governance.predictive import PredictiveConvergenceEngine
from agents.repair_convergence_governance.security import ConvergenceSecuritySentinel
from agents.repair_convergence_governance.experience import ConvergenceExperienceStore
from agents.repair_convergence_governance.proof import CompositeConvergenceProofEngine
from agents.repair_convergence_governance.bridge import AutonomousRepairConvergenceBridge


# 1. Success Termination
def test_success_termination():
    bridge = AutonomousRepairConvergenceBridge()
    init_snap = RepairStepSnapshot(
        iteration_id=0,
        timestamp=time.time(),
        active_failures=["err_missing_import", "err_undefined_var"],
        risk_score=0.45,
        behavioral_proof_coverage=0.60,
    )
    bridge.initialize_governance("msn_01", "tx_01", init_snap)

    step1 = RepairStepSnapshot(
        iteration_id=1,
        timestamp=time.time(),
        active_failures=["err_undefined_var"],
        fixed_failures=["err_missing_import"],
        patches_applied=["patch_import"],
        modified_files=["app.py"],
        risk_score=0.25,
        behavioral_proof_coverage=0.75,
        test_pass_rate=0.5,
    )
    p1 = ProgressVector(resolved_failures=1, new_failures=0, blocking_failures=1, coverage_gain=0.15, risk_reduction=0.20, proof_progress=0.5)
    proof1 = {"patch_id": "patch_import", "verified": True}
    bridge.evaluate_step(step1, p1, patch_proof=proof1)

    step2 = RepairStepSnapshot(
        iteration_id=2,
        timestamp=time.time(),
        active_failures=[],
        fixed_failures=["err_missing_import", "err_undefined_var"],
        patches_applied=["patch_var"],
        modified_files=["app.py"],
        risk_score=0.05,
        behavioral_proof_coverage=0.92,
        test_pass_rate=1.0,
    )
    p2 = ProgressVector(resolved_failures=2, new_failures=0, blocking_failures=0, coverage_gain=0.32, risk_reduction=0.40, proof_progress=1.0)
    proof2 = {"patch_id": "patch_var", "verified": True}
    state, decision = bridge.evaluate_step(step2, p2, patch_proof=proof2, invariants_verified=True)

    assert state.state == TerminationState.COMMITTED
    assert decision["action"] == "COMMIT_TRANSACTION"
    cert = bridge.finalize_governance()
    assert cert.convergence_verdict == ConvergenceVerdict.CONVERGED
    assert cert.termination_reason == TerminationReason.CONVERGED_VERIFIED


# 2. Stall Detection
def test_stall_detection():
    detector = StallDetector(min_stagnant_iterations=3, epsilon_progress=0.01)
    history = [
        RepairStepSnapshot(1, time.time(), active_failures=["err1", "err2"], risk_score=0.420),
        RepairStepSnapshot(2, time.time(), active_failures=["err1", "err2"], risk_score=0.421),
        RepairStepSnapshot(3, time.time(), active_failures=["err1", "err2"], risk_score=0.420),
    ]
    report = detector.evaluate_stall(history)
    assert report.stalled is True
    assert report.stall_type in (StallType.FAILURE_COUNT_UNCHANGED, StallType.RISK_STAGNATION)
    assert report.consecutive_stagnant_iterations == 3


# 3. Divergence Detection
def test_divergence_detection():
    detector = DivergenceDetector(divergence_threshold=0.75, failure_spike_threshold=3)
    history = [
        RepairStepSnapshot(0, time.time(), active_failures=["err1"], risk_score=0.20, behavioral_proof_coverage=0.80),
        RepairStepSnapshot(1, time.time(), active_failures=["err1", "err2", "err3", "err4"], risk_score=0.70, behavioral_proof_coverage=0.50),
    ]
    report = detector.evaluate_divergence(history)
    assert report.diverging is True
    assert report.divergence_velocity > 0.75


# 4. Cycle Detection Length 2 (A -> B -> A)
def test_cycle_detection_length_2():
    detector = CycleDetector()
    history = [
        RepairStepSnapshot(1, time.time(), active_failures=["errA"]),
        RepairStepSnapshot(2, time.time(), active_failures=["errB"]),
        RepairStepSnapshot(3, time.time(), active_failures=["errA"]),
    ]
    report = detector.detect_cycles(history)
    assert report.cycle_detected is True
    assert report.cycle_type == CycleType.PING_PONG_FAILURE_CYCLE
    assert report.cycle_period == 2


# 5. Cycle Detection Length 3 (A -> B -> C -> A)
def test_cycle_detection_length_3():
    detector = CycleDetector()
    history = [
        RepairStepSnapshot(1, time.time(), active_failures=["errA"]),
        RepairStepSnapshot(2, time.time(), active_failures=["errB"]),
        RepairStepSnapshot(3, time.time(), active_failures=["errC"]),
        RepairStepSnapshot(4, time.time(), active_failures=["errA"]),
    ]
    report = detector.detect_cycles(history)
    assert report.cycle_detected is True
    assert report.cycle_period == 3


# 6. Repeated Repair Detection
def test_repeated_repair_detection():
    detector = CycleDetector()
    history = [
        RepairStepSnapshot(1, time.time(), active_failures=["err1"], patches_applied=["patch_fix_x"]),
        RepairStepSnapshot(2, time.time(), active_failures=["err1"], patches_applied=["patch_fix_x"]),
    ]
    report = detector.detect_cycles(history)
    assert report.cycle_detected is True
    assert report.cycle_type == CycleType.REPEATED_REPAIR_CYCLE


# 7. Risk Increase Trigger
def test_risk_increase_trigger():
    detector = DivergenceDetector()
    history = [
        RepairStepSnapshot(0, time.time(), active_failures=["err1"], risk_score=0.10),
        RepairStepSnapshot(1, time.time(), active_failures=["err1"], risk_score=0.65),
    ]
    score = detector.calculate_divergence_score(history)
    assert score.risk_growth > 0.50
    assert score.is_diverging is True


# 8. Coverage Stagnation
def test_coverage_stagnation():
    detector = StallDetector(min_stagnant_iterations=3, epsilon_progress=0.01)
    history = [
        RepairStepSnapshot(1, time.time(), active_failures=["e1"], patches_applied=["p1"], behavioral_proof_coverage=0.60),
        RepairStepSnapshot(2, time.time(), active_failures=["e2"], patches_applied=["p2"], behavioral_proof_coverage=0.602),
        RepairStepSnapshot(3, time.time(), active_failures=["e3"], patches_applied=["p3"], behavioral_proof_coverage=0.604),
    ]
    report = detector.evaluate_stall(history)
    assert report.stalled is True
    assert report.stall_type == StallType.COVERAGE_STAGNATION


# 9. Budget Exhaustion
def test_budget_exhaustion():
    budget = TerminationBudget(max_repairs=3)
    mgr = TerminationBudgetManager(budget)
    is_exhausted, _ = mgr.consume_step(repairs=1)
    assert is_exhausted is False
    is_exhausted, _ = mgr.consume_step(repairs=1)
    assert is_exhausted is False
    is_exhausted, reasons = mgr.consume_step(repairs=1)
    assert is_exhausted is True
    assert "max_repairs" in reasons


# 10. Human Escalation Triggers
def test_human_escalation_triggers():
    escalation = HumanEscalationManager()
    for reason in TerminationEscalationReason:
        ticket = escalation.create_escalation_ticket("msn_1", "plan_1", reason, {"reason": reason.value})
        assert ticket.ticket_id.startswith("tkt_")
        assert ticket.status == EscalationStatus.PENDING
    assert len(escalation.tickets) == len(TerminationEscalationReason)


# 11. Economic Escalation Block
def test_economic_escalation_block():
    escalation = HumanEscalationManager()
    # If not economic, allowed even if troubled
    allowed, _ = escalation.evaluate_economic_safety(is_economic_operation=False, is_diverging_or_stalled_or_cycling=True)
    assert allowed is True

    # If economic and troubled, strictly blocked
    allowed, reason = escalation.evaluate_economic_safety(is_economic_operation=True, is_diverging_or_stalled_or_cycling=True)
    assert allowed is False
    assert reason == TerminationEscalationReason.ECONOMIC_RISK


# 12. Security Escalation Sentinel
def test_security_escalation_sentinel():
    sentinel = ConvergenceSecuritySentinel()
    budget = TerminationBudget(max_repairs=10)
    budget.consume(repairs=5)

    # Budget spoofing check: claiming consumption 2 < verified 5
    valid, err = sentinel.validate_budget_integrity(budget, claimed_consumption=2)
    assert valid is False
    assert "Budget spoofing" in err


# 13. Progress Spoofing Prevention
def test_progress_spoofing_prevention():
    sentinel = ConvergenceSecuritySentinel()
    p_before = ProgressVector(resolved_failures=0)
    # Claiming 100 resolved failures when actual active domain is only 2
    p_after = ProgressVector(resolved_failures=100)
    delta = ProgressDelta(score=300.0, resolved_delta=100)

    valid, err = sentinel.validate_progress_vector(p_before, p_after, delta, actual_active_failures=["err1", "err2"])
    assert valid is False
    assert "Progress spoofing" in err


# 14. Cycle Spoofing Prevention
def test_cycle_spoofing_prevention():
    sentinel = ConvergenceSecuritySentinel()
    h1 = RepairStepSnapshot(1, time.time(), state_hash="hash_alpha")
    h2 = RepairStepSnapshot(2, time.time(), state_hash="hash_beta")
    history = [h1, h2]

    # Manipulating recorded hash
    forged_hashes = ["hash_alpha", "hash_gamma"]
    valid, err = sentinel.validate_cycle_integrity(forged_hashes, history)
    assert valid is False
    assert "Cycle spoofing" in err


# 15. Risk Spoofing Prevention
def test_risk_spoofing_prevention():
    sentinel = ConvergenceSecuritySentinel()
    # Claiming risk 0.01 with critical failures active
    valid, err = sentinel.validate_risk_assessment(claimed_risk=0.01, empirical_failure_count=5, has_critical_failures=True)
    assert valid is False
    assert "Risk spoofing" in err


# 16. Deterministic Replay
def test_deterministic_replay():
    engine = DeterministicReplayEngine(seed=123)
    init_snap = RepairStepSnapshot(0, 1000.0, active_failures=["err1", "err2"], behavioral_proof_coverage=0.50, risk_score=0.40)
    patches = [
        {"patch_id": "p1", "resolves": ["err1"], "files": ["src/a.py"]},
        {"patch_id": "p2", "resolves": ["err2"], "files": ["src/b.py"]},
    ]

    run1 = engine.replay_sequence(init_snap, patches, environment_seed=999)
    run2 = engine.replay_sequence(init_snap, patches, environment_seed=999)

    hashes1 = [s.state_hash for s in run1]
    hashes2 = [s.state_hash for s in run2]

    identical, discrepancies = engine.verify_replay_identity(hashes1, hashes2)
    assert identical is True
    assert len(discrepancies) == 0


# 17. Crash Recovery
def test_crash_recovery():
    recovery = CrashRecoveryEngine()
    persisted_entries = [
        {"event_type": "step_1", "payload": {"iteration": 1, "failure_count": 3, "state": "CONVERGING", "risk": 0.35}},
        {"event_type": "step_2", "payload": {"iteration": 2, "failure_count": 2, "state": "CONVERGING", "risk": 0.22}},
    ]
    state, ledger, budget = recovery.recover_from_persistence(persisted_entries, "chk_state_hash_recovered")
    assert state.iteration == 2
    assert state.failure_count == 2
    assert state.state == TerminationState.CONVERGING
    assert len(ledger.entries) == 2


# 18. Convergence Certificate
def test_convergence_certificate():
    cert_engine = ConvergenceCertificateEngine()
    cert = cert_engine.issue_certificate(
        mission_id="msn_cert_test",
        transaction_id="tx_cert_test",
        termination_reason=TerminationReason.CONVERGED_VERIFIED,
        convergence_verdict=ConvergenceVerdict.CONVERGED,
        initial_state_hash="init_hash_1",
        final_state_hash="final_hash_2",
        repair_sequence=["p1", "p2"],
        progress_history=[],
        risk_history=[0.4, 0.1],
        coverage_history=[0.6, 0.95],
        proof_history=["p1", "p2"],
        cycles_detected=0,
        rollbacks_count=0,
        human_review_required=False,
        budget_summary={},
        total_iterations=2,
        total_duration_seconds=5.2,
        security_sentinel_approved=True,
    )
    assert cert.signature.startswith("CERT_SIG_")
    assert cert_engine.verify_certificate(cert) is True


# 19. Composite Transaction Proof
def test_composite_transaction_proof():
    engine = CompositeConvergenceProofEngine(min_composite_coverage=0.85)
    individual_proofs = [
        {"patch_id": "p1", "verified": True},
        {"patch_id": "p2", "verified": True},
    ]
    # Pass scenario
    ok, msg, data = engine.verify_composite_proof(
        "tx_1", individual_proofs, ["INV_A", "INV_B"], [], 1.0, 0.90
    )
    assert ok is True
    assert "COMPOSITE_PROOF_" in data["composite_proof_hash"]

    # Fail scenario: pass rate < 100%
    ok, msg, _ = engine.verify_composite_proof(
        "tx_1", individual_proofs, ["INV_A", "INV_B"], [], 0.98, 0.90
    )
    assert ok is False
    assert "100.0%" in msg


# 20. Rollback on Oscillation
def test_rollback_on_oscillation():
    bridge = AutonomousRepairConvergenceBridge()
    init_snap = RepairStepSnapshot(0, time.time(), active_failures=["errA"])
    bridge.initialize_governance("m1", "tx_osc", init_snap)

    s1 = RepairStepSnapshot(1, time.time(), active_failures=["errB"], patches_applied=["p1"])
    bridge.evaluate_step(s1, ProgressVector(resolved_failures=1, new_failures=1))

    s2 = RepairStepSnapshot(2, time.time(), active_failures=["errA"], patches_applied=["p2"])
    state, decision = bridge.evaluate_step(s2, ProgressVector(resolved_failures=1, new_failures=1))

    assert state.state == TerminationState.OSCILLATING
    assert decision["action"] == "TRIGGER_ROLLBACK"
    assert bridge.budget_manager.budget.consumed_rollbacks == 1


# 21. Experience Memory Influence
def test_experience_memory_influence():
    store = ConvergenceExperienceStore()
    store.record_mission_outcome("m0", "ReferenceError: express", ["p_pkg", "p_app"], converged=True)
    guidance = store.get_advisory_heuristic("ReferenceError: express")
    assert guidance["has_guidance"] is True
    assert guidance["historical_success_rate"] == 1.0
    assert guidance["authority"] == "ADVISORY_ONLY_NOT_FORMAL_PROOF"


# 22. Predictive Calibration
def test_predictive_calibration():
    engine = PredictiveConvergenceEngine()
    pred = engine.predict_patch_impact("patch_1", "TypeError: auth", ["app.py"], 2, 0.3)
    actual_delta = ProgressDelta(score=pred["predicted_score"] + 0.5)
    engine.record_actual_outcome(pred, actual_delta)

    report = engine.compute_calibration_report()
    assert "directional_accuracy" in report
    assert "mean_absolute_error" in report
    assert "brier_score" in report
    assert report["directional_accuracy"] == 1.0


# 23. Oscillation State Classification
def test_oscillation_state_classification():
    detector = OscillationDetector()
    history = [
        RepairStepSnapshot(1, time.time(), active_failures=["err1"]),
        RepairStepSnapshot(2, time.time(), active_failures=["err2"]),
        RepairStepSnapshot(3, time.time(), active_failures=["err1"]),
    ]
    report = detector.detect_oscillation(history)
    assert report.oscillating is True
    assert report.cycle_length == 2


# 24. Unknown State Recovery
def test_unknown_state_recovery():
    recovery = CrashRecoveryEngine()
    unknown_state = ConvergenceState(
        state=TerminationState.UNKNOWN,
        iteration=5,
        failure_count=3,
        blocking_failure_count=3,
        risk_score=0.4,
        coverage=0.6,
        uncertainty=0.5,
        proof_status="UNKNOWN",
        repair_count=5,
    )
    # Revalidating with zero active failures and verified invariants transitions to STABLE
    revalidated = recovery.revalidate_unknown_state(unknown_state, active_failures_probe=[], invariants_verified=True)
    assert revalidated.state == TerminationState.STABLE
    assert revalidated.failure_count == 0
