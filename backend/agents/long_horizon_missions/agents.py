"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
Agent Roster & Engineering Role Management.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional


@dataclass
class AgentMember:
    agent_id: str
    name: str
    role: str
    status: str = "IDLE"  # IDLE, BUSY, FAILED, OFFLINE
    active_task: Optional[str] = None
    completed_tasks: int = 0
    failures: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "status": self.status,
            "active_task": self.active_task,
            "completed_tasks": self.completed_tasks,
            "failures": self.failures,
        }


class AgentRosterManager:
    """Manages active engineering agents assigned to the long-horizon mission."""

    DEFAULT_ROLES = [
        ("ag_arch", "ArchitectAgent", "System Architect"),
        ("ag_coder", "CoderAgent", "Software Engineer"),
        ("ag_tester", "TesterAgent", "QA & Test Engineer"),
        ("ag_sec", "SecurityAgent", "Security Sentinel"),
        ("ag_verif", "VerificationAgent", "Continuous Verifier"),
    ]

    def __init__(self, initial_members: Optional[List[AgentMember]] = None):
        self._members: Dict[str, AgentMember] = {}
        if initial_members:
            for m in initial_members:
                self._members[m.agent_id] = m
        else:
            for aid, name, role in self.DEFAULT_ROLES:
                self._members[aid] = AgentMember(aid, name, role)

    def get_agent(self, agent_id: str) -> Optional[AgentMember]:
        return self._members.get(agent_id)

    def list_agents(self) -> List[AgentMember]:
        return list(self._members.values())

    def assign_task(self, agent_id: str, task_id: str) -> None:
        agent = self._members.get(agent_id)
        if agent:
            agent.status = "BUSY"
            agent.active_task = task_id

    def complete_task(self, agent_id: str, success: bool = True) -> None:
        agent = self._members.get(agent_id)
        if agent:
            agent.status = "IDLE"
            agent.active_task = None
            if success:
                agent.completed_tasks += 1
            else:
                agent.failures += 1

    def to_dict(self) -> Dict[str, Any]:
        return {k: v.to_dict() for k, v in self._members.items()}
