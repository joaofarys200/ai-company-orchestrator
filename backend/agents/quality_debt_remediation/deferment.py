"""
JARVIS OS — Phase 69: Autonomous Quality Debt Remediation
Debt deferment manager.
Maintains transparent deferment records with mandatory review conditions.
Enforces the rule: DEFERRED debts are NEVER hidden from the quality ledger.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from .models import DebtDeferment


class DebtDefermentManager:
    """
    Manages explicit technical debt deferments.
    Guarantees that deferred debts remain fully auditable and visible in the quality ledger.
    """

    def __init__(self):
        self._deferments: Dict[str, DebtDeferment] = {}

    def create_deferment(
        self,
        debt_id: str,
        reason: str,
        risk: float,
        expected_cost: float,
        revisit_condition: str,
        expiration_days: float = 30.0,
        owner: str = "LeadArchitect",
    ) -> DebtDeferment:
        deferment_id = f"def_{uuid.uuid4().hex[:8]}"
        expiration_date = time.time() + (expiration_days * 86400.0)

        deferment = DebtDeferment(
            deferment_id=deferment_id,
            debt_id=debt_id,
            reason=reason,
            risk=risk,
            expected_cost=expected_cost,
            revisit_condition=revisit_condition,
            expiration_date=expiration_date,
            owner=owner,
            timestamp=time.time(),
        )
        self._deferments[debt_id] = deferment
        return deferment

    def get_deferment(self, debt_id: str) -> Optional[DebtDeferment]:
        return self._deferments.get(debt_id)

    def list_all_deferments(self) -> List[DebtDeferment]:
        return list(self._deferments.values())

    def check_expired(self, current_time: Optional[float] = None) -> List[DebtDeferment]:
        now = current_time or time.time()
        return [d for d in self._deferments.values() if d.expiration_date <= now]
