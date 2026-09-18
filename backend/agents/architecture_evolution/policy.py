"""
JARVIS OS — Phase 64: Autonomous Architecture Evolution & Design Governance
Module: policy.py
Architecture evolution governance policies and threshold configurations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class ArchitecturePolicy:
    """Configurable thresholds governing autonomous architectural evolution."""
    name: str
    max_coupling_fanout: int = 8
    max_scc_size: int = 3
    allow_autonomous_approval: bool = True
    require_dual_path_on_contracts: bool = True
    mandatory_rollback_coverage: bool = True
    require_human_review_for_irreversible: bool = True
    max_migration_effort_hours: float = 40.0


POLICIES: Dict[str, ArchitecturePolicy] = {
    "CONSERVATIVE": ArchitecturePolicy(
        name="CONSERVATIVE",
        max_coupling_fanout=12,
        max_scc_size=4,
        allow_autonomous_approval=False,
        require_dual_path_on_contracts=True,
        mandatory_rollback_coverage=True,
        require_human_review_for_irreversible=True,
        max_migration_effort_hours=20.0,
    ),
    "STANDARD": ArchitecturePolicy(
        name="STANDARD",
        max_coupling_fanout=8,
        max_scc_size=3,
        allow_autonomous_approval=True,
        require_dual_path_on_contracts=True,
        mandatory_rollback_coverage=True,
        require_human_review_for_irreversible=True,
        max_migration_effort_hours=40.0,
    ),
    "STRICT": ArchitecturePolicy(
        name="STRICT",
        max_coupling_fanout=6,
        max_scc_size=2,
        allow_autonomous_approval=False,
        require_dual_path_on_contracts=True,
        mandatory_rollback_coverage=True,
        require_human_review_for_irreversible=True,
        max_migration_effort_hours=30.0,
    ),
    "SECURITY_FIRST": ArchitecturePolicy(
        name="SECURITY_FIRST",
        max_coupling_fanout=6,
        max_scc_size=2,
        allow_autonomous_approval=False,
        require_dual_path_on_contracts=True,
        mandatory_rollback_coverage=True,
        require_human_review_for_irreversible=True,
        max_migration_effort_hours=25.0,
    ),
}


class ArchitecturePolicyManager:
    """Retrieves and manages active architecture policies."""

    def __init__(self, default_policy: str = "STANDARD"):
        self.default_policy = default_policy

    def get_policy(self, name: str = "") -> ArchitecturePolicy:
        key = (name or self.default_policy).upper()
        return POLICIES.get(key, POLICIES["STANDARD"])
