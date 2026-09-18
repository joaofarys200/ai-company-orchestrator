"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
Risk Governance & Human Review Escalation Gate.
Triggers mandatory human review on critical uncertainty or architectural irreversibility.
Enforces that review timeout yields BLOCKED instead of infinite wait.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Dict, List, Optional, Tuple


class RiskSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class RiskItem:
    risk_id: str
    description: str
    severity: RiskSeverity
    category: str
    detected_at: float = field(default_factory=time.time)
    resolved: bool = False
    mitigation_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_id": self.risk_id,
            "description": self.description,
            "severity": self.severity.value,
            "category": self.category,
            "detected_at": self.detected_at,
            "resolved": self.resolved,
            "mitigation_notes": self.mitigation_notes,
        }


class RiskGovernor:
    """
    Evaluates mission risks and enforces mandatory human review triggers.
    Enforces review timeout -> BLOCKED.
    """

    MANDATORY_REVIEW_TRIGGERS = {
        "ambiguous_behavior",
        "security_uncertainty",
        "irreversible_architecture_change",
        "objective_modification",
        "unresolved_contract_break",
        "residual_state",
        "repeated_convergence_failure",
        "unknown_dynamic_boundaries",
    }

    def __init__(self, review_timeout_sec: float = 300.0):
        self.review_timeout_sec = review_timeout_sec
        self._risks: Dict[str, RiskItem] = {}
        self._pending_reviews: Dict[str, Dict[str, Any]] = {}

    def report_risk(
        self,
        risk_id: str,
        description: str,
        severity: RiskSeverity,
        category: str,
    ) -> RiskItem:
        item = RiskItem(
            risk_id=risk_id,
            description=description,
            severity=severity,
            category=category,
        )
        self._risks[risk_id] = item
        return item

    def resolve_risk(self, risk_id: str, notes: str) -> None:
        if risk_id in self._risks:
            r = self._risks[risk_id]
            r.resolved = True
            r.mitigation_notes = notes

    def list_unresolved_risks(self) -> List[RiskItem]:
        return [r for r in self._risks.values() if not r.resolved]

    def check_mandatory_review(self, context: Dict[str, Any]) -> Tuple[bool, List[str]]:
        reasons: List[str] = []
        for trigger in self.MANDATORY_REVIEW_TRIGGERS:
            if context.get(trigger, False):
                reasons.append(trigger)

        for r in self.list_unresolved_risks():
            if r.severity == RiskSeverity.CRITICAL:
                reasons.append(f"CRITICAL_RISK_{r.risk_id}")

        requires_review = len(reasons) > 0
        return requires_review, reasons

    def create_review_ticket(self, mission_id: str, reasons: List[str]) -> str:
        ticket_id = f"rev_{mission_id}_{int(time.time()*1000)}"
        self._pending_reviews[ticket_id] = {
            "ticket_id": ticket_id,
            "mission_id": mission_id,
            "reasons": reasons,
            "created_at": time.time(),
            "status": "PENDING",
        }
        return ticket_id

    def check_review_timeout(self, ticket_id: str, simulated_current_time: Optional[float] = None) -> bool:
        ticket = self._pending_reviews.get(ticket_id)
        if not ticket:
            return False
        now = simulated_current_time or time.time()
        elapsed = now - ticket["created_at"]
        if elapsed > self.review_timeout_sec:
            ticket["status"] = "TIMEOUT_BLOCKED"
            return True
        return False
