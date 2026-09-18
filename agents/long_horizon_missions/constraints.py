"""
JARVIS OS — Phase 67: Long-Horizon Autonomous Engineering Missions
Constraints Validation & Invariant Checking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Callable, Dict, List, Optional, Tuple


class ConstraintSeverity(str, Enum):
    HARD = "HARD"
    SOFT = "SOFT"
    GOVERNANCE = "GOVERNANCE"


@dataclass
class MissionConstraint:
    constraint_id: str
    description: str
    severity: ConstraintSeverity = ConstraintSeverity.HARD
    validator_name: str = "custom"
    parameters: Dict[str, Any] = field(default_factory=dict)
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "constraint_id": self.constraint_id,
            "description": self.description,
            "severity": self.severity.value,
            "validator_name": self.validator_name,
            "parameters": dict(self.parameters),
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MissionConstraint:
        return cls(
            constraint_id=data["constraint_id"],
            description=data["description"],
            severity=ConstraintSeverity(data.get("severity", "HARD")),
            validator_name=data.get("validator_name", "custom"),
            parameters=dict(data.get("parameters", {})),
            active=data.get("active", True),
        )


class ConstraintValidator:
    """Validates operational and architectural constraints against mission context."""

    def __init__(self, constraints: Optional[List[MissionConstraint]] = None):
        self._constraints: Dict[str, MissionConstraint] = {}
        if constraints:
            for c in constraints:
                self.add_constraint(c)

    def add_constraint(self, constraint: MissionConstraint) -> None:
        self._constraints[constraint.constraint_id] = constraint

    def get_constraint(self, constraint_id: str) -> Optional[MissionConstraint]:
        return self._constraints.get(constraint_id)

    def list_constraints(self) -> List[MissionConstraint]:
        return list(self._constraints.values())

    def check_constraints(self, context: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
        """
        Validates all active constraints.
        Returns: (all_passed, hard_violations, soft_warnings)
        """
        hard_violations: List[str] = []
        soft_warnings: List[str] = []

        for c in self._constraints.values():
            if not c.active:
                continue

            # Built-in constraint checks
            passed, msg = self._evaluate_single(c, context)
            if not passed:
                if c.severity == ConstraintSeverity.HARD:
                    hard_violations.append(f"[{c.constraint_id}] {msg}")
                else:
                    soft_warnings.append(f"[{c.constraint_id}] {msg}")

        all_passed = len(hard_violations) == 0
        return all_passed, hard_violations, soft_warnings

    def _evaluate_single(self, constraint: MissionConstraint, context: Dict[str, Any]) -> Tuple[bool, str]:
        p = constraint.parameters
        name = constraint.validator_name

        if name == "max_file_changes":
            max_changes = p.get("max_changes", 50)
            actual = context.get("file_changes_count", 0)
            if actual > max_changes:
                return False, f"File changes ({actual}) exceed limit ({max_changes})"

        elif name == "forbidden_paths":
            forbidden = p.get("paths", [".git", "node_modules", ".env"])
            touched = context.get("touched_files", [])
            for f in touched:
                for fb in forbidden:
                    if fb in f:
                        return False, f"Touched forbidden path: {f}"

        elif name == "architecture_boundary":
            allowed_modules = p.get("allowed_modules", [])
            if allowed_modules:
                target_module = context.get("target_module")
                if target_module and target_module not in allowed_modules:
                    return False, f"Module '{target_module}' outside allowed boundaries: {allowed_modules}"

        elif name == "zero_unresolved_contracts":
            unresolved = context.get("unresolved_contract_breaks", 0)
            if unresolved > 0:
                return False, f"Found {unresolved} unresolved contract breaks"

        return True, "OK"
