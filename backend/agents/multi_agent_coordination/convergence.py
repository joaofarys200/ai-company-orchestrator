"""
JARVIS OS — Phase 66: Multi-Agent Engineering Coordination & Conflict Arbitration
Module: convergence.py
ConvergenceGovernor integrating F56 to monitor convergence trajectories and enforce
rigorous execution budgets across multi-agent coordination waves.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from .models import ConvergenceState


class ConvergenceGovernor:
    """Enforces execution and retry budgets to prevent unbounded multi-agent loops."""

    def __init__(
        self,
        max_active_agents: int = 32,
        max_parallel_waves: int = 10,
        max_conflict_retries: int = 3,
        max_rebases: int = 3,
        max_merge_attempts: int = 3,
        max_deadlock_resolutions: int = 2,
        max_wall_time_sec: float = 300.0,
    ):
        self.max_active_agents = max_active_agents
        self.max_parallel_waves = max_parallel_waves
        self.max_conflict_retries = max_conflict_retries
        self.max_rebases = max_rebases
        self.max_merge_attempts = max_merge_attempts
        self.max_deadlock_resolutions = max_deadlock_resolutions
        self.max_wall_time_sec = max_wall_time_sec

        self.retries_by_intent: Dict[str, int] = {}
        self.rebases_by_agent: Dict[str, int] = {}
        self.history_conflicts_remaining: List[int] = []
        self.current_retries: int = 0
        self.start_time = time.time()

    def record_wave(
        self,
        conflicts_remaining: int = 0,
        conflicts_count: Optional[int] = None,
    ) -> Tuple[ConvergenceState, str]:
        """Track convergence trajectory after a scheduling/arbitration wave."""
        rem = conflicts_count if conflicts_count is not None else conflicts_remaining
        if self.current_retries > self.max_conflict_retries:
            return ConvergenceState.BLOCKED, f"MAX_RETRIES_EXCEEDED: Reached conflict retry limit of {self.max_conflict_retries}."

        now = time.time()
        if now - self.start_time > self.max_wall_time_sec:
            return ConvergenceState.BLOCKED, f"WALL_TIME_EXCEEDED: Coordination surpassed {self.max_wall_time_sec}s."

        self.history_conflicts_remaining.append(rem)
        waves_count = len(self.history_conflicts_remaining)

        if waves_count > self.max_parallel_waves:
            return ConvergenceState.BLOCKED, f"MAX_WAVES_EXCEEDED: Reached wave limit of {self.max_parallel_waves}."

        if conflicts_remaining == 0:
            return ConvergenceState.STABLE, "CONVERGENCE_REACHED: All intents scheduled without remaining conflicts."

        if len(self.history_conflicts_remaining) >= 3:
            recent = self.history_conflicts_remaining[-3:]
            if recent[0] == recent[1] == recent[2]:
                return ConvergenceState.STALLED, "COORDINATION_STALLED: Conflict count unchanged over 3 consecutive waves."
            if recent[2] > recent[1] > recent[0]:
                return ConvergenceState.DIVERGING, "COORDINATION_DIVERGING: Conflict count increasing across waves."
            if recent[0] == recent[2] and recent[1] != recent[0]:
                return ConvergenceState.OSCILLATING, "COORDINATION_OSCILLATING: Alternating conflict oscillations detected."

        return ConvergenceState.CONVERGING, f"CONVERGING: {conflicts_remaining} conflicts remaining."

    def record_retry(self, intent_id: str) -> bool:
        cnt = self.retries_by_intent.get(intent_id, 0) + 1
        self.retries_by_intent[intent_id] = cnt
        return cnt <= self.max_conflict_retries

    def record_rebase(self, agent_id: str) -> bool:
        cnt = self.rebases_by_agent.get(agent_id, 0) + 1
        self.rebases_by_agent[agent_id] = cnt
        return cnt <= self.max_rebases
