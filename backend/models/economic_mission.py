from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class EconomicMission:
    """Represents an economic mission goal executed by autonomous JARVIS agent swarms."""

    mission_id: str = field(default_factory=lambda: f"econ_m_{uuid.uuid4().hex[:8]}")
    objective: str = ""
    target_niche: str = ""
    budget_usd: float = 0.0
    max_runtime_hours: float = 24.0
    risk_tolerance: str = "low"  # low, medium, high
    requires_approval_for: list[str] = field(
        default_factory=lambda: [
            "financial_transaction",
            "external_account_create",
            "publish_digital_asset",
            "irreversible_action",
        ]
    )
    expected_value_usd: float = 0.0
    confidence_score: float = 0.0
    status: str = "CREATED"  # CREATED, RESEARCHING, BUILDING, TESTING, PENDING_APPROVAL, ACTIVE, COMPLETED, FAILED
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    work_packages: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(
        default_factory=lambda: {
            "total_cost_usd": 0.0,
            "runtime_seconds": 0.0,
            "leads_generated": 0,
            "conversions": 0,
            "revenue_usd": 0.0,
            "roi_pct": 0.0,
        }
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EconomicMission:
        return cls(**data)


__all__ = ["EconomicMission"]
