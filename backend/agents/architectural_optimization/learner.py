"""
JARVIS OS — Phase 74: Autonomous Architectural Evolution & Optimization
Module: learner.py
Continuous calibration store. Tracks prediction accuracy vs empirical outcomes
to avoid repeating flawed assumptions across architectural optimization cycles.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import CalibrationRecord


class OptimizationLearner:
    """
    Maintains a durable ledger of past optimization experiments and real executions,
    calibrating future predictions and penalizing structural patterns that previously failed.
    """

    def __init__(self, storage_dir: Optional[str] = None):
        self.storage_dir = Path(storage_dir or ".jarvis/architectural_optimization/calibration")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.records: List[CalibrationRecord] = []
        self._load_records()

    def record_outcome(
        self,
        pattern_type: str,
        target_metric: str,
        predicted_delta: float,
        measured_delta: float,
        successful: bool,
        notes: str = "",
    ) -> CalibrationRecord:
        """
        Records a calibration observation and persists it to disk.
        """
        error = abs(predicted_delta - measured_delta)
        rec = CalibrationRecord(
            calibration_id=f"cal_{uuid.uuid4().hex[:8]}",
            pattern_type=pattern_type,
            target_metric=target_metric,
            predicted_delta=predicted_delta,
            measured_delta=measured_delta,
            prediction_error=round(error, 3),
            successful=successful,
            notes=notes,
            timestamp=time.time(),
        )
        self.records.append(rec)
        self._persist_record(rec)
        return rec

    def get_pattern_penalty(self, pattern_type: str, target_metric: str) -> float:
        """
        Computes a risk penalty [0.0 to 0.4] for a pattern type based on historical failure rate.
        If a pattern repeatedly caused regressions, future predictions penalize it.
        """
        matching = [
            r for r in self.records
            if r.pattern_type == pattern_type and r.target_metric == target_metric
        ]
        if not matching:
            return 0.0

        failures = [r for r in matching if not r.successful]
        failure_rate = len(failures) / len(matching)
        return round(failure_rate * 0.4, 3)

    def is_assumption_previously_refuted(self, pattern_type: str, target_metric: str) -> bool:
        """
        Returns True if historical experiments prove this pattern produces regressions or
        no measurable improvement on this target metric.
        """
        matching = [
            r for r in self.records
            if r.pattern_type == pattern_type and r.target_metric == target_metric
        ]
        if len(matching) >= 2 and all(not r.successful for r in matching):
            return True
        return False

    def _persist_record(self, record: CalibrationRecord) -> None:
        file_path = self.storage_dir / f"{record.calibration_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(record.to_dict(), f, indent=2)

    def _load_records(self) -> None:
        for f in self.storage_dir.glob("cal_*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                    rec = CalibrationRecord(
                        calibration_id=data["calibration_id"],
                        pattern_type=data["pattern_type"],
                        target_metric=data["target_metric"],
                        predicted_delta=data["predicted_delta"],
                        measured_delta=data["measured_delta"],
                        prediction_error=data["prediction_error"],
                        successful=data["successful"],
                        notes=data.get("notes", ""),
                        timestamp=data.get("timestamp", 0.0),
                    )
                    self.records.append(rec)
            except Exception:
                continue
