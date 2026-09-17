"""
JARVIS OS — Phase 57: Mission Quality, Security & Economic Gates
Enforces safety gates at preflight, execution, security, economic, and completion boundaries.
"""

from __future__ import annotations

from typing import Any

from .completion import MissionCompletionEvaluator
from .models import (
    AutonomousMission,
    CompletionDecision,
    EconomicPolicy,
    MissionHumanReviewReason,
    MissionState,
)


class GateVerdict:
    PASSED = "PASSED"
    BLOCKED = "BLOCKED"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class MissionSafetyGate:
    """Enforces multi-layer safety invariants before and during execution."""

    @classmethod
    def evaluate_preflight_gate(cls, mission: AutonomousMission) -> tuple[str, str | None]:
        # Check basic invariants
        if not mission.objective or len(mission.objective.strip()) < 3:
            return GateVerdict.BLOCKED, "Objetivo da missão inválido ou vazio"
        if not mission.requirements:
            return GateVerdict.BLOCKED, "Missão sem requisitos formulados"
        if not mission.acceptance_criteria:
            return GateVerdict.BLOCKED, "Missão sem critérios de aceitação observáveis"
        return GateVerdict.PASSED, None

    @classmethod
    def evaluate_security_gate(cls, mission: AutonomousMission) -> tuple[str, str | None]:
        # Security Sentinel sovereign check
        for failure in mission.failures:
            if failure.get("category") == "SECURITY" and not failure.get("resolved", False):
                return GateVerdict.BLOCKED, f"Violação de segurança ativa: {failure.get('description')}"
        return GateVerdict.PASSED, None

    @classmethod
    def evaluate_economic_gate(cls, mission: AutonomousMission) -> tuple[str, str | None]:
        policy = mission.economic_policy
        if not policy:
            # Non-economic mission passes automatically
            return GateVerdict.PASSED, None

        if not policy.authorization:
            return GateVerdict.BLOCKED, "Missão económica sem autorização formal concedida"
        if policy.amount < 0.0:
            return GateVerdict.BLOCKED, "Montante financeiro não pode ser negativo"
        if not policy.currency or len(policy.currency) < 3:
            return GateVerdict.BLOCKED, "Moeda inválida na política económica"
        if not policy.ledger:
            return GateVerdict.BLOCKED, "Livro-razão económico não especificado"
        if not policy.idempotency_key:
            return GateVerdict.BLOCKED, "Chave de idempotência ausente"
        if not policy.rollback_supported:
            return GateVerdict.HUMAN_REVIEW, "Transação económica sem garantia de reversibilidade/rollback"

        return GateVerdict.PASSED, None

    @classmethod
    def evaluate_completion_gate(cls, mission: AutonomousMission) -> tuple[CompletionDecision, dict[str, Any]]:
        return MissionCompletionEvaluator.evaluate(mission)
