"""
JARVIS OS — Phase 50: Behavioral Contract Preservation & Migration Proof
Structural Schema Validation for Baselines, Traces, and Proofs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from agents.behavioral_contract_proof.models import (
    BehaviorBaseline,
    BehavioralModel,
    MigrationProof,
    RuntimeTrace,
)


class BehavioralValidationError(ValueError):
    """Raised when an object fails structural validation."""
    pass


class BehavioralValidator:
    """
    Validates structural integrity and correctness of behavioral entities.
    """

    @classmethod
    def validate_baseline(cls, baseline: BehaviorBaseline) -> None:
        """Validates BehaviorBaseline structure."""
        if not baseline.contract_id:
            raise BehavioralValidationError("BehaviorBaseline requires a non-empty contract_id")
        if not baseline.contract_version:
            raise BehavioralValidationError("BehaviorBaseline requires a non-empty contract_version")
        if not baseline.consumer_id:
            raise BehavioralValidationError("BehaviorBaseline requires a non-empty consumer_id")
        if not (100 <= baseline.status_code <= 599):
            raise BehavioralValidationError(f"Invalid HTTP status code: {baseline.status_code}")
        if not isinstance(baseline.input_shape, dict):
            raise BehavioralValidationError("input_shape must be a dictionary")
        if not isinstance(baseline.output_shape, dict):
            raise BehavioralValidationError("output_shape must be a dictionary")

    @classmethod
    def validate_trace(cls, trace: RuntimeTrace) -> None:
        """Validates RuntimeTrace structure."""
        if not trace.trace_id:
            raise BehavioralValidationError("RuntimeTrace requires a non-empty trace_id")
        if not trace.contract_id:
            raise BehavioralValidationError("RuntimeTrace requires a non-empty contract_id")
        if not trace.consumer_id:
            raise BehavioralValidationError("RuntimeTrace requires a non-empty consumer_id")
        if not (100 <= trace.status_code <= 599):
            raise BehavioralValidationError(f"Invalid HTTP status code: {trace.status_code}")

    @classmethod
    def validate_proof(cls, proof: MigrationProof) -> None:
        """Validates MigrationProof structure."""
        if not proof.migration_id:
            raise BehavioralValidationError("MigrationProof requires a non-empty migration_id")
        if not proof.before_version or not proof.after_version:
            raise BehavioralValidationError("MigrationProof requires before_version and after_version")
        if not (0.0 <= proof.confidence <= 1.0):
            raise BehavioralValidationError(f"Confidence score must be between 0.0 and 1.0, got {proof.confidence}")
