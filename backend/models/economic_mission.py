from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from backend.gateway.verification_gate import EvidenceLevel


class EconomicStage(str, Enum):
    CREATED = "CREATED"
    DISCOVERING = "DISCOVERING"
    VALIDATING = "VALIDATING"
    APPROVED = "APPROVED"
    BUILDING = "BUILDING"
    TESTING = "TESTING"
    PUBLISHED = "PUBLISHED"
    ACQUIRING = "ACQUIRING"
    MEASURING = "MEASURING"
    MONETIZED = "MONETIZED"
    ITERATING = "ITERATING"
    BENCHMARK_PASSED = "BENCHMARK_PASSED"
    PAUSED = "PAUSED"
    ABANDONED = "ABANDONED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


VALID_STAGE_TRANSITIONS: dict[EconomicStage, set[EconomicStage]] = {
    EconomicStage.CREATED: {EconomicStage.DISCOVERING, EconomicStage.PAUSED, EconomicStage.FAILED},
    EconomicStage.DISCOVERING: {EconomicStage.VALIDATING, EconomicStage.PAUSED, EconomicStage.ABANDONED, EconomicStage.FAILED},
    EconomicStage.VALIDATING: {EconomicStage.APPROVED, EconomicStage.BUILDING, EconomicStage.PAUSED, EconomicStage.ABANDONED, EconomicStage.FAILED},
    EconomicStage.APPROVED: {EconomicStage.BUILDING, EconomicStage.PAUSED, EconomicStage.ABANDONED},
    EconomicStage.BUILDING: {EconomicStage.TESTING, EconomicStage.PAUSED, EconomicStage.FAILED},
    EconomicStage.TESTING: {EconomicStage.PUBLISHED, EconomicStage.BUILDING, EconomicStage.PAUSED, EconomicStage.FAILED},
    EconomicStage.PUBLISHED: {EconomicStage.ACQUIRING, EconomicStage.PAUSED, EconomicStage.FAILED},
    EconomicStage.ACQUIRING: {EconomicStage.MEASURING, EconomicStage.PAUSED, EconomicStage.FAILED},
    EconomicStage.MEASURING: {EconomicStage.MONETIZED, EconomicStage.ITERATING, EconomicStage.BENCHMARK_PASSED, EconomicStage.PAUSED, EconomicStage.ABANDONED},
    EconomicStage.MONETIZED: {EconomicStage.ITERATING, EconomicStage.SUCCESS, EconomicStage.PAUSED},
    EconomicStage.ITERATING: {EconomicStage.SUCCESS, EconomicStage.BENCHMARK_PASSED, EconomicStage.ABANDONED, EconomicStage.BUILDING, EconomicStage.PAUSED},
    EconomicStage.BENCHMARK_PASSED: set(),
    EconomicStage.PAUSED: {EconomicStage.CREATED, EconomicStage.DISCOVERING, EconomicStage.VALIDATING, EconomicStage.BUILDING, EconomicStage.TESTING, EconomicStage.PUBLISHED, EconomicStage.ACQUIRING, EconomicStage.MEASURING, EconomicStage.ABANDONED},
    EconomicStage.ABANDONED: set(),
    EconomicStage.SUCCESS: set(),
    EconomicStage.FAILED: set(),
}


@dataclass
class EvidenceArtifact:
    """Represents verifiable evidence produced during an economic mission stage."""

    stage: str
    description: str
    artifact_ref: str
    level: EvidenceLevel = EvidenceLevel.LOCAL_REAL
    sha256: str = ""
    signature: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def compute_sha256(self, content: str | bytes) -> str:
        data = content if isinstance(content, bytes) else content.encode("utf-8")
        self.sha256 = hashlib.sha256(data).hexdigest()
        return self.sha256


@dataclass
class BoundedAutonomyPolicy:
    """Defines hard constraints and boundary gates for autonomous execution."""

    autonomy_level: str = "LEVEL_1_SUPERVISED"  # LEVEL_0_ASSISTED, LEVEL_1_SUPERVISED, LEVEL_2_BOUNDED
    max_budget_usd: float = 100.0
    max_runtime_hours: float = 24.0
    max_loss_limit_usd: float = 50.0
    allowed_domains: list[str] = field(default_factory=lambda: ["localhost", "127.0.0.1"])
    allowed_tools: list[str] = field(
        default_factory=lambda: [
            "web_search",
            "read_file",
            "write_file",
            "list_directory",
            "apply_code_patch",
            "run_unit_tests",
            "semantic_code_search",
            "capture_screen",
        ]
    )


