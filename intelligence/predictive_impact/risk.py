"""
JARVIS OS — Phase 39: Deterministic Risk Model

Evaluates multi-dimensional operational risk across 9 explicit dimensions:
1. Scope (LOCAL, CROSS_FILE, CROSS_MODULE, ARCHITECTURAL, MISSION_WIDE)
2. Coupling (fan-out and number of affected files/modules)
3. Security (authentication, credentials, sentinel invariants)
4. Architecture (API contracts, protocols, framework changes)
5. State & Persistence (database schema, shared memory, state machine)
6. Evidence Invalidation (Zero False Success impact)
7. Rollback Complexity (reversibility of proposed changes)
8. Concurrent Activity (in-flight tasks, leases, running workers)
9. Economic Impact (token/compute budget expansion)
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from intelligence.predictive_impact.models import ImpactScope, RiskLevel


class DeterministicRiskModel:
    """
    Computes deterministic risk score without model hallucinations.
    Explains the exact factors contributing to the risk level.
    """

    @classmethod
    def evaluate_risk(
        cls,
        scope: str,
        predicted_files: list[dict[str, Any]],
        predicted_tasks: list[dict[str, Any]],
        predicted_evidence_impact: list[dict[str, Any]],
        directive_text: str,
        is_running: bool = False,
    ) -> Tuple[str, float, dict[str, Any], bool]:
        """
        Returns:
            - risk_level: str (LOW, MEDIUM, HIGH, CRITICAL)
            - total_score: float (0.0 to 100.0)
            - factors: dict[str, Any]
            - approval_required: bool
        """
        text_lower = directive_text.lower()
        factors: dict[str, float] = {}

        # 1. Scope Factor (0 - 30)
        scope_scores = {
            ImpactScope.NONE.value: 0.0,
            ImpactScope.LOCAL.value: 5.0,
            ImpactScope.CROSS_FILE.value: 12.0,
            ImpactScope.CROSS_MODULE.value: 20.0,
            ImpactScope.ARCHITECTURAL.value: 28.0,
            ImpactScope.MISSION_WIDE.value: 30.0,
        }
        factors["scope_score"] = scope_scores.get(scope, 10.0)

        # 2. Coupling Factor (0 - 15)
        file_count = len(predicted_files)
        factors["coupling_score"] = min(15.0, file_count * 3.0)

        # 3. Security Factor (0 - 25)
        sec_keywords = ["auth", "jwt", "password", "token", "segurança", "sentinel", "permissão", "crypto"]
        if any(k in text_lower for k in sec_keywords):
            factors["security_score"] = 22.0
        else:
            factors["security_score"] = 0.0

        # 4. Architecture Factor (0 - 15)
        arch_keywords = ["graphql", "rest", "api", "framework", "arquitetura", "protocolo", "websocket"]
        if any(k in text_lower for k in arch_keywords) or scope in (ImpactScope.ARCHITECTURAL.value, ImpactScope.MISSION_WIDE.value):
            factors["architecture_score"] = 14.0
        else:
            factors["architecture_score"] = 2.0

        # 5. State & Persistence Factor (0 - 10)
        state_keywords = ["database", "sqlite", "schema", "migração", "persistência", "tabela"]
        if any(k in text_lower for k in state_keywords):
            factors["state_score"] = 9.0
        else:
            factors["state_score"] = 1.0

        # 6. Evidence Invalidation Factor (0 - 10)
        invalidated_count = len([e for e in predicted_evidence_impact if e.get("predicted_status") in ("REQUIRES_REVALIDATION", "SUPERSEDED")])
        factors["evidence_invalidation_score"] = min(10.0, invalidated_count * 3.5)

        # 7. Rollback Complexity (0 - 10)
        if any(t.get("action") == "REMOVE_TASK" for t in predicted_tasks):
            factors["rollback_complexity_score"] = 8.0
        else:
            factors["rollback_complexity_score"] = 3.0

        # 8. Concurrent Activity (0 - 10)
        factors["concurrency_score"] = 8.0 if is_running else 1.0

        # 9. Economic / Budget expansion (0 - 5)
        if len(predicted_tasks) >= 4:
            factors["economic_score"] = 4.0
        else:
            factors["economic_score"] = 1.0

        # Sum total
        total_score = sum(factors.values())

        # Determine level & approval requirements
        if total_score >= 60.0 or factors.get("security_score", 0.0) >= 20.0:
            risk_level = RiskLevel.CRITICAL.value if total_score >= 75.0 else RiskLevel.HIGH.value
            approval_required = True
        elif total_score >= 30.0 or factors.get("architecture_score", 0.0) >= 12.0 or invalidated_count > 0:
            risk_level = RiskLevel.MEDIUM.value
            approval_required = (scope in (ImpactScope.ARCHITECTURAL.value, ImpactScope.MISSION_WIDE.value))
        else:
            risk_level = RiskLevel.LOW.value
            approval_required = False

        factors_summary = {
            "total_score": round(total_score, 2),
            "breakdown": factors,
            "justification": cls._build_justification(factors, risk_level, scope),
        }

        return risk_level, total_score, factors_summary, approval_required

    @classmethod
    def _build_justification(cls, factors: dict[str, float], risk_level: str, scope: str) -> str:
        parts = []
        if factors.get("security_score", 0.0) > 0:
            parts.append("Toca em domínio de segurança/autenticação")
        if factors.get("evidence_invalidation_score", 0.0) > 0:
            parts.append("Invalida evidências ativas exigindo revalidação (Zero False Success)")
        if factors.get("architecture_score", 0.0) > 10.0:
            parts.append("Impacto arquitetural em contratos ou serviços centrais")
        if factors.get("coupling_score", 0.0) > 8.0:
            parts.append("Acoplamento elevado com múltiplos ficheiros afetados")
        if not parts:
            parts.append(f"Alteração de escopo {scope} com baixo acoplamento e sem impacto em segurança")
        return f"Risco avaliado como {risk_level}: " + "; ".join(parts) + "."
