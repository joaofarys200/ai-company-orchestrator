"""
JARVIS OS — Phase 62: Continuous Verification & Autonomous Regression Governance
Module: metrics.py
Metrics tracker for Continuous Verification.
Explicitly separates synthetic microbenchmarks, real repository, unseen tasks, and browser QA.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class MetricBucket:
    changes_verified: int = 0
    changes_blocked: int = 0
    regressions_detected: int = 0
    false_regression_observed: int = 0
    insufficient_evidence: int = 0
    flaky_tests: int = 0
    tests_selected: int = 0
    tests_synthesized: int = 0
    tests_reused: int = 0
    tests_skipped: int = 0
    verification_time_ms: float = 0.0
    synthesis_time_ms: float = 0.0
    execution_time_ms: float = 0.0
    coverage_delta: float = 0.0
    mutation_delta: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    human_review_count: int = 0

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return round(self.cache_hits / total, 4) if total > 0 else 0.0

    @property
    def human_review_rate(self) -> float:
        total = self.changes_verified + self.changes_blocked + self.insufficient_evidence
        return round(self.human_review_count / total, 4) if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "changes_verified": self.changes_verified,
            "changes_blocked": self.changes_blocked,
            "regressions_detected": self.regressions_detected,
            "false_regression_observed": self.false_regression_observed,
            "insufficient_evidence": self.insufficient_evidence,
            "flaky_tests": self.flaky_tests,
            "tests_selected": self.tests_selected,
            "tests_synthesized": self.tests_synthesized,
            "tests_reused": self.tests_reused,
            "tests_skipped": self.tests_skipped,
            "verification_time_ms": round(self.verification_time_ms, 2),
            "synthesis_time_ms": round(self.synthesis_time_ms, 2),
            "execution_time_ms": round(self.execution_time_ms, 2),
            "coverage_delta": round(self.coverage_delta, 4),
            "mutation_delta": round(self.mutation_delta, 4),
            "cache_hit_rate": self.cache_hit_rate,
            "human_review_rate": self.human_review_rate,
        }


class ContinuousVerificationMetrics:
    """
    Maintains segregated metrics across the four operational domains:
    1. synthetic_microbenchmark
    2. real_repository
    3. unseen_tasks
    4. browser_qa
    """

    def __init__(self) -> None:
        self.synthetic_microbenchmark = MetricBucket()
        self.real_repository = MetricBucket()
        self.unseen_tasks = MetricBucket()
        self.browser_qa = MetricBucket()

    def get_bucket(self, domain: str) -> MetricBucket:
        domain_clean = domain.lower().replace(" ", "_")
        if "benchmark" in domain_clean or "micro" in domain_clean:
            return self.synthetic_microbenchmark
        elif "unseen" in domain_clean:
            return self.unseen_tasks
        elif "browser" in domain_clean or "qa" in domain_clean:
            return self.browser_qa
        else:
            return self.real_repository

    def to_dict(self) -> Dict[str, Any]:
        return {
            "synthetic_microbenchmark": self.synthetic_microbenchmark.to_dict(),
            "real_repository": self.real_repository.to_dict(),
            "unseen_tasks": self.unseen_tasks.to_dict(),
            "browser_qa": self.browser_qa.to_dict(),
        }
