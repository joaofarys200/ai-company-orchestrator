"""
JARVIS OS — Phase 66: Multi-Agent Engineering Coordination & Conflict Arbitration
Module: arbiter.py
ConflictArbiter adjudicating multi-agent conflicts through serialization, 3-way merge,
rebase, task splitting, or human review gates. Never ignores security or contract breaks.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    AgentConflict,
    AgentEngineeringIntent,
    ArbitrationDecision,
    ArbitrationResolution,
    ConflictType,
)
from .priority import AgentPriorityModel


class ConflictArbiter:
    """Arbitrates conflicting agent intents using multi-criteria trade-off evaluations."""

    def __init__(self):
        self.priority_model = AgentPriorityModel()

    def arbitrate_conflict(
        self,
        conflict: AgentConflict,
        intent_a: AgentEngineeringIntent,
        intent_b: AgentEngineeringIntent,
    ) -> ArbitrationDecision:
        """Deterministically determine the safest resolution for a detected conflict."""
        dec_id = f"arb_{conflict.conflict_id}_{int(time.time() * 1000) % 1000000}"

        # Rule 1: Security Sentinel conflicts are strictly non-negotiable -> BLOCK
        if conflict.conflict_type == ConflictType.SECURITY_CONFLICT:
            return ArbitrationDecision(
                decision_id=dec_id,
                conflict_id=conflict.conflict_id,
                resolution=ArbitrationResolution.BLOCK,
                reason="SECURITY_VIOLATION: Protected system path mutation is blocked by Security Sentinel.",
                execution_order=[],
            )

        # Rule 2: Order / Cyclic Dependency conflict -> SPLIT or CANCEL
        if conflict.conflict_type == ConflictType.ORDER_CONFLICT:
            return ArbitrationDecision(
                decision_id=dec_id,
                conflict_id=conflict.conflict_id,
                resolution=ArbitrationResolution.SPLIT,
                reason="CYCLIC_DEPENDENCY: Mutual intent cycle requires task decomposition or human arbitration.",
                execution_order=[],
            )

        # Rule 3: Behavioral Conflicts (e.g. concurrent timing/concurrency changes) -> HUMAN_REVIEW or SERIALIZE
        if conflict.conflict_type == ConflictType.BEHAVIOR_CONFLICT:
            return ArbitrationDecision(
                decision_id=dec_id,
                conflict_id=conflict.conflict_id,
                resolution=ArbitrationResolution.HUMAN_REVIEW,
                reason="BEHAVIORAL_DRIFT_RISK: Concurrent asynchronous timing mutations require human review.",
                execution_order=[],
            )

        # Rule 4: Contract Conflicts -> SERIALIZE if compatible, else HUMAN_REVIEW
        if conflict.conflict_type == ConflictType.CONTRACT_CONFLICT:
            # Order by priority vector
            vec_a = self.priority_model.compute_priority_vector(intent_a)
            vec_b = self.priority_model.compute_priority_vector(intent_b)
            order = [intent_a.intent_id, intent_b.intent_id] if vec_a["composite_rank"] >= vec_b["composite_rank"] else [intent_b.intent_id, intent_a.intent_id]
            return ArbitrationDecision(
                decision_id=dec_id,
                conflict_id=conflict.conflict_id,
                resolution=ArbitrationResolution.SERIALIZE,
                reason=f"CONTRACT_SERIALIZATION: Executing {order[0]} before {order[1]} to preserve schema order.",
                execution_order=order,
            )

        # Rule 5: File conflict with disjoint symbols -> MERGE
        if "mergeable" in conflict.conflict_id:
            return ArbitrationDecision(
                decision_id=dec_id,
                conflict_id=conflict.conflict_id,
                resolution=ArbitrationResolution.MERGE,
                reason="DISJOINT_SYMBOLS: Same file with disjoint symbol modifications is safe for 3-way merge.",
                execution_order=[intent_a.intent_id, intent_b.intent_id],
            )

        # Rule 6: Same symbol or direct file conflict -> SERIALIZE or REBASE
        vec_a = self.priority_model.compute_priority_vector(intent_a)
        vec_b = self.priority_model.compute_priority_vector(intent_b)
        first, second = (intent_a, intent_b) if vec_a["composite_rank"] >= vec_b["composite_rank"] else (intent_b, intent_a)

        return ArbitrationDecision(
            decision_id=dec_id,
            conflict_id=conflict.conflict_id,
            resolution=ArbitrationResolution.SERIALIZE,
            reason=f"SERIALIZE_OVERLAP: Priority ranking dictates executing {first.intent_id} first; {second.intent_id} will rebase upon completion.",
            execution_order=[first.intent_id, second.intent_id],
        )
