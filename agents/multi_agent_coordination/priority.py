"""
JARVIS OS — Phase 66: Multi-Agent Engineering Coordination & Conflict Arbitration
Module: priority.py
Evaluates multi-dimensional priority vectors across mission criticality,
risk, contract impact, architecture impact, urgency, reversibility, and verification burden.
Never relies on a naive single scalar score.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .models import AgentEngineeringIntent


class AgentPriorityModel:
    """Computes multidimensional priority vectors and explainable rankings."""

    def compute_priority_vector(self, intent: AgentEngineeringIntent) -> Dict[str, Any]:
        """Produce an explainable vector of priority factors."""
        if isinstance(intent.priority, (int, float)):
            criticality = float(intent.priority)
            urgency = 1.0
        elif isinstance(intent.priority, dict):
            criticality = float(intent.priority.get("mission_criticality", 1.0))
            urgency = float(intent.priority.get("urgency", 1.0))
        else:
            criticality = 1.0
            urgency = 1.0

        # Risk factor: Higher risk penalizes immediate un-arbitrated precedence
        risk_score = 1.0 if intent.risk == "LOW" else (2.0 if intent.risk == "MEDIUM" else 3.0)

        # Architectural impact: broad file scope requires higher verification weight
        scope_count = len(intent.requested_files) + len(intent.requested_symbols) + len(intent.requested_contracts)
        scope_impact = min(5.0, max(1.0, scope_count / 2.0))

        # Reversibility estimate: fewer files/contracts are easier to revert
        reversibility = max(0.2, 1.0 - (len(intent.requested_contracts) * 0.2))

        # Verification burden estimate
        verification_burden = 1.0 + (scope_count * 0.5)

        vector = [
            criticality,          # Factor 0: Mission importance
            urgency,              # Factor 1: Deadline/queue wait pressure
            reversibility,        # Factor 2: Safe unwindability
            1.0 / risk_score,     # Factor 3: Safety inversed risk
            1.0 / verification_burden, # Factor 4: Verification agility
        ]

        # Composite guidance score for initial ordering only (never absolute authority)
        composite_rank = round((criticality * 0.35) + (urgency * 0.25) + (reversibility * 0.2) + ((1.0 / risk_score) * 0.2), 3)

        return {
            "intent_id": intent.intent_id,
            "vector": vector,
            "criticality": criticality,
            "urgency": urgency,
            "risk_score": risk_score,
            "scope_impact": scope_impact,
            "reversibility": reversibility,
            "verification_burden": verification_burden,
            "composite_rank": composite_rank,
            "explanation": (
                f"Criticality={criticality:.1f}, Urgency={urgency:.1f}, "
                f"Reversibility={reversibility:.2f}, RiskFactor={risk_score:.1f}"
            ),
        }

    def order_intents_fairly(self, intents: List[AgentEngineeringIntent]) -> List[AgentEngineeringIntent]:
        """Order intents considering starvation wait age and multidimensional priority."""
        scored = []
        for it in intents:
            vec_info = self.compute_priority_vector(it)
            # Add anti-starvation bonus based on wait_count
            starvation_boost = it.wait_count * 0.15
            effective_rank = vec_info["composite_rank"] + starvation_boost
            scored.append((effective_rank, it))

        # Sort descending by effective rank
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored]
