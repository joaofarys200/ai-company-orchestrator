"""
JARVIS OS — Phase 56: Autonomous Repair Convergence Bridge
Orchestrates convergence governance, detector evaluation, budget enforcement, and certificate issuance.
"""

from __future__ import annotations

import time
from typing import Dict, Any, List, Optional, Tuple

from agents.repair_convergence_governance.models import (
    ConvergenceCertificate,
    ConvergenceState,
    ConvergenceVerdict,
    ProgressDelta,
    ProgressVector,
    RepairStepSnapshot,
    TerminationBudget,
    TerminationEscalationReason,
    TerminationReason,
    TerminationState,
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
from agents.repair_convergence_governance.security import ConvergenceSecuritySentinel
from agents.repair_convergence_governance.proof import CompositeConvergenceProofEngine
from agents.repair_convergence_governance.telemetry import ConvergenceTelemetry
from agents.repair_convergence_governance.reversion_manager import ReversionManager


class AutonomousRepairConvergenceBridge:
    """Central coordinator enforcing convergence governance over transactional repair sequences."""

    def __init__(
        self,
        base_budget: Optional[TerminationBudget] = None,
        min_composite_coverage: float = 0.80,
    ):
        self.cycle_detector = CycleDetector()
        self.oscillation_detector = OscillationDetector()
        self.stall_detector = StallDetector()
        self.divergence_detector = DivergenceDetector()
        self.progress_tracker = ProgressVectorTracker()
        self.budget_manager = TerminationBudgetManager(base_budget)
        self.escalation_manager = HumanEscalationManager()
        self.certificate_engine = ConvergenceCertificateEngine()
        self.ledger = ProgressLedger()
        self.security_sentinel = ConvergenceSecuritySentinel()
        self.proof_engine = CompositeConvergenceProofEngine(min_composite_coverage)
        self.telemetry = ConvergenceTelemetry()
        self.reversion_manager = ReversionManager()

        self.snapshots: List[RepairStepSnapshot] = []
        self.individual_proofs: List[Dict[str, Any]] = []
        self.active_state: Optional[ConvergenceState] = None
        self.mission_id: str = ""
        self.transaction_id: str = ""
        self.start_time: float = 0.0

    def initialize_governance(
        self,
        mission_id: str,
        transaction_id: str,
        initial_snapshot: RepairStepSnapshot,
        initial_vector: Optional[ProgressVector] = None,
    ) -> ConvergenceState:
        """Initializes a new governed repair run."""
        self.mission_id = mission_id
        self.transaction_id = transaction_id
        self.start_time = time.time()
        self.snapshots = [initial_snapshot]
        self.individual_proofs = []

        self.progress_tracker.record_initial_state(initial_vector)

        self.active_state = ConvergenceState(
            state=TerminationState.INITIAL,
            iteration=0,
            failure_count=len(initial_snapshot.active_failures),
            blocking_failure_count=len(initial_snapshot.active_failures),
            risk_score=initial_snapshot.risk_score,
            coverage=initial_snapshot.behavioral_proof_coverage,
            uncertainty=0.20,
            proof_status="PENDING",
            repair_count=0,
            state_hash=initial_snapshot.state_hash,
            previous_state_hash="",
        )

        self.ledger.append_entry(
            event_type="convergence_started",
            payload={
                "mission_id": mission_id,
                "transaction_id": transaction_id,
                "state": self.active_state.state.value,
                "failure_count": self.active_state.failure_count,
                "state_hash": self.active_state.state_hash,
            }
        )

        self.telemetry.emit_event(
            event_name="convergence_started",
            mission_id=mission_id,
            transaction_id=transaction_id,
            state=self.active_state.state.value,
            risk=self.active_state.risk_score,
            coverage=self.active_state.coverage,
            proof=self.active_state.proof_status,
            budget=self.budget_manager.get_budget_summary(),
            reason="INITIALIZED",
        )

        return self.active_state

    def evaluate_step(
        self,
        step_snapshot: RepairStepSnapshot,
        p_after: ProgressVector,
        patch_proof: Optional[Dict[str, Any]] = None,
        invariants_verified: bool = True,
        is_economic_op: bool = False,
    ) -> Tuple[ConvergenceState, Dict[str, Any]]:
        """Processes a single repair step through all detectors, updating the governance state."""
        self.snapshots.append(step_snapshot)
        if patch_proof:
            self.individual_proofs.append(patch_proof)

        # 1. Budget consumption
        exhausted, exhaust_reasons = self.budget_manager.consume_step(
            repairs=1,
            runtime_sec=time.time() - self.start_time,
            risk=step_snapshot.risk_score,
            depth=len(self.snapshots),
        )

        # 2. Progress update
        p_before = self.progress_tracker.get_latest_vector()
        delta, is_monotonic = self.progress_tracker.record_step_progress(p_after)

        # 3. Security Sentinel validation (anti-spoofing)
        valid_prog, prog_err = self.security_sentinel.validate_progress_vector(
            p_before, p_after, delta, step_snapshot.active_failures
        )
        if not valid_prog:
            self.active_state.state = TerminationState.BLOCKED
            self.telemetry.emit_event(
                "termination_triggered", self.mission_id, self.transaction_id,
                self.active_state.state.value, step_snapshot.risk_score,
                step_snapshot.behavioral_proof_coverage, "SPOOFING_BLOCKED",
                self.budget_manager.get_budget_summary(), prog_err or "Security violation"
            )
            return self.active_state, {"action": "HALT_SECURITY", "error": prog_err}

        # 4. Detector evaluations
        cycle_rep = self.cycle_detector.detect_cycles(self.snapshots)
        osc_rep = self.oscillation_detector.detect_oscillation(self.snapshots)
        stall_rep = self.stall_detector.evaluate_stall(self.snapshots, self.progress_tracker.vector_history)
        div_rep = self.divergence_detector.evaluate_divergence(
            self.snapshots, self.budget_manager.budget.consumed_rollbacks
        )

        # 5. Economic Safety Check
        is_troubled = cycle_rep.cycle_detected or osc_rep.oscillating or stall_rep.stalled or div_rep.diverging
        econ_safe, econ_reason = self.escalation_manager.evaluate_economic_safety(is_economic_op, is_troubled)

        decision: Dict[str, Any] = {
            "cycle": cycle_rep.to_dict(),
            "oscillation": osc_rep.to_dict(),
            "stall": stall_rep.to_dict(),
            "divergence": div_rep.to_dict(),
            "delta_score": delta.score,
            "is_monotonic": is_monotonic,
        }

        # 6. State arbitration
        prev_hash = self.active_state.state_hash if self.active_state else ""
        next_state = TerminationState.CONVERGING
        term_reason = TerminationReason.MANUAL_TERMINATION

        if not econ_safe:
            next_state = TerminationState.HUMAN_REVIEW_REQUIRED
            term_reason = TerminationReason.SECURITY_SENTINEL_HALT
            decision["action"] = "BLOCK_ECONOMIC_COMMIT"
            self.escalation_manager.create_escalation_ticket(
                self.mission_id, self.transaction_id, TerminationEscalationReason.ECONOMIC_RISK,
                {"detail": "Economic mutation stalled/cycled/diverged; auto-commit blocked."}
            )

        elif osc_rep.oscillating:
            next_state = TerminationState.OSCILLATING
            term_reason = TerminationReason.OSCILLATION_DETECTED
            decision["action"] = "TRIGGER_ROLLBACK"
            self.budget_manager.budget.consume(rollbacks=1)
            self.reversion_manager.execute_reversion(
                self.transaction_id, TerminationReason.OSCILLATION_DETECTED,
                "ckpt_stable", step_snapshot.iteration_id
            )

        elif cycle_rep.cycle_detected:
            next_state = TerminationState.OSCILLATING if cycle_rep.cycle_period == 2 else TerminationState.DIVERGING
            term_reason = TerminationReason.CYCLE_DETECTED
            decision["action"] = "TRIGGER_ROLLBACK"
            self.budget_manager.budget.consume(rollbacks=1)
            self.reversion_manager.execute_reversion(
                self.transaction_id, TerminationReason.CYCLE_DETECTED,
                "ckpt_stable", step_snapshot.iteration_id
            )

        elif div_rep.diverging:
            next_state = TerminationState.DIVERGING
            term_reason = TerminationReason.DIVERGENCE_DETECTED
            decision["action"] = "TRIGGER_ROLLBACK"

        elif stall_rep.stalled:
            next_state = TerminationState.STALLED
            term_reason = TerminationReason.STALL_DETECTED
            decision["action"] = "HUMAN_REVIEW"
            self.escalation_manager.create_escalation_ticket(
                self.mission_id, self.transaction_id, TerminationEscalationReason.INSUFFICIENT_PROGRESS,
                {"stall_type": str(stall_rep.stall_type), "detail": stall_rep.explanation}
            )

        elif exhausted:
            next_state = TerminationState.HUMAN_REVIEW_REQUIRED
            term_reason = TerminationReason.BUDGET_EXHAUSTED
            decision["action"] = "HUMAN_REVIEW"
            self.escalation_manager.create_escalation_ticket(
                self.mission_id, self.transaction_id, TerminationEscalationReason.BUDGET_EXHAUSTED,
                {"exhausted_reasons": exhaust_reasons}
            )

        elif len(step_snapshot.active_failures) == 0 and invariants_verified:
            # Check composite proof
            proof_ok, proof_msg, proof_data = self.proof_engine.verify_composite_proof(
                self.transaction_id,
                self.individual_proofs,
                ["INV_NO_REGRESSION", "INV_TYPE_SOUNDNESS", "INV_CONTRACT_COMPAT"],
                [],
                step_snapshot.test_pass_rate,
                step_snapshot.behavioral_proof_coverage,
            )
            if proof_ok:
                next_state = TerminationState.COMMITTED
                term_reason = TerminationReason.CONVERGED_VERIFIED
                decision["action"] = "COMMIT_TRANSACTION"
                decision["composite_proof"] = proof_data
            else:
                next_state = TerminationState.CONVERGING
                decision["action"] = "CONTINUE_PROOF_INSUFFICIENT"
                decision["proof_error"] = proof_msg
        else:
            next_state = TerminationState.CONVERGING
            decision["action"] = "CONTINUE_REPAIR"

        # Update active state
        self.active_state = ConvergenceState(
            state=next_state,
            iteration=step_snapshot.iteration_id,
            failure_count=len(step_snapshot.active_failures),
            blocking_failure_count=len(step_snapshot.active_failures),
            risk_score=step_snapshot.risk_score,
            coverage=step_snapshot.behavioral_proof_coverage,
            uncertainty=max(0.0, 0.20 - (step_snapshot.iteration_id * 0.03)),
            proof_status="PROVEN" if next_state == TerminationState.COMMITTED else "IN_PROGRESS",
            repair_count=step_snapshot.iteration_id,
            rollback_count=self.budget_manager.budget.consumed_rollbacks,
            cycle_count=1 if cycle_rep.cycle_detected else 0,
            state_hash=step_snapshot.state_hash,
            previous_state_hash=prev_hash,
        )

        # Append to ledger
        self.ledger.append_entry(
            event_type="progress_recorded",
            payload={
                "step": step_snapshot.iteration_id,
                "state": next_state.value,
                "delta_score": delta.score,
                "failures": len(step_snapshot.active_failures),
                "decision": decision["action"],
            }
        )

        # Telemetry
        self.telemetry.emit_event(
            "progress_recorded", self.mission_id, self.transaction_id,
            next_state.value, step_snapshot.risk_score,
            step_snapshot.behavioral_proof_coverage, self.active_state.proof_status,
            self.budget_manager.get_budget_summary(), decision["action"]
        )

        return self.active_state, decision

    def finalize_governance(self) -> ConvergenceCertificate:
        """Issues the cryptographic ConvergenceCertificate at termination."""
        final_snap = self.snapshots[-1] if self.snapshots else RepairStepSnapshot(0, time.time())
        initial_snap = self.snapshots[0] if self.snapshots else final_snap

        state = self.active_state.state if self.active_state else TerminationState.UNKNOWN

        if state == TerminationState.COMMITTED:
            verdict = ConvergenceVerdict.CONVERGED
            reason = TerminationReason.CONVERGED_VERIFIED
        elif state == TerminationState.OSCILLATING:
            verdict = ConvergenceVerdict.OSCILLATING
            reason = TerminationReason.OSCILLATION_DETECTED
        elif state == TerminationState.STALLED:
            verdict = ConvergenceVerdict.STALLED
            reason = TerminationReason.STALL_DETECTED
        elif state == TerminationState.DIVERGING:
            verdict = ConvergenceVerdict.DIVERGED
            reason = TerminationReason.DIVERGENCE_DETECTED
        elif state == TerminationState.HUMAN_REVIEW_REQUIRED:
            verdict = ConvergenceVerdict.ESCALATED
            reason = TerminationReason.HUMAN_INTERVENTION_REQUIRED
        else:
            verdict = ConvergenceVerdict.IN_PROGRESS
            reason = TerminationReason.MANUAL_TERMINATION

        cert = self.certificate_engine.issue_certificate(
            mission_id=self.mission_id,
            transaction_id=self.transaction_id,
            termination_reason=reason,
            convergence_verdict=verdict,
            initial_state_hash=initial_snap.state_hash,
            final_state_hash=final_snap.state_hash,
            repair_sequence=[p for s in self.snapshots for p in s.patches_applied],
            progress_history=[d.to_dict() for d in self.progress_tracker.delta_history],
            risk_history=[s.risk_score for s in self.snapshots],
            coverage_history=[s.behavioral_proof_coverage for s in self.snapshots],
            proof_history=[p.get("patch_id", "p") for p in self.individual_proofs],
            cycles_detected=1 if verdict == ConvergenceVerdict.OSCILLATING else 0,
            rollbacks_count=self.budget_manager.budget.consumed_rollbacks,
            human_review_required=(verdict == ConvergenceVerdict.ESCALATED),
            budget_summary=self.budget_manager.get_budget_summary(),
            total_iterations=len(self.snapshots),
            total_duration_seconds=time.time() - self.start_time,
            security_sentinel_approved=True,
        )

        self.telemetry.emit_event(
            "convergence_certificate_created", self.mission_id, self.transaction_id,
            state.value, final_snap.risk_score, final_snap.behavioral_proof_coverage,
            "CERT_ISSUED", self.budget_manager.get_budget_summary(), cert.signature
        )

        return cert
