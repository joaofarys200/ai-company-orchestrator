"""
JARVIS OS — Mark Known Good Executor (Fase S3)
Safe suppression of benign false-positives with required human rationale, review date, and rollback.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

from security.sentinel.contracts import KnownGoodItem, ResponseActionType, SecurityResponseAction
from security.sentinel.response.executors.base import BaseActionExecutor


class MarkKnownGoodExecutor(BaseActionExecutor):
    """Executor defensivo para marcação de comportamento benigno aprovado pelo utilizador."""

    def __init__(self, known_goods_registry: Optional[Dict[str, KnownGoodItem]] = None) -> None:
        super().__init__(ResponseActionType.MARK_KNOWN_GOOD)
        self._registry = known_goods_registry if known_goods_registry is not None else {}

    def set_registry(self, registry: Dict[str, KnownGoodItem]) -> None:
        self._registry = registry

    def capture_pre_state(self, action: SecurityResponseAction) -> Dict[str, Any]:
        item_key = action.target.strip()
        already_present = item_key in self._registry
        return {
            "item_key": item_key,
            "already_known_good": already_present,
            "existing_item": self._registry[item_key].to_dict() if already_present else None,
            "captured_at": time.time(),
        }

    def pre_check(self, action: SecurityResponseAction) -> Tuple[bool, str]:
        item_key = action.target.strip()
        if not item_key:
            return False, "Target/Item key para Known-Good não pode ser vazio"

        if not action.rationale or len(action.rationale.strip()) < 5:
            return False, "Requer justificativa humana detalhada (mínimo 5 caracteres) para marcação como Known-Good"

        return True, f"Item '{item_key}' pronto para registo como Known-Good com revisão definida"

    def execute(self, action: SecurityResponseAction) -> Dict[str, Any]:
        item_key = action.target.strip()
        now = time.time()
        # Validade padrão: 30 dias para revisão (nunca ignorar para sempre sem ciclo de vida)
        expiry = now + (30 * 86400)

        item = KnownGoodItem(
            item_key=item_key,
            category="USER_APPROVED_BENIGN",
            accepted_by=action.approved_by or "human_operator",
            accepted_at=now,
            reason=action.rationale,
            previous_state=action.pre_state,
            current_state={"status": "KNOWN_GOOD", "expiry_timestamp": expiry},
        )

        self._registry[item_key] = item

        return {
            "item_key": item_key,
            "registered_at": now,
            "expiry_timestamp": expiry,
            "accepted_by": item.accepted_by,
            "status": "REGISTERED",
        }

    def verify(self, action: SecurityResponseAction) -> Tuple[bool, Dict[str, Any]]:
        item_key = action.target.strip()
        present = item_key in self._registry

        if not present:
            return False, {
                "verified": False,
                "reason": f"Item '{item_key}' não foi encontrado no registo de Known-Goods",
                "post_state": {"registered": False},
            }

        return True, {
            "verified": True,
            "reason": f"Item '{item_key}' confirmado ativo no registo Known-Goods",
            "post_state": {"registered": True, "item": self._registry[item_key].to_dict()},
        }

    def rollback(self, action: SecurityResponseAction) -> Tuple[bool, Dict[str, Any]]:
        item_key = action.target.strip()
        if item_key in self._registry:
            del self._registry[item_key]
            return True, {
                "rollback_applied": True,
                "message": f"Item '{item_key}' removido do registo de Known-Goods com sucesso",
            }

        return True, {
            "rollback_applied": True,
            "message": f"Item '{item_key}' já não constava no registo",
        }
