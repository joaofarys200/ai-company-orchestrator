"""
Phase 72 — Preventive Action Verification
Verifies post-remediation metric trajectories against pre-action baselines.
Never promotes INSUFFICIENT_EVIDENCE to PREVENTION_EFFECTIVE.
"""

from __future__ import annotations

import statistics
import time
import uuid
from typing import Any, Dict, List, Optional

from .models import (
    Baseline,
    PreventionVerificationStatus,
    PreventiveAction,
    PreventiveVerification,
    ReliabilityObservation,
)


class PreventiveVerifier:
    """Verifies that an executed preventive action restored stability."""

    def __init__(self, min_verification_samples: int = 3):
        self.min_samples = min_verification_samples

    def verify(
        self,
        plan_id: str,
        action: PreventiveAction,
        pre_baseline: Optional[Baseline],
        post_observations: List[ReliabilityObservation],
        stability_window_seconds: float = 60.0,
    ) -> PreventiveVerification:
        verification_id = f"ver_{uuid.uuid4().hex[:8]}"
        now = time.time()

        pre_dict = pre_baseline.to_dict() if pre_baseline else {}
        pre_mean = pre_baseline.rolling_mean if pre_baseline else 0.0

        if not post_observations or len(post_observations) < self.min_samples:
            return PreventiveVerification(
                verification_id=verification_id,
                plan_id=plan_id,
                action_id=action.action_id,
                pre_action_baseline={"mean": pre_mean},
                post_action_baseline={},
                status=PreventionVerificationStatus.INSUFFICIENT_EVIDENCE,
                observed_metrics={},
                verified_at=now,
                stability_window_seconds=stability_window_seconds,
            )

        post_vals = [o.value for o in post_observations]
        post_mean = statistics.mean(post_vals)
        metric = post_observations[0].metric.lower()

        is_higher_better = metric in ("availability", "uptime", "throughput")

        # Check effectiveness: metric must improve or remain stable within normal bounds
        if is_higher_better:
            effective = post_mean >= pre_mean or post_mean >= 0.99
        else:
            effective = post_mean <= pre_mean or post_mean <= 0.05

        status = (
            PreventionVerificationStatus.PREVENTION_EFFECTIVE
            if effective
            else PreventionVerificationStatus.PREVENTION_INEFFECTIVE
        )

        return PreventiveVerification(
            verification_id=verification_id,
            plan_id=plan_id,
            action_id=action.action_id,
            pre_action_baseline={"mean": pre_mean},
            post_action_baseline={"mean": post_mean, "min": min(post_vals), "max": max(post_vals)},
            status=status,
            observed_metrics={"sample_count": len(post_vals), "latest": post_vals[-1]},
            verified_at=now,
            stability_window_seconds=stability_window_seconds,
        )
