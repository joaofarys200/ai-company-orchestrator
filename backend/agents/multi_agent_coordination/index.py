"""
JARVIS OS — Phase 66: Multi-Agent Engineering Coordination & Conflict Arbitration
Module: index.py
In-memory registry and query index for active agents, intents, and resource claims.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set


class CoordinationIndex:
    """Provides rapid indexing and reverse lookups for agents, intents, and claimed resources."""

    def __init__(self):
        self.intents_by_agent: Dict[str, Set[str]] = {}
        self.claims_by_resource: Dict[str, Set[str]] = {}
        self.active_agents: Set[str] = set()

    def index_intent(self, agent_id: str, intent_id: str, resources: List[str]):
        self.active_agents.add(agent_id)
        if agent_id not in self.intents_by_agent:
            self.intents_by_agent[agent_id] = set()
        self.intents_by_agent[agent_id].add(intent_id)

        for r in resources:
            norm_r = r.replace("\\", "/").strip()
            if norm_r not in self.claims_by_resource:
                self.claims_by_resource[norm_r] = set()
            self.claims_by_resource[norm_r].add(intent_id)

    def remove_intent(self, agent_id: str, intent_id: str, resources: List[str]):
        if agent_id in self.intents_by_agent:
            self.intents_by_agent[agent_id].discard(intent_id)
        for r in resources:
            norm_r = r.replace("\\", "/").strip()
            if norm_r in self.claims_by_resource:
                self.claims_by_resource[norm_r].discard(intent_id)

    def get_intents_for_resource(self, resource_id: str) -> List[str]:
        norm = resource_id.replace("\\", "/").strip()
        return sorted(list(self.claims_by_resource.get(norm, set())))
