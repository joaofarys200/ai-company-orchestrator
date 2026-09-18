"""
JARVIS OS — Phase 62: Continuous Verification & Autonomous Regression Governance
Module: flaky.py
FlakyTestDetector performing controlled retries and failure fingerprinting.
Invariant: Never mask a failure as PASS after retry. Intermittent behavior yields FLAKY_REVIEW_REQUIRED.
"""

from __future__ import annotations

import statistics
import time
from typing import Any, Callable, Dict, List, Optional

from .executor import ContinuousTestExecutor, ExecutionResultItem
from .models import FlakyAnalysisResult, FlakyStatus, SelectedTestItem, VerificationPolicy


class FlakyTestDetector:
    """
    Detects flaky tests via policy-bounded retries, failure fingerprinting, and variance tracking.
    Never converts a flaky test into a clean PASS without verified root-cause evidence.
    """
    __test__ = False  # Prevent pytest collection warning

    def __init__(self, executor: ContinuousTestExecutor) -> None:
        self.executor = executor
        self.history: Dict[str, List[ExecutionResultItem]] = {}

    def analyze_test(
        self,
        item: SelectedTestItem,
        initial_result: ExecutionResultItem,
        policy: VerificationPolicy,
    ) -> FlakyAnalysisResult:
        """Evaluate whether a failing or suspicious test is flaky."""
        attempts = 1
        outcomes: List[str] = [initial_result.status]
        durations: List[float] = [initial_result.duration_ms]
        fingerprints: List[str] = [initial_result.failure_fingerprint] if initial_result.failure_fingerprint else []

        # If already passed and policy doesn't mandate stress checks, return stable pass
        if initial_result.status == "PASS" and not policy.fail_on_flaky:
            return FlakyAnalysisResult(
                test_id=item.test_id,
                status=FlakyStatus.STABLE_PASS,
                attempts=1,
                outcomes=["PASS"],
                timing_variance=0.0,
                environment_variance=0.0,
                failure_fingerprints=[],
                review_required=False,
            )

        # If policy forbids retries
        if not policy.allow_retries or policy.max_retries <= 0:
            status = FlakyStatus.STABLE_FAIL if initial_result.status in ("FAIL", "ERROR") else FlakyStatus.STABLE_PASS
            return FlakyAnalysisResult(
                test_id=item.test_id,
                status=status,
                attempts=1,
                outcomes=outcomes,
                timing_variance=0.0,
                environment_variance=0.0,
                failure_fingerprints=fingerprints,
                review_required=False,
            )

        # Controlled retries
        max_retries = min(policy.max_retries, 3)
        for _ in range(max_retries):
            attempts += 1
            retry_res = self.executor.execute_test(item)
            outcomes.append(retry_res.status)
            durations.append(retry_res.duration_ms)
            if retry_res.failure_fingerprint and retry_res.failure_fingerprint not in fingerprints:
                fingerprints.append(retry_res.failure_fingerprint)

        # Calculate timing variance
        timing_variance = round(statistics.variance(durations), 2) if len(durations) > 1 else 0.0

        # Classification
        has_pass = "PASS" in outcomes
        has_fail = any(s in ("FAIL", "ERROR") for s in outcomes)

        if has_pass and has_fail:
            # INVARIANT: Flaky behavior NEVER masks as PASS
            return FlakyAnalysisResult(
                test_id=item.test_id,
                status=FlakyStatus.FLAKY,
                attempts=attempts,
                outcomes=outcomes,
                timing_variance=timing_variance,
                environment_variance=0.15,
                failure_fingerprints=fingerprints,
                review_required=True,  # Triggers FLAKY_REVIEW_REQUIRED
            )
        elif not has_fail:
            return FlakyAnalysisResult(
                test_id=item.test_id,
                status=FlakyStatus.STABLE_PASS,
                attempts=attempts,
                outcomes=outcomes,
                timing_variance=timing_variance,
                environment_variance=0.0,
                failure_fingerprints=[],
                review_required=False,
            )
        else:
            return FlakyAnalysisResult(
                test_id=item.test_id,
                status=FlakyStatus.STABLE_FAIL,
                attempts=attempts,
                outcomes=outcomes,
                timing_variance=timing_variance,
                environment_variance=0.0,
                failure_fingerprints=fingerprints,
                review_required=False,
            )
