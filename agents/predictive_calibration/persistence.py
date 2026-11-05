"""
JARVIS OS — Phase 76: Autonomous Engineering Learning & Predictive Calibration
Module: persistence.py
Durable atomic persistence, versioned calibration store, and rollback management.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from .models import (
    CalibrationState,
    CalibrationVersion,
    DriftSignal,
    ObservedOutcome,
    PredictionOutcomePair,
    PredictionRecord,
    PredictionType,
)
from .recorder import PredictionOutcomeRecorder


class CalibrationStore:
    """
    Manages versioned, durable storage for prediction records, outcomes,
    fitted calibration parameters, and rollback ledgers.
    """

    def __init__(self, base_dir: str = ".jarvis/predictive_calibration"):
        self.base_dir = Path(base_dir)
        self.versions_dir = self.base_dir / "versions"
        self.records_file = self.base_dir / "pairs.json"
        self.drift_file = self.base_dir / "drift_signals.json"
        self.rollback_file = self.base_dir / "rollback_ledger.json"

        self.versions_dir.mkdir(parents=True, exist_ok=True)

    def save_calibration_version(self, version: CalibrationVersion) -> Path:
        """Atomically persist a versioned calibration model."""
        target_path = self.versions_dir / f"{version.version_id}.json"
        temp_path = self.versions_dir / f"{version.version_id}.tmp"

        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(version.to_dict(), f, indent=2)

        # Atomic replacement
        os.replace(temp_path, target_path)
        return target_path

    def load_calibration_version(self, version_id: str) -> Optional[CalibrationVersion]:
        """Load a persisted calibration version by ID."""
        target_path = self.versions_dir / f"{version_id}.json"
        if not target_path.exists():
            return None
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return CalibrationVersion.from_dict(data)

    def get_active_promoted_version(
        self,
        prediction_type: PredictionType,
        target_metric: str,
    ) -> Optional[CalibrationVersion]:
        """
        Retrieve the latest PROMOTED calibration version for the requested metric.
        """
        candidates: List[CalibrationVersion] = []
        for f in self.versions_dir.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                    ver = CalibrationVersion.from_dict(data)
                    if (
                        ver.prediction_type == prediction_type
                        and ver.target_metric == target_metric
                        and ver.state == CalibrationState.PROMOTED
                    ):
                        candidates.append(ver)
            except Exception:
                continue

        if not candidates:
            return None

        # Return latest by promoted_at or created_at
        return sorted(candidates, key=lambda v: (v.promoted_at or 0.0, v.created_at), reverse=True)[0]

    def rollback_calibration(
        self,
        current_version_id: str,
        target_version_id: str,
        reason: str = "Rollback requested",
    ) -> bool:
        """
        Roll back an active calibration version to a previously validated version.
        """
        curr = self.load_calibration_version(current_version_id)
        target = self.load_calibration_version(target_version_id)
        if not curr or not target:
            return False

        curr.state = CalibrationState.ROLLED_BACK
        target.state = CalibrationState.PROMOTED
        target.description += f" [Restored via rollback from {current_version_id}]"

        self.save_calibration_version(curr)
        self.save_calibration_version(target)

        # Log rollback
        rollbacks = []
        if self.rollback_file.exists():
            try:
                with open(self.rollback_file, "r", encoding="utf-8") as f:
                    rollbacks = json.load(f)
            except Exception:
                rollbacks = []
        rollbacks.append({
            "from_version": current_version_id,
            "to_version": target_version_id,
            "reason": reason,
        })
        with open(self.rollback_file, "w", encoding="utf-8") as f:
            json.dump(rollbacks, f, indent=2)

        return True

    def save_recorder_state(self, recorder: PredictionOutcomeRecorder) -> None:
        """Persist all reconciled pairs from the recorder."""
        data = [p.to_dict() for p in recorder._pairs_by_op.values()]
        temp_path = self.base_dir / "pairs.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(temp_path, self.records_file)

    def load_recorder_state(self, recorder: PredictionOutcomeRecorder) -> None:
        """Load persisted prediction-outcome pairs into the recorder."""
        if not self.records_file.exists():
            return
        with open(self.records_file, "r", encoding="utf-8") as f:
            items = json.load(f)
        for item in items:
            pred = PredictionRecord.from_dict(item["prediction"])
            recorder.record_prediction(pred)
            if item.get("outcome"):
                out = ObservedOutcome.from_dict(item["outcome"])
                recorder.record_outcome(out)
