"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
Objectives Management & Objective Drift Guard (Integrating F57).
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.agents.long_horizon_missions.models import (
    MissionObjective,
    ObjectiveCategory,
    ObjectiveState,
)


class ObjectiveDriftError(Exception):
    """Raised when an unauthorized objective drift is detected."""
    pass


class ObjectiveTracker:
    """
    Manages primary and secondary objectives, invariants, and non-goals.
    Enforces that secondary objectives can never substitute primary objectives.
    Includes Objective Drift Guard (F57) to prevent autonomous scope creep or diversion.
    """

    def __init__(self, initial_objectives: Optional[List[MissionObjective]] = None):
        self._objectives: Dict[str, MissionObjective] = {}
        self._baseline_signatures: Dict[str, str] = {}
        self._objective_history: List[Dict[str, Any]] = []
        if initial_objectives:
            for obj in initial_objectives:
                self.add_objective(obj, is_baseline=True)

    def add_objective(self, obj: MissionObjective, is_baseline: bool = False) -> None:
        self._objectives[obj.objective_id] = obj
        if is_baseline or obj.objective_id not in self._baseline_signatures:
            self._baseline_signatures[obj.objective_id] = self._signature(obj)
        self._objective_history.append({
            "timestamp": time.time(),
            "action": "ADD_OR_UPDATE",
            "objective_id": obj.objective_id,
            "category": obj.category.value,
            "status": obj.status.value,
        })

    def get_objective(self, objective_id: str) -> Optional[MissionObjective]:
        return self._objectives.get(objective_id)

    def list_objectives(self, category: Optional[ObjectiveCategory] = None) -> List[MissionObjective]:
        if category:
            return [o for o in self._objectives.values() if o.category == category]
        return list(self._objectives.values())

    def update_status(self, objective_id: str, new_status: ObjectiveState, evidence_ref: Optional[str] = None) -> None:
        if objective_id not in self._objectives:
            raise KeyError(f"Objective {objective_id} not found")
        obj = self._objectives[objective_id]
        old_status = obj.status
        obj.status = new_status
        if evidence_ref:
            ev_list = obj.metadata.setdefault("evidence_refs", [])
            if evidence_ref not in ev_list:
                ev_list.append(evidence_ref)
        self._objective_history.append({
            "timestamp": time.time(),
            "action": "STATUS_CHANGE",
            "objective_id": objective_id,
            "old_status": old_status.value,
            "new_status": new_status.value,
            "evidence_ref": evidence_ref,
        })

    def are_primary_objectives_satisfied(self) -> Tuple[bool, List[str]]:
        """
        Validates all PRIMARY_OBJECTIVES.
        Secondary objectives cannot substitute primary objectives.
        """
        primaries = self.list_objectives(ObjectiveCategory.PRIMARY_OBJECTIVES)
        if not primaries:
            return False, ["NO_PRIMARY_OBJECTIVES_DEFINED"]

        unsatisfied = []
        for p in primaries:
            if p.status != ObjectiveState.SATISFIED:
                unsatisfied.append(p.objective_id)

        return len(unsatisfied) == 0, unsatisfied

    def are_invariants_satisfied(self) -> Tuple[bool, List[str]]:
        invariants = self.list_objectives(ObjectiveCategory.INVARIANTS)
        violated = []
        for inv in invariants:
            if inv.status in (ObjectiveState.BLOCKED, ObjectiveState.UNSATISFIED):
                violated.append(inv.objective_id)
        return len(violated) == 0, violated

    def evaluate_objective_drift(self, candidate_objective: MissionObjective) -> Tuple[bool, float, str]:
        """
        Objective Drift Guard (Integrating F57).
        Detects:
        - scope drift
        - requirement drift
        - architecture drift
        - quality drift
        - verification drift

        Example: objective 'reduce latency' cannot evolve autonomously to 'reduce components'.
        Returns: (has_drift, drift_score, reason)
        """
        baseline_sig = self._baseline_signatures.get(candidate_objective.objective_id)
        if not baseline_sig:
            return False, 0.0, "NEW_OBJECTIVE"

        curr_sig = self._signature(candidate_objective)
        if curr_sig == baseline_sig:
            return False, 0.0, "NO_DRIFT"

        # Semantic token comparison
        old_tokens = set(re.findall(r"\w+", baseline_sig.lower()))
        new_tokens = set(re.findall(r"\w+", curr_sig.lower()))
        intersection = old_tokens.intersection(new_tokens)
        union = old_tokens.union(new_tokens)
        jaccard = len(intersection) / max(1, len(union))
        drift_score = 1.0 - jaccard

        # Forbidden drift patterns: primary downgraded, invariants relaxed, or semantic mismatch
        reasons = []
        original = self._objectives.get(candidate_objective.objective_id)
        if original and original.category == ObjectiveCategory.PRIMARY_OBJECTIVES:
            if candidate_objective.category != ObjectiveCategory.PRIMARY_OBJECTIVES:
                reasons.append("FORBIDDEN_CATEGORY_DOWNGRADE")
                drift_score = 1.0

        if original and len(candidate_objective.measurable_conditions) < len(original.measurable_conditions):
            reasons.append("MEASURABLE_CONDITIONS_REMOVED")
            drift_score = max(drift_score, 0.75)

        if drift_score > 0.3:
            reasons.append(f"SEMANTIC_DRIFT_SCORE_{drift_score:.2f}")

        has_drift = len(reasons) > 0 or drift_score > 0.35
        reason_str = "; ".join(reasons) if reasons else "NO_MATERIAL_DRIFT"
        return has_drift, drift_score, reason_str

    def enforce_no_unauthorized_drift(self, updated_objective: MissionObjective) -> None:
        has_drift, score, reason = self.evaluate_objective_drift(updated_objective)
        if has_drift:
            raise ObjectiveDriftError(
                f"OBJECTIVE_CHANGE_REQUIRES_GOVERNANCE_REVIEW: Objective '{updated_objective.objective_id}' "
                f"exhibits material drift (score={score:.2f}, reason={reason}). "
                f"Secondary alternatives cannot replace primary invariants without human review."
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "objectives": {k: v.to_dict() for k, v in self._objectives.items()},
            "baseline_signatures": dict(self._baseline_signatures),
            "history_count": len(self._objective_history),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ObjectiveTracker:
        tracker = cls()
        for obj_dict in data.get("objectives", {}).values():
            obj = MissionObjective.from_dict(obj_dict)
            tracker.add_objective(obj, is_baseline=True)
        tracker._baseline_signatures = dict(data.get("baseline_signatures", {}))
        return tracker

    @staticmethod
    def _signature(obj: MissionObjective) -> str:
        tokens = [
            obj.objective_id,
            obj.description.strip().lower(),
            obj.category.value,
            ",".join(sorted(obj.measurable_conditions)),
            ",".join(sorted(obj.evidence_requirements)),
            ",".join(sorted(obj.verification_requirements)),
            str(obj.priority),
        ]
        return "::".join(tokens)
