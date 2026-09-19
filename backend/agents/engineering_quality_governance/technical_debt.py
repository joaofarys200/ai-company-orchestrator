"""
JARVIS OS — Phase 68: Technical Debt Lifecycle Manager
Manages TechnicalDebtItem lifecycle across 9 categories and 8 states:
Categories:
ARCHITECTURAL, CODE, TEST, CONTRACT, BEHAVIOR, SECURITY, PERFORMANCE, DOCUMENTATION, OPERATIONAL.
States:
OPEN, ACKNOWLEDGED, PLANNED, IN_PROGRESS, RESOLVED, DEFERRED, INVALIDATED, UNKNOWN.

Core Invariant:
Never declare DEBT_RESOLVED without concrete posterior evidence.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from .models import (
    DebtCategory,
    DebtEvent,
    DebtSeverity,
    DebtStatus,
    TechnicalDebtItem,
)


class TechnicalDebtManager:
    """
    Tracks and governs technical debt items throughout their lifecycle.
    """

    def __init__(self) -> None:
        self._debt_items: Dict[str, TechnicalDebtItem] = {}
        self._events: List[DebtEvent] = []

    def create_debt_item(
        self,
        category: DebtCategory,
        affected_surface: str,
        origin_mission: str,
        evidence: List[Dict[str, Any]],
        severity: DebtSeverity = DebtSeverity.MEDIUM,
        confidence: float = 0.8,
        estimated_cost: float = 1.0,
        risk: float = 0.5,
        dependencies: Optional[List[str]] = None,
        resolution_options: Optional[List[str]] = None,
        debt_id: Optional[str] = None,
    ) -> TechnicalDebtItem:
        d_id = debt_id or f"debt_{category.value.lower()}_{uuid.uuid4().hex[:8]}"

        item = TechnicalDebtItem(
            debt_id=d_id,
            category=category,
            affected_surface=affected_surface,
            origin_mission=origin_mission,
            evidence=evidence,
            severity=severity,
            confidence=confidence,
            estimated_cost=estimated_cost,
            risk=risk,
            age=0.0,
            dependencies=dependencies or [],
            resolution_options=resolution_options or ["Refactor in next maintenance milestone"],
            status=DebtStatus.OPEN,
            recurrence_count=1,
            created_at=time.time(),
            updated_at=time.time(),
        )

        self._debt_items[d_id] = item
        self._record_event(d_id, "CREATED", {"category": category.value, "severity": severity.value})
        return item

    def record_recurrence(self, debt_id: str, new_evidence: Dict[str, Any]) -> TechnicalDebtItem:
        item = self._debt_items.get(debt_id)
        if not item:
            raise KeyError(f"Technical debt item '{debt_id}' not found.")

        item.recurrence_count += 1
        item.evidence.append(new_evidence)
        item.risk = min(1.0, item.risk + 0.1)
        item.updated_at = time.time()

        self._record_event(
            debt_id,
            "RECURRENCE_INCREMENTED",
            {"recurrence_count": item.recurrence_count, "new_risk": item.risk},
        )
        return item

    def update_status(
        self,
        debt_id: str,
        new_status: DebtStatus,
        posterior_evidence: Optional[Dict[str, Any]] = None,
    ) -> TechnicalDebtItem:
        item = self._debt_items.get(debt_id)
        if not item:
            raise KeyError(f"Technical debt item '{debt_id}' not found.")

        # Invariant check: Cannot mark RESOLVED without posterior evidence
        if new_status == DebtStatus.RESOLVED and not posterior_evidence:
            raise ValueError(
                f"Cannot transition debt item '{debt_id}' to RESOLVED without concrete posterior evidence."
            )

        old_status = item.status
        item.status = new_status
        item.updated_at = time.time()
        if posterior_evidence:
            item.evidence.append(posterior_evidence)

        self._record_event(
            debt_id,
            "STATUS_CHANGED",
            {"from": old_status.value, "to": new_status.value, "has_posterior_evidence": bool(posterior_evidence)},
        )
        return item

    def get_item(self, debt_id: str) -> Optional[TechnicalDebtItem]:
        return self._debt_items.get(debt_id)

    def list_items(
        self,
        status_filter: Optional[DebtStatus] = None,
        category_filter: Optional[DebtCategory] = None,
    ) -> List[TechnicalDebtItem]:
        items = list(self._debt_items.values())
        if status_filter:
            items = [i for i in items if i.status == status_filter]
        if category_filter:
            items = [i for i in items if i.category == category_filter]
        return items

    def list_unresolved(self) -> List[TechnicalDebtItem]:
        return [i for i in self._debt_items.values() if i.status in (DebtStatus.OPEN, DebtStatus.ACKNOWLEDGED, DebtStatus.IN_PROGRESS)]

    def list_events(self, debt_id: Optional[str] = None) -> List[DebtEvent]:
        if debt_id:
            return [e for e in self._events if e.debt_id == debt_id]
        return list(self._events)

    def _record_event(self, debt_id: str, event_type: str, details: Dict[str, Any]) -> None:
        evt = DebtEvent(
            event_id=f"evt_{uuid.uuid4().hex[:8]}",
            debt_id=debt_id,
            event_type=event_type,
            details=details,
            timestamp=time.time(),
        )
        self._events.append(evt)
