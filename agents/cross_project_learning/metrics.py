"""
JARVIS OS — Phase 63: Cross-Project Engineering Learning & Verification Transfer
Module: metrics.py
CrossProjectLearningMetrics tracks telemetry across retrieval, applicability, transfer,
harm detection, local validation, and cache performance.
Explicitly separates synthetic microbenchmarks, real repository runs, and unseen projects.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MetricBucket:
    items_indexed: int = 0
    queries_executed: int = 0
    candidates_retrieved: int = 0
    transfers_proposed: int = 0
    transfers_accepted: int = 0
    transfers_rejected: int = 0
    local_validations_passed: int = 0
    local_validations_failed: int = 0
    harm_events_detected: int = 0
    conflicts_detected: int = 0
    stale_items_detected: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_cpu_time_ms: float = 0.0

    @property
    def transfer_acceptance_rate(self) -> float:
        total = self.transfers_accepted + self.transfers_rejected
        return self.transfers_accepted / total if total > 0 else 0.0

    @property
    def validation_success_rate(self) -> float:
        total = self.local_validations_passed + self.local_validations_failed
        return self.local_validations_passed / total if total > 0 else 0.0

    @property
    def harm_rate(self) -> float:
        return self.harm_events_detected / self.transfers_accepted if self.transfers_accepted > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["transfer_acceptance_rate"] = round(self.transfer_acceptance_rate, 4)
        d["validation_success_rate"] = round(self.validation_success_rate, 4)
        d["harm_rate"] = round(self.harm_rate, 4)
        return d


class CrossProjectLearningMetrics:
    """Manages telemetry partitioned by evaluation axis."""

    def __init__(self) -> None:
        self.synthetic_microbenchmark = MetricBucket()
        self.real_repository = MetricBucket()
        self.unseen_projects = MetricBucket()
        self.browser_qa = MetricBucket()

    def get_bucket(self, context: str) -> MetricBucket:
        if "microbenchmark" in context.lower():
            return self.synthetic_microbenchmark
        elif "real" in context.lower():
            return self.real_repository
        elif "unseen" in context.lower():
            return self.unseen_projects
        elif "browser" in context.lower():
            return self.browser_qa
        return self.real_repository

    def record_transfer(
        self,
        accepted: bool,
        context: str = "real_repository",
    ) -> None:
        bucket = self.get_bucket(context)
        bucket.transfers_proposed += 1
        if accepted:
            bucket.transfers_accepted += 1
        else:
            bucket.transfers_rejected += 1

    def record_validation(
        self,
        passed: bool,
        is_harm: bool = False,
        context: str = "real_repository",
    ) -> None:
        bucket = self.get_bucket(context)
        if passed:
            bucket.local_validations_passed += 1
        else:
            bucket.local_validations_failed += 1
        if is_harm:
            bucket.harm_events_detected += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "synthetic_microbenchmark": self.synthetic_microbenchmark.to_dict(),
            "real_repository": self.real_repository.to_dict(),
            "unseen_projects": self.unseen_projects.to_dict(),
            "browser_qa": self.browser_qa.to_dict(),
        }
