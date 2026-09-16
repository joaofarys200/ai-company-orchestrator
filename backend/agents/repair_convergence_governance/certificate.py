"""
JARVIS OS — Phase 56: Convergence Certificate Engine
Issues and cryptographically validates formal, tamper-evident ConvergenceCertificates.
"""

from __future__ import annotations

import time
import hashlib
from typing import Dict, Any, List, Optional
from agents.repair_convergence_governance.models import (
    ConvergenceCertificate,
    ConvergenceVerdict,
    TerminationReason,
    compute_deterministic_hash,
)


class ConvergenceCertificateEngine:
    """Issues and cryptographically validates convergence certificates."""

    def issue_certificate(
        self,
        mission_id: str,
        transaction_id: str,
        termination_reason: TerminationReason,
        convergence_verdict: ConvergenceVerdict,
        initial_state_hash: str,
        final_state_hash: str,
        repair_sequence: List[str],
        progress_history: List[Dict[str, Any]],
        risk_history: List[float],
        coverage_history: List[float],
        proof_history: List[str],
        cycles_detected: int,
        rollbacks_count: int,
        human_review_required: bool,
        budget_summary: Dict[str, Any],
        total_iterations: int,
        total_duration_seconds: float,
        security_sentinel_approved: bool,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConvergenceCertificate:
        """Issues a new signed ConvergenceCertificate."""
        reason_val = termination_reason.value if hasattr(termination_reason, "value") else str(termination_reason)
        verdict_val = convergence_verdict.value if hasattr(convergence_verdict, "value") else str(convergence_verdict)
        cert_raw = f"{mission_id}:{transaction_id}:{reason_val}:{time.time()}"
        cert_id = "cert_" + hashlib.sha256(cert_raw.encode("utf-8")).hexdigest()[:12]

        cert = ConvergenceCertificate(
            certificate_id=cert_id,
            mission_id=mission_id,
            transaction_id=transaction_id,
            termination_reason=termination_reason,
            convergence_verdict=convergence_verdict,
            initial_state_hash=initial_state_hash,
            final_state_hash=final_state_hash,
            repair_sequence=repair_sequence,
            progress_history=progress_history,
            risk_history=risk_history,
            coverage_history=coverage_history,
            proof_history=proof_history,
            cycles_detected=cycles_detected,
            rollbacks_count=rollbacks_count,
            human_review_required=human_review_required,
            budget_summary=budget_summary,
            total_iterations=total_iterations,
            total_duration_seconds=total_duration_seconds,
            security_sentinel_approved=security_sentinel_approved,
            metadata=metadata or {},
        )
        return cert

    def verify_certificate(self, cert: ConvergenceCertificate) -> bool:
        """Verifies cryptographic signature integrity and state consistency of certificate."""
        payload = {
            "id": cert.certificate_id,
            "mission_id": cert.mission_id,
            "transaction_id": cert.transaction_id,
            "reason": cert.termination_reason.value,
            "verdict": cert.convergence_verdict.value,
            "initial_hash": cert.initial_state_hash,
            "final_hash": cert.final_state_hash,
            "repairs": sorted(cert.repair_sequence),
            "iterations": cert.total_iterations,
            "sentinel": cert.security_sentinel_approved,
        }
        expected_sig = "CERT_SIG_" + compute_deterministic_hash(payload)
        return cert.signature == expected_sig
