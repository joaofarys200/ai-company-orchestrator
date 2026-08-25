"""
JARVIS OS — Base Action Executor Interface (Fase S3)
Defensive execution foundation: pre-check, execution, verification, and rollback.
"""

from __future__ import annotations

import abc
from typing import Any, Dict, Tuple

from security.sentinel.contracts import ResponseActionType, SecurityResponseAction


class BaseActionExecutor(abc.ABC):
    """Interface abstrata para executores de ações de resposta de segurança."""

    def __init__(self, action_type: ResponseActionType) -> None:
        self.action_type = action_type

    @abc.abstractmethod
    def capture_pre_state(self, action: SecurityResponseAction) -> Dict[str, Any]:
        """Captura o estado do alvo antes de qualquer modificação."""
        pass

    @abc.abstractmethod
    def pre_check(self, action: SecurityResponseAction) -> Tuple[bool, str]:
        """Valida se a ação é segura e viável (ex: processo ainda existe, não é processo crítico do SO)."""
        pass

    @abc.abstractmethod
    def execute(self, action: SecurityResponseAction) -> Dict[str, Any]:
        """Executa a mutação no sistema com privilégio mínimo e isolamento."""
        pass

    @abc.abstractmethod
    def verify(self, action: SecurityResponseAction) -> Tuple[bool, Dict[str, Any]]:
        """Verifica empiricamente se o pós-estado reflete o resultado esperado (não confia só em exit code 0)."""
        pass

    @abc.abstractmethod
    def rollback(self, action: SecurityResponseAction) -> Tuple[bool, Dict[str, Any]]:
        """Reverte a alteração para o estado anterior, se tecnicamente suportado."""
        pass
