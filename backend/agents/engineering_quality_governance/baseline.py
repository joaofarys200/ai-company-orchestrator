"""
JARVIS OS — Phase 68: Quality Baseline Management
Captures QUALITY_BASELINE before mission start and QUALITY_AFTER post mission execution.
Ensures both baselines are stored immutably with cryptographic verification.
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
from typing import Any, Dict, Optional

from .models import (
    DimensionChange,
    DimensionEvaluation,
    QualityDelta,
    QualityDimension,
    QualitySnapshot,
)


class QualityBaselineManager:
    """
    Captures, stores, and compares immutable QualitySnapshots.
    Enforces that baseline snapshots cannot be altered after creation.
    """

    def __init__(self) -> None:
        self._baselines: Dict[str, QualitySnapshot] = {}  # mission_id -> baseline
        self._afters: Dict[str, QualitySnapshot] = {}  # mission_id -> after
        self._sealed_hashes: Dict[str, str] = {}  # snapshot_id -> sha256

    def _compute_hash(self, snapshot: QualitySnapshot) -> str:
        payload = {
            "snapshot_id": snapshot.snapshot_id,
            "mission_id": snapshot.mission_id,
            "architecture_hash": snapshot.architecture_hash,
            "contract_hash": snapshot.contract_hash,
            "behavior_hash": snapshot.behavior_hash,
            "test_hash": snapshot.test_hash,
            "security_hash": snapshot.security_hash,
            "dimensions": {k: v.to_dict() for k, v in snapshot.dimensions.items()},
        }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def capture_baseline(
        self,
        mission_id: str,
        snapshot_id: Optional[str] = None,
        dimensions: Optional[Dict[str, DimensionEvaluation]] = None,
        hashes: Optional[Dict[str, str]] = None,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> QualitySnapshot:
        """Captures QUALITY_BASELINE before an F67 mission begins."""
        if mission_id in self._baselines:
            raise ValueError(f"Baseline for mission '{mission_id}' already exists and is immutable.")

        s_id = snapshot_id or f"baseline_{mission_id}_{int(time.time()*1000)}"
        h = hashes or {}
        prov = provenance or {"phase": "phase68", "agent": "EngineeringQualityGovernance"}

        snapshot = QualitySnapshot(
            snapshot_id=s_id,
            mission_id=mission_id,
            architecture_hash=h.get("architecture", "arch_init"),
            contract_hash=h.get("contract", "contract_init"),
            behavior_hash=h.get("behavior", "behavior_init"),
            test_hash=h.get("test", "test_init"),
            security_hash=h.get("security", "security_init"),
            timestamp=time.time(),
            provenance=prov,
            dimensions=copy.deepcopy(dimensions or {}),
            sealed=True,
        )

        h_val = self._compute_hash(snapshot)
        self._sealed_hashes[snapshot.snapshot_id] = h_val
        self._baselines[mission_id] = snapshot
        return copy.deepcopy(snapshot)

    def capture_after(
        self,
        mission_id: str,
        snapshot_id: Optional[str] = None,
        dimensions: Optional[Dict[str, DimensionEvaluation]] = None,
        hashes: Optional[Dict[str, str]] = None,
        provenance: Optional[Dict[str, Any]] = None,
    ) -> QualitySnapshot:
        """Captures QUALITY_AFTER after mission execution."""
        if mission_id in self._afters:
            raise ValueError(f"Post-mission snapshot for mission '{mission_id}' already exists and is immutable.")

        s_id = snapshot_id or f"after_{mission_id}_{int(time.time()*1000)}"
        h = hashes or {}
        prov = provenance or {"phase": "phase68", "agent": "EngineeringQualityGovernance"}

        snapshot = QualitySnapshot(
            snapshot_id=s_id,
            mission_id=mission_id,
            architecture_hash=h.get("architecture", "arch_post"),
            contract_hash=h.get("contract", "contract_post"),
            behavior_hash=h.get("behavior", "behavior_post"),
            test_hash=h.get("test", "test_post"),
            security_hash=h.get("security", "security_post"),
            timestamp=time.time(),
            provenance=prov,
            dimensions=copy.deepcopy(dimensions or {}),
            sealed=True,
        )

        h_val = self._compute_hash(snapshot)
        self._sealed_hashes[snapshot.snapshot_id] = h_val
        self._afters[mission_id] = snapshot
        return copy.deepcopy(snapshot)

    def get_baseline(self, mission_id: str) -> Optional[QualitySnapshot]:
        snap = self._baselines.get(mission_id)
        return copy.deepcopy(snap) if snap else None

    def get_after(self, mission_id: str) -> Optional[QualitySnapshot]:
        snap = self._afters.get(mission_id)
        return copy.deepcopy(snap) if snap else None

    def verify_integrity(self, snapshot_id: str, snapshot: QualitySnapshot) -> bool:
        expected = self._sealed_hashes.get(snapshot_id)
        if not expected:
            return False
        return self._compute_hash(snapshot) == expected
