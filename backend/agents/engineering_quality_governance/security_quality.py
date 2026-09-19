"""
JARVIS OS — Phase 68: Security Quality Evaluator
Integrates all Sentinel security layers (Sandboxing, Path Jail, Secret Redaction,
Privileged Operation Auditing, Supply Chain Integrity).

Measures:
- blocked operations
- secret exposure attempts
- privileged changes
- protected path changes
- unsafe dependency changes
- sandbox violations
- security review backlog

Hard Invariant:
Any critical security regression must produce:
SECURITY_QUALITY_GATE = BLOCKED
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .models import (
    DimensionChange,
    DimensionEvaluation,
    DimensionStatus,
    ObservationType,
    QualityDimension,
    QualityObservation,
)


class SecurityQualityEvaluator:
    """
    Evaluates security posture, sentinel telemetry, and vulnerability attempts.
    """

    def __init__(self) -> None:
        pass

    def evaluate(
        self,
        context: Optional[Dict[str, Any]] = None,
        scope: str = "global",
    ) -> DimensionEvaluation:
        ctx = context or {}
        sec_data = ctx.get("security", {})

        blocked_ops = int(sec_data.get("blocked_operations", 0))
        secret_attempts = int(sec_data.get("secret_exposure_attempts", 0))
        priv_changes = int(sec_data.get("privileged_changes", 0))
        prot_path_changes = int(sec_data.get("protected_path_changes", 0))
        unsafe_deps = int(sec_data.get("unsafe_dependency_changes", 0))
        sandbox_violations = int(sec_data.get("sandbox_violations", 0))
        review_backlog = int(sec_data.get("security_review_backlog", 0))

        observations = [
            QualityObservation(
                dimension=QualityDimension.SECURITY,
                metric_name="blocked_operations",
                measured_value=blocked_ops,
                evidence={"sentinel_blocked_operations": blocked_ops},
                uncertainty=0.001,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.SECURITY,
                metric_name="secret_exposure_attempts",
                measured_value=secret_attempts,
                evidence={"secret_attempts_caught": secret_attempts},
                uncertainty=0.001,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.SECURITY,
                metric_name="privileged_changes",
                measured_value=priv_changes,
                evidence={"unvetted_privileged_changes": priv_changes},
                uncertainty=0.005,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.SECURITY,
                metric_name="protected_path_changes",
                measured_value=prot_path_changes,
                evidence={"protected_path_mutations": prot_path_changes},
                uncertainty=0.001,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.SECURITY,
                metric_name="unsafe_dependency_changes",
                measured_value=unsafe_deps,
                evidence={"unvetted_or_cve_dependencies": unsafe_deps},
                uncertainty=0.01,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.SECURITY,
                metric_name="sandbox_violations",
                measured_value=sandbox_violations,
                evidence={"container_jail_escapes_or_violations": sandbox_violations},
                uncertainty=0.001,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
            QualityObservation(
                dimension=QualityDimension.SECURITY,
                metric_name="security_review_backlog",
                measured_value=review_backlog,
                evidence={"pending_security_reviews": review_backlog},
                uncertainty=0.01,
                scope=scope,
                observation_type=ObservationType.OBSERVED,
            ),
        ]

        # Invariant: Any critical security regression yields BLOCKED
        is_blocked = (
            secret_attempts > 0
            or sandbox_violations > 0
            or prot_path_changes > 0
            or unsafe_deps > 0
        )
        is_degraded = blocked_ops > 2 or priv_changes > 0 or review_backlog > 3

        status = DimensionStatus.BLOCKED if is_blocked else (
            DimensionStatus.DEGRADED if is_degraded else DimensionStatus.HEALTHY
        )

        summary = (
            f"Security status {status.value}: secret_attempts={secret_attempts}, "
            f"sandbox_violations={sandbox_violations}, blocked_ops={blocked_ops}, "
            f"protected_path_changes={prot_path_changes}, unsafe_deps={unsafe_deps}"
        )

        return DimensionEvaluation(
            dimension=QualityDimension.SECURITY,
            observations=observations,
            evidence=[{
                "evaluator": "SecurityQualityEvaluator",
                "blocked_ops": blocked_ops,
                "secret_attempts": secret_attempts,
                "sandbox_violations": sandbox_violations,
            }],
            uncertainty=0.01,
            scope=scope,
            status=status,
            summary=summary,
        )

    def compare_security(
        self,
        baseline_eval: DimensionEvaluation,
        after_eval: DimensionEvaluation,
    ) -> Tuple[DimensionChange, bool, List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Returns (change, is_critical_security_blocked, degradations, improvements).
        """
        base_obs = {o.metric_name: o.measured_value for o in baseline_eval.observations}
        after_obs = {o.metric_name: o.measured_value for o in after_eval.observations}

        degradations = []
        improvements = []
        is_critical_blocked = False

        for metric in ["secret_exposure_attempts", "sandbox_violations", "protected_path_changes", "unsafe_dependency_changes"]:
            b_v = int(base_obs.get(metric, 0))
            a_v = int(after_obs.get(metric, 0))
            if a_v > b_v or a_v > 0:
                is_critical_blocked = True
                degradations.append({
                    "metric": metric,
                    "from": b_v,
                    "to": a_v,
                    "reason": f"Critical security degradation on {metric}",
                    "severity": "CRITICAL",
                })
            elif a_v < b_v and a_v == 0:
                improvements.append({
                    "metric": metric,
                    "from": b_v,
                    "to": a_v,
                    "reason": f"Security violation on {metric} resolved",
                })

        b_b = int(base_obs.get("blocked_operations", 0))
        a_b = int(after_obs.get("blocked_operations", 0))
        if a_b > b_b:
            degradations.append({"metric": "blocked_operations", "from": b_b, "to": a_b, "reason": "more operations blocked by sentinel"})

        if is_critical_blocked or (degradations and not improvements):
            change = DimensionChange.DEGRADED
        elif improvements and not degradations:
            change = DimensionChange.IMPROVED
        elif degradations and improvements:
            change = DimensionChange.DEGRADED if is_critical_blocked else DimensionChange.UNCERTAIN
        else:
            change = DimensionChange.UNCHANGED

        return change, is_critical_blocked, degradations, improvements
