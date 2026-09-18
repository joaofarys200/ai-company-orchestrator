"""
JARVIS OS — Phase 62: Continuous Verification & Autonomous Regression Governance
Module: baseline.py
Immutable Baseline Store recording versioned baseline snapshots.
Historical baselines are strictly immutable and never overwritten.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional

from .models import BaselineSnapshot, CoverageVector


class BaselineStore:
    """
    Manages immutable BaselineSnapshots.
    Each baseline represents a validated state of the system with full coverage and execution data.
    New observations create new version IDs rather than mutating previous baselines.
    """

    def __init__(self) -> None:
        self._snapshots: Dict[str, BaselineSnapshot] = {}
        self._history: List[str] = []

    def create_snapshot(
        self,
        test_results: Dict[str, Any],
        coverage_vector: CoverageVector,
        mutation_data: Optional[Dict[str, Any]] = None,
        regression_state: str = "STABLE",
        flaky_status: Optional[Dict[str, Any]] = None,
        execution_duration: float = 0.0,
        evidence_hashes: Optional[List[str]] = None,
        environment_metadata: Optional[Dict[str, Any]] = None,
    ) -> BaselineSnapshot:
        """Create a new immutable baseline snapshot with a unique version ID."""
        ts = time.time()
        snap_id = f"snap_{int(ts * 1000)}"
        version_id = f"v{len(self._history) + 1}_{snap_id[:8]}"

        snapshot = BaselineSnapshot(
            snapshot_id=snap_id,
            version_id=version_id,
            timestamp=ts,
            test_results=dict(test_results),
            coverage_vector=coverage_vector,
            mutation_data=dict(mutation_data or {}),
            regression_state=regression_state,
            flaky_status=dict(flaky_status or {}),
            execution_duration=execution_duration,
            evidence_hashes=list(evidence_hashes or []),
            environment_metadata=dict(environment_metadata or {"os": "windows", "python": "3.11"}),
            immutable=True,
        )

        self._snapshots[snap_id] = snapshot
        self._history.append(snap_id)
        return snapshot

    def get_latest_snapshot(self) -> Optional[BaselineSnapshot]:
        if not self._history:
            return None
        return self._snapshots[self._history[-1]]

    def get_snapshot(self, snapshot_id: str) -> Optional[BaselineSnapshot]:
        return self._snapshots.get(snapshot_id)

    def list_history(self) -> List[Dict[str, Any]]:
        return [self._snapshots[sid].to_dict() for sid in self._history]
