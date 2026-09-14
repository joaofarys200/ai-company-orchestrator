"""
JARVIS OS — Phase 53: Universal Project Preflight & Runtime Failure Auto-Recovery
Preflight & Post-Repair Validator: Evaluates gate clearance, post-repair health checks,
and minimal smoke behavioral proof before releasing execution.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from agents.project_preflight.models import (
    PreflightGateDecision,
    PreflightIssue,
    PreflightPolicy,
    PreflightResult,
    RepairConfidence,
    RepairPlan,
    StartupHealthResult,
)


class PreflightProofValidator:
    """
    Validates preflight outcomes, repair gates, and post-repair behavioral readiness.
    Never accepts 'process starts' as proof that 'behavior is correct'.
    """

    def evaluate_preflight_gate(
        self, preflight_result: PreflightResult, policy: PreflightPolicy
    ) -> Tuple[PreflightGateDecision, str]:
        blockers = preflight_result.blockers
        if blockers:
            return (
                PreflightGateDecision.EXECUTION_BLOCKED,
                f"Bloqueado: {len(blockers)} problemas críticos detetados no preflight: {blockers[0].message}",
            )

        warnings = preflight_result.warnings
        if warnings and policy in (PreflightPolicy.STRICT, PreflightPolicy.CRITICAL):
            return (
                PreflightGateDecision.HUMAN_REVIEW_REQUIRED,
                f"Avisos de preflight sob política {policy.value} requerem aprovação humana: {warnings[0].message}",
            )

        return (
            PreflightGateDecision.GATE_CLEARED,
            "Preflight aprovado sem bloqueios funcionais.",
        )

    def evaluate_post_repair_proof(
        self,
        repair_plan: RepairPlan,
        health_result: StartupHealthResult,
        smoke_behavior_ok: bool = True,
    ) -> Tuple[bool, str]:
        if not health_result.started:
            return False, f"Falha pós-reparação: Processo não iniciou ({health_result.failure_reason})"

        if not health_result.ready:
            return False, f"Falha pós-reparação: Endpoint de saúde não respondeu com sucesso ({health_result.failure_reason})"

        if not smoke_behavior_ok:
            return False, "Falha pós-reparação: Comportamento funcional básico (smoke behavior) não preservado."

        return True, "Reparação verificada com sucesso: processo ativo, endpoint HTTP funcional e smoke test aprovado."
