"""
JARVIS OS — Phase 57: Experience Memory Integration
Connects Phase 42 (Experience Memory) & Phase 43 (Cross-Mission Generalization).
Retrieves relevant prior mission lessons, records runtime events, and stores post-completion experience.
Axiom: Memory is advisory and never possesses veto or overriding authority over current facts.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from .models import AutonomousMission


class MissionExperienceMemory:
    """Manages advisory experience memory and cross-mission generalization."""

    _memory_store: list[dict[str, Any]] = []

    @classmethod
    def retrieve_experience(cls, objective: str, domain: str) -> list[dict[str, Any]]:
        """Retrieves prior mission experiences matching domain or objective keywords."""
        matches = []
        lower_obj = objective.lower()
        for item in cls._memory_store:
            if item.get("domain") == domain or any(w in item.get("objective", "").lower() for w in lower_obj.split()):
                matches.append(item)
        return matches[:3]

    @classmethod
    def store_mission_experience(cls, mission: AutonomousMission) -> dict[str, Any]:
        """Persists mission outcome, repair lessons, and proof metadata for future transfer."""
        exp_id = f"exp_{uuid.uuid4().hex[:6]}"
        now = time.time()
        domain = mission.provenance.get("domain", "general_engineering")

        entry = {
            "experience_id": exp_id,
            "mission_id": mission.mission_id,
            "objective": mission.objective,
            "domain": domain,
            "tasks_count": len(mission.plan.get("tasks", [])),
            "repairs_count": len(mission.repairs),
            "final_decision": mission.final_decision.value if mission.final_decision else "UNKNOWN",
            "proof_id": mission.proof.proof_id if mission.proof else None,
            "timestamp": now,
            "lessons": [
                f"Domínio '{domain}' validado com {len(mission.evidence_set.evidences)} evidências",
                f"Score de risco final: {mission.risk:.3f}",
            ],
        }

        cls._memory_store.append(entry)
        mission.metadata["stored_experience_id"] = exp_id
        return entry
