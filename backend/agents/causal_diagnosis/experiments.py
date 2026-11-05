"""
JARVIS OS — Phase 78: Autonomous Causal Diagnosis & Root-Cause Analysis
Module: experiments.py
Safe diagnostic experiment planner and runner for hypothesis discrimination.
Enforces read-only safety, preflight validation, and authorization boundaries.
"""

from __future__ import annotations

import uuid
from typing import Dict, List, Optional, Tuple

from .models import (
    CausalHypothesis,
    DiagnosticExperiment,
    ExperimentOutcome,
    ExperimentScope,
    HypothesisStatus,
    UnauthorizedDiagnosticActionError,
)


class DiagnosticExperimentPlanner:
    """
    Formulates and evaluates safe, read-only diagnostic checks to discriminate between
    competing root-cause explanations without executing destructive operations.
    """

    DESTRUCTIVE_KEYWORDS = {"rm ", "drop ", "delete ", "kill ", "format ", "truncate ", "reboot "}

    @classmethod
    def plan_discriminating_experiment(
        cls,
        hyp_a: CausalHypothesis,
        hyp_b: CausalHypothesis,
        inspection_check: str,
        expected_if_a: str,
        expected_if_b: str,
        scope: ExperimentScope = ExperimentScope.READ_ONLY_INSPECTION,
        requires_authorization: bool = False,
    ) -> DiagnosticExperiment:
        """
        Formulates a safe diagnostic experiment capable of distinguishing between hyp_a and hyp_b.
        """
        # Safety validation
        for kw in cls.DESTRUCTIVE_KEYWORDS:
            if kw in inspection_check.lower():
                raise UnauthorizedDiagnosticActionError(
                    f"Diagnostic experiment check '{inspection_check}' contains forbidden destructive command keyword '{kw}'."
                )

        return DiagnosticExperiment(
            experiment_id=f"exp_{uuid.uuid4().hex[:8]}",
            hypothesis_tested=hyp_a.hypothesis_id,
            scope=scope,
            command_or_check=inspection_check,
            expected_observation_if_true=expected_if_a,
            expected_observation_if_false=expected_if_b,
            is_read_only=(scope == ExperimentScope.READ_ONLY_INSPECTION),
            requires_authorization=requires_authorization,
            status=ExperimentOutcome.INCONCLUSIVE,
        )

    @classmethod
    def evaluate_experiment_outcome(
        cls,
        experiment: DiagnosticExperiment,
        actual_observation: str,
        auth_token: Optional[str] = None,
    ) -> Tuple[ExperimentOutcome, str]:
        """
        Evaluates the experiment outcome against observed results, enforcing authorization if required.
        """
        if experiment.requires_authorization:
            if not auth_token or "AUTH" not in auth_token:
                experiment.status = ExperimentOutcome.BLOCKED
                experiment.conclusion = "Experiment blocked: valid authorization token required."
                return ExperimentOutcome.BLOCKED, experiment.conclusion

        experiment.actual_observation = actual_observation

        if experiment.expected_observation_if_true.lower() in actual_observation.lower():
            experiment.status = ExperimentOutcome.SUCCESS
            experiment.conclusion = f"Observed result confirms hypothesis '{experiment.hypothesis_tested}'."
        elif experiment.expected_observation_if_false.lower() in actual_observation.lower():
            experiment.status = ExperimentOutcome.FAILED
            experiment.conclusion = f"Observed result refutes hypothesis '{experiment.hypothesis_tested}'."
        else:
            experiment.status = ExperimentOutcome.INCONCLUSIVE
            experiment.conclusion = "Observed result was ambiguous or matched neither expected branch."

        return experiment.status, experiment.conclusion
