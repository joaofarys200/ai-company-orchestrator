"""
JARVIS OS — Phase 57: Failure Diagnosis & Classification
Captures, classifies and tracks runtime, syntax, contract, and security failures during mission execution.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from .models import AutonomousMission


class FailureSeverity:
    BLOCKING = "BLOCKING"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class FailureCategory:
    SYNTAX = "SYNTAX"
    RUNTIME = "RUNTIME"
    CONTRACT = "CONTRACT"
    BEHAVIOR = "BEHAVIOR"
    SECURITY = "SECURITY"
    ECONOMIC = "ECONOMIC"
    ENVIRONMENT = "ENVIRONMENT"


class FailureManager:
    """Manages failure reporting and resolution status for an autonomous mission."""

    @classmethod
    def record_failure(
        cls,
        mission: AutonomousMission,
        description: str,
        category: str,
        severity: str = FailureSeverity.BLOCKING,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        fid = f"fail_{uuid.uuid4().hex[:6]}"
        failure_record = {
            "failure_id": fid,
            "description": description,
            "category": category,
            "severity": severity,
            "blocking": severity == FailureSeverity.BLOCKING,
            "resolved": False,
            "timestamp": time.time(),
            "details": details or {},
        }
        mission.failures.append(failure_record)
        return failure_record

    @classmethod
    def resolve_failure(cls, mission: AutonomousMission, failure_id: str, resolution_notes: str) -> bool:
        for f in mission.failures:
            if f["failure_id"] == failure_id:
                f["resolved"] = True
                f["resolution_notes"] = resolution_notes
                f["resolved_at"] = time.time()
                return True
        return False
