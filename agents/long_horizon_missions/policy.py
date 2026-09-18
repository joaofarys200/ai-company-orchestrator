"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
Mission Governance Policies & Operating Modes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class MissionGovernancePolicy:
    name: str
    require_human_review_on_objective_drift: bool = True
    checkpoint_frequency: str = "MILESTONE"
    require_all_verification_layers: bool = True
    allow_adaptive_replanning: bool = True
    max_replan_iterations: int = 50
    strict_budget_enforcement: bool = True
    human_review_timeout_sec: float = 300.0


POLICIES: Dict[str, MissionGovernancePolicy] = {
    "STRICT": MissionGovernancePolicy(
        name="STRICT",
        require_human_review_on_objective_drift=True,
        checkpoint_frequency="ALWAYS",
        require_all_verification_layers=True,
        allow_adaptive_replanning=True,
        max_replan_iterations=20,
        strict_budget_enforcement=True,
        human_review_timeout_sec=180.0,
    ),
    "GOVERNED": MissionGovernancePolicy(
        name="GOVERNED",
        require_human_review_on_objective_drift=True,
        checkpoint_frequency="MILESTONE",
        require_all_verification_layers=True,
        allow_adaptive_replanning=True,
        max_replan_iterations=50,
        strict_budget_enforcement=True,
        human_review_timeout_sec=300.0,
    ),
    "ADAPTIVE": MissionGovernancePolicy(
        name="ADAPTIVE",
        require_human_review_on_objective_drift=True,
        checkpoint_frequency="MILESTONE",
        require_all_verification_layers=False,
        allow_adaptive_replanning=True,
        max_replan_iterations=100,
        strict_budget_enforcement=True,
        human_review_timeout_sec=600.0,
    ),
    "LENIENT": MissionGovernancePolicy(
        name="LENIENT",
        require_human_review_on_objective_drift=False,
        checkpoint_frequency="ON_COMPLETION",
        require_all_verification_layers=False,
        allow_adaptive_replanning=True,
        max_replan_iterations=200,
        strict_budget_enforcement=False,
        human_review_timeout_sec=1800.0,
    ),
}


def get_policy(name: str) -> MissionGovernancePolicy:
    return POLICIES.get(name.upper(), POLICIES["GOVERNED"])
