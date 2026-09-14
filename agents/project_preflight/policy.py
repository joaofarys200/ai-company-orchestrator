"""
JARVIS OS — Phase 53: Universal Project Preflight & Runtime Failure Auto-Recovery
Policy Engine: Controls repair authorization gates, retry limits, and safety overrides.
"""

from __future__ import annotations

from typing import Tuple

from agents.project_preflight.models import (
    PreflightGateDecision,
    PreflightPolicy,
    RepairConfidence,
    RepairPlan,
)


class PreflightPolicyEngine:
    """
    Evaluates whether a planned repair is allowed to be automatically executed
    or must be blocked / escalated to human review.
    """

    def __init__(self) -> None:
        self.max_attempts_map = {
            PreflightPolicy.STANDARD: 3,
            PreflightPolicy.STRICT: 2,
            PreflightPolicy.CRITICAL: 1,
            PreflightPolicy.ECONOMIC_CRITICAL: 1,
            PreflightPolicy.SECURITY_CRITICAL: 1,
        }

    def get_max_recovery_attempts(self, policy: PreflightPolicy) -> int:
        return self.max_attempts_map.get(policy, 2)

    def evaluate_repair_gate(
        self,
        repair_plan: RepairPlan,
        policy: PreflightPolicy,
        attempt_number: int,
    ) -> Tuple[PreflightGateDecision, str]:
        # 1. Enforce max attempts limit
        max_attempts = self.get_max_recovery_attempts(policy)
        if attempt_number > max_attempts:
            return (
                PreflightGateDecision.EXECUTION_BLOCKED,
                f"Limite máximo de tentativas de recuperação ({max_attempts}) atingido sob política {policy.value}.",
            )

        # 2. Strict / Critical Policies demand Human Review for all mutations
        if policy in (PreflightPolicy.CRITICAL, PreflightPolicy.ECONOMIC_CRITICAL, PreflightPolicy.SECURITY_CRITICAL):
            return (
                PreflightGateDecision.HUMAN_REVIEW_REQUIRED,
                f"Política {policy.value} requer revisão e aprovação explícita antes de qualquer reparação de código.",
            )

        # 3. Low Confidence is ALWAYS BLOCKED
        if repair_plan.confidence == RepairConfidence.LOW_CONFIDENCE:
            return (
                PreflightGateDecision.EXECUTION_BLOCKED,
                "Reparação com baixa confiança de evidência (LOW_CONFIDENCE) não tem autorização para execução automática.",
            )

        # 4. Medium Confidence requires Human Review
        if repair_plan.confidence == RepairConfidence.MEDIUM_CONFIDENCE:
            return (
                PreflightGateDecision.HUMAN_REVIEW_REQUIRED,
                "Reparação com confiança moderada (MEDIUM_CONFIDENCE) requer validação humana prévia.",
            )

        # 5. High Confidence allowed under STANDARD policy
        if repair_plan.confidence == RepairConfidence.HIGH_CONFIDENCE:
            return (
                PreflightGateDecision.GATE_CLEARED,
                f"Reparação de alta confiança (HIGH_CONFIDENCE) autorizada sob política {policy.value}.",
            )

        return PreflightGateDecision.HUMAN_REVIEW_REQUIRED, "Decisão padrão de precaução."
