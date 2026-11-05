"""
JARVIS OS — Phase 79: Autonomous Adaptive Experimentation & Scientific Hypothesis Validation
Module: executor.py
Safe experiment preflight validation, authorization boundary enforcement, and observation recording.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Optional, Tuple

from .models import (
    CandidateExperiment,
    ExperimentExecutionRecord,
    OutcomeFidelity,
    UnauthorizedExperimentError,
)


class ExperimentExecutor:
    """
    Executes and records diagnostic probes while enforcing strict non-destructive safety gates.
    """

    DESTRUCTIVE_KEYWORDS = {"rm ", "drop ", "delete ", "kill ", "format ", "truncate ", "reboot "}

    @classmethod
    def execute_experiment(
        cls,
        experiment: CandidateExperiment,
        simulated_or_real_observation: str,
        matched_outcome: str,
        auth_token: Optional[str] = None,
        is_synthetic: bool = False,
    ) -> ExperimentExecutionRecord:
        """
        Validates safety policy and records the empirical observation with SHA-256 provenance.
        """
        # Safety validation
        for kw in cls.DESTRUCTIVE_KEYWORDS:
            if kw in experiment.probe_check.lower():
                raise UnauthorizedExperimentError(
                    f"Forbidden destructive command '{kw}' detected in experiment probe '{experiment.probe_check}'."
                )

        # Authorization check
        if experiment.requires_authorization:
            if not auth_token or "AUTH" not in auth_token:
                raise UnauthorizedExperimentError(
                    f"Privileged experiment '{experiment.experiment_id}' requires a valid authorization token."
                )

        # Compute provenance hash
        payload = f"{experiment.experiment_id}:{experiment.probe_check}:{simulated_or_real_observation}:{time.time()}"
        prov_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        rec = ExperimentExecutionRecord(
            record_id=f"rec_{uuid.uuid4().hex[:8]}",
            experiment_id=experiment.experiment_id,
            observation=simulated_or_real_observation,
            matched_outcome=matched_outcome,
            observation_time=time.time(),
            provenance_hash=prov_hash,
            cost_incurred=experiment.cost,
            outcome_fidelity=(
                OutcomeFidelity.SYNTHETIC_FIXTURE_EVIDENCE
                if is_synthetic
                else OutcomeFidelity.REAL_RUNTIME_EXECUTION
            ),
        )
        return rec
