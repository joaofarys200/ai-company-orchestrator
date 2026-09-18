"""
JARVIS OS — Phase 66: Multi-Agent Engineering Coordination & Conflict Arbitration
Module: scheduler.py
CoordinationScheduler partitions candidate intents into verified parallel waves or serialized sequences.
Never assumes parallel safety merely because file paths differ.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from .claims import ClaimManager
from .conflicts import AgentConflictDetector
from .dependencies import CoordinationDependencyAnalyzer
from .models import (
    AgentConflict,
    AgentEngineeringIntent,
    ArbitrationResolution,
    ConflictType,
    SchedulingDecision,
)


class CoordinationScheduler:
    """Computes parallel waves and serial execution schedules."""

    def __init__(self, claim_manager: Optional[ClaimManager] = None):
        self.claim_manager = claim_manager or ClaimManager()
        self.dependency_analyzer = CoordinationDependencyAnalyzer()
        self.conflict_detector = AgentConflictDetector()

    def schedule_intents(
        self,
        intents: List[AgentEngineeringIntent],
    ) -> Dict[str, Any]:
        """Produce an execution schedule partitioning intents into safe parallel waves or serial steps."""
        if not intents:
            return {
                "decision": SchedulingDecision.PARALLEL_SAFE.value,
                "parallel_waves": [],
                "serial_queue": [],
                "conflicts": [],
                "is_dag": True,
            }

        # 1. Detect conflicts
        conflicts = self.conflict_detector.detect_conflicts(intents)
        critical_conflicts = [c for c in conflicts if c.conflict_type == ConflictType.SECURITY_CONFLICT]
        if critical_conflicts:
            return {
                "decision": SchedulingDecision.BLOCKED.value,
                "parallel_waves": [],
                "serial_queue": [],
                "conflicts": [c.to_dict() for c in critical_conflicts],
                "reason": "Security violation detected across candidate intents.",
                "is_dag": False,
            }

        # 2. Analyze causal dependencies & cycles
        dep_info = self.dependency_analyzer.build_dependency_graph(intents)
        if dep_info["has_cycle"]:
            return {
                "decision": SchedulingDecision.BLOCKED.value,
                "parallel_waves": [],
                "serial_queue": [],
                "conflicts": [c.to_dict() for c in conflicts],
                "reason": f"Cyclic dependency detected among intents: {dep_info['cycle_nodes']}",
                "is_dag": False,
            }

        # 3. If there are file/symbol/contract conflicts, serialize conflicting intents
        conflicted_pairs = {(c.intent_a, c.intent_b) for c in conflicts}
        conflicted_pairs.update({(c.intent_b, c.intent_a) for c in conflicts})

        # Refine parallel waves to ensure no pair within the same wave conflicts
        refined_waves: List[List[str]] = []
        for raw_wave in dep_info["parallel_waves"]:
            sub_waves: List[List[str]] = []
            for item in raw_wave:
                placed = False
                for sw in sub_waves:
                    if not any((item, existing) in conflicted_pairs for existing in sw):
                        sw.append(item)
                        placed = True
                        break
                if not placed:
                    sub_waves.append([item])
            refined_waves.extend(sub_waves)

        is_purely_parallel = (len(refined_waves) == 1 and len(refined_waves[0]) == len(intents))
        decision = SchedulingDecision.PARALLEL_SAFE if is_purely_parallel else SchedulingDecision.SERIAL_REQUIRED

        return {
            "decision": decision.value,
            "parallel_waves": refined_waves,
            "serial_queue": dep_info["topological_order"],
            "conflicts": [c.to_dict() for c in conflicts],
            "total_waves": len(refined_waves),
            "is_dag": True,
        }
