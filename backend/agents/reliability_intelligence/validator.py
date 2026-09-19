"""
Phase 72 — Payload and Schema Validator
Validates observation payloads, preventive actions, and prediction inputs.
"""

from __future__ import annotations

from typing import Any, Dict


class PayloadValidationError(ValueError):
    """Raised when payload schema validation fails."""
    pass


class ReliabilityPayloadValidator:
    """Validates structure and typing of incoming requests."""

    @staticmethod
    def validate_observation_payload(payload: Dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            raise PayloadValidationError("Payload must be a dictionary.")
        if "metric" not in payload:
            raise PayloadValidationError("Missing required field 'metric'.")
        if "value" not in payload:
            raise PayloadValidationError("Missing required field 'value'.")
        try:
            float(payload["value"])
        except (ValueError, TypeError):
            raise PayloadValidationError("Field 'value' must be numeric.")
