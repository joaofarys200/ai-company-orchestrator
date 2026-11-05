"""
JARVIS OS — Phase 76: Autonomous Engineering Learning & Predictive Calibration
Module: models.py
Domain models, enums, exceptions, and data structures for prediction-outcome records,
calibration analytics, and estimator versions.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple


class PredictionType(str, enum.Enum):
    """Types of engineering predictions supported by the calibration engine."""
    CONTINUOUS_EFFORT = "CONTINUOUS_EFFORT"          # Effort units / story points / difficulty
    CONTINUOUS_DURATION = "CONTINUOUS_DURATION"      # Execution time in seconds
    CONTINUOUS_BENEFIT = "CONTINUOUS_BENEFIT"        # Quantitative metric improvement (e.g. % or latency ms)
    CONTINUOUS_COST = "CONTINUOUS_COST"              # Financial or resource cost in USD / CPU cycles
    PROBABILITY_FAILURE = "PROBABILITY_FAILURE"      # Probability of failure [0.0, 1.0]
    PROBABILITY_REGRESSION = "PROBABILITY_REGRESSION"# Probability of regression [0.0, 1.0]


class OutcomeVerificationStatus(str, enum.Enum):
    """Verification lifecycle of an observed outcome."""
    UNOBSERVED = "UNOBSERVED"                        # Operation pending or in-flight
    MEASURED_UNVERIFIED = "MEASURED_UNVERIFIED"      # Measurement recorded but not yet verified
    VERIFIED = "VERIFIED"                            # Empirically verified by authoritative test suite
    INVALID_MEASUREMENT = "INVALID_MEASUREMENT"      # Measurement instrument corrupted or failed
    INCOMPARABLE_ENVIRONMENT = "INCOMPARABLE_ENVIRONMENT" # Environment shifted; observation quarantined


class CalibrationState(str, enum.Enum):
    """Lifecycle state of a calibration model version."""
    EXPERIMENTAL = "EXPERIMENTAL"                    # Newly created, undergoing holdout evaluation
    SHADOW = "SHADOW"                                # Tracking live predictions in parallel without influence
    PROMOTED = "PROMOTED"                            # Authoritatively active for production estimates
    SUSPENDED = "SUSPENDED"                          # Drift detected; temporarily fallen back to baseline
    ROLLED_BACK = "ROLLED_BACK"                      # Deprecated in favor of earlier stable version


class DriftSeverity(str, enum.Enum):
    """Severity classification of detected prediction or environmental drift."""
    LOW = "LOW"
    MODERATE = "MODERATE"
    CRITICAL = "CRITICAL"


# --- Exceptions ---

class CalibrationError(Exception):
    """Base exception for predictive calibration."""
    pass


class IncompatibleUnitsError(CalibrationError):
    """Raised when pairing a prediction and outcome with incompatible units."""
    pass


class InsufficientSamplesError(CalibrationError):
    """Raised when training sample size is below the minimum required threshold."""
    pass


class DataLeakageError(CalibrationError):
    """Raised when temporal holdout ordering is violated or test data leaks into training."""
    pass


class StaleCalibrationError(CalibrationError):
    """Raised when attempting to use a suspended or superseded calibration version."""
    pass


class CalibrationPromotionError(CalibrationError):
    """Raised when a candidate calibration fails predefined promotion criteria."""
    pass


# --- Domain Data Structures ---

@dataclass
class PredictionRecord:
    """
    Immutable record of an engineering prediction captured before execution.
    """
    prediction_id: str
    operation_id: str
    prediction_type: PredictionType
    target_metric: str
    predicted_value: float
    unit: str
    estimator_version: str = "baseline_v1.0.0"
    uncertainty_low: Optional[float] = None
    uncertainty_high: Optional[float] = None
    context_features: Dict[str, Any] = field(default_factory=dict)
    assumptions: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["prediction_type"] = self.prediction_type.value
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PredictionRecord:
        d = dict(data)
        d["prediction_type"] = PredictionType(d["prediction_type"])
        return cls(**d)


@dataclass
class ObservedOutcome:
    """
    Empirical observation captured after operation completion and verification.
    """
    outcome_id: str
    operation_id: str
    actual_value: float
    unit: str
    verification_status: OutcomeVerificationStatus = OutcomeVerificationStatus.VERIFIED
    measurement_method: str = "empirical_benchmark"
    verifier_identity: str = "automated_verifier"
    notes: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["verification_status"] = self.verification_status.value
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ObservedOutcome:
        d = dict(data)
        d["verification_status"] = OutcomeVerificationStatus(d.get("verification_status", "VERIFIED"))
        return cls(**d)


@dataclass
class PredictionOutcomePair:
    """
    Reconciled pair linking a prediction to its verified actual outcome.
    """
    prediction: PredictionRecord
    outcome: Optional[ObservedOutcome] = None
    signed_error: Optional[float] = None       # predicted - actual
    absolute_error: Optional[float] = None     # |predicted - actual|
    is_eligible_for_calibration: bool = False

    def calculate_errors(self) -> None:
        """Calculate signed and absolute error if verified outcome exists."""
        if self.outcome and self.outcome.verification_status == OutcomeVerificationStatus.VERIFIED:
            self.signed_error = round(self.prediction.predicted_value - self.outcome.actual_value, 4)
            self.absolute_error = round(abs(self.signed_error), 4)
            self.is_eligible_for_calibration = True
        else:
            self.signed_error = None
            self.absolute_error = None
            self.is_eligible_for_calibration = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction": self.prediction.to_dict(),
            "outcome": self.outcome.to_dict() if self.outcome else None,
            "signed_error": self.signed_error,
            "absolute_error": self.absolute_error,
            "is_eligible_for_calibration": self.is_eligible_for_calibration,
        }


@dataclass
class ErrorMetrics:
    """Statistical summary of prediction errors over a sample set."""
    sample_count: int
    signed_bias: float                     # Mean signed error (predicted - actual)
    mean_absolute_error: float             # MAE
    root_mean_squared_error: float         # RMSE
    mean_percentage_error: Optional[float] # MAPE where mathematically valid
    brier_score: Optional[float]           # For probabilistic predictions
    overestimation_count: int
    underestimation_count: int
    exact_count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CalibrationParameters:
    """Mathematical parameters for a fitted calibration model."""
    scale_alpha: float = 1.0               # Multiplicative scaling
    offset_beta: float = 0.0               # Additive bias adjustment (actual - predicted)
    variance_sigma: float = 1.0            # Residual error variance for prediction intervals
    sample_count: int = 0
    min_samples: int = 5

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CalibrationVersion:
    """
    A durable, versioned calibration model for a specific prediction type and target metric.
    """
    version_id: str                        # e.g. "cal_v1.0.0"
    prediction_type: PredictionType
    target_metric: str
    state: CalibrationState
    parameters: CalibrationParameters
    train_metrics: Optional[ErrorMetrics] = None
    holdout_metrics: Optional[ErrorMetrics] = None
    parent_version: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    promoted_at: Optional[float] = None
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id": self.version_id,
            "prediction_type": self.prediction_type.value,
            "target_metric": self.target_metric,
            "state": self.state.value,
            "parameters": self.parameters.to_dict(),
            "train_metrics": self.train_metrics.to_dict() if self.train_metrics else None,
            "holdout_metrics": self.holdout_metrics.to_dict() if self.holdout_metrics else None,
            "parent_version": self.parent_version,
            "created_at": self.created_at,
            "promoted_at": self.promoted_at,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CalibrationVersion:
        d = dict(data)
        d["prediction_type"] = PredictionType(d["prediction_type"])
        d["state"] = CalibrationState(d["state"])
        d["parameters"] = CalibrationParameters(**d["parameters"])
        if d.get("train_metrics"):
            d["train_metrics"] = ErrorMetrics(**d["train_metrics"])
        if d.get("holdout_metrics"):
            d["holdout_metrics"] = ErrorMetrics(**d["holdout_metrics"])
        return cls(**d)


@dataclass
class DriftSignal:
    """Diagnostic signal emitted when prediction error drifts beyond acceptable tolerance."""
    signal_id: str
    prediction_type: PredictionType
    target_metric: str
    severity: DriftSeverity
    baseline_mae: float
    rolling_mae: float
    drift_ratio: float
    sample_count: int
    detected_at: float = field(default_factory=time.time)
    diagnostic: str = ""

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["prediction_type"] = self.prediction_type.value
        res["severity"] = self.severity.value
        return res


@dataclass
class EstimateResult:
    """Result returned to downstream consumers containing baseline and calibrated estimates."""
    baseline_value: float
    calibrated_value: float
    uncertainty_low: float
    uncertainty_high: float
    calibration_version: Optional[str]
    is_calibrated: bool
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
