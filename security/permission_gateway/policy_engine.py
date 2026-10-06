"""
JARVIS OS — Permission Gateway Policy Engine
Enforces existing Sentinel S3 and Workspace Policy invariants.
Maintains strict distinction between READ_ONLY, LOW_RISK_MUTATION,
HIGH_RISK_MUTATION, and CRITICAL_MUTATION.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Tuple

from security.permission_gateway.models import (
    PermissionRequest,
    PermissionRiskLevel,
    PermissionRequestStatus,
)
from workspace_policy import COMMAND_BLOCKLIST


class PolicyDecision:
    def __init__(
        self,
        is_eligible_for_human_approval: bool,
        is_auto_permitted: bool,
        is_blocked_by_policy: bool,
        reason: str,
        initial_status: PermissionRequestStatus,
    ):
        self.is_eligible_for_human_approval = is_eligible_for_human_approval
        self.is_auto_permitted = is_auto_permitted
        self.is_blocked_by_policy = is_blocked_by_policy
        self.reason = reason
        self.initial_status = initial_status

    @property
    def requires_human_approval(self) -> bool:
        return self.is_eligible_for_human_approval and not self.is_auto_permitted and not self.is_blocked_by_policy

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_eligible_for_human_approval": self.is_eligible_for_human_approval,
            "is_auto_permitted": self.is_auto_permitted,
            "is_blocked_by_policy": self.is_blocked_by_policy,
            "reason": self.reason,
            "initial_status": self.initial_status.value,
        }


class PermissionPolicyEngine:
    """
    Avalia a elegibilidade de pedidos de permissão sem enfraquecer as políticas existentes.
    """

    POLICY_BLOCKED_EXPLANATION = "Esta operação está bloqueada pela política de segurança atual."

    # Ferramentas ou operações explicitamente autorizadas para solicitar aprovação humana
    AUTHORIZED_HIGH_RISK_TOOLS = {
        "nmap",
        "npcap",
        "arp-scan",
        "ffmpeg",
        "ocr",
        "tesseract",
        "node-gyp",
        "build-tools",
    }

    @classmethod
    def is_command_blocklisted(cls, command: str) -> bool:
        cmd_lower = command.strip().lower()
        if re.search(r"\|\s*(sh|bash|powershell|cmd)\b", cmd_lower) or re.search(r"/dev/tcp/", cmd_lower):
            return True
        for pattern, _ in COMMAND_BLOCKLIST:
            if re.search(pattern, cmd_lower):
                return True
        return False

    @classmethod
    def evaluate(cls, request: PermissionRequest) -> PolicyDecision:
        risk = request.risk_level
        operation = request.requested_operation.strip().lower()

        # 1. Inspeção estrita contra lista negra de comandos destrutivos
        for pattern, block_reason in COMMAND_BLOCKLIST:
            if re.search(pattern, operation):
                return PolicyDecision(
                    is_eligible_for_human_approval=False,
                    is_auto_permitted=False,
                    is_blocked_by_policy=True,
                    reason=f"{cls.POLICY_BLOCKED_EXPLANATION} Violação: {block_reason}.",
                    initial_status=PermissionRequestStatus.BLOCKED_BY_POLICY,
                )

        # 2. CRITICAL_MUTATION é SEMPRE estritamente bloqueado pela política Sentinel
        if risk == PermissionRiskLevel.CRITICAL_MUTATION.value:
            return PolicyDecision(
                is_eligible_for_human_approval=False,
                is_auto_permitted=False,
                is_blocked_by_policy=True,
                reason=f"{cls.POLICY_BLOCKED_EXPLANATION} Mutações críticas destrutivas não são permitidas.",
                initial_status=PermissionRequestStatus.BLOCKED_BY_POLICY,
            )

        # 3. READ_ONLY pode executar sem aprovação quando permitido pela política
        if risk == PermissionRiskLevel.READ_ONLY.value:
            return PolicyDecision(
                is_eligible_for_human_approval=False,
                is_auto_permitted=True,
                is_blocked_by_policy=False,
                reason="Operação de leitura segura permitida automaticamente.",
                initial_status=PermissionRequestStatus.AVAILABLE,
            )

        # 4. LOW_RISK_MUTATION é elegível para aprovação humana
        if risk == PermissionRiskLevel.LOW_RISK_MUTATION.value:
            return PolicyDecision(
                is_eligible_for_human_approval=True,
                is_auto_permitted=False,
                is_blocked_by_policy=False,
                reason="Mutação de baixo risco elegível para autorização humana just-in-time.",
                initial_status=PermissionRequestStatus.WAITING_FOR_USER,
            )

        # 5. HIGH_RISK_MUTATION não se transforma automaticamente em permitido
        if risk == PermissionRiskLevel.HIGH_RISK_MUTATION.value:
            tool_normalized = request.tool_name.strip().lower()
            if tool_normalized in cls.AUTHORIZED_HIGH_RISK_TOOLS:
                return PolicyDecision(
                    is_eligible_for_human_approval=True,
                    is_auto_permitted=False,
                    is_blocked_by_policy=False,
                    reason="Mutação de alto risco controlada; requer autorização explícita do utilizador.",
                    initial_status=PermissionRequestStatus.WAITING_FOR_USER,
                )
            else:
                return PolicyDecision(
                    is_eligible_for_human_approval=False,
                    is_auto_permitted=False,
                    is_blocked_by_policy=True,
                    reason=f"{cls.POLICY_BLOCKED_EXPLANATION} Ferramenta '{request.tool_name}' não catalogada para elevação.",
                    initial_status=PermissionRequestStatus.BLOCKED_BY_POLICY,
                )

        # Caso não identificado: falha fechada (fail-closed)
        return PolicyDecision(
            is_eligible_for_human_approval=False,
            is_auto_permitted=False,
            is_blocked_by_policy=True,
            reason=f"{cls.POLICY_BLOCKED_EXPLANATION} Nível de risco desconhecido '{risk}'.",
            initial_status=PermissionRequestStatus.BLOCKED_BY_POLICY,
        )
