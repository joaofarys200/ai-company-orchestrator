"""
JARVIS OS — Phase 66: Multi-Agent Engineering Coordination & Conflict Arbitration
Module: branching.py
Tracks base snapshot anchors, divergent branches, and AgentChangeSets.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .models import AgentChangeSet


class BranchManager:
    """Tracks branch divergence from base snapshots and maintains active changesets."""

    def __init__(self):
        self.changesets: Dict[str, AgentChangeSet] = {}
        self.branch_bases: Dict[str, str] = {}  # branch_id/agent_id -> base_snapshot_hash

    def register_changeset(self, cs: AgentChangeSet) -> bool:
        """Register a verified change produced by an agent with its base anchor."""
        if not cs.base_snapshot:
            return False
        self.changesets[cs.changeset_id] = cs
        self.branch_bases[cs.agent_id] = cs.base_snapshot
        return True

    def get_changeset(self, changeset_id: str) -> Optional[AgentChangeSet]:
        return self.changesets.get(changeset_id)

    def is_stale_base(self, agent_id: str, current_head_snapshot: str) -> bool:
        """Check if an agent's change branch has diverged from the latest head snapshot."""
        base = self.branch_bases.get(agent_id)
        if not base:
            return False
        return base != current_head_snapshot
