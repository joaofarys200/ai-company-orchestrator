"""
Phase 72 — Reliability Governance Policy
Configurable thresholds, risk tolerance, and action authorizations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .models import PreventiveActionType, RiskLevel


@dataclass
class ReliabilityPolicy:
    """Policy rules governing autonomous reliability intervention."""

    max_autonomous_risk: RiskLevel = RiskLevel.MEDIUM
    allowed_autonomous_actions: List[PreventiveActionType] = field(
        default_factory=lambda: [
            PreventiveActionType.INCREASE_OBSERVATION_FREQUENCY,
            PreventiveActionType.RUN_ADDITIONAL_HEALTHCHECKS,
            PreventiveActionType.REBUILD_CACHE,
            PreventiveActionType.CREATE_CHECKPOINT,
        ]
    )
    min_samples_for_baseline: int = 5
    min_samples_for_trend: int = 4
    high_latency_threshold_ms: float = 200.0
    high_error_rate_threshold: float = 0.05
    require_human_for_rollback: bool = True
