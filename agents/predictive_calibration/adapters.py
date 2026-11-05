"""
JARVIS OS — Phase 76: Autonomous Engineering Learning & Predictive Calibration
Module: adapters.py
Safe feedback adapters providing calibrated estimates to Phase 73 (Macro-Refactoring),
Phase 74 (Architectural Optimization), and Phase 75 (Portfolio Orchestration).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .calibrator import PredictiveCalibrator
from .models import (
    CalibrationVersion,
    EstimateResult,
    PredictionType,
)
from .persistence import CalibrationStore


class Phase73MacroRefactoringAdapter:
    """
    Refines migration step duration and verification cost estimates for Phase 73.
    """

    def __init__(self, store: CalibrationStore, calibrator: PredictiveCalibrator):
        self.store = store
        self.calibrator = calibrator

    def estimate_migration_duration(
        self,
        step_count: int,
        component_count: int,
        target_metric: str = "macro_migration_duration",
    ) -> EstimateResult:
        """
        Calculates baseline duration and applies promoted calibration if available.
        Baseline: step_count * 25.0 + component_count * 10.0 seconds.
        """
        baseline_duration = float(step_count * 25.0 + component_count * 10.0)
        active_cal = self.store.get_active_promoted_version(
            PredictionType.CONTINUOUS_DURATION, target_metric
        )
        return self.calibrator.calibrate(baseline_duration, active_cal)


class Phase74ArchitecturalOptimizationAdapter:
    """
    Refines predicted architectural performance deltas and costs for Phase 74.
    """

    def __init__(self, store: CalibrationStore, calibrator: PredictiveCalibrator):
        self.store = store
        self.calibrator = calibrator

    def estimate_performance_gain(
        self,
        baseline_delta: float,
        pattern_type: str,
    ) -> EstimateResult:
        """
        Calibrates raw predicted performance gains for a specific structural pattern.
        """
        metric_key = f"arch_delta_{pattern_type.lower()}"
        active_cal = self.store.get_active_promoted_version(
            PredictionType.CONTINUOUS_BENEFIT, metric_key
        )
        return self.calibrator.calibrate(baseline_delta, active_cal)


class Phase75PortfolioOrchestrationAdapter:
    """
    Refines initiative effort, duration, and budget forecasts for Phase 75 portfolio scheduling.
    """

    def __init__(self, store: CalibrationStore, calibrator: PredictiveCalibrator):
        self.store = store
        self.calibrator = calibrator

    def estimate_initiative_effort(
        self,
        raw_effort: float,
        initiative_type: str,
    ) -> EstimateResult:
        """
        Refines initiative effort estimates based on historical execution error.
        """
        metric_key = f"effort_{initiative_type.lower()}"
        active_cal = self.store.get_active_promoted_version(
            PredictionType.CONTINUOUS_EFFORT, metric_key
        )
        return self.calibrator.calibrate(raw_effort, active_cal)