@dataclass
class EconomicMission:
    """Represents an economic mission with a full 14-stage lifecycle and evidence validation."""

    mission_id: str = field(default_factory=lambda: f"econ_m_{uuid.uuid4().hex[:8]}")
    objective: str = ""
    target_niche: str = ""
    hypothesis: str = ""
    budget_usd: float = 0.0
    expected_value_usd: float = 0.0
    confidence_score: float = 0.0
    risk_tolerance: str = "low"  # low, medium, high
    current_stage: EconomicStage = EconomicStage.CREATED
    status: str = "CREATED"
    requires_approval_for: list[str] = field(
        default_factory=lambda: [
            "financial_transaction",
            "external_account_create",
            "publish_digital_asset",
            "irreversible_action",
        ]
    )
    stop_conditions: dict[str, Any] = field(
        default_factory=lambda: {
            "max_iterations": 10,
            "min_expected_value_usd": 10.0,
            "max_runtime_seconds": 3600,
        }
    )
    bounded_autonomy: BoundedAutonomyPolicy = field(default_factory=BoundedAutonomyPolicy)
    actions_taken: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    work_packages: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metrics: dict[str, Any] = field(
        default_factory=lambda: {
            "total_cost_usd": 0.0,
            "runtime_seconds": 0.0,
            "leads_generated": 0,
            "conversions": 0,
            "revenue_usd": 0.0,
            "verified_revenue_usd": 0.0,
            "synthetic_revenue_usd": 0.0,
            "roi_pct": 0.0,
            "cac_usd": 0.0,
            "ltv_usd": 0.0,
        }
    )

    def transition_to_stage(self, new_stage: EconomicStage) -> None:
        """Enforces legal state machine transitions and blocks illegal state jumps."""
        allowed_targets = VALID_STAGE_TRANSITIONS.get(self.current_stage, set())
        if new_stage not in allowed_targets and new_stage != self.current_stage:
            raise ValueError(
                f"Transição ilegal de estágio: não é permitido saltar de {self.current_stage.value} para {new_stage.value}."
            )
        self.current_stage = new_stage
        self.status = new_stage.value
        self.updated_at = time.time()

    def record_action(self, agent: str, action: str, tool: str, outcome: str, details: str = "") -> None:
        self.actions_taken.append({
            "timestamp": time.time(),
            "agent": agent,
            "action": action,
            "tool": tool,
            "outcome": outcome,
            "details": details,
            "stage": self.current_stage.value,
        })
        self.updated_at = time.time()

    def add_evidence(
        self,
        stage: str,
        description: str,
        artifact_ref: str,
        content: str = "",
        level: EvidenceLevel = EvidenceLevel.LOCAL_REAL,
        signature: str = "",
    ) -> EvidenceArtifact:
        ev = EvidenceArtifact(
            stage=stage,
            description=description,
            artifact_ref=artifact_ref,
            level=level,
            signature=signature,
        )
        if content:
            ev.compute_sha256(content)
        self.evidence.append(asdict(ev))
        self.updated_at = time.time()
        return ev

    def update_metrics(
        self,
        *,
        cost: float = 0.0,
        verified_revenue: float = 0.0,
        synthetic_revenue: float = 0.0,
        leads: int = 0,
        conversions: int = 0,
    ) -> None:
        self.metrics["total_cost_usd"] += cost
        self.metrics["verified_revenue_usd"] += verified_revenue
        self.metrics["synthetic_revenue_usd"] += synthetic_revenue
        self.metrics["revenue_usd"] = self.metrics["verified_revenue_usd"] + self.metrics["synthetic_revenue_usd"]
        self.metrics["leads_generated"] += leads
        self.metrics["conversions"] += conversions

        total_cost = self.metrics["total_cost_usd"]
        verified_rev = self.metrics["verified_revenue_usd"]
        if total_cost > 0:
            self.metrics["roi_pct"] = round(((verified_rev - total_cost) / total_cost) * 100.0, 2)
        else:
            self.metrics["roi_pct"] = 0.0

        if self.metrics["conversions"] > 0:
            self.metrics["cac_usd"] = round(total_cost / self.metrics["conversions"], 2)
        self.updated_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["current_stage"] = self.current_stage.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EconomicMission:
        if "current_stage" in data and isinstance(data["current_stage"], str):
            data["current_stage"] = EconomicStage(data["current_stage"])
        return cls(**data)


__all__ = [
    "EconomicStage",
    "EvidenceLevel",
    "EvidenceArtifact",
    "BoundedAutonomyPolicy",
    "EconomicMission",
    "VALID_STAGE_TRANSITIONS",
]
