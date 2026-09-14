"""
JARVIS OS — Phase 42: Deterministic Structured Experience Indexing
Builds multi-axis inverted indexes over semantic intent, taxonomy, technology stack,
failure classes, and temporal bounds without opaque vector databases.
"""

from __future__ import annotations

import bisect
import time
from collections import defaultdict
from typing import Any, Optional

from agents.experience_memory.models import ExperienceRecord


class ExperienceIndex:
    """Multi-dimensional inverted index for fast deterministic experience retrieval with incremental updates."""

    def __init__(
        self,
        index_version: str = "43.0.0",
        schema_version: str = "2.0.0",
        policy_version: str = "43.0.0",
        architecture_snapshot: str = "JARVIS_PHASE_43_MODULAR",
    ):
        self.index_version = index_version
        self.schema_version = schema_version
        self.policy_version = policy_version
        self.architecture_snapshot = architecture_snapshot
        self._by_intent: dict[str, set[str]] = defaultdict(set)
        self._by_taxonomy: dict[str, set[str]] = defaultdict(set)
        self._by_tech: dict[str, set[str]] = defaultdict(set)
        self._by_failure: dict[str, set[str]] = defaultdict(set)
        self._by_decision: dict[str, set[str]] = defaultdict(set)
        self._timeline: list[tuple[float, str]] = []  # sorted by (created_at, exp_id)
        self.incremental_appends_count = 0
        self.last_incremental_latency_ms = 0.0

    def index_experience(self, record: ExperienceRecord) -> None:
        """Indexes an experience record incrementally preserving temporal ordering via bisect."""
        self.index_incremental(record)

    def index_incremental(self, record: ExperienceRecord) -> float:
        """
        Incrementally updates inverted indices in O(log N) temporal insertion,
        eliminating costly global rebuilds when appending single operational records.
        Returns elapsed latency in milliseconds.
        """
        t0 = time.perf_counter()
        exp_id = record.experience_id
        sig = record.intent_signature

        # Intent category
        if sig.intent_category:
            self._by_intent[sig.intent_category.upper()].add(exp_id)

        # Tags and taxonomy
        for tag in record.tags:
            self._by_taxonomy[tag.upper()].add(exp_id)

        # Technology stack
        for t in sig.technology:
            self._by_tech[t.lower()].add(exp_id)

        # Failure class
        if sig.observed_failure and sig.observed_failure != "NONE":
            self._by_failure[sig.observed_failure.upper()].add(exp_id)

        # Decision
        if sig.decision:
            self._by_decision[sig.decision.upper()].add(exp_id)

        # Incremental timeline insertion using bisect (O(log N) lookup + O(N) shift vs O(N log N) full sort)
        bisect.insort(self._timeline, (record.created_at, exp_id))

        self.incremental_appends_count += 1
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self.last_incremental_latency_ms = elapsed_ms
        return elapsed_ms

    def index_batch_incremental(self, records: list[ExperienceRecord]) -> float:
        """Appends a batch of records incrementally. Returns total duration in ms."""
        t0 = time.perf_counter()
        for r in records:
            self.index_incremental(r)
        return (time.perf_counter() - t0) * 1000.0

    def query_candidates(
        self,
        intent_category: Optional[str] = None,
        technology: Optional[list[str]] = None,
        failure_class: Optional[str] = None,
        decision_context: Optional[str] = None,
        max_timestamp: Optional[float] = None,
    ) -> set[str]:
        """
        Retrieves candidate experience IDs satisfying multi-axis criteria,
        strictly enforcing the temporal upper bound (Anti-Leakage Guarantee).
        """
        candidate_sets: list[set[str]] = []

        if intent_category and intent_category.upper() in self._by_intent:
            candidate_sets.append(self._by_intent[intent_category.upper()])

        if failure_class and failure_class.upper() in self._by_failure:
            candidate_sets.append(self._by_failure[failure_class.upper()])

        if technology:
            tech_matches = set()
            for t in technology:
                if t.lower() in self._by_tech:
                    tech_matches.update(self._by_tech[t.lower()])
            if tech_matches:
                candidate_sets.append(tech_matches)

        if decision_context and decision_context.upper() in self._by_decision:
            candidate_sets.append(self._by_decision[decision_context.upper()])

        if not candidate_sets:
            # Fallback: all experiences in timeline
            all_ids = {item[1] for item in self._timeline}
        else:
            # Union of candidate sets for high recall before scoring
            all_ids = set().union(*candidate_sets)

        # Enforce strict Anti-Leakage filter: only experiences created before max_timestamp
        if max_timestamp is not None:
            valid_temporal_ids = {
                item[1] for item in self._timeline if item[0] < max_timestamp
            }
            all_ids = all_ids.intersection(valid_temporal_ids)

        return all_ids

    def rebuild(self, records: list[ExperienceRecord]) -> float:
        """Flushes and rebuilds indexes from scratch. Returns total rebuild duration in ms."""
        t0 = time.perf_counter()
        self._by_intent.clear()
        self._by_taxonomy.clear()
        self._by_tech.clear()
        self._by_failure.clear()
        self._by_decision.clear()
        self._timeline.clear()
        self.incremental_appends_count = 0
        for r in records:
            self.index_incremental(r)
        return (time.perf_counter() - t0) * 1000.0

    def get_metadata(self) -> dict[str, Any]:
        return {
            "index_version": self.index_version,
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "architecture_snapshot": self.architecture_snapshot,
            "indexed_count": len(self._timeline),
            "incremental_appends_count": self.incremental_appends_count,
            "last_incremental_latency_ms": round(self.last_incremental_latency_ms, 4),
        }
