"""
JARVIS OS — Safety & Intent Classification Engine
Classifica intenções e pedidos de desenvolvimento em:
- OFFENSIVE_CYBER: Armas cibernéticas, botnets, DDoS flooders, malware (Bloqueio estrito).
- DEFENSIVE_ENGINEERING: Mitigação, rate limiting, proteção, benchmarks locais (Permitido).
- AMBIGUOUS_DUAL_USE: Testes de stress / flooding genéricos (Restrito a laboratório local).
- BENIGN: Desenvolvimento geral de software (Permitido).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class SafetyStatus(str, Enum):
    BLOCKED = "BLOCKED / SAFETY_REFUSED"
    ALLOWED = "ALLOWED / SAFE_DEFENSIVE"
    RESTRICTED_LAB = "RESTRICTED / LOCAL_LAB_ONLY"


class IntentCategory(str, Enum):
    OFFENSIVE_CYBER = "OFFENSIVE_CYBER"
    DEFENSIVE_ENGINEERING = "DEFENSIVE_ENGINEERING"
    AMBIGUOUS_DUAL_USE = "AMBIGUOUS_DUAL_USE"
    BENIGN = "BENIGN"


@dataclass(frozen=True)
class SafetyAssessment:
    is_allowed: bool
    status: SafetyStatus
    category: IntentCategory
    policy_rule: str
    reason: str
    sanitized_intent: str
    request_id: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_allowed": self.is_allowed,
            "status": self.status.value,
            "category": self.category.value,
            "policy_rule": self.policy_rule,
            "reason": self.reason,
            "sanitized_intent": self.sanitized_intent,
            "request_id": self.request_id,
            "timestamp": self.timestamp,
        }


class SafetyRefusalError(Exception):
    """Exceção levantada quando um pedido viola a política de segurança cibernética."""

    def __init__(self, assessment: SafetyAssessment):
        super().__init__(assessment.reason)
        self.assessment = assessment


class SafetyClassifier:
    """Motor determinístico de classificação e barreira de segurança de pedidos."""

    OFFENSIVE_PATTERNS = (
        (
            r"\b(?:fazer|executar|dar|lancar|lançar|iniciar|criar|produzir|desenvolver)\s+(?:um[a]?\s+)?(?:ataque\s+)?(?:ddos|dos|flooder|syn flood|udp flood|http flood|botnet)\b",
            "SEC-POLICY-CYBER-001",
            "Solicitação explícita de desenvolvimento ou execução de ferramenta/API ofensiva de negação de serviço (DDoS/Flooding).",
        ),
        (
            r"\b(?:api|script|ferramenta|codigo|código)\s+(?:capaz\s+de|para|que)\s+(?:fazer|dar|executar)\s+ddos\b",
            "SEC-POLICY-CYBER-001",
            "Solicitação de desenvolvimento de API com capacidades ofensivas de negação de serviço (DDoS).",
        ),
        (
            r"\b(?:ransomware|keylogger|trojan|rootkit|credential harvest|exploit payload|c2 server)\b",
            "SEC-POLICY-CYBER-002",
            "Solicitação de criação de artefactos de malware, ransomware ou exfiltração não autorizada.",
        ),
    )

    DEFENSIVE_KEYWORDS = (
        "defesa", "defensivo", "proteger", "protecao", "proteção",
        "mitigacao", "mitigação", "mitigar", "rate limit", "rate limiting",
        "load shedding", "circuit breaker", "resistencia", "resistência",
        "ambiente local", "localmente", "metricas", "métricas", "telemetria",
        "hardening", "auditoria", "firewall", "waf", "anti-ddos"
    )

    AMBIGUOUS_PATTERNS = (
        r"\b(?:testar|benchmark|avaliar|stress test|load test|resistencia|resistência)\s+.*\b(?:flooding|picos|carga|stress)\b",
        r"\b(?:ferramenta|api|script)\s+para\s+testar\s+.*\b(?:flooding|ataques|resistencia)\b",
    )

    @classmethod
    def evaluate(cls, prompt_text: str, request_id: str | None = None) -> SafetyAssessment:
        clean_prompt = str(prompt_text or "").strip()
        lower_prompt = clean_prompt.lower()
        req_id = request_id or f"REQ-SEC-{uuid.uuid4().hex[:8]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Check explicit offensive patterns
        for pattern, rule, reason in cls.OFFENSIVE_PATTERNS:
            if re.search(pattern, lower_prompt):
                # Verify if there is explicit defensive/mitigation framing
                has_defensive_focus = any(kw in lower_prompt for kw in ("mitigacao", "mitigação", "rate limit", "proteger", "defesa contra", "bloquear ddos", "anti-ddos"))
                if not has_defensive_focus:
                    return SafetyAssessment(
                        is_allowed=False,
                        status=SafetyStatus.BLOCKED,
                        category=IntentCategory.OFFENSIVE_CYBER,
                        policy_rule=rule,
                        reason=reason,
                        sanitized_intent="[BLOQUEADO: Desenvolvimento de ferramentas ofensivas de negação de serviço/DDoS]",
                        request_id=req_id,
                        timestamp=now_iso,
                    )

        # 2. Check explicit defensive engineering
        is_defensive = any(kw in lower_prompt for kw in cls.DEFENSIVE_KEYWORDS)
        if is_defensive:
            return SafetyAssessment(
                is_allowed=True,
                status=SafetyStatus.ALLOWED,
                category=IntentCategory.DEFENSIVE_ENGINEERING,
                policy_rule="SEC-POLICY-DEFENSE-001",
                reason="Solicitação defensiva e de engenharia de software autorizada (rate limiting, mitigação e métricas locais).",
                sanitized_intent=clean_prompt,
                request_id=req_id,
                timestamp=now_iso,
            )

        # 3. Check ambiguous / dual-use patterns
        for pattern in cls.AMBIGUOUS_PATTERNS:
            if re.search(pattern, lower_prompt):
                return SafetyAssessment(
                    is_allowed=True,
                    status=SafetyStatus.RESTRICTED_LAB,
                    category=IntentCategory.AMBIGUOUS_DUAL_USE,
                    policy_rule="SEC-POLICY-LAB-RESTRICTED-001",
                    reason="Solicitação de teste de stress de segurança confinada estritamente ao ambiente de laboratório e sandbox local.",
                    sanitized_intent=f"[LABORATÓRIO LOCAL RESTRITO] {clean_prompt} (Sem tráfego externo; simulação em localhost)",
                    request_id=req_id,
                    timestamp=now_iso,
                )

        # 4. Standard benign development
        return SafetyAssessment(
            is_allowed=True,
            status=SafetyStatus.ALLOWED,
            category=IntentCategory.BENIGN,
            policy_rule="SEC-POLICY-GENERAL-001",
            reason="Solicitação de desenvolvimento padrão permitida.",
            sanitized_intent=clean_prompt,
            request_id=req_id,
            timestamp=now_iso,
        )
