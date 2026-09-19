"""
Phase 72 — Security Guard and Validation
Hardens against poisoned telemetry, forged timestamps, command injection, and path traversal.
"""

from __future__ import annotations

import math
import re
import time
from typing import Any, Dict

from .models import (
    PreventiveAction,
    ReliabilityObservation,
)


class SecurityViolationError(ValueError):
    """Raised when incoming telemetry, service identifiers, or actions fail security sanitization."""
    pass


class ReliabilitySecurityGuard:
    """Sanitizes inputs and prevents telemetry manipulation or injection attacks."""

    _FORBIDDEN_CHARS = re.compile(r"[\;\&\|\`\$\(\)\<\>\\]")
    _PATH_TRAVERSAL = re.compile(r"(\.\./|\.\.\\)")

    @classmethod
    def validate_service_id(cls, service_id: str) -> None:
        if not service_id or not isinstance(service_id, str):
            raise SecurityViolationError("Service ID must be a non-empty string.")
        if cls._PATH_TRAVERSAL.search(service_id):
            raise SecurityViolationError(f"Path traversal detected in service ID: {service_id}")
        if cls._FORBIDDEN_CHARS.search(service_id):
            raise SecurityViolationError(f"Command injection character detected in service ID: {service_id}")
        if len(service_id) > 128:
            raise SecurityViolationError("Service ID exceeds maximum length of 128 characters.")

    @classmethod
    def validate_observation(cls, observation: ReliabilityObservation) -> None:
        cls.validate_service_id(observation.service)

        # 1. Validate numeric value
        val = observation.value
        if math.isnan(val) or math.isinf(val):
            raise SecurityViolationError("Telemetry value must be finite; NaN/Inf rejected.")

        # 2. Check for extreme non-physical values
        if abs(val) > 1e12:
            raise SecurityViolationError(f"Telemetry value {val} out of physically plausible bounds.")

        # 3. Metric name sanitization
        metric = observation.metric
        if not metric or not isinstance(metric, str) or cls._FORBIDDEN_CHARS.search(metric) or cls._PATH_TRAVERSAL.search(metric):
            raise SecurityViolationError(f"Invalid or unsafe metric identifier: {metric}")

        # 4. Timestamp sanitization (reject timestamps in far future or negative epoch)
        now = time.time()
        # Allow +/- 3 days drift maximum
        if observation.timestamp < 0 or observation.timestamp > (now + 259200):
            raise SecurityViolationError(f"Forged timestamp detected: {observation.timestamp} (current: {now})")

    @classmethod
    def validate_preventive_action(cls, action: PreventiveAction) -> None:
        cls.validate_service_id(action.target_service)
        if cls._FORBIDDEN_CHARS.search(action.expected_effect) or cls._PATH_TRAVERSAL.search(action.expected_effect):
            raise SecurityViolationError("Unsafe characters detected in action expected_effect.")
