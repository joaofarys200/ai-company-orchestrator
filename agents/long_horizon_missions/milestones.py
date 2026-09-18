"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
Milestones Execution Manager & Verifiable State Enforcement.
Strict Invariant: Never allow M1 PASS -> M2 ASSUMED PASS without verified evidence.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.agents.long_horizon_missions.models import (
    Milestone,
    MilestoneState,
)


class UnverifiedMilestoneError(Exception):
    """Raised when an attempt is made to mark a milestone completed without required evidence."""
    pass


class MilestoneManager:
    """
    Manages milestone lifecycles and enforces that each milestone ends in a verified state.
    """

    def __init__(self, milestones: Optional[Dict[str, Milestone]] = None):
        self.milestones: Dict[str, Milestone] = milestones or {}
        self.completed_milestones: Set[str] = {
            m_id for m_id, m in self.milestones.items() if m.status == MilestoneState.COMPLETED
        }
        self.failed_milestones: Set[str] = {
            m_id for m_id, m in self.milestones.items() if m.status == MilestoneState.FAILED
        }

    def register_milestones(self, milestones: List[Milestone]) -> None:
        for m in milestones:
            self.milestones[m.milestone_id] = m
            if m.status == MilestoneState.COMPLETED:
                self.completed_milestones.add(m.milestone_id)

    def start_milestone(self, milestone_id: str) -> Milestone:
        m = self._get(milestone_id)
        # Verify dependencies are completed
        unmet = [dep for dep in m.dependencies if dep not in self.completed_milestones]
        if unmet:
            raise ValueError(
                f"Cannot start milestone '{milestone_id}': dependencies not completed: {unmet}"
            )
        m.status = MilestoneState.RUNNING
        m.started_at = time.time()
        return m

    def complete_milestone(
        self,
        milestone_id: str,
        outputs: List[str],
        evidence_ids: List[str],
        verified: bool = True,
    ) -> Milestone:
        """
        Marks a milestone as COMPLETED.
        Strict invariant: M1 PASS -> M2 ASSUMED PASS is strictly forbidden.
        Evidence IDs and explicit verification are mandatory.
        """
        m = self._get(milestone_id)
        if not verified:
            m.status = MilestoneState.FAILED
            m.error_message = f"Milestone '{milestone_id}' verification failed"
            self.failed_milestones.add(milestone_id)
            raise UnverifiedMilestoneError(
                f"Cannot complete milestone '{milestone_id}' without verified verification evidence!"
            )

        if m.verification_requirements and not evidence_ids:
            m.status = MilestoneState.FAILED
            m.error_message = f"Milestone '{milestone_id}' missing required evidence"
            self.failed_milestones.add(milestone_id)
            raise UnverifiedMilestoneError(
                f"Zero False Success: Milestone '{milestone_id}' has verification requirements "
                f"{m.verification_requirements} but provided zero evidence_ids."
            )

        m.actual_outputs = list(outputs)
        m.evidence_ids = list(evidence_ids)
        m.status = MilestoneState.COMPLETED
        m.completed_at = time.time()
        self.completed_milestones.add(milestone_id)
        if milestone_id in self.failed_milestones:
            self.failed_milestones.remove(milestone_id)
        return m

    def fail_milestone(self, milestone_id: str, error_message: str) -> Milestone:
        m = self._get(milestone_id)
        m.status = MilestoneState.FAILED
        m.error_message = error_message
        m.completed_at = time.time()
        self.failed_milestones.add(milestone_id)
        return m

    def rollback_milestone(self, milestone_id: str) -> Milestone:
        m = self._get(milestone_id)
        m.status = MilestoneState.ROLLED_BACK
        if milestone_id in self.completed_milestones:
            self.completed_milestones.remove(milestone_id)
        return m

    def get_progress(self) -> Dict[str, Any]:
        total = len(self.milestones)
        completed = len(self.completed_milestones)
        failed = len(self.failed_milestones)
        pct = (completed / max(1, total)) * 100.0
        return {
            "total_milestones": total,
            "completed_milestones": completed,
            "failed_milestones": failed,
            "completion_percentage": round(pct, 2),
        }

    def _get(self, milestone_id: str) -> Milestone:
        if milestone_id not in self.milestones:
            raise KeyError(f"Milestone '{milestone_id}' not found in registry")
        return self.milestones[milestone_id]
