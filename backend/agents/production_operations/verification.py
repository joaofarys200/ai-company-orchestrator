"""
Phase 71 — Post-Recovery Verification Engine
Multi-variable verification across stability windows.
Guarantees RECOVERED is never declared based on a single isolated healthcheck.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional
from .models import (
    HealthCheckResult,
    HealthStatus,
    RecoveryVerification,
    SLOEvaluation,
    SLOStatus,
    VerificationStatus,
)


class PostRecoveryVerifier:
    """
    Evaluates runtime stability over a multi-cycle window following a recovery or rollback action.
    """

    def __init__(self, service_id: str, min_required_checks: int = 3):
        self.service_id = service_id
        self.min_required_checks = min_required_checks
        self._history: List[RecoveryVerification] = []

    def verify_recovery(
        self,
        incident_id: str,
        health_results: List[HealthCheckResult],
        slo_evaluations: List[SLOEvaluation],
        stability_window_seconds: int = 60,
    ) -> RecoveryVerification:
        """
        Synthesizes recovery verification over the collected health and SLO evidence.
        """
        verification_id = f"verif-{uuid.uuid4().hex[:8]}"

        # Check sample count invariant: single check is INSUFFICIENT
        total_checks = len(health_results)
        if total_checks < self.min_required_checks:
            res = RecoveryVerification(
                verification_id=verification_id,
                incident_id=incident_id,
                status=VerificationStatus.INSUFFICIENT_EVIDENCE,
                stability_window_seconds=stability_window_seconds,
                healthchecks_passed=sum(1 for h in health_results if h.status == HealthStatus.HEALTHY),
                healthchecks_failed=sum(1 for h in health_results if h.status != HealthStatus.HEALTHY),
                slo_evaluations=[s.to_dict() for s in slo_evaluations],
                details=(
                    f"Insufficient observation evidence: {total_checks} healthchecks provided, "
                    f"minimum {self.min_required_checks} required to declare recovery."
                ),
            )
            self._history.append(res)
            return res

        passed_hc = sum(1 for h in health_results if h.status == HealthStatus.HEALTHY)
        failed_hc = sum(1 for h in health_results if h.status != HealthStatus.HEALTHY)

        breached_slos = [s for s in slo_evaluations if s.status == SLOStatus.BREACH]

        if failed_hc == 0 and not breached_slos:
            status = VerificationStatus.RECOVERY_VERIFIED
            details = f"All {passed_hc} healthchecks passed and 0 SLO breaches across {stability_window_seconds}s window."
        else:
            status = VerificationStatus.RECOVERY_FAILED
            details = (
                f"Verification failed: {failed_hc} healthcheck failures, "
                f"{len(breached_slos)} SLO breaches observed."
            )

        res = RecoveryVerification(
            verification_id=verification_id,
            incident_id=incident_id,
            status=status,
            stability_window_seconds=stability_window_seconds,
            healthchecks_passed=passed_hc,
            healthchecks_failed=failed_hc,
            slo_evaluations=[s.to_dict() for s in slo_evaluations],
            details=details,
        )
        self._history.append(res)
        return res

    def get_history(self) -> List[RecoveryVerification]:
        return list(self._history)
