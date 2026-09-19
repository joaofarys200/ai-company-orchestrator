"""
Phase 71 — Operational Schema & Contract Validator
Validates runtime payloads and parameters against required operational schemas.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


class PayloadValidationError(ValueError):
    """Raised when an operational payload fails structural validation."""
    pass


class OperationalPayloadValidator:
    """Validates structural correctness of observations, incidents, and recovery requests."""

    REQUIRED_OBSERVATION_FIELDS = {
        "service_id", "environment", "state", "latency_ms", "error_rate", "availability"
    }

    @classmethod
    def validate_observation_dict(cls, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        for field in cls.REQUIRED_OBSERVATION_FIELDS:
            if field not in data:
                errors.append(f"Missing required field: '{field}'")

        if "error_rate" in data:
            try:
                val = float(data["error_rate"])
                if val < 0.0 or val > 1.0:
                    errors.append("error_rate must be between 0.0 and 1.0")
            except (ValueError, TypeError):
                errors.append("error_rate must be numeric")

        if "availability" in data:
            try:
                val = float(data["availability"])
                if val < 0.0 or val > 1.0:
                    errors.append("availability must be between 0.0 and 1.0")
            except (ValueError, TypeError):
                errors.append("availability must be numeric")

        return (len(errors) == 0, errors)

    @classmethod
    def enforce_observation_dict(cls, data: Dict[str, Any]) -> None:
        valid, errors = cls.validate_observation_dict(data)
        if not valid:
            raise PayloadValidationError(f"Payload validation failed: {'; '.join(errors)}")
