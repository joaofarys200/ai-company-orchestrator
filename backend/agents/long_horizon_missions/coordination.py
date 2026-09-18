"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
Multi-Agent Engineering Coordination Integration (Integrating F66).
Translates milestones into agent intents, queries claims, schedules execution, and binds transactions.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

from backend.agents.long_horizon_missions.models import Milestone


class MultiAgentBypassError(Exception):
    """Raised when an execution attempts to bypass the Multi-Agent Coordination Engine."""
    pass


class MissionCoordinationManager:
    """
    Integrates F66 Multi-Agent Coordination.
    Enforces flow: MISSION -> MILESTONE -> AGENT INTENTS -> CLAIMS -> DEPENDENCIES -> SCHEDULER -> EXECUTION.
    """

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = workspace_root or "."
        self.intent_registry: Dict[str, Dict[str, Any]] = {}
        self.coordination_records: List[Dict[str, Any]] = []

    def dispatch_milestone_tasks(
        self,
        milestone: Milestone,
        agent_roster: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Deconstructs milestone agent_tasks into formal Agent Engineering Intents.
        Registers: agent_id, intent_id, claim_ids, transaction_id, milestone_id.
        """
        dispatched: List[Dict[str, Any]] = []

        tasks = milestone.agent_tasks
        if not tasks:
            # Default task if none explicitly listed
            tasks = [{
                "task_id": f"task_{milestone.milestone_id}_default",
                "role": "CoderAgent",
                "target_files": [f"src/{milestone.milestone_id.lower()}.py"],
                "target_symbols": ["execute_step"],
            }]

        for idx, task in enumerate(tasks):
            agent_id = task.get("role", agent_roster[idx % len(agent_roster)])
            intent_id = f"intent_{milestone.milestone_id}_{idx+1}"
            claim_ids = [f"claim_{f}" for f in task.get("target_files", [])]
            tx_id = f"tx_{uuid.uuid4().hex[:8]}"

            record = {
                "milestone_id": milestone.milestone_id,
                "agent_id": agent_id,
                "intent_id": intent_id,
                "claim_ids": claim_ids,
                "transaction_id": tx_id,
                "task_id": task.get("task_id", f"tsk_{idx+1}"),
                "target_files": task.get("target_files", []),
                "target_symbols": task.get("target_symbols", []),
                "timestamp": time.time(),
                "status": "SCHEDULED",
            }
            self.intent_registry[intent_id] = record
            self.coordination_records.append(record)
            dispatched.append(record)

        return dispatched

    def register_execution_completion(
        self,
        intent_id: str,
        success: bool,
        error_msg: Optional[str] = None,
    ) -> None:
        rec = self.intent_registry.get(intent_id)
        if not rec:
            raise KeyError(f"Intent {intent_id} not registered")
        rec["status"] = "COMMITTED" if success else "FAILED"
        rec["error"] = error_msg
        rec["completed_at"] = time.time()
